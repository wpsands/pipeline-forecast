#!/usr/bin/env python3
"""Pipeline Forecast Model: check CRM data, measure historical rates, plan pipeline and forecast the quarter.

Part of the pipeline-forecast plugin. Python 3.10+, standard library only. Read-only: it never writes to a CRM.

A run is a folder (default ./runs/<name>) holding:
  run.json        settings: as-of date, fiscal year start, lookback, stage order, column mapping, targets
  opps.jsonl      opportunities from the CRM export, normalized
  history.jsonl   stage and close-date changes from a field-history export (optional)
  checks.json     written by `check`
  rates.json      written by `baseline`
  forecast.json   written by `forecast`
  plan.json       written by `plan`
  backtest.json   written by `backtest`
  report.md       written by `report`

Commands:
  init RUN [--as-of YYYY-MM-DD] [--fy-start-month 1] [--lookback-months 24] [--name NAME]
  ingest RUN OPPS.csv [--map MAP.json] [--types "New Business,..."] [--day-first]
  history RUN HISTORY.csv [--map MAP.json] [--day-first]
  stages RUN [--order "A,B,C"] [--won "Closed Won"] [--lost "Closed Lost"]   show or confirm the stage order
  check RUN
  baseline RUN
  forecast RUN [--target 4M] [--sims 5000] [--keep-outliers]
  plan RUN --targets 4M,4.2M,4.5M,5M [--mix "Inbound Demo=40,Outbound=30,..."] [--lead-rates "Inbound Demo=25%"]
  backtest RUN [--quarters 4]
  report RUN                      rerun every step with the saved settings and write report.md
  sample OUTDIR                   generate synthetic CRM data and run every step on it
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pflib import synth  # noqa: E402
from pflib.backtest import backtest  # noqa: E402
from pflib.checks import run_checks  # noqa: E402
from pflib.data import Run, ingest, ingest_history, normalize_source  # noqa: E402
from pflib.forecast import DEFAULT_SIMS, forecast  # noqa: E402
from pflib.plan import plan  # noqa: E402
from pflib.rates import compute_rates  # noqa: E402
from pflib.report import render_report  # noqa: E402
from pflib.util import parse_probability, read_json, write_json  # noqa: E402

SAMPLE_TARGETS = [3_600_000, 3_800_000, 4_000_000, 4_200_000]


def _split(s: str | None) -> list[str] | None:
    return [x.strip() for x in s.split(",") if x.strip()] if s else None


def parse_money(s: str) -> float:
    """Accepts 4000000, $4,000,000, 4M, 4.2m, 750K."""
    t = str(s).strip().replace("$", "").replace(",", "").upper()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)([KMB]?)", t)
    if not m:
        raise SystemExit(f"error: cannot read amount {s!r}; use forms like 4000000, 4M or 750K")
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)]


def parse_pairs(s: str | None, value=float) -> dict | None:
    """'Inbound Demo=40, Outbound=30' -> {'inbound demo': 40.0, 'outbound': 30.0}"""
    if not s:
        return None
    out = {}
    for part in s.split(","):
        if "=" not in part:
            raise SystemExit(f"error: expected name=value, got {part.strip()!r}")
        k, v = part.split("=", 1)
        key = normalize_source(k)
        if not key:
            raise SystemExit(f"error: {k.strip()!r} is not a source name")
        out[key] = value(v)
    return out


def outlier_ids(run: Run, checks: dict) -> set:
    if run.settings.get("keep_outliers"):
        return set()
    return {i for f in checks["findings"] if f["id"] == "amount_outliers" for i in f["ids"]}


def do_check(run: Run) -> dict:
    s = run.settings
    c = run_checks(run.opps(), s["stages"], run.as_of, run.history())
    write_json(run.root / "checks.json", c)
    return c


def do_baseline(run: Run) -> dict:
    s = run.settings
    r = compute_rates(run.opps(), s["stages"], run.as_of, s.get("lookback_months", 24), run.history(),
                      s.get("fy_start_month", 1))
    write_json(run.root / "rates.json", r)
    return r


def do_forecast(run: Run, rates: dict, checks: dict) -> dict:
    s = run.settings
    targets = s.get("targets") or []
    f = forecast(run.opps(), s["stages"], rates, run.as_of, s.get("fy_start_month", 1),
                 target=targets[0] if targets else s.get("target"), sims=s.get("sims", DEFAULT_SIMS),
                 outlier_ids=outlier_ids(run, checks))
    write_json(run.root / "forecast.json", f)
    return f


def do_plan(run: Run, rates: dict, checks: dict) -> dict | None:
    s = run.settings
    if not s.get("targets"):
        return None
    p = plan(run.opps(), s["stages"], rates, run.as_of, s["targets"], s.get("fy_start_month", 1),
             mix=s.get("mix"), lead_rates=s.get("lead_rates"), outlier_ids=outlier_ids(run, checks))
    write_json(run.root / "plan.json", p)
    return p


def do_backtest(run: Run, checks: dict) -> dict:
    s = run.settings
    b = backtest(run.opps(), run.history(), s["stages"], run.as_of, s.get("fy_start_month", 1),
                 s.get("lookback_months", 24), s.get("backtest_quarters", 4), outlier_ids=outlier_ids(run, checks))
    write_json(run.root / "backtest.json", b)
    return b


def do_report(run: Run) -> Path:
    s = run.settings
    checks = do_check(run)
    rates = do_baseline(run)
    f = do_forecast(run, rates, checks)
    p = do_plan(run, rates, checks)
    b = do_backtest(run, checks)
    text = render_report(s["name"], checks, rates, s.get("source_labels", {}), f, p, b)
    out = run.root / "report.md"
    out.write_text(text)
    return out


def build_sample(outdir: Path) -> Path:
    outdir = Path(outdir)
    data = outdir / "data"
    synth.generate(data)
    run = Run(outdir / "run")
    run.root.mkdir(parents=True, exist_ok=True)
    write_json(run.root / "run.json", {"name": "Synthetic sample (fictional company)", "as_of": synth.AS_OF.isoformat(),
                                       "fy_start_month": 1, "lookback_months": 24})
    ingest(run, data / "opportunities.csv", types=["New Business"])
    ingest_history(run, data / "field-history.csv")
    s = run.settings
    s["stages"] = {"order": list(synth.STAGES), "won": ["Closed Won"], "lost": ["Closed Lost"],
                   "method": "confirmed by user", "confirmed": True}
    s["targets"] = SAMPLE_TARGETS
    s["backtest_quarters"] = 6
    run.save_settings(s)
    return do_report(run)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pf", description="Pipeline Forecast Model")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("run"); p.add_argument("--as-of")
    p.add_argument("--fy-start-month", type=int, default=1); p.add_argument("--lookback-months", type=int, default=24)
    p.add_argument("--name")
    p = sub.add_parser("ingest"); p.add_argument("run"); p.add_argument("file"); p.add_argument("--map")
    p.add_argument("--types"); p.add_argument("--day-first", action="store_true")
    p = sub.add_parser("history"); p.add_argument("run"); p.add_argument("file"); p.add_argument("--map")
    p.add_argument("--day-first", action="store_true")
    p = sub.add_parser("stages"); p.add_argument("run"); p.add_argument("--order"); p.add_argument("--won")
    p.add_argument("--lost")
    for name in ("check", "baseline", "report"):
        p = sub.add_parser(name); p.add_argument("run")
    p = sub.add_parser("forecast"); p.add_argument("run"); p.add_argument("--target")
    p.add_argument("--sims", type=int); p.add_argument("--keep-outliers", action="store_true")
    p = sub.add_parser("plan"); p.add_argument("run"); p.add_argument("--targets", required=True)
    p.add_argument("--mix"); p.add_argument("--lead-rates"); p.add_argument("--keep-outliers", action="store_true")
    p = sub.add_parser("backtest"); p.add_argument("run"); p.add_argument("--quarters", type=int)
    p = sub.add_parser("sample"); p.add_argument("outdir")
    a = ap.parse_args(argv)

    if a.cmd == "sample":
        out = build_sample(Path(a.outdir))
        print(f"sample written; report at {out}")
        return 0

    run = Run(Path(a.run))
    if a.cmd == "init":
        run.root.mkdir(parents=True, exist_ok=True)
        if (run.root / "run.json").exists():
            print(f"error: {run.root} already has a run.json", file=sys.stderr)
            return 1
        if not 1 <= a.fy_start_month <= 12:
            print("error: --fy-start-month must be 1 to 12", file=sys.stderr)
            return 1
        write_json(run.root / "run.json", {"name": a.name or run.root.name,
                                           "as_of": a.as_of or date.today().isoformat(),
                                           "fy_start_month": a.fy_start_month, "lookback_months": a.lookback_months})
        print(f"run created at {run.root}")
        return 0

    s = run.settings  # validates the folder
    if a.cmd == "ingest":
        mapping = read_json(Path(a.map)) if a.map else None
        res = ingest(run, Path(a.file), mapping, a.day_first, _split(a.types))
        print(f"read {res['rows']:,} rows, kept {res['kept']:,}")
        for k, v in res["skipped"].items():
            print(f"  skipped {v:,}: {k}")
        print("columns: " + ", ".join(f"{k} <- {v!r}" for k, v in res["mapping"].items()))
        if res["unmapped_required"]:
            print("not found (checks will flag them): " + ", ".join(res["unmapped_required"]))
        tv = run.settings.get("type_values") or {}
        if len(tv) > 1 and not a.types:
            print(f"deal types found: {tv}. To model new business only, re-run with --types")
        st = run.settings["stages"]
        print(f"stages ({st['method']}, not yet confirmed): {' > '.join(st['order'])} | won: {st['won']} | lost: {st['lost']}")
    elif a.cmd == "history":
        mapping = read_json(Path(a.map)) if a.map else None
        res = ingest_history(run, Path(a.file), mapping, a.day_first)
        print(f"read {res['rows']:,} rows: {res['stage_changes']:,} stage changes, {res['close_date_changes']:,} close-date changes")
        st = run.settings["stages"]
        if not st.get("confirmed"):
            print(f"stages ({st['method']}): {' > '.join(st['order'])}")
    elif a.cmd == "stages":
        st = s["stages"]
        if a.order or a.won or a.lost:
            st["order"] = _split(a.order) or st["order"]
            st["won"] = _split(a.won) or st["won"]
            st["lost"] = _split(a.lost) or st["lost"]
            st["confirmed"] = True
            st["method"] = "confirmed by user"
            run.save_settings(s)
        print(json.dumps(st, indent=2))
    elif a.cmd == "check":
        c = do_check(run)
        print(f"{sum(1 for f in c['findings'] if f['count'])} checks found problems; confidence {c['confidence']}; wrote checks.json")
    elif a.cmd == "baseline":
        r = do_baseline(run)
        print(f"overall win rate {r['overall']['win_rate']:.1%} over {r['overall']['mature_n']:,} mature deals; wrote rates.json")
    elif a.cmd == "forecast":
        if a.target:
            s["target"] = parse_money(a.target)
        if a.sims:
            s["sims"] = a.sims
        if a.keep_outliers:
            s["keep_outliers"] = True
        run.save_settings(s)
        checks = do_check(run)
        f = do_forecast(run, do_baseline(run), checks)
        line = f"{f['quarter']}: P10 ${f['p10']:,.0f}, P50 ${f['p50']:,.0f}, P90 ${f['p90']:,.0f}"
        if f["target"]:
            line += f"; chance of ${f['target']:,.0f}: {f['p_hit_target']:.0%}"
        print(line + "; wrote forecast.json")
    elif a.cmd == "plan":
        s["targets"] = [parse_money(x) for x in _split(a.targets)]
        s["mix"] = parse_pairs(a.mix)
        s["lead_rates"] = parse_pairs(a.lead_rates, parse_probability)
        if a.keep_outliers:
            s["keep_outliers"] = True
        run.save_settings(s)
        checks = do_check(run)
        p = do_plan(run, do_baseline(run), checks)
        for q in p["quarters"]:
            print(f"{q['quarter']}: target ${q['target']:,.0f}, expected from open deals ${q['expected_from_open']:,.0f}, gap ${q['gap']:,.0f}")
        print("wrote plan.json")
    elif a.cmd == "backtest":
        if a.quarters:
            s["backtest_quarters"] = a.quarters
            run.save_settings(s)
        b = do_backtest(run, do_check(run))
        for q in b["quarters"]:
            print(f"{q['quarter']}: P10 ${q['p10']:,.0f}  P50 ${q['p50']:,.0f}  P90 ${q['p90']:,.0f}  actual ${q['actual']:,.0f}")
        print(f"inside range {b['inside_band']} of {len(b['quarters'])}; wrote backtest.json")
    elif a.cmd == "report":
        print(f"wrote {do_report(run)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
