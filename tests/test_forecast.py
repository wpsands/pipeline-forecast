"""Tests for the quarter forecast, the pipeline plan and the backtest."""
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import pf  # noqa: E402
from pflib.backtest import view_as_of  # noqa: E402
from pflib.data import Run  # noqa: E402
from pflib.forecast import ECDF, Model, forecast, quarter_swing  # noqa: E402
from pflib.plan import plan  # noqa: E402
from pflib.rates import compute_rates  # noqa: E402
from test_pf import sample  # noqa: E402


def loaded():
    s = sample()
    run = Run(s["dir"] / "run")
    st = run.settings
    out = {i for f in s["checks"]["findings"] if f["id"] == "amount_outliers" for i in f["ids"]}
    return run, st, out


class Pieces(unittest.TestCase):
    def test_ecdf(self):
        e = ECDF([10, 20, 30, 40])
        self.assertEqual((e.F(5), e.F(20), e.F(100)), (0.0, 0.5, 1.0))
        self.assertEqual(e.S(20), 0.5)

    def test_quarter_swing(self):
        self.assertEqual(quarter_swing({"quarterly_win_rates": [{"win_rate": 0.2, "n": 100}] * 2}), 0.0)
        flat = [{"win_rate": 0.2, "n": 10000}] * 4
        self.assertEqual(quarter_swing({"quarterly_win_rates": flat}), 0.0)
        spread = [{"win_rate": r, "n": 10000} for r in (0.15, 0.25, 0.15, 0.25)]
        self.assertGreater(quarter_swing({"quarterly_win_rates": spread}), 0.2)

    def test_parse_money(self):
        self.assertEqual([pf.parse_money(x) for x in ("4000000", "$4,000,000", "4M", "4.2m", "750K")],
                         [4e6, 4e6, 4e6, 4.2e6, 750e3])
        with self.assertRaises(SystemExit):
            pf.parse_money("four million")


class ForecastModel(unittest.TestCase):
    def test_window_probabilities_are_consistent(self):
        run, st, _ = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        m = Model(rates, st["stages"])
        a = run.as_of
        for o in [o for o in run.opps() if o["stage"] in st["stages"]["order"]][:40]:
            q1 = m.window_prob(o, a, a, a + timedelta(days=92))
            q2 = m.window_prob(o, a, a + timedelta(days=92), a + timedelta(days=184))
            both = m.window_prob(o, a, a, a + timedelta(days=184))
            self.assertGreaterEqual(q1, 0)
            self.assertAlmostEqual(q1 + q2, both, places=6)
            self.assertLessEqual(both, 1)
            self.assertEqual(m.window_prob(o, a, a, a), 0.0)

    def test_later_stages_close_more_often(self):
        run, st, _ = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        m = Model(rates, st["stages"])
        a = run.as_of
        probe = {"created": a - timedelta(days=45), "source": None}
        ps = [m.window_prob(dict(probe, stage=s), a, a, a + timedelta(days=92)) for s in st["stages"]["order"]]
        self.assertEqual(ps, sorted(ps))

    def test_forecast_is_deterministic_and_centered(self):
        run, st, out = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        f1 = forecast(run.opps(), st["stages"], rates, run.as_of, sims=2000, outlier_ids=out)
        f2 = forecast(run.opps(), st["stages"], rates, run.as_of, sims=2000, outlier_ids=out)
        self.assertEqual(f1["p50"], f2["p50"])
        self.assertLess(abs(f1["p50"] / f1["expected"] - 1), 0.05)
        self.assertLess(f1["p10"], f1["p50"])
        self.assertLess(f1["p50"], f1["p90"])
        self.assertEqual(f1["excluded_outliers"], len(out))

    def test_outliers_would_inflate_the_forecast(self):
        run, st, out = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        kept = forecast(run.opps(), st["stages"], rates, run.as_of, sims=500)
        dropped = forecast(run.opps(), st["stages"], rates, run.as_of, sims=500, outlier_ids=out)
        self.assertGreater(kept["expected"], dropped["expected"])


