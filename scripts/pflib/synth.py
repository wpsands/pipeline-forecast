"""Synthetic CRM data for a fictional B2B SaaS company, with known true rates and planted data problems.

Everything is generated from one seed using only random.random(), so output is identical across Python versions.
The truth (rates used to generate the data and every planted problem) is written to truth.json so tests can
check that the model recovers it.
"""
from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

from .util import add_months, write_json

AS_OF = date(2026, 10, 1)
START = date(2024, 4, 1)
SEED = 20261001

# name, opps created per month, true win rate, median deal size, median won cycle (days)
SOURCES = [
    ("Inbound Demo", 22, 0.28, 32000, 48),
    ("Outbound", 18, 0.14, 48000, 80),
    ("Partner", 7, 0.34, 60000, 95),
    ("Events", 9, 0.18, 38000, 70),
    ("Paid Search", 12, 0.20, 24000, 42),
]
SEASON = [0.9, 1.0, 1.1, 1.0, 1.0, 0.95, 0.85, 0.8, 1.05, 1.15, 1.1, 0.9]  # Jan..Dec
GROWTH = 0.015  # per month
STAGES = ["Discovery", "Qualification", "Solution", "Proposal", "Negotiation"]
STAGE_PROB = [10, 20, 40, 60, 80]
STAGE_AT = [0.0, 0.15, 0.35, 0.6, 0.8]  # share of the cycle elapsed when each stage is entered
LOST_EXIT = [0.35, 0.30, 0.18, 0.10, 0.07]  # last stage reached by lost deals
LOST_CYCLE_FACTOR = 1.3  # lost deals take longer to be closed out
FORECAST_CAT = ["Pipeline", "Pipeline", "Best Case", "Best Case", "Commit"]


class Rng:
    def __init__(self, seed: int):
        self.r = random.Random(seed)

    def u(self) -> float:
        return self.r.random()

    def normal(self) -> float:
        u1 = max(self.u(), 1e-12)
        return math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * self.u())

    def lognormal(self, med: float, sigma: float) -> float:
        return med * math.exp(sigma * self.normal())

    def poisson(self, lam: float) -> int:
        limit, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.u()
            if p <= limit:
                return k
            k += 1

    def randint(self, a: int, b: int) -> int:
        return a + int(self.u() * (b - a + 1))

    def choice(self, xs):
        return xs[int(self.u() * len(xs))]

    def sample(self, xs, k):
        pool = list(xs)
        out = []
        for _ in range(min(k, len(pool))):
            out.append(pool.pop(int(self.u() * len(pool))))
        return out


def true_stage_win_rates() -> dict:
    """P(win | deal reached stage k) implied by the generating parameters, per source."""
    reach_lost = [sum(LOST_EXIT[k:]) for k in range(len(STAGES))]
    out = {}
    for name, _, p, _, _ in SOURCES:
        out[name] = [round(p / (p + (1 - p) * reach_lost[k]), 4) for k in range(len(STAGES))]
    return out


def _fmt_us(d: date | None) -> str:
    return f"{d.month}/{d.day}/{d.year}" if d else ""


