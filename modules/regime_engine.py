"""Pure-computation regime-detection engine for the macro dashboard.

It re-uses the economic regime-classification logic from ``compute_regime_state``
/ ``_classify_regime`` in the main dashboard file, and adds new trend/vol, HMM,
vol-regime and liquidity detectors that each emit a ``RegimeSignal``.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

# Optional heavy dependencies are imported lazily inside functions so the module
# can still be imported for lightweight tests even if they are absent.


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RegimeSignal:
    """A single detector reading.

    Attributes:
        detector_name: Human-readable detector id.
        timeframe: "D", "W" or "M".
        state: Detector-specific label (e.g. "Trend Confirmed").
        risk_score: Normalised score in [-1, +1]; -1 = maximum risk-off.
        confidence: Confidence weight in [0, 1].
        color: Hex colour for UI rendering.
        as_of: Date the signal refers to.
        history: Time-series of intermediate state/risk_score values.
    """

    detector_name: str
    timeframe: str
    state: str
    risk_score: float
    confidence: float
    color: str
    as_of: datetime.date
    history: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __post_init__(self) -> None:
        self.risk_score = float(np.clip(self.risk_score, -1.0, 1.0))
        self.confidence = float(np.clip(self.confidence, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Helper indicators (Wilder / EMA, no pandas_ta dependency)
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=max(int(span), 1), adjust=False).mean()


def _wilder_smooth(series: pd.Series, length: int) -> pd.Series:
    """Wilder smoothing: equivalent to EWM with alpha = 1 / length."""
    return series.ewm(alpha=1.0 / max(int(length), 1), adjust=False, min_periods=length).mean()


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _atr14(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    return _wilder_smooth(_true_range(high, low, close), 14)


def _adx14(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Average Directional Index (ADX) with Wilder length 14.

    The implementation mirrors ``ta.adx(length=14)`` using only causal
    operations.
    """
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(0.0, index=high.index)
    minus_dm = pd.Series(0.0, index=high.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move

    tr = _true_range(high, low, close)
    tr_smooth = _wilder_smooth(tr, 14)
    plus_di = 100.0 * _wilder_smooth(plus_dm, 14) / tr_smooth
    minus_di = 100.0 * _wilder_smooth(minus_dm, 14) / tr_smooth

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _wilder_smooth(dx, 14)
    return adx


def _realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    """Rolling standard deviation of daily log returns (unannualised)."""
    returns = np.log(close / close.shift(1))
    return returns.rolling(window=max(int(window), 2), min_periods=2).std()


def _resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to Friday-weekly bars."""
    required = ["open", "high", "low", "close", "volume"]
    if not set(required).issubset(df.columns):
        return pd.DataFrame(columns=required)
    ohlcv = df[required].copy()
    ohlcv.index = pd.to_datetime(ohlcv.index)
    weekly = ohlcv.resample("W-FRI").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return weekly.dropna(how="all")


def _as_of_date(index: pd.Index) -> datetime.date:
    """Best-effort as-of date from a time index."""
    if len(index) == 0:
        return datetime.date.today()
    last = index[-1]
    if isinstance(last, pd.Timestamp):
        return last.date()
    if isinstance(last, datetime.datetime):
        return last.date()
    if isinstance(last, datetime.date):
        return last
    return datetime.date.today()


def _history_df(index: pd.Index, states: pd.Series, scores: pd.Series) -> pd.DataFrame:
    """Build a compact history DataFrame."""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(index).date,
            "state": states.values,
            "risk_score": scores.values,
        },
        index=index,
    )
    return df.dropna(subset=["state", "risk_score"])


# ---------------------------------------------------------------------------
# Trend/Vol detector (Pine TE v9.4 ADX gate + v9.1 vol gate)
# ---------------------------------------------------------------------------

def _price_vs_ema_gate(close: pd.Series, ema_len: int = 200) -> pd.Series:
    ema = _ema(close, ema_len)
    return close > ema


def _trendvol_state(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """Return a daily state series using the consolidated TrendVol rules."""
    ema200 = _ema(close, 200)
    ema_rising = ema200 > ema200.shift(5)
    adx = _adx14(high, low, close)
    rv = _realized_vol(close, 20)

    # Current RV percentile relative to its own trailing one-year history.
    # Low percentile = low realised vol, which is supportive for risk-on.
    rv_rank = rv.rolling(252, min_periods=60).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    )
    # Avoid excessive volatility (top tercile) confirming trend.
    vol_suppressed = rv_rank > 0.67

    above_gate = close > ema200
    adx_pass = adx >= 20.0

    state = pd.Series("Below Trend", index=close.index)
    weak = above_gate & (~adx_pass | vol_suppressed | ~ema_rising)
    confirmed = above_gate & adx_pass & ema_rising & ~vol_suppressed
    state[weak] = "Trend Weak"
    state[confirmed] = "Trend Confirmed"
    return state


def _state_to_risk_score(state: str) -> float:
    return {
        "Trend Confirmed": 0.8,
        "Trend Weak": 0.2,
        "Below Trend": -0.6,
    }.get(state, 0.0)


def _state_to_color(state: str) -> str:
    return {
        "Trend Confirmed": "#22c55e",
        "Trend Weak": "#fbbf24",
        "Below Trend": "#ef4444",
    }.get(state, "#94a3b8")


def trend_vol_detector(
    prices_df: pd.DataFrame,
    timeframe: str = "D",
) -> RegimeSignal:
    """Trend/vol regime detector ported from Pine TE v9.

    Parameters:
        prices_df: DataFrame with columns ``open``, ``high``, ``low``,
            ``close``, ``volume``.
        timeframe: ``"D"`` or ``"W"``.  Weekly bars are built by resampling
            the daily input.
    """
    required = {"open", "high", "low", "close", "volume"}
    if not isinstance(prices_df, pd.DataFrame) or not required.issubset(prices_df.columns):
        return _no_data_signal("TrendVol", timeframe)

    df = prices_df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.dropna(subset=["open", "high", "low", "close"])

    if timeframe == "W":
        df = _resample_to_weekly(df)
    elif timeframe != "D":
        return _no_data_signal("TrendVol", timeframe)

    if len(df) < 250 or df["close"].isna().mean() > 0.1:
        return _no_data_signal("TrendVol", timeframe)

    try:
        states = _trendvol_state(df["close"], df["high"], df["low"], df["volume"])
        scores = states.map(_state_to_risk_score)
        current_state = states.iloc[-1]
        current_score = float(scores.iloc[-1])
        confidence = 1.0 - min(0.3, df["close"].isna().mean())
        history = _history_df(df.index, states, scores)
        return RegimeSignal(
            detector_name="TrendVol",
            timeframe=timeframe,
            state=str(current_state),
            risk_score=current_score,
            confidence=confidence,
            color=_state_to_color(str(current_state)),
            as_of=_as_of_date(df.index),
            history=history,
        )
    except Exception:
        return _no_data_signal("TrendVol", timeframe)


# ---------------------------------------------------------------------------
# HMM regime detector
# ---------------------------------------------------------------------------

_HMM_CACHE: Dict[str, Dict[str, Any]] = {}
_HMM_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


def _hmm_cache_key(n_states: int, train_days: int, refit_days: int, seed: int) -> str:
    return f"hmm:{n_states}:{train_days}:{refit_days}:{seed}"


def _hmm_parquet_path(n_states: int, train_days: int, refit_days: int, seed: int) -> str:
    os.makedirs(_HMM_CACHE_DIR, exist_ok=True)
    return os.path.join(
        _HMM_CACHE_DIR,
        f"hmm_history_n{n_states}_t{train_days}_r{refit_days}_s{seed}.parquet",
    )


def _load_hmm_history(path: str) -> Optional[pd.DataFrame]:
    """Load cached HMM inference history from parquet."""
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
        if not {"state_idx", "prob", "score"}.issubset(df.columns):
            return None
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return None


def _save_hmm_history(
    path: str,
    state_idx: pd.Series,
    prob: pd.Series,
    score: pd.Series,
) -> None:
    """Persist HMM inference history to parquet."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame({
        "state_idx": state_idx,
        "prob": prob,
        "score": score,
    })
    df.index = pd.to_datetime(df.index)
    df.to_parquet(path)


