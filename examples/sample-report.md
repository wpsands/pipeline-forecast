# Pipeline forecast: Synthetic sample (fictional company)

## Summary

- **2026 Q4 forecast: $3.3M** (likely range $2.8M to $3.9M, 80% of simulated outcomes). Chance of reaching the $3.6M target: 25%.
- $2.4M is expected from 302 open deals worth $14.0M, and $863K from deals not created yet.
- **2026 Q4 gap after expected bookings from open deals: $1.3M.** Closing it with new deals alone would take about 166 new deals a month, against 93 a month today (1.8x), because few deals created now close this quarter.
- For 2027 Q1, 2027 Q2, 2027 Q3, new deal creation must run above its current pace: Events +58%, Outbound +50%, Partner +45%, Inbound Demo +40%, Paid Search +16%.
- **Backtest:** actual bookings fell inside the forecast range in 6 of 6 past quarters; the middle forecast was off by 7% on average.
- **Data confidence: normal.** 5 high-severity checks found problems, touching 10% of open pipeline. Details below.

## 2026 Q4 forecast

As of 2026-10-01. 5,000 simulated quarters. Each open deal is weighted by what happened to past deals in the same stage and age band (monthly snapshots by stage and age), adjusted for its source. Deals not created yet are simulated from each source's recent creation rate, win rate and cycle length. Rep close dates are not used.

| Outcome | Bookings |
|---|---|
| Low (P10) | $2.8M |
| Middle (P50) | $3.3M |
| High (P90) | $3.9M |
| Expected | $3.3M |
| Chance of $3.6M or more | 25% |

| Source | Expected from open deals | Expected from new deals | Total |
|---|---|---|---|
| Inbound Demo | $889K | $482K | $1.4M |
| Outbound | $580K | $138K | $718K |
| Partner | $332K | $87K | $419K |
| Untagged | $278K | $0 | $278K |
| Paid Search | $156K | $106K | $262K |
| Events | $209K | $51K | $261K |

| Stage | Open deals | Open pipeline | Expected this quarter | Share of pipeline expected |
|---|---|---|---|---|
| Discovery | 116 | $5.4M | $250K | 5% |
| Qualification | 88 | $4.2M | $456K | 11% |
| Solution | 52 | $2.3M | $554K | 24% |
| Proposal | 22 | $1.0M | $458K | 45% |
| Negotiation | 19 | $888K | $693K | 78% |
| Stage 3 - Legacy | 5 | $307K | $35K | 12% |

Reps' view, from forecast category on deals with a close date this quarter: Best Case $3.3M, Commit $888K, Pipeline $8.2M. Compare Commit with the model's low case, and Commit plus Best Case with its middle case.

Largest expected contributions:

| Deal | Source | Stage | Amount | Chance this quarter |
|---|---|---|---|---|
| OPP-02337 | Outbound | Negotiation | $106K | 75% |
| OPP-02263 | Outbound | Negotiation | $111K | 69% |
| OPP-01850 | Partner | Negotiation | $101K | 73% |
| OPP-02412 | Untagged | Negotiation | $71K | 82% |
| OPP-02238 | Inbound Demo | Proposal | $122K | 38% |
| OPP-02403 | Inbound Demo | Negotiation | $53K | 87% |
| OPP-02328 | Outbound | Negotiation | $56K | 75% |
| OPP-02312 | Untagged | Proposal | $71K | 57% |
| OPP-02314 | Inbound Demo | Negotiation | $47K | 87% |
| OPP-02443 | Partner | Proposal | $58K | 65% |

Notes: 3 deals flagged as amount outliers are left out until confirmed; 12 open deals with no amount use their source's average won deal; quarters swing together by about 7% in win rate, which widens the range.

## Pipeline plan

Works back from each quarter's target. The gap after expected bookings from open deals is split across sources by share of won bookings, last 12 months: Events 12%, Inbound Demo 38%, Outbound 25%, Paid Search 6%, Partner 19%.

| Quarter | Target | Booked | Expected from open deals | Gap to fill with new pipeline |
|---|---|---|---|---|
| 2026 Q4 | $3.6M | $0 | $2.3M | $1.3M |
| 2027 Q1 | $3.8M | $0 | $330K | $3.5M |
| 2027 Q2 | $4.0M | $0 | $30K | $4.0M |
| 2027 Q3 | $4.2M | $0 | $9.4K | $4.2M |

Deals each source must create per month, starting now and held steady, to hit each quarter's target (multiple of today's pace in brackets):

