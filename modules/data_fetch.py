"""Network data fetching helpers with Streamlit caching.

All functions that need ``@st.cache_data`` or ``st.secrets`` live here so that
``modules.regime_engine`` remains a pure-computation module.
"""

from __future__ import annotations

import datetime
import io
import os
import shutil
import subprocess
from urllib.parse import urlencode
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st


# Prefer curl for FRED/HTTPS fetches: Python's urllib3 SSL handshake to some
# hosts (notably fred.stlouisfed.org) can hang on this machine while curl
# completes in under a second.
_CURL_AVAILABLE = shutil.which("curl") is not None


def _http_get(url: str, timeout: int = 12) -> bytes:
    """HTTP GET with a curl subprocess fallback for problematic TLS handshakes."""
    if _CURL_AVAILABLE:
        try:
            proc = subprocess.run(
                ["curl", "-s", "-L", "--max-time", str(timeout), url],
                capture_output=True,
                timeout=timeout + 2,
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
        except Exception:
            pass

    import urllib.request

    return urllib.request.urlopen(url, timeout=timeout).read()


def _http_get_text(url: str, timeout: int = 12) -> str:
    return _http_get(url, timeout).decode("utf-8", errors="ignore")


def _http_get_json(url: str, timeout: int = 12) -> Any:
    import json

    return json.loads(_http_get(url, timeout))


def _normalize_fredgraph_df(csv_text: str) -> Optional[pd.DataFrame]:
    """Read a FREDGraph CSV and normalize columns to DATE/VALUE.

    The public FREDGraph endpoint returns ``observation_date`` plus a column
    named after the series id (e.g. ``CPIAUCSL``), not ``DATE``/``VALUE``.
    """
    try:
        df = pd.read_csv(io.StringIO(csv_text))
    except Exception:
        return None

    if df.empty or len(df.columns) < 2:
        return None

    # Modern FREDGraph format: observation_date, SERIES_ID
    if "observation_date" in df.columns:
        df = df.rename(columns={"observation_date": "DATE"})
        value_cols = [c for c in df.columns if c != "DATE"]
        if not value_cols:
            return None
        df = df.rename(columns={value_cols[0]: "VALUE"})
    elif "DATE" not in df.columns:
        return None

    if "VALUE" not in df.columns:
        return None

    df = df[df["VALUE"].astype(str) != "."].copy()
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
    df = df.dropna(subset=["DATE", "VALUE"]).sort_values("DATE")
    return df if not df.empty else None


def _fred_api_key() -> Optional[str]:
    """Resolve the FRED API key from Streamlit secrets or environment."""
    try:
        key = st.secrets.get("FRED_API_KEY")
    except Exception:
        key = None
    return key or os.environ.get("FRED_API_KEY")


def _secret(name: str) -> Optional[str]:
    """Read a provider credential without ever logging it."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value or os.environ.get(name)


def _tiingo_daily(ticker: str, period: str) -> Optional[pd.DataFrame]:
    """Return Tiingo OHLCV in the same shape as yfinance history."""
    key = _secret("TIINGO_API_KEY")
    if not key:
        return None
    years = 10 if period.endswith("y") else 2
    start = (datetime.date.today() - datetime.timedelta(days=366 * years)).isoformat()
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?" + urlencode({"startDate": start, "token": key})
    try:
        rows = _http_get_json(url, timeout=20)
        df = pd.DataFrame(rows)
        if df.empty or "date" not in df:
            return None
        df.index = pd.to_datetime(df.pop("date"), utc=True).tz_convert(None)
        cols = {"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}
        df = df.rename(columns=cols)
        required = [c for c in cols.values() if c in df.columns]
        if not {"open", "high", "low", "close", "volume"}.issubset(required):
            return None
        df = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce").dropna()
        df.attrs["source"] = "Tiingo"
        return df if not df.empty else None
    except Exception:
        return None


@st.cache_data(ttl=900)
def fetch_spy_vix_history(
    period: str = "10y",
    interval: str = "1d",
) -> Dict[str, Optional[pd.DataFrame]]:
    """Fetch daily SPY and ^VIX history, falling back to Tiingo for SPY.

    Returns a dict with keys ``spy`` and ``vix``.  Any network failure returns
    ``None`` values rather than raising.
    """
    source = "yfinance"
    try:
        import yfinance as yf
    except Exception:
        yf = None

    try:
        spy = yf.Ticker("SPY").history(period=period, interval=interval, timeout=20) if yf else None
        if spy is not None and not spy.empty:
            spy = spy.rename(columns=str.lower).rename(
                columns={
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                }
            )[["open", "high", "low", "close", "volume"]]
    except Exception:
        spy = None

    if spy is None or spy.empty:
        spy = _tiingo_daily("SPY", period)
        if spy is not None:
            source = "Tiingo"

    try:
        vix = yf.Ticker("^VIX").history(period=period, interval=interval, timeout=20) if yf else None
        if vix is not None and not vix.empty:
            vix = vix[["Close"]].rename(columns={"Close": "close"})
    except Exception:
        vix = None

    if spy is not None:
        spy.attrs["source"] = source
    return {"spy": spy, "vix": vix, "source": source}


@st.cache_data(ttl=3600)
def fetch_fred_latest(series_id: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Minimal FRED latest-value fetch with FredGraph CSV fallback."""
    key = api_key or _fred_api_key()

    if key:
        url = (
            "https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={key}"
            "&file_type=json&sort_order=desc&limit=1&units=lin"
        )
        try:
            data = _http_get_json(url, timeout=15)
            obs = [o for o in data.get("observations", []) if o.get("value") not in (None, ".")]
            if obs:
                return {
                    "value": float(obs[0]["value"]),
                    "date": obs[0]["date"],
                    "series_id": series_id,
                }
        except Exception:
            pass

    # FredGraph CSV fallback (no API key required).
    try:
        start = (datetime.date.today() - datetime.timedelta(days=365 * 2)).isoformat()
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
        df = _normalize_fredgraph_df(_http_get_text(url, timeout=20))
        if df is None:
            return None
        latest = df.iloc[-1]
        return {
            "value": float(latest["VALUE"]),
            "date": latest["DATE"].strftime("%Y-%m-%d"),
            "series_id": series_id,
        }
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_fred_hist(series_id: str, limit: int = 16, units: str = "lin") -> List[tuple]:
    """Fetch the most recent ``limit`` FRED observations as (value, date) tuples.

    The returned date string is ``YYYY-MM`` for monthly-style consumption by
    the macro quadrant adapter and liquidity ROC helpers.
    """
    key = _fred_api_key()

    obs: List[Dict[str, Any]] = []
    if key:
        url = (
            "https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={key}"
            f"&file_type=json&sort_order=desc&limit={limit}&units={units}"
        )
        try:
            data = _http_get_json(url, timeout=15)
            obs = [o for o in data.get("observations", []) if o.get("value") not in (None, ".")]
        except Exception:
            obs = []

    # Fallback to FredGraph when API key is absent or returned no observations.
    if not obs:
        try:
            lookback_years = 2 if limit <= 6 else 5 if limit <= 16 else 8 if limit <= 52 else 12
            start = (datetime.date.today() - datetime.timedelta(days=365 * lookback_years)).isoformat()
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
            df = _normalize_fredgraph_df(_http_get_text(url, timeout=20))
            if df is None:
                return []
            df = df.tail(limit)
            obs = [
                {"date": row["DATE"].strftime("%Y-%m-%d"), "value": str(row["VALUE"])}
                for _, row in df.iterrows()
            ]
        except Exception:
            return []

    rows = []
    for o in obs:
        if o.get("value") == ".":
            continue
        try:
            value = float(o["value"])
        except (TypeError, ValueError):
            continue
        if series_id in {"BAMLH0A0HYM2", "BAMLC0A0CM"} and units == "lin":
            value *= 100.0
        rows.append((value, o["date"][:7]))
    return rows