def _sort_hmm_states_by_risk(model) -> np.ndarray:
    """Return a permutation so states are ordered risk-on -> moderate -> stress.

    Sort key is mean return / (volatility + eps); high Sharpe-like ratio is
    interpreted as the low-vol bull / risk-on state.
    """
    means = model.means_.flatten()
    covars = np.sqrt(model.covars_.flatten())
    score = means / (covars + 1e-6)
    return np.argsort(-score)  # descending


def hmm_detector(
    prices_df: pd.DataFrame,
    n_states: int = 3,
    train_days: int = 1260,
    refit_days: int = 5,
    seed: int = 42,
) -> RegimeSignal:
    """Forward-filtered Gaussian HMM regime detector with parquet persistence.

    The model is fit on a trailing ``train_days`` window ending strictly before
    each inference day.  Inference uses ``predict_proba`` on the trailing
    ``min(250, i)`` observations ending at day ``i``; only the last row is
    retained, so no future data is ever used (no repaint).

    The full walk-forward history is cached to ``.cache/hmm_history_*.parquet``
    so subsequent runs only extend from the last cached date.
    """
    if not isinstance(prices_df, pd.DataFrame) or "close" not in prices_df.columns:
        return _no_data_signal("HMM", "D")

    close = pd.to_numeric(prices_df["close"], errors="coerce").dropna()
    if len(close) < train_days + n_states + 10:
        return _no_data_signal("HMM", "D")

    try:
        from hmmlearn.hmm import GaussianHMM
    except Exception:
        return _no_data_signal("HMM", "D")

    returns = np.log(close / close.shift(1)).dropna().to_frame("ret")
    if len(returns) < train_days + 10:
        return _no_data_signal("HMM", "D")

    cache_key = _hmm_cache_key(n_states, train_days, refit_days, seed)
    cache = _HMM_CACHE.get(cache_key, {})

    model: Optional[Any] = cache.get("model")
    last_fit_idx: int = cache.get("last_fit_idx", -1)
    permutation: Optional[np.ndarray] = cache.get("permutation")

    # Initialize output series.
    state_idx_series = pd.Series(index=returns.index, dtype=float)
    prob_series = pd.Series(index=returns.index, dtype=float)
    score_series = pd.Series(index=returns.index, dtype=float)

    # Load prior inference history and extend it rather than recomputing.
    parquet_path = _hmm_parquet_path(n_states, train_days, refit_days, seed)
    cached_history = _load_hmm_history(parquet_path)
    if cached_history is not None:
        aligned = cached_history.reindex(returns.index)
        state_idx_series = aligned["state_idx"].copy()
        prob_series = aligned["prob"].copy()
        score_series = aligned["score"].copy()
        last_valid = state_idx_series.last_valid_index()
        if last_valid is not None:
            start_idx = int(returns.index.get_loc(last_valid)) + 1
        else:
            start_idx = train_days
    else:
        start_idx = train_days

    start_idx = max(start_idx, train_days)

    for i in range(start_idx, len(returns)):
        if model is None or (i - last_fit_idx) >= refit_days:
            train_slice = returns.iloc[i - train_days : i].values
            model = GaussianHMM(
                n_components=n_states,
                covariance_type="diag",
                n_iter=50,
                random_state=seed,
                init_params="stmc",
            )
            model.fit(train_slice)
            permutation = _sort_hmm_states_by_risk(model)
            last_fit_idx = i

        assert permutation is not None

        # Forward-filtered inference: predict on the trailing window ending at i,
        # then keep only the probability assigned to the current observation.
        window_len = min(250, i)
        x = returns.iloc[i - window_len : i + 1].values
        probs_unordered = model.predict_proba(x)
        probs = probs_unordered[-1][permutation]
        state_t = int(np.argmax(probs))
        prob_t = float(probs[state_t])

        state_idx_series.iloc[i] = float(state_t)
        prob_series.iloc[i] = prob_t
        score_series.iloc[i] = _hmm_state_score(state_t, prob_t)

    _save_hmm_history(parquet_path, state_idx_series, prob_series, score_series)

    _HMM_CACHE[cache_key] = {
        "model": model,
        "last_fit_idx": last_fit_idx,
        "permutation": permutation,
    }

    valid = state_idx_series.dropna()
    if valid.empty:
        return _no_data_signal("HMM", "D")

    current_state = int(valid.iloc[-1])
    current_prob = float(prob_series.dropna().iloc[-1])
    state_label = _hmm_state_label(current_state)
    current_score = _hmm_state_score(current_state, current_prob)

    states_named = state_idx_series.map(
        lambda x: _hmm_state_label(int(x)) if pd.notna(x) else "No Data"
    )
    history = _history_df(returns.index, states_named, score_series.fillna(0.0))

    return RegimeSignal(
        detector_name="HMM",
        timeframe="D",
        state=state_label,
        risk_score=current_score,
        confidence=current_prob,
        color=_hmm_state_color(state_label),
        as_of=_as_of_date(returns.index),
        history=history,
    )


