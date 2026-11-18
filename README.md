# Pipeline Forecast Model

Most pipeline forecasts are built on CRM data nobody has checked, using win rates that run high. This Claude Code plugin checks the data first, then measures the rates the forecast depends on.

It works from a CRM export. It needs no API access and makes no changes to the CRM.

## What it does today

1. **Data integrity report.** Fifteen checks for the problems that distort a forecast: missing amounts and close dates, past-due close dates, unknown stages, amount outliers, duplicates, untagged or inconsistently spelled sources, stalled deals and repeated close-date pushes.
   - Each finding shows how much open pipeline it touches, with example deal ids.
   - If high-severity problems touch more than 20% of open pipeline, the forecast is marked low confidence.
2. **Historical rates.** By source:
   - win rate, from mature cohorts
   - deal size, cycle length, and pipeline created per month

   Also:
   - win rate by stage reached, measured from field history
   - how much win rates swing from quarter to quarter

Coming in the next release:
- the pipeline plan, which works back from the bookings target to the pipeline each source must create each month
- a quarter forecast with a likely range (P10, P50 and P90) and the chance of hitting target
- a backtest against past quarters

See a full report on synthetic data: [examples/sample-report.md](examples/sample-report.md). The company in it is fictional.

## Why mature cohorts

The usual win rate is won ÷ (won + lost) over recently closed deals, and it runs high:
- Losses are often closed out later than wins.
- Recent deals that will lose are still open, so they are left out.

This model counts only deals created long enough ago that 95% of them would have closed. Its tests include a constructed case where the usual method reports 100% against a true 25%. The method is in [method/model.md](method/model.md).

## How it is validated

The synthetic sample comes from a fictional company with known true rates and planted data problems. The tests require that:
- the model recovers each source's win rate, cycle length and deal size within three standard errors
- the stage win rates match what the generator implies
- the integrity checks find every planted problem, with no false outliers or duplicates

## Install

```
/plugin marketplace add wpsands/pipeline-forecast
/plugin install pipeline-forecast@pipeline-forecast
```

Then ask Claude Code: "Check our CRM data and measure our win rates," and attach your opportunity export.

## What it needs

| Input | Required | Notes |
|---|---|---|
| Opportunity export (CSV) | Yes | At least 24 months, open and closed. Salesforce and HubSpot column names are recognized automatically; a mapping file covers anything else. |
| Field-history export (CSV) | Recommended | Stage and close-date changes. Lets the model measure stage win rates and find close-date pushes. Salesforce: an Opportunity Field History report. |
| Confirmed stage order | Yes | The model guesses the order; you confirm it. |

## The CLI

The skill drives `scripts/pf.py`, which you can also run directly. It needs Python 3.10 or later and uses only the standard library.

```
python3 scripts/pf.py init runs/acme --as-of 2026-10-01 --fy-start-month 2
python3 scripts/pf.py ingest runs/acme opportunities.csv --types "New Business"
python3 scripts/pf.py history runs/acme field-history.csv
python3 scripts/pf.py stages runs/acme --order "Discovery,Qualification,Solution,Proposal,Negotiation" --won "Closed Won" --lost "Closed Lost"
python3 scripts/pf.py check runs/acme
python3 scripts/pf.py report runs/acme
python3 scripts/pf.py sample /tmp/sample
```

Run folders hold confidential company data. `runs/` and CSV files are in `.gitignore`.

## Development

```
python3 -m unittest discover -s tests -v
python3 scripts/pf.py sample /tmp/sample && diff examples/sample-report.md /tmp/sample/run/report.md
```

CI runs the tests on Python 3.10, 3.12 and 3.13, and checks that `examples/sample-report.md` matches what the code generates.

## About

Built by [Page Sands](https://sandsdx.com/about/) at SandsDX, one of the [GTM agents and skills](https://sandsdx.com/agents/) for building B2B SaaS pipeline. MIT licensed.
