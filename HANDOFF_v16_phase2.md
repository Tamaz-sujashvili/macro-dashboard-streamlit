# Session Handoff — Macro Dashboard v15 Terminal Redesign Phase 2

Date: 2026-07-13  
Working directory: `/Users/tazo/Desktop/macro dashboard`  
Plan file: `/Users/tazo/.kimi-code/sessions/wd_macro-dashboard_77ce7c5b431a/session_1ab16556-a6be-4b7e-9c96-39644f22bc05/agents/main/plans/wonder-woman-flash-crystal.md`

---

## Goal
Apply the dark terminal aesthetic consistently across **all** Plotly charts, verdict banners, tables, KPIs, and the Regime Monitor tab, then verify every tab via Playwright screenshots.

Design tokens: page bg `#0a0e14`, panel `#11161f`, border `#1e2733`, text `#e6edf3`, secondary `#8b98a9`, accent cyan `#22d3ee`, risk-on `#34d399`, risk-off `#f87171`, neutral `#fbbf24`. Fonts: Space Grotesk (UI), JetBrains Mono (numbers).

---

## Completed

### Phase 1 — Shared style upgrades [done]
- `modules/config.py`
  - `apply_house_style()` upgraded: dot gridlines `#1e2733`, hairline axes, JetBrains Mono 10px ticks, uppercase micro-label title, horizontal top-right mono legend, fixed `colorway`, transparent backgrounds that override caller settings.
  - Added `"border": "#1e2733"` to `COLORS`.
- `modules/theme.py`
  - Added `terminal_badge(text, level)` — inline panel, 2px left semantic border, uppercase mono 11px.
  - Added `kpi_tile(label, value, delta, delta_color)` — big mono value, uppercase label, thin top semantic border, `+/-` delta.
  - Added `style_dataframe(df)` — pandas Styler with mono font, right-aligned numerics, red/green signed values, dark header.

### Phase 2 — Chart sweep [done]
- `macro_dashboard_streamlit-v15-x-intel.py`
  - Subagent updated 48 Plotly builders; all 66 chart/gauge/heatmap/radar builders now end with `apply_house_style(fig)`.
  - 4 inline `st.plotly_chart` calls wrapped with `apply_house_style`.
  - 8 gauges restyled to thin arc, dark bg, mono number, no gradient fill.
  - Removed 102 `template=DARK_TEMPLATE`, 102 `paper_bgcolor=PAPER_BG`, 71 `plot_bgcolor=CHART_BG` conflicts.
  - All `key=` arguments preserved.

### Phase 4 — Regime Monitor polish [done]
- `modules/regime_ui.py`
  - Consensus scoreboard converted to terminal tiles: big mono score, uppercase timeframe label, thin colored top border.
  - Detector matrix: mono header/cells, hairline grid.
  - Timeline heatmap: replaced default `RdYlGn` with dark-friendly custom colorscale (`#f87171` → dark red → `#0a0e14` → dark green → `#34d399`).

### Validation so far [done]
- `PYTHONPATH="." .venv/bin/pytest tests/ -q` → **28 passed**.
- `python -m py_compile` passes for all modified `.py` files.

---

## Pending / Next Session

### Phase 3 — Verdict banners → badges
Replace macro/status verdict `st.success` / `st.error` / `st.warning` calls with `terminal_badge(...)`.

Key locations (line numbers current as of handoff):
- ~8683–8719: Macro Overview verdicts (GDP, CPI, recession, unemployment, credit, Sahm Rule, savings, M2, sentiment).
- ~8746–8760: Energy verdicts (backwardation, contango, Brent premium, spread velocity).
- ~8773–8780: Labor & Consumer verdicts (unemployment, jobless claims).
- ~8999–9006: Housing & Credit verdicts (mortgage, HY spreads).
- ~9022–9024: Metals verdicts (gold, copper).
- ~9164–9166: Global Macro verdicts (DXY).
- ~9285–9295: Options & Derivatives verdicts (VIX backwardation, PCR, SKEW, VVIX, GEX).
- ~9751–9764: Liquidity verdicts.
- ~10089–10093: Yield curve verdicts.
- ~10253–10272: Flows / institutional verdicts.
- ~11185–11187: Sentiment verdicts.
- ~13292–13308: Sidebar/X-Intel verdicts.

Note: `terminal_badge` is already imported at the top of the main app. Purely informational `st.info` messages can stay as alerts.

### Phase 5 — KPI row tiles
Convert the six top `st.metric` calls (~13068–13095) to `kpi_tile(...)`:
- GDP (GDPNow)
- CPI Inflation
- Unemployment
- Fed Funds Rate
- Recession Prob
- CAPE Ratio

`kpi_tile` is already imported.

### Phase 6 — Dataframe styling
Wrap numeric `st.dataframe(...)` calls with `style_dataframe(df)`:
- `diag_df` (~4653)
- `fred_errs` (~4655)
- `source_audit_df` (~4713)
- `futures_curve[cols]` (~8881)
- `df_log` (~10446)
- `summary_df` (~12750)

`style_dataframe` is already imported.

### Phase 7 — Verification
- Extend `archive/qa/orca_tab_check.py` (or create `archive/qa/orca_all_tabs.py`) to screenshot all 18 tabs.
- Run full-tab Playwright check.
- Inspect screenshots for: zero emoji, zero white/pastel chart backgrounds, mono numerals, consistent dark theme.
- Create `KNOWN_ISSUES.md` listing any chart/widget that could not be styled.

---

## Files changed so far
- `modules/config.py`
- `modules/theme.py`
- `modules/regime_ui.py`
- `macro_dashboard_streamlit-v15-x-intel.py`

## Files still to create/modify
- `macro_dashboard_streamlit-v15-x-intel.py` (verdict banners, KPI tiles, dataframe styling)
- `archive/qa/orca_tab_check.py` (extend to all 18 tabs)
- `KNOWN_ISSUES.md` (new)

---

## Notes
- The Streamlit server may still be running on `localhost:8501` from verification; kill or reuse as needed.
- No git repo in this directory; changes are in-place.
- The previous Macro Overview blank-tab bug is fixed; expanding detector charts were removed in an earlier session.
