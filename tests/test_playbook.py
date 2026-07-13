"""Synthetic tests for look-ahead-safe playbook statistics."""

import numpy as np
import pandas as pd

from modules.playbook import conditional_stats


def _prices_from_returns(index, returns):
    values = [100.0]
    for value in returns[1:]:
        values.append(values[-1] * (1.0 + value))
    return pd.DataFrame({"SPY": values, "TLT": values}, index=index)


def test_risk_off_followed_by_negative_equity_returns_is_reflected():
    index = pd.date_range("2025-01-01", periods=120, freq="B")
    regimes = pd.Series(["Risk-On"] * 60 + ["Risk-Off"] * 60, index=index)
    returns = np.array([np.nan] + [0.01 if regimes.iloc[pos - 1] == "Risk-On" else -0.01 for pos in range(1, len(index))])
    prices = _prices_from_returns(index, returns)

    stats = conditional_stats(regimes, prices)
    risk_off = stats[(stats["regime_label"] == "Risk-Off") & (stats["asset"] == "SPY")].iloc[0]

    assert risk_off.ann_return < 0
    assert risk_off.hit_rate == 0.0
    assert risk_off.n_days >= 59
    assert bool(risk_off.low_sample)


def test_regime_is_shifted_before_joining_returns():
    index = pd.date_range("2025-02-03", periods=5, freq="B")
    regimes = pd.Series(["Risk-Off", "Risk-On", "Risk-Off", "Risk-On", "Risk-On"], index=index)
    returns = np.array([np.nan, 0.10, -0.10, 0.10, -0.10])
    prices = _prices_from_returns(index, returns)

    stats = conditional_stats(regimes, prices)
    shifted_risk_off = stats[(stats["regime_label"] == "Risk-Off") & (stats["asset"] == "SPY")].iloc[0]

    # With the required one-row shift, Risk-Off conditions the +10% returns
    # at the second and fourth closes. Same-day conditioning would be negative.
    assert shifted_risk_off.ann_return > 0


def test_small_samples_are_flagged():
    index = pd.date_range("2025-03-03", periods=30, freq="B")
    regimes = pd.Series(["Neutral"] * len(index), index=index)
    prices = _prices_from_returns(index, np.array([np.nan] + [0.002] * (len(index) - 1)))

    stats = conditional_stats(regimes, prices)
    assert not stats.empty
    assert stats["n_days"].max() < 60
    assert stats["low_sample"].all()


def test_missing_price_data_returns_empty_stats():
    index = pd.date_range("2025-04-01", periods=10, freq="B")
    regimes = pd.Series(["Risk-Off"] * len(index), index=index)
    prices = pd.DataFrame({"SPY": [np.nan] * len(index)}, index=index)

    stats = conditional_stats(regimes, prices)
    assert stats.empty
    assert list(stats.columns) == [
        "regime_label",
        "asset",
        "ann_return",
        "ann_vol",
        "sharpe",
        "hit_rate",
        "max_drawdown",
        "n_days",
        "low_sample",
    ]
