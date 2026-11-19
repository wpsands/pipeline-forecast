# Pipeline Forecast Model

Most pipeline forecasts are built on CRM data nobody has checked, using win rates that run high. This Claude Code plugin does four things:
- checks the data first
- forecasts the quarter as a range
- works back from targets to the pipeline each source must create
- backtests itself against past quarters

It works from a CRM export. It needs no API access and makes no changes to the CRM.

## What it produces

1. **Quarter forecast.** A range from 5,000 simulated quarters:
   - low, middle and high outcomes (P10, P50 and P90)
   - the chance of reaching the target
   - expected bookings by source, split into open deals and deals not created yet
   - expected bookings by stage, with the largest deals
   - the reps' forecast categories side by side

   Each open deal is weighted by what happened to past deals in the same stage and age band. Rep close dates are not used.
2. **Pipeline plan.** It works back from each quarter's target:
   - the gap after expected bookings from open deals
   - the deals and pipeline each source must create per month, as a multiple of today's pace
   - optionally, the leads needed

   It also says when the current quarter can no longer be fixed with new pipeline.
3. **Backtest.** The same model, rerun as of the start of each past quarter using only what was known then, compared with what actually closed.
4. **Data integrity report.** Fifteen checks for the problems that distort a forecast:
   - missing amounts and close dates, past-due close dates, unknown stages
   - amount outliers and duplicates
   - untagged or inconsistently spelled sources
   - stalled deals and repeated close-date pushes

   Each finding is sized by the open pipeline it touches. If high-severity problems touch more than 20% of open pipeline, the forecast is marked low confidence.
5. **Historical rates.**
   - By source: win rate from mature cohorts, deal size, cycle length and pipeline created per month.
   - By stage: win rates measured two ways, explained below.

See a full report on synthetic data: [examples/sample-report.md](examples/sample-report.md). The company in it is fictional.

## Two traps it avoids

**Win rates that run high.** The usual win rate is won ÷ (won + lost) over recently closed deals. Losses are often closed out later than wins, and recent deals that will lose are still open. This model counts only deals created long enough ago that 95% of them would have closed. Its tests include a constructed case where the usual method reports 100% against a true 25%.

**Stage weights that run high.** The share of deals that reach a stage and go on to win is not the chance for a deal sitting in that stage today. Deals that will lose stall, so they crowd the early stages of any snapshot.
- In the sample, 22% of deals that reached Discovery were won.
- Of deals sitting in Discovery at a month start, only 6% were won within a year.
- A forecast built on the first number ran about 50% high in every backtested quarter.

This model rebuilds past snapshots of the pipeline and measures the second number directly. The full method is in [method/model.md](method/model.md).

## How it is validated

The synthetic sample comes from a fictional company with known true rates and planted data problems. The tests require that:
- the model recovers each source's win rate, cycle length and deal size within three standard errors
- the stage win rates match what the generator implies
- the integrity checks find every planted problem, with no false outliers or duplicates
- the backtest puts actual bookings inside the forecast range in at least 4 of 6 past quarters. Today it is 6 of 6, with the middle estimate off by 7% on average.
- the plan's required pace scales with the gap, and a year out it matches the steady-state pace

## What it needs

| Input | Required | Notes |
|---|---|---|
| Opportunity export (CSV) | Yes | At least 24 months, open and closed. Salesforce and HubSpot column names are recognized automatically; a mapping file covers anything else. |
| Field-history export (CSV) | Strongly recommended | Stage and close-date changes. The forecast's stage weights are measured from it. Without it, deals are weighted by age and source only. Salesforce: an Opportunity Field History report. |
| Confirmed stage order | Yes | The model guesses the order; you confirm it. |
| Quarterly bookings targets | For the plan | New business, starting with the current quarter. |

## Install

You need [Claude Code](https://claude.com/claude-code). Type these two commands into Claude Code itself, in the same box where you chat with Claude. They are not terminal commands.

```
/plugin marketplace add wpsands/pipeline-forecast
/plugin install pipeline-forecast@pipeline-forecast
```

1. The first command registers this public GitHub repo as a plugin source. Claude Code calls a source like this a marketplace. Nothing is installed yet.
2. The second command installs the plugin. The format is `plugin@marketplace`. The plugin and the repo share the name `pipeline-forecast`, so the name appears twice.
3. Restart Claude Code if the plugin does not show up right away.

To get a later version, run `/plugin marketplace update pipeline-forecast`.

Then ask Claude Code: "Forecast our quarter and tell me how much pipeline we need," and attach your opportunity export. Have your quarterly bookings targets ready.

## Who sees what

The plugin runs on your machine, with your accounts. Installing it downloads a copy of this public repo, the same files the Code button on GitHub gives you. It needs no GitHub account and grants no access in either direction.

- It reads only the CSV exports you give it. It never connects to your CRM or changes it.
- Results go in a `runs/` folder on your machine, which is kept out of git.
- Nothing is sent to the author, to this repo or to sandsdx.com.

## The CLI

The skill drives `scripts/pf.py`, which you can also run directly. It needs Python 3.10 or later and uses only the standard library.

```
python3 scripts/pf.py init runs/acme --as-of 2026-10-01 --fy-start-month 2
python3 scripts/pf.py ingest runs/acme opportunities.csv --types "New Business"
python3 scripts/pf.py history runs/acme field-history.csv
python3 scripts/pf.py stages runs/acme --order "Discovery,Qualification,Solution,Proposal,Negotiation" --won "Closed Won" --lost "Closed Lost"
python3 scripts/pf.py check runs/acme
python3 scripts/pf.py forecast runs/acme --target 4M
python3 scripts/pf.py plan runs/acme --targets 4M,4.2M,4.5M,5M [--mix "Inbound Demo=40,Outbound=30,Partner=30"] [--lead-rates "Inbound Demo=25%"]
python3 scripts/pf.py backtest runs/acme --quarters 4
python3 scripts/pf.py report runs/acme
python3 scripts/pf.py sample /tmp/sample
```

Run folders hold confidential company data. `runs/` and CSV files are in `.gitignore`.

## Not in this version

- Expansion and renewal pipeline. Filter to new business with `--types`.
- Rep-level forecasts.
- Direct CRM connections.

## Development

```
python3 -m unittest discover -s tests -v
python3 scripts/pf.py sample /tmp/sample && diff examples/sample-report.md /tmp/sample/run/report.md
```

CI runs the tests on Python 3.10, 3.12 and 3.13, and checks that `examples/sample-report.md` matches what the code generates.

## About

Built by [Page Sands](https://sandsdx.com/about/) at SandsDX, one of the [GTM agents and skills](https://sandsdx.com/agents/) for building B2B SaaS pipeline. MIT licensed.