def _hmm_state_label(state: int) -> str:
    return {
        0: "Low-Vol Bull",
        1: "Moderate",
        2: "High-Vol Stress",
    }.get(state, "Moderate")


def _hmm_state_color(label: str) -> str:
    return {
        "Low-Vol Bull": "#22c55e",
        "Moderate": "#fbbf24",
        "High-Vol Stress": "#ef4444",
    }.get(label, "#94a3b8")


def _hmm_state_score(state: int, prob: float) -> float:
    base = {0: 0.7, 1: 0.0, 2: -0.7}.get(state, 0.0)
    # Confidence scales the magnitude toward the base score.
    return base * (0.5 + 0.5 * prob)


# ---------------------------------------------------------------------------
# Volatility regime detector (VIX level + term structure + HV20)
# ---------------------------------------------------------------------------

def _hv20_percentile(spy_prices: Optional[pd.DataFrame]) -> Optional[float]:
    if spy_prices is None or "close" not in spy_prices.columns:
        return None
    close = pd.to_numeric(spy_prices["close"], errors="coerce").dropna()
    if len(close) < 60:
        return None
    hv = _realized_vol(close, 20)
    hist = hv.dropna()
    if len(hist) < 60:
        return None
    return float((hist <= hist.iloc[-1]).mean())


