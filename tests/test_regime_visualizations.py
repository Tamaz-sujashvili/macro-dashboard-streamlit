"""Smoke coverage for Regime Monitor lightweight-chart payload preparation."""
import pandas as pd

from modules.regime_ui import (
    _consensus_history,
    _ohlc_for_timeframe,
)
from modules.regime_engine import RegimeSignal


def test_lightweight_chart_data_supports_ohlc_resampling_and_consensus():
    index = pd.date_range("2025-01-01", periods=30, freq="B", tz="America/New_York")
    spy = pd.DataFrame({"open": range(100, 130), "high": range(101, 131), "low": range(99, 129), "close": range(100, 130)}, index=index)
    signal = RegimeSignal("Test", "D", "Risk-On", 0.6, 0.8, "#34d399", index[-1].date(), pd.DataFrame({"date": index, "risk_score": [0.6] * len(index)}))
    weekly = _ohlc_for_timeframe(spy.tz_localize(None), "1W")
    scores = _consensus_history([signal], spy.index.tz_localize(None))
    assert len(weekly) >= 4
    assert scores.notna().all()
