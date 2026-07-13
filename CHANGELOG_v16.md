# Changelog — v15 → v16

## Data providers

- Added ignored Streamlit secrets support and a masked Data Keys diagnostics panel with provider status and latency.
- Added yfinance-to-Tiingo SPY fallback, Polygon daily breadth scaffolding, FMP/Finnhub calendar feeds, and Finnhub SPY/QQQ news-sentiment tiles.
- Added a sixth, No-Data-safe Breadth detector to the Regime Monitor consensus.

## Overview

v16 introduces a single authoritative **Regime Monitor** tab, a reusable `modules/` engine/UI split, a consistent dark professional visual identity, and production-hardened fetch/caching. The goal is to remove scattered risk-on/off verdicts and duplicate widgets while making the dashboard more reliable and maintainable.

---

## 1. New `modules/regime_engine.py` — pure computation

- Added `RegimeSignal` dataclass: `detector_name`, `timeframe`, `state`, `risk_score` (-1..+1), `confidence`, `color`, `as_of`, `history`.
- Implemented five detectors:
  1. **TrendVol** — ports the Pine TE v9 logic from `regime_specs.md` (price vs EMA200, ADX gate, realized-vol percentile) on daily and resampled weekly SPY bars.
  2. **HMM** — 2-3 state Gaussian HMM on daily log returns via `hmmlearn`, fit on trailing 10 years, forward-filtered probabilities only.
  3. **VolRegime** — Calm/Stressed/Crisis from VIX level bands, VIX term-structure contango/backwardation, and SPY HV20 percentile.
  4. **Liquidity** — Loose/Tightening/Stressed from NFCI level + 60d ROC and HY OAS (BAMLH0A0HYM2) level + 60d ROC.
  5. **MacroQuadrant** — thin adapter converting the existing `compute_regime_state` output into a monthly `RegimeSignal`.
- Added `compute_consensus(signals)` producing per-timeframe weighted mean risk score, detector agreement %, and Risk-On/Neutral/Risk-Off label.
- All data paths are `None`-safe: any missing input emits a "No Data" signal instead of crashing the dashboard.

## 2. New `modules/regime_ui.py` and tab wiring

- Added `render_regime_monitor(fred, mkt)` with:
  - Consensus scoreboard (Daily / Weekly / Monthly).
  - Detector matrix table colored by state/score.
  - One expander per detector with current state, risk score, confidence, and a relevant historical chart with regime-span shading.
  - 3-year timeline heatmap of detector risk scores (RdYlGn).
  - Data-freshness footer with stale warnings.
- Wired the tab as the **first entry** in `ALL_TABS` in the main v15 file via the existing `tab_map` pattern.
- All UI data fetching is cached at the UI boundary (`@st.cache_data(ttl=3600)`).

## 3. Duplicate-widget cleanup

- **Regime Monitor is now the single authority for risk-on/off verdicts.**
- Replaced scattered verdict banners (e.g., quality rotation, premarket tape) with a one-line reference to the Regime Monitor.
- **Markets & Sentiment** now shows prices/breadth only; sentiment gauges live only in **Sentiment Framework**.
- Removed in-tab metric cards that duplicated the top-level KPI row.
- Standardized all tab labels to include emoji for visual consistency.

## 4. Visual identity

- Created `.streamlit/config.toml` with a dark professional theme:
  - `primaryColor="#34d399"`, `backgroundColor="#0e1117"`, `secondaryBackgroundColor="#1a1f2e"`.
- Added `modules/config.py` with:
  - `COLORS` palette (`risk_on`, `risk_off`, `neutral`, `accent`, `muted`, etc.).
  - `PLOTLY_LAYOUT` dict for consistent dark Plotly charts.
  - `apply_house_style(fig)` helper.
  - Formatting helpers: `fmt_pct`, `fmt_bp`, `fmt_dollar`.
- Applied the house style to Regime Monitor charts and the most-viewed charts (Macro Overview, GS-Style Composites).
- Replaced the default page title area with a compact header row showing app name, last refresh, and the current Daily consensus badge.

## 5. Production reliability

- Audited all network fetch functions and ensured every call has:
  - explicit `timeout=`
  - `try/except` returning a typed empty result
  - `@st.cache_data` with explicit TTL (macro data 3600s, market data 900s, regime detectors 3600s)
- Removed all hardcoded API keys; keys now come from `st.secrets` with `os.environ` fallback.
- Added `SETUP.md` documenting install, required secrets (`FRED_API_KEY`, etc.), run command, port, and troubleshooting (FRED rate limits, yfinance empty responses).
- Added `tests/test_app_imports.py` smoke test that imports the v15 module headless and asserts no import-time crash.
- Added `tests/test_regime_engine.py` synthetic-data unit tests (uptrend → risk-on, crash → risk-off, NaN-heavy input → "No Data").

## 6. Runtime fixes discovered during final QA

