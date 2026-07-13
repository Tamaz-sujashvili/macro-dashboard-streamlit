# Frontend Redesign — v17 "Terminal" Look

Goal: dark, cool, futuristic, zero emojis, no default-Streamlit look. Aesthetic reference: Bloomberg Terminal / sci-fi ops console — near-black surfaces, hairline borders, one cold accent color, monospace numerals, uppercase micro-labels. Run prompts in order in `macro dashboard`.

## Design system (locked — all prompts must follow this)

- Backgrounds: page `#0a0e14`, panel `#11161f`, hover `#161d29`
- Hairline borders: `#1e2733`, 1px, radius 4px (sharp, not rounded/bubbly)
- Text: primary `#e6edf3`, secondary `#8b98a9`, disabled `#4d5866`
- Accent (ONE only): cyan `#22d3ee` — used for active nav, links, focus, key lines
- Semantics unchanged: risk-on `#34d399`, risk-off `#f87171`, neutral `#fbbf24`
- Fonts: headings/UI = "Space Grotesk", data/numbers/tickers = "JetBrains Mono" (Google Fonts)
- Micro-labels: 10-11px, uppercase, letter-spacing 0.08em, secondary color
- NO emojis anywhere. NO gradients on panels. No default Streamlit red accent.

---

## PROMPT 10 — Design system core + emoji purge (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard". App: macro_dashboard_streamlit-v15-x-intel.py + modules/. Back up the v15 file to archive/ first. This is a visual redesign to a dark futuristic terminal aesthetic. Design tokens (use EXACTLY these): page bg #0a0e14, panel #11161f, border #1e2733 1px radius 4px, text #e6edf3, secondary text #8b98a9, single accent cyan #22d3ee, risk-on #34d399, risk-off #f87171, neutral #fbbf24. Fonts: Space Grotesk (headings/UI), JetBrains Mono (all numbers, tickers, timestamps).

