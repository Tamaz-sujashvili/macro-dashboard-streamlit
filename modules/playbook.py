"""Historical regime-conditional asset statistics.

The public functions in this module are Streamlit-free.  Network access is
kept deliberately small and defensive so callers can use the same yfinance
first, Tiingo fallback behavior as the dashboard data layer without making
the computation module depend on Streamlit.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlencode

import numpy as np
import pandas as pd


DEFAULT_TICKERS = (
    "SPY",
    "QQQ",
    "IWM",
    "TLT",
    "IEF",
    "LQD",
    "HYG",
    "GLD",
    "DBC",
    "UUP",
    "XLU",
    "XLK",
    "XLE",
    "BIL",
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK_PRICES_PATH = _PROJECT_ROOT / ".cache" / "playbook_prices.parquet"
_CURL_AVAILABLE = shutil.which("curl") is not None


# Textbook prior, not fitted data.  These descriptions are intentionally
# separate from the empirical tables and should never be presented as model
# output.
CANONICAL_PLAYBOOK = {
    "Goldilocks": (
        "Textbook prior: Favor equities and credit as growth remains steady while inflation cools. "
        "Cyclical participation and balanced duration are usually rewarded in this mix."
    ),
    "Reflation": (
        "Textbook prior: Favor cyclicals, value and commodities as nominal growth and inflation reaccelerate. "
        "Real assets and economically sensitive exposures generally have the strongest relative tailwind."
    ),
    "Stagflation": (
        "Textbook prior: Favor commodities and energy, with short duration and inflation-sensitive exposures. "
        "Reduce broad equity and credit beta because sticky inflation and weak growth can pressure multiples and spreads."
    ),
    "Recession": (
        "Textbook prior: Favor long Treasuries, quality and defensives as growth contracts and disinflationary pressure builds. "
        "Reduce cyclical and lower-quality credit exposure while preserving liquidity."
    ),
    "Risk-On": (
        "Textbook prior: Favor broad equities, cyclicals and credit when the aggregate detector signal is constructive. "
        "Keep diversification across duration and real assets because a consensus label is not a forecast."
    ),
    "Neutral": (
        "Textbook prior: Keep exposures balanced when the aggregate signal is inside its neutral band. "
        "Favor quality, liquidity and measured risk while waiting for a clearer regime transition."
    ),
    "Risk-Off": (
        "Textbook prior: Favor duration, the dollar and low-beta or defensive assets when the aggregate signal is defensive. "
        "Reduce high-beta equities and lower-quality credit while recognizing that historical regimes can reverse quickly."
    ),
}


def _empty_prices(tickers: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(index=pd.DatetimeIndex([], name="date"), columns=list(tickers), dtype=float)


def _normalise_index(index: Any) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(index, errors="coerce", utc=True)
    if isinstance(parsed, pd.Series):
        parsed = parsed.dt.tz_convert(None)
        return pd.DatetimeIndex(parsed.dt.normalize())
    parsed = parsed.tz_convert(None) if getattr(parsed, "tz", None) is not None else parsed
    return pd.DatetimeIndex(parsed).normalize()


def _secret(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value
    secrets_path = _PROJECT_ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return None
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        with secrets_path.open("rb") as handle:
            secrets = tomllib.load(handle)
        value = secrets.get(name)
        return str(value) if value else None
    except Exception:
        return None


def _http_get_json(url: str, timeout: int = 20) -> Any:
    if _CURL_AVAILABLE:
        try:
            proc = subprocess.run(
                ["curl", "-s", "-L", "--max-time", str(timeout), url],
                capture_output=True,
                timeout=timeout + 2,
            )
            if proc.returncode == 0 and proc.stdout:
                return json.loads(proc.stdout)
        except Exception:
            pass
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def _close_series(frame: Any) -> Optional[pd.Series]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    candidates = ["Close", "close", "Adj Close", "adjClose", "adjclose"]
    close = None
    for column in candidates:
        if column in frame.columns:
            close = frame[column]
            break
    if close is None:
        return None
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    values = pd.to_numeric(close, errors="coerce")
    index = _normalise_index(frame.index)
    series = pd.Series(values.to_numpy(), index=index, name=str(getattr(close, "name", "close")))
    series = series[~series.index.isna()].dropna()
    return series[~series.index.duplicated(keep="last")].sort_index()


def _fetch_yfinance_close(ticker: str, years: int, start: Optional[pd.Timestamp]) -> Optional[pd.Series]:
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        history_kwargs: dict[str, Any] = {"interval": "1d", "timeout": 20}
        if start is None:
            history_kwargs["period"] = f"{years}y"
        else:
            history_kwargs["start"] = start.strftime("%Y-%m-%d")
            history_kwargs["end"] = (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        frame = yf.Ticker(ticker).history(**history_kwargs)
        return _close_series(frame)
    except Exception:
        return None


def _fetch_tiingo_close(ticker: str, years: int, start: Optional[pd.Timestamp]) -> Optional[pd.Series]:
    token = _secret("TIINGO_API_KEY")
    if not token:
        return None
    start_date = start or (pd.Timestamp.today().normalize() - pd.Timedelta(days=366 * max(years, 1)))
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?" + urlencode(
        {"startDate": start_date.strftime("%Y-%m-%d"), "token": token}
    )
    try:
        rows = _http_get_json(url, timeout=20)
        frame = pd.DataFrame(rows)
        if frame.empty or "date" not in frame:
            return None
        date_values = pd.to_datetime(frame.pop("date"), errors="coerce", utc=True).dt.tz_convert(None)
        close_column = "close" if "close" in frame else "adjClose" if "adjClose" in frame else None
        if close_column is None:
            return None
        series = pd.Series(pd.to_numeric(frame[close_column], errors="coerce").to_numpy(), index=_normalise_index(date_values), name=ticker)
        series = series.dropna()
        return series[~series.index.duplicated(keep="last")].sort_index()
    except Exception:
        return None


def _load_price_cache(path: Path) -> pd.DataFrame:
    try:
        if not path.exists():
            return pd.DataFrame()
        frame = pd.read_parquet(path)
        if frame.empty:
            return pd.DataFrame()
        frame.index = _normalise_index(frame.index)
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        return frame.apply(pd.to_numeric, errors="coerce")
    except Exception:
        return pd.DataFrame()


def _write_price_cache(frame: pd.DataFrame, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path)
    except Exception:
        return


def fetch_asset_history(tickers: Sequence[str] = DEFAULT_TICKERS, years: int = 15) -> pd.DataFrame:
    """Fetch daily close histories, extending the project parquet cache.

    yfinance is attempted first for every ticker.  If it returns no usable
    close series, the ticker is retried through Tiingo when a Tiingo token is
    available.  Individual failures are non-fatal and leave any cached data
    intact.
    """
    requested = list(dict.fromkeys(str(ticker).upper() for ticker in (tickers or [])))
    if not requested:
        return _empty_prices([])
    years = max(int(years), 1)
    path = Path(PLAYBOOK_PRICES_PATH)
    cached = _load_price_cache(path)
    result = cached.copy()
    for ticker in requested:
        prior = result[ticker].dropna() if ticker in result.columns else pd.Series(dtype=float)
        if prior.empty:
            start = None
        else:
            # Re-fetch a small tail so revisions to recent closes are absorbed
            # while all older cache rows remain intact.
            start = prior.index.max() - pd.offsets.BDay(5)
        series = _fetch_yfinance_close(ticker, years, start)
        source = "yfinance"
        if series is None or series.empty:
            series = _fetch_tiingo_close(ticker, years, start)
            source = "Tiingo"
        if series is None or series.empty:
            continue
        result = result.reindex(result.index.union(series.index)).sort_index()
        result.loc[series.index, ticker] = series.astype(float)
        result.attrs.setdefault("sources", {})[ticker] = source

    if result.empty:
        return _empty_prices(requested)
    all_columns = list(dict.fromkeys([*result.columns.tolist(), *requested]))
    for ticker in all_columns:
        if ticker not in result:
            result[ticker] = np.nan
    result = result[all_columns].sort_index()
    result.index.name = "date"
    _write_price_cache(result, path)
    return result[requested]


def _normalise_regime_series(regime_series: Any) -> pd.Series:
    if isinstance(regime_series, pd.DataFrame):
        frame = regime_series.copy()
        if "date" in frame.columns:
            frame = frame.set_index("date")
        if "timeframe" in frame.columns and (frame["timeframe"] == "D").any():
            frame = frame[frame["timeframe"] == "D"]
        label_column = next((column for column in ("label", "state", "regime", "regime_label") if column in frame.columns), None)
        if label_column is None:
            return pd.Series(dtype="object")
        series = frame[label_column]
    elif isinstance(regime_series, pd.Series):
        series = regime_series.copy()
    else:
        return pd.Series(dtype="object")
    if series.empty:
        return pd.Series(dtype="object")
    series.index = _normalise_index(series.index)
    series = series[~series.index.isna()].dropna()
    return series[~series.index.duplicated(keep="last")].sort_index().astype(str)


def _max_drawdown_by_spells(frame: pd.DataFrame, label: str) -> float:
    working = frame.copy()
    if working.empty:
        return 0.0
    working["_spell"] = working["_regime"].ne(working["_regime"].shift()).cumsum()
    drawdowns = []
    for _, spell in working.groupby("_spell", sort=False):
        if str(spell["_regime"].iloc[0]) != label:
            continue
        equity = (1.0 + spell["_return"]).cumprod()
        drawdowns.append(float((equity / equity.cummax() - 1.0).min()))
    return float(min(drawdowns)) if drawdowns else 0.0


def conditional_stats(regime_series: Any, prices: pd.DataFrame) -> pd.DataFrame:
    """Compute next-day return statistics by regime and asset.

    ``prices.pct_change()`` is indexed by the close on which the return ends.
    The regime is therefore shifted by one row before joining: this is the
    look-ahead guard that conditions the return on the regime known at the
    prior close, never on the close that produced the return.
    """
    columns = [
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
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        return pd.DataFrame(columns=columns)
    regime = _normalise_regime_series(regime_series)
    if regime.empty:
        return pd.DataFrame(columns=columns)

    frame = prices.copy()
    frame.index = _normalise_index(frame.index)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame = frame.apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(axis=1, how="all")
    if frame.empty:
        return pd.DataFrame(columns=columns)

    returns = frame.pct_change(fill_method=None)
    # Monthly histories such as MacroQuadrant become point-in-time daily
    # conditioning variables by carrying the latest known state forward.
    regime = regime.reindex(frame.index, method="ffill")
    # Look-ahead guard: returns[t] are from t-1 to t, so regime[t-1] is the
    # information available at the prior close that conditions that return.
    shifted_regime = regime.shift(1).rename("_regime")
    joined = returns.join(shifted_regime, how="inner").sort_index()
    rows: list[dict[str, Any]] = []
    for asset in frame.columns:
        if asset not in joined.columns:
            continue
        asset_frame = joined[["_regime", asset]].rename(columns={asset: "_return"}).dropna(subset=["_regime", "_return"])
        if asset_frame.empty:
            continue
        asset_frame["_regime"] = asset_frame["_regime"].astype(str)
        for label, group in asset_frame.groupby("_regime", sort=True):
            daily = pd.to_numeric(group["_return"], errors="coerce").dropna()
            n_days = int(len(daily))
            if n_days == 0:
                continue
            ann_return = float(daily.mean() * 252.0)
            ann_vol = float(daily.std(ddof=1) * np.sqrt(252.0)) if n_days > 1 else 0.0
            sharpe = float(ann_return / ann_vol) if ann_vol > 0 else 0.0
            rows.append(
                {
                    "regime_label": str(label),
                    "asset": str(asset),
                    "ann_return": ann_return,
                    "ann_vol": ann_vol,
                    "sharpe": sharpe,
                    "hit_rate": float((daily > 0).mean()),
                    "max_drawdown": _max_drawdown_by_spells(asset_frame, str(label)),
                    "n_days": n_days,
                    "low_sample": bool(n_days < 60),
                }
            )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(["regime_label", "asset"]).reset_index(drop=True)


__all__ = [
    "CANONICAL_PLAYBOOK",
    "DEFAULT_TICKERS",
    "PLAYBOOK_PRICES_PATH",
    "conditional_stats",
    "fetch_asset_history",
]
