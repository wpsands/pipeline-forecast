# Model

How the model turns a CRM export into historical rates, a quarter forecast, a pipeline plan and a backtest. The code is in `scripts/pflib/`; this file and the code must agree.

## Inputs

- **Opportunity export (required).** One row per deal: id, created date, close date, stage, amount, source. Optional: name, account, owner, forecast category, CRM probability, last activity date, type. Column names from Salesforce and HubSpot exports are recognized automatically; a mapping file covers anything else.
- **Field-history export (optional, strongly recommended).** One row per change to stage or close date: id, field, old value, new value, date. A Salesforce "Opportunity Field History" report has this shape. With it, stage weights are measured, not assumed. The integrity checks also cover close-date pushes and skipped stages.
- **Settings.** As-of date, fiscal year start month, lookback (24 months by default), deal types to include (new business only is recommended), the stage order (confirmed by the user), and quarterly bookings targets for the plan.

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
- **Cycle length:** created date to close date for deals won in the lookback window, by source. The model keeps the full distribution, because the forecast and the plan need its shape. Lost-deal cycles are kept too.

## Pipeline creation

Deals and pipeline created per month by source, over the last 12 full months. Untagged deals are shown as their own row.

## Win rate by stage reached

- **With field history.** For each stage: of mature-cohort deals that reached it, the share that won. Reaching a later stage counts as passing the earlier ones. Small samples can make a later stage look worse than an earlier one, so the rates are fitted to a non-decreasing sequence (pool-adjacent-violators) weighted by deal count.
- **Without field history.** The CRM's own stage probabilities, labeled "not calibrated".

This number describes the funnel. It is not used to weight open deals; see the next section.

## Snapshot curves: the forecast's stage weights

The win rate of deals that ever reached a stage is the wrong weight for deals sitting in that stage today. Deals that will lose tend to stall, so they sit in early stages longer and make up a larger share of any snapshot. In the synthetic sample:
- 22% of deals that reached Discovery were won.
- Of deals sitting in Discovery at a month start, 6% were won within a year.

A forecast built on the first number ran about 50% high in every backtested quarter.

The model measures the second number directly:
1. Rebuild the pipeline as it stood at each month start in the lookback window. A deal's stage at that date comes from field history.
2. Group deals by stage and by age band: under 30 days, 30 to 89, 90 to 179, and 180 or more.
3. For each group, record the share won in each of the next 12 months. Only use months that had fully passed by the as-of date.
4. Small groups are pulled toward their stage's overall curve with 20 pseudo-deals.

Without field history, the groups are by age band only.

## Quarterly swing

Win rate by quarter created, for mature quarters with at least 20 deals. The spread across quarters, beyond what sample size explains, measures how much results move together from one quarter to the next.

## Quarter forecast

Each open deal's chance of being won inside the quarter comes from its group's snapshot curve: the cumulative share won by the quarter end, minus the share won by the window start. That chance is adjusted for the deal's source in odds: odds × (source win-rate odds ÷ overall win-rate odds). Rep close dates and CRM probabilities are not used.

Deals not created yet are added per source:
- Creation is a Poisson process at the source's average daily rate over the last three full months.
- Each new deal is won at the source's win rate.
- It closes inside the quarter with the probability given by the source's won-cycle distribution.
- Amounts are drawn from the source's won deals in the last 12 months.

The simulation runs 5,000 quarters by default, with a fixed seed so the result repeats. In each simulated quarter:
- A shared multiplier, lognormal with mean 1, scales every probability. Its spread is the quarterly swing.
- Without it, deals are treated as independent, and the range comes out too narrow.

Outputs:
- the low, middle and high outcomes (P10, P50 and P90) and the expected value
- the chance of reaching the target
- the expected bookings by source, split into open deals and deals not created yet
- the expected bookings by stage
- the largest expected contributions
- the reps' forecast categories for comparison

Deals flagged as amount outliers are left out until confirmed; `--keep-outliers` includes them. Open deals with no amount use their source's average won deal.

## Pipeline plan

Targets are given per quarter, starting with the current one.

1. **Gap.** For each quarter: target − booked so far − expected bookings from open deals. The expected bookings use the same per-deal timing as the forecast.
2. **Split by source.** The gap is divided by mix: each source's share of won bookings in the last 12 months, or a mix the user sets.
3. **Required pace.** For source s, one deal a month created in quarter i is expected to book this much in quarter j:

   a(i, j) = win rate × deal size × P(the cycle lands the close in quarter j)

   The required pace for quarter j is the steady number of deals a month, from now on, that books the source's share of the gap:

   n(j) = share of gap ÷ sum over i ≤ j of a(i, j)

   Each quarter's pace answers one question: how many deals a month from today to hit that quarter.
4. **Rejected alternative.** Solving quarter by quarter for a pace that changes each quarter was tried and rejected. It swings between zero and several times the current pace, because undoing the spread of cycle lengths is numerically unstable.
5. **Current quarter.** Few deals created now close before quarter end, so the current quarter usually needs a multiple of today's pace. The report says to read that column as the size of the gap, not as a plan.
6. **Leads.** With lead-to-deal rates, the plan also gives leads needed per month.

Untagged deals are left out of the mix, and the report counts them.

## Backtest

For each of the last N quarters, the CRM is rebuilt as it stood on the quarter's first day:
- Deals created later are dropped.
- Deals that closed later are reopened.
- Stages are set from field history.
- Close dates, probabilities and last activity are cleared.
- Field history after that day is dropped.

Rates, snapshot curves and the forecast are recomputed from that view alone, then compared with the bookings that actually closed that quarter. Amounts are current amounts, because exports carry no amount history.

The report shows each quarter's range, the actual result, whether it fell inside, and the error of the middle estimate. An 80% range should contain the actual result in about 8 of 10 quarters.

## Validation

The synthetic sample is generated from known rates with planted data problems (`scripts/pflib/synth.py`, `truth.json`). The tests require that:
- win rates by source come within three standard errors of the true rates
- stage win rates come within three standard errors of the rates the generator implies
- median cycle and deal size come within three standard errors
- every planted data problem is found, with no false outliers or duplicates
- the backtest puts the actual result inside the P10 to P90 range in at least 4 of 6 quarters, with a middle-estimate error under 15%. Today: 6 of 6 and 7%.
- one deal's chances over two quarters add up to its chance over both, and later stages always score higher
- the plan's required pace scales with the gap, and a year out it matches the steady-state pace
- the backtest view contains nothing dated after its as-of date

## Not in this version

- Expansion and renewal pipeline. Filter to new business with `--types`.
- Rep-level forecasts.
- Amount changes over a deal's life. Exports rarely include amount history.
- Direct CRM connections. The model works from exports and never writes to a CRM.
