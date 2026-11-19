"""Quarter forecast: a Monte Carlo simulation of every open deal plus deals not yet created.

For each open deal the model asks: of past deals open at a month start in the same stage and age band, what share
were won within the window? Those shares come from monthly snapshots of the company's own history (rates.py),
shifted by the deal's source in odds. The win rate of deals that ever reached a stage is not used here: deals that
will lose tend to stall in early stages, so it overstates the odds for deals sitting there today. Rep close dates
are not used either; they are the least reliable field in most CRMs. Deals not created yet are simulated from each
source's recent creation rate, win rate and won-cycle distribution. See method/model.md.
"""
from __future__ import annotations

import bisect
import math
import random
from collections import defaultdict
from datetime import date

from .data import stage_index, status
from .rates import DAYS_PER_MONTH, age_bucket
from .util import add_months, quantile, quarter_label, quarter_start

MIN_SOURCE_CYCLES = 30  # below this many won cycles a source uses the overall distribution
DEFAULT_SIMS = 5000
SEED = 7


class ECDF:
    def __init__(self, xs):
        self.xs = sorted(xs)
        self.n = len(self.xs)

    def F(self, x: float) -> float:
        return bisect.bisect_right(self.xs, x) / self.n if self.n else 0.0

    def S(self, x: float) -> float:
        return 1.0 - self.F(x)


