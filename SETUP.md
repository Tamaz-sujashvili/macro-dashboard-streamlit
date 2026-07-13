# Macro Regime Dashboard — Setup Guide

A Streamlit-based macro market dashboard with multi-detector regime monitoring.

---

## 1. Install

```bash
# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Core dependencies: `streamlit`, `pandas`, `numpy`, `plotly`, `requests`, `yfinance`, `fredapi`, `hmmlearn`, `scipy`.

---

## 2. Configure secrets

API keys are read from **`.streamlit/secrets.toml`** first, then environment variables, then runtime sidebar inputs. No keys are hard-coded in the source.

Create `.streamlit/secrets.toml`:

```toml
[secrets]
FRED_API_KEY = "your-fred-key"
ALPHA_VANTAGE_KEY = ""
BLS_API_KEY = ""
EIA_API_KEY = ""
FMP_API_KEY = ""
CFTC_APP_TOKEN = ""
NASDAQ_API_KEY = ""
CONGRESS_GOV_API_KEY = ""
FINNHUB_API_KEY = ""
```

### Required

- **FRED_API_KEY** — required for macro series (GDP, CPI, yields, NFCI, HY spreads, etc.).
  - Get one free at: https://fred.stlouisfed.org/docs/api/api_key.html

### Optional

Only add these if you use the associated tabs:

| Key | Used for |
| --- | --- |
| `ALPHA_VANTAGE_KEY` | News & Signals tab (Alpha Vantage news feed) |
| `BLS_API_KEY` | Labor & Consumer tab (BLS CES/CPS/PPI microdata) |
| `EIA_API_KEY` | Energy Futures tab (EIA petroleum data) |
| `FMP_API_KEY` | Institutional Flows / fundamentals |
| `CFTC_APP_TOKEN` | Institutional Flows tab (CFTC COT reports) |
| `NASDAQ_API_KEY` | Market data fallbacks |
| `CONGRESS_GOV_API_KEY` | X Intelligence / legislative data |
| `FINNHUB_API_KEY` | Institutional Flows tab (13F aggregate data) |

### Environment-variable fallback

Any secret can also be set as an environment variable with the same name:

```bash
export FRED_API_KEY="your-fred-key"
streamlit run macro_dashboard_streamlit-v15-x-intel.py
```

---

## 3. Run

```bash
streamlit run macro_dashboard_streamlit-v15-x-intel.py
```

- Default URL: `http://localhost:8501`
- The app uses a wide layout and dark theme defined in `.streamlit/config.toml`.

---

## 4. Tests

```bash
python3 -m pytest tests/ -q
```

Expected: all tests pass, including `tests/test_app_imports.py` (import smoke test) and `tests/test_regime_engine.py` (regime detector logic).

---

## 5. Troubleshooting

### Most live feeds are unavailable

If the app shows:

> Most live feeds are currently unavailable. Check internet/DNS access first, then verify your API keys in the sidebar.

- Confirm `FRED_API_KEY` is set in `.streamlit/secrets.toml` or as an env var.
- Check your internet connection / DNS.
- Some corporate networks block Yahoo Finance; try a different network or VPN.

### FRED rate limit / empty response

- The FRED API allows a limited number of requests per day.
- The dashboard caches FRED data for **1 hour** (`ttl=3600`).
- If you hit the limit, wait or upgrade to a FRED premium key.

### `yfinance` returns “possibly delisted; no price data found”

- Yahoo Finance may be unreachable, rate-limited, or the symbol may have changed.
- The dashboard silently falls back to cached data or empty placeholders; it will not crash.
- Wait a few minutes and refresh; the market-data cache expires in **15 minutes** (`ttl=900`).

### Regime Monitor shows stale timestamps

- The Regime Monitor footer shows the age of each source.
- A warning appears when data is older than **2× the refresh interval**.
- Click **Force Refresh** in the sidebar or delete the cache to refetch immediately.

### Streamlit theming looks wrong

- Ensure `.streamlit/config.toml` is present at the project root.
- Restart the app after editing it.

### Module import errors in tests

- Make sure you installed all requirements (`pip install -r requirements.txt`).
- Run tests from the project root: `python3 -m pytest tests/ -q`.
# Data provider secrets

Create `.streamlit/secrets.toml` (this file is ignored) with only the keys you use:

```toml
FRED_API_KEY = ""
BLS_API_KEY = ""
EIA_API_KEY = ""
CFTC_APP_TOKEN = ""
TIINGO_API_KEY = ""
POLYGON_API_KEY = ""
ALPHA_VANTAGE_KEY = ""
FMP_API_KEY = ""
FINNHUB_API_KEY = ""
EODHD_API_KEY = ""
```