def _term_structure_slope(
    vix_value: Optional[float],
    term_structure: Optional[Mapping[str, Optional[float]]],
) -> Optional[float]:
    if term_structure is None:
        return None
    front = term_structure.get("^VIX9D") or term_structure.get("^VIX")
    back = term_structure.get("^VIX3M") or term_structure.get("^VIX6M")
    if front is not None and back is not None:
        return float(back) - float(front)
    if vix_value is not None and back is not None:
        return float(back) - float(vix_value)
    return None


def vol_regime_detector(
    vix_value: Optional[float],
    vix_term_structure: Optional[Mapping[str, Optional[float]]],
    spy_prices: Optional[pd.DataFrame],
) -> RegimeSignal:
    """VIX-driven volatility regime: Calm / Stressed / Crisis."""
    has_any = (
        vix_value is not None
        or (vix_term_structure and any(v is not None for v in vix_term_structure.values()))
        or (spy_prices is not None and not spy_prices.empty)
    )
    if not has_any:
        return _no_data_signal("VolRegime", "D")

    try:
        vix = _safe_float(vix_value)
        slope = _term_structure_slope(vix, vix_term_structure)
        hv_pct = _hv20_percentile(spy_prices)

        inputs = sum(x is not None for x in (vix, slope, hv_pct))
        confidence = max(0.3, inputs / 3.0)

        state, score = _classify_vol_state(vix, slope, hv_pct)
        return RegimeSignal(
            detector_name="VolRegime",
            timeframe="D",
            state=state,
            risk_score=score,
            confidence=confidence,
            color=_vol_state_color(state),
            as_of=datetime.date.today(),
        )
    except Exception:
        return _no_data_signal("VolRegime", "D")


