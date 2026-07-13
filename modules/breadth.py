"""Polygon-backed market breadth, designed to degrade to a No Data signal."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import requests
import streamlit as st

from modules.config import COLORS
from modules.regime_engine import RegimeSignal

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONSTITUENTS_PATH = DATA_DIR / "sp500_constituents.csv"
DMA_PATH = DATA_DIR / "sp500_200dma.csv"
BREADTH_HISTORY_PATH = DATA_DIR / "breadth_history.csv"
CONSTITUENTS_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"


def _key() -> Optional[str]:
    try:
        return st.secrets.get("POLYGON_API_KEY") or os.environ.get("POLYGON_API_KEY")
    except Exception:
        return os.environ.get("POLYGON_API_KEY")


def load_constituents() -> pd.DataFrame:
    """Load static constituents, downloading once only when the file is absent."""
    if not CONSTITUENTS_PATH.exists():
        try:
            DATA_DIR.mkdir(exist_ok=True)
            response = requests.get(CONSTITUENTS_URL, timeout=20)
            response.raise_for_status()
            CONSTITUENTS_PATH.write_bytes(response.content)
        except Exception:
            return pd.DataFrame(columns=["Symbol"])
    try:
        df = pd.read_csv(CONSTITUENTS_PATH)
        return df.rename(columns={"Symbol": "symbol"})
    except Exception:
        return pd.DataFrame(columns=["symbol"])


def load_dma_snapshot() -> pd.DataFrame:
    """Use a daily local 200DMA snapshot; bootstrap it once with yfinance bulk data.

    Polygon is deliberately used only for the last grouped close.  The one-time
    historical bootstrap is a bulk Yahoo request and is persisted locally.
    """
    if DMA_PATH.exists() and (dt.datetime.now().timestamp() - DMA_PATH.stat().st_mtime) < 86400:
        try:
            return pd.read_csv(DMA_PATH)
        except Exception:
            pass
    symbols = load_constituents().get("symbol", pd.Series(dtype=str)).dropna().astype(str).str.replace(".", "-", regex=False).tolist()
    if not symbols:
        return pd.DataFrame(columns=["ticker", "dma200"])
    try:
        import yfinance as yf
        closes = yf.download(symbols, period="1y", interval="1d", group_by="column", progress=False, threads=True, auto_adjust=True)["Close"]
        dma = closes.tail(200).mean().dropna()
        snapshot = pd.DataFrame({"ticker": dma.index, "dma200": dma.values})
        DATA_DIR.mkdir(exist_ok=True)
        snapshot.to_csv(DMA_PATH, index=False)
        return snapshot
    except Exception:
        return pd.DataFrame(columns=["ticker", "dma200"])


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_polygon_grouped(close_date: Optional[str] = None) -> pd.DataFrame:
    """Fetch just the last completed session, respecting Polygon's free tier."""
    key = _key()
    if not key:
        return pd.DataFrame()
    date = close_date or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date}"
    try:
        response = requests.get(url, params={"adjusted": "true", "apiKey": key}, timeout=20)
        if response.status_code != 200:
            return pd.DataFrame()
        rows = response.json().get("results", [])
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def compute_breadth(grouped: pd.DataFrame, dma_snapshot: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Compute A/D and % above 200DMA from cached daily inputs.

    ``dma_snapshot`` is a locally-maintained snapshot (ticker, dma200); this
    avoids hundreds of historical Polygon requests on the free tier.
    """
    if grouped is None or grouped.empty or not {"c", "o"}.issubset(grouped.columns):
        return {"advancers": None, "decliners": None, "ad_line": None, "pct_above_200": None, "history": pd.DataFrame()}
    adv = int((grouped["c"] > grouped["o"]).sum())
    dec = int((grouped["c"] < grouped["o"]).sum())
    pct = None
    if dma_snapshot is not None and not dma_snapshot.empty and {"ticker", "dma200"}.issubset(dma_snapshot.columns):
        merged = grouped.merge(dma_snapshot, left_on="T", right_on="ticker", how="inner")
        if not merged.empty:
            pct = float((merged["c"] > merged["dma200"]).mean() * 100)
    history = pd.DataFrame([{ "date": pd.Timestamp.today().normalize(), "ad_line": adv - dec, "pct_above_200": pct }])
    return {"advancers": adv, "decliners": dec, "ad_line": adv - dec, "pct_above_200": pct, "history": history}


def update_breadth_history(reading: Dict[str, Any]) -> Dict[str, Any]:
    """Persist one reading per close and turn daily net advances into A/D line."""
    if not reading or reading.get("ad_line") is None:
        return reading
    DATA_DIR.mkdir(exist_ok=True)
    today = pd.Timestamp.today().normalize()
    try:
        history = pd.read_csv(BREADTH_HISTORY_PATH, parse_dates=["date"]) if BREADTH_HISTORY_PATH.exists() else pd.DataFrame()
    except Exception:
        history = pd.DataFrame()
    row = pd.DataFrame([{"date": today, "net_advances": reading["ad_line"], "pct_above_200": reading.get("pct_above_200")}])
    if history.empty or not (pd.to_datetime(history["date"]).dt.normalize() == today).any():
        history = pd.concat([history, row], ignore_index=True)
        history.to_csv(BREADTH_HISTORY_PATH, index=False)
    history["ad_line"] = pd.to_numeric(history["net_advances"], errors="coerce").fillna(0).cumsum()
    reading["ad_line"] = float(history["ad_line"].iloc[-1])
    reading["history"] = history.tail(504)
    return reading


def breadth_detector(breadth: Dict[str, Any]) -> RegimeSignal:
    pct = breadth.get("pct_above_200") if breadth else None
    if pct is None:
        return RegimeSignal("Breadth", "D", "No Data", 0, 0, COLORS["muted"], dt.date.today())
    state = "Broad" if pct >= 60 else "Narrow" if pct >= 40 else "Deteriorating"
    # percentile-like normalized positioning around the 40/60 regime bands.
    score = max(-1.0, min(1.0, (float(pct) - 50.0) / 25.0))
    color = COLORS["risk_on"] if state == "Broad" else COLORS["neutral"] if state == "Narrow" else COLORS["risk_off"]
    hist = breadth.get("history", pd.DataFrame())
    return RegimeSignal("Breadth", "D", state, score, 0.7, color, dt.date.today(), hist)
