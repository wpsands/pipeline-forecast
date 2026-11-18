"""Backtest: rerun the forecast as of the start of past quarters, using only what was known then.

For each past quarter, the CRM is rebuilt as it stood on the first day:
- Deals created after that day are removed.
- Deals that closed later are reopened.
- Their stage is set from field history, or left unknown when there is no history; the current stage would leak the future.
- Close date, CRM probability and last activity are cleared.

Rates and the forecast are then recomputed from that view and compared with what actually closed. Amounts are the
current amounts, because exports do not carry amount history; the report says so.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from .data import status
from .forecast import forecast
from .rates import compute_rates
from .util import add_months, quarter_label, quarter_start


def view_as_of(opps: list[dict], history: list[dict], stages: dict, t: date) -> tuple[list[dict], list[dict]]:
    stage_at = {}
    if history:
        last = defaultdict(lambda: None)
        for h in sorted(history, key=lambda h: h["changed"]):
            if h["field"] == "stage" and h["changed"] <= t:
                last[h["id"]] = h["new"]
        stage_at = dict(last)
    view = []
    for o in opps:
        if o["created"] >= t:
            continue
        st = status(o, stages)
        if st in ("won", "lost") and o.get("close") and o["close"] < t:
            view.append(dict(o))
            continue
        v = dict(o, close=None, probability=None, last_activity=None)
        s = stage_at.get(o["id"])
        if s in stages["order"]:
            v["stage"] = s
        elif history:
            v["stage"] = stages["order"][0] if stages["order"] else None
        else:
            v["stage"] = None
        view.append(v)
    hist_t = [h for h in history if h["changed"] < t]
    return view, hist_t


def backtest(opps: list[dict], history: list[dict], stages: dict, as_of: date, fy_start_month: int = 1,
             lookback_months: int = 24, quarters: int = 4, sims: int = 2000, outlier_ids: set | None = None) -> dict:
    outlier_ids = outlier_ids or set()
    data_start = min(o["created"] for o in opps)
    current_q = quarter_start(as_of, fy_start_month)
    rows = []
    for i in range(quarters, 0, -1):
        t = add_months(current_q, -3 * i)
        if t < add_months(data_start, max(12, lookback_months // 2)):
            continue
        end = add_months(t, 3)
        view, hist_t = view_as_of(opps, history, stages, t)
        rates = compute_rates(view, stages, t, lookback_months, hist_t, fy_start_month)
        if not rates["sources"] or rates["overall"]["mature_n"] < 50:
            continue
        f = forecast(view, stages, rates, t, fy_start_month, sims=sims, outlier_ids=outlier_ids)
        actual = sum(o.get("amount") or 0 for o in opps
                     if o["id"] not in outlier_ids and status(o, stages) == "won" and o.get("close") and t <= o["close"] < end)
        rows.append({
            "quarter": quarter_label(t, fy_start_month), "as_of": t.isoformat(),
            "p10": f["p10"], "p50": f["p50"], "p90": f["p90"], "actual": round(actual, 2),
            "inside_p10_p90": f["p10"] <= actual <= f["p90"],
            "p50_error": round((f["p50"] - actual) / actual, 4) if actual else None,
            "stage_method": f["stage_method"],
        })
    errs = [abs(r["p50_error"]) for r in rows if r["p50_error"] is not None]
    return {
        "quarters": rows,
        "inside_band": sum(r["inside_p10_p90"] for r in rows),
        "mean_abs_p50_error": round(sum(errs) / len(errs), 4) if errs else None,
        "note": "Amounts are current amounts; exports carry no amount history.",
    }