def _classify_vol_state(
    vix: Optional[float],
    slope: Optional[float],
    hv_pct: Optional[float],
) -> tuple[str, float]:
    # Crisis: VIX very high, backwardation, or realised vol in top decile.
    crisis_vix = vix is not None and vix >= 30.0
    crisis_slope = slope is not None and slope < -2.0
    crisis_hv = hv_pct is not None and hv_pct >= 0.90
    if crisis_vix or (crisis_slope and (vix is None or vix >= 20.0)) or crisis_hv:
        return "Crisis", -0.8

    # Calm: VIX low, contango, realised vol not elevated.
    calm_vix = vix is not None and vix < 18.0
    calm_slope = slope is not None and slope > 1.0
    calm_hv = hv_pct is not None and hv_pct <= 0.50
    if calm_vix and (calm_slope or calm_hv or slope is None):
        return "Calm", 0.7

    # Stressed: everything in between.
    return "Stressed", 0.0


def _vol_state_color(state: str) -> str:
    return {
        "Calm": "#22c55e",
        "Stressed": "#fbbf24",
        "Crisis": "#ef4444",
    }.get(state, "#94a3b8")


# ---------------------------------------------------------------------------
# Liquidity regime detector (NFCI + HY OAS)
# ---------------------------------------------------------------------------

def _fred_current(fred: Mapping[str, Any], key: str) -> Optional[float]:
    val = fred.get(key)
    if isinstance(val, dict):
        return _safe_float(val.get("value"))
    return _safe_float(val)


def _fred_roc(fred: Mapping[str, Any], hist_key: str, periods_back: int = 3) -> Optional[float]:
    hist = fred.get(hist_key, [])
    if not isinstance(hist, (list, tuple)) or len(hist) < periods_back + 1:
        return None
    try:
        latest = _safe_float(hist[-1][0])
        earlier = _safe_float(hist[-(periods_back + 1)][0])
        if latest is None or earlier is None or earlier == 0:
            return None
        return (latest - earlier) / abs(earlier) * 100.0
    except Exception:
        return None


def liquidity_regime_detector(fred: Mapping[str, Any]) -> RegimeSignal:
    """Liquidity regime from NFCI and high-yield OAS level + ROC."""
    if not fred:
        return _no_data_signal("Liquidity", "W")

    try:
        nfci = _fred_current(fred, "NFCI")
        hy = _fred_current(fred, "BAMLH0A0HYM2")
        nfci_roc = _fred_roc(fred, "NFCI_HIST", periods_back=3)
        hy_roc = _fred_roc(fred, "HY_SPREAD_HIST", periods_back=3)

        if nfci is None and hy is None:
            return _no_data_signal("Liquidity", "W")

        state, score = _classify_liquidity_state(nfci, hy, nfci_roc, hy_roc)
        inputs = sum(x is not None for x in (nfci, hy, nfci_roc, hy_roc))
        confidence = max(0.3, inputs / 4.0)

        return RegimeSignal(
            detector_name="Liquidity",
            timeframe="W",
            state=state,
            risk_score=score,
            confidence=confidence,
            color=_liquidity_color(state),
            as_of=datetime.date.today(),
        )
    except Exception:
        return _no_data_signal("Liquidity", "W")


def _classify_liquidity_state(
    nfci: Optional[float],
    hy: Optional[float],
    nfci_roc: Optional[float],
    hy_roc: Optional[float],
) -> tuple[str, float]:
    # Stressed: restrictive financial conditions or elevated HY spreads.
    stressed_nfci = nfci is not None and nfci >= 0.5
    stressed_hy = hy is not None and hy >= 500.0
    stressed_roc = (nfci_roc is not None and nfci_roc >= 20.0) or (hy_roc is not None and hy_roc >= 20.0)
    if stressed_nfci or stressed_hy or stressed_roc:
        return "Stressed", -0.7

    # Loose: accommodative conditions and spreads low/falling.
    loose_nfci = nfci is not None and nfci <= -0.3
    loose_hy = hy is not None and hy <= 350.0
    loose_roc = (nfci_roc is None or nfci_roc <= 5.0) and (hy_roc is None or hy_roc <= 10.0)
    if (loose_nfci or loose_hy) and loose_roc:
        return "Loose", 0.6

    return "Tightening", 0.0


