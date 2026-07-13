"""Calendar and Finnhub sentiment feeds with provider fallback."""
from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st


def _secret(name: str) -> Optional[str]:
    try:
        return st.secrets.get(name) or os.environ.get(name)
    except Exception:
        return os.environ.get(name)


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_calendar() -> Dict[str, pd.DataFrame]:
    """Next 14d US high-impact economics plus megacap earnings; FMP then Finnhub."""
    today, end = dt.date.today(), dt.date.today() + dt.timedelta(days=14)
    fmp, finnhub = _secret("FMP_API_KEY"), _secret("FINNHUB_API_KEY")
    econ: List[Dict[str, Any]] = []
    earnings: List[Dict[str, Any]] = []
    if fmp:
        try:
            data = requests.get("https://financialmodelingprep.com/api/v3/economic_calendar", params={"from": today, "to": end, "apikey": fmp}, timeout=20).json()
            econ = [{"Date": x.get("date"), "Event": x.get("event"), "Impact": x.get("impact", ""), "Source": "FMP"} for x in data if x.get("country") in {"US", "United States"} and str(x.get("impact", "")).lower() == "high"]
            data = requests.get("https://financialmodelingprep.com/api/v3/earning_calendar", params={"from": today, "to": end, "apikey": fmp}, timeout=20).json()
            mega = {"AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","TSLA","BRK-B","GOOG","LLY","JPM","V","WMT","XOM","MA","UNH","COST","PG","JNJ"}
            earnings = [{"Date": x.get("date"), "Symbol": x.get("symbol"), "EPS Est.": x.get("epsEstimated"), "Source": "FMP"} for x in data if x.get("symbol") in mega]
        except Exception:
            pass
    if not econ and finnhub:
        try:
            data = requests.get("https://finnhub.io/api/v1/calendar/economic", params={"from": today, "to": end, "token": finnhub}, timeout=20).json().get("economicCalendar", [])
            econ = [{"Date": x.get("time"), "Event": x.get("event"), "Impact": x.get("impact", ""), "Source": "Finnhub"} for x in data if x.get("country") == "US" and str(x.get("impact", "")).lower() == "high"]
        except Exception:
            pass
    return {"economic": pd.DataFrame(econ), "earnings": pd.DataFrame(earnings)}


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_finnhub_sentiment(symbol: str) -> Optional[Dict[str, Any]]:
    key = _secret("FINNHUB_API_KEY")
    if not key:
        return None
    try:
        start = (dt.date.today() - dt.timedelta(days=30)).isoformat()
        data = requests.get("https://finnhub.io/api/v1/news-sentiment", params={"symbol": symbol, "from": start, "to": dt.date.today().isoformat(), "token": key}, timeout=20).json()
        sentiment = data.get("sentiment", {})
        return {"symbol": symbol, "bullish": sentiment.get("bullishPercent"), "bearish": sentiment.get("bearishPercent")}
    except Exception:
        return None
