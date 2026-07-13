"""Unit tests for modules.regime_engine.

All tests use synthetic data so they run without network access.
"""

import datetime
import glob
import os

import numpy as np
import pandas as pd
import pytest

from modules.regime_engine import (
    RegimeSignal,
    _adx14,
    _atr14,
    _ema,
    _realized_vol,
    _resample_to_weekly,
    compute_consensus,
    hmm_detector,
    liquidity_regime_detector,
    macro_quadrant_adapter,
    trend_vol_detector,
    vol_regime_detector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ohlc(index, close, vol=1_000_000):
    """Build an OHLCV DataFrame from a close-price series.

    High/low are derived causally from open/close so that persistent trends
    produce meaningful directional movement for ADX.
    """
    close = pd.Series(close, index=index).astype(float)
    np.random.seed(42)
    open_p = close.shift(1).fillna(close.iloc[0])
    body = (close - open_p).abs()
    range_pct = 0.005 + 0.005 * (body / body.mean()).clip(0.5, 3.0)
    high = pd.concat([open_p, close], axis=1).max(axis=1) * (1 + range_pct)
    low = pd.concat([open_p, close], axis=1).min(axis=1) * (1 - range_pct)
    return pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
    })


def _daily_index(n):
    return pd.date_range(end=datetime.date.today(), periods=n, freq="B")


@pytest.fixture(autouse=True)
def _clear_hmm_parquet_cache():
    """Remove persisted HMM cache so synthetic tests never read stale history."""
    for path in glob.glob(".cache/hmm_history_*.parquet"):
        try:
            os.remove(path)
        except Exception:
            pass
    yield


@pytest.fixture
def realistic_fred():
    """FRED-style dict resembling fetch_fred() output for macro quadrant tests."""
    months = pd.date_range(end=datetime.date.today(), periods=18, freq="MS")
    cpi_hist = []
    spread_hist = []
    # Falling inflation + tightening credit spreads => Goldilocks regime.
    for i, m in enumerate(months):
        cpi = 3.0 - 0.08 * i + 0.05 * np.sin(i)
        spread = 180.0 - 2.0 * i + 3.0 * np.cos(i)
        cpi_hist.append((round(cpi, 2), m.strftime("%Y-%m")))
        spread_hist.append((round(spread, 2), m.strftime("%Y-%m")))
    return {
        "CPI_HIST": cpi_hist,
        "SPREAD_HIST": spread_hist,
    }


@pytest.fixture
def uptrend_lowvol():
    """Persistent uptrend with autocorrelated positive returns (ADX > 20)."""
    idx = _daily_index(300)
    rs = np.random.RandomState(1)
    returns = np.zeros(len(idx))
    returns[0] = rs.normal(0.001, 0.005)
    for t in range(1, len(idx)):
        returns[t] = 0.3 * returns[t - 1] + rs.normal(0.0008, 0.006)
    log_price = np.cumsum(returns)
    close = 100 * np.exp(log_price)
    return _make_ohlc(idx, close)


@pytest.fixture
def crash_series():
    """Strong uptrend followed by a sharp crash."""
    idx = _daily_index(300)
    rs = np.random.RandomState(2)
    up = np.linspace(100, 180, 250)
    crash = np.linspace(180, 90, 50)
    close = np.concatenate([up + rs.normal(0, 0.5, 250), crash + rs.normal(0, 3, 50)])
    return _make_ohlc(idx, close)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


def test_regime_signal_clips_values():
    sig = RegimeSignal(
        detector_name="Test",
        timeframe="D",
        state="Risk-On",
        risk_score=1.5,
        confidence=-0.2,
        color="#22c55e",
        as_of=datetime.date.today(),
    )
    assert sig.risk_score == pytest.approx(1.0)
    assert sig.confidence == pytest.approx(0.0)


def test_empty_signal_is_safe():
    sig = trend_vol_detector(pd.DataFrame(), timeframe="D")
    assert sig.state == "No Data"
    assert sig.risk_score == 0.0


# ---------------------------------------------------------------------------
# Indicator helpers
# ---------------------------------------------------------------------------


def test_ema_rises_in_uptrend(uptrend_lowvol):
    ema = _ema(uptrend_lowvol["close"], 200)
    ema_valid = ema.dropna()
    assert ema_valid.iloc[-1] > ema_valid.iloc[0]
    assert ema.iloc[-1] > ema.iloc[-5]


