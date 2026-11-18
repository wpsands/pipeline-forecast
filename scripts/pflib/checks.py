"""Data integrity checks. Every finding is sized by the open pipeline it touches.

Checks run before any rate or forecast, because each problem biases a specific number:
missing amounts understate pipeline, past-due close dates distort timing, untagged sources break
the plan by source, and unknown stages break stage-based win rates.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date

from .data import UNTAGGED, stage_index, status
from .util import norm_key, quantile

HIGH, MEDIUM, LOW = "high", "medium", "low"
CONFIDENCE_THRESHOLD = 0.20  # share of open pipeline touched by high-severity findings that lowers confidence
STALE_ACTIVITY_DAYS = 30
PUSH_LIMIT = 3


def _finding(fid, group, title, severity, ids, opps_by_id, why, detail=None):
    ids = sorted(set(ids))
    open_amt = sum((opps_by_id[i].get("amount") or 0) for i in ids if opps_by_id[i]["_status"] == "open")
    return {"id": fid, "group": group, "title": title, "severity": severity, "count": len(ids),
            "open_pipeline": round(open_amt, 2), "examples": ids[:5], "ids": ids, "why": why, "detail": detail}


def run_checks(opps: list[dict], stages: dict, as_of: date, history: list[dict] | None = None) -> dict:
    history = history or []
    for o in opps:
        o["_status"] = status(o, stages)
    by_id = {o["id"]: o for o in opps}
    open_ = [o for o in opps if o["_status"] == "open"]
    won = [o for o in opps if o["_status"] == "won"]
    closed = [o for o in opps if o["_status"] in ("won", "lost")]
    total_open = sum(o.get("amount") or 0 for o in open_)
    F = []

    # ---- hygiene ----
    ids = [o["id"] for o in open_ + won if o.get("amount") is None or o.get("amount") == 0]
    F.append(_finding("missing_amount", "Hygiene", "Open or won deals with no amount", HIGH, ids, by_id,
                      "Pipeline and bookings are understated by these deals, and deal-size averages skip them."))
    ids = [o["id"] for o in opps if o.get("close") is None]
    F.append(_finding("missing_close_date", "Hygiene", "Deals with no close date", HIGH, ids, by_id,
                      "Open deals with no close date cannot be placed in a quarter; closed deals drop out of cycle-time history."))
    ids = [o["id"] for o in open_ if o.get("close") and o["close"] < as_of]
    F.append(_finding("past_due", "Hygiene", "Open deals with a close date in the past", HIGH, ids, by_id,
                      "The close date is no longer a forecast. The model ignores it and times these deals from their age."))
    ids = [o["id"] for o in opps if o.get("close") and o["close"] < o["created"]]
    F.append(_finding("close_before_created", "Hygiene", "Close date earlier than created date", HIGH, ids, by_id,
                      "Negative cycle times. These deals are left out of cycle-time history."))

    won_cycles = [(o["close"] - o["created"]).days for o in won if o.get("close") and o["close"] >= o["created"]]
    p90 = quantile(won_cycles, 0.9)
    ids = [o["id"] for o in open_ if p90 and (as_of - o["created"]).days > 2 * p90]
    F.append(_finding("aged_open", "Hygiene", "Open deals older than twice the 90th-percentile won cycle", MEDIUM, ids, by_id,
                      "Few deals this old ever close. They inflate coverage while adding little expected value.",
                      detail={"p90_won_cycle_days": round(p90) if p90 else None}))

    ids = [o["id"] for o in open_ if o.get("last_activity") and (as_of - o["last_activity"]).days > STALE_ACTIVITY_DAYS]
    if any(o.get("last_activity") for o in opps):
        F.append(_finding("stale_activity", "Hygiene", f"Open deals with no activity in {STALE_ACTIVITY_DAYS} days", LOW,
                          ids, by_id, "Usually stalled. Worth a review before the forecast call."))

    # Deal sizes are skewed and differ by source, so fences are set on a log scale, per source when the source
    # has at least 30 amounts: 3 interquartile ranges above the upper quartile.
    def fence(rows):
        logs = [math.log(o["amount"]) for o in rows if o.get("amount") and o["amount"] > 0]
        if len(logs) < 4:
            return None
        q1, q3 = quantile(logs, 0.25), quantile(logs, 0.75)
        return math.exp(q3 + 3 * (q3 - q1))

    sized = open_ + won
    hi = fence(sized)
    by_source = defaultdict(list)
    for o in sized:
        by_source[o.get("source")].append(o)
    fences = {k: (fence(v) if len(v) >= 30 else hi) for k, v in by_source.items()}
    ids = [o["id"] for o in sized if o.get("amount") is not None
           and (o["amount"] < 0 or ((fences.get(o.get("source")) or hi) and o["amount"] > (fences.get(o.get("source")) or hi)))]
    F.append(_finding("amount_outliers", "Hygiene", "Amounts far outside the normal range", MEDIUM, ids, by_id,
                      "Set per source on a log scale. One mistyped amount can move the forecast more than a dozen real deals. Confirm each one.",
                      detail={"upper_fence_overall": round(hi) if hi else None,
                              "upper_fence_by_source": {k or "(untagged)": round(v) for k, v in fences.items() if v}}))

    dup_pairs = _duplicates(open_ + won)
    F.append(_finding("duplicates", "Hygiene", "Likely duplicate deals", MEDIUM, [i for p in dup_pairs for i in p], by_id,
                      "Same account, amount within 10% and created within 14 days. Duplicates double count pipeline.",
                      detail={"pairs": dup_pairs[:20]}))

    # ---- source tagging ----
    ids = [o["id"] for o in opps if not o.get("source")]
    untagged_won = sum(o.get("amount") or 0 for o in won if not o.get("source"))
    total_won = sum(o.get("amount") or 0 for o in won)
    F.append(_finding("untagged_source", "Source tagging", "Deals with a blank or catch-all source", MEDIUM, ids, by_id,
                      "Rates by source and the plan by source exclude these deals. A high share means the plan by source is unreliable.",
                      detail={"share_of_rows": round(len(ids) / len(opps), 4) if opps else 0,
                              "share_of_won_bookings": round(untagged_won / total_won, 4) if total_won else 0,
                              "values_treated_as_untagged": sorted(v for v in UNTAGGED if v)}))
    spellings = defaultdict(Counter)
    for o in opps:
        if o.get("source"):
            spellings[o["source"]][o["source_raw"]] += 1
    variants = {k: dict(c) for k, c in spellings.items() if len(c) > 1}
    dominant = {k: c.most_common(1)[0][0] for k, c in spellings.items()}
    ids = [o["id"] for o in opps if o.get("source") in variants and o["source_raw"] != dominant[o["source"]]]
    F.append(_finding("source_variants", "Source tagging", "One source spelled several ways", LOW, ids, by_id,
                      "Counted here: deals not using the most common spelling. Merged automatically for this model. Fix in the CRM so reports agree.",
                      detail={"variants": variants}))

    # ---- stage definitions ----
    known = set(stages["order"]) | set(stages["won"]) | set(stages["lost"])
    ids = [o["id"] for o in opps if o.get("stage") and o["stage"] not in known]
    F.append(_finding("unknown_stage", "Stage definitions", "Deals in a stage outside the defined stage order", HIGH, ids, by_id,
                      "These deals cannot get a stage-based win rate. Map the stage or close the deal.",
                      detail={"stages": dict(Counter(by_id[i]["stage"] for i in ids))}))
    ids = [o["id"] for o in opps if not o.get("stage")]
    F.append(_finding("missing_stage", "Stage definitions", "Deals with no stage", HIGH, ids, by_id,
                      "Status cannot be determined. Treated as open."))

    probs = defaultdict(list)
    for o in open_:
        if o.get("probability") is not None and stage_index(o["stage"], stages) is not None:
            probs[o["stage"]].append(o["probability"])
    meds = [(st, quantile(probs[st], 0.5)) for st in stages["order"] if probs.get(st)]
    bad = [meds[i + 1][0] for i in range(len(meds) - 1) if meds[i + 1][1] < meds[i][1]]
    ids = [o["id"] for o in open_ if o["stage"] in bad]
    if meds:
        F.append(_finding("probability_order", "Stage definitions", "CRM probability falls at a later stage", LOW, ids, by_id,
                          "Stage probabilities should rise through the stage order. Either the order or the probabilities are wrong.",
                          detail={"median_probability_by_stage": {st: m for st, m in meds}}))

    if history:
        F += _history_checks(opps, by_id, stages, history)

    for f in F:
        f["share_of_open_pipeline"] = round(f["open_pipeline"] / total_open, 4) if total_open else 0
    high_ids = {i for f in F if f["severity"] == HIGH for i in f["ids"] if by_id[i]["_status"] == "open"}
    high_amt = sum(by_id[i].get("amount") or 0 for i in high_ids)
    # Deals with no amount carry no dollars; count them by share of open deals instead.
    high_share = max(high_amt / total_open if total_open else 0, len(high_ids) / len(open_) if open_ else 0)
    for o in opps:
        o.pop("_status", None)
    order = {HIGH: 0, MEDIUM: 1, LOW: 2}
    F.sort(key=lambda f: (f["count"] == 0, order[f["severity"]], -f["open_pipeline"], f["id"]))
    return {
        "as_of": as_of.isoformat(),
        "opportunities": len(opps), "open": len(open_), "open_pipeline": round(total_open, 2),
        "won": len(won), "closed": len(closed),
        "high_severity_share_of_open": round(high_share, 4),
        "confidence": "low" if high_share > CONFIDENCE_THRESHOLD else "normal",
        "history_checked": bool(history),
        "findings": F,
    }


def _duplicates(opps: list[dict]) -> list[list[str]]:
    by_acct = defaultdict(list)
    for o in opps:
        if o.get("account"):
            by_acct[norm_key(o["account"])].append(o)
    pairs = []
    for group in by_acct.values():
        group.sort(key=lambda o: o["created"])
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if (b["created"] - a["created"]).days > 14:
                    break
                x, y = a.get("amount"), b.get("amount")
                if x and y and abs(x - y) / max(x, y) <= 0.10:
                    pairs.append(sorted([a["id"], b["id"]]))
    return sorted(pairs)


def _history_checks(opps, by_id, stages, history) -> list[dict]:
    F = []
    seq = defaultdict(list)
    pushes = Counter()
    for h in history:
        if h["id"] not in by_id:
            continue
        if h["field"] == "stage":
            seq[h["id"]].append(h["new"])
        elif h["field"] == "close" and h.get("old") and h.get("new") and h["new"] > h["old"]:
            pushes[h["id"]] += 1
    order = stages["order"]
    skipped = []
    won_with_history = 0
    for o in opps:
        if o["_status"] != "won" or o["id"] not in seq:
            continue
        won_with_history += 1
        seen = {order.index(s) for s in seq[o["id"]] if s in order}
        if seen and any(k not in seen for k in range(min(seen), len(order))):
            skipped.append(o["id"])
    F.append(_finding("skipped_stages", "Stage definitions", "Won deals that skipped a stage", LOW, skipped, by_id,
                      "If many won deals skip a stage, the stage either is not used or is not defined clearly enough to enforce.",
                      detail={"share_of_won_with_history": round(len(skipped) / won_with_history, 4) if won_with_history else 0}))
    ids = [i for i, n in pushes.items() if n >= PUSH_LIMIT and by_id[i]["_status"] == "open"]
    F.append(_finding("repeated_close_pushes", "Hygiene", f"Open deals whose close date was pushed {PUSH_LIMIT} or more times",
                      MEDIUM, ids, by_id, "Repeated pushes usually mean the deal has stalled. The rep's close date is not a reliable signal here."))
    return F
