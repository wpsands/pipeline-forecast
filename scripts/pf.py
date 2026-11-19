#!/usr/bin/env python3
"""Pipeline Forecast Model: check CRM data, measure historical rates, plan pipeline and forecast the quarter.

Part of the pipeline-forecast plugin. Python 3.10+, standard library only. Read-only: it never writes to a CRM.

A run is a folder (default ./runs/<name>) holding:
  run.json        settings: as-of date, fiscal year start, lookback, stage order, column mapping
  opps.jsonl      opportunities from the CRM export, normalized
  history.jsonl   stage and close-date changes from a field-history export (optional)
  checks.json     written by `check`
  rates.json      written by `baseline`
  report.md       written by `report`

Commands:
  init RUN [--as-of YYYY-MM-DD] [--fy-start-month 1] [--lookback-months 24] [--name NAME]
  ingest RUN OPPS.csv [--map MAP.json] [--types "New Business,..."] [--day-first]
  history RUN HISTORY.csv [--map MAP.json] [--day-first]
  stages RUN [--order "A,B,C"] [--won "Closed Won"] [--lost "Closed Lost"]   show or confirm the stage order
  check RUN
  baseline RUN
  report RUN
  sample OUTDIR                   generate synthetic CRM data and run every step on it
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pflib import synth  # noqa: E402
from pflib.checks import run_checks  # noqa: E402
from pflib.data import Run, ingest, ingest_history  # noqa: E402
from pflib.rates import compute_rates  # noqa: E402
from pflib.report import render_report  # noqa: E402
from pflib.util import read_json, write_json  # noqa: E402


def _split(s: str | None) -> list[str] | None:
    return [x.strip() for x in s.split(",") if x.strip()] if s else None


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


def do_report(run: Run) -> Path:
    s = run.settings
    checks = do_check(run)
    rates = do_baseline(run)
    text = render_report(s["name"], checks, rates, s.get("source_labels", {}))
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

    run.settings  # validates the folder
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
        s = run.settings
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
    elif a.cmd == "report":
        print(f"wrote {do_report(run)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
