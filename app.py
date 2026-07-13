"""Streamlit Cloud entrypoint for the production macro dashboard.

The repository's real dashboard lives in the versioned v15/v17 script.  This
small launcher keeps Streamlit Cloud's default ``app.py`` entrypoint working
without requiring a manual Main file path override.
"""

from pathlib import Path
import runpy


_DASHBOARD = Path(__file__).with_name("macro_dashboard_streamlit-v15-x-intel.py")

if not _DASHBOARD.is_file():
    raise FileNotFoundError(f"Dashboard entrypoint not found: {_DASHBOARD}")

runpy.run_path(str(_DASHBOARD), run_name="__main__")
