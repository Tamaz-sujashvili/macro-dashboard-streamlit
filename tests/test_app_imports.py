"""Smoke test: the v15 dashboard module can be imported without crashing.

This guards against import-time regressions (missing dependencies, top-level
Streamlit errors, syntax issues) in CI or fresh environments.
"""

import importlib.util
import os
import sys
from pathlib import Path

import streamlit as st


# The module calls st.set_page_config at import time.  Stub it so the test
# runs headless and does not need a live Streamlit session.
st.set_page_config = lambda **kwargs: None


def test_import_v15_module():
    root = Path(__file__).resolve().parent.parent
    file_path = root / "macro_dashboard_streamlit-v15-x-intel.py"
    assert file_path.exists(), f"{file_path} not found"

    spec = importlib.util.spec_from_file_location("macro_dashboard_v15", file_path)
    module = importlib.util.module_from_spec(spec)

    # Force the module to execute, which validates top-level imports and the
    # st.set_page_config call.
    spec.loader.exec_module(module)

    # Sanity checks that the expected shared modules were loaded.
    assert hasattr(module, "main")
    assert hasattr(module, "render_regime_monitor")
    assert module.COLORS["risk_on"] == "#34d399"