| Source | Created per month today | 2026 Q4 | 2027 Q1 | 2027 Q2 | 2027 Q3 |
|---|---|---|---|---|---|
| Events | 11.8 | 33 (2.8x) | 19 (1.6x) | 18 (1.5x) | 19 (1.6x) |
| Inbound Demo | 29.0 | 31 (1.1x) | 38 (1.3x) | 41 (1.4x) | 43 (1.5x) |
| Outbound | 25.6 | 61 (2.4x) | 42 (1.6x) | 35 (1.4x) | 37 (1.5x) |
| Paid Search | 17.5 | 15 (0.9x) | 19 (1.1x) | 21 (1.2x) | 22 (1.2x) |
| Partner | 8.7 | 26 (3.0x) | 13 (1.6x) | 12 (1.4x) | 12 (1.4x) |

The same pace as pipeline created per month:

| Source | 2026 Q4 | 2027 Q1 | 2027 Q2 | 2027 Q3 |
|---|---|---|---|---|
| Events | $1.4M | $788K | $744K | $796K |
| Inbound Demo | $1.2M | $1.4M | $1.6M | $1.6M |
| Outbound | $3.6M | $2.5M | $2.1M | $2.2M |
| Paid Search | $451K | $552K | $614K | $648K |
| Partner | $2.6M | $1.3M | $1.2M | $1.2M |

2026 Q4: few deals created now close before quarter end, so the current quarter's gap needs a multiple of today's creation pace. Read that column as the size of the gap, not a plan. Close the current quarter with the deals already open, and set the creation plan from the later quarters.

Untagged deals (96 in the win-rate cohort) are left out of the mix. Tag sources to include them.

## Backtest

The same model, rerun as of the first day of each past quarter using only what was known then, compared with what closed.

| Quarter | Low (P10) | Middle (P50) | High (P90) | Actual | Inside range | Middle vs actual |
|---|---|---|---|---|---|---|
| 2025 Q2 | $2.5M | $2.9M | $3.4M | $2.6M | yes | +11.7% |
| 2025 Q3 | $2.1M | $2.6M | $3.2M | $2.6M | yes | +1.0% |
| 2025 Q4 | $2.3M | $2.9M | $3.4M | $2.9M | yes | -3.0% |
| 2026 Q1 | $2.1M | $2.9M | $3.7M | $2.4M | yes | +21.0% |
| 2026 Q2 | $2.7M | $3.2M | $3.8M | $3.3M | yes | -1.9% |
| 2026 Q3 | $2.4M | $2.9M | $3.5M | $2.9M | yes | +0.9% |

Amounts are current amounts; exports carry no amount history. An 80% range should contain the actual result in about 8 of 10 quarters.

## Data integrity

2,607 deals checked as of 2026-10-01: 306 open worth $18.6M, 528 won. 12 of 15 checks found problems.

Forecast confidence: normal. High-severity problems touch 10% of open pipeline.

| Severity | Check | Deals | Open pipeline touched | Share of open pipeline |
|---|---|---|---|---|
| high | Open deals with a close date in the past | 10 | $443K | 2.4% |
| high | Deals in a stage outside the defined stage order | 5 | $307K | 1.7% |
| high | Deals with no close date | 5 | $242K | 1.3% |
| high | Close date earlier than created date | 7 | $225K | 1.2% |
| high | Open or won deals with no amount | 12 | unknown | unknown |
| medium | Amounts far outside the normal range | 3 | $5.1M | 27.3% |
| medium | Open deals whose close date was pushed 3 or more times | 46 | $2.1M | 11.2% |
| medium | Deals with a blank or catch-all source | 170 | $1.2M | 6.3% |
| medium | Open deals older than twice the 90th-percentile won cycle | 9 | $587K | 3.2% |
| medium | Likely duplicate deals | 8 | $454K | 2.4% |
| low | Open deals with no activity in 30 days | 25 | $1.1M | 5.7% |
| low | One source spelled several ways | 101 | $522K | 2.8% |
| high | Deals with no stage | 0 | $0 | 0.0% |
| low | CRM probability falls at a later stage | 0 | $0 | 0.0% |
| low | Won deals that skipped a stage | 0 | $0 | 0.0% |

**Open deals with a close date in the past** (high). The close date is no longer a forecast. The model ignores it and times these deals from their age. Examples: OPP-02267, OPP-02383, OPP-02388, OPP-02419, OPP-02426.

**Deals in a stage outside the defined stage order** (high). These deals cannot get a stage-based win rate. Map the stage or close the deal. Examples: OPP-01969, OPP-02322, OPP-02510, OPP-02526, OPP-02588. Stages: Stage 3 - Legacy (5).

**Deals with no close date** (high). Open deals with no close date cannot be placed in a quarter; closed deals drop out of cycle-time history. Examples: OPP-01678, OPP-02316, OPP-02421, OPP-02514, OPP-02585.

