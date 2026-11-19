---
name: pipeline-forecast
description: Checks a B2B SaaS company's CRM opportunity data for problems that distort forecasts, then measures historical win rates, deal size, cycle length and pipeline creation by source and by stage. Works from a Salesforce or HubSpot export; read-only. Use when the user says "check our CRM data", "pipeline data integrity", "what's our real win rate", "win rate by source", "how long is our sales cycle", "pipeline forecast", or "how much pipeline do we need".
---

# Pipeline Forecast Model

Turn a CRM export into an integrity report and measured rates. Every number comes from the export; nothing is assumed.

## Load the method

Before starting, read `${CLAUDE_PLUGIN_ROOT}/method/integrity.md` and `${CLAUDE_PLUGIN_ROOT}/method/model.md`.

The CLI is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pf.py`. Below it is written as `pf`.

## Inputs

Ask once, only for what is missing:

1. **Opportunity export.** A CSV of opportunities from Salesforce, HubSpot or another CRM, covering at least the last 24 months, open and closed. Guide the user if needed:
   - **Salesforce:** an Opportunities report, tabular, all time, with Opportunity ID, Created Date, Close Date, Stage, Amount, Lead Source, Owner, Forecast Category, Probability (%), Last Activity and Type. Export it as CSV, details only.
   - **HubSpot:** Deals, export all properties.
2. **Field-history export (recommended).** Salesforce: an Opportunity Field History report filtered to Stage and Close Date. It lets the model measure stage win rates and find close-date pushes.
3. **As-of date.** Default today. Use the first day of the quarter to forecast.
4. **Fiscal year start month.** Default January.
5. **Deal types.** New business only is recommended, if the export has a type column.

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
Do not continue until the order is confirmed. Stage win rates depend on it.

### 3. Check integrity, then stop
```
pf check RUN
```
Present the findings, high severity first, with the open pipeline each one touches and the example deal ids. State the forecast confidence. Ask whether the user wants to fix data in the CRM and re-export, or continue with the data as it is. Never edit the CRM.

### 4. Measure rates and write the report
```
pf report RUN
```
This reruns the checks, writes `rates.json`, and writes `report.md`. Present:
- win rate, deal size and cycle by source
- the win rate by stage reached, and its method
- how much results swing from quarter to quarter

Point out where the numbers differ from what the team believes, for example a CRM probability far from the measured stage win rate. Mark any source with few deals as uncertain.

## Output rules
- Every number in the report comes from the export. If a value cannot be measured, say so. Do not fill it in.
- Name the method for stage win rates every time: measured from history, or CRM probabilities that are not calibrated.
- Company data stays local. Do not publish company names or figures without the company's agreement.
- Write plainly: short sentences, no em dashes, no hype.
