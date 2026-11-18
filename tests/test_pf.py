import json
import math
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import pf  # noqa: E402
from pflib import synth  # noqa: E402
from pflib.checks import run_checks  # noqa: E402
from pflib.data import Run, detect_mapping, infer_stages, ingest, normalize_source  # noqa: E402
from pflib.rates import _shrunk, compute_rates, isotonic_increasing  # noqa: E402
from pflib.util import add_months, parse_amount, parse_date, parse_probability, quantile, quarter_label, quarter_start  # noqa: E402

_SAMPLE = {}


def sample():
    """Builds the synthetic sample once per test run."""
    if not _SAMPLE:
        d = tempfile.mkdtemp()
        pf.build_sample(Path(d))
        _SAMPLE["dir"] = Path(d)
        _SAMPLE["truth"] = json.loads((Path(d) / "data" / "truth.json").read_text())
        _SAMPLE["checks"] = json.loads((Path(d) / "run" / "checks.json").read_text())
        _SAMPLE["rates"] = json.loads((Path(d) / "run" / "rates.json").read_text())
    return _SAMPLE


class Util(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(parse_date("2026-03-04"), date(2026, 3, 4))
        self.assertEqual(parse_date("3/4/2026"), date(2026, 3, 4))
        self.assertEqual(parse_date("3/4/2026", day_first=True), date(2026, 4, 3))
        self.assertEqual(parse_date("2026-03-04T13:22:00Z"), date(2026, 3, 4))
        self.assertEqual(parse_date("3/4/2026 1:22 PM"), date(2026, 3, 4))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date("soon"))

    def test_amounts_and_probability(self):
        self.assertEqual(parse_amount("$1,200.50"), 1200.5)
        self.assertEqual(parse_amount("(500)"), -500)
        self.assertEqual(parse_amount("USD 3,000"), 3000)
        self.assertIsNone(parse_amount(""))
        self.assertEqual(parse_probability("40%"), 0.4)
        self.assertEqual(parse_probability("0.4"), 0.4)

    def test_quantile_and_months(self):
        self.assertEqual(quantile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2026, 11, 15), 3), date(2027, 2, 15))

    def test_fiscal_quarters(self):
        self.assertEqual(quarter_start(date(2026, 11, 20)), date(2026, 10, 1))
        self.assertEqual(quarter_label(date(2026, 10, 1)), "2026 Q4")
        # February fiscal year start, named by the year it ends
        self.assertEqual(quarter_start(date(2026, 4, 10), 2), date(2026, 2, 1))
        self.assertEqual(quarter_label(date(2026, 2, 1), 2), "FY2027 Q1")
        self.assertEqual(quarter_label(date(2027, 1, 1), 2), "FY2027 Q4")


