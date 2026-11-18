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
    lines += [f"### Win rate by stage reached", "", f"Method: {sr['method']}.", "",
              "| Stage | Win rate |", "|---|---|"]
    for st, v in sr["by_stage"].items():
        extra = f" ({v['reached']:,} reached it)" if "reached" in v else ""
        lines.append(f"| {st} | {fmt_pct(v['win_rate'], 1)}{extra} |")
    lines.append("")
    if sr["method"].startswith("CRM probability"):
        lines += ["These are the CRM's stage probabilities, not measured rates. Provide a field-history export to measure them.", ""]
    q = r["quarterly_win_rates"]
    if len(q) >= 2:
        lines += ["Win rate by quarter created: " + ", ".join(f"{x['quarter']} {fmt_pct(x['win_rate'], 1)}" for x in q) + ".", ""]
    return lines


def render_report(name: str, checks: dict | None, rates: dict | None, labels: dict, extra_top: list[str] | None = None) -> str:
    lines = [f"# Pipeline forecast: {name}", ""]
    if extra_top:
        lines += extra_top
    if checks:
        lines += render_integrity(checks)
    if rates:
        lines += render_rates(rates, labels)
    lines += ["Method: method/model.md. Integrity checks: method/integrity.md.", ""]
    return "\n".join(lines).rstrip() + "\n"
