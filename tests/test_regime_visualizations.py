"""Smoke coverage for the restored Regime Monitor visualizations."""
import pandas as pd
import plotly.graph_objects as go

from modules.regime_ui import (
    make_regime_history_chart,
    make_regime_quadrant_chart,
    make_spy_regime_chart,
)
from modules.regime_engine import RegimeSignal


def test_restored_regime_charts_return_plotly_figures():
    state = {
        "regime": "Goldilocks",
        "credit_roc": -12.0,
        "inflation_roc": -0.4,
        "history": [
            {"date": "2025-01", "regime": "Reflation"},
            {"date": "2025-02", "regime": "Goldilocks"},
        ],
    }
    index = pd.date_range("2025-01-01", periods=6, freq="B")
    spy = pd.DataFrame({"close": [100, 101, 102, 101, 103, 104]}, index=index)
    signal = RegimeSignal("Test", "D", "Risk-On", 0.6, 0.8, "#34d399", index[-1].date(), pd.DataFrame({"date": index, "risk_score": [0.6] * len(index)}))
    assert isinstance(make_regime_history_chart(state), go.Figure)
    assert isinstance(make_regime_quadrant_chart(state), go.Figure)
    assert isinstance(make_spy_regime_chart(spy, [signal]), go.Figure)