def _liquidity_color(state: str) -> str:
    return {
        "Loose": "#22c55e",
        "Tightening": "#fbbf24",
        "Stressed": "#ef4444",
    }.get(state, "#94a3b8")


# ---------------------------------------------------------------------------
# Macro quadrant adapter (re-uses the main dashboard economic regime logic)
# ---------------------------------------------------------------------------

def _classify_regime(credit_roc: Optional[float], inflation_roc: Optional[float]) -> tuple[str, str]:
    """Copied from the main dashboard so this module stays pure."""
    spreads_falling = (credit_roc or 0) < 0
    inflation_rising = (inflation_roc or 0) >= 0
    if spreads_falling and inflation_rising:
        regime = "Reflation"
    elif not spreads_falling and inflation_rising:
        regime = "Stagflation"
    elif spreads_falling and not inflation_rising:
        regime = "Goldilocks"
    else:
        regime = "Recession"
    return regime, _REGIME_COLORS[regime]


_REGIME_COLORS = {
    "Reflation": "#fbbf24",
    "Stagflation": "#f87171",
    "Goldilocks": "#34d399",
    "Recession": "#94a3b8",
}


def _compute_regime_state(fred: Mapping[str, Any], lookback_days: int = 60) -> Dict[str, Any]:
    """Re-implementation of ``compute_regime_state`` from the main dashboard.

    Uses only ``CPI_HIST`` and ``SPREAD_HIST`` from the FRED-style dict.
    """
    cpi_hist = fred.get("CPI_HIST", [])
    spread_hist = fred.get("SPREAD_HIST", [])
    if not cpi_hist or not spread_hist:
        return {
            "regime": "Mixed / Uncertain",
            "color": "#fbbf24",
            "credit_roc": None,
            "inflation_roc": None,
            "days_in_regime": 0,
            "history": [],
        }

    cpi_df = pd.DataFrame(cpi_hist, columns=["inflation", "date"])
    spread_df = pd.DataFrame(spread_hist, columns=["credit", "date"])
    cpi_df["date"] = pd.to_datetime(cpi_df["date"], format="%Y-%m", errors="coerce")
    spread_df["date"] = pd.to_datetime(spread_df["date"], format="%Y-%m", errors="coerce")
    cpi_df["inflation"] = pd.to_numeric(cpi_df["inflation"], errors="coerce")
    spread_df["credit"] = pd.to_numeric(spread_df["credit"], errors="coerce")

    df = (
        spread_df.merge(cpi_df, on="date", how="inner")
        .dropna(subset=["date", "credit", "inflation"])
        .sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )
    if len(df) < 3:
        return {
            "regime": "Mixed / Uncertain",
            "color": "#fbbf24",
            "credit_roc": None,
            "inflation_roc": None,
            "days_in_regime": 0,
            "history": [],
        }

    df["target_date"] = df["date"] - pd.Timedelta(days=int(lookback_days))
    lag_source = df[["date", "credit", "inflation"]].rename(
        columns={"date": "lag_date", "credit": "credit_lag", "inflation": "inflation_lag"}
    )
    df = pd.merge_asof(
        df.sort_values("target_date"),
        lag_source.sort_values("lag_date"),
        left_on="target_date",
        right_on="lag_date",
        direction="backward",
    ).sort_values("date").reset_index(drop=True)

    df["credit_roc"] = df["credit"] - df["credit_lag"]
    df["inflation_roc"] = (df["inflation"] - df["inflation_lag"]) * 100.0
    df = df.dropna(subset=["credit_roc", "inflation_roc"]).reset_index(drop=True)
    if df.empty:
        return {
            "regime": "Mixed / Uncertain",
            "color": "#fbbf24",
            "credit_roc": None,
            "inflation_roc": None,
            "days_in_regime": 0,
            "history": [],
        }

    history = []
    for _, row in df.iterrows():
        regime, color = _classify_regime(row["credit_roc"], row["inflation_roc"])
        history.append(
            {
                "date": row["date"].strftime("%Y-%m"),
                "regime": regime,
                "color": color,
                "credit_roc": float(row["credit_roc"]),
                "inflation_roc": float(row["inflation_roc"]),
            }
        )

    current = history[-1]
    start_date = pd.to_datetime(current["date"], format="%Y-%m")
    for item in reversed(history[:-1]):
        if item["regime"] != current["regime"]:
            break
        start_date = pd.to_datetime(item["date"], format="%Y-%m")
    end_date = pd.to_datetime(current["date"], format="%Y-%m")
    days_in_regime = max(1, int((end_date - start_date).days))

    return {
        "regime": current["regime"],
        "color": current["color"],
        "credit_roc": float(current["credit_roc"]),
        "inflation_roc": float(current["inflation_roc"]),
        "days_in_regime": days_in_regime,
        "history": history[-90:],
    }