class Mapping(unittest.TestCase):
    def test_salesforce_headers(self):
        m = detect_mapping(["Opportunity ID", "Created Date", "Close Date", "Stage", "Amount", "Lead Source", "Probability (%)"])
        self.assertEqual(m["created"], "Created Date")
        self.assertEqual(m["source"], "Lead Source")
        self.assertEqual(m["probability"], "Probability (%)")

    def test_hubspot_headers(self):
        m = detect_mapping(["Record ID", "Deal Name", "Create Date", "Close Date", "Deal Stage", "Amount", "Original Source"])
        self.assertEqual(m["id"], "Record ID")
        self.assertEqual(m["stage"], "Deal Stage")
        self.assertEqual(m["source"], "Original Source")

    def test_source_normalization(self):
        self.assertEqual(normalize_source("Inbound Demo "), normalize_source("inbound-demo"))
        for v in ("", "Other", "unknown", "N/A", None):
            self.assertIsNone(normalize_source(v))

    def test_stage_inference_from_probability(self):
        opps = [{"stage": s, "probability": p} for s, p in
                [("Proposal", 0.6), ("Discovery", 0.1), ("Closed Won", 1), ("Closed Lost", 0), ("Solution", 0.4)]]
        st = infer_stages(opps)
        self.assertEqual(st["order"], ["Discovery", "Solution", "Proposal"])
        self.assertEqual((st["won"], st["lost"]), (["Closed Won"], ["Closed Lost"]))
        self.assertFalse(st["confirmed"])

    def test_ingest_filters_and_reports_skips(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "x.csv"
            csv_path.write_text(
                "Opportunity ID,Created Date,Close Date,Stage,Amount,Lead Source,Type\n"
                "A1,1/5/2026,3/1/2026,Closed Won,\"$10,000\",Webinar,New Business\n"
                "A2,,3/1/2026,Discovery,5000,Webinar,New Business\n"
                ",1/5/2026,3/1/2026,Discovery,5000,Webinar,New Business\n"
                "A3,1/9/2026,3/1/2026,Discovery,5000,Other,Expansion\n")
            run = Run(Path(d) / "run")
            pf.main(["init", str(run.root), "--as-of", "2026-04-01"])
            res = ingest(run, csv_path, types=["New Business"])
            self.assertEqual(res["kept"], 1)
            self.assertEqual(res["skipped"], {"created date missing or unreadable": 1, "no id": 1, "type filtered out": 1})
            o = run.opps()[0]
            self.assertEqual((o["amount"], o["source"], o["created"]), (10000.0, "webinar", date(2026, 1, 5)))


class Checks(unittest.TestCase):
    def test_every_planted_problem_is_found(self):
        s = sample()
        planted, found = s["truth"]["planted"], {f["id"]: set(f["ids"]) for f in s["checks"]["findings"]}
        for key in ("missing_amount", "missing_close_date", "past_due", "close_before_created", "unknown_stage",
                    "repeated_close_pushes", "stale_activity", "amount_outliers"):
            with self.subTest(key=key):
                self.assertTrue(set(planted[key]) <= found[key], key)
        self.assertEqual(sorted(s["truth"]["planted"]["duplicates"]),
                         next(f for f in s["checks"]["findings"] if f["id"] == "duplicates")["detail"]["pairs"])

    def test_no_false_outliers_or_duplicates(self):
        s = sample()
        found = {f["id"]: set(f["ids"]) for f in s["checks"]["findings"]}
        self.assertEqual(found["amount_outliers"], set(s["truth"]["planted"]["amount_outliers"]))
        self.assertEqual(found["duplicates"], {i for p in s["truth"]["planted"]["duplicates"] for i in p})

    def test_source_variants_and_untagged(self):
        s = sample()
        f = {x["id"]: x for x in s["checks"]["findings"]}
        v = f["source_variants"]["detail"]["variants"]
        self.assertEqual(set(v), {"inbound demo", "paid search"})
        self.assertGreater(f["untagged_source"]["count"], 0)

    def test_confidence_drops_when_high_severity_problems_are_widespread(self):
        stages = {"order": ["Discovery"], "won": ["Closed Won"], "lost": ["Closed Lost"]}
        opps = [{"id": f"o{i}", "created": date(2026, 1, 1), "close": None, "stage": "Discovery", "amount": 1000,
                 "source": "x", "source_raw": "x", "account": None} for i in range(10)]
        c = run_checks(opps, stages, date(2026, 4, 1))
        self.assertEqual(c["confidence"], "low")


class Rates(unittest.TestCase):
    def test_isotonic(self):
        self.assertEqual(isotonic_increasing([0.2, 0.5, 0.4, 0.8], [1, 1, 1, 1]), [0.2, 0.45, 0.45, 0.8])
        self.assertEqual(isotonic_increasing([0.1, 0.2], [5, 5]), [0.1, 0.2])

    def test_shrinkage_pulls_small_samples(self):
        self.assertAlmostEqual(_shrunk(3, 5, 0.2), (3 + 2) / 15)
        self.assertAlmostEqual(_shrunk(300, 1000, 0.2), (300 + 2) / 1010)

    def test_win_rates_recover_truth_within_three_standard_errors(self):
        s = sample()
        for name, t in s["truth"]["sources"].items():
            key = name.lower()
            r = s["rates"]["sources"][key]
            se = math.sqrt(t["win_rate"] * (1 - t["win_rate"]) / r["mature_n"])
            with self.subTest(source=name):
                self.assertLess(abs(r["win_rate_raw"] - t["win_rate"]), 3 * se)

    def test_stage_win_rates_recover_truth(self):
        s = sample()
        r = s["rates"]
        self.assertEqual(r["stage_win_rates"]["method"], "stage history")
        reach_lost = [sum(synth.LOST_EXIT[k:]) for k in range(len(synth.STAGES))]
        mix = {name.lower(): (t["win_rate"], r["sources"][name.lower()]["mature_n"]) for name, t in s["truth"]["sources"].items()}
        for k, st in enumerate(synth.STAGES):
            won = sum(n * p for p, n in mix.values())
            reached = sum(n * (p + (1 - p) * reach_lost[k]) for p, n in mix.values())
            expected = won / reached
            got = r["stage_win_rates"]["by_stage"][st]
            se = math.sqrt(expected * (1 - expected) / got["reached"])
            with self.subTest(stage=st):
                self.assertLess(abs(got["win_rate"] - expected), 3 * se + 0.01)

    def test_cycle_and_size_close_to_truth(self):
        """Medians of lognormal draws: standard error of log(median) is about 1.2533 * sigma / sqrt(n)."""
        s = sample()
        for name, t in s["truth"]["sources"].items():
            r = s["rates"]["sources"][name.lower()]
            cyc_se = 1.2533 * 0.5 / math.sqrt(r["won_cycle_days"]["n"])
            size_se = 1.2533 * 0.6 / math.sqrt(r["deal_size"]["n"])
            with self.subTest(source=name):
                self.assertLess(abs(math.log(r["won_cycle_days"]["median"] / t["median_won_cycle_days"])), 3 * cyc_se)
                self.assertLess(abs(math.log(r["deal_size"]["median"] / t["median_deal_size"])), 3 * size_se)

    def test_mature_cohort_avoids_late_loss_bias(self):
        """Wins close in 30 days, losses in 200. True win rate 25%. Recent closed deals look like 100% wins."""
        as_of = date(2026, 10, 1)
        stages = {"order": ["Open"], "won": ["Won"], "lost": ["Lost"]}
        opps = []
        for m in range(24):
            created = add_months(date(2024, 10, 1), m)
            for i in range(20):
                won = i < 5
                close = created + (timedelta(days=30) if won else timedelta(days=200))
                closed = close <= as_of
                stage = ("Won" if won else "Lost") if closed else "Open"
                opps.append({"id": f"{m}-{i}", "created": created, "close": close, "stage": stage, "amount": 1000.0,
                             "source": "web", "source_raw": "web"})
        recent = [o for o in opps if o["created"] >= add_months(as_of, -6) and o["stage"] != "Open"]
        naive = sum(o["stage"] == "Won" for o in recent) / len(recent)
        self.assertEqual(naive, 1.0)
        r = compute_rates(opps, stages, as_of)
        self.assertAlmostEqual(r["overall"]["win_rate"], 0.25, places=2)


class Sample(unittest.TestCase):
    def test_deterministic_and_plain(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ra = pf.build_sample(Path(a)).read_text()
            rb = pf.build_sample(Path(b)).read_text()
        self.assertEqual(ra, rb)
        self.assertNotIn("—", ra, "no em dashes in report copy")
        self.assertEqual(ra, (ROOT / "examples" / "sample-report.md").read_text())


if __name__ == "__main__":
    unittest.main()
