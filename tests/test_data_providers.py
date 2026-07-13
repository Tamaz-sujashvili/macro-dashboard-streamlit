"""Network-free tests for resilient provider integrations."""
import datetime
import sys
import types

import pandas as pd

from modules import breadth, data_fetch


def test_spy_history_uses_tiingo_when_yfinance_is_empty(monkeypatch):
    class EmptyTicker:
        def __init__(self, _symbol): pass
        def history(self, **_kwargs): return pd.DataFrame()
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=EmptyTicker))
    expected = pd.DataFrame({"open":[1.], "high":[2.], "low":[1.], "close":[2.], "volume":[100]}, index=pd.to_datetime(["2025-01-01"]))
    monkeypatch.setattr(data_fetch, "_tiingo_daily", lambda *_args: expected.copy())
    data_fetch.fetch_spy_vix_history.clear()
    result = data_fetch.fetch_spy_vix_history(period="1y")
    assert result["source"] == "Tiingo"
    assert result["spy"] is not None and not result["spy"].empty


def test_breadth_detector_is_safe_and_classifies():
    grouped = pd.DataFrame({"T":["AAA", "BBB", "CCC"], "o":[10, 10, 10], "c":[11, 9, 12]})
    dma = pd.DataFrame({"ticker":["AAA", "BBB", "CCC"], "dma200":[10, 10, 10]})
    reading = breadth.compute_breadth(grouped, dma)
    signal = breadth.breadth_detector(reading)
    assert reading["advancers"] == 2
    assert signal.state == "Broad"
    assert signal.timeframe == "D"


def test_breadth_no_data_is_nonfatal():
    signal = breadth.breadth_detector(breadth.compute_breadth(pd.DataFrame()))
    assert signal.state == "No Data"
