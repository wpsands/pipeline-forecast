"""Markdown report. Sections appear when their inputs exist in the run folder."""
from __future__ import annotations

from .util import fmt_money, fmt_pct


def _days(x) -> str:
    return "n/a" if x is None else f"{x:.0f} days"


def render_integrity(c: dict) -> list[str]:
    found = [f for f in c["findings"] if f["count"]]
    lines = [
        "## Data integrity",
        "",
        f"{c['opportunities']:,} deals checked as of {c['as_of']}: {c['open']:,} open worth {fmt_money(c['open_pipeline'])}, "
        f"{c['won']:,} won. {len(found)} of {len(c['findings'])} checks found problems.",
        "",
    ]
    if c["confidence"] == "low":
        lines += [f"**Forecast confidence: low.** High-severity problems touch {fmt_pct(c['high_severity_share_of_open'])} "
                  "of open pipeline. The forecast still runs, but fix these first for a number to commit to.", ""]
    else:
        lines += [f"Forecast confidence: normal. High-severity problems touch {fmt_pct(c['high_severity_share_of_open'])} "
                  "of open pipeline.", ""]
    lines += ["| Severity | Check | Deals | Open pipeline touched | Share of open pipeline |", "|---|---|---|---|---|"]
    for f in c["findings"]:
        if f["id"] == "missing_amount":
            amt, share = "unknown", "unknown"
        else:
            amt, share = fmt_money(f["open_pipeline"]), fmt_pct(f["share_of_open_pipeline"], 1)
        lines.append(f"| {f['severity']} | {f['title']} | {f['count']:,} | {amt} | {share} |")
    lines.append("")
    for f in found:
        ex = ", ".join(f["examples"])
        lines += [f"**{f['title']}** ({f['severity']}). {f['why']} Examples: {ex}."]
        d = f.get("detail") or {}
        if f["id"] == "untagged_source":
            lines[-1] += (f" {fmt_pct(d['share_of_rows'], 1)} of deals and {fmt_pct(d['share_of_won_bookings'], 1)} "
                          "of won bookings have no usable source.")
        if f["id"] == "source_variants" and d.get("variants"):
            parts = ["; ".join(f"{k}" for k in sorted(v)) for v in d["variants"].values()]
            lines[-1] += " Spellings found: " + " | ".join(parts) + "."
        if f["id"] == "unknown_stage" and d.get("stages"):
            lines[-1] += " Stages: " + ", ".join(f"{k} ({v})" for k, v in d["stages"].items()) + "."
        if f["id"] == "aged_open" and d.get("p90_won_cycle_days"):
            lines[-1] += f" The 90th-percentile won cycle is {d['p90_won_cycle_days']} days."
        lines.append("")
    if not c["history_checked"]:
        lines += ["Stage skips and close-date pushes were not checked because no field-history export was provided.", ""]
    return lines


