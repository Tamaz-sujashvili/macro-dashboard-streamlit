# Macro Dashboard v16 — Regime Integration & Professionalization Plan

Senior-quant review of `macro_dashboard_streamlit-v15-x-intel.py` (14,265 lines) plus execution prompts for Kimi Code. Run prompts in order, each in a fresh session, in the folder stated at the top of each prompt.

---

## Part 1 — Review verdict

### What's good
- Data breadth is institutional-grade: FRED, Treasury, options surface, COT, ICI flows, 13F, VIX term structure, liquidity (SOFR, Amihud), X intelligence.
- GS-style composites and the credit×inflation regime quadrant are legitimate frameworks.
- Beginner-label translation layer is a nice product touch.

### What blocks "finished product" status
1. **Monolith**: 14k lines in one file. Every change risks the whole app. No tests possible.
2. **Five uncoordinated risk-on/off verdicts** (macro quadrant, GS risk appetite, quality rotation, premarket tape, MMF flows) scattered across tabs. A professional product has ONE regime section that reconciles them.
3. **Section duplication**: sentiment appears in "Markets & Sentiment", "Sentiment Framework", and Fear&Greed widgets; VIX appears in Options, Sentiment, and Markets; recession probability appears in KPI row, GS composites, and Macro Overview.
4. **Repo hygiene**: ~15 legacy files (`v11`, `v12`, `phillips copy`, `mkkkacro...`, `.rtf`) sit next to the live file. `streamlit_secrets_ready_to_paste.toml` in the repo is a credential risk.
5. **No config layer**: thresholds (e.g., "20% recession alert", "25 CAPE avg") are hardcoded magic numbers.
6. **Visualization**: Plotly is fine — keep it. Streamlit+Plotly is the standard stack; alternatives (ECharts, lightweight-charts) add complexity for no analytical gain. The polish problem is inconsistent theming, not the library.

### Regime Monitor design (the new centerpiece)
One new tab, first position, named **"Regime Monitor"**. A detector × timeframe matrix:

| Detector | Source | Timeframes | Output |
|---|---|---|---|
| Macro Quadrant | existing `compute_regime_state` (credit ROC × inflation ROC) | Monthly | Goldilocks / Reflation / Stagflation / Recession |
| Trend+Vol (TV port) | ported from quant-alpha-swarm TE v9 Pine logic: price vs EMA200, ADX threshold, realized-vol percentile — on SPY | Daily, Weekly | Risk-On / Neutral / Risk-Off |
| HMM | 2–3 state Gaussian HMM on SPY log returns (`hmmlearn`), fit on trailing 10y, walk-forward, never refit intraday | Daily | Low-vol bull / High-vol bear / Transition + state probability |
| Volatility Regime | VIX level + term structure (contango/backwardation, already fetched) + HV20 percentile | Daily | Calm / Stressed / Crisis |
| Liquidity & Credit | FRED: NFCI, HY OAS level+ROC (already fetched) | Weekly | Loose / Tightening / Stressed |

Top of tab: **consensus scoreboard** — one row per timeframe (Daily / Weekly / Monthly), each cell colored, plus a composite score = weighted vote with detector agreement %. Below: one Plotly chart per detector (SPY price shaded by regime state), plus a historical regime-timeline heatmap (detectors × time). This gives the "multiple regime detections, multiple timeframes, one section" requirement.

---

## Part 2 — Prompts for Kimi Code

### PROMPT 1 — Extract regime specs (folder: `quant-alpha-swarm`) — READ-ONLY

