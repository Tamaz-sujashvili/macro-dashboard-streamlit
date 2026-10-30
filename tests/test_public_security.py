"""Protect server credentials and local-only features in the public demo."""

from pathlib import Path
import runpy

import pytest
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "macro_dashboard_streamlit-v15-x-intel.py"
SENTINEL = "SERVER_SECRET_DO_NOT_SEND_4719"


def _sidebar():
    return AppTest.from_string(
        f"import runpy\napp = runpy.run_path({str(APP)!r})\napp['build_sidebar']()"
    ).run(timeout=30)


def test_public_sidebar_never_sends_server_secret(monkeypatch):
    monkeypatch.delenv("MACRO_DASHBOARD_MODE", raising=False)
    monkeypatch.setenv("FRED_API_KEY", SENTINEL)
    app = _sidebar()
    assert not app.exception
    assert not app.text_input
    assert not any(x.label in {"Force Refresh", "Apply API Keys"} for x in app.button)
    assert "AI ANALYSIS" not in app.multiselect[0].options
    assert "X INTEL" not in app.multiselect[0].options
    for element in app:
        proto = getattr(element, "proto", None)
        if proto is not None:
            assert SENTINEL.encode() not in proto.SerializeToString()


def test_local_mode_keeps_inputs_without_prefilling_secret(monkeypatch):
    monkeypatch.setenv("MACRO_DASHBOARD_MODE", "local")
    monkeypatch.setenv("FRED_API_KEY", SENTINEL)
    app = _sidebar()
    assert not app.exception
    assert len(app.text_input) == 8
    assert all(input.value == "" for input in app.text_input)
    assert all(SENTINEL.encode() not in item.proto.SerializeToString() for item in app.text_input)
    assert any(x.label == "Force Refresh" for x in app.button)


def test_public_mode_keeps_secrets_server_side_and_blocks_local_tool(monkeypatch):
    monkeypatch.delenv("MACRO_DASHBOARD_MODE", raising=False)
    monkeypatch.setenv("FRED_API_KEY", SENTINEL)
    module = runpy.run_path(str(APP))
    assert module["get_api_key"]("FRED_API_KEY") == SENTINEL
    assert module["_mask_key"](SENTINEL) == "configured"
    with pytest.raises(PermissionError):
        module["_run_codex_macro_analysis_subprocess"]({}, "unused")


def test_public_mode_never_loads_local_futures_files(monkeypatch):
    monkeypatch.delenv("MACRO_DASHBOARD_MODE", raising=False)
    module = runpy.run_path(str(APP))
    load = module["_load_futures_curve"]
    def unexpected_load(_):
        raise AssertionError("public mode read a local futures file")
    monkeypatch.setitem(load.__globals__, "load_futures_spreads", unexpected_load)
    assert load("private.csv").empty


def test_local_mode_still_accepts_futures_files(monkeypatch):
    monkeypatch.setenv("MACRO_DASHBOARD_MODE", "local")
    module = runpy.run_path(str(APP))
    load = module["_load_futures_curve"]
    expected = object()
    monkeypatch.setitem(load.__globals__, "load_futures_spreads", lambda _: expected)
    assert load("local.csv") is expected


def test_public_diagnostics_do_not_expose_provider_error(monkeypatch):
    monkeypatch.delenv("MACRO_DASHBOARD_MODE", raising=False)
    script = f'''
import runpy
import pandas as pd
m = runpy.run_path({str(APP)!r})
fn = m["render_data_diagnostics"]
fn.__globals__["_FRED_ERRORS"] = {{"CPIAUCSL": "request failed: {SENTINEL}"}}
fn.__globals__["validate_data_keys"] = lambda: pd.DataFrame(
    [("FRED", "HTTP ERROR", "-", "configured")],
    columns=["Provider", "Status", "Latency", "Key"])
fn({{}}, {{}}, {{}}, None, None, None, None, [], None)
'''
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    for element in app:
        proto = getattr(element, "proto", None)
        if proto is not None:
            assert SENTINEL.encode() not in proto.SerializeToString()