**Close date earlier than created date** (high). Negative cycle times. These deals are left out of cycle-time history. Examples: OPP-00501, OPP-01711, OPP-02426, OPP-02463, OPP-02494.

**Open or won deals with no amount** (high). Pipeline and bookings are understated by these deals, and deal-size averages skip them. Examples: OPP-01942, OPP-02058, OPP-02205, OPP-02308, OPP-02347.

**Amounts far outside the normal range** (medium). Set per source on a log scale. One mistyped amount can move the forecast more than a dozen real deals. Confirm each one. Examples: OPP-02556, OPP-02566, OPP-02600.

**Open deals whose close date was pushed 3 or more times** (medium). Repeated pushes usually mean the deal has stalled. The rep's close date is not a reliable signal here. Examples: OPP-00950, OPP-01032, OPP-01133, OPP-01457, OPP-01590.

**Deals with a blank or catch-all source** (medium). Rates by source and the plan by source exclude these deals. A high share means the plan by source is unreliable. Examples: OPP-00027, OPP-00028, OPP-00039, OPP-00054, OPP-00060. 6.5% of deals and 5.7% of won bookings have no usable source.

**Open deals older than twice the 90th-percentile won cycle** (medium). Few deals this old ever close. They inflate coverage while adding little expected value. Examples: OPP-00950, OPP-01032, OPP-01133, OPP-01457, OPP-01590. The 90th-percentile won cycle is 123 days.

**Likely duplicate deals** (medium). Same account, amount within 10% and created within 14 days. Duplicates double count pipeline. Examples: OPP-02351, OPP-02466, OPP-02493, OPP-02497, OPP-02644.

**Open deals with no activity in 30 days** (low). Usually stalled. Worth a review before the forecast call. Examples: OPP-01690, OPP-01839, OPP-01854, OPP-02190, OPP-02258.

**One source spelled several ways** (low). Counted here: deals not using the most common spelling. Merged automatically for this model. Fix in the CRM so reports agree. Examples: OPP-00013, OPP-00016, OPP-00017, OPP-00056, OPP-00138. Spellings found: Inbound Demo; Inbound demo; inbound demo | Paid Search; Paid search; paid-search.

## Historical rates

Win rates use deals created between 2024-10-01 and 2026-02-22. Deals created later are left out because many have not closed yet: 95% of closed deals closed within 221 days. Deal size uses deals won in the last 12 months. Cycle length uses deals won in the last 24 months.

Overall: 22.0% of 1,448 deals won; average won deal $47K; median won cycle 62 days.

| Source | Deals in cohort | Win rate | Avg won deal | Median cycle | 90th pct cycle | New deals / month | New pipeline / month |
|---|---|---|---|---|---|---|---|
| Outbound | 353 | 15.5% | $59K | 81 days | 173 days | 25.6 | $1.5M |
| Inbound Demo | 444 | 28.9% | $42K | 49 days | 91 days | 29.0 | $1.1M |
| Partner | 118 | 28.3% | $77K | 96 days | 162 days | 8.7 | $852K |
| Paid Search | 264 | 16.5% | $24K | 46 days | 86 days | 17.5 | $520K |
| Events | 173 | 20.3% | $41K | 87 days | 127 days | 11.8 | $491K |

\* Fewer than 30 deals in the cohort or fewer than 10 won deals: the rate is pulled toward the overall rate (win rate) or replaced by it (deal size).

### Win rate by stage

Two different numbers. The first is the share of deals that ever reached the stage and went on to win (stage history). The second is the share of deals sitting in the stage at a month start that were won within 3 and within 12 months, measured from monthly snapshots. The forecast uses the second. Deals that will lose tend to stall in early stages, so early-stage deals in today's pipeline win less often than the first number suggests.

| Stage | Reached it and won | Sitting in it, won within 3 months | Sitting in it, won within 12 months |
|---|---|---|---|
| Discovery | 22.0% (1,448 deals) | 3.7% | 6.3% |
| Qualification | 30.7% (1,037 deals) | 9.0% | 12.7% |
| Solution | 44.6% (713 deals) | 21.6% | 23.9% |
| Proposal | 63.1% (504 deals) | 43.1% | 43.7% |
| Negotiation | 81.5% (390 deals) | 74.2% | 74.4% |

Win rate by quarter created: 2024 Q4 19.5%, 2025 Q1 23.1%, 2025 Q2 22.6%, 2025 Q3 20.2%, 2025 Q4 26.2%, 2026 Q1 17.3%.

Method: method/model.md. Integrity checks: method/integrity.md.