```
Work in /Users/tazo/Desktop/quant-alpha-swarm. This repo has strict governance (CLAUDE.md): do NOT modify, move, or delete anything in this repo — you are strictly READ-ONLY here. Do not touch runtime/, projects/, or strategies/ contents. Write your single output file OUTSIDE this repo, to: "/Users/tazo/Desktop/macro dashboard/regime_specs.md".

Task: extract implementable regime-detection specifications for a Python macro dashboard.

1. Read strategies/pine/te_v9_1_CORE.pine and strategies/pine/research/READY_TO_USE/TE_v9.4_ADX_GATE_SplitHalf.pine. Document exactly: the ADX filter (length, threshold, direction), the relative-volume filter, any EMA/trend filter, and any ATR/volatility gating — with exact parameter values and formulas.
2. Read unified-wiki/concepts/regime-switching-methods.md, unified-wiki/concepts/regime-detection.md (if present), and grep unified-wiki/ for "HMM", "clustering detector", "Bayesian smoothing", "regime". Summarize each regime-detection method described: inputs, states, update rule, recommended smoothing, and known pitfalls (especially look-ahead bias and refit frequency).
3. Write "/Users/tazo/Desktop/macro dashboard/regime_specs.md" with one section per detector: (a) TrendVol detector spec ported from the Pine logic — translate Pine formulas to explicit pandas pseudocode with exact parameters; (b) HMM detector spec (2-3 state Gaussian on daily log returns, trailing 10y fit, forward-only inference); (c) any additional detector the wiki supports well enough to spec numerically. Every spec must state: inputs, parameters, output states, update frequency, and how to avoid look-ahead bias.

Do not invent parameters — if a value isn't in the source files, mark it "NOT SPECIFIED, propose default X" explicitly.
```

### PROMPT 2 — Repo hygiene + module skeleton (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard". The live app is macro_dashboard_streamlit-v15-x-intel.py (14k lines, runs at http://127.0.0.1:8501 via streamlit run). DO NOT edit the v15 file in this prompt.

1. Create archive/ and move all legacy files into it: every macro_dashboard_streamlit*.py EXCEPT the v15 file, all *phillips*.py, mkkkacro*.py, *html_alpha*.py, macro_dashboard_html.py, update_alpha_macro.py.rtf, "macro_dashboard_streamlit-v12-polished copy.txt", 1macro_dashboard_html_alpha.py, Fmacro_dashboard_phillips.py, Lovable App.html, lovable1_dashboard_html_alpha.py. Keep app.py, kaggle data, worldmonitor-main, treemap scripts in place.
2. Move streamlit_secrets_ready_to_paste.toml into archive/ and create .gitignore covering secrets*.toml, .streamlit/secrets.toml, __pycache__, archive/.
3. Create a modules/ package: modules/__init__.py, modules/regime_engine.py (empty stub with docstring), modules/regime_ui.py (stub), modules/config.py containing a THRESHOLDS dict for magic numbers (recession_alert=20, cape_avg=25, unemployment_natural=4.0, cpi_target=2.0, gdp_trend=2.0).
4. Create requirements.txt by scanning imports of the v15 file (streamlit, pandas, numpy, plotly, requests, yfinance, etc.) plus hmmlearn and scipy for upcoming work.
5. Verify: streamlit run macro_dashboard_streamlit-v15-x-intel.py still starts without error (imports unchanged). Report the final folder tree.
```

### PROMPT 3 — Build the regime engine (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard". Read regime_specs.md (detector specifications) and modules/config.py first. Also read the existing regime code in macro_dashboard_streamlit-v15-x-intel.py: functions _classify_regime, compute_regime_state (around line 4110-4260), and compute_gs_style_composites — you will REUSE these, not duplicate them.

Build modules/regime_engine.py:

1. RegimeSignal dataclass: detector_name, timeframe ("D"/"W"/"M"), state (str), risk_score (float -1..+1, -1=max risk-off), confidence (0..1), color (hex), as_of (date), history (DataFrame with date/state/risk_score).
2. Detectors, each a function returning RegimeSignal(s):
   - trend_vol_detector(prices_df, timeframe): port the Pine TE v9 logic per regime_specs.md — price vs EMA200, ADX gate, realized-vol percentile. Compute on SPY daily and weekly bars (resample daily→weekly).
   - hmm_detector(prices_df): 2-3 state Gaussian HMM on daily log returns via hmmlearn, fit on trailing 10 years, label states by mean/vol (low-vol-bull = risk-on), forward-filtered probabilities only (no smoothing that uses future data). Cache the fitted model; refit at most weekly.
   - vol_regime_detector(vix_value, vix_term_structure, spy_prices): Calm/Stressed/Crisis from VIX level bands, contango/backwardation, HV20 percentile.
   - liquidity_regime_detector(fred): Loose/Tightening/Stressed from NFCI and HY OAS (BAMLH0A0HYM2) level + 60d ROC. FRED fetch helpers already exist in the v15 file — import or replicate the minimal fetch, respecting its caching pattern.
   - macro_quadrant_adapter(fred): thin wrapper converting existing compute_regime_state output into a RegimeSignal (monthly).
3. compute_consensus(signals) -> dict per timeframe: weighted mean risk_score, agreement %, label (Risk-On > 0.3, Neutral, Risk-Off < -0.3).
4. Data: use yfinance for SPY/^VIX history (10y daily). Wrap all fetches in try/except returning None-safe RegimeSignals with state "No Data" — the dashboard must never crash on a data gap.
5. Write tests/test_regime_engine.py with synthetic-data unit tests: monotone uptrend low-vol → risk-on; crash series → risk-off; NaN-heavy input → "No Data" not exception. Run pytest and make it pass.

No Streamlit imports in regime_engine.py — pure computation module.
```

