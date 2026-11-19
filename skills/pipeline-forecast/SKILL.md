---
name: pipeline-forecast
description: Forecasts a B2B SaaS company's quarter as a range, works back from bookings targets to the pipeline each source must create per month, and backtests the forecast against past quarters. It first checks CRM opportunity data for problems that distort forecasts and measures win rates, deal size and cycle length by source and stage. Works from a Salesforce or HubSpot export; read-only. Use when the user says "pipeline forecast", "forecast the quarter", "will we hit the number", "how much pipeline do we need", "pipeline coverage", "check our CRM data", "what's our real win rate", or "how long is our sales cycle".
---

# Pipeline Forecast Model

Turn a CRM export into an integrity report, measured rates, a quarter forecast, a pipeline plan and a backtest. Every number comes from the export; nothing is assumed.

## Load the method

Before starting, read `${CLAUDE_PLUGIN_ROOT}/method/integrity.md` and `${CLAUDE_PLUGIN_ROOT}/method/model.md`.

The CLI is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pf.py`. Below it is written as `pf`.

## Inputs

Ask once, only for what is missing:

1. **Opportunity export.** A CSV of opportunities from Salesforce, HubSpot or another CRM, covering at least the last 24 months, open and closed. Guide the user if needed:
   - **Salesforce:** an Opportunities report, tabular, all time, with Opportunity ID, Created Date, Close Date, Stage, Amount, Lead Source, Owner, Forecast Category, Probability (%), Last Activity and Type. Export it as CSV, details only.
   - **HubSpot:** Deals, export all properties.
2. **Field-history export (strongly recommended).** Salesforce: an Opportunity Field History report filtered to Stage and Close Date. The forecast's stage weights are measured from it. Without it, deals are weighted by age and source only. Say so in the results.
3. **As-of date.** Default today. Use the first day of the quarter for a clean quarter forecast.
4. **Fiscal year start month.** Default January.
5. **Deal types.** New business only is recommended, if the export has a type column.
6. **Quarterly new-business bookings targets**, starting with the current quarter. These are needed for the plan and the chance of hitting target.
7. **Source mix (optional).** If the team plans a different mix than last year, for example more partner-sourced deals.
8. **Lead-to-deal rates (optional).** For sources where leads matter, such as inbound.

Run folders hold confidential company data. Keep them in `./runs/`, which is out of git. Never paste rows of the data into chat beyond the few examples the report lists.

## Workflow

### 1. Set up and ingest
```
pf init RUN --as-of YYYY-MM-DD --fy-start-month N
pf ingest RUN opportunities.csv [--types "New Business"] [--map map.json] [--day-first]
pf history RUN field-history.csv
```
Report what ingest found: rows kept and skipped, the column mapping, and anything not found. If a required column was not recognized, write a mapping file (`{"created": "Their Column Name", ...}`) and run ingest again. If dates look wrong (for example, day and month swapped), use `--day-first`.

### 2. Confirm the stage order
Ingest guesses the open stages in order, plus the won and lost stages. Show the guess and how it was made, and ask the user to confirm or correct it:
```
pf stages RUN --order "Discovery,Qualification,Solution,Proposal,Negotiation" --won "Closed Won" --lost "Closed Lost"
```
Do not continue until the order is confirmed.

### 3. Check integrity, then stop
```
pf check RUN
```
Present the findings, high severity first, with the open pipeline each one touches and the example deal ids. State the forecast confidence. Ask whether the user wants to fix data in the CRM and re-export, or continue with the data as it is. Ask the user to confirm or dismiss each amount outlier. Outliers are left out of the forecast unless the user says they are real; in that case, add `--keep-outliers`. Never edit the CRM.

### 4. Forecast, plan and backtest
```
pf forecast RUN --target <current quarter target>
pf plan RUN --targets <q1>,<q2>,<q3>,<q4> [--mix "Source=share,..."] [--lead-rates "Source=rate,..."]
pf backtest RUN --quarters 4
pf report RUN
```
`report` reruns every step with the saved settings and writes `report.md`. Present it in this order:
1. **The forecast range and the chance of hitting target.** Compare the model with the reps' forecast categories: Commit against the low case, and Commit plus Best Case against the middle case.
2. **The current-quarter gap.** Say plainly whether new pipeline can still close it. Usually it cannot, and the quarter has to be closed with deals already open.
3. **The required creation pace by source for the following quarters,** as a multiple of today's pace. Name the sources that need the largest increase.
4. **The backtest.** Report how many past quarters fell inside the range and the typical error. If the backtest is poor (fewer than half inside, or error above 25%), say the forecast should not be relied on yet, and point to the integrity findings or the missing field history.
5. **The integrity findings that matter most,** and the stage-weight table. Explain the gap between "reached it and won" and "sitting in it" when it is large. It is usually the most useful finding for the team.

## Output rules
- Every number in the report comes from the export. If a value cannot be measured, say so. Do not fill it in.
- Always give the forecast as a range with its backtest. Never present a single number as the forecast.
- Name the stage-weight method every time: snapshots by stage and age, or by age only without field history.
- Company data stays local. Do not publish company names or figures without the company's agreement.
- Write plainly: short sentences, no em dashes, no hype.
