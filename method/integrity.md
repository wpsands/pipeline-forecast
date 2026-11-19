# Data integrity checks

The checks run before any rate or forecast. Each one names the forecast number it would distort, and each finding is sized by the open pipeline it touches, so the report shows how much of the forecast is affected. The code is `scripts/pflib/checks.py`; this file and the code must agree.

## Checks

| Check | Severity | What it finds | What it distorts |
|---|---|---|---|
| Missing amount | high | Open or won deals with a blank or zero amount | Pipeline and bookings are understated; deal-size averages skip them |
| Missing close date | high | Deals with no close date | Open deals cannot be placed in a quarter; closed deals drop out of cycle history |
| Past-due close date | high | Open deals whose close date is before the as-of date | Timing. The forecast ignores these close dates and times the deal from its age |
| Close before created | high | Close date earlier than created date | Negative cycle times; excluded from cycle history |
| Unknown stage | high | A stage outside the confirmed stage order, won stages and lost stages | Stage-based win rates |
| Missing stage | high | Deals with no stage | Status. Treated as open |
| Amount outliers | medium | Amounts more than 3 interquartile ranges above the upper quartile, on a log scale, per source when the source has 30 or more amounts; also negative amounts | One typo can outweigh many real deals |
| Repeated close-date pushes | medium | Open deals pushed 3 or more times (needs field history) | Rep close dates on stalled deals |
| Untagged source | medium | Blank source or a catch-all such as Other, Unknown, None, N/A | Rates by source and the plan by source |
| Aged open deals | medium | Open deals older than twice the 90th-percentile won cycle | Coverage looks higher than the expected value behind it |
| Likely duplicates | medium | Same account, amounts within 10%, created within 14 days | Double-counted pipeline |
| Source spelled several ways | low | One source with several spellings, such as "Inbound Demo" and "inbound demo" | Reports that split one source. Merged automatically for the model |
| Stale activity | low | Open deals with no activity in 30 days (needs a last-activity column) | Usually stalled deals |
| Probability out of order | low | Median CRM probability falls at a later stage | Either the stage order or the probabilities are wrong |
| Skipped stages | low | Won deals that skipped a stage (needs field history) | Shows a stage that is not used or not enforced |

## Forecast confidence

Confidence is **low** when high-severity findings touch more than 20% of open pipeline, measured by dollars or by deal count, whichever is higher. Deal count matters because a deal with no amount carries no dollars. The forecast still runs at low confidence. The report says so first and lists what to fix.

## What the checks do not do

They never change the CRM. Merging spellings and ignoring past-due close dates happen only inside the model. The report lists the deals so the team can fix the source data.