### PROMPT 4 — Regime Monitor tab UI (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard". Read modules/regime_engine.py and how tabs are built in macro_dashboard_streamlit-v15-x-intel.py (ALL_TABS list around line 13424, tab rendering below it, and an example renderer like render_gs_style_composites around line 9588 for style conventions).

Build modules/regime_ui.py with render_regime_monitor(fred, mkt) and wire it in:

1. Add "Regime Monitor" as the FIRST entry of ALL_TABS and render it via the same tab_map pattern. Import from modules.regime_ui at the top of the v15 file. Keep the edit to the v15 file minimal: one import, one list entry, one with-block.
2. Tab layout, top to bottom:
   a. Consensus scoreboard: st.columns row per timeframe (Daily/Weekly/Monthly) — big colored badge Risk-On/Neutral/Risk-Off, composite score, detector agreement %. Use green #34d399 / amber #fbbf24 / red #f87171 to match existing app colors.
   b. Detector matrix: a Plotly table or styled dataframe, rows = detectors, columns = timeframes, cells colored by state with score.
   c. One expander per detector containing: current state + confidence metric, and a Plotly chart of SPY (or the relevant series) with background shading by historical regime state (use fig.add_vrect for regime spans).
   d. Regime timeline heatmap: Plotly heatmap, x = last 3 years of dates, y = detectors, z = risk_score, RdYlGn colorscale — shows when detectors agreed/diverged.
3. Everything cached with @st.cache_data(ttl=3600) at the UI-fetch boundary. Every chart gets a unique key= (existing convention: key="chart_...").
4. If any detector returns "No Data", render a grey badge, not an error.
5. Verify by running streamlit run macro_dashboard_streamlit-v15-x-intel.py and confirming the tab renders with all 5 detectors and no exceptions in terminal output.
```

### PROMPT 5 — Deduplicate & consolidate sections (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard" on macro_dashboard_streamlit-v15-x-intel.py. Goal: remove duplicated/overlapping content now that Regime Monitor is the single risk-on/off authority. Make a backup copy to archive/ first.

1. Audit and report duplication before cutting anything: search where these appear more than once across tabs — VIX metrics, Fear&Greed, recession probability, risk-on/off verdicts (quality rotation ~line 13761, premarket tape ~line 9434, MMF risk-off ~line 10812), CAPE, yield-curve spread. Produce a table: item / tab locations / keep-where / remove-where.
2. Apply: keep each indicator in exactly one primary tab. Risk-on/off verdicts: replace scattered verdict banners with a one-line reference "See Regime Monitor" or a small shared badge calling modules.regime_engine consensus (do NOT recompute independently).
3. Merge "Markets & Sentiment" and "Sentiment Framework" overlap: sentiment gauges live only in Sentiment Framework; Markets tab keeps prices/breadth only.
4. Remove the KPI-row metrics that repeat identically inside tabs (keep the KPI row, remove in-tab duplicates).
5. Do not delete any fetch functions still used elsewhere. After edits: streamlit run must start clean; click through every tab mentally by checking each render_* still referenced. Report lines removed and final tab list.
```

### PROMPT 6 — Design polish pass (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard" on macro_dashboard_streamlit-v15-x-intel.py and modules/. Goal: consistent professional visual identity. No functional changes.