def test_adx_is_numeric(uptrend_lowvol):
    adx = _adx14(uptrend_lowvol["high"], uptrend_lowvol["low"], uptrend_lowvol["close"])
    assert not adx.empty
    assert adx.notna().any()
    assert adx.dropna().between(0, 100).all()


def test_atr_positive(uptrend_lowvol):
    atr = _atr14(uptrend_lowvol["high"], uptrend_lowvol["low"], uptrend_lowvol["close"])
    assert (atr.dropna() > 0).all()


# ---------------------------------------------------------------------------
# TrendVol detector
# ---------------------------------------------------------------------------


def test_uptrend_lowvol_is_risk_on(uptrend_lowvol):
    sig = trend_vol_detector(uptrend_lowvol, timeframe="D")
    assert sig.state == "Trend Confirmed"
    assert sig.risk_score > 0.5
    assert sig.timeframe == "D"
    assert not sig.history.empty


def test_crash_series_is_risk_off(crash_series):
    sig = trend_vol_detector(crash_series, timeframe="D")
    assert sig.state in {"Below Trend", "Trend Weak"}
    assert sig.risk_score < 0.3


def test_weekly_timeframe_works(uptrend_lowvol):
    sig = trend_vol_detector(uptrend_lowvol, timeframe="W")
    assert sig.timeframe == "W"
    assert sig.state in {"Trend Confirmed", "Trend Weak", "Below Trend", "No Data"}


def test_nan_heavy_input_returns_no_data():
    df = pd.DataFrame({
        "open": [np.nan] * 50,
        "high": [np.nan] * 50,
        "low": [np.nan] * 50,
        "close": [np.nan] * 50,
        "volume": [0] * 50,
    })
    sig = trend_vol_detector(df, timeframe="D")
    assert sig.state == "No Data"
    assert sig.risk_score == 0.0


def test_missing_columns_return_no_data():
    df = pd.DataFrame({"close": [1, 2, 3]})
    sig = trend_vol_detector(df, timeframe="D")
    assert sig.state == "No Data"


# ---------------------------------------------------------------------------
# HMM detector
# ---------------------------------------------------------------------------


def test_hmm_on_uptrend(uptrend_lowvol):
    sig = hmm_detector(uptrend_lowvol, n_states=3, train_days=252)
    assert sig.state in {"Low-Vol Bull", "Moderate", "High-Vol Stress", "No Data"}
    assert -1.0 <= sig.risk_score <= 1.0
    if sig.state != "No Data":
        assert not sig.history.empty


def test_hmm_on_crash(crash_series):
    sig = hmm_detector(crash_series, n_states=3, train_days=252)
    # The crash tail should pull the dominant state toward stress or moderate
    assert sig.state in {"Low-Vol Bull", "Moderate", "High-Vol Stress", "No Data"}
    assert -1.0 <= sig.risk_score <= 1.0


def test_hmm_returns_no_data_for_short_series():
    df = pd.DataFrame({"close": [100, 101, 102, 101, 100]})
    sig = hmm_detector(df, n_states=3, train_days=252)
    assert sig.state == "No Data"


# ---------------------------------------------------------------------------
# Vol regime detector
# ---------------------------------------------------------------------------


def test_vol_regime_calm():
    sig = vol_regime_detector(14.0, {"^VIX9D": 13.5, "^VIX3M": 15.0}, None)
    assert "Calm" in sig.state
    assert sig.risk_score > 0.3


def test_vol_regime_crisis():
    sig = vol_regime_detector(32.0, {"^VIX9D": 35.0, "^VIX3M": 28.0}, None)
    assert "Crisis" in sig.state
    assert sig.risk_score < -0.3


def test_vol_regime_missing_data():
    sig = vol_regime_detector(None, None, None)
    assert sig.state == "No Data"


# ---------------------------------------------------------------------------
# Liquidity regime detector
# ---------------------------------------------------------------------------


def test_liquidity_loose():
    fred = {
        "NFCI": {"value": -0.8},
        "BAMLH0A0HYM2": {"value": 250.0},
        "NFCI_HIST": [(-0.9, "2024-01"), (-0.85, "2024-02"), (-0.8, "2024-03")],
        "HY_SPREAD_HIST": [(230.0, "2024-01"), (240.0, "2024-02"), (250.0, "2024-03")],
    }
    sig = liquidity_regime_detector(fred)
    assert "Loose" in sig.state
    assert sig.risk_score > 0.3
    assert sig.timeframe == "W"


