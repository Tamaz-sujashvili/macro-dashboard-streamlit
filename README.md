# Macro Dashboard

**Repository:** [github.com/Tamaz-sujashvili/macro-dashboard-streamlit](https://github.com/Tamaz-sujashvili/macro-dashboard-streamlit)  
**Live app:** [macro-dashboard-app.streamlit.app](https://macro-dashboard-app-7ju3ucvwbeihu75sjkeryf.streamlit.app/)

Finance-oriented Streamlit dashboard for tracking macro regime, liquidity, market stress, options structure, institutional positioning, and energy futures in one place.

The project is designed as a multi-factor macro model rather than a single-signal screener. It combines growth, inflation, rates, sentiment, positioning, volatility, and cross-asset market data to help readers form a top-down view of the current regime and the risks around it.

## What The Dashboard Does

The dashboard organizes macro information into a decision workflow:

1. Identify the macro regime using growth, inflation, labor, consumer, and curve signals.
2. Check whether market pricing agrees with that macro backdrop through equities, rates, FX, commodities, and volatility.
3. Evaluate whether liquidity is supportive or deteriorating using funding and market-depth proxies.
4. Inspect options and dealer-positioning structure for convexity, crowding, and near-term risk asymmetry.
5. Review institutional flow and positioning indicators to see whether large allocators are adding or withdrawing risk.
6. Use headline and energy sections to connect the live narrative to the quantitative signals.

This is best interpreted as a macro dashboard for synthesis, not as a fully systematic trading engine.

## How To Interpret It As A Multi-Factor Macro Model

The model works through signal clustering instead of relying on one headline number.

- `Growth`: GDP-style activity proxies, labor market conditions, housing, spending, and nowcast-style inputs.
- `Inflation`: CPI/PCE-style pressure, energy sensitivity, inflation breadth, and pricing persistence.
- `Rates and Curve`: Treasury levels, term structure, funding spreads, and duration-sensitive signals.
- `Liquidity`: SOFR/funding conditions, money market behavior, Amihud-style market depth, and bond-volatility proxies.
- `Risk Appetite`: Fear & Greed, AAII, NAAIM, VIX term structure, put/call behavior, and realized versus implied volatility.
- `Positioning and Flows`: CFTC COT, mutual fund flows, money market migration, CTA-style trend models, and 13F aggregation proxies.
- `Cross-Asset Confirmation`: Equities, dollar, oil, gold, credit, and volatility should either confirm or challenge the base macro view.

In practice:

- Broad agreement across these blocks suggests higher-confidence regime identification.
- Sharp disagreement usually means transition risk, unstable narrative, or crowded positioning.
- Market signals can lead economic releases, so a deteriorating liquidity or options backdrop may matter before backward-looking macro data does.

## Feature Overview

The current app includes:

- `Macro Overview`: Growth, inflation, labor, recession, spending, housing, and curve context.
- `Markets & Sentiment`: Equity indices, consumer sentiment, flows, FX, commodities, and market mood.
- `Options & Derivatives`: Put/call ratios, VIX term structure, skew, SPY options-chain analytics, gamma-style structure, and related volatility signals.
- `News & Signals`: Macro headlines plus signal summaries to connect narrative and pricing.
- `Liquidity Conditions`: Funding stress, SOFR-related measures, Treasury/liquidity proxies, and market-depth indicators.
- `Institutional Flows`: CFTC positioning, ICI fund flows, money market movement, CTA-style models, and 13F-derived context.
- `Global Macro`: Cross-country and central-bank-oriented context.
- `Sentiment Framework`: Composite view of vol, retail sentiment, skew, and market stress indicators.
- `AI Macro Analysis`: Local Codex CLI workflow that turns the current snapshot into a written macro brief.
- `X Intelligence`: Local file-based workflow for analyzed social/chart intelligence.
- `Energy Futures`: Oil curve and spread-focused section with local CSV fallback support.
- `Offline Export`: Ability to generate an offline HTML snapshot of the dashboard state.

## Data Sources

The dashboard uses a mix of official/public APIs, publisher pages, and market-data wrappers.

Primary sources used by the app include:

- `FRED` for macro time series and public-series aggregation.
- `U.S. Treasury` data/pages for rates and related market context.
- `BLS Public Data API` for labor series.
- `New York Fed` and `FRED` fallback for SOFR-related inputs.
- `CFTC Public Reporting API` for Commitment of Traders data.
- `ICI` public flow tables for mutual fund flow estimates.
- `EIA API` for crude inventory and energy context.
- `Alpha Vantage` for macro/news feed content.
- `Yahoo Finance` via `yfinance` for many market prices, options chains, futures proxies, and history.
- `RSS and configured news feeds` for broader world and market headlines.

Source quality varies by section:

- Official/public-institution series are generally suitable for macro monitoring.
- `yfinance` and similar wrappers are useful for analytics and visualization, but they are not exchange-certified real-time feeds.
- Options-chain analytics in the dashboard should be treated as analytical proxies, not institutional-grade execution data.

## Local Run

```bash
cd /Users/tazo/Documents/macrodashboard
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
streamlit run app.py
```

The default local URL is usually `http://localhost:8501`.

## Streamlit Deployment

This repo is structured to deploy directly on Streamlit Community Cloud.

**Live deployment:** [https://macro-dashboard-app-7ju3ucvwbeihu75sjkeryf.streamlit.app/](https://macro-dashboard-app-7ju3ucvwbeihu75sjkeryf.streamlit.app/)

1. Push the repository to GitHub.
2. In Streamlit Community Cloud, create a new app from the GitHub repo.
3. Set the main file path to `app.py`.
4. Keep the Python dependencies sourced from `requirements.txt`.
5. Add secrets in the app settings before expecting all API-backed sections to work.

The repo already includes `.streamlit/config.toml` for basic Streamlit server/theme configuration.

## Secrets Setup

Use `.streamlit/secrets.toml.example` as the starting template for local or hosted secrets.

Typical setup:

1. Copy the example to `.streamlit/secrets.toml` locally.
2. Fill only the keys you actually use.
3. In Streamlit Community Cloud, paste the same TOML into `App -> Settings -> Secrets`.

Supported secrets:

- `FRED_API_KEY`
- `ALPHA_VANTAGE_KEY`
- `BLS_API_KEY`
- `EIA_API_KEY`
- `FMP_API_KEY`
- `CFTC_APP_TOKEN`
- `NASDAQ_API_KEY`
- `CONGRESS_GOV_API_KEY`
- `FINNHUB_API_KEY`
- `FINNHUBAPIKEY`
- `ENABLE_LOCAL_AI_ANALYSIS`
- `ENABLE_X_INTELLIGENCE_REFRESH`

Notes:

- The app currently checks both `FINNHUB_API_KEY` and `FINNHUBAPIKEY`, so the template includes both for deployment safety.
- Keep `ENABLE_LOCAL_AI_ANALYSIS` and `ENABLE_X_INTELLIGENCE_REFRESH` set to `false` in public Streamlit deployments unless you have intentionally provisioned the local tooling they require.
- Some sections can still render with public/fallback data when keys are absent.
- Secrets should never be committed; `.streamlit/secrets.toml` is already ignored by Git.

## Deployment Caveats

Some parts of the dashboard are local-machine oriented and will not behave the same way on hosted Streamlit.

- `AI Macro Analysis` depends on a local Codex CLI workflow and is not expected to run on Streamlit Community Cloud unless that runtime is explicitly provisioned with the required tooling.
- `X Intelligence` references local files under the user home directory and should be treated as a local-only workflow unless reworked for hosted infrastructure.
- Energy futures have a local CSV fallback in `data/`, which helps resilience but does not replace a proper live market-data integration.

## Limitations

- The dashboard is an interpretation layer, not investment advice or an execution system.
- Data freshness differs materially by source; some series are daily, weekly, monthly, delayed, or scraped.
- Several sections depend on unofficial transport layers such as `yfinance`, which can break or lag without warning.
- Macro indicators are heterogeneous and can conflict; signal disagreement should be treated as information, not as a bug.
- Options and positioning analytics are approximations built for monitoring and scenario framing.
- Hosted Streamlit environments are resource-constrained relative to a local research machine.

## Repository Structure

```text
macrodashboard/
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── data/
│   └── futures-spreads-clm26-04-23-2026.csv
├── handoff/
│   ├── macro-dashboard-handoff.md
│   ├── macro_ai_codex_prompt.md
│   └── macro_ai_codex_schema.json
├── cli/
│   └── local helper scripts and ingestion tools
├── app.py
├── requirements.txt
└── README.md
```

## Scope And Maintenance Notes

- This repository contains both deploy-facing files and local research helpers.
- Public readers should treat `README.md`, `requirements.txt`, `.streamlit/`, and `app.py` as the deploy-relevant surfaces.
- If you are adapting this for production use, the next hardening step is usually replacing ad hoc public wrappers with more durable licensed or official feeds, then separating local-only features from cloud-safe ones.