def render_rates(r: dict, labels: dict) -> list[str]:
    o = r["overall"]
    lines = [
        "## Historical rates",
        "",
        f"Win rates use deals created between {r['window_start']} and {r['mature_cohort_end']}. Deals created later are left out "
        f"because many have not closed yet: 95% of closed deals closed within {r['maturity_horizon_days']} days. "
        f"Deal size uses deals won in the last 12 months. Cycle length uses deals won in the last {r['lookback_months']} months.",
        "",
        f"Overall: {fmt_pct(o['win_rate'], 1)} of {o['mature_n']:,} deals won; average won deal {fmt_money(o['deal_size']['mean'])}; "
        f"median won cycle {_days(o['won_cycle_days']['median'])}.",
        "",
        "| Source | Deals in cohort | Win rate | Avg won deal | Median cycle | 90th pct cycle | New deals / month | New pipeline / month |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s, v in sorted(r["sources"].items(), key=lambda kv: -kv[1]["created_amount_per_month"]):
        wr = fmt_pct(v["win_rate"], 1) + ("*" if v["mature_n"] < 30 else "")
        size = fmt_money(v["deal_size_used"]) + ("*" if v["deal_size_pooled"] else "")
        cyc = v["won_cycle_days"]
        lines.append(f"| {labels.get(s, s)} | {v['mature_n']:,} | {wr} | {size} | {_days(cyc['median'])} | {_days(cyc['p90'])} | "
                     f"{v['created_per_month']:.1f} | {fmt_money(v['created_amount_per_month'])} |")
    lines += ["", "\\* Fewer than 30 deals in the cohort or fewer than 10 won deals: the rate is pulled toward the overall rate "
              "(win rate) or replaced by it (deal size).", ""]
    sr = r["stage_win_rates"]
    cells = (r.get("snapshot") or {}).get("cells", {})
    lines += ["### Win rate by stage", "",
              f"Two different numbers. The first is the share of deals that ever reached the stage and went on to win "
              f"({sr['method']}). The second is the share of deals sitting in the stage at a month start that were won within "
              "3 and within 12 months, measured from monthly snapshots. The forecast uses the second. Deals that will lose tend "
              "to stall in early stages, so early-stage deals in today's pipeline win less often than the first number suggests.", "",
              "| Stage | Reached it and won | Sitting in it, won within 3 months | Sitting in it, won within 12 months |",
              "|---|---|---|---|"]
    for st, v in sr["by_stage"].items():
        extra = f" ({v['reached']:,} deals)" if "reached" in v else ""
        c = cells.get(f"{st}|*")
        w3 = fmt_pct(c["cumulative"][2], 1) if c and len(c["cumulative"]) > 2 else "n/a"
        w12 = fmt_pct(c["cumulative"][-1], 1) if c else "n/a"
        lines.append(f"| {st} | {fmt_pct(v['win_rate'], 1)}{extra} | {w3} | {w12} |")
    lines.append("")
    if sr["method"].startswith("CRM probability"):
        lines += ["These are the CRM's stage probabilities, not measured rates. Provide a field-history export to measure them.", ""]
    q = r["quarterly_win_rates"]
    if len(q) >= 2:
        lines += ["Win rate by quarter created: " + ", ".join(f"{x['quarter']} {fmt_pct(x['win_rate'], 1)}" for x in q) + ".", ""]
    return lines


def _label(labels: dict, s: str | None) -> str:
    if s is None or s == "(untagged)":
        return "Untagged"
    return labels.get(s, s)


def render_summary(f: dict | None, pl: dict | None, bt: dict | None, checks: dict | None, labels: dict) -> list[str]:
    lines = ["## Summary", ""]
    if f:
        rng = f"{fmt_money(f['p10'])} to {fmt_money(f['p90'])}"
        line = f"- **{f['quarter']} forecast: {fmt_money(f['p50'])}** (likely range {rng}, 80% of simulated outcomes)."
        if f.get("target"):
            line += f" Chance of reaching the {fmt_money(f['target'])} target: {fmt_pct(f['p_hit_target'])}."
        lines.append(line)
        lines.append(f"- {fmt_money(f['expected_from_open'])} is expected from {f['open_deals']:,} open deals worth "
                     f"{fmt_money(f['open_pipeline'])}, and {fmt_money(f['expected_from_new'])} from deals not created yet."
                     + (f" {fmt_money(f['booked_to_date'])} is already booked this quarter." if f["booked_to_date"] else ""))
    if pl and pl["quarters"]:
        q = pl["quarters"][0]
        need = sum(v["current_quarter_opps_per_month"] for v in pl["pace"].values())
        cur = sum(v["current_opps_per_month"] for v in pl["pace"].values())
        line = f"- **{q['quarter']} gap after expected bookings from open deals: {fmt_money(q['gap'])}.**"
        if q["gap"] and cur:
            line += (f" Closing it with new deals alone would take about {need:,.0f} new deals a month, against {cur:,.0f} "
                     f"a month today ({need / cur:.1f}x), because few deals created now close this quarter.")
        lines.append(line)
        over = [(s, v) for s, v in pl["pace"].items() if v.get("later_quarters_ratio") and v["later_quarters_ratio"] > 1.05]
        later = ", ".join(x["quarter"] for x in pl["quarters"][1:])
        if len(pl["quarters"]) > 1 and over:
            parts = ", ".join(f"{_label(labels, s)} +{fmt_pct(v['later_quarters_ratio'] - 1)}"
                              for s, v in sorted(over, key=lambda kv: -kv[1]["later_quarters_ratio"]))
            lines.append(f"- For {later}, new deal creation must run above its current pace: {parts}.")
        elif len(pl["quarters"]) > 1:
            lines.append(f"- For {later}, every source's current pace of new deal creation covers the plan.")
    if bt and bt["quarters"]:
        lines.append(f"- **Backtest:** actual bookings fell inside the forecast range in {bt['inside_band']} of "
                     f"{len(bt['quarters'])} past quarters; the middle forecast was off by "
                     f"{fmt_pct(bt['mean_abs_p50_error'])} on average.")
    if checks:
        n_high = sum(1 for x in checks["findings"] if x["severity"] == "high" and x["count"])
        lines.append(f"- **Data confidence: {checks['confidence']}.** {n_high} high-severity checks found problems, touching "
                     f"{fmt_pct(checks['high_severity_share_of_open'])} of open pipeline. Details below.")
    lines.append("")
    return lines


def render_forecast(f: dict, labels: dict) -> list[str]:
    lines = [
        f"## {f['quarter']} forecast",
        "",
        f"As of {f['as_of']}. {f['sims']:,} simulated quarters. Each open deal is weighted by what happened to past deals "
        f"in the same stage and age band ({f['stage_method']}), adjusted for its source. Deals not created yet are "
        "simulated from each source's recent creation rate, win rate and cycle length. Rep close dates are not used.",
        "",
        "| Outcome | Bookings |",
        "|---|---|",
        f"| Low (P10) | {fmt_money(f['p10'])} |",
        f"| Middle (P50) | {fmt_money(f['p50'])} |",
        f"| High (P90) | {fmt_money(f['p90'])} |",
        f"| Expected | {fmt_money(f['expected'])} |",
    ]
    if f.get("target"):
        lines.append(f"| Chance of {fmt_money(f['target'])} or more | {fmt_pct(f['p_hit_target'])} |")
    lines += ["", "| Source | Expected from open deals | Expected from new deals | Total |", "|---|---|---|---|"]
    for s, v in sorted(f["by_source"].items(), key=lambda kv: -(kv[1]["open"] + kv[1]["new"])):
        lines.append(f"| {_label(labels, s)} | {fmt_money(v['open'])} | {fmt_money(v['new'])} | {fmt_money(v['open'] + v['new'])} |")
    lines += ["", "| Stage | Open deals | Open pipeline | Expected this quarter | Share of pipeline expected |",
              "|---|---|---|---|---|"]
    for st, v in f["by_stage"].items():
        share = v["expected"] / v["amount"] if v["amount"] else 0
        lines.append(f"| {st} | {v['deals']:,} | {fmt_money(v['amount'])} | {fmt_money(v['expected'])} | {fmt_pct(share)} |")
    rep = f.get("rep_forecast_categories") or {}
    if rep:
        lines += ["", "Reps' view, from forecast category on deals with a close date this quarter: "
                  + ", ".join(f"{k} {fmt_money(v)}" for k, v in rep.items())
                  + ". Compare Commit with the model's low case, and Commit plus Best Case with its middle case."]
    lines += ["", "Largest expected contributions:", "", "| Deal | Source | Stage | Amount | Chance this quarter |",
              "|---|---|---|---|---|"]
    for d in f["top_deals"]:
        lines.append(f"| {d['id']} | {_label(labels, d['source'])} | {d['stage'] or 'none'} | {fmt_money(d['amount'])} | "
                     f"{fmt_pct(d['p_window'])} |")
    notes = []
    if f["excluded_outliers"]:
        notes.append(f"{f['excluded_outliers']} deals flagged as amount outliers are left out until confirmed")
    if f["imputed_amounts"]:
        notes.append(f"{f['imputed_amounts']} open deals with no amount use their source's average won deal")
    if f["swing"]:
        notes.append(f"quarters swing together by about {fmt_pct(f['swing'])} in win rate, which widens the range")
    if notes:
        lines += ["", "Notes: " + "; ".join(notes) + "."]
    lines.append("")
    return lines


def render_plan(pl: dict, labels: dict) -> list[str]:
    lines = [
        "## Pipeline plan",
        "",
        "Works back from each quarter's target. The gap after expected bookings from open deals is split across sources by "
        f"{pl['mix_source']}: " + ", ".join(f"{_label(labels, s)} {fmt_pct(w)}" for s, w in pl["mix"].items()) + ".",
        "",
        "| Quarter | Target | Booked | Expected from open deals | Gap to fill with new pipeline |",
        "|---|---|---|---|---|",
    ]
    for q in pl["quarters"]:
        lines.append(f"| {q['quarter']} | {fmt_money(q['target'])} | {fmt_money(q['booked_to_date'])} | "
                     f"{fmt_money(q['expected_from_open'])} | {fmt_money(q['gap'])} |")
    lines += ["", "Deals each source must create per month, starting now and held steady, to hit each quarter's target "
              "(multiple of today's pace in brackets):", ""]
    lines += ["| Source | Created per month today | " + " | ".join(q["quarter"] for q in pl["quarters"]) + " |",
              "|---|---|" + "---|" * len(pl["quarters"])]
    for s in pl["mix"]:
        cells = []
        for q in pl["quarters"]:
            r = q["by_source"][s]
            ratio = f" ({r['pace_ratio']:.1f}x)" if r["pace_ratio"] is not None else ""
            cells.append(f"{r['deals_per_month']:.0f}{ratio}")
        lines.append(f"| {_label(labels, s)} | {pl['pace'][s]['current_opps_per_month']:.1f} | " + " | ".join(cells) + " |")
    lines += ["", "The same pace as pipeline created per month:", "",
              "| Source | " + " | ".join(q["quarter"] for q in pl["quarters"]) + " |", "|---|" + "---|" * len(pl["quarters"])]
    for s in pl["mix"]:
        lines.append(f"| {_label(labels, s)} | " + " | ".join(fmt_money(q["by_source"][s]["pipeline_per_month"]) for q in pl["quarters"]) + " |")
    leads = [(s, v) for s, v in pl["pace"].items() if v.get("later_quarters_leads_per_month")]
    if leads:
        lines += ["", "Leads needed after the current quarter: " + "; ".join(
            f"{_label(labels, s)} {v['later_quarters_leads_per_month']:,.0f} a month at {fmt_pct(v['lead_to_opp_rate'])} lead to deal"
            for s, v in leads) + "."]
    q = pl["quarters"][0]
    if q["gap"]:
        lines += ["", f"{q['quarter']}: few deals created now close before quarter end, so the current quarter's gap needs a "
                  "multiple of today's creation pace. Read that column as the size of the gap, not a plan. Close the current "
                  "quarter with the deals already open, and set the creation plan from the later quarters."]
    if pl.get("untagged_note"):
        lines += ["", f"Untagged deals ({pl['untagged_note']:,} in the win-rate cohort) are left out of the mix. "
                  "Tag sources to include them."]
    lines.append("")
    return lines


def render_backtest(bt: dict) -> list[str]:
    if not bt["quarters"]:
        return ["## Backtest", "", "Not enough history before the as-of date to backtest.", ""]
    lines = [
        "## Backtest",
        "",
        "The same model, rerun as of the first day of each past quarter using only what was known then, compared with what closed.",
        "",
        "| Quarter | Low (P10) | Middle (P50) | High (P90) | Actual | Inside range | Middle vs actual |",
        "|---|---|---|---|---|---|---|",
    ]
    for q in bt["quarters"]:
        err = "n/a" if q["p50_error"] is None else (("+" if q["p50_error"] >= 0 else "") + fmt_pct(q["p50_error"], 1))
        lines.append(f"| {q['quarter']} | {fmt_money(q['p10'])} | {fmt_money(q['p50'])} | {fmt_money(q['p90'])} | "
                     f"{fmt_money(q['actual'])} | {'yes' if q['inside_p10_p90'] else 'no'} | {err} |")
    lines += ["", f"{bt['note']} An 80% range should contain the actual result in about 8 of 10 quarters.", ""]
    return lines


def render_report(name: str, checks: dict | None, rates: dict | None, labels: dict, forecast: dict | None = None,
                  plan: dict | None = None, backtest: dict | None = None) -> str:
    lines = [f"# Pipeline forecast: {name}", ""]
    if forecast or plan:
        lines += render_summary(forecast, plan, backtest, checks, labels)
    if forecast:
        lines += render_forecast(forecast, labels)
    if plan:
        lines += render_plan(plan, labels)
    if backtest:
        lines += render_backtest(backtest)
    if checks:
        lines += render_integrity(checks)
    if rates:
        lines += render_rates(rates, labels)
    lines += ["Method: method/model.md. Integrity checks: method/integrity.md.", ""]
    return "\n".join(lines).rstrip() + "\n"