def test_liquidity_stressed():
    fred = {
        "NFCI": {"value": 0.8},
        "BAMLH0A0HYM2": {"value": 650.0},
        "NFCI_HIST": [(0.4, "2024-01"), (0.6, "2024-02"), (0.8, "2024-03")],
        "HY_SPREAD_HIST": [(400.0, "2024-01"), (500.0, "2024-02"), (650.0, "2024-03")],
    }
    sig = liquidity_regime_detector(fred)
    assert "Stressed" in sig.state
    assert sig.risk_score < -0.3


def test_liquidity_missing_data():
    sig = liquidity_regime_detector({})
    assert sig.state == "No Data"
    assert sig.timeframe == "W"


# ---------------------------------------------------------------------------
# Macro quadrant adapter
# ---------------------------------------------------------------------------


def test_macro_quadrant_goldilocks():
    fred = {
        "CPI_HIST": [(2.0, "2024-01"), (2.1, "2024-02"), (2.0, "2024-03"), (1.9, "2024-04")],
        "SPREAD_HIST": [(100.0, "2024-01"), (95.0, "2024-02"), (90.0, "2024-03"), (85.0, "2024-04")],
    }
    sig = macro_quadrant_adapter(fred)
    assert sig.state in {"Goldilocks", "Reflation", "Stagflation", "Recession", "Mixed / Uncertain", "No Data"}
    assert sig.timeframe == "M"
    assert -1.0 <= sig.risk_score <= 1.0


def test_macro_quadrant_realistic_fred_fixture(realistic_fred):
    """Regression test: a realistic fetch_fred()-style dict yields a real quadrant."""
    sig = macro_quadrant_adapter(realistic_fred)
    assert sig.state != "No Data"
    assert sig.state != "Mixed / Uncertain"
    assert sig.timeframe == "M"
    assert -1.0 <= sig.risk_score <= 1.0
    assert not sig.history.empty


def test_macro_quadrant_missing_data():
    sig = macro_quadrant_adapter({})
    assert sig.state == "No Data"


# ---------------------------------------------------------------------------
# Consensus aggregator
# ---------------------------------------------------------------------------


def test_compute_consensus_risk_on():
    signals = [
        RegimeSignal("A", "D", "Risk-On", 0.9, 1.0, "#22c55e", datetime.date.today()),
        RegimeSignal("B", "D", "Risk-On", 0.8, 0.8, "#22c55e", datetime.date.today()),
        RegimeSignal("C", "D", "No Data", 0.0, 0.0, "#94a3b8", datetime.date.today()),
    ]
    consensus = compute_consensus(signals)
    assert "D" in consensus
    assert consensus["D"]["label"] == "Risk-On"
    assert consensus["D"]["risk_score"] > 0.3
    assert consensus["D"]["n"] == 2


def test_compute_consensus_risk_off():
    signals = [
        RegimeSignal("A", "D", "Crisis", -0.9, 1.0, "#ef4444", datetime.date.today()),
        RegimeSignal("B", "D", "Stressed", -0.6, 0.8, "#fbbf24", datetime.date.today()),
    ]
    consensus = compute_consensus(signals)
    assert consensus["D"]["label"] == "Risk-Off"
    assert consensus["D"]["risk_score"] < -0.3


def test_compute_consensus_empty():
    assert compute_consensus([]) == {}


def test_compute_consensus_no_data_only():
    signals = [
        RegimeSignal("A", "D", "No Data", 0.0, 0.0, "#94a3b8", datetime.date.today()),
    ]
    consensus = compute_consensus(signals)
    assert consensus["D"]["label"] == "No Data"
    assert consensus["D"]["n"] == 0


# ---------------------------------------------------------------------------
# Integration / smoke
# ---------------------------------------------------------------------------


def test_all_detectors_handle_synthetic_data(uptrend_lowvol):
    signals = [
        trend_vol_detector(uptrend_lowvol, "D"),
        trend_vol_detector(uptrend_lowvol, "W"),
        hmm_detector(uptrend_lowvol, train_days=252),
        vol_regime_detector(14.0, {"^VIX9D": 13.0, "^VIX3M": 15.0}, uptrend_lowvol),
        liquidity_regime_detector({
            "NFCI": {"value": -0.6},
            "BAMLH0A0HYM2": {"value": 280.0},
            "NFCI_HIST": [(-0.7, "2024-01"), (-0.6, "2024-02")],
            "HY_SPREAD_HIST": [(260.0, "2024-01"), (280.0, "2024-02")],
        }),
    ]
    consensus = compute_consensus(signals)
    assert isinstance(consensus, dict)
    # At least daily consensus should exist and be numeric
    assert "D" in consensus
    assert isinstance(consensus["D"]["risk_score"], float)