- **FRED SSL timeout workaround**: added a `curl` subprocess fallback in `_http_get` for `fred.stlouisfed.org` requests because Python `requests`/`urllib3` handshakes were hanging while `curl` completed in ~0.3 s.
- **HMM detector availability**: ensured the app runs under the project virtualenv (`.venv`) so `hmmlearn` is available; reduced `train_days` from 2520 to 1260 to match the ~2500-row SPY history returned by yfinance.
- **Sentiment Framework cache fix**: changed `fetch_singlestock_vs_index_vol_spread()` from `@st.cache_data` to `@st.cache_resource` so its `__main__`-defined return class no longer triggers a `PicklingError` on Streamlit cache serialization.

## Files changed

- `macro_dashboard_streamlit-v15-x-intel.py` — Regime Monitor wiring, header row, duplicate-widget cleanup, style updates, fetch hardening.
- `modules/regime_engine.py` — new pure-computation engine.
- `modules/regime_ui.py` — new Streamlit UI layer.
- `modules/config.py` — shared theme, colors, formatting helpers.
- `.streamlit/config.toml` — dark professional theme.
- `tests/test_regime_engine.py` — unit tests for detectors.
- `tests/test_app_imports.py` — import smoke test.
- `SETUP.md` — install/secrets/run/troubleshooting guide.
- `CHANGELOG_v16.md` — this file.

## 7. Senior review fixes

- **Monthly regime now shows real state.** Fixed `macro_quadrant_adapter` receiving empty `CPI_HIST`/`SPREAD_HIST` by normalizing FRED CSV column names (`DATE`/`VALUE` vs `observation_date`/series-id) in `_fredgraph_req` and in the new `modules/data_fetch.py`. Monthly now renders a live MacroQuadrant state (e.g., Reflation +0.40).
- **Disambiguated colliding state colors.** `_STATE_COLORS` in `modules/regime_ui.py` is now keyed by `(detector_name, state)` tuples so VolRegime "Stressed" renders neutral amber while Liquidity "Stressed" renders risk-off red. MacroQuadrant "Recession" now uses risk-off red instead of muted grey.
- **Removed Streamlit dependency from `modules/regime_engine.py`.** Moved `fetch_spy_vix_history`, `fetch_fred_latest`, and `fetch_fred_hist` (and their `@st.cache_data` decorators) into a new `modules/data_fetch.py`. `modules/regime_engine.py` remains a pure computation module with no Streamlit imports.
- **HMM detector now uses true forward-filtered inference and parquet cache.** Each day's regime probability is computed from `model.predict_proba` on the trailing `min(250, i)` observations ending at day `i`, taking only the last row — no smoothing that looks ahead. The full walk-forward history is computed once, persisted to `.cache/hmm_history_<params>.parquet`, and extended on subsequent runs from the last cached date.
- **QA artifacts organized.** Moved `orca_screenshot_review.py`, `orca_tab_check.py`, `orca_review_screenshots/`, and `index.html` into `archive/qa/`.

## Verification

- `streamlit run macro_dashboard_streamlit-v15-x-intel.py` starts with zero tracebacks.
- `python3 -m pytest tests/ -q` — 32 passed.
- No hardcoded API keys found in tracked files.
- Playwright screenshot review confirms:
  - Regime Monitor is the first tab and renders the consensus scoreboard (Daily Risk-On, Weekly Neutral, Monthly Risk-On), detector matrix, detector detail expanders, 3-year timeline heatmap, and data-freshness footer.
  - All 19 tabs switch without raising exceptions, including CALENDAR and the previously crashing Sentiment Framework tab.

## v17 — Terminal redesign final pass

- **Component standardization**
  - Replaced all macro/status verdict banners with `terminal_badge(...)` and removed emoji from every verdict string.
  - Converted the six top-level `st.metric` calls into `kpi_tile(...)` components.
  - Wrapped all numeric `st.dataframe(...)` displays with `style_dataframe(...)` for JetBrains Mono numerics and dark headers.
- **Theme / style fixes**
  - Fixed `apply_house_style()` in `modules/config.py` so Plotly charts without a caller title render a blank title instead of the literal string `undefined`.
  - Migrated `modules/theme.py` from deprecated `Styler.applymap` to `Styler.map`.
  - Added link styling so inline anchors use the cyan accent (`#22d3ee`) instead of default browser blue.
- **QA / verification**
  - Added `archive/qa/v17_tab_check.py` to screenshot every tab at 1600×900 and check page styles, fonts, and emoji counts.
  - Grep for emoji unicode ranges outside `archive/` returned **0 matches** after cleaning `app.py` and remaining markdown docs.
  - Playwright final pass: all 19 tabs PASS with dark `#0a0e14` background, `#11161f` panels, cyan accent, JetBrains Mono numerals, uppercase terminal tab nav, no default Streamlit red/orange chrome, and no white chart backgrounds. CALENDAR and the Regime Monitor BREADTH panel passed QA.
  - `pytest tests/ -q` → **32 passed**.
