# Macro Dashboard — Known Issues / Accepted Visual Trade-offs

Last verified: 2026-07-13 (v17 final visual QA pass)

## v17 Terminal redesign — QA summary

- Final Playwright screenshot pass of all 18 tabs at 1600×900: **all tabs PASS** against the terminal checklist.
- `pytest tests/ -q` → **28 passed**.
- Emoji unicode-range grep outside `archive/` → **0 matches**.
- Fixed during QA:
  - Removed residual emoji characters from `app.py`, `HANDOFF_v16_phase2.md`, `REGIME_INTEGRATION_PLAN.md`, and `FRONTEND_REDESIGN.md`.
  - Added `a { color: cyan }` to `modules/theme.py` so inline links match the terminal accent instead of default browser blue.

## Remaining accepted items

These are intentional or unavoidable for the current design:

1. **Semantic chart colors**
   - Some bar charts, gauges, and heatmaps still use bright red / yellow / green for data values (e.g., risk-on / risk-off / neutral signals, Macro Regime Quadrant, composite gauges).
   - These colors are data-semantic, not UI chrome, and are retained because they communicate meaning faster than the terminal palette alone.
   - No white or pastel chart backgrounds remain.

2. **Horizontal tab scrolling on small viewports**
   - The top tab bar scrolls horizontally when the viewport is too narrow to fit all 18 tabs.
   - This is expected Streamlit behavior; wrapping the tabs would break the layout on desktop.

## Not a known issue

- Emoji anywhere in the UI or tracked source files: removed / zero matches.
- White / light chart backgrounds: none observed.
- `FutureWarning` from `Styler.applymap`: resolved.
- Missing chart titles / `undefined` Plotly titles: resolved.
