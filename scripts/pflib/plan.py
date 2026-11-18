"""Pipeline plan: work back from bookings targets to the deals each source must create each month.

For each future quarter j:
  1. Expected bookings from deals already open, using the forecast's per-deal timing model.
  2. Gap_j = target_j - booked - expected from open deals.
  3. The gap is split across sources by mix (share of won bookings in the last 12 months, or the user's mix).
  4. For source s, one deal a month created during quarter i is expected to book
         a_s(i, j) = win rate x deal size x P(cycle lands the close in quarter j)
     in quarter j, from the source's own won-cycle distribution.
  5. The required pace for quarter j is the steady number of deals a month, created from now on, that books the
     source's share of the gap: n_s(j) = gap_s(j) / sum over i <= j of a_s(i, j).
     Each quarter's pace stands on its own: it answers "how many deals a month from today to hit that quarter".
     Solving quarter by quarter for a changing pace was tried and rejected: it swings between zero and several times
     the current pace, because undoing the spread of cycle lengths is unstable.

The current quarter usually needs far more creation than any team can add, because few deals created now close
before quarter end. The plan says so plainly instead of hiding it. See method/model.md.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from .data import status
from .forecast import ECDF, Model, open_deals
from .util import add_months, quarter_label, quarter_start

MIN_SOURCE_CYCLES = 30


def default_mix(opps: list[dict], stages: dict, rates: dict, as_of: date) -> dict:
    """Share of won bookings by source over the last 12 months, among tagged sources in the rates."""
    won = defaultdict(float)
    for o in opps:
        if (status(o, stages) == "won" and o.get("close") and add_months(as_of, -12) <= o["close"] < as_of
                and o.get("source") in rates["sources"]):
            won[o["source"]] += o.get("amount") or 0
    total = sum(won.values())
    return {s: round(v / total, 4) for s, v in sorted(won.items())} if total else {}


def creation_months(q_start: date, as_of: date) -> list[date]:
    """Months of a quarter in which deals can still be created (the as-of month counts)."""
    first_open = date(as_of.year, as_of.month, 1)
    return [m for m in (add_months(q_start, k) for k in range(3)) if m >= first_open]


def unit_bookings(won: ECDF, win_rate: float, size: float, q_create: date, as_of: date, q_close_start: date,
                  q_close_end: date) -> float:
    """Expected bookings in a close quarter from creating one deal a month during a creation quarter."""
    total = 0.0
    for m in creation_months(q_create, as_of):
        created = max(m + timedelta(days=15), as_of)
        lo = (q_close_start - created).days - 1
        hi = (q_close_end - created).days - 1
        if hi < 0:
            continue
        p = won.F(hi) - (won.F(lo) if lo >= 0 else 0.0)
        total += win_rate * size * max(0.0, p)
    return total


def plan(opps: list[dict], stages: dict, rates: dict, as_of: date, targets: list[float], fy_start_month: int = 1,
         mix: dict | None = None, lead_rates: dict | None = None, outlier_ids: set | None = None) -> dict:
    m = Model(rates, stages)
    outlier_ids = outlier_ids or set()
    user_mix = bool(mix)
    if mix:
        unknown = [k for k in mix if k not in rates["sources"]]
        if unknown:
            raise SystemExit(f"error: unknown source in mix: {', '.join(unknown)}. Known: {', '.join(rates['sources'])}")
    mix = mix or default_mix(opps, stages, rates, as_of)
    total_mix = sum(mix.values())
    mix = {s: w / total_mix for s, w in mix.items()} if total_mix else {}
    q0 = quarter_start(as_of, fy_start_month)
    qs = [add_months(q0, 3 * i) for i in range(len(targets))]
    opens = [o for o in open_deals(opps, stages, as_of) if o["id"] not in outlier_ids]

    quarters = []
    for i, (qstart, target) in enumerate(zip(qs, targets)):
        qend = add_months(qstart, 3)
        booked = 0.0
        if i == 0:
            booked = sum(o.get("amount") or 0 for o in opps
                         if status(o, stages) == "won" and o.get("close") and qstart <= o["close"] < as_of)
        from_open = sum((o.get("amount") or 0) * m.window_prob(o, as_of, max(qstart, as_of), qend) for o in opens)
        quarters.append({"quarter": quarter_label(qstart, fy_start_month), "start": qstart, "end": qend, "target": target,
                         "booked_to_date": round(booked, 2), "expected_from_open": round(from_open, 2),
                         "gap": round(max(0.0, target - booked - from_open), 2), "by_source": {}})

    pace = {}
    for s, w in mix.items():
        v = rates["sources"][s]
        won = ECDF(v["won_cycles"]) if len(v["won_cycles"]) >= MIN_SOURCE_CYCLES else ECDF(rates["overall"]["won_cycles"])
        size = v["deal_size_used"] or rates["overall"]["deal_size"]["mean"]
        wr = v["win_rate"]
        avg_created = (v["created_amount_per_month"] / v["created_per_month"]) if v["created_per_month"] else size
        n = []
        for j, q in enumerate(quarters):
            need = q["gap"] * w
            # Bookings in quarter j from creating one deal a month in every month from now through quarter j.
            per_unit = sum(unit_bookings(won, wr, size, quarters[i]["start"], as_of, q["start"], q["end"]) for i in range(j + 1))
            nj = need / per_unit if per_unit > 0 else 0.0
            n.append(nj)
            q["by_source"][s] = {
                "bookings_needed": round(need, 2),
                "deals_per_month": round(nj, 2),
                "pipeline_per_month": round(nj * avg_created, 2),
                "pace_ratio": round(nj / v["created_per_month"], 3) if v["created_per_month"] else None,
                "bookings_per_unit_pace": round(per_unit, 2),
            }
        cur = v["created_per_month"]
        ahead = n[1:] or n
        avg_req = sum(ahead) / len(ahead) if ahead else 0.0
        pace[s] = {"current_opps_per_month": cur,
                   "current_quarter_opps_per_month": round(n[0], 2) if n else 0.0,
                   "current_quarter_ratio": round(n[0] / cur, 3) if n and cur else None,
                   "later_quarters_opps_per_month": round(avg_req, 2),
                   "later_quarters_ratio": round(avg_req / cur, 3) if cur else None}
        if lead_rates and lead_rates.get(s):
            pace[s]["lead_to_opp_rate"] = lead_rates[s]
            pace[s]["later_quarters_leads_per_month"] = round(avg_req / lead_rates[s], 1)

    for q in quarters:
        q["start"], q["end"] = q["start"].isoformat(), q["end"].isoformat()
    return {
        "as_of": as_of.isoformat(), "mix": {s: round(w, 4) for s, w in mix.items()},
        "mix_source": "set by user" if user_mix else "share of won bookings, last 12 months",
        "quarters": quarters,
        "pace": pace,
        "untagged_note": rates["overall"]["untagged_mature_n"],
    }