def generate(outdir: Path) -> dict:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rng = Rng(SEED)
    opps, history = [], []
    n = 0
    month = START
    m_index = 0
    while month < AS_OF:
        for name, per_month, p_win, size, cyc in SOURCES:
            lam = per_month * SEASON[month.month - 1] * (1 + GROWTH) ** m_index
            for _ in range(rng.poisson(lam)):
                n += 1
                days_in_month = (add_months(month, 1) - month).days
                created = month + timedelta(days=int(rng.u() * days_in_month))
                won = rng.u() < p_win
                if won:
                    cycle = max(7, round(rng.lognormal(cyc, 0.5)))
                    last_stage = len(STAGES) - 1
                else:
                    cycle = max(5, round(rng.lognormal(cyc * LOST_CYCLE_FACTOR, 0.6)))
                    x, acc, last_stage = rng.u(), 0.0, 0
                    for k, w in enumerate(LOST_EXIT):
                        acc += w
                        if x <= acc:
                            last_stage = k
                            break
                closed_on = created + timedelta(days=cycle)
                amount = round(rng.lognormal(size, 0.6), -2)
                oid = f"OPP-{n:05d}"
                entries = [(STAGES[k], created + timedelta(days=round(cycle * STAGE_AT[k]))) for k in range(last_stage + 1)]
                is_closed = closed_on <= AS_OF
                if is_closed:
                    stage = "Closed Won" if won else "Closed Lost"
                    close = closed_on
                    prob = 100 if won else 0
                    fc = "Closed" if won else "Omitted"
                    last_activity = closed_on - timedelta(days=rng.randint(0, 5))
                else:
                    reached = [e for e in entries if e[1] <= AS_OF]
                    stage = reached[-1][0]
                    k = STAGES.index(stage)
                    prob = STAGE_PROB[k]
                    fc = FORECAST_CAT[k]
                    # Reps estimate the close date; when the estimate passes they push it.
                    est = created + timedelta(days=max(14, round(rng.lognormal(cyc, 0.3))))
                    pushes = 0
                    while est < AS_OF:
                        new = est + timedelta(days=rng.randint(14, 45))
                        history.append({"id": oid, "field": "Close Date", "old": _fmt_us(est), "new": _fmt_us(new),
                                        "date": est + timedelta(days=rng.randint(0, 3))})
                        est, pushes = new, pushes + 1
                    close = est
                    last_activity = AS_OF - timedelta(days=rng.randint(0, 20))
                    entries = reached
                prev = ""
                for st, d in entries:
                    if d <= AS_OF:
                        history.append({"id": oid, "field": "Stage", "old": prev, "new": st, "date": d})
                        prev = st
                if is_closed:
                    history.append({"id": oid, "field": "Stage", "old": prev, "new": stage, "date": close})
                opps.append({
                    "id": oid, "name": f"Account {n:05d} new business", "account": f"Account {n:05d}",
                    "created": created, "close": close, "stage": stage, "amount": amount, "source": name,
                    "owner": f"AE {1 + int(rng.u() * 8):02d}", "fc": fc, "prob": prob,
                    "last_activity": last_activity, "type": "New Business", "won": won, "cycle": cycle,
                })
        month = add_months(month, 1)
        m_index += 1

    # A few expansion deals that a new-business filter should drop.
    for i in range(40):
        base = rng.choice(opps)
        n += 1
        opps.append(dict(base, id=f"OPP-{n:05d}", type="Expansion", name=f"{base['account']} expansion"))

    planted = _plant_problems(rng, opps, history, n)
    _write(outdir, opps, history)
    truth = {
        "as_of": AS_OF.isoformat(),
        "seed": SEED,
        "sources": {name: {"win_rate": p, "median_deal_size": size, "median_won_cycle_days": cyc,
                           "opps_per_month_at_start": per_month}
                    for name, per_month, p, size, cyc in SOURCES},
        "stage_win_rates": true_stage_win_rates(),
        "stages": STAGES,
        "planted": planted,
    }
    write_json(outdir / "truth.json", truth)
    return truth


def _open_new_business(opps):
    return [o for o in opps if o["type"] == "New Business" and o["stage"] in STAGES]