def _macro_regime_score(regime: str) -> float:
    return {
        "Goldilocks": 0.8,
        "Reflation": 0.4,
        "Stagflation": -0.5,
        "Recession": -0.8,
        "Mixed / Uncertain": 0.0,
    }.get(regime, 0.0)


def macro_quadrant_adapter(fred: Mapping[str, Any]) -> RegimeSignal:
    """Thin wrapper converting the economic regime state into a RegimeSignal."""
    try:
        state = _compute_regime_state(fred)
    except Exception:
        return _no_data_signal("MacroQuadrant", "M")

    regime = state.get("regime", "Mixed / Uncertain")
    if regime in (None, "Mixed / Uncertain") and not state.get("history"):
        return _no_data_signal("MacroQuadrant", "M")

    score = _macro_regime_score(regime)
    confidence = 0.85 if regime != "Mixed / Uncertain" else 0.4

    history_rows = []
    for item in state.get("history", []):
        history_rows.append(
            {
                "date": pd.to_datetime(item["date"]).date(),
                "state": item["regime"],
                "risk_score": _macro_regime_score(item["regime"]),
                "credit_roc": item.get("credit_roc"),
                "inflation_roc": item.get("inflation_roc"),
            }
        )
    history = pd.DataFrame(history_rows)

    return RegimeSignal(
        detector_name="MacroQuadrant",
        timeframe="M",
        state=regime,
        risk_score=score,
        confidence=confidence,
        color=state.get("color", "#94a3b8"),
        as_of=datetime.date.today(),
        history=history,
    )


# ---------------------------------------------------------------------------
# Consensus aggregator
# ---------------------------------------------------------------------------

def compute_consensus(signals: Sequence[RegimeSignal]) -> Dict[str, Dict[str, Any]]:
    """Aggregate detector signals into a per-timeframe consensus."""
    if not signals:
        return {}

    groups: Dict[str, List[RegimeSignal]] = {}
    for sig in signals:
        groups.setdefault(sig.timeframe, []).append(sig)

    result: Dict[str, Dict[str, Any]] = {}
    for tf, sigs in groups.items():
        valid = [s for s in sigs if s.state != "No Data"]
        n = len(valid)
        if n == 0:
            result[tf] = {
                "risk_score": 0.0,
                "agreement": 0.0,
                "label": "No Data",
                "n": 0,
            }
            continue

        weights = [max(s.confidence, 0.01) for s in valid]
        total_w = sum(weights)
        weighted_score = sum(s.risk_score * w for s, w in zip(valid, weights)) / total_w

        # Agreement = share of valid signals whose sign matches the consensus sign.
        consensus_sign = np.sign(weighted_score)
        if consensus_sign == 0:
            agree = sum(1 for s in valid if abs(s.risk_score) < 0.15)
        else:
            agree = sum(1 for s in valid if np.sign(s.risk_score) == consensus_sign)
        agreement = agree / n

        if weighted_score > 0.3:
            label = "Risk-On"
        elif weighted_score < -0.3:
            label = "Risk-Off"
        else:
            label = "Neutral"

        result[tf] = {
            "risk_score": round(float(weighted_score), 4),
            "agreement": round(float(agreement), 4),
            "label": label,
            "n": n,
        }
    return result


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _no_data_signal(detector_name: str, timeframe: str) -> RegimeSignal:
    return RegimeSignal(
        detector_name=detector_name,
        timeframe=timeframe,
        state="No Data",
        risk_score=0.0,
        confidence=0.0,
        color="#94a3b8",
        as_of=datetime.date.today(),
    )

