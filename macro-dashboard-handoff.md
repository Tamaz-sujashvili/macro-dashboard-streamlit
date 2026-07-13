# Macro Dashboard Project Handoff

## Main files
- Local dashboard: `/Users/tazo/Desktop/macro_dashboard_streamlit-v12-polished.py`
- Streamlit deploy repo: `/Users/tazo/Desktop/macro ouputs/macro-dashboard-streamlit-deploy/app.py`
- GitHub repo: `https://github.com/suja-labarum/macro-dashboard-streamlit`

## Current deployed branch
- Branch: `main`
- Latest pushed commit: `89b8bde Redesign energy futures charts`

## What this dashboard does
Streamlit macro dashboard with live macro, liquidity, sentiment, options, institutional flow, premarket, AI macro analysis, global macro, GS-style composites, and energy futures sections.

## Important recent changes
- Added and redesigned the Energy Futures tab.
- Energy Futures now includes:
  - Oil Market 3-Signal Summary
  - Where the Market Thinks Oil Prices Are Heading
  - Oil Price Forecast range band
  - How Much Extra Each Month Costs
  - US Oil vs Global Oil price gap
- Added local futures CSV fallback:
  `/Users/tazo/Desktop/macro ouputs/futures-spreads-clm26-04-23-2026.csv`
- Pushed latest deploy version to GitHub.

## Run deploy version locally
```bash
cd "macro-dashboard-streamlit-deploy"
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

## Run standalone script locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install streamlit pandas numpy plotly requests yfinance beautifulsoup4 lxml openpyxl scipy
python3 -m streamlit run macro_dashboard_streamlit-v12-polished.py
```

## Deployment
The deployable Streamlit file is:
`macro-dashboard-streamlit-deploy/app.py`

Push command from deploy repo:
```bash
git status
git add app.py
git commit -m "Describe change"
git push origin main
```

## API key/privacy note
Do not hardcode API keys in the Python file for public deployment. Use Streamlit Cloud Secrets instead.

## Known priorities
- Keep beginner/professional mode stable.
- Avoid repeated sentence translation bugs.
- Verify live data freshness before adding new signal logic.
- Prefer official or traceable data sources.
- Keep deploy `app.py` synced with local polished script when needed.

## New Codex start prompt
Read this handoff first. Continue from the current deployed Streamlit dashboard. Preserve existing functionality unless explicitly asked to change it. When editing, update `macro-dashboard-streamlit-deploy/app.py` for deployment and keep the standalone polished script synced if needed.