1. EMOJI PURGE: remove every emoji from the entire codebase — tab labels in ALL_TABS and _display_tab_label, section headers, st.success/st.error/st.warning/st.info strings (green/red/yellow circles, warning, compass, bank, briefcase, currency, chart-down, coin, house, chart, newspaper, robot, etc.), captions, and modules/regime_ui.py. Tab labels become plain uppercase-style text: "REGIME MONITOR", "MACRO OVERVIEW", "LABOR & CONSUMER", "MARKETS", "OPTIONS & DERIVATIVES", "METALS", "HOUSING & CREDIT", "PHILLIPS CURVE", "NEWS & SIGNALS", "LIQUIDITY", "FLOWS", "COMPOSITES", "GLOBAL MACRO", "SENTIMENT", "AI ANALYSIS", "X INTEL", "BOND AUCTIONS", "ENERGY". Grep for remaining emoji with a unicode-range regex and confirm zero matches.
2. Create modules/theme.py exporting inject_theme() that renders one <style> block via st.markdown(unsafe_allow_html=True), called once at app start. It must:
   a. Import the two Google Fonts.
   b. Set page bg #0a0e14; hide Streamlit chrome: #MainMenu, footer, header[data-testid="stHeader"], the "Deploy" button.
   c. Restyle st.tabs into a terminal nav: transparent background, borderless, uppercase JetBrains Mono 11px letter-spacing 0.08em tabs, secondary color; active tab = accent cyan text with a 2px cyan bottom border. No pill/rounded shapes.
   d. Restyle st.metric: panel bg #11161f, 1px #1e2733 border, radius 4px, padding 12px; label = uppercase micro-label style; value = JetBrains Mono 22px #e6edf3.
   e. Restyle st.alert boxes (success/error/warning/info): flat panel bg, 2px left border in the semantic color, no emoji icon, no rounded bubble.
   f. Restyle expanders, dataframes, sidebar (sidebar bg #0d1219, uppercase section labels), buttons (transparent bg, 1px border, cyan on hover), dividers to hairlines.
3. Update .streamlit/config.toml: backgroundColor="#0a0e14", secondaryBackgroundColor="#11161f", primaryColor="#22d3ee", textColor="#e6edf3".
4. Update modules/config.py: COLORS to the new tokens (keep semantic keys and risk colors), PLOTLY_LAYOUT font family "JetBrains Mono", gridcolor #1e2733, zerolinecolor #1e2733.
5. Rebuild the page header as a terminal status bar: single full-width row, panel bg, hairline bottom border — left: "MACRO REGIME TERMINAL" in Space Grotesk 14px letter-spaced; center: UTC timestamp ticking format "2026-07-12 14:03 UTC" in mono; right: Daily consensus badge (colored square + "RISK-ON +0.53" in mono). No emoji, no st.title anywhere.
6. Verify: streamlit run starts clean; screenshot the Regime Monitor and Macro Overview tabs (playwright, as in archive/qa/orca scripts) and confirm: no emoji visible, dark bg, mono numerals, cyan-only accent.
```

## PROMPT 11 — Component & chart sweep (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard". Continue the terminal redesign (tokens in modules/config.py and modules/theme.py — read them first, follow exactly; no emojis, single cyan accent).

1. Charts: sweep ALL st.plotly_chart figures in macro_dashboard_streamlit-v15-x-intel.py and modules/regime_ui.py through apply_house_style(). Then upgrade apply_house_style: gridlines #1e2733 dash "dot", axis line hairline, tick font JetBrains Mono 10px #8b98a9, title as uppercase micro-label, legend horizontal top-right 10px mono, colorway ["#22d3ee","#34d399","#f87171","#fbbf24","#8b98a9","#60a5fa"]. Remove any per-chart hardcoded template/paper_bgcolor that conflicts. Gauges (GS composites): restyle to thin arc, dark bg, mono number, no gradient fill.
2. Replace remaining st.success/st.error verdict banners with a shared badge(text, level) helper in modules/theme.py: inline-block, panel bg, 2px left border in semantic color, uppercase mono 11px text like "RISK-OFF PRE-OPEN TAPE".
3. Regime Monitor polish: consensus scoreboard cells become terminal tiles — big mono score, small uppercase timeframe label, thin colored top border (not filled backgrounds); detector matrix table dark with hairline grid; heatmap uses a dark-friendly custom colorscale from #f87171 through #0a0e14-adjacent dark neutral to #34d399 (not default RdYlGn which reads pastel on dark).
4. Tables/dataframes: st.dataframe styling via pandas Styler where used — mono font, right-aligned numerics, red/green for signed values.
5. KPI row at top: convert the six st.metric into the new tile look, values mono, deltas as small colored mono text with ▲▼ replaced by "+"/"-" (no arrows/emoji).
6. Verify with playwright screenshots of ALL tabs: zero white/pastel chart backgrounds, zero emojis, consistent fonts. Fix any chart that ignored the sweep. List any charts left unstyled in KNOWN_ISSUES.md.
```

## PROMPT 12 — Final design QA (folder: `macro dashboard`)

```
Work in "/Users/tazo/Desktop/macro dashboard". Final visual QA of the terminal redesign at http://127.0.0.1:8501.

1. Playwright: screenshot every tab at 1600x900 into archive/qa/v17_screens/. Review each image and report pass/fail per tab against this checklist: (a) no emoji anywhere; (b) page bg #0a0e14, panels #11161f with hairline borders; (c) only cyan #22d3ee as accent besides semantic red/green/amber; (d) all numbers in JetBrains Mono; (e) tab nav is the uppercase terminal style; (f) no default Streamlit red/orange elements, no white chart backgrounds; (g) header status bar renders with live consensus badge.
2. Run pytest — all tests must still pass (theme changes must not touch engine logic).
3. Grep the repo for emoji unicode ranges one final time — must be zero outside archive/.
4. Fix failures under 20 lines each; log bigger items in KNOWN_ISSUES.md. Append a "v17 Terminal redesign" section to CHANGELOG_v16.md (or start CHANGELOG_v17.md).
```

## Notes

- Streamlit CSS selectors (data-testid) change between versions — the prompts target stable testids, but if a selector misses, inspect the live DOM rather than guessing.
- Keep ALL logic untouched: this is presentation only. If a prompt session proposes touching regime_engine or fetch logic, refuse it.
- If after this it still reads too "Streamlit", the next escalation is the hybrid path: FastAPI + custom HTML/JS page for Regime Monitor only. Don't start that until v17 ships.
