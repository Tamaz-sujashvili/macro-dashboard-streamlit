"""Small Streamlit-free market and FRED input path for scheduled alerts."""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import pandas as pd

from modules.config import COLORS
from modules.regime_engine import RegimeSignal


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CURL_AVAILABLE = shutil.which("curl") is not None


def get_secret(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value
    path = _PROJECT_ROOT / ".streamlit" / "secrets.toml"
    if not path.exists():
        return None
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        with path.open("rb") as handle:
            values = tomllib.load(handle)
        value = values.get(name)
        return str(value) if value else None
    except Exception:
        return None


def _http_bytes(url: str, timeout: int = 20) -> bytes:
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
    request = urllib.request.Request(url, headers={"User-Agent": "macro-regime-terminal/18"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _normalise_index(index: Any) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(index, errors="coerce", utc=True)
    if isinstance(parsed, pd.Series):
        return pd.DatetimeIndex(parsed.dt.tz_convert(None).dt.normalize())
    return pd.DatetimeIndex(parsed.tz_convert(None) if getattr(parsed, "tz", None) is not None else parsed).normalize()


def _normalise_ohlcv(frame: Any) -> Optional[pd.DataFrame]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    frame = frame.rename(columns=lambda column: str(column).lower())
    required = ["open", "high", "low", "close", "volume"]
    if not set(required).issubset(frame.columns):
        return None
    frame = frame[required].apply(pd.to_numeric, errors="coerce")
    frame.index = _normalise_index(frame.index)
    frame = frame[~frame.index.isna()].dropna(subset=["open", "high", "low", "close"]).sort_index()
    return frame[~frame.index.duplicated(keep="last")] if not frame.empty else None


def _tiingo_daily(ticker: str, years: int = 15) -> Optional[pd.DataFrame]:
    token = get_secret("TIINGO_API_KEY")
    if not token:
        return None
    start = (dt.date.today() - dt.timedelta(days=366 * max(years, 1))).isoformat()
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?" + urlencode({"startDate": start, "token": token})
    try:
        rows = json.loads(_http_bytes(url, timeout=20))
        frame = pd.DataFrame(rows)
        if frame.empty or "date" not in frame:
            return None
        frame.index = _normalise_index(frame.pop("date"))
        frame = frame.rename(columns={"adjClose": "close"})
        required = ["open", "high", "low", "close", "volume"]
        if not set(required).issubset(frame.columns):
            return None
        frame = frame[required].apply(pd.to_numeric, errors="coerce").dropna()
        frame.attrs["source"] = "Tiingo"
        return frame if not frame.empty else None
    except Exception:
        return None


def _fetch_yfinance(ticker: str, period: str) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        frame = yf.Ticker(ticker).history(period=period, interval="1d", timeout=20)
        return _normalise_ohlcv(frame)
    except Exception:
        return None


def _fred_series(series_id: str, years: int = 12) -> pd.DataFrame:
    start = (dt.date.today() - dt.timedelta(days=365 * years)).isoformat()
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    try:
        frame = pd.read_csv(io.BytesIO(_http_bytes(url, timeout=20)))
        if frame.empty or len(frame.columns) < 2:
            return pd.DataFrame(columns=["date", "value"])
        date_column = "observation_date" if "observation_date" in frame.columns else "DATE"
        value_columns = [column for column in frame.columns if column != date_column]
        if not value_columns:
            return pd.DataFrame(columns=["date", "value"])
        frame = frame[[date_column, value_columns[0]]].rename(columns={date_column: "date", value_columns[0]: "value"})
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame["value"] = pd.to_numeric(frame["value"].replace(".", pd.NA), errors="coerce")
        return frame.dropna().sort_values("date").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["date", "value"])


def _monthly_rows(frame: pd.DataFrame, scale: float = 1.0) -> list[tuple[float, str]]:
    if frame.empty:
        return []
    monthly = frame.assign(month=frame["date"].dt.strftime("%Y-%m")).groupby("month", as_index=False).last()
    return [(float(row.value) * scale, str(row.month)) for row in monthly.itertuples()]


def _headless_fred() -> dict[str, Any]:
    cpi = _fred_series("CPIAUCSL")
    spread = _fred_series("BAMLC0A0CM")
    nfci = _fred_series("NFCI")
    hy = _fred_series("BAMLH0A0HYM2")
    cpi_monthly = cpi.assign(month=cpi["date"].dt.to_period("M")).groupby("month", as_index=False).last() if not cpi.empty else cpi
    if not cpi_monthly.empty:
        cpi_monthly["value"] = cpi_monthly["value"].pct_change(12) * 100.0
        cpi_monthly = cpi_monthly.dropna(subset=["value"])
    spread_rows = _monthly_rows(spread, 100.0)
    nfci_rows = _monthly_rows(nfci)
    hy_rows = _monthly_rows(hy, 100.0)
    fred: dict[str, Any] = {
        "CPI_HIST": [(value, month) for value, month in _monthly_rows(cpi_monthly)],
        "SPREAD_HIST": spread_rows,
        "NFCI_HIST": nfci_rows,
        "HY_SPREAD_HIST": hy_rows,
    }
    if nfci_rows:
        fred["NFCI"] = nfci_rows[-1][0]
    if hy_rows:
        fred["BAMLH0A0HYM2"] = hy_rows[-1][0]
    return fred


def _headless_breadth() -> RegimeSignal:
    """Build the same Breadth signal as the UI without importing Streamlit."""
    key = get_secret("POLYGON_API_KEY")
    if not key:
        return RegimeSignal("Breadth", "D", "No Data", 0, 0, COLORS["muted"], dt.date.today())

    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{(dt.date.today() - dt.timedelta(days=1)).isoformat()}"
    try:
        payload = json.loads(_http_bytes(url + "?" + urlencode({"adjusted": "true", "apiKey": key}), timeout=20))
        grouped = pd.DataFrame(payload.get("results", []))
    except Exception:
        grouped = pd.DataFrame()
    if grouped.empty or not {"c", "o"}.issubset(grouped.columns):
        return RegimeSignal("Breadth", "D", "No Data", 0, 0, COLORS["muted"], dt.date.today())

    dma_path = _PROJECT_ROOT / "data" / "sp500_200dma.csv"
    try:
        dma = pd.read_csv(dma_path) if dma_path.exists() else pd.DataFrame()
    except Exception:
        dma = pd.DataFrame()
    pct = None
    if not dma.empty and {"ticker", "dma200"}.issubset(dma.columns) and "T" in grouped:
        merged = grouped.merge(dma, left_on="T", right_on="ticker", how="inner")
        if not merged.empty:
            pct = float((pd.to_numeric(merged["c"], errors="coerce") > pd.to_numeric(merged["dma200"], errors="coerce")).mean() * 100)
    if pct is None:
        return RegimeSignal("Breadth", "D", "No Data", 0, 0, COLORS["muted"], dt.date.today())

    state = "Broad" if pct >= 60 else "Narrow" if pct >= 40 else "Deteriorating"
    score = max(-1.0, min(1.0, (pct - 50.0) / 25.0))
    color = COLORS["risk_on"] if state == "Broad" else COLORS["neutral"] if state == "Narrow" else COLORS["risk_off"]
    history_path = _PROJECT_ROOT / "data" / "breadth_history.csv"
    try:
        history = pd.read_csv(history_path, parse_dates=["date"]) if history_path.exists() else pd.DataFrame()
    except Exception:
        history = pd.DataFrame()
    today = pd.Timestamp.today().normalize()
    row = pd.DataFrame([{"date": today, "net_advances": int((grouped["c"] > grouped["o"]).sum()), "pct_above_200": pct}])
    if history.empty or "date" not in history or not (pd.to_datetime(history["date"], errors="coerce").dt.normalize() == today).any():
        history = pd.concat([history, row], ignore_index=True)
        try:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            history.to_csv(history_path, index=False)
        except Exception:
            pass
    historical_pct = pd.to_numeric(history.get("pct_above_200"), errors="coerce")
    history["risk_score"] = ((historical_pct - 50.0) / 25.0).clip(-1.0, 1.0)
    history["state"] = pd.NA
    history.loc[historical_pct >= 60, "state"] = "Broad"
    history.loc[(historical_pct >= 40) & (historical_pct < 60), "state"] = "Narrow"
    history.loc[historical_pct < 40, "state"] = "Deteriorating"
    return RegimeSignal("Breadth", "D", state, score, 0.7, color, dt.date.today(), history.tail(504))


def fetch_headless_inputs(period: str = "15y") -> dict[str, Any]:
    """Return the market/FRED inputs needed by the scheduled regime runner."""
    spy = _fetch_yfinance("SPY", period)
    if spy is None or spy.empty:
        spy = _tiingo_daily("SPY", years=15)
    if spy is None or spy.empty:
        raise RuntimeError("SPY history unavailable from yfinance and Tiingo")

    vix_frames: dict[str, Optional[pd.DataFrame]] = {}
    for ticker in ("^VIX", "^VIX9D", "^VIX3M", "^VIX6M"):
        vix_frames[ticker] = _fetch_yfinance(ticker, "1y")
    vix_values = {
        ticker: float(frame["close"].dropna().iloc[-1])
        for ticker, frame in vix_frames.items()
        if frame is not None and not frame.empty and frame["close"].notna().any()
    }
    fred = _headless_fred()
    return {
        "spy": spy,
        "vix": vix_values.get("^VIX"),
        "term_structure": vix_values,
        "fred": fred,
        "breadth": _headless_breadth(),
    }