def _odds(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return p / (1 - p)


def _prob(o):
    return o / (1 + o)


def quarter_swing(rates: dict) -> float:
    """Spread of quarterly cohort win rates beyond what sample size explains, as a relative standard deviation."""
    q = rates.get("quarterly_win_rates") or []
    if len(q) < 3:
        return 0.0
    ps = [x["win_rate"] for x in q]
    mean = sum(ps) / len(ps)
    if mean <= 0:
        return 0.0
    var = sum((p - mean) ** 2 for p in ps) / (len(ps) - 1)
    sampling = sum(mean * (1 - mean) / x["n"] for x in q) / len(q)
    between = max(0.0, var - sampling)
    return round(math.sqrt(between) / mean, 4)


class Model:
    """Per-deal probabilities from measured rates."""

    def __init__(self, rates: dict, stages: dict):
        self.rates = rates
        self.stages = stages
        ov = rates["overall"]
        self.overall_wr = ov["win_rate"]
        self.won_all = ECDF(ov["won_cycles"])
        self.lost_all = ECDF(ov["lost_cycles"])
        self.won = {}
        self.lost = {}
        for s, v in rates["sources"].items():
            self.won[s] = ECDF(v["won_cycles"]) if len(v["won_cycles"]) >= MIN_SOURCE_CYCLES else self.won_all
            self.lost[s] = ECDF(v["lost_cycles"]) if len(v["lost_cycles"]) >= MIN_SOURCE_CYCLES else self.lost_all
        self.stage_wr = {st: v["win_rate"] for st, v in rates["stage_win_rates"]["by_stage"].items() if v.get("win_rate") is not None}
        self.stage_method = rates["snapshot"]["method"]
        self.snapshot = rates["snapshot"]

    def win_rate(self, o: dict) -> tuple[float, str]:
        src = self.rates["sources"].get(o.get("source"))
        src_wr = src["win_rate"] if src else self.overall_wr
        st = o.get("stage")
        if st in self.stage_wr and stage_index(st, self.stages) is not None:
            # Stage rate, shifted by how the deal's source compares with the overall rate (in odds).
            p = _prob(_odds(self.stage_wr[st]) * _odds(src_wr) / _odds(self.overall_wr))
            return p, "stage"
        return src_wr, "source"

    def cell(self, o: dict, age_days: int) -> str:
        cells = self.snapshot["cells"]
        st = o.get("stage") if stage_index(o.get("stage"), self.stages) is not None else None
        b = age_bucket(age_days)
        for key in (f"{st}|{b}", f"{st}|*", f"*|{b}", "*|*"):
            if not key.startswith("None") and key in cells:
                return key
        return "*|*"

    def cumulative(self, key: str, days: float) -> float:
        """P(won within `days` of the as-of date) for the cell, interpolated between whole months."""
        curve = [0.0] + self.snapshot["cells"][key]["cumulative"]
        x = max(0.0, days / DAYS_PER_MONTH)
        if x >= len(curve) - 1:
            return curve[-1]
        i = int(x)
        return curve[i] + (curve[i + 1] - curve[i]) * (x - i)

    def source_ratio(self, o: dict) -> float:
        src = self.rates["sources"].get(o.get("source"))
        return _odds(src["win_rate"]) / _odds(self.overall_wr) if src else 1.0

    def window_prob(self, o: dict, as_of: date, start: date, end: date) -> float:
        """P(deal is won with a close date in [start, end)), given it is open at as_of.

        From snapshot curves: what share of past deals in the same stage and age band, open at a past month start,
        were won within that many days. Shifted by the deal's source (in odds) and kept monotone.
        """
        key = self.cell(o, (as_of - o["created"]).days)
        r = self.source_ratio(o)
        lo = (start - as_of).days
        hi = (end - as_of).days
        if hi <= lo or hi <= 0:
            return 0.0
        c_hi = _prob(_odds(self.cumulative(key, hi)) * r)
        c_lo = _prob(_odds(self.cumulative(key, max(lo, 0))) * r) if lo > 0 else 0.0
        return max(0.0, c_hi - c_lo)

    def new_deal_rate(self, source: str) -> float:
        """Deals created per day by a source, from the last three full months."""
        v = self.rates["sources"][source]
        last3 = list(v["created_by_month"].values())[-3:]
        return sum(last3) / 3 / 30.44 if last3 else 0.0

    def new_deal_expected_wins(self, source: str, as_of: date, start: date, end: date) -> float:
        """Expected number of deals created from as_of onward that are won with a close in [start, end)."""
        v = self.rates["sources"][source]
        rate = self.new_deal_rate(source)
        won = self.won.get(source, self.won_all)
        total = 0.0
        for d in range((end - as_of).days):
            lo = max(-1, (start - as_of).days - d - 1)
            hi = (end - as_of).days - d - 1
            if hi >= 0:
                total += rate * v["win_rate"] * max(0.0, won.F(hi) - (won.F(lo) if lo >= 0 else 0.0))
        return total


def open_deals(opps: list[dict], stages: dict, as_of: date) -> list[dict]:
    return [o for o in opps if status(o, stages) == "open" and o["created"] < as_of]


def forecast(opps: list[dict], stages: dict, rates: dict, as_of: date, fy_start_month: int = 1,
             target: float | None = None, sims: int = DEFAULT_SIMS, seed: int = SEED, outlier_ids: set | None = None) -> dict:
    q0 = quarter_start(as_of, fy_start_month)
    q1 = add_months(q0, 3)
    m = Model(rates, stages)
    outlier_ids = outlier_ids or set()

    booked = sum(o.get("amount") or 0 for o in opps
                 if status(o, stages) == "won" and o.get("close") and q0 <= o["close"] < as_of)

    deals = []
    imputed = 0
    excluded_outliers = 0
    for o in open_deals(opps, stages, as_of):
        if o["id"] in outlier_ids:
            excluded_outliers += 1
            continue
        amt = o.get("amount")
        if not amt or amt <= 0:
            src = rates["sources"].get(o.get("source"))
            amt = src["deal_size_used"] if src else rates["overall"]["deal_size"]["mean"]
            imputed += 1
        pw = m.window_prob(o, as_of, as_of, q1)
        p, basis = m.win_rate(o)
        deals.append({"id": o["id"], "name": o.get("name"), "source": o.get("source"), "stage": o.get("stage"),
                      "amount": amt, "p_window": pw, "p_win": p, "basis": basis,
                      "forecast_category": o.get("forecast_category"), "rep_close": o.get("close"),
                      "age_days": (as_of - o["created"]).days})

    new_sources = {}
    for s, v in rates["sources"].items():
        lam = m.new_deal_expected_wins(s, as_of, as_of, q1)
        amounts = v["won_amounts"] or rates["overall"]["won_amounts"]
        if lam > 0 and amounts:
            new_sources[s] = (lam, amounts)

    swing = quarter_swing(rates)
    rng = random.Random(seed)
    totals = []
    by_source_sum = defaultdict(float)
    for _ in range(sims):
        mult = math.exp(swing * _gauss(rng) - swing * swing / 2) if swing else 1.0
        t = booked
        for d in deals:
            if rng.random() < min(1.0, d["p_window"] * mult):
                t += d["amount"]
                by_source_sum[d["source"] or "(untagged)"] += d["amount"]
        for s, (lam, amounts) in new_sources.items():
            for _ in range(_poisson(rng, lam * mult)):
                a = amounts[int(rng.random() * len(amounts))]
                t += a
                by_source_sum[f"{s}::new"] += a
        totals.append(t)

    totals.sort()
    exp_open = sum(d["amount"] * d["p_window"] for d in deals)
    exp_new = sum(lam * (sum(a) / len(a)) for lam, a in new_sources.values())
    by_source = defaultdict(lambda: {"open": 0.0, "new": 0.0})
    for d in deals:
        by_source[d["source"] or "(untagged)"]["open"] += d["amount"] * d["p_window"]
    for s, (lam, a) in new_sources.items():
        by_source[s]["new"] += lam * sum(a) / len(a)
    by_stage = defaultdict(lambda: {"deals": 0, "amount": 0.0, "expected": 0.0})
    for d in deals:
        b = by_stage[d["stage"] or "(none)"]
        b["deals"] += 1
        b["amount"] += d["amount"]
        b["expected"] += d["amount"] * d["p_window"]

    rep = defaultdict(float)
    for d in deals:
        if d["rep_close"] and q0 <= d["rep_close"] < q1 and d["forecast_category"]:
            rep[d["forecast_category"]] += d["amount"]

    out = {
        "as_of": as_of.isoformat(), "quarter": quarter_label(q0, fy_start_month),
        "quarter_start": q0.isoformat(), "quarter_end": q1.isoformat(),
        "sims": sims, "seed": seed, "swing": swing, "stage_method": m.stage_method,
        "booked_to_date": round(booked, 2),
        "open_deals": len(deals), "open_pipeline": round(sum(d["amount"] for d in deals), 2),
        "imputed_amounts": imputed, "excluded_outliers": excluded_outliers,
        "expected": round(booked + exp_open + exp_new, 2),
        "expected_from_open": round(exp_open, 2), "expected_from_new": round(exp_new, 2),
        "p10": round(quantile(totals, 0.1), 2), "p50": round(quantile(totals, 0.5), 2), "p90": round(quantile(totals, 0.9), 2),
        "target": target,
        "p_hit_target": round(sum(1 for t in totals if t >= target) / sims, 4) if target else None,
        "by_source": {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in sorted(by_source.items())},
        "by_stage": {st: {k: round(v, 2) if isinstance(v, float) else v for k, v in by_stage[st].items()}
                     for st in stages["order"] + sorted(k for k in by_stage if k not in stages["order"]) if st in by_stage},
        "rep_forecast_categories": {k: round(v, 2) for k, v in sorted(rep.items())},
        "top_deals": [{k: (v.isoformat() if isinstance(v, date) else (round(v, 4) if isinstance(v, float) else v))
                       for k, v in d.items()} for d in sorted(deals, key=lambda d: -d["amount"] * d["p_window"])[:10]],
    }
    return out


def _gauss(rng: random.Random) -> float:
    u1 = max(rng.random(), 1e-12)
    return math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * rng.random())


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 30:  # normal approximation keeps large sources fast
        return max(0, round(lam + math.sqrt(lam) * _gauss(rng)))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1