1. Create .streamlit/config.toml with a dark professional theme: base="dark", primaryColor="#34d399", backgroundColor="#0e1117", secondaryBackgroundColor="#1a1f2e", font="sans serif".
2. Define in modules/config.py a PLOTLY_LAYOUT dict (template="plotly_dark", consistent font family/size, margin=dict(l=40,r=20,t=40,b=30), transparent paper/plot bg, unified hovermode="x unified") and a COLORS palette (risk_on #34d399, risk_off #f87171, neutral #fbbf24, accent #60a5fa, muted #94a3b8). Apply via a helper apply_house_style(fig) and update the Regime Monitor charts plus the 10 most-viewed charts (Macro Overview, GS Composites) to use it. Do not attempt all 79 charts in one pass.
3. Standardize tab labels: either all with emoji or none — pick all-emoji, add missing ones (Bond Auctions, Energy Futures, Liquidity Conditions, Institutional Flows, GS-Style Composites, Global Macro, Sentiment Framework).
4. Page header: replace default title area with a compact header row — app name "Macro Regime Dashboard", last-refresh timestamp, and the current Daily consensus badge from regime_engine (small, top-right).
5. Consistent number formatting helper: percentages 1 decimal, bp 0 decimals, large $ with thousands separators — apply in Regime Monitor and KPI row.
6. Verify: app starts, dark theme active, no chart renders with default white background in the updated tabs.
```

### PROMPT 7 — Backend hardening (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard". Goal: production reliability. Files: macro_dashboard_streamlit-v15-x-intel.py, modules/.

1. Audit all network fetch functions (fetch_fred, fetch_treasury, fetch_market, yfinance calls in modules/regime_engine.py, etc.): every one must have timeout=, try/except returning a typed empty result, and @st.cache_data with explicit ttl (macro data ttl=3600, market data ttl=900, regime detectors ttl=3600).
2. API keys: all keys must come from st.secrets with os.environ fallback — grep for any hardcoded key strings and remove them. Document required secrets in a new SETUP.md (FRED key, any X/AI keys) with .streamlit/secrets.toml template.
3. Add a data-freshness footer to the Regime Monitor tab: per-source last-updated timestamp and stale warning if > 2x ttl.
4. Add a simple smoke test tests/test_app_imports.py that imports the v15 module with streamlit stubbed/headless and asserts no import-time crash; run pytest.
5. Create SETUP.md: install (pip install -r requirements.txt), secrets setup, run command, port, and a troubleshooting section for common failures (FRED rate limit, yfinance empty response).
```

### PROMPT 8 — Final verification (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard". Final QA of the finished product at http://127.0.0.1:8501.

1. streamlit run macro_dashboard_streamlit-v15-x-intel.py. Capture terminal output for the full startup; zero tracebacks allowed.
2. Checklist — verify and report pass/fail for each: (a) Regime Monitor is first tab and shows 5 detectors × consensus scoreboard; (b) all three timeframes show a state; (c) timeline heatmap renders 3y history; (d) no tab raises an exception; (e) no duplicate VIX/Fear&Greed/recession widgets across tabs; (f) dark theme consistent in updated tabs; (g) pytest passes; (h) no secrets in tracked files.
3. Any failure: fix it if under ~20 lines, otherwise document it in KNOWN_ISSUES.md with exact file/line.
4. Write CHANGELOG_v16.md summarizing everything changed from v15.
```

---

## Part 3 — Notes & guardrails

- **Order matters**: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Prompts 5–7 can be reordered if needed; 3 depends on 1's output file.
- **quant-alpha-swarm is read-only** for this project. Its CLAUDE.md forbids runtime edits and file moves; Prompt 1 respects that by writing output into the macro dashboard folder.
- **HMM caveat**: fit on trailing window, forward-filter only. A smoothed HMM repaints history and will look deceptively good — same failure class as OOS peeking.
- **Don't split the monolith yet.** New code goes in modules/; the 14k file shrinks gradually (Prompt 5 cuts, future versions extract). A big-bang refactor of a working 14k-line app is how you lose a week.
- **Plotly stays.** Consistency (Prompt 6 house style) is what makes it look professional, not a library swap.
- Later ideas (v17+): regime-conditional playbook per state (what historically works in each regime), alerting when consensus flips, persisting regime history to a local parquet so history survives restarts.
