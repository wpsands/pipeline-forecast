# Pipeline forecast: Synthetic sample (fictional company)

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

### Win rate by stage reached

Method: stage history.

| Stage | Win rate |
|---|---|
| Discovery | 22.0% (1,448 reached it) |
| Qualification | 30.7% (1,037 reached it) |
| Solution | 44.6% (713 reached it) |
| Proposal | 63.1% (504 reached it) |
| Negotiation | 81.5% (390 reached it) |

Win rate by quarter created: 2024 Q4 19.5%, 2025 Q1 23.1%, 2025 Q2 22.6%, 2025 Q3 20.2%, 2025 Q4 26.2%, 2026 Q1 17.3%.

Method: method/model.md. Integrity checks: method/integrity.md.