def _plant_problems(rng: Rng, opps: list[dict], history: list[dict], n: int) -> dict:
    planted = {}
    open_nb = _open_new_business(opps)
    used: set[str] = set()

    def pick(pool, k):
        picks = rng.sample([o for o in pool if o["id"] not in used], k)
        used.update(o["id"] for o in picks)
        return picks

    for o in pick(open_nb, 12):
        o["amount"] = None
    planted["missing_amount"] = sorted(o["id"] for o in opps if o["amount"] is None)

    for o in pick(open_nb, 5):
        o["close"] = None
    planted["missing_close_date"] = sorted(o["id"] for o in opps if o["close"] is None)

    for o in pick(open_nb, 10):
        o["close"] = AS_OF - timedelta(days=rng.randint(5, 60))
    planted["past_due"] = sorted(o["id"] for o in opps if o["stage"] in STAGES and o["close"] and o["close"] < AS_OF)

    for o in pick(open_nb, 3):
        o["amount"] = o["amount"] * 25
    planted["amount_outliers"] = sorted(o["id"] for o in opps if o["id"] in used and o["amount"] and o["amount"] > 400000)

    for o in pick(open_nb, 5):
        o["stage"] = "Stage 3 - Legacy"
    planted["unknown_stage"] = sorted(o["id"] for o in opps if o["stage"] == "Stage 3 - Legacy")

    dups = []
    for o in pick(open_nb, 4):
        n += 1
        d = dict(o, id=f"OPP-{n:05d}", created=o["created"] + timedelta(days=3),
                 amount=round(o["amount"] * 1.03, -2) if o["amount"] else None)
        opps.append(d)
        dups.append(sorted([o["id"], d["id"]]))
    planted["duplicates"] = dups

    closed = [o for o in opps if o["stage"] in ("Closed Won", "Closed Lost") and o["type"] == "New Business"]
    for o in pick(closed, 2):
        o["close"] = o["created"] - timedelta(days=rng.randint(3, 20))
    planted["close_before_created"] = sorted(o["id"] for o in opps if o["close"] and o["close"] < o["created"])

    pushed = []
    for o in pick(open_nb, 12):
        d = AS_OF - timedelta(days=120)
        for _ in range(4):
            history.append({"id": o["id"], "field": "Close Date", "old": _fmt_us(d), "new": _fmt_us(d + timedelta(days=30)),
                            "date": d})
            d += timedelta(days=30)
        pushed.append(o["id"])
    planted["repeated_close_pushes"] = sorted(pushed)

    for o in pick(open_nb, 25):
        o["last_activity"] = AS_OF - timedelta(days=rng.randint(45, 120))
    planted["stale_activity"] = sorted(o["id"] for o in opps if o["stage"] in STAGES and o["last_activity"]
                                       and (AS_OF - o["last_activity"]).days > 30)

    variants = {"Inbound Demo": ["inbound demo", "Inbound demo", "Inbound Demo "], "Paid Search": ["Paid search", "paid-search"]}
    var_ids = []
    for o in opps:
        if o["source"] in variants and rng.u() < 0.08:
            o["source"] = rng.choice(variants[o["source"]])
            var_ids.append(o["id"])
    planted["source_variants"] = {"Inbound Demo": sorted(set(variants["Inbound Demo"])),
                                  "Paid Search": sorted(set(variants["Paid Search"])), "rows": len(var_ids)}

    untagged = 0
    for o in opps:
        x = rng.u()
        if x < 0.05:
            o["source"], untagged = "Other", untagged + 1
        elif x < 0.07:
            o["source"], untagged = "", untagged + 1
    planted["untagged_rows"] = untagged
    return planted


def _write(outdir: Path, opps: list[dict], history: list[dict]) -> None:
    with open(outdir / "opportunities.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Opportunity ID", "Opportunity Name", "Account Name", "Created Date", "Close Date", "Stage",
                    "Amount", "Lead Source", "Opportunity Owner", "Forecast Category", "Probability (%)",
                    "Last Activity", "Type"])
        for o in sorted(opps, key=lambda o: o["id"]):
            w.writerow([o["id"], o["name"], o["account"], _fmt_us(o["created"]), _fmt_us(o["close"]), o["stage"],
                        "" if o["amount"] is None else f"{o['amount']:.2f}", o["source"], o["owner"], o["fc"],
                        o["prob"], _fmt_us(o["last_activity"]), o["type"]])
    with open(outdir / "field-history.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Opportunity ID", "Field / Event", "Old Value", "New Value", "Edit Date"])
        for h in sorted(history, key=lambda h: (h["id"], h["date"], h["field"])):
            w.writerow([h["id"], h["field"], h["old"], h["new"], _fmt_us(h["date"])])
