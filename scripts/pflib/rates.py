"""Historical rates: win rate, deal size, cycle length and pipeline creation, by source and by stage.

Win rates come from mature cohorts only: deals created long enough ago that nearly all have closed.
A plain won / (won + lost) over recent deals runs high, because losses are often closed out late and
recent deals that will lose are still open. See method/model.md.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from .data import stage_index, status
from .util import add_months, month_key, quantile, quarter_label, quarter_start

SHRINK_K = 10  # pseudo-deals pulling a small source's win rate toward the overall rate
MIN_SIZE_N = 10
MATURITY_QUANTILE = 0.95  # a cohort counts as mature once this share of closed deals would have closed  # below this many won deals, a source uses the overall deal size


def _shrunk(won: int, n: int, prior: float, k: int = SHRINK_K) -> float:
    return (won + k * prior) / (n + k) if (n + k) else prior


def isotonic_increasing(values: list[float], weights: list[float]) -> list[float]:
    """Pool-adjacent-violators: the closest non-decreasing sequence."""
    blocks = [[v, w, 1] for v, w in zip(values, weights)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] > blocks[i + 1][0]:
            v1, w1, c1 = blocks[i]
            v2, w2, c2 = blocks[i + 1]
            w = w1 + w2
            blocks[i] = [(v1 * w1 + v2 * w2) / w if w else (v1 + v2) / 2, w, c1 + c2]
            del blocks[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    out = []
    for v, _, c in blocks:
        out += [v] * c
    return out


def compute_rates(opps: list[dict], stages: dict, as_of: date, lookback_months: int = 24,
                  history: list[dict] | None = None, fy_start_month: int = 1) -> dict:
    start = add_months(as_of, -lookback_months)
    for o in opps:
        o["_status"] = status(o, stages)
    valid = [o for o in opps if not (o.get("close") and o["close"] < o["created"])]
    in_window = [o for o in valid if start <= o["created"] < as_of]

    # Maturity horizon: 95th percentile cycle of closed deals from the older half of the window,
    # which have had at least half the window to close.
    older_half = [o for o in in_window if o["created"] < add_months(as_of, -(lookback_months // 2))]
    closed_cycles = [(o["close"] - o["created"]).days for o in older_half
                     if o["_status"] in ("won", "lost") and o.get("close") and o["close"] <= as_of]
    horizon = round(quantile(closed_cycles, MATURITY_QUANTILE) or 180)
    horizon = min(horizon, lookback_months * 30 // 2)
    mature_end = as_of - timedelta(days=horizon)
    mature = [o for o in in_window if o["created"] < mature_end]

    def win_stats(rows):
        n = len(rows)
        w = sum(1 for o in rows if o["_status"] == "won")
        created_amt = sum(o.get("amount") or 0 for o in rows)
        won_amt = sum(o.get("amount") or 0 for o in rows if o["_status"] == "won")
        return n, w, created_amt, won_amt

    n_all, w_all, ca_all, wa_all = win_stats(mature)
    overall_wr = w_all / n_all if n_all else 0.0

    sources = sorted({o["source"] for o in valid if o.get("source")})
    by_src = defaultdict(list)
    for o in mature:
        by_src[o.get("source")].append(o)

    won_recent = [o for o in valid if o["_status"] == "won" and o.get("close") and add_months(as_of, -12) <= o["close"] < as_of]
    sizes_all = [o["amount"] for o in won_recent if o.get("amount")]
    won_cycle_rows = [o for o in valid if o["_status"] == "won" and o.get("close") and start <= o["close"] < as_of]
    cycles_all = sorted((o["close"] - o["created"]).days for o in won_cycle_rows)

    def size_stats(xs):
        return {"n": len(xs), "mean": round(sum(xs) / len(xs), 2) if xs else None,
                "median": round(quantile(xs, 0.5), 2) if xs else None}

    def cycle_stats(xs):
        return {"n": len(xs), "median": quantile(xs, 0.5), "p75": quantile(xs, 0.75), "p90": quantile(xs, 0.9)}

    # Pipeline creation: last 12 full months.
    first_month = add_months(date(as_of.year, as_of.month, 1), -12)
    months = [month_key(add_months(first_month, i)) for i in range(12)]
    created = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
    for o in valid:
        if first_month <= o["created"] < date(as_of.year, as_of.month, 1):
            cell = created[o.get("source") or "(untagged)"][month_key(o["created"])]
            cell[0] += 1
            cell[1] += o.get("amount") or 0

    src_out = {}
    for s in sources:
        n, w, ca, wa = win_stats(by_src.get(s, []))
        sz = [o["amount"] for o in won_recent if o.get("source") == s and o.get("amount")]
        cy = sorted((o["close"] - o["created"]).days for o in won_cycle_rows if o.get("source") == s)
        size = size_stats(sz)
        use_pooled_size = size["n"] < MIN_SIZE_N
        monthly = [created[s][m][0] for m in months]
        monthly_amt = [created[s][m][1] for m in months]
        src_out[s] = {
            "mature_n": n, "mature_won": w,
            "win_rate_raw": round(w / n, 4) if n else None,
            "win_rate": round(_shrunk(w, n, overall_wr), 4),
            "value_win_rate": round(wa / ca, 4) if ca else None,
            "deal_size": size,
            "deal_size_used": (size_stats(sizes_all)["mean"] if use_pooled_size else size["mean"]),
            "deal_size_pooled": use_pooled_size,
            "won_cycle_days": cycle_stats(cy) if cy else cycle_stats(cycles_all),
            "won_cycles": cy,
            "cycle_pooled": not cy,
            "created_per_month": round(sum(monthly) / 12, 2),
            "created_amount_per_month": round(sum(monthly_amt) / 12, 2),
            "created_by_month": dict(zip(months, monthly)),
        }

    # Quarterly cohort win rates feed the quarter-level swing in the forecast.
    q = defaultdict(lambda: [0, 0])
    for o in mature:
        qs = quarter_start(o["created"], fy_start_month)
        q[qs][0] += 1
        q[qs][1] += o["_status"] == "won"
    quarters = [{"quarter": quarter_label(k, fy_start_month), "n": v[0], "win_rate": round(v[1] / v[0], 4)}
                for k, v in sorted(q.items()) if v[0] >= 20]

    stage_rates = _stage_rates(mature, opps, stages, history, overall_wr)
    untagged_mature = len(by_src.get(None, []))
    for o in opps:
        o.pop("_status", None)
    return {
        "as_of": as_of.isoformat(), "lookback_months": lookback_months, "window_start": start.isoformat(),
        "maturity_horizon_days": horizon, "mature_cohort_end": mature_end.isoformat(),
        "overall": {
            "mature_n": n_all, "mature_won": w_all, "win_rate": round(overall_wr, 4),
            "value_win_rate": round(wa_all / ca_all, 4) if ca_all else None,
            "deal_size": size_stats(sizes_all), "won_cycle_days": cycle_stats(cycles_all), "won_cycles": cycles_all,
            "untagged_mature_n": untagged_mature,
        },
        "sources": src_out,
        "quarterly_win_rates": quarters,
        "stage_win_rates": stage_rates,
        "months": months,
    }


def _stage_rates(mature, opps, stages, history, overall_wr) -> dict:
    order = stages["order"]
    if history:
        reached = defaultdict(set)
        for h in history:
            if h["field"] == "stage" and h["new"] in order:
                reached[h["id"]].add(order.index(h["new"]))
        n = [0] * len(order)
        w = [0] * len(order)
        used = 0
        for o in mature:
            ks = set(reached.get(o["id"], set()))
            k = stage_index(o.get("stage"), stages)
            if k is not None:
                ks.add(k)
            if not ks:
                continue
            used += 1
            top = max(ks)
            for i in range(top + 1):  # reaching a later stage implies passing the earlier ones
                n[i] += 1
                w[i] += o["_status"] == "won"
        if used >= 50:
            raw = [w[i] / n[i] if n[i] else overall_wr for i in range(len(order))]
            fitted = isotonic_increasing(raw, n)
            return {"method": "stage history", "n_deals": used,
                    "by_stage": {st: {"reached": n[i], "won": w[i], "raw": round(raw[i], 4), "win_rate": round(fitted[i], 4)}
                                 for i, st in enumerate(order)}}
    probs = defaultdict(list)
    for o in opps:
        if o.get("stage") in order and o.get("probability") is not None:
            probs[o["stage"]].append(o["probability"])
    if len(probs) >= max(2, len(order) - 1):
        return {"method": "CRM probability (not calibrated)",
                "by_stage": {st: {"win_rate": round(quantile(probs[st], 0.5), 4) if probs.get(st) else None} for st in order}}
    return {"method": "overall win rate (no stage data)", "by_stage": {st: {"win_rate": round(overall_wr, 4)} for st in order}}