class Backtest(unittest.TestCase):
    def test_view_as_of_does_not_leak_the_future(self):
        run, st, _ = loaded()
        t = date(2026, 1, 1)
        view, hist = view_as_of(run.opps(), run.history(), st["stages"], t)
        self.assertTrue(all(o["created"] < t for o in view))
        self.assertTrue(all(h["changed"] < t for h in hist))
        closed = st["stages"]["won"] + st["stages"]["lost"]
        for o in view:
            if o["stage"] in closed:
                self.assertLess(o["close"], t)
            else:
                self.assertIsNone(o["close"])
                self.assertIsNone(o["probability"])

    def test_sample_backtest_is_calibrated(self):
        b = json.loads((sample()["dir"] / "run" / "backtest.json").read_text())
        self.assertEqual(len(b["quarters"]), 6)
        self.assertGreaterEqual(b["inside_band"], 4)
        self.assertLess(b["mean_abs_p50_error"], 0.15)

    def test_reached_stage_rates_would_have_run_high(self):
        """The trap the snapshot curves avoid: deals sitting in early stages win less often than deals that ever reached them."""
        run, st, _ = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        reached = rates["stage_win_rates"]["by_stage"]["Discovery"]["win_rate"]
        sitting = rates["snapshot"]["cells"]["Discovery|*"]["cumulative"][-1]
        self.assertLess(sitting, reached * 0.75)


class Plan(unittest.TestCase):
    def test_pace_scales_with_the_gap(self):
        run, st, out = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        p1 = plan(run.opps(), st["stages"], rates, run.as_of, [4e6, 5e6], outlier_ids=out)
        p2 = plan(run.opps(), st["stages"], rates, run.as_of, [4e6, 10e6], outlier_ids=out)
        q1, q2 = p1["quarters"][1], p2["quarters"][1]
        for s in p1["mix"]:
            r = q2["gap"] / q1["gap"]
            self.assertAlmostEqual(q2["by_source"][s]["deals_per_month"], q1["by_source"][s]["deals_per_month"] * r, places=1)

    def test_no_gap_means_no_new_deals_needed(self):
        run, st, out = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        p = plan(run.opps(), st["stages"], rates, run.as_of, [1.0], outlier_ids=out)
        self.assertEqual(p["quarters"][0]["gap"], 0)
        self.assertTrue(all(v["deals_per_month"] == 0 for v in p["quarters"][0]["by_source"].values()))

    def test_far_quarter_pace_matches_steady_state(self):
        """A year out, the required pace approaches gap share / (win rate x deal size x 3 months)."""
        run, st, out = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        p = plan(run.opps(), st["stages"], rates, run.as_of, [4e6] * 5, outlier_ids=out)
        far = p["quarters"][-1]
        for s, w in p["mix"].items():
            v = rates["sources"][s]
            steady = far["gap"] * w / (v["win_rate"] * v["deal_size_used"] * 3)
            with self.subTest(source=s):
                self.assertLess(abs(far["by_source"][s]["deals_per_month"] / steady - 1), 0.12)

    def test_user_mix_and_unknown_source(self):
        run, st, out = loaded()
        rates = json.loads((run.root / "rates.json").read_text())
        p = plan(run.opps(), st["stages"], rates, run.as_of, [4e6], mix={"inbound demo": 3, "outbound": 1}, outlier_ids=out)
        self.assertEqual(p["mix"], {"inbound demo": 0.75, "outbound": 0.25})
        self.assertEqual(p["mix_source"], "set by user")
        with self.assertRaises(SystemExit):
            plan(run.opps(), st["stages"], rates, run.as_of, [4e6], mix={"carrier pigeon": 1})


class Cli(unittest.TestCase):
    def test_forecast_plan_backtest_commands(self):
        s = sample()
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "acme"
            pf.main(["init", str(run), "--as-of", "2026-10-01"])
            pf.main(["ingest", str(run), str(s["dir"] / "data" / "opportunities.csv"), "--types", "New Business"])
            pf.main(["history", str(run), str(s["dir"] / "data" / "field-history.csv")])
            pf.main(["stages", str(run), "--order", "Discovery,Qualification,Solution,Proposal,Negotiation",
                     "--won", "Closed Won", "--lost", "Closed Lost"])
            pf.main(["forecast", str(run), "--target", "3.6M", "--sims", "500"])
            pf.main(["plan", str(run), "--targets", "3.6M,3.8M", "--mix", "Inbound Demo=60,Outbound=40",
                     "--lead-rates", "Inbound Demo=25%"])
            pf.main(["backtest", str(run), "--quarters", "2"])
            pf.main(["report", str(run)])
            report = (run / "report.md").read_text()
            settings = json.loads((run / "run.json").read_text())
        self.assertEqual(settings["targets"], [3.6e6, 3.8e6])
        self.assertEqual(settings["lead_rates"], {"inbound demo": 0.25})
        for heading in ("## Summary", "## 2026 Q4 forecast", "## Pipeline plan", "## Backtest", "## Data integrity",
                        "## Historical rates"):
            self.assertIn(heading, report)
        self.assertIn("Leads needed after the current quarter", report)


if __name__ == "__main__":
    unittest.main()
