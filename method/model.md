# Model

How the model turns a CRM export into historical rates. The pipeline plan, the quarter forecast and the backtest are added in the next release. The code is in `scripts/pflib/`; this file and the code must agree.

## Inputs

- **Opportunity export (required).** One row per deal: id, created date, close date, stage, amount, source. Optional: name, account, owner, forecast category, CRM probability, last activity date, type. Column names from Salesforce and HubSpot exports are recognized automatically; a mapping file covers anything else.
- **Field-history export (optional, recommended).** One row per change to stage or close date: id, field, old value, new value, date. A Salesforce "Opportunity Field History" report has this shape. With it, win rates by stage are measured instead of taken from CRM probabilities, and the integrity checks cover close-date pushes and skipped stages.
- **Settings.** As-of date, fiscal year start month, lookback (24 months by default), deal types to include (new business only is recommended), and the stage order, which the user confirms.

## Win rate: mature cohorts only

A common shortcut is won ÷ (won + lost) over recently closed deals. It runs high for two reasons:
- Losses are often closed out later than wins, so recent closed deals skew toward wins.
- Recent deals that will eventually lose are still open, so they are left out.

The test suite includes a constructed case where the shortcut shows 100% against a true 25%.

The model uses mature cohorts instead:

1. Take closed deals created in the older half of the lookback window. These have had at least a year to close.
2. The maturity horizon is the 95th percentile of their cycle length, created to closed.
3. The mature cohort is every deal created in the lookback window at least one horizon before the as-of date.
4. Win rate = won ÷ all deals in the cohort. Deals still open in the cohort count as not won. By construction they are older than 95% of closed cycles.

**Small sources.** A source's rate is pulled toward the overall rate with 10 pseudo-deals: (won + 10 × overall) ÷ (deals + 10). This matters only for sources with few deals. The report marks sources with fewer than 30 deals in the cohort.

**Value win rate.** Won amount ÷ created amount for the same cohort. It is reported alongside, because large deals often win at a different rate.

## Deal size and cycle length

- **Deal size:** the mean amount of deals won in the last 12 months, by source. Sources with fewer than 10 won deals use the overall mean.
- **Cycle length:** created date to close date for deals won in the lookback window, by source. The model keeps the full distribution, not only the median, because the forecast needs the shape.

## Pipeline creation

Deals and pipeline created per month by source, over the last 12 full months. Untagged deals are shown as their own row.

## Win rate by stage reached

- **With field history.** For each stage: of mature-cohort deals that reached it, the share that won. Reaching a later stage counts as passing the earlier ones. Small samples can make a later stage look worse than an earlier one, so the rates are fitted to a non-decreasing sequence (pool-adjacent-violators) weighted by deal count.
- **Without field history.** The CRM's own stage probabilities, labeled "not calibrated" in the report.
- **With neither.** The overall win rate for every stage.

## Quarterly win rates

Win rate by quarter created, for mature quarters with at least 20 deals. The spread across quarters shows how much results swing from one quarter to the next, and the forecast will use it so the range is not too narrow.

## Validation

The synthetic sample is generated from known rates with planted data problems (`scripts/pflib/synth.py`, `truth.json`). The tests require that:
- win rates by source come within three standard errors of the true rates
- stage win rates come within three standard errors of the rates the generator implies
- median cycle and deal size come within three standard errors
- every planted data problem is found, with no false outliers or duplicates
