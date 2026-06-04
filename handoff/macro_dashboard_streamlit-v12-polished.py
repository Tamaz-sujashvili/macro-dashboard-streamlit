#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        MACRO MARKET DASHBOARD  —  Streamlit Edition (v12 polished)                  ║
║  Refactored from static HTML output to a fully interactive Streamlit app.   ║
║  All data-fetching logic preserved; UI/UX layer modernized.                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

# ─── .streamlit/secrets.toml ──────────────────────────────────────────────────
# [secrets]
# FRED_API_KEY      = ""
# ALPHA_VANTAGE_KEY = ""
#
# Obtain keys at:
#   FRED: https://fred.stlouisfed.org/docs/api/api_key.html
#   Alpha Vantage: https://www.alphavantage.co/support/#api-key
# ─────────────────────────────────────────────────────────────────────────────

# ─── .streamlit/config.toml ──────────────────────────────────────────────────
# [theme]
# base                   = "dark"
# primaryColor           = "#3b82f6"
# backgroundColor        = "#0f1117"
# secondaryBackgroundColor = "#161b27"
# textColor              = "#e2e8f0"
# ─────────────────────────────────────────────────────────────────────────────
"""

import os, json, time, datetime, threading, io, re, ssl, sys, subprocess, shutil
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Macro Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL UI THEME (v12) ─────────────────────────────────────────────────────
# Modern Bloomberg/Notion-inspired dark theme. Pure presentation layer:
# does not modify any data, calculations, or Plotly chart definitions.
_THEME_CSS = """
<style>
  /* ---------- Fonts ---------- */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

  :root {
    --bg:          #0b0e14;
    --bg-elev:    #10141d;
    --surface:    #141923;
    --surface-2:  #1a2030;
    --border:     #1f2a3a;
    --border-soft:#172033;
    --text:       #e6edf3;
    --muted:      #8b95a7;
    --muted-2:    #6b7689;
    --accent:     #3b82f6;
    --accent-2:   #60a5fa;
    --green:      #22c55e;
    --green-bg:   rgba(34,197,94,0.12);
    --amber:      #f59e0b;
    --amber-bg:   rgba(245,158,11,0.12);
    --red:        #ef4444;
    --red-bg:     rgba(239,68,68,0.12);
    --blue-bg:    rgba(59,130,246,0.14);
    --radius-card:10px;
    --radius-pill:999px;
  }

  html, body, .stApp, .main, .block-container,
  [data-testid="stAppViewContainer"],
  [data-testid="stSidebar"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    color: var(--text);
  }
  .stApp { background: var(--bg) !important; }

  /* Preserve Streamlit's icon ligature font inside controls like expanders. */
  [data-testid="stIconMaterial"],
  .material-symbols-rounded,
  .material-symbols-outlined,
  .material-icons {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
    font-weight: normal !important;
    font-style: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
  }

  .block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1500px;
  }

  /* ---------- Headings ---------- */
  h1, h2, h3, h4 {
    font-family: 'Inter', sans-serif !important;
    color: var(--text) !important;
    letter-spacing: -0.01em;
    font-weight: 600 !important;
  }
  h1 { font-size: 1.7rem !important; }
  h2 { font-size: 1.25rem !important; margin-top: 0.4rem !important; }
  h3 { font-size: 1.05rem !important; }

  /* Streamlit subheader: add an accent bar on the left */
  [data-testid="stHeadingWithActionElements"] h2,
  [data-testid="stHeadingWithActionElements"] h3 {
    position: relative;
    padding-left: 12px;
  }
  [data-testid="stHeadingWithActionElements"] h2::before,
  [data-testid="stHeadingWithActionElements"] h3::before {
    content: "";
    position: absolute;
    left: 0; top: 14%;
    width: 3px; height: 72%;
    background: var(--accent);
    border-radius: 2px;
    opacity: 0.85;
  }

  /* ---------- Numbers (mono) ---------- */
  [data-testid="stMetricValue"],
  [data-testid="stMetricDelta"],
  .mono, code, pre, table tbody td {
    font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace !important;
    font-variant-numeric: tabular-nums;
  }

  /* ---------- Streamlit metric cards ---------- */
  [data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    padding: 14px 16px 12px 16px;
    transition: transform 0.15s ease, border-color 0.15s ease;
  }
  [data-testid="stMetric"]:hover {
    transform: translateY(-1px);
    border-color: #2a3a55;
  }
  [data-testid="stMetricLabel"] p {
    color: var(--muted) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500 !important;
  }
  [data-testid="stMetricValue"] {
    color: var(--text) !important;
    font-size: 1.55rem !important;
    font-weight: 600 !important;
  }
  [data-testid="stMetricDelta"] {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
  }

  /* ---------- Tabs ---------- */
  .stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg-elev);
    border: 1px solid var(--border-soft);
    border-radius: 10px;
    padding: 4px;
    position: sticky;
    top: 0;
    z-index: 50;
    backdrop-filter: blur(8px);
  }
  .stTabs [data-baseweb="tab"] {
    height: 38px;
    padding: 0 14px;
    background: transparent;
    border-radius: 7px;
    color: var(--muted) !important;
    font-weight: 500;
    font-size: 0.92rem;
    border: none !important;
    transition: all 0.15s ease;
  }
  .stTabs [data-baseweb="tab"]:hover {
    color: var(--text) !important;
    background: var(--surface);
  }
  .stTabs [aria-selected="true"] {
    background: var(--surface-2) !important;
    color: var(--accent-2) !important;
    box-shadow: inset 0 -2px 0 0 var(--accent);
  }
  .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
  .stTabs [data-baseweb="tab-border"]    { display: none !important; }

  /* ---------- Dividers ---------- */
  hr, [data-testid="stDivider"] {
    border: none !important;
    border-top: 1px solid var(--border-soft) !important;
    margin: 1.1rem 0 0.9rem 0 !important;
    opacity: 1 !important;
  }

  /* ---------- Sidebar ---------- */
  [data-testid="stSidebar"] {
    background: var(--bg-elev) !important;
    border-right: 1px solid var(--border-soft);
  }
  [data-testid="stSidebar"] * { color: var(--text); }
  [data-testid="stSidebar"] h2 { font-size: 1.15rem !important; }

  /* ---------- DataFrame ---------- */
  [data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    overflow: hidden;
  }

  /* ---------- Expanders ---------- */
  [data-testid="stExpander"] {
    background: var(--surface);
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-card) !important;
  }
  [data-testid="stExpander"] summary {
    color: var(--text) !important;
    font-weight: 500;
  }

  /* ---------- Buttons ---------- */
  .stButton > button {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.15s ease;
  }
  .stButton > button:hover {
    background: var(--surface-2);
    border-color: var(--accent);
    color: var(--accent-2);
  }

  /* ---------- Inputs ---------- */
  .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div,
  .stDateInput input {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
  }

  /* ---------- v12 reusable components ---------- */
  .v12-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    padding: 14px 16px;
    margin-bottom: 10px;
  }
  .v12-card-title {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    font-weight: 600;
    margin-bottom: 10px;
  }
  .v12-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 4px;
    border-bottom: 1px solid var(--border-soft);
    transition: background 0.12s ease;
  }
  .v12-row:last-child { border-bottom: none; }
  .v12-row:hover { background: rgba(255,255,255,0.02); }
  .v12-row .v12-label {
    color: var(--muted);
    font-size: 0.88rem;
    display: flex; align-items: center; gap: 8px;
  }
  .v12-row .v12-value {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 0.94rem;
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }

  .v12-dot {
    width: 8px; height: 8px; border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 0 2px rgba(255,255,255,0.04);
  }
  .v12-dot.green { background: var(--green); }
  .v12-dot.amber { background: var(--amber); }
  .v12-dot.red   { background: var(--red); }
  .v12-dot.blue  { background: var(--accent); }
  .v12-dot.muted { background: var(--muted-2); }

  .v12-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    font-size: 0.78rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.02em;
  }
  .v12-pill.green { background: var(--green-bg); color: var(--green); }
  .v12-pill.amber { background: var(--amber-bg); color: var(--amber); }
  .v12-pill.red   { background: var(--red-bg);   color: var(--red); }
  .v12-pill.blue  { background: var(--blue-bg);  color: var(--accent-2); }
  .v12-pill.muted { background: rgba(139,149,167,0.12); color: var(--muted); }

  .v12-kpi {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    padding: 14px 16px;
    height: 100%;
    transition: transform 0.15s ease, border-color 0.15s ease;
  }
  .v12-kpi:hover { transform: translateY(-1px); border-color: #2a3a55; }
  .v12-kpi-label {
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    font-weight: 600;
  }
  .v12-kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.55rem;
    font-weight: 600;
    color: var(--text);
    margin-top: 6px;
    font-variant-numeric: tabular-nums;
  }

  .v12-tile {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    padding: 12px 14px;
    display: flex; flex-direction: column; gap: 4px;
  }
  .v12-tile .v12-tile-ticker {
    font-size: 0.75rem;
    color: var(--muted);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .v12-tile .v12-tile-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }

  /* Hide Streamlit chrome we don't need */
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }
  [data-testid="stHeader"] { background: transparent; }

  /* Plotly card wrapper */
  .stPlotlyChart {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    padding: 6px 6px 2px 6px;
  }

  /* Caption / small text */
  .stCaption, [data-testid="stCaptionContainer"] { color: var(--muted) !important; }
</style>
"""
st.markdown(_THEME_CSS, unsafe_allow_html=True)


# ── v12 reusable HTML helpers (presentation only) ─────────────────────────────
def _v12_pill(text: str, color: str = "blue") -> str:
    """Return HTML for a colored status pill. color in {green,amber,red,blue,muted}."""
    c = color if color in {"green", "amber", "red", "blue", "muted"} else "blue"
    return f'<span class="v12-pill {c}">{text}</span>'

def _v12_dot(color: str = "blue") -> str:
    c = color if color in {"green", "amber", "red", "blue", "muted"} else "blue"
    return f'<span class="v12-dot {c}"></span>'

def _v12_kpi_card(label: str, value: str, delta: str = "", delta_color: str = "muted") -> str:
    delta_html = f'<div style="margin-top:8px">{_v12_pill(delta, delta_color)}</div>' if delta else ""
    return (
        f'<div class="v12-kpi">'
        f'  <div class="v12-kpi-label">{label}</div>'
        f'  <div class="v12-kpi-value">{value}</div>'
        f'  {delta_html}'
        f'</div>'
    )

def _v12_indicator_row(name: str, value: str, status: str = "muted") -> str:
    return (
        f'<div class="v12-row">'
        f'  <div class="v12-label">{_v12_dot(status)} {name}</div>'
        f'  <div class="v12-value">{value}</div>'
        f'</div>'
    )

def _v12_card_open(title: str = "") -> str:
    t = f'<div class="v12-card-title">{title}</div>' if title else ""
    return f'<div class="v12-card">{t}'

def _v12_card_close() -> str:
    return '</div>'

def _v12_tile(ticker: str, price: str, change_pct: float | None = None) -> str:
    pill = ""
    if change_pct is not None:
        color = "green" if change_pct > 0 else ("red" if change_pct < 0 else "muted")
        arrow = "▲" if change_pct > 0 else ("▼" if change_pct < 0 else "■")
        pill = _v12_pill(f"{arrow} {change_pct:+.2f}%", color)
    return (
        f'<div class="v12-tile">'
        f'  <div class="v12-tile-ticker">{ticker}</div>'
        f'  <div class="v12-tile-price">{price}</div>'
        f'  <div>{pill}</div>'
        f'</div>'
    )
# ─────────────────────────────────────────────────────────────────────────────


# ── API KEYS (helpers + loading) ────────────────────────────────────────────
def get_api_key(key_name: str) -> str:
    """
    Retrieve an API key by checking multiple sources in priority order.

    Order of precedence:
    1. Streamlit session_state (allows runtime overrides from sidebar inputs)
    2. st.secrets (keys defined in `.streamlit/secrets.toml`)
    3. Environment variables

    Keys are case-insensitive; both uppercase and lowercase variants are tried.
    Returns an empty string if the key is not found.
    """
    variants = {key_name, key_name.upper(), key_name.lower()}
    # Check session_state first for dynamically entered keys
    try:
        if hasattr(st, "session_state"):
            for variant in variants:
                val = st.session_state.get(variant)
                if val:
                    return val
    except Exception:
        pass
    # Then st.secrets (if available)
    for variant in variants:
        try:
            if variant in st.secrets:
                return st.secrets[variant]
        except Exception:
            pass
    # Finally environment variables
    for variant in variants:
        val = os.environ.get(variant)
        if val:
            return val
    return ""

# Default keys can be overridden by `.streamlit/secrets.toml` or env vars.
FRED_API_KEY = get_api_key("FRED_API_KEY")
ALPHA_VANTAGE_KEY = get_api_key("ALPHA_VANTAGE_KEY")
BLS_API_KEY = get_api_key("BLS_API_KEY")
EIA_API_KEY = get_api_key("EIA_API_KEY")
FMP_API_KEY = get_api_key("FMP_API_KEY")
CFTC_APP_TOKEN = get_api_key("CFTC_APP_TOKEN")
NASDAQ_API_KEY = get_api_key("NASDAQ_API_KEY")
CONGRESS_GOV_API_KEY = get_api_key("CONGRESS_GOV_API_KEY")
FINNHUB_API_KEY = get_api_key("FINNHUBAPIKEY") or get_api_key("FINNHUB_API_KEY")

# ── HTTP HELPERS (requests preferred; urllib fallback with SSL fix) ────────────
try:
    import requests as _requests
    _SESSION = _requests.Session()
    _SESSION.headers.update({"User-Agent": "macro-dashboard/10"})
    _USE_REQUESTS = True
except ImportError:
    _USE_REQUESTS = False

try:
    import certifi as _certifi
    _SSL_CTX = ssl.create_default_context(cafile=_certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode    = ssl.CERT_NONE

def _http_get(url, timeout=12):
    if _USE_REQUESTS:
        r = _SESSION.get(url, timeout=timeout)
        r.raise_for_status()
        return r.content
    req = urllib.request.Request(url, headers={"User-Agent": "macro-dashboard/10"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        return r.read()

def _http_get_text(url, timeout=12):
    return _http_get(url, timeout).decode("utf-8", errors="ignore")

def _http_get_json(url, timeout=12):
    return json.loads(_http_get(url, timeout))

_FRED_ERRORS: dict = {}


def _has_key(value) -> bool:
    return bool(str(value).strip()) if value is not None else False

# ── SERIES / TICKER CONFIG ───────────────────────────────────────────────────
FRED_SERIES = {
    "GDPNOW"         : ("GDPNow (Atlanta Fed)",         "Growth",    "%"),
    "A191RL1Q225SBEA": ("GDP Growth (Annualized)",       "Growth",    "%"),
    "INDPRO"         : ("Industrial Production",         "Growth",    "%"),
    "WEI"            : ("Weekly Economic Index",         "Growth",    "idx"),
    "USSLIND"        : ("Leading Economic Index (LEI)",  "Growth",    "idx"),
    "CFNAI"          : ("Chicago Fed CFNAI",             "Growth",    "idx"),
    "CPIAUCSL"       : ("CPI Inflation (YoY)",           "Inflation", "%"),
    "CPILFESL"       : ("Core CPI (ex Food/Energy)",     "Inflation", "%"),
    "PCEPILFE"       : ("Core PCE Inflation",            "Inflation", "%"),
    "T10YIE"         : ("10Y Breakeven Inflation",       "Inflation", "%"),
    "UNRATE"         : ("Unemployment Rate",             "Labor",     "%"),
    "U6RATE"         : ("U-6 Underemployment",           "Labor",     "%"),
    "CIVPART"        : ("Labor Force Participation",     "Labor",     "%"),
    "JTSJOL"         : ("Job Openings (JOLTS)",          "Labor",     "k"),
    "CES0500000003"  : ("Average Hourly Earnings",       "Labor",     "$"),
    "ICSA"           : ("Initial Jobless Claims",        "Labor",     "k"),
    "DFF"            : ("Fed Funds Rate",                "Fed",       "%"),
    "DFEDTARU"       : ("Fed Funds Upper Target",        "Fed",       "%"),
    "DFEDTARL"       : ("Fed Funds Lower Target",        "Fed",       "%"),
    "WALCL"          : ("Fed Balance Sheet",             "Fed",       "$T"),
    "M2SL"           : ("M2 Money Supply",               "Liquidity", "$B"),
    "ECBDFR"         : ("ECB Deposit Rate",              "GlobalCB",  "%"),
    "BOERUKM"        : ("Bank of England Rate",          "GlobalCB",  "%"),
    "IRSTCI01JPM156N": ("Bank of Japan Rate",            "GlobalCB",  "%"),
    "BAMLH0A0HYM2"   : ("HY Credit Spread",             "Credit",    "bp"),
    "BAMLC0A0CM"     : ("IG Credit Spread",              "Credit",    "bp"),
    "DGS2"           : ("2Y Treasury Yield",              "Rates",     "%"),
    "DGS10"          : ("10Y Treasury Yield",            "Rates",     "%"),
    "DGS30"          : ("30Y Treasury Yield",            "Rates",     "%"),
    "NFCI"           : ("Chicago Financial Conditions",  "Credit",    "idx"),
    "STLFSI2"        : ("St. Louis Stress Index",        "Credit",    "idx"),
    "T10Y3M"         : ("10Y-3M Yield Spread",           "Liquidity", "%"),
    "T10Y2Y"         : ("10Y-2Y Yield Spread",           "Liquidity", "%"),
    "T30Y2Y"         : ("30Y-2Y Treasury Slope",         "Rates",     "%"),
    "SOFR"           : ("SOFR Rate",                     "Liquidity", "%"),
    "TEDRATE"        : ("TED Spread",                    "Liquidity", "%"),
    "DRTSCILM"       : ("Loan Officer Tightening Stds",  "Liquidity", "%"),
    "BOGMBASE"       : ("Monetary Base",                 "Liquidity", "B"),
    "WRMFSL"         : ("Retail Money Market Funds (Discontinued)", "Liquidity", "B"),
    "WRMFNS"         : ("Retail Money Market Fund Assets",          "Liquidity", "B"),
    "WIMFSL"         : ("Institutional Money Market Funds (Discontinued)", "Liquidity", "B"),
    "WIMFNS"         : ("Institutional Money Market Funds (Discontinued)", "Liquidity", "B"),
    "BOGZ1FL653064100Q": ("Mutual Fund Total Equity Assets",      "Institutional", "B"),
    "DTWEXBGS"       : ("USD Broad Trade-Weighted Index",         "CTA",           "idx"),
    "UMCSENT"        : ("University of Michigan Consumer Sentiment Index", "Sentiment", "idx"),
    "RSXFS"          : ("Retail Sales (ex-Auto)",        "Consumer",  "$B"),
    "DSPIC96"        : ("Real Disposable Income",        "Consumer",  "$B"),
    "PSAVERT"        : ("Personal Savings Rate",         "Labor/Consumer", "%"),
    "TOTALSL"        : ("Total Consumer Credit",         "Consumer",  "$B"),
    "HOUST"          : ("Housing Starts",                "Housing",   "k"),
    "PERMIT"         : ("Building Permits",              "Housing",   "k"),
    "MSPUS"          : ("Median Home Price",             "Housing",   "$"),
    "CSUSHPINSA"     : ("Case-Shiller HPI (YoY)",        "Housing",   "%"),
    "MORTGAGE30US"   : ("30yr Mortgage Rate",            "Housing",   "%"),
    "MORTGAGE15US"   : ("15yr Mortgage Rate",            "Housing",   "%"),
    "MSPNHSUS"        : ("New Home Sales",                "Housing",   "k"),
    "RECPROUSM156N"  : ("US Recession Probability",      "Risk",      "%"),
    "SAHMREALTIME"   : ("Sahm Rule Real-Time",           "Recession", "pts"),
}

YF_TICKERS = [
    "^GSPC","^IXIC","^DJI","^RUT",
    "ES=F","NQ=F","YM=F","RTY=F",
    "^FTSE","^N225","^STOXX50E","^HSI",
    "^VIX","^VIX9D","^VIX3M","^VIX6M","^VIX1Y","^VVIX","^GVZ","^SKEW","^MOVE",
    "^DSPX","^KCJ",
    "CL=F","BZ=F","GC=F","SI=F","HG=F","PL=F","PA=F","ALI=F","NG=F",
    "BTC-USD",
    "DX-Y.NYB","JPY=X","EURUSD=X","GBPUSD=X","CNY=X","CNH=X",
    "^TNX","^FVX","^TYX",
    "TLT","HYG","IWM","LQD",
]

THRESHOLDS = {
    "CPIAUCSL"       : [(2.5, "🟢"), (4.0, "🟡"), (1e9, "🔴")],
    "CPILFESL"       : [(2.5, "🟢"), (3.5, "🟡"), (1e9, "🔴")],
    "PCEPILFE"       : [(2.5, "🟢"), (3.5, "🟡"), (1e9, "🔴")],
    "T10YIE"         : [(2.5, "🟢"), (3.5, "🟡"), (1e9, "🔴")],
    "UNRATE"         : [(4.5, "🟢"), (6.0, "🟡"), (1e9, "🔴")],
    "U6RATE"         : [(8.0, "🟢"), (10.0,"🟡"), (1e9, "🔴")],
    "ICSA"           : [(250,  "🟢"), (350, "🟡"), (1e9, "🔴")],
    "CIVPART"        : [(62.0, "🔴"), (63.5,"🟡"), (1e9, "🟢")],
    "GDPNOW"         : [(0.0,  "🔴"), (2.0, "🟡"), (1e9, "🟢")],
    "A191RL1Q225SBEA": [(0.0,  "🔴"), (2.0, "🟡"), (1e9, "🟢")],
    "INDPRO"         : [(-1.0, "🔴"), (0.0, "🟡"), (1e9, "🟢")],
    "USSLIND"        : [(0.0,  "🔴"), (0.3, "🟡"), (1e9, "🟢")],
    "WEI"            : [(0.0,  "🔴"), (0.5, "🟡"), (1e9, "🟢")],
    "CFNAI"          : [(-1.0, "🔴"), (0.0, "🟡"), (1e9, "🟢")],
    "SAHMREALTIME"   : [(0.3, "🟢"), (0.5, "🟡"), (1e9, "🔴")],
    "DFF"            : [(3.0,  "🟢"), (5.5, "🟡"), (1e9, "🔴")],
    "BAMLH0A0HYM2"   : [(300,  "🟢"), (500, "🟡"), (1e9, "🔴")],
    "BAMLC0A0CM"     : [(100,  "🟢"), (200, "🟡"), (1e9, "🔴")],
    "NFCI"           : [(-0.5, "🟢"), (0.5, "🟡"), (1e9, "🔴")],
    "STLFSI2"        : [(-0.5, "🟢"), (0.5, "🟡"), (1e9, "🔴")],
    "T10Y3M"         : [(-0.5, "🔴"), (0.0, "🟡"), (1e9, "🟢")],
    "T10Y2Y"         : [(-0.5, "🔴"), (0.0, "🟡"), (1e9, "🟢")],
    "T30Y2Y"         : [(-0.5, "🔴"), (0.0, "🟡"), (1e9, "🟢")],
    "SOFR"           : [(0.0, "🟢"), (5.0, "🟡"), (1e9, "🔴")],
    "TEDRATE"        : [(0.3, "🟢"), (0.5, "🟡"), (1e9, "🔴")],
    "DRTSCILM"       : [(20,  "🟡"), (40,  "🔴"), (1e9, "🔴")],
    "WRMFNS"         : [(5000, "🟢"), (6000, "🟡"), (1e9, "🔴")],
    "WRMFSL"         : [(2000, "🟢"), (3000, "🟡"), (1e9, "🔴")],
    "UMCSENT"        : [(60.0, "🔴"), (80.0,"🟡"), (1e9, "🟢")],
    "PSAVERT"        : [(3.0,  "🔴"), (8.0, "🟡"), (1e9, "🟢")],
    "MORTGAGE30US"   : [(6.0,  "🟢"), (7.0, "🟡"), (1e9, "🔴")],
    "MORTGAGE15US"   : [(5.5,  "🟢"), (6.5, "🟡"), (1e9, "🔴")],
    "MSPNHSUS"        : [(550, "🔴"), (700, "🟡"), (1e9, "🟢")],
    "RECPROUSM156N"  : [(10,   "🟢"), (30,  "🟡"), (1e9, "🔴")],
    "SHILLER_CAPE"   : [(20,   "🟢"), (30,  "🟡"), (1e9, "🔴")],
    "AAII_BEAR"      : [(20,   "🟢"), (40,  "🟡"), (1e9, "🔴")],
    "AAII_SPREAD"    : [(-10,  "🔴"), (10,  "🟡"), (1e9, "🟢")],
    "SPREAD_2_10"    : [(0,    "🔴"), (0.5, "🟡"), (1e9, "🟢")],
}

INDICATOR_RANGES = {
    "CPIAUCSL"       : (0, 10),
    "CPILFESL"       : (0, 8),
    "PCEPILFE"       : (0, 6),
    "T10YIE"         : (1, 4.5),
    "UNRATE"         : (3, 12),
    "U6RATE"         : (6, 18),
    "CIVPART"        : (60, 68),
    "ICSA"           : (150, 700),
    "GDPNOW"         : (-5, 7),
    "A191RL1Q225SBEA": (-5, 7),
    "INDPRO"         : (-20, 10),
    "WEI"            : (-3, 3),
    "USSLIND"        : (-2.5, 2),
    "DFF"            : (0, 6),
    "DFEDTARU"       : (0, 6),
    "DFEDTARL"       : (0, 6),
    "WALCL"          : (4000, 9000),
    "BAMLH0A0HYM2"   : (200, 1500),
    "BAMLC0A0CM"     : (50, 400),
    "NFCI"           : (-1.5, 2.5),
    "STLFSI2"        : (-2.0, 3.0),
    "T10Y3M"         : (-2.5, 3.0),
    "T10Y2Y"         : (-2.0, 3.0),
    "T30Y2Y"         : (-2.0, 3.0),
    "SOFR"           : (0, 7),
    "TEDRATE"        : (0, 2.0),
    "DRTSCILM"       : (-30, 80),
    "WRMFNS"         : (3000, 9000),
    "WRMFSL"         : (1000, 5000),
    "UMCSENT"        : (50, 110),
    "PSAVERT"        : (2, 20),
    "SAHMREALTIME"   : (0, 1.5),
    "MORTGAGE30US"   : (3, 9),
    "MORTGAGE15US"   : (2.5, 8),
    "CFNAI"          : (-5, 3),
    "RECPROUSM156N"  : (0, 100),
    "SHILLER_CAPE"   : (10, 45),
    "AAII_BULL"      : (15, 60),
    "AAII_BEAR"      : (10, 55),
    "AAII_SPREAD"    : (-35, 35),
    "SPREAD_2_10"    : (-2, 2),
    "HOUST"          : (800, 1800),
    "PERMIT"         : (800, 1800),
    "CSUSHPINSA"     : (-15, 25),
    "MSPNHSUS"       : (400, 1200),
    "TOTALSL"        : (3000, 5200),
    "JTSJOL"         : (3000, 12000),
    "ECBDFR"         : (-1, 5),
    "BOERUKM"        : (0, 6),
    "IRSTCI01JPM156N": (-0.5, 1.5),
}

# ── DATA-FETCHING FUNCTIONS (all wrapped with @st.cache_data) ─────────────────

@st.cache_data(ttl="1h")
def fetch_fred():
    _FRED_ERRORS.clear()
    pct_series = {"CPIAUCSL","CPILFESL","PCEPILFE","INDPRO","CES0500000003",
                  "RSXFS","DSPIC96","CSUSHPINSA","TOTALSL"}
    results = {}

    def _infer_periods_per_year(dates: pd.Series) -> int:
        try:
            diffs = dates.sort_values().diff().dropna()
            if diffs.empty:
                return 12
            median_days = diffs.dt.total_seconds().median() / 86400.0
            if median_days <= 2:
                return 365
            if median_days <= 10:
                return 52
            if median_days <= 40:
                return 12
            if median_days <= 110:
                return 4
            return 1
        except Exception:
            return 12

    def _fredgraph_req(series_id, units="lin", limit=5, record_error=True):
        if limit <= 6:
            lookback_years = 2
        elif limit <= 16:
            lookback_years = 5
        elif limit <= 52:
            lookback_years = 8
        else:
            lookback_years = 12
        cosd = (datetime.date.today() - datetime.timedelta(days=365 * lookback_years)).isoformat()
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={cosd}"
        last_error = None
        for attempt, timeout in enumerate((12, 20, 30), start=1):
            try:
                csv_text = _http_get_text(url, timeout=timeout)
                df = pd.read_csv(io.StringIO(csv_text))
                if df.empty or "DATE" not in df.columns or "VALUE" not in df.columns:
                    return []
                df = df[df["VALUE"].astype(str) != "."].copy()
                df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
                df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
                df = df.dropna(subset=["DATE", "VALUE"]).sort_values("DATE")
                if df.empty:
                    return []

                if units == "pc1":
                    periods = _infer_periods_per_year(df["DATE"])
                    df["VALUE"] = df["VALUE"].pct_change(periods=periods) * 100.0
                    df = df.dropna(subset=["VALUE"])
                    if df.empty:
                        return []

                df = df.tail(limit).sort_values("DATE", ascending=False)
                _FRED_ERRORS.pop(series_id, None)
                return [
                    {"date": d.strftime("%Y-%m-%d"), "value": str(v)}
                    for d, v in zip(df["DATE"].tolist(), df["VALUE"].tolist())
                ]
            except Exception as e:
                last_error = e
                if attempt < 3:
                    time.sleep(0.35 * attempt)

        if record_error:
            _FRED_ERRORS[series_id] = f"FREDGraph {type(last_error).__name__}: {last_error}"
        return []

    def _fred_req(series_id, units="lin", limit=5, record_error=True):
        if not FRED_API_KEY:
            return _fredgraph_req(series_id, units=units, limit=limit, record_error=record_error)

        url = (f"https://api.stlouisfed.org/fred/series/observations"
               f"?series_id={series_id}&api_key={FRED_API_KEY}"
               f"&file_type=json&sort_order=desc&limit={limit}&units={units}")
        last_error = None
        for attempt, timeout in enumerate((12, 20, 30), start=1):
            try:
                data = _http_get_json(url, timeout=timeout)
                obs = [o for o in data.get("observations", []) if o.get("value") not in (None, ".")]
                if obs:
                    _FRED_ERRORS.pop(series_id, None)
                    return obs
                last_error = RuntimeError(data.get("error_message", "No observations returned"))
            except Exception as e:
                last_error = e
                response_text = ""
                try:
                    response_text = getattr(getattr(e, "response", None), "text", "") or ""
                except Exception:
                    response_text = ""
                err_text = f"{type(e).__name__}: {e} {response_text}".lower()
                if "series does not exist" in err_text:
                    if record_error:
                        _FRED_ERRORS[series_id] = "Invalid FRED series ID: series does not exist"
                    return []
            if attempt < 3:
                time.sleep(0.35 * attempt)

        if last_error is not None and record_error:
            _FRED_ERRORS[series_id] = f"{type(last_error).__name__}: {last_error}"

        # Fallback that doesn't require an API key
        return _fredgraph_req(series_id, units=units, limit=limit, record_error=record_error)

    def _fred_hist(series_id, units="lin", limit=16, record_error=False):
        obs = _fred_req(series_id, units, limit, record_error=record_error)
        rows = []
        for o in obs:
            if o["value"] == ".":
                continue
            value = float(o["value"])
            if series_id in {"BAMLH0A0HYM2", "BAMLC0A0CM"} and units == "lin":
                value *= 100.0
            rows.append((value, o["date"][:7]))
        return rows

    def _get(sid):
        units = "pc1" if sid in pct_series else "lin"
        obs = _fred_req(sid, units, 5)
        if obs:
            try:
                v = float(obs[0]["value"])
                if sid in {"BAMLH0A0HYM2", "BAMLC0A0CM"} and units == "lin":
                    v *= 100.0
                lbl, cat, unit = FRED_SERIES[sid]
                return sid, {"value":v,"date":obs[0]["date"],"label":lbl,"category":cat,
                             "unit":unit,"source_tag":"FRED","period":obs[0]["date"][:7],"quality":"release"}
            except Exception:
                pass
        return sid, None

    max_workers = 2 if FRED_API_KEY else 1
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sid, res in ex.map(_get, FRED_SERIES.keys()):
            if res: results[sid] = res

    # Cleanup pass: retry missing series sequentially so a burst of timeouts does not blank large sections.
    priority_series = ["A191RL1Q225SBEA", "CPIAUCSL", "UNRATE", "DFF", "RECPROUSM156N"]
    remaining_series = [sid for sid in FRED_SERIES if sid not in priority_series]
    retry_series = priority_series + remaining_series
    for sid in retry_series:
        if sid in results:
            continue
        units = "pc1" if sid in pct_series else "lin"
        obs = _fred_req(sid, units, 5)
        if not obs:
            continue
        try:
            v = float(obs[0]["value"])
            if sid in {"BAMLH0A0HYM2", "BAMLC0A0CM"} and units == "lin":
                v *= 100.0
            lbl, cat, unit = FRED_SERIES[sid]
            results[sid] = {
                "value": v,
                "date": obs[0]["date"],
                "label": lbl,
                "category": cat,
                "unit": unit,
                "source_tag": "FRED",
                "period": obs[0]["date"][:7],
                "quality": "release",
            }
        except Exception:
            pass

    # GDPNow official workbook
    try:
        raw = _http_get(
            "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/cqer/researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx",
            timeout=20,
        )
        gdp_book = pd.read_excel(io.BytesIO(raw), sheet_name="CurrentQtrEvolution")
        points = []
        for idx in ("", ".1", ".2"):
            date_col = f"Date{idx}"
            gdp_col = f"GDP*{idx}"
            if date_col not in gdp_book.columns or gdp_col not in gdp_book.columns:
                continue
            block = gdp_book[[date_col, gdp_col]].copy()
            block.columns = ["date", "value"]
            block["date"] = pd.to_datetime(block["date"], errors="coerce")
            block["value"] = pd.to_numeric(block["value"], errors="coerce")
            block = block.dropna(subset=["date", "value"])
            if not block.empty:
                points.append(block)
        if points:
            gdp_df = pd.concat(points, ignore_index=True).sort_values("date")
            latest = gdp_df.iloc[-1]
            gdp_date = latest["date"].strftime("%Y-%m-%d")
            results["GDPNOW"] = {"value":float(latest["value"]),"date":gdp_date,
                                  "label":"GDPNow (Atlanta Fed)","category":"Growth","unit":"%",
                                  "source_tag":"Atlanta Fed","period":gdp_date[:7],"quality":"nowcast"}
    except Exception:
        pass
    if "GDPNOW" not in results:
        obs = _fred_req("GDPNOW","lin",5)
        if obs:
            results["GDPNOW"] = {"value":float(obs[0]["value"]),"date":obs[0]["date"],
                                  "label":"GDPNow (Atlanta Fed)","category":"Growth","unit":"%",
                                  "source_tag":"FRED","period":obs[0]["date"][:7],"quality":"release"}

    # Mortgage spread
    m30 = results.get("MORTGAGE30US",{}).get("value")
    m15 = results.get("MORTGAGE15US",{}).get("value")
    if m30 and m15:
        results["MTG_SPREAD"] = {"value":round((m30-m15)*100,1),"date":str(datetime.date.today()),
                                  "label":"30yr vs 15yr Spread","category":"Housing","unit":"bp",
                                  "source_tag":"Computed","period":str(datetime.date.today())[:7]}

    d30 = results.get("DGS30", {}).get("value")
    d2 = results.get("DGS2", {}).get("value")
    if d30 is not None and d2 is not None:
        results["T30Y2Y"] = {
            "value": round(float(d30) - float(d2), 3),
            "date": str(datetime.date.today()),
            "label": "30Y-2Y Treasury Slope",
            "category": "Rates",
            "unit": "%",
            "source_tag": "Computed from DGS30-DGS2",
            "period": str(datetime.date.today())[:7],
            "quality": "computed",
        }
        _FRED_ERRORS.pop("T30Y2Y", None)

    def _mark_stale(series_id, max_age_days, null_value=True):
        entry = results.get(series_id)
        if not entry or not entry.get("date"):
            return
        try:
            dt = pd.to_datetime(entry["date"], errors="coerce")
            if pd.isna(dt):
                return
            age_days = int((pd.Timestamp(datetime.date.today()) - dt.normalize()).days)
            entry["age_days"] = age_days
            if age_days > max_age_days:
                entry["quality"] = "stale"
                entry["stale"] = True
                entry["last_value"] = entry.get("value")
                entry["source_tag"] = f"{entry.get('source_tag', 'FRED')} (stale)"
                if null_value:
                    entry["value"] = None
                _FRED_ERRORS[series_id] = f"Series stale: latest official observation {entry['date']} ({age_days}d old)"
        except Exception:
            return

    for stale_sid in ("USSLIND", "TEDRATE", "STLFSI2", "WRMFSL", "WIMFSL", "WIMFNS"):
        _mark_stale(stale_sid, 60, null_value=True)

    # Historical series used by Phillips Curve and regime state modules
    results["CPI_HIST"]    = _fred_hist("CPIAUCSL", "pc1", 90, record_error=False)
    results["SPREAD_HIST"] = _fred_hist("BAMLC0A0CM", "lin", 90, record_error=False)
    results["UNRATE_HIST"] = _fred_hist("UNRATE",   "lin", 36, record_error=False)
    results["T10Y3M_HIST"] = _fred_hist("T10Y3M",   "lin", 90, record_error=False)
    results["T10Y2Y_HIST"] = _fred_hist("T10Y2Y",   "lin", 90, record_error=False)
    results["T30Y2Y_HIST"] = _fred_hist("T30Y2Y",   "lin", 90, record_error=False)
    results["NFCI_HIST"]   = _fred_hist("NFCI",     "lin", 90, record_error=False)
    results["STLFSI2_HIST"] = _fred_hist("STLFSI2", "lin", 90, record_error=False)
    results["TEDRATE_HIST"] = _fred_hist("TEDRATE", "lin", 90, record_error=False)
    results["DFF_HIST"] = _fred_hist("DFF", "lin", 90, record_error=False)
    results["DGS2_HIST"] = _fred_hist("DGS2", "lin", 90, record_error=False)
    results["DGS10_HIST"] = _fred_hist("DGS10", "lin", 90, record_error=False)
    results["DGS30_HIST"] = _fred_hist("DGS30", "lin", 90, record_error=False)
    try:
        d2_hist = {date: value for value, date in results.get("DGS2_HIST", [])}
        d30_hist = {date: value for value, date in results.get("DGS30_HIST", [])}
        common_dates = [date for date in d30_hist.keys() if date in d2_hist]
        results["T30Y2Y_HIST"] = [
            (round(float(d30_hist[date]) - float(d2_hist[date]), 3), date)
            for date in common_dates[:90]
        ]
    except Exception:
        pass
    results["HY_SPREAD_HIST"] = _fred_hist("BAMLH0A0HYM2", "lin", 90, record_error=False)
    results["IG_SPREAD_HIST"] = _fred_hist("BAMLC0A0CM", "lin", 90, record_error=False)
    results["M2SL_HIST"] = _fred_hist("M2SL", "lin", 48, record_error=False)
    results["M2SL_YOY_HIST"] = _fred_hist("M2SL", "pc1", 36, record_error=False)
    results["PSAVERT_HIST"] = _fred_hist("PSAVERT", "lin", 36, record_error=False)
    results["UMCSENT_HIST"] = _fred_hist("UMCSENT", "lin", 36, record_error=False)
    results["SAHMREALTIME_HIST"] = _fred_hist("SAHMREALTIME", "lin", 36, record_error=False)
    results["PAYEMS_HIST"] = _fred_hist("PAYEMS", "lin", 36, record_error=False)
    results["GDP_HIST"] = _fred_hist("A191RL1Q225SBEA", "lin", 24, record_error=False)
    results["LEI_HIST"] = _fred_hist("USSLIND", "lin", 48, record_error=False)
    results["NAPM_HIST"] = _fred_hist("NAPM", "lin", 24, record_error=False)
    results["WRMFNS_HIST"] = _fred_hist("WRMFNS", "lin", 52, record_error=False)
    results["WRMFSL_HIST"] = _fred_hist("WRMFSL", "lin", 52, record_error=False)
    results["WIMFNS_HIST"] = _fred_hist("WIMFNS", "lin", 52, record_error=False)
    results["WIMFSL_HIST"] = _fred_hist("WIMFSL", "lin", 52, record_error=False)
    results["DTWEXBGS_HIST"] = _fred_hist("DTWEXBGS", "lin", 52, record_error=False)
    return results

@st.cache_data(ttl="1h")
def fetch_treasury():
    try:
        month_candidates = []
        today = datetime.date.today().replace(day=1)
        month_candidates.append(today.strftime("%Y%m"))
        prev_month = (today - datetime.timedelta(days=1)).replace(day=1)
        if prev_month.strftime("%Y%m") not in month_candidates:
            month_candidates.append(prev_month.strftime("%Y%m"))

        mapping = {
            "1 Mo": "1M",
            "3 Mo": "3M",
            "6 Mo": "6M",
            "1 Yr": "1Y",
            "2 Yr": "2Y",
            "3 Yr": "3Y",
            "5 Yr": "5Y",
            "7 Yr": "7Y",
            "10 Yr": "10Y",
            "20 Yr": "20Y",
            "30 Yr": "30Y",
        }

        for month_code in month_candidates:
            url = (
                "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                f"TextView?type=daily_treasury_yield_curve&field_tdr_date_value={month_code}"
            )
            html = _http_get_text(url, timeout=12)
            tables = pd.read_html(io.StringIO(html))
            if not tables:
                continue
            df = tables[0].copy()
            if "Date" not in df.columns:
                continue
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values("Date")
            if df.empty:
                continue
            latest = df.iloc[-1]
            date_s = latest["Date"].strftime("%Y-%m-%d")
            out = {}
            for col, tenor in mapping.items():
                if col not in latest.index:
                    continue
                value = pd.to_numeric(pd.Series([latest[col]]), errors="coerce").iloc[0]
                if pd.notna(value):
                    out[tenor] = {
                        "value": float(value),
                        "date": date_s,
                        "source_tag": "Treasury",
                        "period": date_s[:7],
                        "quality": "release",
                    }
            if out:
                return out
    except Exception:
        pass

    # Legacy fallback for environments where the HTML table changes.
    try:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/"
               "interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=all")
        xml = _http_get_text(url, timeout=12)
        entries = re.findall(r'<entry>(.*?)</entry>', xml, re.S)
        if not entries:
            return {}
        last = entries[-1]
        def yld(tag):
            m = re.search(rf'<d:{tag}[^>]*>([\d.]+)</d:{tag}>', last)
            return float(m.group(1)) if m else None
        date_m = re.search(r'<d:NEW_DATE[^>]*>([\d\-T:]+)', last)
        date_s = date_m.group(1)[:10] if date_m else "N/A"
        mapping = {"BC_1MONTH":"1M","BC_3MONTH":"3M","BC_6MONTH":"6M","BC_1YEAR":"1Y",
                   "BC_2YEAR":"2Y","BC_3YEAR":"3Y","BC_5YEAR":"5Y","BC_7YEAR":"7Y",
                   "BC_10YEAR":"10Y","BC_20YEAR":"20Y","BC_30YEAR":"30Y"}
        return {tenor: {"value":yld(tag),"date":date_s,"source_tag":"Treasury",
                        "period":date_s[:7],"quality":"legacy-xml"}
                for tag, tenor in mapping.items() if yld(tag) is not None}
    except Exception:
        return {}

@st.cache_data(ttl="2m")
def fetch_market():
    try:
        import yfinance as yf
        results = {}

        fresh_symbols = {
            "^GSPC", "^IXIC", "^DJI", "^RUT",
            "ES=F", "NQ=F", "YM=F", "RTY=F",
            "^VIX", "^VIX9D", "^VIX3M", "^VIX6M", "^VIX1Y", "^VVIX", "^GVZ", "^SKEW", "^MOVE",
            "SPY", "QQQ", "IWM", "TLT", "HYG", "LQD",
            "DX-Y.NYB", "BTC-USD", "GC=F", "SI=F", "CL=F",
        }

        def _fetch_one(sym):
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = getattr(info, "last_price", None)
                prev = getattr(info, "previous_close", None)

                intraday_series = pd.Series(dtype=float)
                daily_series = pd.Series(dtype=float)
                hist_time = None

                try:
                    intraday = ticker.history(period="5d", interval="1m", prepost=True)
                    if intraday is not None and not intraday.empty and "Close" in intraday.columns:
                        intraday_series = intraday["Close"].dropna()
                except Exception:
                    intraday_series = pd.Series(dtype=float)

                try:
                    daily = ticker.history(period="10d", interval="1d", prepost=False)
                    if daily is not None and not daily.empty and "Close" in daily.columns:
                        daily_series = daily["Close"].dropna()
                except Exception:
                    daily_series = pd.Series(dtype=float)

                hist_price = float(intraday_series.iloc[-1]) if not intraday_series.empty else None
                hist_time = intraday_series.index[-1] if not intraday_series.empty else None
                hist_prev = float(daily_series.iloc[-2]) if len(daily_series) >= 2 else None

                if hist_price is not None and (
                    price is None or
                    sym in fresh_symbols or
                    abs(float(hist_price) - float(price)) / max(abs(float(price)), 1.0) > 0.0005
                ):
                    price = hist_price

                if prev is None and hist_prev is not None:
                    prev = hist_prev

                chg_pct = round((float(price) - float(prev)) / float(prev) * 100, 2) if price is not None and prev not in (None, 0) else None
                return sym, {
                    "value": price,
                    "change_pct": chg_pct,
                    "prev_close": prev,
                    "last_time": str(hist_time) if hist_time is not None else None,
                    "source_tag": "Yahoo 1m" if hist_price is not None and price == hist_price else "Yahoo",
                }
            except Exception:
                return sym, None

        with ThreadPoolExecutor(max_workers=6) as ex:
            for sym, data in ex.map(_fetch_one, YF_TICKERS):
                if data:
                    results[sym] = data

        retry_symbols = [
            "SPY", "QQQ", "IWM", "TLT",
            "ES=F", "NQ=F", "YM=F", "RTY=F",
            "^VIX", "^VIX9D", "^VIX3M", "^VIX6M", "^VIX1Y", "^VVIX", "^SKEW", "^MOVE",
        ] + [sym for sym in YF_TICKERS if sym not in results]
        seen = set()
        for sym in retry_symbols:
            if sym in seen or sym in results or sym not in YF_TICKERS:
                continue
            seen.add(sym)
            _, data = _fetch_one(sym)
            if data:
                results[sym] = data

        for sym in ["SPY", "QQQ"]:
            if sym in results:
                continue
            try:
                ticker = yf.Ticker(sym)
                intraday = ticker.history(period="5d", interval="1m", prepost=True)
                daily = ticker.history(period="10d", interval="1d", prepost=False)
                close_1m = intraday["Close"].dropna() if intraday is not None and not intraday.empty and "Close" in intraday.columns else pd.Series(dtype=float)
                close_1d = daily["Close"].dropna() if daily is not None and not daily.empty and "Close" in daily.columns else pd.Series(dtype=float)
                if close_1m.empty:
                    continue
                price = float(close_1m.iloc[-1])
                prev = float(close_1d.iloc[-2]) if len(close_1d) >= 2 else None
                chg_pct = round((price - prev) / prev * 100, 2) if prev not in (None, 0) else None
                results[sym] = {
                    "value": price,
                    "change_pct": chg_pct,
                    "prev_close": prev,
                    "last_time": str(close_1m.index[-1]),
                    "source_tag": "Yahoo 1m",
                }
            except Exception:
                pass
        return results
    except ImportError:
        return {}


@st.cache_data(ttl="30m")
def fetch_yfinance_close_history(symbol, period="1y", interval="1d"):
    """Return yfinance close history as [{date, value}], silently failing to []."""
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period=period, interval=interval)
        if hist is None or hist.empty or "Close" not in hist.columns:
            return []
        close = hist["Close"].dropna()
        return [
            {"date": pd.Timestamp(d).strftime("%Y-%m-%d"), "value": float(v)}
            for d, v in close.items()
            if pd.notna(v)
        ]
    except Exception:
        return []


@st.cache_data(ttl="2m")
def fetch_premarket_snapshot():
    """
    Macro tape snapshot for the pre-open dashboard strip.
    Includes direct symbols plus ratio indicators built from live quotes.
    """
    try:
        import yfinance as yf
        base_map = {
            "ES=F": "E-Mini S&P",
            "DX-Y.NYB": "DXY",
            "GC=F": "Gold",
            "SI=F": "Silver",
            "HG=F": "Copper",
            "CL=F": "WTI Crude",
            "JPY=X": "USD/JPY",
        }

        def _fetch_one(sym, label):
            try:
                ticker = yf.Ticker(sym)
                hist = ticker.history(period="10d", interval="15m", prepost=True)
                if hist is None or hist.empty or "Close" not in hist.columns:
                    return sym, None
                close_series = hist["Close"].dropna()
                if close_series.empty:
                    return sym, None
                session_dates = list(pd.Index(pd.to_datetime(close_series.index).date).unique())
                if len(session_dates) > 5:
                    keep_dates = set(session_dates[-5:])
                    close_series = close_series[pd.Index(pd.to_datetime(close_series.index).date).isin(keep_dates)]
                chart_points = [
                    {"ts": ts.isoformat(), "value": round(float(v), 4)}
                    for ts, v in close_series.items()
                ]

                info = ticker.fast_info
                prev = getattr(info, "previous_close", None)
                daily = ticker.history(period="15d", interval="1d", prepost=False)
                daily_close = None
                sessions_5d = []
                if daily is not None and not daily.empty and "Close" in daily.columns:
                    daily_close = daily["Close"].dropna()
                    if prev is None and len(daily_close) >= 2:
                        prev = float(daily_close.iloc[-2])
                    if len(daily_close) >= 2:
                        recent_daily = daily_close.tail(6)
                        for i in range(1, len(recent_daily)):
                            cur = float(recent_daily.iloc[i])
                            prv = float(recent_daily.iloc[i - 1])
                            chg = round((cur - prv) / prv * 100, 2) if prv else None
                            sessions_5d.append({
                                "date": recent_daily.index[i].strftime("%Y-%m-%d"),
                                "close": round(cur, 4),
                                "change_pct": chg,
                            })
                        sessions_5d = sessions_5d[-5:]

                price = float(close_series.iloc[-1])
                last_ts = close_series.index[-1]
                chg_pct = round((price - prev) / prev * 100, 2) if prev not in (None, 0) else None

                return sym, {
                    "label": label,
                    "price": round(price, 4),
                    "prev_close": prev,
                    "change_pct": chg_pct,
                    "last_time": str(last_ts),
                    "history": [round(float(v), 4) for v in close_series.tail(78).tolist()],
                    "series": close_series.tail(78),
                    "chart_points": chart_points,
                    "daily_series": daily_close.tail(6) if daily_close is not None else None,
                    "sessions_5d": sessions_5d,
                }
            except Exception:
                return sym, None

        cards = {}
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = [ex.submit(_fetch_one, sym, label) for sym, label in base_map.items()]
            for fut in as_completed(futures):
                sym, data = fut.result()
                if data:
                    cards[sym] = data

        def _ratio_card(key, label, num_sym, den_sym):
            try:
                num = cards.get(num_sym)
                den = cards.get(den_sym)
                if not num or not den:
                    return None
                num_series = num.get("series")
                den_series = den.get("series")
                if num_series is None or den_series is None:
                    return None
                joined = (
                    pd.concat([num_series.rename("num"), den_series.rename("den")], axis=1)
                    .sort_index()
                    .ffill()
                    .dropna()
                )
                if joined.empty:
                    return None
                ratio_series = joined["num"] / joined["den"]
                ratio_dates = list(pd.Index(pd.to_datetime(ratio_series.index).date).unique())
                if len(ratio_dates) > 5:
                    keep_dates = set(ratio_dates[-5:])
                    ratio_series = ratio_series[pd.Index(pd.to_datetime(ratio_series.index).date).isin(keep_dates)]
                price = float(ratio_series.iloc[-1])
                prev_num = num.get("prev_close")
                prev_den = den.get("prev_close")
                prev = (float(prev_num) / float(prev_den)) if prev_num not in (None, 0) and prev_den not in (None, 0) else None
                chg_pct = round((price - prev) / prev * 100, 2) if prev not in (None, 0) else None
                chart_points = [
                    {"ts": ts.isoformat(), "value": round(float(v), 4)}
                    for ts, v in ratio_series.items()
                ]
                sessions_5d = []
                num_daily = num.get("daily_series")
                den_daily = den.get("daily_series")
                if num_daily is not None and den_daily is not None:
                    daily_joined = pd.concat([num_daily.rename("num"), den_daily.rename("den")], axis=1).dropna()
                    if len(daily_joined) >= 2:
                        ratio_daily = (daily_joined["num"] / daily_joined["den"]).tail(6)
                        for i in range(1, len(ratio_daily)):
                            cur = float(ratio_daily.iloc[i])
                            prv = float(ratio_daily.iloc[i - 1])
                            chg = round((cur - prv) / prv * 100, 2) if prv else None
                            sessions_5d.append({
                                "date": ratio_daily.index[i].strftime("%Y-%m-%d"),
                                "close": round(cur, 4),
                                "change_pct": chg,
                            })
                        sessions_5d = sessions_5d[-5:]
                return {
                    "label": label,
                    "price": round(price, 4),
                    "prev_close": prev,
                    "change_pct": chg_pct,
                    "last_time": num.get("last_time") or den.get("last_time"),
                    "history": [round(float(v), 4) for v in ratio_series.tail(78).tolist()],
                    "chart_points": chart_points,
                    "sessions_5d": sessions_5d,
                }
            except Exception:
                return None

        cards["ES_GC"] = _ratio_card("ES_GC", "ES/GC", "ES=F", "GC=F")
        cards["GC_SI"] = _ratio_card("GC_SI", "GC/SI", "GC=F", "SI=F")
        cards = {k: v for k, v in cards.items() if v}

        if not cards:
            return None

        return {
            "cards": cards,
            "source_tag": "Yahoo 5m",
        }
    except Exception:
        return None


@st.cache_data(ttl="2m")
def fetch_vix_term_structure():
    try:
        mkt = fetch_market()
        curve = [
            ("9D", "^VIX9D"),
            ("1M", "^VIX"),
            ("3M", "^VIX3M"),
            ("6M", "^VIX6M"),
            ("1Y", "^VIX1Y"),
        ]
        term = []
        for expiry, symbol in curve:
            iv = (mkt.get(symbol) or {}).get("value")
            if iv is not None:
                term.append({"expiry": expiry, "iv": float(iv)})
        if not term:
            return []
        back_iv = term[-1]["iv"]
        backwardation = any(item["iv"] > back_iv for item in term[:-1])
        for item in term:
            item["backwardation"] = backwardation
        return term
    except Exception:
        return []


@st.cache_data(ttl="5m")
def fetch_put_call_ratio_live():
    """
    Fetch current intraday put/call ratio from a public CBOE-derived table.

    Primary: Cboe's own public market statistics page.
    Fallback: PutCallRatio.org CBOE-derived tables.

    TradingView symbol USI:PCC is useful visually, but TradingView does not provide
    a stable public data API for dashboard ingestion.
    """
    try:
        import warnings

        def _fetch_text(url, timeout=12):
            try:
                return _http_get_text(url, timeout=timeout)
            except Exception:
                if not _USE_REQUESTS:
                    return ""
                try:
                    from urllib3.exceptions import InsecureRequestWarning
                    warnings.simplefilter("ignore", InsecureRequestWarning)
                except Exception:
                    pass
                r = _requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0"},
                    verify=False,
                )
                r.raise_for_status()
                return r.text

        def _normalize_pcr_table(df, label):
            df = df.copy()
            df.columns = [str(c).strip().lower().replace(" ", "_").replace("/", "_") for c in df.columns]
            ratio_col = next((c for c in df.columns if "p_c" in c or "ratio" in c), None)
            if ratio_col is None or "time" not in df.columns:
                return None
            df[ratio_col] = pd.to_numeric(df[ratio_col], errors="coerce")
            df = df.dropna(subset=[ratio_col])
            if df.empty:
                return None
            latest = df.iloc[-1]
            return {
                "label": label,
                "time": str(latest.get("time", "")),
                "calls": int(float(latest.get("calls", 0) or 0)),
                "puts": int(float(latest.get("puts", 0) or 0)),
                "total": int(float(latest.get("total", 0) or 0)),
                "pcr": round(float(latest[ratio_col]), 2),
                "intraday": [
                    {"time": str(r.get("time", "")), "pcr": round(float(r[ratio_col]), 2)}
                    for _, r in df.iterrows()
                    if pd.notna(r.get(ratio_col))
                ],
            }

        # Official Cboe market statistics. The page publishes Total, Index, and
        # Equity option tables with intraday P/C ratios.
        try:
            html = _fetch_text("https://www.cboe.com/us/options/market_statistics/market/", timeout=12)
            dfs = pd.read_html(io.StringIO(html))
            pcr_tables = []
            for df in dfs:
                cols = {str(c).strip().lower() for c in df.columns}
                if {"time", "calls", "puts", "total"}.issubset(cols) and any("p/c" in c or "ratio" in c for c in cols):
                    pcr_tables.append(df)
            if pcr_tables:
                total = _normalize_pcr_table(pcr_tables[0], "Total Options") if len(pcr_tables) >= 1 else None
                index = _normalize_pcr_table(pcr_tables[1], "Index Options") if len(pcr_tables) >= 2 else None
                equity = _normalize_pcr_table(pcr_tables[2], "Equity Options") if len(pcr_tables) >= 3 else None
                primary = total or equity or index
                if primary:
                    update_m = re.search(r"Data as of\s*([^.<]+)", html, re.I)
                    return {
                        "value": primary.get("pcr"),
                        "time": primary.get("time"),
                        "date": str(datetime.date.today()),
                        "last_update": update_m.group(1).strip() if update_m else None,
                        "source": "Cboe official market statistics intraday total options PCR",
                        "total_options": total,
                        "index_options": index,
                        "equity_options": equity,
                    }
        except Exception:
            pass

        def _parse_table(kind, label):
            html = _fetch_text(f"https://putcallratio.org/data/_data{kind}.html")
            dfs = pd.read_html(io.StringIO(html))
            if not dfs:
                return None
            df = dfs[0].copy()
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            ratio_col = next((c for c in df.columns if "ratio" in c), None)
            if ratio_col is None or "time" not in df.columns:
                return None
            df[ratio_col] = pd.to_numeric(df[ratio_col], errors="coerce")
            df = df.dropna(subset=[ratio_col])
            if df.empty:
                return None
            latest = df.iloc[-1]
            return {
                "label": label,
                "time": str(latest.get("time", "")),
                "calls": int(float(latest.get("calls", 0) or 0)),
                "puts": int(float(latest.get("puts", 0) or 0)),
                "total": int(float(latest.get("total", 0) or 0)),
                "pcr": round(float(latest[ratio_col]), 2),
                "intraday": [
                    {
                        "time": str(r.get("time", "")),
                        "pcr": round(float(r[ratio_col]), 2),
                    }
                    for _, r in df.iterrows()
                    if pd.notna(r.get(ratio_col))
                ],
            }

        total = _parse_table("total", "Total Options")
        index = _parse_table("index", "Index Options")
        equity = _parse_table("equity", "Equity Options")
        if not total and not index and not equity:
            return None

        last_update = None
        try:
            update_html = _fetch_text("https://putcallratio.org/data/_lastupdate.html")
            m = re.search(r"Last update:\s*([^<]+)", update_html, re.I)
            if m:
                last_update = m.group(1).strip()
        except Exception:
            pass

        primary = total or equity or index
        return {
            "value": primary.get("pcr"),
            "time": primary.get("time"),
            "date": str(datetime.date.today()),
            "last_update": last_update,
            "source": "PutCallRatio.org CBOE-derived intraday total options PCR",
            "total_options": total,
            "index_options": index,
            "equity_options": equity,
        }
    except Exception:
        return None


@st.cache_data(ttl="2m")
def fetch_options_indicators():
    out = {
        "pcr": None,
        "pcr_source": None,
        "pcr_date": None,
        "pcr_time": None,
        "pcr_detail": None,
        "skew_proxy": None,
        "vvix": None,
        "gvz": None,
        "backwardation": False,
    }
    try:
        mkt = fetch_market()
        vix = (mkt.get("^VIX") or {}).get("value")
        vix3m = (mkt.get("^VIX3M") or {}).get("value")
        vvix = (mkt.get("^VVIX") or {}).get("value")
        gvz = (mkt.get("^GVZ") or {}).get("value")
        if vix is not None and vix3m is not None:
            out["skew_proxy"] = round(float(vix3m) - float(vix), 2)
        if vvix is not None:
            out["vvix"] = float(vvix)
        if gvz is not None:
            out["gvz"] = float(gvz)
        term = fetch_vix_term_structure()
        if term:
            out["backwardation"] = bool(term[0].get("backwardation"))
    except Exception:
        pass

    try:
        live_pcr = fetch_put_call_ratio_live()
        if live_pcr and live_pcr.get("value") is not None:
            out["pcr"] = round(float(live_pcr["value"]), 2)
            out["pcr_source"] = live_pcr.get("source")
            out["pcr_date"] = live_pcr.get("date")
            out["pcr_time"] = live_pcr.get("time") or live_pcr.get("last_update")
            out["pcr_detail"] = live_pcr
    except Exception:
        pass

    try:
        import yfinance as yf
        if out.get("pcr") is None:
            spy = yf.Ticker("SPY")
            expiries = spy.options
            if expiries:
                chain = spy.option_chain(expiries[0])
                call_oi = float(chain.calls["openInterest"].fillna(0).sum())
                put_oi = float(chain.puts["openInterest"].fillna(0).sum())
                if call_oi > 0:
                    out["pcr"] = round(put_oi / call_oi, 2)
                    out["pcr_source"] = "Yahoo Finance SPY option-chain open interest fallback"
                    out["pcr_date"] = str(datetime.date.today())
    except Exception:
        pass

    return out


@st.cache_data(ttl="1h")
def fetch_skew_index():
    try:
        mkt = fetch_market()
        value = (mkt.get("^SKEW") or {}).get("value")
        if value is not None:
            return {"value": float(value), "date": str(datetime.date.today())}
    except Exception:
        pass
    return {}


@st.cache_data(ttl=3600)
def fetch_sofr_spread():
    """
    Fetch SOFR rate from NY Fed public API.
    Returns dict with value, date, spread_to_fed_funds.
    Falls back to FRED SOFR series if NY Fed unavailable.
    """
    def _latest_fred_obs(series_id):
        try:
            if FRED_API_KEY:
                url = (
                    "https://api.stlouisfed.org/fred/series/observations"
                    f"?series_id={series_id}&api_key={FRED_API_KEY}"
                    "&file_type=json&sort_order=desc&limit=3&units=lin"
                )
                data = _http_get_json(url, timeout=10)
                obs = [o for o in data.get("observations", []) if o.get("value") not in (None, ".")]
                if obs:
                    return obs[0]
        except Exception:
            pass
        try:
            cosd = (datetime.date.today() - datetime.timedelta(days=365 * 2)).isoformat()
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={cosd}"
            csv_text = _http_get_text(url, timeout=10)
            df = pd.read_csv(io.StringIO(csv_text))
            if df.empty or "DATE" not in df.columns or "VALUE" not in df.columns:
                return None
            df = df[df["VALUE"].astype(str) != "."].copy()
            df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
            df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
            df = df.dropna(subset=["DATE", "VALUE"]).sort_values("DATE", ascending=False)
            if df.empty:
                return None
            latest = df.iloc[0]
            return {"value": str(latest["VALUE"]), "date": latest["DATE"].strftime("%Y-%m-%d")}
        except Exception:
            return None

    try:
        url = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/5.json"
        data = _http_get_json(url, timeout=10)
        rates = data.get("refRates", [])
        latest = rates[0] if isinstance(rates, list) and rates else rates if isinstance(rates, dict) else None
        if latest:
            sofr_val = float(latest.get("percentRate", 0))
            sofr_date = latest.get("effectiveDate", str(datetime.date.today()))
            dff_obs = _latest_fred_obs("DFF")
            dff_val = float(dff_obs["value"]) if dff_obs and dff_obs.get("value") not in (None, ".") else None
            spread = round(sofr_val - dff_val, 3) if dff_val is not None else None
            return {
                "value": sofr_val,
                "date": sofr_date,
                "label": "SOFR Rate",
                "source_tag": "NY Fed",
                "quality": "release",
                "spread_to_fed_funds": spread,
            }
    except Exception:
        pass

    try:
        obs = _latest_fred_obs("SOFR")
        if obs:
            dff_obs = _latest_fred_obs("DFF")
            sofr_val = float(obs["value"])
            dff_val = float(dff_obs["value"]) if dff_obs and dff_obs.get("value") not in (None, ".") else None
            spread = round(sofr_val - dff_val, 3) if dff_val is not None else None
            return {
                "value": sofr_val,
                "date": obs["date"],
                "label": "SOFR Rate",
                "source_tag": "FRED",
                "quality": "release",
                "spread_to_fed_funds": spread,
            }
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def fetch_amihud_illiquidity(ticker="SPY", lookback=30):
    """
    Compute Amihud (2002) illiquidity ratio for a given ticker.
    Amihud = mean(|daily_return| / dollar_volume) * 1e6
    Higher = less liquid. Source: yfinance OHLCV.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{lookback + 5}d")
        if hist.empty or len(hist) < 5:
            return None
        hist = hist.tail(lookback).copy()
        hist["ret"] = hist["Close"].pct_change().abs()
        hist["dollar_vol"] = hist["Close"] * hist["Volume"]
        hist = hist.dropna(subset=["ret", "dollar_vol"])
        hist = hist[hist["dollar_vol"] > 0]
        if hist.empty:
            return None
        series = hist["ret"] / hist["dollar_vol"] * 1e9
        amihud = series.mean()
        return {
            "value": round(float(amihud), 4),
            "series": [
                {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 6)}
                for d, v in zip(hist.index, series)
            ],
            "ticker": ticker,
            "label": f"Amihud Illiquidity ({ticker})",
            "source_tag": "Yahoo",
        }
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_cot_data():
    """
    Fetch CFTC Commitment of Traders (COT) data for key markets.
    Uses CFTC public reporting Socrata API — no key required (CFTC app token improves rate limit).
    Markets: S&P 500 E-mini, 10Y Treasury, VIX, USD Index.
    Returns dict keyed by market name with net non-commercial and leveraged fund positions.
    """
    try:
        markets = {
            "SP500_Emini": {"cftc_code": "13874A", "label": "S&P 500 E-mini"},
            "Treasury_10Y": {"cftc_code": "043602", "label": "10Y T-Note"},
            "VIX_Futures": {"cftc_code": "1170E1", "label": "VIX Futures"},
            "USD_Index": {"cftc_code": "098662", "label": "USD Index"},
        }
        results = {}
        base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
        base_headers = {"User-Agent": "macro-dashboard/1.0"}
        auth_headers = dict(base_headers)
        if CFTC_APP_TOKEN:
            auth_headers["X-App-Token"] = CFTC_APP_TOKEN

        for key, meta in markets.items():
            try:
                url = (
                    f"{base}?cftc_contract_market_code={meta['cftc_code']}"
                    "&$order=report_date_as_yyyy_mm_dd DESC&$limit=12"
                )
                rows = None
                if _USE_REQUESTS:
                    for headers in (auth_headers, base_headers) if CFTC_APP_TOKEN else (base_headers,):
                        try:
                            r = _SESSION.get(url, timeout=15, headers=headers)
                            if r.status_code == 403 and headers.get("X-App-Token"):
                                continue
                            r.raise_for_status()
                            rows = r.json()
                            break
                        except Exception:
                            if headers.get("X-App-Token"):
                                continue
                            raise
                else:
                    for headers in (auth_headers, base_headers) if CFTC_APP_TOKEN else (base_headers,):
                        try:
                            req = urllib.request.Request(url, headers=headers)
                            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
                                rows = json.loads(r.read().decode("utf-8", errors="ignore"))
                            break
                        except urllib.error.HTTPError as e:
                            if e.code == 403 and headers.get("X-App-Token"):
                                continue
                            raise
                if not rows:
                    continue

                latest = rows[0]
                history = []
                for row in reversed(rows):
                    try:
                        net_nc = (
                            float(row.get("noncomm_positions_long_all", 0))
                            - float(row.get("noncomm_positions_short_all", 0))
                        )
                        net_lev = (
                            float(row.get("lev_money_positions_long_all", 0))
                            - float(row.get("lev_money_positions_short_all", 0))
                        )
                        date_str = row.get("report_date_as_yyyy_mm_dd", "")[:10]
                        history.append({"date": date_str, "net_nc": net_nc, "net_lev": net_lev})
                    except Exception:
                        continue

                results[key] = {
                    "label": meta["label"],
                    "net_nc": float(latest.get("noncomm_positions_long_all", 0)) - float(latest.get("noncomm_positions_short_all", 0)),
                    "net_lev": float(latest.get("lev_money_positions_long_all", 0)) - float(latest.get("lev_money_positions_short_all", 0)),
                    "date": latest.get("report_date_as_yyyy_mm_dd", "")[:10],
                    "history": history,
                    "open_interest": float(latest.get("open_interest_all", 0)),
                }
            except Exception:
                continue
        return results if results else None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_ici_fund_flows():
    """
    Fetch ICI weekly mutual fund flow estimates from the official public table.
    Returns equity and bond fund flows for the last 12 weekly observations.
    """
    try:
        html = _http_get_text("https://www.iciglobal.org/research/stats/flows", timeout=20)
        tables = pd.read_html(io.StringIO(html), flavor="lxml")
        for df in tables:
            if df.shape[0] < 5 or df.shape[1] < 3:
                continue
            labels = df.iloc[:, 0].astype(str).str.strip().str.lower()
            if not any(labels.str.contains("total equity")) or not any(labels.str.contains("total bond")):
                continue
            date_cols = []
            header_row = df.iloc[0]
            data_df = df.iloc[1:].copy()
            labels = data_df.iloc[:, 0].astype(str).str.strip().str.lower()
            for col in data_df.columns[1:]:
                dt = pd.to_datetime(str(header_row[col]), errors="coerce")
                if pd.notna(dt):
                    date_cols.append((col, dt))
            if not date_cols:
                continue

            def _row_value(pattern, col):
                try:
                    row = data_df[labels.str.contains(pattern, na=False)].iloc[0]
                    return float(pd.to_numeric(row[col], errors="coerce"))
                except Exception:
                    return None

            flows = []
            for col, dt in date_cols:
                flows.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "equity": _row_value(r"^total equity$", col),
                    "bond": _row_value(r"^total bond$", col),
                    "money_market": None,
                })
            flows = [row for row in flows if row.get("equity") is not None or row.get("bond") is not None]
            flows = sorted(flows, key=lambda row: row["date"])[-12:]
            if flows:
                latest = flows[-1]
                return {
                    "flows": flows,
                    "equity": latest.get("equity"),
                    "bond": latest.get("bond"),
                    "latest_equity": latest.get("equity"),
                    "latest_bond": latest.get("bond"),
                    "latest_money_market": latest.get("money_market"),
                    "date": latest.get("date"),
                    "source": "ICI official weekly flows table",
                }
        return None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_13f_aggregate(top_n=10):
    """
    Fetch aggregate institutional ownership data.
    Primary: Finnhub institutional ownership for SPY when key available.
    Fallback: SEC EDGAR recent 13F filing summary.
    """
    try:
        finnhub_key = get_api_key("FINNHUBAPIKEY") or get_api_key("FINNHUB_API_KEY") or FINNHUB_API_KEY
        if finnhub_key:
            try:
                url = f"https://finnhub.io/api/v1/stock/institutional-ownership?symbol=SPY&token={finnhub_key}"
                data = _http_get_json(url, timeout=12)
                ownership = data.get("ownership", []) or data.get("data", [])
                if ownership:
                    total_shares = sum(float(o.get("share", 0) or 0) for o in ownership[:top_n])
                    return {
                        "top_holders": [
                            {
                                "name": o.get("name", "Unknown"),
                                "shares": float(o.get("share", 0) or 0),
                                "change": float(o.get("change", 0) or 0),
                            }
                            for o in ownership[:top_n]
                        ],
                        "total_shares_top10": total_shares,
                        "date": data.get("symbol", "SPY"),
                        "source": "Finnhub 13F",
                    }
            except Exception:
                pass

        try:
            url = (
                "https://efts.sec.gov/LATEST/search-index?q=%2213F-HR%22"
                "&dateRange=custom&startdt=2024-01-01&forms=13F-HR"
                "&hits.hits._source=period_of_report,display_names"
                "&hits.hits.total.value=true&hits.hits.hits._source=period_of_report"
            )
            data = _http_get_json(url, timeout=12)
            hits = data.get("hits", {}).get("hits", [])
            total_filings = data.get("hits", {}).get("total", {}).get("value", 0)
            return {
                "total_filings": total_filings,
                "recent_sample": [h.get("_source", {}).get("display_names", "") for h in hits[:5]],
                "source": "SEC EDGAR",
                "note": f"{total_filings:,} total 13F filings on record",
            }
        except Exception:
            pass
        return None
    except Exception:
        return None


def fetch_mmf_assets_history(fred):
    """
    Build weekly money market fund flow series from FRED history.
    WRMFNS is the current retail weekly series.
    Institutional weekly series were discontinued in 2021 and are omitted when stale.
    """
    try:
        inst_hist = fred.get("WIMFNS_HIST", []) or fred.get("WIMFSL_HIST", [])
        ret_hist = fred.get("WRMFNS_HIST", []) or fred.get("WRMFSL_HIST", [])

        def build_flow_series(hist, max_age_days=None):
            if not hist or len(hist) < 2:
                return []
            df = pd.DataFrame(hist, columns=["value", "date"])
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna().sort_values("date").reset_index(drop=True)
            if df.empty:
                return []
            if max_age_days is not None:
                age_days = int((pd.Timestamp(datetime.date.today()) - df["date"].iloc[-1].normalize()).days)
                if age_days > max_age_days:
                    return []
            df["flow"] = df["value"].diff()
            return df.dropna(subset=["flow"]).to_dict("records")

        return {
            "institutional": build_flow_series(inst_hist, max_age_days=120),
            "retail": build_flow_series(ret_hist, max_age_days=120),
        }
    except Exception:
        return None


@st.cache_data(ttl=1800)
def fetch_vrp_and_realized_vol(lookback_days: int = 252 * 2):
    """
    Compute Volatility Risk Premium (VRP) = VIX − 20-day Realized Volatility of SPY.

    VRP > 0  → implied vol expensive vs realized (fear premium, market pricing in stress)
    VRP > 25 → historically extreme fear / hidden risk warning
    VRP < 0  → complacency (realized vol exceeds implied)
    VRP < -5 → realized vol spike, market moving faster than priced
    """
    try:
        import numpy as np

        spy_hist = fetch_yfinance_close_history("SPY", period="3y", interval="1d")
        vix_hist = fetch_yfinance_close_history("^VIX", period="3y", interval="1d")
        if len(spy_hist) < 60 or len(vix_hist) < 40:
            return None

        hist = pd.DataFrame(spy_hist)
        hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
        hist["Close"] = pd.to_numeric(hist["value"], errors="coerce")
        hist = hist.dropna(subset=["date", "Close"]).sort_values("date").set_index("date")[["Close"]]

        vix_df = pd.DataFrame(vix_hist)
        vix_df["date"] = pd.to_datetime(vix_df["date"], errors="coerce")
        vix_df["vix"] = pd.to_numeric(vix_df["value"], errors="coerce")
        vix_df = vix_df.dropna(subset=["date", "vix"]).sort_values("date").set_index("date")[["vix"]]

        log_ret = np.log(hist["Close"] / hist["Close"].shift(1))
        hist["rv20"] = log_ret.rolling(20).std() * np.sqrt(252) * 100
        hist["rv30"] = log_ret.rolling(30).std() * np.sqrt(252) * 100
        hist["rv60"] = log_ret.rolling(60).std() * np.sqrt(252) * 100
        hist = hist.dropna(subset=["rv20"])

        merged = hist.join(vix_df, how="inner").dropna()
        if len(merged) < 40:
            return None

        merged["vrp"] = merged["vix"] - merged["rv20"]
        merged["vrp30"] = merged["vix"] - merged["rv30"]
        merged = merged.tail(lookback_days)

        latest = merged.iloc[-1]
        current_vrp = round(float(latest["vrp"]), 2)
        current_rv20 = round(float(latest["rv20"]), 2)
        current_rv30 = round(float(latest["rv30"]), 2)
        current_rv60 = round(float(latest["rv60"]), 2)
        current_vix = round(float(latest["vix"]), 2)

        vrp_series = merged["vrp"].dropna()
        pct_rank = round(float((vrp_series <= current_vrp).sum() / len(vrp_series) * 100), 1)

        weekly = merged[["vix", "rv20", "vrp"]].resample("W").last().dropna().tail(104)
        history = [
            {
                "date": d.strftime("%Y-%m-%d"),
                "vix": round(float(r["vix"]), 2),
                "rv20": round(float(r["rv20"]), 2),
                "vrp": round(float(r["vrp"]), 2),
            }
            for d, r in weekly.iterrows()
        ]

        if current_vrp > 25:
            signal, signal_color = "🔴 Extreme Fear Premium", "#f87171"
        elif current_vrp > 10:
            signal, signal_color = "🟡 Elevated Fear Premium", "#fbbf24"
        elif current_vrp > 0:
            signal, signal_color = "🟢 Normal (IV > RV)", "#34d399"
        elif current_vrp > -5:
            signal, signal_color = "🟡 Slight Complacency", "#fbbf24"
        else:
            signal, signal_color = "🔴 Complacency / RV Spike", "#f87171"

        return {
            "vrp": current_vrp,
            "rv20": current_rv20,
            "rv30": current_rv30,
            "rv60": current_rv60,
            "vix": current_vix,
            "vrp_pct_rank": pct_rank,
            "signal": signal,
            "signal_color": signal_color,
            "history": history,
        }
    except Exception:
        return None


def compute_gs_panic_proxy(mkt, opts, skew_idx, pcr_hist):
    """
    Build Goldman Sachs Panic Index Proxy (0–10 scale).
    """
    try:
        import yfinance as yf

        components = {}

        try:
            vix_hist = yf.Ticker("^VIX").history(period="2y")[["Close"]].dropna()
            current_vix = (mkt.get("^VIX") or {}).get("value")
            if len(vix_hist) >= 40:
                if current_vix is None:
                    current_vix = float(vix_hist["Close"].iloc[-1])
                pct = float((vix_hist["Close"] <= float(current_vix)).sum() / len(vix_hist) * 100)
                components["vix_pct"] = round(pct, 1)
        except Exception:
            pass

        try:
            vvix_hist = yf.Ticker("^VVIX").history(period="2y")[["Close"]].dropna()
            current_vvix = (opts or {}).get("vvix")
            if len(vvix_hist) >= 40:
                if current_vvix is None:
                    current_vvix = float(vvix_hist["Close"].iloc[-1])
                pct = float((vvix_hist["Close"] <= float(current_vvix)).sum() / len(vvix_hist) * 100)
                components["vvix_pct"] = round(pct, 1)
        except Exception:
            pass

        try:
            skew_hist = yf.Ticker("^SKEW").history(period="2y")[["Close"]].dropna()
            current_skew = (skew_idx or {}).get("value")
            if len(skew_hist) >= 40:
                if current_skew is None:
                    current_skew = float(skew_hist["Close"].iloc[-1])
                pct = float((skew_hist["Close"] <= float(current_skew)).sum() / len(skew_hist) * 100)
                components["skew_pct"] = round(pct, 1)
        except Exception:
            pass

        try:
            if pcr_hist and len(pcr_hist) >= 10:
                pcr_values = [float(p["pcr"]) for p in pcr_hist if p.get("pcr") is not None]
                current_pcr = (opts or {}).get("pcr")
                if pcr_values:
                    if current_pcr is None:
                        current_pcr = pcr_values[-1]
                    pct = float(sum(v <= float(current_pcr) for v in pcr_values) / len(pcr_values) * 100)
                    components["pcr_pct"] = round(pct, 1)
        except Exception:
            pass

        if not components:
            return None

        avg_pct = sum(components.values()) / len(components)
        raw_score = round(avg_pct / 10, 2)

        if raw_score >= 9.0:
            label, color = "🔴 Institutional Panic", "#f87171"
        elif raw_score >= 7.0:
            label, color = "🟠 Elevated Fear", "#fbbf24"
        elif raw_score >= 4.0:
            label, color = "🟡 Neutral", "#fbbf24"
        else:
            label, color = "🟢 Complacency", "#34d399"

        return {
            "score": raw_score,
            "label": label,
            "color": color,
            "components": components,
            "n_components": len(components),
        }
    except Exception:
        return None


@st.cache_data(ttl=1800)
def fetch_cta_momentum_model():
    """
    Build a CTA positioning estimate using the standard 3-window momentum model.
    CTAs are purely price-momentum driven — their positions can be approximated by:
      signal = sign(price vs MA) weighted by inverse volatility
      windows: 20d (short), 63d (medium), 252d (long)

    Assets covered:
      SPY  — US equity exposure
      QQQ  — Tech/Nasdaq exposure
      TLT  — Treasury/bond exposure
      GLD  — Gold / safe-haven exposure
      DX-Y.NYB — USD Index exposure
      CL=F — Crude oil / commodity exposure
      IWM  — Small-cap risk exposure

    Returns dict with per-asset signals, composite CTA equity exposure score,
    and rolling history for charting.
    """
    try:
        import yfinance as yf
        import numpy as np

        assets = {
            "SPY": {"label": "US Equities (SPY)", "weight": 0.30},
            "QQQ": {"label": "Nasdaq (QQQ)", "weight": 0.20},
            "TLT": {"label": "Bonds (TLT)", "weight": 0.15},
            "GLD": {"label": "Gold (GLD)", "weight": 0.15},
            "DX-Y.NYB": {"label": "USD Index", "weight": 0.10},
            "CL=F": {"label": "Crude Oil", "weight": 0.05},
            "IWM": {"label": "Small-Cap (IWM)", "weight": 0.05},
        }

        short_w, short_days = 0.25, 20
        medium_w, medium_days = 0.50, 63
        long_w, long_days = 0.25, 252

        results = {}
        equity_signals = []
        equity_weights = []

        for ticker, meta in assets.items():
            try:
                hist = yf.Ticker(ticker).history(period="2y")
                if hist.empty or len(hist) < long_days + 5:
                    continue
                price = hist["Close"].dropna()
                if len(price) < long_days:
                    continue

                ma_short = price.rolling(short_days).mean()
                ma_medium = price.rolling(medium_days).mean()
                ma_long = price.rolling(long_days).mean()

                sig_short = np.where(price > ma_short, 1.0, -1.0)
                sig_medium = np.where(price > ma_medium, 1.0, -1.0)
                sig_long = np.where(price > ma_long, 1.0, -1.0)

                composite_signal = (
                    short_w * pd.Series(sig_short, index=price.index) +
                    medium_w * pd.Series(sig_medium, index=price.index) +
                    long_w * pd.Series(sig_long, index=price.index)
                )

                vol = price.pct_change().rolling(20).std() * (252 ** 0.5)
                vol = vol.clip(lower=0.05)
                scaled_signal = composite_signal / vol

                rolling_min = scaled_signal.rolling(252, min_periods=60).min()
                rolling_max = scaled_signal.rolling(252, min_periods=60).max()
                denom = (rolling_max - rolling_min).replace(0, np.nan)
                normalized = (scaled_signal - rolling_min) / denom * 2 - 1

                current_signal = float(composite_signal.iloc[-1])
                current_normalized = float(normalized.dropna().iloc[-1]) if not normalized.dropna().empty else 0.0
                current_price = float(price.iloc[-1])
                current_ma_short = float(ma_short.iloc[-1])
                current_ma_medium = float(ma_medium.iloc[-1])
                current_ma_long = float(ma_long.iloc[-1])
                current_vol = float(vol.iloc[-1])

                hist_weekly = normalized.resample("W").last().dropna().tail(52)
                history = [
                    {"date": d.strftime("%Y-%m-%d"), "signal": round(float(v), 3)}
                    for d, v in hist_weekly.items()
                ]

                results[ticker] = {
                    "label": meta["label"],
                    "weight": meta["weight"],
                    "signal": round(current_signal, 3),
                    "normalized": round(current_normalized, 3),
                    "price": round(current_price, 2),
                    "ma_short": round(current_ma_short, 2),
                    "ma_medium": round(current_ma_medium, 2),
                    "ma_long": round(current_ma_long, 2),
                    "vol_annual": round(current_vol * 100, 1),
                    "above_short": bool(current_price > current_ma_short),
                    "above_medium": bool(current_price > current_ma_medium),
                    "above_long": bool(current_price > current_ma_long),
                    "history": history,
                }

                if ticker in ("SPY", "QQQ", "IWM"):
                    equity_signals.append(current_normalized * meta["weight"])
                    equity_weights.append(meta["weight"])
            except Exception:
                continue

        if not results:
            return None

        total_eq_w = sum(equity_weights) or 1.0
        cta_equity_score = sum(equity_signals) / total_eq_w

        if cta_equity_score > 0.5:
            eq_label, eq_color = "🟢 CTA Long Bias", "#34d399"
        elif cta_equity_score > 0.1:
            eq_label, eq_color = "🟡 CTA Slight Long", "#fbbf24"
        elif cta_equity_score > -0.1:
            eq_label, eq_color = "⬜ CTA Neutral", "#94a3b8"
        elif cta_equity_score > -0.5:
            eq_label, eq_color = "🟠 CTA Slight Short", "#fbbf24"
        else:
            eq_label, eq_color = "🔴 CTA Short Bias", "#f87171"

        return {
            "assets": results,
            "equity_score": round(cta_equity_score, 3),
            "equity_label": eq_label,
            "equity_color": eq_color,
        }

    except Exception:
        return None


def fetch_sg_cta_index_performance():
    """
    Fetch SG CTA Index recent performance from BarclayHedge public portal.
    The SG CTA Index tracks the 20 largest CTAs — its momentum signals when
    CTAs are making/losing money (proxy for whether they are adding/reducing positions).

    Falls back to scraping public performance tables from nilssonhedge.com.
    Returns dict with latest monthly return and YTD, or None on failure.
    """
    try:
        url = (
            "https://portal.barclayhedge.com/cgi-bin/indices/displayHfIndex.cgi"
            "?indexCat=SG-Prime-Services-Indices&indexName=SG-CTA-Index"
        )
        html = _http_get_text(url, timeout=12)
        if html:
            months = re.findall(r"<td[^>]*>\s*([-\d.]+%)\s*</td>", html)
            if months and len(months) >= 2:
                def pct_to_float(s):
                    try:
                        return round(float(str(s).replace("%", "")), 2)
                    except Exception:
                        return None

                latest_month = pct_to_float(months[0])
                ytd = pct_to_float(months[1]) if len(months) > 1 else None

                if latest_month is not None:
                    return {
                        "latest_month_return": latest_month,
                        "ytd_return": ytd,
                        "source": "SG CTA Index via BarclayHedge",
                        "signal": "adding_positions" if latest_month > 0 else "reducing_positions",
                        "color": "#34d399" if latest_month > 0 else "#f87171",
                    }
    except Exception:
        pass

    try:
        url = "https://nilssonhedge.com/index/cta-index/systematic-cta-index/systematic-quant-cta-index/"
        html = _http_get_text(url, timeout=12)
        if html:
            m = re.search(r"([-\d.]+)\s*%.*?(?:YTD|return)", html, re.I | re.S)
            if m:
                ytd_val = round(float(m.group(1)), 2)
                return {
                    "latest_month_return": None,
                    "ytd_return": ytd_val,
                    "source": "NilssonHedge Systematic CTA Index",
                    "signal": "adding_positions" if ytd_val > 0 else "reducing_positions",
                    "color": "#34d399" if ytd_val > 0 else "#f87171",
                }
    except Exception:
        pass

    return None


@st.cache_data(ttl="5m")
def fetch_options_chain_data(ticker_sym="SPY"):
    """
    Fetch detailed options chain from yfinance for OI profile, IV smile, GEX,
    and multi-expiry structure views.
    Source: Yahoo Finance (yfinance) — ~15-min delayed, free, no API key needed.
    """
    try:
        import yfinance as yf, math

        ticker = yf.Ticker(ticker_sym)
        spot = getattr(ticker.fast_info, "last_price", None)
        if spot is None:
            hist = ticker.history(period="5d", interval="1d")
            if not hist.empty:
                spot = float(hist["Close"].dropna().iloc[-1])
        expiries = list(ticker.options or [])[:6]
        if not expiries or spot is None:
            return {}

        r = 0.05

        def _norm_pdf(x):
            return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

        def _norm_cdf(x):
            return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

        def _d1(S, K, T, r, sigma):
            if S <= 0 or K <= 0 or sigma <= 0 or T <= 0:
                return None
            return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))

        def _gamma(S, K, T, r, sigma):
            d1 = _d1(S, K, T, r, sigma)
            if d1 is None:
                return 0.0
            return _norm_pdf(d1) / (S * sigma * math.sqrt(T))

        def _delta(S, K, T, r, sigma, is_call=True):
            d1 = _d1(S, K, T, r, sigma)
            if d1 is None:
                return 0.0
            return _norm_cdf(d1) if is_call else (_norm_cdf(d1) - 1.0)

        all_expiry_data = []
        pcr_term = []
        atm_term = []
        heatmap_rows = []
        gex_by_expiry = []

        for idx, exp in enumerate(expiries):
            try:
                chain = ticker.option_chain(exp)
                calls = chain.calls.copy()
                puts = chain.puts.copy()
                calls = calls[calls["openInterest"].fillna(0) > 0]
                puts = puts[puts["openInterest"].fillna(0) > 0]
                if calls.empty and puts.empty:
                    continue

                expiry_dt = pd.Timestamp(exp)
                dte = max((expiry_dt.normalize() - pd.Timestamp.now().normalize()).days, 1)
                T = max(dte / 365.0, 1 / 365)

                calls["side"] = "call"
                puts["side"] = "put"
                full = pd.concat([calls, puts], ignore_index=True, sort=False)
                full["expiry"] = exp
                full["dte"] = dte
                full["moneyness"] = (full["strike"] / spot - 1.0) * 100.0

                def _calc_row(row):
                    K = float(row["strike"])
                    iv = float(row["impliedVolatility"]) if pd.notna(row["impliedVolatility"]) else 0.0
                    oi = float(row["openInterest"]) if pd.notna(row["openInterest"]) else 0.0
                    if iv <= 0 or oi <= 0:
                        return pd.Series({"gamma": 0.0, "delta": 0.0, "gex": 0.0, "delta_notional": 0.0})
                    is_call = row["side"] == "call"
                    gamma = _gamma(spot, K, T, r, iv)
                    delta = _delta(spot, K, T, r, iv, is_call=is_call)
                    gex = gamma * oi * 100 * spot ** 2 * 0.01
                    if not is_call:
                        gex = -gex
                    delta_notional = -delta * oi * 100 * spot
                    return pd.Series({
                        "gamma": gamma,
                        "delta": delta,
                        "gex": gex,
                        "delta_notional": delta_notional,
                    })

                full[["gamma", "delta", "gex", "delta_notional"]] = full.apply(_calc_row, axis=1)

                call_oi = float(calls["openInterest"].fillna(0).sum())
                put_oi = float(puts["openInterest"].fillna(0).sum())
                if call_oi > 0:
                    pcr_term.append({"expiry": exp, "pcr": round(put_oi / call_oi, 3), "dte": dte})

                near_full = full[(full["strike"] >= spot * 0.85) & (full["strike"] <= spot * 1.15)].copy()
                if not near_full.empty:
                    gex_by_expiry.append({
                        "expiry": exp,
                        "dte": dte,
                        "total_gex": round(float(near_full["gex"].sum()), 2),
                    })

                for _, r_heat in near_full.iterrows():
                    heatmap_rows.append({
                        "expiry": exp,
                        "dte": dte,
                        "strike": float(r_heat["strike"]),
                        "gex": float(r_heat["gex"]),
                    })

                front_atm = None
                if idx == 0:
                    front_atm = near_full.copy()
                else:
                    front_atm = full.copy()

                if not front_atm.empty:
                    atm_idx = (front_atm["strike"] - spot).abs().idxmin()
                    atm_row = front_atm.loc[atm_idx]
                    if pd.notna(atm_row.get("impliedVolatility")):
                        atm_term.append({
                            "expiry": exp,
                            "dte": dte,
                            "atm_iv": round(float(atm_row["impliedVolatility"]) * 100, 2),
                            "is_current": idx == 0,
                        })

                all_expiry_data.append({"expiry": exp, "dte": dte, "full": full})
            except Exception:
                continue

        if not all_expiry_data:
            return {}

        front = all_expiry_data[0]
        full = front["full"]
        calls = full[full["side"] == "call"].copy()
        puts = full[full["side"] == "put"].copy()

        call_oi = calls.groupby("strike")["openInterest"].sum().rename("call_oi")
        put_oi = puts.groupby("strike")["openInterest"].sum().rename("put_oi")
        call_iv = calls.groupby("strike")["impliedVolatility"].mean().rename("call_iv")
        put_iv = puts.groupby("strike")["impliedVolatility"].mean().rename("put_iv")
        gex_s = full.groupby("strike")["gex"].sum().rename("gex")
        delta_s = full.groupby("strike")["delta_notional"].sum().rename("delta_notional")
        oi_prof = pd.concat([call_oi, put_oi, call_iv, put_iv, gex_s, delta_s], axis=1).fillna(0).reset_index()
        oi_prof = oi_prof[
            (oi_prof["strike"] >= spot * 0.85) &
            (oi_prof["strike"] <= spot * 1.15)
        ].sort_values("strike")
        oi_prof["combined_oi"] = oi_prof["call_oi"] + oi_prof["put_oi"]
        oi_prof["pc_ratio"] = np.where(oi_prof["call_oi"] > 0, oi_prof["put_oi"] / oi_prof["call_oi"], np.nan)

        def _smile(df):
            d = df[
                (df["strike"] >= spot * 0.88) &
                (df["strike"] <= spot * 1.12) &
                df["impliedVolatility"].notna()
            ][["strike", "impliedVolatility", "delta"]].copy()
            d["moneyness"] = (d["strike"] / spot - 1.0) * 100.0
            return d.to_dict("records")

        calls_smile = _smile(calls)
        puts_smile = _smile(puts)

        gex_by_strike = oi_prof[["strike", "gex"]].copy()
        total_gex = float(gex_by_strike["gex"].sum())
        gex_list = gex_by_strike.to_dict("records")

        front_calls = calls[(calls["strike"] >= spot * 0.88) & (calls["strike"] <= spot * 1.12)].copy()
        front_puts = puts[(puts["strike"] >= spot * 0.88) & (puts["strike"] <= spot * 1.12)].copy()
        skew_25d = None
        try:
            if not front_calls.empty and not front_puts.empty:
                call_25 = front_calls.iloc[(front_calls["delta"] - 0.25).abs().argsort()[:1]]
                put_25 = front_puts.iloc[(front_puts["delta"] + 0.25).abs().argsort()[:1]]
                if not call_25.empty and not put_25.empty:
                    skew_25d = round(float(put_25["impliedVolatility"].iloc[0] - call_25["impliedVolatility"].iloc[0]) * 100, 2)
        except Exception:
            skew_25d = None

        max_pain = None
        pinning_curve = []
        try:
            strikes = oi_prof["strike"].tolist()
            pain_rows = []
            for settle in strikes:
                call_pain = ((np.maximum(settle - oi_prof["strike"], 0.0) * oi_prof["call_oi"]) * 100).sum()
                put_pain = ((np.maximum(oi_prof["strike"] - settle, 0.0) * oi_prof["put_oi"]) * 100).sum()
                total_pain = float(call_pain + put_pain)
                pain_rows.append({"strike": float(settle), "pain": total_pain})
            if pain_rows:
                pain_df = pd.DataFrame(pain_rows)
                max_pain = float(pain_df.loc[pain_df["pain"].idxmin(), "strike"])
                pain_min = float(pain_df["pain"].min())
                pain_max = float(pain_df["pain"].max())
                denom = pain_max - pain_min if pain_max != pain_min else 1.0
                pain_df["pinning_score"] = 1.0 - ((pain_df["pain"] - pain_min) / denom)
                pinning_curve = pain_df.to_dict("records")
        except Exception:
            max_pain = None
            pinning_curve = []

        pos_gex_strike = None
        neg_gex_strike = None
        call_wall = None
        put_wall = None
        try:
            call_wall = float(oi_prof.loc[oi_prof["call_oi"].idxmax(), "strike"])
        except Exception:
            pass
        try:
            put_wall = float(oi_prof.loc[oi_prof["put_oi"].idxmax(), "strike"])
        except Exception:
            pass
        try:
            pos_gex_strike = float(oi_prof.loc[oi_prof["gex"].idxmax(), "strike"])
        except Exception:
            pass
        try:
            neg_gex_strike = float(oi_prof.loc[oi_prof["gex"].idxmin(), "strike"])
        except Exception:
            pass

        key_candidates = []
        for label, strike in (
            ("max_pain", max_pain),
            ("negative_gex", neg_gex_strike),
            ("positive_gex", pos_gex_strike),
            ("call_wall", call_wall),
            ("put_wall", put_wall),
        ):
            if strike is not None and strike not in [k["strike"] for k in key_candidates]:
                key_candidates.append({"label": label, "strike": float(strike)})

        strike_palette = ["#3b82f6", "#f87171", "#f59e0b", "#34d399", "#a78bfa"]
        key_strikes = []
        for idx, row in enumerate(key_candidates[:5]):
            key_strikes.append({
                "label": row["label"],
                "strike": row["strike"],
                "color": strike_palette[idx],
            })

        return {
            "spot": spot,
            "expiry": front["expiry"],
            "oi_profile": oi_prof.to_dict("records"),
            "calls_smile": calls_smile,
            "puts_smile": puts_smile,
            "gex": gex_list,
            "total_gex": total_gex,
            "pcr_term": pcr_term,
            "atm_term": atm_term,
            "gex_heatmap": heatmap_rows,
            "gex_by_expiry": gex_by_expiry,
            "pc_ratio_by_strike": oi_prof[["strike", "pc_ratio"]].replace([np.inf, -np.inf], np.nan).dropna().to_dict("records"),
            "max_pain": max_pain,
            "pinning_curve": pinning_curve,
            "delta_flow": oi_prof[["strike", "delta_notional"]].to_dict("records"),
            "key_strikes": key_strikes,
            "skew_25d": skew_25d,
        }
    except Exception:
        return {}


@st.cache_data(ttl="1h")
def fetch_pcr_history():
    """
    Fetch 30-day historical Put/Call Ratio.
    Primary: official Cboe CSV endpoint.
    Fallback: current intraday table from fetch_put_call_ratio_live().
    """
    try:
        def _parse_cboe_csv(url):
            csv_text = _http_get_text(url, timeout=15)
            lines = [line for line in csv_text.splitlines() if line.strip()]
            header_idx = next((i for i, line in enumerate(lines) if line.upper().startswith("DATE,")), None)
            if header_idx is None:
                return []
            df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))
            date_col = next((c for c in df.columns if "date" in str(c).lower()), df.columns[0])
            ratio_col = next((c for c in df.columns if "ratio" in str(c).lower()), None)
            if ratio_col is None:
                return []
            df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
            df["_pcr"] = pd.to_numeric(df[ratio_col], errors="coerce")
            df = df.dropna(subset=["_date", "_pcr"]).sort_values("_date")
            if df.empty:
                return []
            latest_dt = df["_date"].iloc[-1]
            if int((pd.Timestamp(datetime.date.today()) - latest_dt.normalize()).days) > 14:
                return []
            df = df.tail(30)
            return [
                {"date": row["_date"].strftime("%Y-%m-%d"), "pcr": round(float(row["_pcr"]), 4)}
                for _, row in df.iterrows()
            ]

        rows = _parse_cboe_csv("https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv")
        if rows:
            return rows
        rows = _parse_cboe_csv("https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv")
        if rows:
            return rows
    except Exception:
        pass

    try:
        live = fetch_put_call_ratio_live() or {}
        for bucket in ("total_options", "equity_options", "index_options"):
            rows = (live.get(bucket) or {}).get("intraday") or []
            if rows:
                today = datetime.date.today().strftime("%Y-%m-%d")
                return [
                    {"date": f"{today} {row.get('time', '')}".strip(), "pcr": round(float(row["pcr"]), 4)}
                    for row in rows
                    if row.get("pcr") is not None
                ]
    except Exception:
        pass

    return []


@st.cache_data(ttl="5m")
def fetch_fear_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://edition.cnn.com/markets/fear-and-greed",
            "Origin": "https://edition.cnn.com",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if _USE_REQUESTS:
            r = _SESSION.get(url, timeout=10, headers=headers)
            r.raise_for_status()
            d = r.json()
        else:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
                d = json.loads(r.read().decode("utf-8", errors="ignore"))
        fg = d.get("fear_and_greed", {})
        score = fg.get("score")
        if score is not None:
            return {
                "value": int(round(float(score))),
                "label": str(fg.get("rating", "neutral")).replace("_", " ").title(),
                "source_tag": "CNN",
                "quality": "live",
                "timestamp": fg.get("timestamp"),
                "previous_close": fg.get("previous_close"),
                "previous_1_week": fg.get("previous_1_week"),
                "previous_1_month": fg.get("previous_1_month"),
                "previous_1_year": fg.get("previous_1_year"),
            }
    except Exception:
        pass

    # CNN page fallback
    try:
        html = _http_get_text("https://edition.cnn.com/markets/fear-and-greed", timeout=10)
        data_url_m = re.search(r'data-data-url="([^"]+fearandgreed[^"]+)"', html, re.I)
        if data_url_m and _USE_REQUESTS:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://edition.cnn.com/markets/fear-and-greed",
                "Origin": "https://edition.cnn.com",
            }
            r = _SESSION.get(data_url_m.group(1), timeout=10, headers=headers)
            if r.ok:
                d = r.json()
                fg = d.get("fear_and_greed", {})
                score = fg.get("score")
                if score is not None:
                    return {
                        "value": int(round(float(score))),
                        "label": str(fg.get("rating", "neutral")).replace("_", " ").title(),
                        "source_tag": "CNN",
                        "quality": "live",
                        "timestamp": fg.get("timestamp"),
                        "previous_close": fg.get("previous_close"),
                        "previous_1_week": fg.get("previous_1_week"),
                        "previous_1_month": fg.get("previous_1_month"),
                        "previous_1_year": fg.get("previous_1_year"),
                    }
        m = re.search(r'Fear & Greed Index.*?(Extreme Fear|Fear|Neutral|Greed|Extreme Greed)', html, re.I | re.S)
        if m:
            label = m.group(1).title()
            fallback_map = {
                "Extreme Fear": 10,
                "Fear": 30,
                "Neutral": 50,
                "Greed": 70,
                "Extreme Greed": 90,
            }
            return {
                "value": fallback_map.get(label, 50),
                "label": label,
                "source_tag": "CNN",
                "quality": "page-fallback",
            }
    except Exception:
        pass
    return {}

@st.cache_data(ttl="1h")
def fetch_bls():
    """
    Fetch Bureau of Labor Statistics data.

    Currently retrieves nonfarm payrolls (CES0000000001) and computes the month-over-month
    change (in thousands). If a BLS_API_KEY is available it is appended as a `registrationkey`
    parameter. Fallback gracefully if the API call fails.
    """
    try:
        base_url = "https://api.bls.gov/publicAPI/v2/timeseries/data/CES0000000001"
        current_year = datetime.date.today().year
        start_year = max(2019, current_year - 1)
        params = f"?startyear={start_year}&endyear={current_year}"
        if BLS_API_KEY:
            params += f"&registrationkey={BLS_API_KEY}"
        url = base_url + params
        d = _http_get_json(url, timeout=12)
        for series in d.get("Results", {}).get("series", []):
            data = series.get("data", [])
            if len(data) >= 2:
                latest = data[0]
                prev = data[1]
                try:
                    v = float(latest.get("value", 0)) - float(prev.get("value", 0))
                except Exception:
                    continue
                return {
                    "nonfarm_payrolls": {
                        "value": round(v, 0),
                        "date": f"{latest['year']}-{latest['period'].replace('M','')}",
                        "unit": "k",
                        "source_tag": "BLS",
                    }
                }
    except Exception:
        pass
    return {}

@st.cache_data(ttl="1h")
def fetch_naaim():
    try:
        html = _http_get_text("https://www.naaim.org/programs/naaim-exposure-index/", timeout=12)
        tables = re.findall(r'<table.*?</table>', html, re.S)
        for table in tables:
            rows = re.findall(r'<tr.*?</tr>', table, re.S)
            for row in rows[1:3]:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                if len(cells) < 2: continue
                date_str = re.sub(r'<[^>]+>','', cells[0]).strip()
                vals = []
                for cell in cells[1:]:
                    cell = re.sub(r'<[^>]+>','', cell).strip()
                    try:
                        v = float(cell)
                        if -200 <= v <= 300: vals.append(v); break
                    except (TypeError, ValueError): pass
                if vals:
                    return {"value":vals[-1],"date":date_str,"label":"NAAIM Exposure Index",
                            "source_tag":"NAAIM","period":date_str[:7],"quality":"release"}
    except Exception: pass
    return {}

@st.cache_data(ttl="1h")
def fetch_shiller_cape():
    today = str(datetime.date.today())

    def _parse_cape_value(html: str):
        for pattern in [
            r'Current Shiller PE Ratio is\s*([\d.]+)',
            r'id=["\']current["\'][^>]*>\s*([\d.]+)',
            r'data-current-value=["\']([\d.]+)',
            r'Shiller PE Ratio.*?<span[^>]*>([\d.]+)<',
            r'"shiller".*?([\d]{2}\.\d+)',
        ]:
            m = re.search(pattern, html, re.S | re.I)
            if m:
                try:
                    return float(m.group(1))
                except Exception:
                    return None
        return None

    try:
        html = _http_get_text("https://www.multpl.com/shiller-pe", timeout=12)
        v = _parse_cape_value(html)
        if v is not None:
            return {
                "value": v,
                "date": today,
                "label": "Shiller CAPE Ratio",
                "source_tag": "multpl",
                "period": today[:7],
                "quality": "live",
            }
    except Exception:
        pass

    # Fallback: parse the latest value from the historical table page
    try:
        html = _http_get_text("https://www.multpl.com/shiller-pe/table/by-month", timeout=12)
        m = re.search(
            r"<tr>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([\d.]+)</td>",
            html,
            re.S | re.I,
        )
        if m:
            v = float(m.group(2))
            return {
                "value": v,
                "date": today,
                "label": "Shiller CAPE Ratio",
                "source_tag": "multpl",
                "period": today[:7],
                "quality": "table",
            }
    except Exception:
        pass
    return {}

@st.cache_data(ttl="1h")
def fetch_aaii():
    try:
        html = _http_get_text("https://www.aaii.com/sentimentsurvey", timeout=15)
        bulls   = re.findall(r'Bullish.*?([\d]+\.[\d]+)%', html, re.S)
        bears   = re.findall(r'Bearish.*?([\d]+\.[\d]+)%', html, re.S)
        neutral = re.findall(r'Neutral.*?([\d]+\.[\d]+)%', html, re.S)
        if bulls and bears:
            bull_v = float(bulls[0]); bear_v = float(bears[0])
            neut_v = float(neutral[0]) if neutral else round(100-bull_v-bear_v,1)
            today  = str(datetime.date.today())
            return {"bull":bull_v,"bear":bear_v,"neutral":neut_v,
                    "spread":round(bull_v-bear_v,1),"date":today,
                    "source_tag":"AAII","quality":"live"}
    except Exception:
        pass

    # Official fallback: AAII publishes the weekly survey in its public Insights feed.
    try:
        xml = _http_get_text("https://insights.aaii.com/feed", timeout=15)
        items = re.findall(r"<item>(.*?)</item>", xml, re.S | re.I)
        for item in items:
            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", item, re.S | re.I)
            title = title_m.group(1).strip() if title_m else ""
            if "Sentiment Survey" not in title:
                continue

            content_m = re.search(
                r"<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>",
                item,
                re.S | re.I,
            )
            content = content_m.group(1) if content_m else item

            bull_m = re.search(
                r"Bullish sentiment, expectations that stock prices will rise over the next six months,.*?to\s+(\d+\.\d+)%",
                content,
                re.S | re.I,
            )
            neutral_m = re.search(
                r"Neutral sentiment, expectations that stock prices will stay essentially unchanged over the next six months,.*?to\s+(\d+\.\d+)%",
                content,
                re.S | re.I,
            )
            bear_m = re.search(
                r"Bearish sentiment, expectations that stock prices will fall over the next six months,.*?to\s+(\d+\.\d+)%",
                content,
                re.S | re.I,
            )
            if bull_m and neutral_m and bear_m:
                bull_v = float(bull_m.group(1))
                neut_v = float(neutral_m.group(1))
                bear_v = float(bear_m.group(1))
                pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S | re.I)
                pub_dt = None
                if pub_m:
                    try:
                        pub_dt = datetime.datetime.strptime(pub_m.group(1).strip(), "%a, %d %b %Y %H:%M:%S %Z")
                    except Exception:
                        pub_dt = None
                date_s = pub_dt.strftime("%Y-%m-%d") if pub_dt else today
                return {
                    "bull": bull_v,
                    "bear": bear_v,
                    "neutral": neut_v,
                    "spread": round(bull_v - bear_v, 1),
                    "date": date_s,
                    "source_tag": "AAII Insights",
                    "quality": "feed",
                }
    except Exception:
        pass
    return {}

@st.cache_data(ttl="5m")
def fetch_news():
    try:
        url = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
               f"&topics=economy_macro&sort=LATEST&limit=6&apikey={ALPHA_VANTAGE_KEY}")
        d = _http_get_json(url, timeout=12)
        out = []
        for it in d.get("feed",[])[:6]:
            score = float(it.get("overall_sentiment_score",0))
            out.append({"title":it.get("title",""),"url":it.get("url","#"),
                        "source":it.get("source",""),"time":it.get("time_published","")[:8],
                        "score":score,"sentiment":it.get("overall_sentiment_label","Neutral"),
                        "color":"#34d399" if score>0.1 else "#f87171" if score<-0.1 else "#fbbf24"})
        if out:
            return out
    except Exception:
        pass

    try:
        fallback = fetch_worldmonitor_news(
            per_category=3,
            category_keys=["finance", "us", "gov", "energy"],
        )
        flat = []
        seen = set()
        for key in ("finance", "us", "gov", "energy"):
            for item in fallback.get(key, []):
                dedupe_key = (item.get("title"), item.get("url"))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                flat.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", "#"),
                    "source": item.get("source", f"World Monitor · {item.get('category_label', key)}"),
                    "time": item.get("time", ""),
                    "score": 0.0,
                    "sentiment": item.get("category_label", key),
                    "color": "#3b82f6",
                })
        flat = sorted(flat, key=lambda row: row.get("time", ""), reverse=True)
        if flat:
            return flat[:6]
    except Exception:
        pass
    return []


WORLDMONITOR_NEWS_CATEGORY_LABELS = {
    "intel": "INTEL FEED",
    "thinktanks": "Think Tanks",
    "politics": "World News",
    "us": "United States",
    "gov": "Government",
    "finance": "Financial",
    "energy": "Energy & Resources",
    "asia": "Asia-Pacific",
    "ai": "AI/ML",
    "tech": "Technology",
}

WORLDMONITOR_NEWS_CATEGORY_ORDER = [
    "intel",
    "thinktanks",
    "politics",
    "us",
    "gov",
    "finance",
    "energy",
    "asia",
    "ai",
    "tech",
]

# Canonical feed inventory mirrored from worldmonitor-main feed configuration.
# This uses the same underlying feed map as the site for the requested sections.
WORLDMONITOR_NEWS_FEEDS = {
    "intel": [
        {"name": "Defense One", "url": "https://www.defenseone.com/rss/all/"},
        {"name": "The War Zone", "url": "https://www.twz.com/feed"},
        {"name": "Defense News", "url": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml"},
        {"name": "Military Times", "url": "https://www.militarytimes.com/arc/outboundfeeds/rss/?outputType=xml"},
        {"name": "Task & Purpose", "url": "https://taskandpurpose.com/feed/"},
        {"name": "USNI News", "url": "https://news.google.com/rss/search?q=site:news.usni.org+when:3d&hl=en-US&gl=US&ceid=US:en"},
        {"name": "gCaptain", "url": "https://gcaptain.com/feed/"},
        {"name": "Oryx OSINT", "url": "https://www.oryxspioenkop.com/feeds/posts/default?alt=rss"},
        {"name": "Foreign Policy", "url": "https://foreignpolicy.com/feed/"},
        {"name": "Foreign Affairs", "url": "https://www.foreignaffairs.com/rss.xml"},
        {"name": "Atlantic Council", "url": "https://www.atlanticcouncil.org/feed/"},
        {"name": "Bellingcat", "url": "https://news.google.com/rss/search?q=site:bellingcat.com&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Krebs Security", "url": "https://krebsonsecurity.com/feed/"},
        {"name": "Arms Control Assn", "url": "https://news.google.com/rss/search?q=site:armscontrol.org&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Bulletin of Atomic Scientists", "url": "https://news.google.com/rss/search?q=site:thebulletin.org&hl=en-US&gl=US&ceid=US:en"},
        {"name": "FAO News", "url": "https://www.fao.org/feeds/fao-newsroom-rss"},
    ],
    "thinktanks": [
        {"name": "Foreign Policy", "url": "https://foreignpolicy.com/feed/"},
        {"name": "Atlantic Council", "url": "https://www.atlanticcouncil.org/feed/"},
        {"name": "Foreign Affairs", "url": "https://www.foreignaffairs.com/rss.xml"},
        {"name": "War on the Rocks", "url": "https://warontherocks.com/feed"},
        {"name": "CSIS", "url": "https://www.csis.org/rss.xml"},
    ],
    "politics": [
        {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "Guardian World", "url": "https://www.theguardian.com/world/rss"},
        {"name": "AP News", "url": "https://news.google.com/rss/search?q=site:apnews.com&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Reuters World", "url": "https://news.google.com/rss/search?q=site:reuters.com+world&hl=en-US&gl=US&ceid=US:en"},
        {"name": "CNN World", "url": "https://news.google.com/rss/search?q=site:cnn.com+world+news+when:1d&hl=en-US&gl=US&ceid=US:en"},
    ],
    "us": [
        {"name": "Reuters US", "url": "https://news.google.com/rss/search?q=site:reuters.com+US&hl=en-US&gl=US&ceid=US:en"},
        {"name": "NPR News", "url": "https://feeds.npr.org/1001/rss.xml"},
        {"name": "PBS NewsHour", "url": "https://www.pbs.org/newshour/feeds/rss/headlines"},
        {"name": "ABC News", "url": "https://feeds.abcnews.com/abcnews/topstories"},
        {"name": "CBS News", "url": "https://www.cbsnews.com/latest/rss/main"},
        {"name": "NBC News", "url": "https://feeds.nbcnews.com/nbcnews/public/news"},
        {"name": "Wall Street Journal", "url": "https://feeds.content.dowjones.io/public/rss/RSSUSnews"},
        {"name": "Politico", "url": "https://rss.politico.com/politics-news.xml"},
        {"name": "The Hill", "url": "https://thehill.com/news/feed"},
        {"name": "Axios", "url": "https://api.axios.com/feed/"},
    ],
    "gov": [
        {"name": "White House", "url": "https://news.google.com/rss/search?q=site:whitehouse.gov&hl=en-US&gl=US&ceid=US:en"},
        {"name": "State Dept", "url": "https://news.google.com/rss/search?q=site:state.gov+OR+%22State+Department%22&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Pentagon", "url": "https://news.google.com/rss/search?q=site:defense.gov+OR+Pentagon&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Federal Reserve", "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
        {"name": "SEC", "url": "https://www.sec.gov/news/pressreleases.rss"},
        {"name": "UN News", "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml"},
        {"name": "CISA", "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml"},
        {"name": "Treasury", "url": "https://news.google.com/rss/search?q=site:treasury.gov&hl=en-US&gl=US&ceid=US:en"},
        {"name": "DOJ", "url": "https://news.google.com/rss/search?q=site:justice.gov&hl=en-US&gl=US&ceid=US:en"},
    ],
    "finance": [
        {"name": "CNBC", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
        {"name": "MarketWatch", "url": "https://news.google.com/rss/search?q=site:marketwatch.com+markets+when:1d&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
        {"name": "Financial Times", "url": "https://www.ft.com/rss/home"},
        {"name": "Reuters Business", "url": "https://news.google.com/rss/search?q=site:reuters.com+business+markets&hl=en-US&gl=US&ceid=US:en"},
    ],
    "energy": [
        {"name": "Oil & Gas", "url": "https://news.google.com/rss/search?q=(oil+price+OR+OPEC+OR+%22natural+gas%22+OR+pipeline+OR+LNG)+when:2d&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Reuters Energy", "url": "https://news.google.com/rss/search?q=site:reuters.com+energy+when:2d&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Nuclear Energy", "url": "https://news.google.com/rss/search?q=(%22nuclear+energy%22+OR+%22nuclear+power%22+OR+%22nuclear+reactor%22)+when:3d&hl=en-US&gl=US&ceid=US:en"},
    ],
    "asia": [
        {"name": "BBC Asia", "url": "https://feeds.bbci.co.uk/news/world/asia/rss.xml"},
        {"name": "The Diplomat", "url": "https://thediplomat.com/feed/"},
        {"name": "Nikkei Asia", "url": "https://news.google.com/rss/search?q=site:asia.nikkei.com+when:3d&hl=en-US&gl=US&ceid=US:en"},
        {"name": "CNA", "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"},
        {"name": "NDTV", "url": "https://feeds.feedburner.com/ndtvnews-top-stories"},
        {"name": "South China Morning Post", "url": "https://news.google.com/rss/search?q=site:scmp.com+when:2d&hl=en-US&gl=US&ceid=US:en"},
        {"name": "The Hindu", "url": "https://www.thehindu.com/feeder/default.rss"},
        {"name": "Asia News", "url": "https://news.google.com/rss/search?q=site:asianews.it+when:3d&hl=en-US&gl=US&ceid=US:en"},
    ],
    "ai": [
        {"name": "AI News", "url": "https://news.google.com/rss/search?q=(OpenAI+OR+Anthropic+OR+Google+AI+OR+%22large+language+model%22+OR+ChatGPT)+when:2d&hl=en-US&gl=US&ceid=US:en"},
        {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/"},
        {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
        {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
        {"name": "ArXiv AI", "url": "https://export.arxiv.org/rss/cs.AI"},
    ],
    "tech": [
        {"name": "Hacker News", "url": "https://hnrss.org/frontpage"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
    ],
}


def _extract_rss_tag(xml_block, tag):
    try:
        cdata = re.search(rf"<{tag}[^>]*>\s*<!\[CDATA\[(.*?)\]\]>\s*</{tag}>", xml_block, re.I | re.S)
        if cdata:
            return cdata.group(1).strip()
        plain = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml_block, re.I | re.S)
        if plain:
            text = re.sub(r"<[^>]+>", "", plain.group(1))
            return (
                text.replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&#39;", "'")
                .strip()
            )
    except Exception:
        return ""
    return ""


def _parse_worldmonitor_rss(xml_text, source_name, category_key, limit=4):
    try:
        blocks = re.findall(r"<item[\s>](.*?)</item>", xml_text, re.I | re.S)
        is_atom = not blocks
        if is_atom:
            blocks = re.findall(r"<entry[\s>](.*?)</entry>", xml_text, re.I | re.S)
        items = []
        for block in blocks:
            title = _extract_rss_tag(block, "title")
            if not title:
                continue
            if is_atom:
                m = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', block, re.I)
                link = m.group(1).strip() if m else ""
            else:
                link = _extract_rss_tag(block, "link")
            if not link.startswith("http"):
                continue
            pub_raw = (
                _extract_rss_tag(block, "pubDate")
                or _extract_rss_tag(block, "published")
                or _extract_rss_tag(block, "updated")
            )
            try:
                pub_dt = pd.to_datetime(pub_raw, utc=True, errors="coerce")
                time_str = pub_dt.strftime("%Y-%m-%d %H:%M") if pd.notna(pub_dt) else ""
                sort_ts = int(pub_dt.timestamp()) if pd.notna(pub_dt) else 0
            except Exception:
                time_str, sort_ts = "", 0
            items.append({
                "title": title,
                "url": link,
                "source": source_name,
                "time": time_str,
                "sort_ts": sort_ts,
                "category": category_key,
                "category_label": WORLDMONITOR_NEWS_CATEGORY_LABELS.get(category_key, category_key),
                "color": "#3b82f6",
            })
            if len(items) >= limit:
                break
        return items
    except Exception:
        return []


def _normalize_worldmonitor_digest_item(item, category_key):
    try:
        published_at = item.get("publishedAt")
        try:
            pub_dt = pd.to_datetime(published_at, unit="ms", utc=True, errors="coerce")
            if pd.isna(pub_dt):
                pub_dt = pd.to_datetime(published_at, utc=True, errors="coerce")
        except Exception:
            pub_dt = pd.NaT
        return {
            "title": item.get("title", ""),
            "url": item.get("link", "#"),
            "source": item.get("source", "World Monitor"),
            "time": pub_dt.strftime("%Y-%m-%d %H:%M") if pd.notna(pub_dt) else "",
            "sort_ts": int(pub_dt.timestamp()) if pd.notna(pub_dt) else 0,
            "category": category_key,
            "category_label": WORLDMONITOR_NEWS_CATEGORY_LABELS.get(category_key, category_key),
            "color": "#3b82f6",
        }
    except Exception:
        return None


@st.cache_data(ttl=1200)
def fetch_worldmonitor_news(per_category=8, category_keys=None):
    try:
        requested_keys = [
            key for key in (category_keys or WORLDMONITOR_NEWS_CATEGORY_ORDER)
            if key in WORLDMONITOR_NEWS_CATEGORY_LABELS
        ]

        # Primary path: fetch the same underlying feeds defined in worldmonitor-main.
        out = {key: [] for key in requested_keys}

        def _fetch_feed(category_key, feed):
            try:
                xml_text = _http_get_text(feed["url"], timeout=12)
                if not xml_text:
                    return category_key, []
                return category_key, _parse_worldmonitor_rss(
                    xml_text,
                    source_name=feed["name"],
                    category_key=category_key,
                    limit=4,
                )
            except Exception:
                return category_key, []

        futures = []
        with ThreadPoolExecutor(max_workers=10) as ex:
            for category_key in requested_keys:
                feeds = WORLDMONITOR_NEWS_FEEDS.get(category_key) or []
                for feed in feeds:
                    futures.append(ex.submit(_fetch_feed, category_key, feed))
            for fut in as_completed(futures):
                category_key, items = fut.result()
                if items:
                    out[category_key].extend(items)

        cleaned = {}
        for category_key, items in out.items():
            deduped = []
            seen = set()
            for item in sorted(items, key=lambda x: x.get("sort_ts", 0), reverse=True):
                sig = (item.get("title", "").strip().lower(), item.get("url", "").strip())
                if not sig[0] or sig in seen:
                    continue
                seen.add(sig)
                deduped.append(item)
                if len(deduped) >= per_category:
                    break
            if deduped:
                cleaned[category_key] = deduped

        if cleaned:
            return cleaned

        # Secondary path: public World Monitor digest endpoint. This is sometimes
        # Cloudflare-protected, so we only try it if direct feed harvesting fails.
        try:
            digest = _http_get_json(
                "https://www.worldmonitor.app/api/news/v1/list-feed-digest?variant=full&lang=en",
                timeout=20,
            )
            categories = (digest or {}).get("categories") or {}
            if categories:
                out = {}
                for key in requested_keys:
                    bucket = categories.get(key) or {}
                    items = []
                    for raw in (bucket.get("items") or [])[:per_category]:
                        normalized = _normalize_worldmonitor_digest_item(raw, key)
                        if normalized and normalized.get("title") and normalized.get("url"):
                            items.append(normalized)
                    if items:
                        out[key] = items
                if out:
                    return out
        except Exception:
            pass

        return {}
    except Exception:
        return {}


def render_worldmonitor_news_section(worldmonitor_news):
    st.subheader("🌐 World Monitor Headlines")
    st.caption(
        "Using the World Monitor feed inventory from the attached "
        "`worldmonitor-main` source. If the public World Monitor digest is blocked, "
        "this section pulls the same underlying RSS feeds directly."
    )

    if not worldmonitor_news:
        st.info(
            "World Monitor headlines are unavailable right now. "
            "This usually means the upstream feeds returned no items."
        )
        return

    ordered_keys = [
        key for key in WORLDMONITOR_NEWS_CATEGORY_ORDER
        if key in WORLDMONITOR_NEWS_CATEGORY_LABELS
    ]
    category_tabs = st.tabs([
        WORLDMONITOR_NEWS_CATEGORY_LABELS[key] for key in ordered_keys
    ])

    for tab, category_key in zip(category_tabs, ordered_keys):
        with tab:
            items = worldmonitor_news.get(category_key) or []
            if not items:
                st.markdown(
                    '<div style="background:#161b27;border:1px solid #fbbf24;'
                    'border-radius:10px;padding:12px 14px;color:#fbbf24;'
                    'font-size:13px">No headlines returned for this World Monitor '
                    'sector on the current refresh.</div>',
                    unsafe_allow_html=True,
                )
                continue

            for item in items:
                st.markdown(
                    f'<div style="background:#161b27;border-radius:10px;padding:14px 16px;'
                    f'margin-bottom:10px;border:1px solid #1e2d3d">'
                    f'<a href="{item.get("url", "#")}" target="_blank" rel="noopener noreferrer" '
                    f'style="color:#e2e8f0;font-weight:600;text-decoration:none;font-size:14px">'
                    f'{item.get("title", "Untitled headline")}</a><br>'
                    f'<span style="color:#64748b;font-size:11px">'
                    f'{item.get("source", "World Monitor")}  ·  '
                    f'{item.get("time", "time unavailable")}</span></div>',
                    unsafe_allow_html=True,
                )

# ── HELPERS ───────────────────────────────────────────────────────────────────
def _fmt(v, unit):
    if v is None: return "N/A"
    try: v = float(v)
    except: return "N/A"
    if unit=="%":   return f"{v:+.2f}%" if abs(v)<50 else f"{v:.2f}%"
    if unit=="bp":  return f"{v:.0f} bp"
    if unit=="idx": return f"{v:.2f}"
    if unit=="B":   return f"${v:,.0f}B"
    if unit=="$T":  return f"${v/1e3:.2f}T"
    if unit=="$B":  return f"${v/1e3:.1f}T" if v>1e6 else f"${v:.1f}B"
    if unit=="$":   return f"${v:,.0f}"
    if unit=="k":   return f"{v:,.0f}K"
    return f"{v:.2f}"

def _status_color(sid, v):
    if v is None or sid not in THRESHOLDS: return None
    try: v = float(v)
    except: return None
    for threshold, dot in THRESHOLDS[sid]:
        if v <= threshold:
            return "#34d399" if dot=="🟢" else "#f87171" if dot=="🔴" else "#fbbf24"
    return None


BEGINNER_LABEL_REPLACEMENTS = {
    "CAPE Ratio": "Stock Market Expensiveness (CAPE)",
    "Shiller CAPE Ratio": "Stock Market Expensiveness (CAPE)",
    "VIX": "Market Nervousness (VIX)",
    "PCR / Put-Call Ratio": "Investor Fear Gauge (PCR)",
    "Put/Call Ratio": "Investor Fear Gauge (PCR)",
    "Put/Call OI Ratio": "Investor Fear Gauge (PCR)",
    "PCR": "Investor Fear Gauge (PCR)",
    "GEX / Gamma Exposure": "Dealer Hedging Force (GEX)",
    "Gamma Exposure": "Dealer Hedging Force (GEX)",
    "GEX": "Dealer Hedging Force (GEX)",
    "VVIX": "Fear-of-Fear Index (VVIX)",
    "SKEW Index": "Crash Insurance Demand (SKEW)",
    "SKEW": "Crash Insurance Demand (SKEW)",
    "VRP / Vol Risk Premium": "Fear Premium (how much extra people pay for protection)",
    "Volatility Risk Premium": "Fear Premium (how much extra people pay for protection)",
    "VRP": "Fear Premium (how much extra people pay for protection)",
    "MOVE Index": "Bond Market Anxiety (MOVE)",
    "MOVE": "Bond Market Anxiety (MOVE)",
    "SOFR Rate": "Short-Term Borrowing Rate (SOFR)",
    "SOFR": "Short-Term Borrowing Rate (SOFR)",
    "TED Spread": "Bank Stress Indicator (TED Spread)",
    "HY Credit Spread": "Junk Bond Stress Level",
    "HY Spread": "Junk Bond Stress Level",
    "IG Credit Spread": "Corporate Bond Health",
    "NFCI": "Overall Financial Stress Index",
    "COT S&P Net Non-Comm": "Big Speculator Positioning (S&P Futures)",
    "S&P 500 Net Non-Comm": "Big Speculator Positioning (S&P Futures)",
    "ICI Equity Flow": "Mutual Fund Stock Inflows/Outflows",
    "ICI Equity Flows": "Mutual Fund Stock Inflows/Outflows",
    "MMF Assets": "Cash on the Sidelines",
    "Inst. MMF Assets": "Cash on the Sidelines (Institutional)",
    "Retail MMF Total": "Cash on the Sidelines (Retail)",
    "Inst. MMF Total": "Cash on the Sidelines (Institutional)",
    "AAII Bull/Bear Spread": "Retail Investor Mood (AAII Survey)",
    "AAII Sentiment": "Retail Investor Mood (AAII Survey)",
    "AAII Bearish %": "Retail Investor Mood (AAII Survey)",
    "NAAIM Exposure": "Professional Money Manager Exposure",
    "NAAIM": "Professional Money Manager Exposure",
    "GDPNow": "Real-Time Economy Growth Estimate",
    "GDP (GDPNow)": "Real-Time Economy Growth Estimate",
    "CPI Inflation": "Prices Rising Nationwide (CPI)",
    "CPI YoY": "Prices Rising Nationwide (CPI)",
    "Core PCE": "Fed's Preferred Inflation Measure",
    "Core PCE Inflation": "Fed's Preferred Inflation Measure",
    "Fed Funds Rate": "The Fed's Benchmark Interest Rate",
    "US Fed Funds Rate": "The Fed's Benchmark Interest Rate",
    "10Y-2Y Spread": "Yield Curve (recession predictor)",
    "Yield Curve Spread": "Yield Curve (recession predictor)",
    "DSPX / KCJ": "Stock Chaos vs. Macro Chaos Index",
    "Amihud Illiquidity": "How Hard It Is to Buy/Sell Stocks",
    "Participation Score": "How Invested Institutions Are",
    "Institutional Participation Score": "How Invested Institutions Are",
    "CTA Model Signal": "Trend-Following Fund Signal",
    "Model S&P Signal": "Trend-Following Fund Signal (S&P)",
    "Model QQQ Signal": "Trend-Following Fund Signal (Nasdaq)",
    "Model TLT Signal": "Trend-Following Fund Signal (Bonds)",
    "Phillips Curve": "Jobs vs. Inflation Trade-Off",
    "Macro Regime": "Current Economic Environment",
    "VIX Backwardation": "Near-Term Fear Spike Warning",
    "Backwardation": "Near-Term Fear Spike Warning",
    "Negative GEX": "Amplified Volatility Mode",
    "Positive GEX": "Stabilized Volatility Mode",
}

BEGINNER_REGIME_LABELS = {
    "Stagflation": "Economy: High Inflation + Slow Growth",
    "Goldilocks": "Economy: Stable Growth + Cooling Inflation",
    "Reflation": "Economy: Growth Rebounding + Inflation Rising",
    "Recession": "Economy: Contracting / High Recession Risk",
}

TAB_DISPLAY_LABELS = {
    "🏦 Macro Overview": "🏦 Economy Overview",
    "💼 Labor & Consumer": "💼 Jobs, Wages & Spending",
    "💱 Markets & Sentiment": "💱 Markets & Investor Mood",
    "Energy Futures": "🛢️ Energy Futures",
    "📉 Options & Derivatives": "📉 Options Risk & Market Protection",
    "🪙 Metals": "🪙 Metals & Commodities",
    "🏠 Housing & Credit": "🏠 Housing, Borrowing & Credit",
    "📊 Phillips Curve": "📊 Jobs vs. Inflation",
    "📰 News & Signals": "📰 News & What It Means",
    "Liquidity Conditions": "💧 Money & Credit Conditions",
    "Institutional Flows": "🏦 Big Money Flows",
    "Sentiment Framework": "😊 Investor Mood Framework",
    "GS-Style Composites": "🧮 Composite Risk Scores",
    "Global Macro": "🌍 Global Macro",
    "🤖 AI Macro Analysis": "🤖 AI Economic Analysis",
}

PLAIN_EXPLANATIONS = {
    "Market Nervousness (VIX)": "Like a stock market weather report. Above 30 usually means stormy markets with bigger daily swings.",
    "Stock Market Expensiveness (CAPE)": "Compares today's stock prices with 10 years of earnings. Higher readings mean stocks look expensive versus history.",
    "Investor Fear Gauge (PCR)": "Shows how much demand there is for downside protection versus upside bets. Higher readings mean investors are getting defensive.",
    "Dealer Hedging Force (GEX)": "Shows whether market makers are likely to calm price moves or accidentally make them bigger through hedging.",
    "Fear-of-Fear Index (VVIX)": "Measures how anxious traders are about future volatility itself. Higher means protection buying is getting urgent.",
    "Crash Insurance Demand (SKEW)": "Shows how much extra investors are paying for protection against a sudden market crash.",
    "Fear Premium (how much extra people pay for protection)": "Compares implied volatility with realized volatility. A big positive gap means investors are paying a high premium for protection.",
    "Bond Market Anxiety (MOVE)": "Tracks expected volatility in the bond market. High readings often spill over into stocks and credit.",
    "Short-Term Borrowing Rate (SOFR)": "A key short-term interest rate for the financial system. It reflects how expensive it is to borrow cash overnight.",
    "Bank Stress Indicator (TED Spread)": "Measures stress in bank-to-bank funding. Higher readings mean banks trust each other less and liquidity is getting tighter.",
    "Junk Bond Stress Level": "Shows the extra interest risky companies must pay to borrow. Wider spreads mean investors are demanding more caution.",
    "Corporate Bond Health": "Shows how healthy borrowing conditions are for stronger companies. Wider spreads mean financing is getting more expensive.",
    "Overall Financial Stress Index": "A broad measure of how tight or easy financial conditions are across markets.",
    "Retail Investor Mood (AAII Survey)": "A weekly survey of how optimistic or pessimistic individual investors feel about the stock market.",
    "Professional Money Manager Exposure": "Shows how aggressively active money managers are positioned in stocks.",
    "Real-Time Economy Growth Estimate": "A high-frequency estimate of how fast the U.S. economy is growing right now.",
    "Prices Rising Nationwide (CPI)": "Measures how quickly consumer prices are rising across the economy.",
    "Fed's Preferred Inflation Measure": "The inflation measure the Federal Reserve watches most closely when making rate decisions.",
    "The Fed's Benchmark Interest Rate": "The main short-term interest rate set by the Federal Reserve to cool down or stimulate the economy.",
    "Yield Curve (recession predictor)": "When short-term yields move above long-term yields, recessions have often followed within about a year.",
    "How Hard It Is to Buy/Sell Stocks": "Higher readings mean markets are less liquid, so large trades can move prices more than usual.",
    "How Invested Institutions Are": "A composite view of whether large investors are putting money to work or pulling back into cash.",
    "Trend-Following Fund Signal": "Shows whether momentum-driven funds are likely buying or selling based on recent price trends.",
    "Jobs vs. Inflation Trade-Off": "Shows how unemployment and inflation are moving together. Lower unemployment can sometimes go with faster price growth.",
    "Current Economic Environment": "Summarizes whether the economy looks hotter, weaker, or more fragile based on growth and inflation trends.",
    "Stock Chaos vs. Macro Chaos Index": "Compares stock-specific turbulence with broad macro-driven market stress.",
}

ALERT_REWRITES = [
    ("VIX term structure in backwardation", "⚠️ Heightened near-term risk: Options traders are paying up for crash protection right now, not just months from now. This often appears before sharp market moves."),
    ("VIX Backwardation detected", "⚠️ Heightened near-term risk: Options traders are paying up for crash protection right now, not just months from now. This often appears before sharp market moves."),
    ("Negative GEX detected", "⚡ Volatility Amplifier ON: Market makers are positioned in a way that can make price swings larger and faster than usual."),
    ("dealers SHORT gamma", "⚡ Volatility Amplifier ON: Market makers are positioned in a way that can make price swings larger and faster than usual."),
    ("CAPE ratio", "📊 Stocks look expensive: Based on 10 years of earnings history, stock prices are high relative to the past. That does not guarantee a crash, but future long-term returns may be lower."),
    ("Recession probability above 50%", "🔴 Elevated recession risk: Economic models suggest the odds of a U.S. recession are meaningfully above normal. This is a watch signal, not a panic signal."),
]

_AUTO_PLOTLY_CAPTIONS_SEEN = set()


def _set_ui_mode(mode):
    canonical = "beginner" if mode == "beginner" else "professional"
    st.session_state["ui_mode"] = canonical
    st.session_state["simple_mode"] = canonical == "beginner"
    st.session_state["professional_mode"] = canonical == "professional"
    _AUTO_PLOTLY_CAPTIONS_SEEN.clear()


def _ensure_ui_mode_state():
    current = st.session_state.get("ui_mode")
    if current in ("beginner", "professional"):
        _set_ui_mode(current)
        return
    if bool(st.session_state.get("simple_mode", False)):
        _set_ui_mode("beginner")
    else:
        _set_ui_mode("professional")


def is_beginner_mode():
    _ensure_ui_mode_state()
    return st.session_state.get("ui_mode") == "beginner"


def is_professional_mode():
    _ensure_ui_mode_state()
    return st.session_state.get("ui_mode") == "professional"


def _translate_regime_label(text):
    if not is_beginner_mode() or text is None or not isinstance(text, str):
        return text
    stripped = text.strip()
    if stripped in BEGINNER_REGIME_LABELS:
        return BEGINNER_REGIME_LABELS[stripped]
    for prefix in ("🧊 ", "🔥 ", "🌤️ ", "🌱 "):
        if stripped.startswith(prefix):
            base = stripped[len(prefix):].strip()
            if base in BEGINNER_REGIME_LABELS:
                return f"{prefix}{BEGINNER_REGIME_LABELS[base]}"
    return text


def _translate_user_text(text):
    if not is_beginner_mode() or text is None:
        return text
    if not isinstance(text, str):
        return text
    replacements = list(BEGINNER_LABEL_REPLACEMENTS.items())
    protected = []
    out = text

    def _protect_phrase(raw_text, phrase):
        if not phrase or phrase not in raw_text:
            return raw_text
        token = f"__BEGINNER_LOCK_{len(protected)}__"
        protected.append((token, phrase))
        return raw_text.replace(phrase, token)

    # Protect already translated phrases so repeated reruns remain idempotent.
    for _, new in sorted(replacements, key=lambda kv: len(kv[1]), reverse=True):
        out = _protect_phrase(out, new)

    staged = []
    for old, new in sorted(replacements, key=lambda kv: len(kv[0]), reverse=True):
        pattern = re.escape(old)
        if re.fullmatch(r"[A-Za-z0-9/%.\-]+", old):
            pattern = rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])"
        token = f"__BEGINNER_STAGE_{len(staged)}__"
        next_out, count = re.subn(pattern, token, out)
        if count:
            out = next_out
            staged.append((token, new))

    for token, phrase in staged:
        out = out.replace(token, phrase)

    for token, phrase in protected:
        out = out.replace(token, phrase)
    return out


def _plain_help_for_text(text):
    if not is_beginner_mode():
        return None
    normalized = _translate_user_text(text or "")
    for key, explanation in PLAIN_EXPLANATIONS.items():
        if key in normalized:
            return explanation
    return None


def _rewrite_alert_text(text):
    if not is_beginner_mode():
        return text
    if not isinstance(text, str):
        return text
    for needle, replacement in ALERT_REWRITES:
        if needle in text:
            return replacement
    return _translate_user_text(text)


def _translate_figure_for_beginner(fig):
    if not is_beginner_mode() or fig is None:
        return fig
    try:
        title_text = getattr(fig.layout.title, "text", None)
        if title_text:
            fig.update_layout(title=dict(text=_translate_user_text(title_text)))
        if getattr(fig.layout, "xaxis", None) and getattr(fig.layout.xaxis, "title", None):
            x_title = getattr(fig.layout.xaxis.title, "text", None)
            if x_title:
                fig.update_xaxes(title_text=_translate_user_text(x_title))
        if getattr(fig.layout, "yaxis", None) and getattr(fig.layout.yaxis, "title", None):
            y_title = getattr(fig.layout.yaxis.title, "text", None)
            if y_title:
                fig.update_yaxes(title_text=_translate_user_text(y_title))
        if getattr(fig.layout, "annotations", None):
            for ann in fig.layout.annotations:
                if getattr(ann, "text", None):
                    ann.text = _translate_user_text(ann.text)
        for trace in getattr(fig, "data", []):
            if getattr(trace, "name", None):
                trace.name = _translate_user_text(trace.name)
    except Exception:
        pass
    return fig


def _chart_caption_from_figure(fig):
    try:
        title_text = getattr(fig.layout.title, "text", "") or ""
    except Exception:
        title_text = ""
    lookup = _plain_help_for_text(title_text)
    if lookup:
        return f"📘 What this means: {lookup}"
    return None


def _display_tab_label(label):
    return TAB_DISPLAY_LABELS.get(label, label) if is_beginner_mode() else label


def render_tab_summary(tab_key, fred, treasury=None, mkt=None, fg=None, naaim=None, cape=None, extra=None):
    extra = extra or {}
    today = datetime.datetime.now().strftime("%B %d, %Y")
    gdp = _get_val(fred, "GDPNOW") or _get_val(fred, "A191RL1Q225SBEA")
    cpi = _get_val(fred, "CPIAUCSL")
    unrate = _get_val(fred, "UNRATE")
    dff = _get_val(fred, "DFF")
    rec = _get_val(fred, "RECPROUSM156N")
    vix = (mkt.get("^VIX") or {}).get("value") if mkt else None
    fear = (fg or {}).get("value")
    cape_v = (cape or {}).get("value")
    yield_curve = _get_val(fred, "T10Y2Y")
    hy = _get_val(fred, "BAMLH0A0HYM2")
    pcr = (extra.get("opts") or {}).get("pcr")
    total_gex = (extra.get("chain_data") or {}).get("total_gex")
    move = (mkt.get("^MOVE") or {}).get("value") if mkt else None
    ted = _get_val(fred, "TEDRATE")
    regime_label = _translate_regime_label(extra.get("regime_state", {}).get("regime", ""))
    inst_score = (extra.get("inst_score") or {}).get("label")

    summaries = {
        "🏦 Macro Overview": (
            f"📰 **Today's Economic Snapshot ({today})**\n"
            f"The economy is growing at about **{_fmt(gdp, '%')}** while prices are rising at **{_fmt(cpi, '%')}**. "
            f"The Fed's benchmark rate sits near **{_fmt(dff, '%')}**, and the yield curve is **{_fmt(yield_curve, '%')}**, which is one of the classic recession watch signals. "
            f"Recession models currently imply about **{_fmt(rec, '%')}** risk."
        ),
        "💼 Labor & Consumer": (
            f"📰 **Today's Jobs & Consumer Snapshot ({today})**\n"
            f"Unemployment is **{_fmt(unrate, '%')}**, which tells you how strong the job market is right now. "
            f"Inflation at **{_fmt(cpi, '%')}** still matters here because rising prices shape wage pressure and household spending power. "
            f"Use this tab to judge whether consumers still have enough income and confidence to keep the economy moving."
        ),
        "💱 Markets & Sentiment": (
            f"📰 **Today's Market Mood ({today})**\n"
            f"Investor mood is around **{fear if fear is not None else 'N/A'} / 100**, while market nervousness is **{_fmt(vix, 'idx')}**. "
            f"Stocks look **{'expensive' if cape_v and cape_v > 30 else 'closer to normal' if cape_v is not None else 'unclear'}** based on the long-term valuation reading of **{_fmt(cape_v, 'idx')}**. "
            f"This tab tells you whether investors feel calm, cautious, or stretched."
        ),
        "Energy Futures": (
            f"📰 **Today's Energy Futures Snapshot ({today})**\n"
            f"This tab reads uploaded WTI futures spread data and converts the curve into simple supply-demand signals. "
            f"The front calendar spread shows whether near-term barrels are priced tight or loose, while WTI-Brent shows whether Brent is commanding a global-risk premium. "
            f"Use it as an oil-market stress panel, not as a model-generated forecast."
        ),
        "📉 Options & Derivatives": (
            f"📰 **Today's Options Risk Snapshot ({today})**\n"
            f"Market nervousness is **{_fmt(vix, 'idx')}**, and the investor fear gauge is **{_fmt(pcr, 'idx')}**. "
            f"Dealer hedging force is currently **{'in amplified volatility mode' if total_gex is not None and total_gex < 0 else 'in stabilized volatility mode' if total_gex is not None else 'not available'}**, which helps explain whether daily moves are likely to be calm or jumpy. "
            f"Use this tab to see where protection demand is clustered and where price swings may accelerate."
        ),
        "🪙 Metals": (
            f"📰 **Today's Metals Snapshot ({today})**\n"
            f"Gold, silver, and copper help tell three different stories: safety demand, industrial demand, and inflation expectations. "
            f"When gold rises while copper weakens, investors are often getting more defensive. "
            f"Use this tab to see whether markets are leaning toward growth optimism or caution."
        ),
        "🏠 Housing & Credit": (
            f"📰 **Today's Housing & Credit Snapshot ({today})**\n"
            f"The yield curve is **{_fmt(yield_curve, '%')}**, junk bond stress is **{_fmt(hy, 'bp')}**, and the current economic environment reads as **{regime_label or 'N/A'}**. "
            f"This tab combines mortgage pressure, housing activity, and credit conditions to show whether borrowing is supporting growth or becoming a headwind. "
            f"When borrowing costs stay high for too long, both home demand and corporate risk appetite usually cool."
        ),
        "📊 Phillips Curve": (
            f"📰 **Today's Jobs vs. Inflation Snapshot ({today})**\n"
            f"Unemployment is **{_fmt(unrate, '%')}** and inflation is **{_fmt(cpi, '%')}**. "
            f"This chart helps you see whether a strong job market is still pushing prices higher or whether inflation is easing without major job losses. "
            f"It is a simple way to visualize how hard the Fed's balancing act currently looks."
        ),
        "📰 News & Signals": (
            f"📰 **Today's Headline Context ({today})**\n"
            f"The current economic environment looks like **{_translate_regime_label(_regime(fred, mkt or {})[0]) if fred and mkt else 'N/A'}**, and market nervousness is **{_fmt(vix, 'idx')}**. "
            f"This section combines live headlines with the main growth, inflation, and risk signals so you can connect the news with what markets are actually pricing. "
            f"Read it like a morning briefing: first the headlines, then the signals that confirm or contradict them."
        ),
        "Liquidity Conditions": (
            f"📰 **Today's Money & Credit Snapshot ({today})**\n"
            f"Bank stress is **{_fmt(ted, '%')}**, overall financial stress is **{_fmt(_get_val(fred, 'NFCI'), 'idx')}**, and bond market anxiety is **{_fmt(move, 'idx')}**. "
            f"This tab shows whether money is flowing smoothly through the system or whether funding is getting tight. "
            f"When several of these indicators worsen together, markets often become more fragile."
        ),
        "Institutional Flows": (
            f"📰 **Today's Big Money Snapshot ({today})**\n"
            f"Large institutions currently look **{inst_score or 'unclear'}**, based on futures positioning, mutual fund flows, and cash balances. "
            f"This tab helps you see whether professional investors are putting money to work or stepping back into cash. "
            f"When big money gets defensive, liquidity can fade even if prices have not fallen yet."
        ),
        "GS-Style Composites": (
            f"📰 **Today's Composite Risk Snapshot ({today})**\n"
            f"This tab combines multiple market and economic inputs into simplified 0–100 scores. "
            f"Financial conditions show whether money is easy or tight, recession risk checks labor/curve/credit stress, and risk appetite shows whether investors are leaning defensive or aggressive. "
            f"Treat these as dashboard proxies, not official Wall Street index values."
        ),
        "Global Macro": (
            f"📰 **Today's Global Macro Snapshot ({today})**\n"
            f"The dollar index is **{_fmt((mkt.get('DX-Y.NYB') or {}).get('value') if mkt else None, 'idx')}**, EUR/USD is **{_fmt((mkt.get('EURUSD=X') or {}).get('value') if mkt else None, 'idx')}**, and USD/JPY is **{_fmt((mkt.get('JPY=X') or {}).get('value') if mkt else None, 'idx')}**. "
            f"A stronger dollar usually tightens financial conditions outside the U.S., especially for emerging markets and dollar borrowers. "
            f"Use this tab to watch global funding pressure and major FX signals."
        ),
        "Sentiment Framework": (
            f"📰 **Today's Investor Mood Snapshot ({today})**\n"
            f"Investor mood is **{fear if fear is not None else 'N/A'} / 100**, market nervousness is **{_fmt(vix, 'idx')}**, and bond market anxiety is **{_fmt(move, 'idx')}**. "
            f"This tab brings together multiple fear gauges to show whether caution is isolated or broad-based. "
            f"If several fear indicators rise at once, short-term market risk usually increases."
        ),
        "🤖 AI Macro Analysis": (
            f"📰 **Today's Analysis Workspace ({today})**\n"
            f"This tab packages the live dashboard into a structured snapshot so you can review the economy, market stress, options positioning, and big-money flows in one place. "
            f"Run the export, inspect the captured values, and then turn them into a readable narrative. "
            f"The goal is not more jargon — it is a faster explanation of what matters now."
        ),
    }

    st.info(summaries.get(tab_key, f"📰 **Today's Snapshot ({today})**\nThis section summarizes the latest live market and economic data in plain English."))
    if tab_key == "🏦 Macro Overview":
        sahm = _get_val(fred, "SAHMREALTIME")
        psavert = _get_val(fred, "PSAVERT")
        psavert_avg = _hist_average(fred, "PSAVERT_HIST", periods=12)
        m2_yoy = compute_m2_yoy_change(fred)
        umich = _get_val(fred, "UMCSENT")
        umich_delta = _hist_latest_delta(fred, "UMCSENT_HIST", periods=1)
        ig = _get_val(fred, "BAMLC0A0CM")
        hy = _get_val(fred, "BAMLH0A0HYM2")
        k = st.columns(5)
        k[0].metric(
            "Sahm Rule",
            f"{sahm:.2f}" if sahm is not None else "N/A",
            delta="Recession trigger" if sahm is not None and sahm >= 0.5 else "Watch" if sahm is not None and sahm >= 0.3 else "Calm" if sahm is not None else None,
            delta_color="inverse" if sahm is not None and sahm >= 0.5 else "normal",
        )
        k[1].metric(
            "Personal Savings Rate",
            f"{psavert:.1f}%" if psavert is not None else "N/A",
            delta=f"{psavert - psavert_avg:+.1f} vs 12M avg" if psavert is not None and psavert_avg is not None else None,
        )
        k[2].metric(
            "M2 YoY Change",
            f"{m2_yoy:+.2f}%" if m2_yoy is not None else "N/A",
            delta="Liquidity drain" if m2_yoy is not None and m2_yoy < 0 else "Liquidity expanding" if m2_yoy is not None else None,
            delta_color="inverse" if m2_yoy is not None and m2_yoy < 0 else "normal",
        )
        k[3].metric(
            "University of Michigan Consumer Sentiment Index",
            f"{umich:.1f}" if umich is not None else "N/A",
            delta=f"{umich_delta:+.1f} vs prior" if umich_delta is not None else None,
        )
        k[4].metric(
            "IG / HY Credit Spread",
            f"{ig:.0f} / {hy:.0f} bp" if ig is not None and hy is not None else "N/A",
            delta="Credit stress building" if ig is not None and ig > 150 else None,
            delta_color="inverse",
        )


if not hasattr(st, "_codex_orig_metric"):
    st._codex_orig_metric = st.metric
    st._codex_orig_plotly_chart = st.plotly_chart
    st._codex_orig_markdown = st.markdown
    st._codex_orig_subheader = st.subheader
    st._codex_orig_caption = st.caption
    st._codex_orig_warning = st.warning
    st._codex_orig_error = st.error
    st._codex_orig_success = st.success
    st._codex_orig_info = st.info

_ORIG_ST_METRIC = st._codex_orig_metric
_ORIG_ST_PLOTLY = st._codex_orig_plotly_chart
_ORIG_ST_MARKDOWN = st._codex_orig_markdown
_ORIG_ST_SUBHEADER = st._codex_orig_subheader
_ORIG_ST_CAPTION = st._codex_orig_caption
_ORIG_ST_WARNING = st._codex_orig_warning
_ORIG_ST_ERROR = st._codex_orig_error
_ORIG_ST_SUCCESS = st._codex_orig_success
_ORIG_ST_INFO = st._codex_orig_info


def _patched_metric(label, value, delta=None, delta_color="normal", help=None, **kwargs):
    translated_label = _translate_user_text(label)
    translated_help = help or _plain_help_for_text(translated_label)
    return _ORIG_ST_METRIC(translated_label, value, delta=delta, delta_color=delta_color, help=translated_help, **kwargs)


def _patched_plotly_chart(fig=None, *args, **kwargs):
    fig = _translate_figure_for_beginner(fig)
    result = _ORIG_ST_PLOTLY(fig, *args, **kwargs)
    caption = _chart_caption_from_figure(fig)
    if caption and caption not in _AUTO_PLOTLY_CAPTIONS_SEEN:
        _AUTO_PLOTLY_CAPTIONS_SEEN.add(caption)
        _ORIG_ST_CAPTION(caption)
    return result


def _patched_markdown(body, *args, **kwargs):
    return _ORIG_ST_MARKDOWN(_translate_user_text(body), *args, **kwargs)


def _patched_subheader(body, *args, **kwargs):
    return _ORIG_ST_SUBHEADER(_translate_user_text(body), *args, **kwargs)


def _patched_caption(body, *args, **kwargs):
    return _ORIG_ST_CAPTION(_translate_user_text(body), *args, **kwargs)


def _patched_warning(body, *args, **kwargs):
    return _ORIG_ST_WARNING(_rewrite_alert_text(body), *args, **kwargs)


def _patched_error(body, *args, **kwargs):
    return _ORIG_ST_ERROR(_rewrite_alert_text(body), *args, **kwargs)


def _patched_success(body, *args, **kwargs):
    return _ORIG_ST_SUCCESS(_rewrite_alert_text(body), *args, **kwargs)


def _patched_info(body, *args, **kwargs):
    return _ORIG_ST_INFO(_translate_user_text(body), *args, **kwargs)


_CODEX_BEGINNER_PATCH_VERSION = 2


if not getattr(st, "_codex_beginner_patched", False):
    st.metric = _patched_metric
    st.plotly_chart = _patched_plotly_chart
    st.markdown = _patched_markdown
    st.subheader = _patched_subheader
    st.caption = _patched_caption
    st.warning = _patched_warning
    st.error = _patched_error
    st.success = _patched_success
    st.info = _patched_info
    st._codex_beginner_patched = True
    st._codex_beginner_patch_version = _CODEX_BEGINNER_PATCH_VERSION
elif getattr(st, "_codex_beginner_patch_version", 0) != _CODEX_BEGINNER_PATCH_VERSION:
    st.metric = _patched_metric
    st.plotly_chart = _patched_plotly_chart
    st.markdown = _patched_markdown
    st.subheader = _patched_subheader
    st.caption = _patched_caption
    st.warning = _patched_warning
    st.error = _patched_error
    st.success = _patched_success
    st.info = _patched_info
    st._codex_beginner_patch_version = _CODEX_BEGINNER_PATCH_VERSION

REGIME_COLORS = {
    "Reflation": "#fbbf24",
    "Stagflation": "#f87171",
    "Goldilocks": "#34d399",
    "Recession": "#94a3b8",
}

REGIME_LABELS = {
    "Reflation": "🌤 Reflation",
    "Stagflation": "🔥 Stagflation",
    "Goldilocks": "🟢 Goldilocks",
    "Recession": "🧊 Recession",
}


def _classify_regime(credit_roc, inflation_roc):
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
    return regime, REGIME_COLORS[regime]


def compute_regime_state(fred, lookback_days=60, energy_curve=None):
    curve_regime = get_energy_curve_regime(energy_curve)
    cpi_hist = fred.get("CPI_HIST", [])
    spread_hist = fred.get("SPREAD_HIST", [])
    if not cpi_hist or not spread_hist:
        return {
            "regime": "Mixed / Uncertain",
            "color": "#fbbf24",
            "curve_regime": curve_regime,
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
            "curve_regime": curve_regime,
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
            "curve_regime": curve_regime,
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
        "curve_regime": curve_regime,
        "credit_roc": float(current["credit_roc"]),
        "inflation_roc": float(current["inflation_roc"]),
        "days_in_regime": days_in_regime,
        "history": history[-90:],
    }


def compute_quality_rotation(mkt):
    spx_chg = (mkt.get("^GSPC") or {}).get("change_pct")
    hyg_chg = (mkt.get("HYG") or {}).get("change_pct")
    iwm_chg = (mkt.get("IWM") or {}).get("change_pct")
    if spx_chg is None or hyg_chg is None or iwm_chg is None:
        return {
            "signal": "Neutral",
            "color": "#fbbf24",
            "hyg_vs_spy": None,
            "iwm_vs_spy": None,
            "score": None,
        }

    hyg_vs_spy = float(hyg_chg) - float(spx_chg)
    iwm_vs_spy = float(iwm_chg) - float(spx_chg)
    score = float(np.mean([hyg_vs_spy, iwm_vs_spy]))
    if hyg_vs_spy > 0 and iwm_vs_spy > 0:
        signal, color = "Risk-On", "#34d399"
    elif hyg_vs_spy < 0 and iwm_vs_spy < 0:
        signal, color = "Risk-Off / Quality Bid", "#f87171"
    else:
        signal, color = "Neutral", "#fbbf24"
    return {
        "signal": signal,
        "color": color,
        "hyg_vs_spy": hyg_vs_spy,
        "iwm_vs_spy": iwm_vs_spy,
        "score": score,
    }


def _regime(fred, mkt):
    lookback_days = int(st.session_state.get("regime_roc_lookback_days", 60))
    regime_state = compute_regime_state(fred, lookback_days=lookback_days)
    regime = regime_state.get("regime")
    if regime in REGIME_LABELS:
        return REGIME_LABELS[regime], regime_state.get("color", "#fbbf24")
    return "⚡ Mixed / Uncertain", "#fbbf24"

def _get_val(fred, sid):
    return (fred.get(sid) or {}).get("value")


def _safe_float(value):
    try:
        if value is None:
            return None
        v = float(value)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    except Exception:
        return None


def _hist_points(fred, key, ascending=True):
    rows = []
    for item in fred.get(key, []) or []:
        try:
            value, date = item
            value = float(value)
            rows.append({"date": str(date), "value": value})
        except Exception:
            continue
    rows = list(reversed(rows)) if ascending else rows
    return rows


def _hist_values(fred, key, ascending=True):
    return [p["value"] for p in _hist_points(fred, key, ascending=ascending)]


def _hist_latest_delta(fred, key, periods=1):
    values = _hist_values(fred, key, ascending=True)
    if len(values) <= periods:
        return None
    return values[-1] - values[-1 - periods]


def _hist_average(fred, key, periods=12):
    values = _hist_values(fred, key, ascending=True)
    values = values[-periods:] if periods else values
    return sum(values) / len(values) if values else None


def _hist_latest(fred, key):
    values = _hist_values(fred, key, ascending=True)
    return values[-1] if values else None


ENERGY_FUTURES_DEFAULT_PATH = os.path.join(
    BASE_DIR, "..", "data", "futures-spreads-clm26-04-23-2026.csv"
)
ENERGY_FUTURES_DEFAULT_PATHS = [
    ENERGY_FUTURES_DEFAULT_PATH,
]
ENERGY_MONTH_CODES = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}


def _decode_futures_contract(contract):
    try:
        m = re.match(r"^([A-Z]+)([FGHJKMNQUVXZ])(\d)$", str(contract).strip().upper())
        if not m:
            return None
        month_code = m.group(2)
        year_digit = int(m.group(3))
        year = 2030 + year_digit if year_digit <= 5 else 2020 + year_digit
        return {
            "symbol": str(contract).strip().upper(),
            "root": m.group(1),
            "month_code": month_code,
            "month": ENERGY_MONTH_CODES[month_code],
            "year": year,
        }
    except Exception:
        return None


def _energy_contract_month_label(contract, long=False):
    try:
        meta = _decode_futures_contract(contract)
        if not meta:
            return str(contract)
        fmt = "%b %Y" if long else "%b '%y"
        return datetime.date(int(meta["year"]), int(meta["month"]), 1).strftime(fmt)
    except Exception:
        return str(contract)


def _infer_energy_front_contract(sp_rows):
    try:
        candidates = sp_rows.copy()
        candidates["Volume"] = pd.to_numeric(candidates.get("Volume"), errors="coerce")
        candidates = candidates.dropna(subset=["Volume"]).sort_values("Volume", ascending=False)
        if not candidates.empty:
            return str(candidates.iloc[0]["Leg1"]).strip().upper()
    except Exception:
        pass
    try:
        modes = sp_rows["Leg1"].dropna().astype(str).str.upper().mode()
        if not modes.empty:
            return modes.iloc[0]
    except Exception:
        pass
    return None


def load_futures_spreads(filepath):
    """
    Load a futures-spread CSV and return the WTI forward spread curve vs the
    inferred front month. Related IS/BF rows are attached in DataFrame attrs.
    """
    try:
        raw = pd.read_csv(filepath, skipfooter=1, engine="python")
        for col in ["Leg1", "Leg2", "Leg3", "Leg4", "Type"]:
            if col in raw.columns:
                raw[col] = raw[col].astype("string").str.strip()
        for col in ["Latest", "Change", "Open", "High", "Low", "Previous", "Volume"]:
            if col in raw.columns:
                raw[col] = pd.to_numeric(raw[col], errors="coerce")

        sp_all = raw[
            (raw.get("Type") == "SP") &
            (raw.get("Leg3").isna()) &
            (raw.get("Leg1").astype(str).str.startswith("CL", na=False))
        ].copy()
        if sp_all.empty:
            return pd.DataFrame()

        front_contract = _infer_energy_front_contract(sp_all)
        front_meta = _decode_futures_contract(front_contract)
        if not front_meta:
            return pd.DataFrame()
        front_month = front_meta["month"]

        curve = sp_all[sp_all["Leg1"].astype(str).str.upper() == front_contract].copy()
        if curve.empty:
            curve = sp_all.copy()
        decoded = curve["Leg2"].apply(_decode_futures_contract)
        curve["leg2_month"] = decoded.apply(lambda x: x.get("month") if x else np.nan)
        curve["leg2_year"] = decoded.apply(lambda x: x.get("year") if x else np.nan)
        curve["months_out"] = (curve["leg2_year"] - 2026) * 12 + curve["leg2_month"] - front_month
        curve["contract_label"] = curve["Leg2"].astype(str) + " vs " + curve["Leg1"].astype(str)
        curve = curve.dropna(subset=["months_out", "Latest"]).copy()
        curve["months_out"] = curve["months_out"].astype(int)
        curve = curve.sort_values("months_out").reset_index(drop=True)

        is_rows = raw[
            (raw.get("Type") == "IS") &
            (raw.get("Leg3").isna()) &
            (raw.get("Leg1").astype(str).str.startswith("CL", na=False)) &
            (raw.get("Leg2").astype(str).str.startswith("QA", na=False))
        ].copy()
        if not is_rows.empty:
            is_decoded = is_rows["Leg2"].apply(_decode_futures_contract)
            is_rows["leg2_month"] = is_decoded.apply(lambda x: x.get("month") if x else np.nan)
            is_rows["leg2_year"] = is_decoded.apply(lambda x: x.get("year") if x else np.nan)
            is_rows["months_out"] = (is_rows["leg2_year"] - 2026) * 12 + is_rows["leg2_month"] - front_month
            is_rows["contract_label"] = is_rows["Leg1"].astype(str) + " / " + is_rows["Leg2"].astype(str)
            is_rows["front_rank"] = np.where(is_rows["Leg1"].astype(str).str.upper() == front_contract, 0, 1)
            is_rows = is_rows.sort_values(["front_rank", "months_out", "Leg1"]).reset_index(drop=True)

        bf_rows = raw[
            (raw.get("Type") == "BF") &
            (raw.get("Leg1").astype(str).str.startswith("CL", na=False))
        ].copy()

        curve.attrs["raw"] = raw
        curve.attrs["intermarket"] = is_rows
        curve.attrs["butterflies"] = bf_rows
        curve.attrs["front_contract"] = front_contract
        curve.attrs["front_month"] = front_month
        curve.attrs["front_year"] = front_meta["year"]
        front_price = None
        try:
            sa_rows = raw[
                (raw.get("Type") == "SA") &
                (raw.get("Leg1").astype(str).str.upper() == front_contract) &
                (raw.get("Leg3").isna()) &
                (raw.get("Latest").between(20, 200))
            ].copy()
            if not sa_rows.empty:
                front_price = float(sa_rows.sort_values("Leg2").iloc[0]["Latest"])
        except Exception:
            front_price = None
        curve.attrs["front_price"] = front_price
        return curve
    except Exception:
        return pd.DataFrame()


def get_energy_curve_regime(futures_curve):
    try:
        if futures_curve is None or futures_curve.empty:
            return None
        front = _energy_spread_row(futures_curve, 1)
        front_spread = _safe_float(front.get("Latest")) if front is not None else None
        if front_spread is None:
            return None
        if front_spread < 0:
            return "Backwardation"
        if front_spread <= 2:
            return "Flat"
        if front_spread <= 5:
            return "Contango"
        return "Deep Contango"
    except Exception:
        return None


def _energy_spread_row(futures_curve, months_out):
    try:
        if futures_curve is None or futures_curve.empty:
            return None
        rows = futures_curve[futures_curve["months_out"] == int(months_out)]
        if rows.empty:
            return None
        return rows.iloc[0]
    except Exception:
        return None


def _normalize_score(value, low, high, invert=False):
    v = _safe_float(value)
    if v is None or high == low:
        return None
    score = max(0.0, min(100.0, (v - low) / (high - low) * 100.0))
    return round(100.0 - score if invert else score, 1)


def _z_score_to_0_100(value, history_values, invert=False):
    v = _safe_float(value)
    vals = [float(x) for x in history_values or [] if _safe_float(x) is not None]
    if v is None or len(vals) < 6:
        return None
    mean = sum(vals) / len(vals)
    std = float(np.std(vals)) or 1.0
    score = max(0.0, min(100.0, 50.0 + ((v - mean) / std) * 10.0))
    return round(100.0 - score if invert else score, 1)


def _avg_available(scores):
    vals = [float(s) for s in scores if s is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def _weighted_available(weighted_scores):
    vals = [(float(score), float(weight)) for score, weight in weighted_scores if score is not None]
    total_w = sum(weight for _, weight in vals)
    return round(sum(score * weight for score, weight in vals) / total_w, 1) if total_w else None


def compute_m2_yoy_change(fred):
    current = _hist_latest(fred, "M2SL_YOY_HIST")
    if current is not None:
        return round(current, 2)
    values = _hist_values(fred, "M2SL_HIST", ascending=True)
    if len(values) < 13 or values[-13] == 0:
        return None
    return round((values[-1] / values[-13] - 1.0) * 100.0, 2)


def compute_real_wage_growth(fred):
    wage = _get_val(fred, "CES0500000003")
    cpi = _get_val(fred, "CPIAUCSL")
    if wage is None or cpi is None:
        return None
    return round(float(wage) - float(cpi), 2)


def compute_dxy_trend(mkt):
    dxy = (mkt.get("DX-Y.NYB") or {}).get("value") if mkt else None
    hist = fetch_yfinance_close_history("DX-Y.NYB", period="6mo", interval="1d")
    values = [p["value"] for p in hist]
    if len(values) < 50:
        return {
            "value": dxy,
            "ma20": None,
            "ma50": None,
            "trend": "Insufficient data",
            "strengthening": False,
            "history": hist,
        }
    ma20 = sum(values[-20:]) / 20
    ma50 = sum(values[-50:]) / 50
    strengthening = ma20 > ma50
    return {
        "value": dxy if dxy is not None else values[-1],
        "ma20": round(ma20, 2),
        "ma50": round(ma50, 2),
        "trend": "Strengthening" if strengthening else "Weakening",
        "strengthening": strengthening,
        "history": hist,
    }


def compute_gs_style_composites(fred, mkt, fg=None, opts=None, cape=None):
    opts = opts or {}
    fg = fg or {}
    cape = cape or {}
    dxy_v = (mkt.get("DX-Y.NYB") or {}).get("value") if mkt else None
    vix_v = (mkt.get("^VIX") or {}).get("value") if mkt else None
    move_v = (mkt.get("^MOVE") or {}).get("value") if mkt else None
    cape_v = cape.get("value")

    fci_components = {
        "Fed Funds": _z_score_to_0_100(_get_val(fred, "DFF"), _hist_values(fred, "DFF_HIST")),
        "10Y Yield": _z_score_to_0_100(_get_val(fred, "DGS10"), _hist_values(fred, "DGS10_HIST")),
        "HY Spread": _z_score_to_0_100(_get_val(fred, "BAMLH0A0HYM2"), _hist_values(fred, "HY_SPREAD_HIST")),
        "IG Spread": _z_score_to_0_100(_get_val(fred, "BAMLC0A0CM"), _hist_values(fred, "IG_SPREAD_HIST")),
        "DXY": _normalize_score(dxy_v, 90, 110),
        "CAPE": _normalize_score(cape_v, 18, 40),
    }
    fci_score = _avg_available(fci_components.values())
    fci_history = []
    dff_h = _hist_points(fred, "DFF_HIST")
    dgs10_h = _hist_points(fred, "DGS10_HIST")
    hy_h = _hist_points(fred, "HY_SPREAD_HIST")
    ig_h = _hist_points(fred, "IG_SPREAD_HIST")
    for i in range(-12, 0):
        try:
            vals = [
                _normalize_score(dff_h[i]["value"], 0, 6) if len(dff_h) >= abs(i) else None,
                _normalize_score(dgs10_h[i]["value"], 1, 6) if len(dgs10_h) >= abs(i) else None,
                _normalize_score(hy_h[i]["value"], 250, 800) if len(hy_h) >= abs(i) else None,
                _normalize_score(ig_h[i]["value"], 60, 250) if len(ig_h) >= abs(i) else None,
                _normalize_score(dxy_v, 90, 110),
                _normalize_score(cape_v, 18, 40),
            ]
            score = _avg_available(vals)
            date = (dff_h[i]["date"] if len(dff_h) >= abs(i) else str(i))
            if score is not None:
                fci_history.append({"date": date, "value": score})
        except Exception:
            continue

    sahm = _get_val(fred, "SAHMREALTIME")
    t10y2y = _get_val(fred, "T10Y2Y")
    lei_values = _hist_values(fred, "LEI_HIST", ascending=True)
    lei_yoy = ((lei_values[-1] / lei_values[-13] - 1) * 100) if len(lei_values) >= 13 and lei_values[-13] else None
    unrate_delta_3m = _hist_latest_delta(fred, "UNRATE_HIST", periods=3)
    rec_components = {
        "Sahm Rule": _normalize_score(sahm, 0.0, 0.8),
        "Yield Curve": _normalize_score(t10y2y, 1.0, -1.0),
        "LEI YoY": _normalize_score(lei_yoy, 3.0, -6.0),
        "HY Spread": _normalize_score(_get_val(fred, "BAMLH0A0HYM2"), 250, 800),
        "Unemployment 3M Delta": _normalize_score(unrate_delta_3m, -0.2, 0.8),
    }
    recession_score = _weighted_available([
        (rec_components["Sahm Rule"], 0.30),
        (rec_components["Yield Curve"], 0.25),
        (rec_components["LEI YoY"], 0.20),
        (rec_components["HY Spread"], 0.15),
        (rec_components["Unemployment 3M Delta"], 0.10),
    ])
    recession_history = []
    sahm_h = _hist_points(fred, "SAHMREALTIME_HIST")
    curve_h = _hist_points(fred, "T10Y2Y_HIST")
    for i in range(-12, 0):
        try:
            score = _weighted_available([
                (_normalize_score(sahm_h[i]["value"], 0.0, 0.8) if len(sahm_h) >= abs(i) else None, 0.30),
                (_normalize_score(curve_h[i]["value"], 1.0, -1.0) if len(curve_h) >= abs(i) else None, 0.25),
                (_normalize_score(hy_h[i]["value"], 250, 800) if len(hy_h) >= abs(i) else None, 0.15),
            ])
            date = (sahm_h[i]["date"] if len(sahm_h) >= abs(i) else str(i))
            if score is not None:
                recession_history.append({"date": date, "value": score})
        except Exception:
            continue

    risk_components = {
        "VIX": _normalize_score(vix_v, 10, 45, invert=True),
        "MOVE": _normalize_score(move_v, 60, 180, invert=True),
        "PCR": _normalize_score(opts.get("pcr"), 0.6, 1.4, invert=True),
        "HY Spread": _normalize_score(_get_val(fred, "BAMLH0A0HYM2"), 250, 800, invert=True),
        "Fear & Greed": _normalize_score(fg.get("value"), 0, 100),
    }
    risk_score = _avg_available(risk_components.values())
    if risk_score is None:
        risk_label, risk_color = "Insufficient data", "#94a3b8"
    elif risk_score < 25:
        risk_label, risk_color = "Extreme Fear", "#f87171"
    elif risk_score < 45:
        risk_label, risk_color = "Fear", "#f97316"
    elif risk_score < 55:
        risk_label, risk_color = "Neutral", "#fbbf24"
    elif risk_score < 75:
        risk_label, risk_color = "Greed", "#34d399"
    else:
        risk_label, risk_color = "Extreme Greed", "#166534"

    def _surprise(name, hist_key, multiplier=100.0):
        vals = _hist_values(fred, hist_key, ascending=True)
        if len(vals) < 2 or vals[-2] == 0:
            return None
        return {"name": name, "value": round((vals[-1] - vals[-2]) / abs(vals[-2]) * multiplier, 2)}

    surprises = [
        _surprise("NFP", "PAYEMS_HIST", 100.0),
        _surprise("CPI", "CPI_HIST", 100.0),
        _surprise("GDP", "GDP_HIST", 100.0),
        _surprise("ISM PMI", "NAPM_HIST", 100.0),
    ]
    surprises = [s for s in surprises if s is not None]
    surprise_score = round(sum(s["value"] for s in surprises) / len(surprises), 2) if surprises else None

    return {
        "fci": {"score": fci_score, "components": fci_components, "history": fci_history},
        "recession": {"score": recession_score, "components": rec_components, "history": recession_history},
        "risk_appetite": {"score": risk_score, "label": risk_label, "color": risk_color, "components": risk_components},
        "macro_surprise": {"score": surprise_score, "components": surprises},
    }


def render_data_diagnostics(fred, treasury, mkt, fg, naaim, cape, aaii, news, bls):
    critical_checks = [
        ("GDPNow", _get_val(fred, "GDPNOW") or _get_val(fred, "A191RL1Q225SBEA")),
        ("CPI", _get_val(fred, "CPIAUCSL")),
        ("Unemployment", _get_val(fred, "UNRATE")),
        ("Fed Funds", _get_val(fred, "DFF")),
        ("Recession Prob", _get_val(fred, "RECPROUSM156N")),
        ("Treasury 10Y", (treasury.get("10Y") or {}).get("value")),
        ("S&P 500", (mkt.get("^GSPC") or {}).get("value")),
        ("CAPE", cape.get("value") if cape else None),
    ]
    missing_critical = [label for label, value in critical_checks if value is None]

    with st.expander("Data diagnostics", expanded=bool(missing_critical)):
        provider_rows = [
            ("FRED", len([k for k in FRED_SERIES if k in fred]), f"{len(_FRED_ERRORS)} errors"),
            ("Treasury", len(treasury), "ok" if treasury else "no rows"),
            ("Yahoo Finance", len(mkt), "ok" if mkt else "empty"),
            ("Composite Inputs", len([v for v in [_get_val(fred, "SAHMREALTIME"), _get_val(fred, "PSAVERT"), _get_val(fred, "M2SL"), _get_val(fred, "BAMLC0A0CM"), (mkt.get("DX-Y.NYB") or {}).get("value")] if v is not None]), "Sahm/savings/M2/IG/DXY"),
            ("Global Macro", len([v for v in [(mkt.get("EURUSD=X") or {}).get("value"), (mkt.get("CNH=X") or mkt.get("CNY=X") or {}).get("value"), (mkt.get("JPY=X") or {}).get("value")] if v is not None]), "FX signals"),
            ("Fear & Greed", 1 if fg else 0, fg.get("source_tag", "missing") if fg else "missing"),
            ("NAAIM", 1 if naaim else 0, naaim.get("date", "missing") if naaim else "missing"),
            ("CAPE", 1 if cape else 0, cape.get("quality", "missing") if cape else "missing"),
            ("AAII", 1 if aaii else 0, aaii.get("date", "missing") if aaii else "missing"),
            ("BLS", 1 if bls else 0, "ok" if bls else "missing"),
            ("Alpha Vantage", len(news), "api key set" if _has_key(ALPHA_VANTAGE_KEY) else "no api key"),
        ]
        diag_df = pd.DataFrame(provider_rows, columns=["Provider", "Records", "Notes"])
        st.dataframe(diag_df, use_container_width=True, hide_index=True)

        if missing_critical:
            st.warning("Missing critical values: " + ", ".join(missing_critical))
        else:
            st.success("All core dashboard data points loaded.")

        if _FRED_ERRORS:
            fred_errs = pd.DataFrame(
                [{"Series": sid, "Error": err} for sid, err in sorted(_FRED_ERRORS.items())[:12]]
            )
            st.caption("Recent FRED fetch errors")
            st.dataframe(fred_errs, use_container_width=True, hide_index=True)

        st.caption("Source provenance audit")
        source_audit_rows = [
            ("FRED macro series", "FRED API + FRED graph CSV fallback", "Official", "Federal Reserve Bank of St. Louis aggregation of official/public series."),
            ("Treasury yield curve", "U.S. Treasury daily rates CSV/XML", "Official", "Direct Treasury feed."),
            ("SOFR", "New York Fed API, FRED fallback", "Official", "Primary SOFR feed is the NY Fed."),
            ("BLS labor data", "BLS Public Data API", "Official", "Uses BLS API when available."),
            ("CFTC COT positioning", "CFTC Public Reporting Environment API", "Official", "Weekly regulator-published futures positioning."),
            ("13F institutional holdings", "SEC EDGAR / Finnhub fallback", "Official/proxy mix", "SEC is official but quarterly and delayed; Finnhub is a normalized third-party transport."),
            ("ICI fund flows", "ICI public XLS", "Primary publisher", "ICI is the industry publisher for these flow estimates."),
            ("GDPNow", "Atlanta Fed page/FRED fallback", "Primary publisher", "Model nowcast; Atlanta Fed states it is not an official Fed forecast."),
            ("Fear & Greed", "CNN dataviz endpoint/page scrape", "Publisher endpoint", "CNN is the publisher, but the JSON endpoint is unsupported and can change."),
            ("AAII sentiment", "AAII public pages", "Primary publisher", "AAII is the survey publisher."),
            ("NAAIM exposure", "NAAIM public page", "Primary publisher", "NAAIM is the survey publisher."),
            ("CAPE valuation", "multpl.com scrape", "Secondary source", "Best upgrade is Robert Shiller/Yale spreadsheet when reachable."),
            ("Market quotes, futures, FX, VIX/MOVE", "Yahoo Finance via yfinance", "Unofficial transport", "Good for dashboard context, not an exchange-certified real-time feed."),
            ("Options chain and GEX", "Yahoo Finance option chains", "Unofficial transport", "Official OPRA/options feeds are licensed; use this as analytical proxy."),
            ("Put/Call ratio", "Cboe market statistics, PutCallRatio.org fallback", "Official primary + proxy fallback", "Direct Cboe is preferred; fallback is clearly labeled if used."),
            ("World/news feeds", "Configured RSS/API sources", "Mixed", "Headlines should be treated as source-attributed, not model-generated facts."),
            ("Global PMI placeholders", "Placeholder text only", "Not connected", "No fabricated PMI values are displayed."),
        ]
        source_audit_df = pd.DataFrame(
            source_audit_rows,
            columns=["Feed", "Current source", "Provenance", "Notes"],
        )
        st.dataframe(source_audit_df, use_container_width=True, hide_index=True)


def has_systemic_data_failure(fred, treasury, mkt, fg, naaim, cape):
    core_values = [
        _get_val(fred, "GDPNOW") or _get_val(fred, "A191RL1Q225SBEA"),
        _get_val(fred, "CPIAUCSL"),
        _get_val(fred, "UNRATE"),
        _get_val(fred, "DFF"),
        _get_val(fred, "RECPROUSM156N"),
        (treasury.get("10Y") or {}).get("value"),
        (mkt.get("^GSPC") or {}).get("value"),
        fg.get("value") if fg else None,
        naaim.get("value") if naaim else None,
        cape.get("value") if cape else None,
    ]
    missing_count = sum(value is None for value in core_values)
    return missing_count >= 8

# ── PLOTLY CHART BUILDERS ─────────────────────────────────────────────────────

DARK_TEMPLATE = "plotly_dark"
CHART_BG = "rgba(0,0,0,0)"
PAPER_BG = "rgba(0,0,0,0)"

def make_yield_curve_chart(treasury):
    tenors_order = ["1M","3M","6M","1Y","2Y","3Y","5Y","7Y","10Y","20Y","30Y"]
    tenors = [t for t in tenors_order if t in treasury]
    values = [treasury[t]["value"] for t in tenors]
    if not tenors:
        return go.Figure()
    # 2Y-10Y spread for inversion detection
    t2  = treasury.get("2Y",{}).get("value")
    t10 = treasury.get("10Y",{}).get("value")
    colors = []
    for i, t in enumerate(tenors):
        v = values[i]
        if t2 and t10 and t2 > t10:
            colors.append("#f87171")  # inverted — red
        else:
            colors.append("#3b82f6")  # normal — blue

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=tenors, y=values,
        marker_color=colors,
        text=[f"{v:.2f}%" for v in values],
        textposition="outside",
        name="Yield",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8", line_width=1,
                  annotation_text="0%", annotation_position="right")
    date_str = treasury.get("10Y",{}).get("date","")
    fig.update_layout(
        title=dict(text=f"US Treasury Yield Curve  —  {date_str}", font_size=13),
        xaxis_title="Maturity",
        yaxis_title="Yield (%)",
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=360,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


def make_phillips_curve_chart(fred, lookback_months=16):
    cpi_hist    = fred.get("CPI_HIST", [])
    unrate_hist = fred.get("UNRATE_HIST", [])
    if not cpi_hist or not unrate_hist or len(cpi_hist) < 3:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Phillips Curve — insufficient data")
        return fig

    min_len = min(len(cpi_hist), len(unrate_hist), lookback_months)
    df = pd.DataFrame({
        "unemp": [unrate_hist[i][0] for i in range(min_len)],
        "cpi": [cpi_hist[i][0] for i in range(min_len)],
        "date": [cpi_hist[i][1] for i in range(min_len)],
    })
    df["date_dt"] = pd.to_datetime(df["date"], format="%Y-%m", errors="coerce")
    df = df.dropna(subset=["unemp", "cpi", "date_dt"]).sort_values("date_dt")
    if len(df) < 3:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Phillips Curve — insufficient data")
        return fig

    current = df.iloc[-1]
    history = df.iloc[:-1].copy()
    unemp = df["unemp"].tolist()
    cpi = df["cpi"].tolist()

    # OLS trend line
    try:
        coeffs = np.polyfit(unemp, cpi, 1)
        x_line = np.linspace(min(unemp)*0.97, max(unemp)*1.03, 60)
        y_line = np.polyval(coeffs, x_line)
        has_trend = True
    except Exception:
        has_trend = False

    fig = go.Figure()

    # Reference zones: keep them subtle so they guide interpretation without clutter.
    x_ref = 4.5
    y_ref = 2.0
    x_min = min(unemp) * 0.97
    x_max = max(unemp) * 1.03
    y_min = min(min(cpi) - 0.15, 1.9)
    y_max = max(max(cpi) + 0.15, 3.4)
    zones = [
        (x_min, x_ref, y_ref, y_max, "Overheating", "rgba(248,113,113,0.07)"),
        (x_ref, x_max, y_ref, y_max, "Inflation with slack", "rgba(251,191,36,0.06)"),
        (x_min, x_ref, y_min, y_ref, "Cool prices / tight labor", "rgba(52,211,153,0.05)"),
        (x_ref, x_max, y_min, y_ref, "Slack / disinflation", "rgba(148,163,184,0.05)"),
    ]
    for x0, x1, y0, y1, label, fill in zones:
        fig.add_shape(
            type="rect",
            x0=x0, x1=x1, y0=y0, y1=y1,
            line=dict(width=0),
            fillcolor=fill,
            layer="below",
        )
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=(y0 + y1) / 2,
            text=label,
            showarrow=False,
            font=dict(color="#64748b", size=10),
            opacity=0.85,
        )

    # Historical path
    if not history.empty:
        fig.add_trace(go.Scatter(
            x=history["unemp"],
            y=history["cpi"],
            mode="lines+markers",
            line=dict(color="rgba(96,165,250,0.35)", width=1.5),
            marker=dict(
                color="#3b82f6",
                size=9,
                opacity=0.8,
                line=dict(color="#93c5fd", width=1),
            ),
            customdata=np.stack([history["date"]], axis=-1),
            name="Prior months",
            hovertemplate="<b>%{customdata[0]}</b><br>Unemp: %{x:.1f}%<br>CPI: %{y:.1f}%<extra></extra>",
        ))

    # Current point
    fig.add_trace(go.Scatter(
        x=[current["unemp"]], y=[current["cpi"]],
        mode="markers+text",
        marker=dict(color="#f87171", size=16, symbol="star",
                    line=dict(color="#fecaca", width=2)),
        text=[f'Latest · {current["date"]}'],
        textfont=dict(size=10, color="#fca5a5"),
        textposition="top right",
        name="Latest month",
        hovertemplate=f"<b>Latest ({current['date']})</b><br>Unemp: %{{x:.1f}}%<br>CPI: %{{y:.1f}}%<extra></extra>",
    ))

    # Trend line
    if has_trend:
        fig.add_trace(go.Scatter(
            x=x_line.tolist(), y=y_line.tolist(),
            mode="lines",
            line=dict(color="#fbbf24", width=1.5, dash="dot"),
            name="Recent relationship",
            hoverinfo="skip",
        ))
        fig.add_annotation(
            x=x_line[-10],
            y=y_line[-10],
            text="Recent inflation/unemployment relationship",
            showarrow=False,
            font=dict(color="#fbbf24", size=10),
            yshift=-12,
        )

    # 2% target line
    fig.add_hline(
        y=y_ref,
        line_dash="dash",
        line_color="rgba(52,211,153,0.56)",
        line_width=1.5,
        annotation_text="2% Fed Target",
        annotation_position="right",
    )
    fig.add_vline(
        x=x_ref,
        line_dash="dash",
        line_color="rgba(148,163,184,0.45)",
        line_width=1.2,
        annotation_text="~4.5% full-employment reference",
        annotation_position="top",
    )

    fig.update_layout(
        title=dict(text=f"Phillips Curve — Unemployment vs Inflation (last {len(df)} months)",
                   font_size=13),
        xaxis_title="Unemployment Rate (%)  ← tighter labor market | more slack →",
        yaxis_title="CPI Inflation YoY (%)  ↑ hotter prices",
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=480,
        margin=dict(l=40, r=20, t=50, b=50),
        legend=dict(orientation="h", y=-0.12),
        xaxis=dict(range=[x_min, x_max]),
        yaxis=dict(range=[y_min, y_max]),
    )
    return fig


def make_sparkline(values, color="#3b82f6", height=60):
    """Minimal sparkline — no axes, transparent background."""
    fig = go.Figure(go.Scatter(
        y=values, mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.12)",
    ))
    fig.update_layout(
        template=DARK_TEMPLATE,
        height=height, margin=dict(l=0,r=0,t=0,b=0),
        plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


def make_macro_tape_chart(chart_points, title, height=150):
    """
    Multi-session market chart for the pre-open tape cards.
    Shows the last 5 sessions with day separators and a title badge.
    """
    if not chart_points:
        fig = go.Figure()
        fig.update_layout(
            template=DARK_TEMPLATE,
            plot_bgcolor="#12233c",
            paper_bgcolor=PAPER_BG,
            height=height,
            margin=dict(l=0, r=0, t=8, b=0),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text="Chart unavailable",
                    x=0.5, y=0.5, xref="paper", yref="paper",
                    showarrow=False,
                    font=dict(color="#94a3b8", size=12),
                )
            ],
        )
        return fig

    df = pd.DataFrame(chart_points)
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["ts", "value"]).sort_values("ts")
    if df.empty:
        return make_macro_tape_chart([], title, height=height)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["ts"],
        y=df["value"],
        mode="lines",
        line=dict(color="#f8fafc", width=2),
        hovertemplate="%{x|%b %d, %H:%M}<br>%{y:,.4f}<extra></extra>",
        name=title,
    ))

    session_starts = []
    for session_date in pd.Index(df["ts"].dt.date).unique():
        day_slice = df[df["ts"].dt.date == session_date]
        if not day_slice.empty:
            session_starts.append(pd.Timestamp(day_slice["ts"].iloc[0]))

    for ts in session_starts[1:]:
        fig.add_vline(
            x=ts,
            line_color="rgba(245,158,11,0.35)",
            line_width=1,
            line_dash="dash",
        )

    tickvals = []
    ticktext = []
    for ts in session_starts:
        tickvals.append(ts)
        ticktext.append(pd.Timestamp(ts).strftime("%b %d"))

    fig.add_annotation(
        text=title,
        x=0.5, y=1.1, xref="paper", yref="paper",
        showarrow=False,
        bgcolor="#fbbf24",
        bordercolor="#fbbf24",
        font=dict(color="#0f172a", size=11, family="JetBrains Mono, monospace"),
        borderpad=6,
    )

    fig.update_layout(
        template=DARK_TEMPLATE,
        plot_bgcolor="#12233c",
        paper_bgcolor=PAPER_BG,
        height=height,
        margin=dict(l=0, r=0, t=22, b=10),
        showlegend=False,
        xaxis=dict(
            title="",
            tickvals=tickvals,
            ticktext=ticktext,
            showgrid=True,
            gridcolor="rgba(148,163,184,0.12)",
            tickfont=dict(color="#94a3b8", size=10),
            zeroline=False,
        ),
        yaxis=dict(
            title="",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.12)",
            tickfont=dict(color="#94a3b8", size=10),
            zeroline=False,
        ),
    )
    return fig


def make_inflation_bar_chart(fred):
    pairs = [
        ("CPIAUCSL","CPI YoY"), ("CPILFESL","Core CPI"),
        ("PCEPILFE","Core PCE"), ("T10YIE","10yr Breakeven"),
    ]
    labels, values, colors = [], [], []
    for sid, label in pairs:
        v = _get_val(fred, sid)
        if v is not None:
            labels.append(label); values.append(v)
            c = _status_color(sid, v) or "#3b82f6"
            colors.append(c)
    if not labels:
        return go.Figure()
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors, text=[f"{v:.2f}%" for v in values],
        textposition="outside",
    ))
    # Plotly does not accept 8-digit hex codes (which include an alpha channel).
    # Convert the desired color (green with transparency) to an rgba() string.
    fig.add_vline(
        x=2.0,
        line_dash="dash",
        line_color="rgba(52,211,153,0.56)",
        annotation_text="2% target",
        annotation_position="top right",
    )
    fig.update_layout(
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=200, margin=dict(l=10,r=60,t=10,b=10), xaxis_title="%",
        showlegend=False,
    )
    return fig


def make_gauge_chart(value, title, min_val=0, max_val=100,
                     thresholds=None, fmt="{:.1f}"):
    steps = []
    if thresholds:
        prev = min_val
        for threshold, color in thresholds:
            steps.append(dict(range=[prev, threshold], color=color))
            prev = threshold
        steps.append(dict(range=[prev, max_val], color=thresholds[-1][1]))

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value if value is not None else 0,
        title={"text": title, "font": {"size": 13}},
        number={"suffix": "", "font": {"size": 22}},
        gauge={
            "axis": {"range": [min_val, max_val], "tickcolor": "#94a3b8"},
            "bar": {"color": "#3b82f6"},
            "bgcolor": "#161b27",
            "bordercolor": "#1e2d3d",
            "steps": steps,
        }
    ))
    fig.update_layout(
        template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
        height=200, margin=dict(l=20,r=20,t=40,b=10),
    )
    return fig


def make_fear_greed_gauge(fg):
    v = fg.get("value") if fg else None
    return make_gauge_chart(
        value=v, title="Fear & Greed Index",
        min_val=0, max_val=100,
        thresholds=[(25,"#f87171"),(45,"#f97316"),(55,"#fbbf24"),(75,"#86efac"),(100,"#34d399")],
    )


def make_composite_gauge(value, title, subtitle="", low_label="Low", high_label="High"):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=0 if value is None else float(value),
        title={"text": f"{title}<br><span style='font-size:11px;color:#94a3b8'>{subtitle}</span>"},
        number={"suffix": "/100", "font": {"size": 26}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#94a3b8"},
            "bar": {"color": "#3b82f6" if value is None else "#34d399" if value < 40 else "#fbbf24" if value < 65 else "#f87171"},
            "bgcolor": CHART_BG,
            "bordercolor": "#1e2d3d",
            "steps": [
                {"range": [0, 40], "color": "rgba(52,211,153,0.18)"},
                {"range": [40, 65], "color": "rgba(251,191,36,0.18)"},
                {"range": [65, 100], "color": "rgba(248,113,113,0.20)"},
            ],
        },
    ))
    fig.add_annotation(text=low_label, x=0.14, y=0.06, xref="paper", yref="paper",
                       showarrow=False, font=dict(color="#94a3b8", size=10))
    fig.add_annotation(text=high_label, x=0.86, y=0.06, xref="paper", yref="paper",
                       showarrow=False, font=dict(color="#94a3b8", size=10))
    fig.update_layout(
        template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
        height=240, margin=dict(l=25, r=25, t=55, b=20),
    )
    return fig


def make_composite_history_chart(history, title, y_title="Score"):
    fig = go.Figure()
    if not history:
        fig.update_layout(
            title=f"{title} — insufficient history",
            template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
            height=260, margin=dict(l=40, r=20, t=45, b=30),
        )
        return fig
    dates = [h["date"] for h in history]
    values = [h["value"] for h in history]
    colors = ["#34d399" if v < 40 else "#fbbf24" if v < 65 else "#f87171" for v in values]
    fig.add_trace(go.Scatter(
        x=dates, y=values, mode="lines+markers",
        line=dict(color="#3b82f6", width=2),
        marker=dict(color=colors, size=7),
        hovertemplate="%{x}<br>Score: %{y:.1f}/100<extra></extra>",
    ))
    fig.add_hrect(y0=0, y1=40, fillcolor="rgba(52,211,153,0.08)", line_width=0)
    fig.add_hrect(y0=40, y1=65, fillcolor="rgba(251,191,36,0.08)", line_width=0)
    fig.add_hrect(y0=65, y1=100, fillcolor="rgba(248,113,113,0.10)", line_width=0)
    fig.update_layout(
        title=dict(text=title, font_size=13),
        yaxis=dict(title=y_title, range=[0, 100]),
        xaxis_title="Date",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=260, margin=dict(l=45, r=20, t=45, b=30),
    )
    return fig


def make_sahm_rule_gauge(fred):
    value = _get_val(fred, "SAHMREALTIME")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=0 if value is None else float(value),
        title={"text": "Sahm Rule Real-Time<br><span style='font-size:11px;color:#94a3b8'>0.5 = recession signal</span>"},
        number={"suffix": " pts", "font": {"size": 26}},
        gauge={
            "axis": {"range": [0, 1.2], "tickcolor": "#94a3b8"},
            "bar": {"color": "#94a3b8" if value is None else "#f87171" if value >= 0.5 else "#fbbf24" if value >= 0.3 else "#34d399"},
            "steps": [
                {"range": [0, 0.3], "color": "rgba(52,211,153,0.18)"},
                {"range": [0.3, 0.5], "color": "rgba(251,191,36,0.18)"},
                {"range": [0.5, 1.2], "color": "rgba(248,113,113,0.22)"},
            ],
            "threshold": {"line": {"color": "#f87171", "width": 3}, "thickness": 0.8, "value": 0.5},
            "bgcolor": CHART_BG,
            "bordercolor": "#1e2d3d",
        },
    ))
    fig.update_layout(
        template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
        height=240, margin=dict(l=25, r=25, t=55, b=20),
    )
    return fig


def make_fred_history_line_chart(fred, key, title, y_title="", color="#3b82f6", zero_line=False):
    history = _hist_points(fred, key, ascending=True)
    fig = go.Figure()
    if not history:
        fig.update_layout(
            title=f"{title} — insufficient data",
            template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
            height=260, margin=dict(l=45, r=20, t=45, b=30),
        )
        return fig
    fig.add_trace(go.Scatter(
        x=[h["date"] for h in history],
        y=[h["value"] for h in history],
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=5, color=color),
        hovertemplate="%{x}<br>%{y:.2f}<extra></extra>",
    ))
    if zero_line:
        fig.add_hline(y=0, line_color="#94a3b8", line_dash="dash", line_width=1)
    fig.update_layout(
        title=dict(text=title, font_size=13),
        xaxis_title="Date", yaxis_title=y_title,
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=260, margin=dict(l=45, r=20, t=45, b=30),
    )
    return fig


def make_credit_spread_comparison_chart(fred):
    hy = _hist_points(fred, "HY_SPREAD_HIST", ascending=True)
    ig = _hist_points(fred, "IG_SPREAD_HIST", ascending=True)
    fig = go.Figure()
    if hy:
        fig.add_trace(go.Scatter(
            x=[h["date"] for h in hy], y=[h["value"] for h in hy],
            mode="lines", name="HY Spread", line=dict(color="#f87171", width=2),
        ))
    if ig:
        fig.add_trace(go.Scatter(
            x=[h["date"] for h in ig], y=[h["value"] for h in ig],
            mode="lines", name="IG Spread", line=dict(color="#fbbf24", width=2),
        ))
    if not hy and not ig:
        fig.update_layout(title="Credit spread comparison — insufficient data")
    fig.update_layout(
        title=dict(text="HY vs IG Credit Spread Comparison", font_size=13),
        xaxis_title="Date", yaxis_title="Spread (bp)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=300, margin=dict(l=45, r=20, t=45, b=30),
        legend=dict(orientation="h", y=1.12),
    )
    return fig


def make_macro_surprise_chart(composite_data):
    rows = (composite_data or {}).get("macro_surprise", {}).get("components", [])
    fig = go.Figure()
    if not rows:
        fig.update_layout(
            title="Macro Surprise Index — insufficient data",
            template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
            height=260, margin=dict(l=45, r=20, t=45, b=30),
        )
        return fig
    values = [r["value"] for r in rows]
    fig.add_trace(go.Bar(
        x=[r["name"] for r in rows],
        y=values,
        marker_color=["#34d399" if v >= 0 else "#f87171" for v in values],
        text=[f"{v:+.2f}" for v in values],
        textposition="outside",
        hovertemplate="%{x}<br>Surprise proxy: %{y:+.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#94a3b8", line_width=1)
    fig.update_layout(
        title=dict(text="Macro Surprise Proxy — Actual Change vs Prior Release", font_size=13),
        yaxis_title="Relative change proxy",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=280, margin=dict(l=45, r=20, t=45, b=30),
    )
    return fig


def make_naaim_gauge(naaim):
    v = naaim.get("value") if naaim else None
    return make_gauge_chart(
        value=v, title="NAAIM Exposure",
        min_val=-50, max_val=200,
        thresholds=[(20,"#f87171"),(50,"#fbbf24"),(100,"#86efac"),(150,"#3b82f6"),(200,"#f97316")],
    )


def make_aaii_bar(aaii):
    if not aaii or not aaii.get("bull"):
        return go.Figure()
    vals = [aaii.get("bull",0), aaii.get("neutral",0), aaii.get("bear",0)]
    labels = ["Bulls", "Neutral", "Bears"]
    colors = ["#34d399","#fbbf24","#f87171"]
    fig = go.Figure(go.Bar(
        x=labels, y=vals, marker_color=colors,
        text=[f"{v:.1f}%" for v in vals], textposition="auto",
    ))
    fig.add_hline(y=50, line_dash="dash", line_color="#94a3b8", line_width=1)
    fig.update_layout(
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=220, margin=dict(l=10,r=10,t=30,b=10),
        title="AAII Investor Sentiment",
        yaxis_title="%",
    )
    return fig


def make_recession_prob_chart(fred):
    v = _get_val(fred, "RECPROUSM156N")
    return make_gauge_chart(
        value=v, title="US Recession Probability (%)",
        min_val=0, max_val=100,
        thresholds=[(15,"#34d399"),(30,"#86efac"),(50,"#fbbf24"),(70,"#f97316"),(100,"#f87171")],
    )


def make_credit_spreads_chart(fred):
    pairs = [
        ("BAMLH0A0HYM2","HY Spread (bp)"),
        ("BAMLC0A0CM","IG Spread (bp)"),
    ]
    labels, values, colors = [], [], []
    for sid, label in pairs:
        v = _get_val(fred, sid)
        if v is not None:
            labels.append(label); values.append(v)
            colors.append(_status_color(sid, v) or "#3b82f6")
    if not labels: return go.Figure()
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker_color=colors,
        text=[f"{v:.0f} bp" for v in values], textposition="auto",
    ))
    fig.update_layout(
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=200, margin=dict(l=10,r=10,t=30,b=10), title="Credit Spreads",
    )
    return fig


def make_regime_quadrant_chart(regime_state):
    credit_roc = regime_state.get("credit_roc")
    inflation_roc = regime_state.get("inflation_roc")
    fig = go.Figure()
    max_abs = max(abs(credit_roc or 0), abs(inflation_roc or 0), 25)
    axis_limit = round(max_abs * 1.25, 0)

    quadrants = [
        (-axis_limit, 0, 0, axis_limit, REGIME_COLORS["Reflation"], "Reflation", "left", "top"),
        (0, axis_limit, 0, axis_limit, REGIME_COLORS["Stagflation"], "Stagflation", "right", "top"),
        (-axis_limit, 0, -axis_limit, 0, REGIME_COLORS["Goldilocks"], "Goldilocks", "left", "bottom"),
        (0, axis_limit, -axis_limit, 0, REGIME_COLORS["Recession"], "Recession", "right", "bottom"),
    ]
    for x0, x1, y0, y1, color, label, xanchor, yanchor in quadrants:
        fig.add_shape(
            type="rect",
            x0=x0, x1=x1, y0=y0, y1=y1,
            line=dict(width=0),
            fillcolor=color,
            opacity=0.08,
            layer="below",
        )
        fig.add_annotation(
            x=x0 + 6 if xanchor == "left" else x1 - 6,
            y=y1 - 6 if yanchor == "top" else y0 + 6,
            text=label,
            showarrow=False,
            font=dict(size=11, color=color),
            xanchor=xanchor,
            yanchor=yanchor,
        )

    fig.add_hline(y=0, line_dash="dash", line_color="#64748b", line_width=1)
    fig.add_vline(x=0, line_dash="dash", line_color="#64748b", line_width=1)

    if credit_roc is not None and inflation_roc is not None:
        fig.add_trace(go.Scatter(
            x=[credit_roc],
            y=[inflation_roc],
            mode="markers+text",
            marker=dict(size=22, symbol="star", color=regime_state.get("color", "#fbbf24"),
                        line=dict(color="#e2e8f0", width=1)),
            text=[regime_state.get("regime", "Current")],
            textposition="top center",
            name="Current",
            hovertemplate="Credit ROC: %{x:.1f} bp<br>Inflation ROC: %{y:.1f} bp<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text="Macro Regime Quadrant", font_size=13),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=360,
        margin=dict(l=20, r=20, t=45, b=20),
        showlegend=False,
        xaxis=dict(title="Credit ROC (bp)", range=[-axis_limit, axis_limit], zeroline=False),
        yaxis=dict(title="Inflation ROC (bp)", range=[-axis_limit, axis_limit], zeroline=False),
    )
    return fig


def make_regime_history_chart(regime_state):
    history = regime_state.get("history", [])
    fig = go.Figure()
    if not history:
        fig.update_layout(
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=120,
            margin=dict(l=10, r=10, t=35, b=20),
            title=dict(text="Macro Regime History", font_size=13),
        )
        return fig

    df = pd.DataFrame(history)
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m", errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    segments = []
    start_idx = 0
    for i in range(1, len(df) + 1):
        if i == len(df) or df.loc[i, "regime"] != df.loc[start_idx, "regime"]:
            start_date = df.loc[start_idx, "date"]
            end_date = df.loc[i - 1, "date"] + pd.offsets.MonthBegin(1)
            segments.append(
                {
                    "regime": df.loc[start_idx, "regime"],
                    "color": df.loc[start_idx, "color"],
                    "start": start_date,
                    "end": end_date,
                }
            )
            start_idx = i

    for segment in segments:
        fig.add_shape(
            type="rect",
            x0=segment["start"],
            x1=segment["end"],
            y0=0,
            y1=1,
            fillcolor=segment["color"],
            opacity=0.9,
            line=dict(width=0),
        )
        midpoint = segment["start"] + (segment["end"] - segment["start"]) / 2
        fig.add_trace(go.Scatter(
            x=[midpoint],
            y=[0.5],
            mode="markers",
            marker=dict(size=18, color=segment["color"], opacity=0.01),
            hovertemplate=f"{segment['regime']}<br>{segment['start']:%Y-%m} → {segment['end']:%Y-%m}<extra></extra>",
            showlegend=False,
        ))

    fig.update_layout(
        title=dict(text="Macro Regime History", font_size=13),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=120,
        margin=dict(l=10, r=10, t=35, b=20),
        xaxis=dict(showgrid=False, tickformat="%Y-%m"),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[0, 1]),
    )
    return fig


def make_quality_rotation_chart(mkt):
    rotation = compute_quality_rotation(mkt)
    values = [rotation.get("hyg_vs_spy"), rotation.get("iwm_vs_spy")]
    labels = ["Credit Risk (HYG vs SPX)", "Small Caps (IWM vs SPX)"]
    if all(value is None for value in values):
        fig = go.Figure()
        fig.update_layout(
            title=dict(text="Capital Flow — Quality Rotation Signal (Daily)", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=220,
            margin=dict(l=20, r=20, t=45, b=20),
        )
        return fig
    colors = ["#34d399" if (value or 0) >= 0 else "#f87171" for value in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[("N/A" if value is None else f"{value:+.2f}%") for value in values],
        textposition="outside",
        hovertemplate="%{y}: %{x:+.2f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="#64748b", line_width=1)
    fig.update_layout(
        title=dict(text="Capital Flow — Quality Rotation Signal (Daily)", font_size=13),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=220,
        margin=dict(l=20, r=20, t=45, b=20),
        showlegend=False,
        xaxis_title="Relative Performance vs S&P 500 (%)",
        yaxis_title="",
    )
    return fig


def make_metals_chart(mkt):
    metals = [
        ("GC=F", "Gold"),
        ("SI=F", "Silver"),
        ("HG=F", "Copper"),
        ("PL=F", "Platinum"),
        ("PA=F", "Palladium"),
        ("ALI=F", "Aluminum"),
    ]
    labels, changes, colors, hover = [], [], [], []
    for sym, label in metals:
        d = mkt.get(sym) or {}
        chg = d.get("change_pct")
        value = d.get("value")
        if chg is None:
            continue
        labels.append(label)
        changes.append(chg)
        colors.append("#34d399" if chg >= 0 else "#f87171")
        hover.append(
            f"{label}<br>Price: {'N/A' if value is None else f'{value:,.2f}'}"
            f"<br>Chg: {chg:+.2f}%"
        )

    if not labels:
        return go.Figure()

    fig = go.Figure(go.Bar(
        x=labels,
        y=changes,
        marker_color=colors,
        text=[f"{c:+.2f}%" for c in changes],
        textposition="outside",
        hovertext=hover,
        hoverinfo="text",
        name="Daily % Change",
    ))
    fig.add_hline(y=0, line_dash="solid", line_color="#475569", line_width=1)
    fig.update_layout(
        title=dict(text="Metals — Daily % Change", font_size=13),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=280,
        margin=dict(l=20, r=20, t=45, b=30),
        yaxis_title="% Change",
        showlegend=False,
    )
    return fig


def make_energy_forward_curve_chart(futures_curve):
    fig = go.Figure()
    if futures_curve is None or futures_curve.empty:
        fig.update_layout(
            title=dict(text="Where the Market Thinks Oil Prices Are Heading — data unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=320,
        )
        return fig
    front_price = _safe_float(futures_curve.attrs.get("front_price"))
    if front_price is None:
        fig.update_layout(
            title=dict(text="Where the Market Thinks Oil Prices Are Heading — front price unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=320,
        )
        return fig
    curve = futures_curve.sort_values("months_out")
    curve = curve.copy()
    curve["delivery_label"] = curve["Leg2"].apply(lambda x: _energy_contract_month_label(x, long=True))
    curve["implied_price"] = front_price + curve["Latest"]
    fig.add_trace(go.Scatter(
        x=curve["delivery_label"],
        y=curve["implied_price"],
        mode="lines+markers",
        line=dict(color="#34d399", width=2.6),
        marker=dict(color="#fbbf24", size=6),
        fill="tozeroy",
        fillcolor="rgba(0,200,150,0.15)",
        hovertemplate="<b>%{customdata}</b><br>Delivery: %{x}<br>Implied price: $%{y:.2f}/bbl<extra></extra>",
        customdata=curve["contract_label"],
        name="Implied price",
    ))
    for marker_month in [6, 12, 24, 60]:
        row = _energy_spread_row(curve, marker_month)
        if row is not None:
            fig.add_trace(go.Scatter(
                x=[_energy_contract_month_label(row["Leg2"], long=True)],
                y=[front_price + float(row["Latest"])],
                mode="markers+text",
                marker=dict(size=12, color="#34d399", line=dict(color="#e2e8f0", width=1)),
                text=[f"{marker_month}M"],
                textposition="top center",
                name=f"{marker_month}M",
                hovertemplate=f"{marker_month}M<br>Implied price: $%{{y:.2f}}/bbl<extra></extra>",
            ))
    fig.add_hline(
        y=front_price,
        line_color="#94a3b8",
        line_width=1,
        line_dash="dash",
        annotation_text=f"Today ~${front_price:.2f}",
        annotation_position="top right",
    )
    fig.update_layout(
        title=dict(text="Where the Market Thinks Oil Prices Are Heading", font_size=13),
        xaxis_title="Delivery Month",
        yaxis_title="Price ($/bbl)",
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=360,
        margin=dict(l=50, r=30, t=45, b=45),
        showlegend=False,
    )
    return fig


def make_energy_price_range_chart(futures_curve):
    fig = go.Figure()
    if futures_curve is None or futures_curve.empty:
        fig.update_layout(
            title=dict(text="Oil Price Forecast — data unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=360,
        )
        return fig
    front_price = _safe_float(futures_curve.attrs.get("front_price"))
    if front_price is None:
        fig.update_layout(
            title=dict(text="Oil Price Forecast — front price unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=360,
        )
        return fig
    curve = futures_curve[(futures_curve["months_out"] >= 1) & (futures_curve["months_out"] <= 24)].copy()
    curve = curve.dropna(subset=["Latest", "High", "Low"]).sort_values("months_out")
    if curve.empty:
        fig.update_layout(
            title=dict(text="Oil Price Forecast — range data unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=360,
        )
        return fig
    curve["delivery_label"] = curve["Leg2"].apply(lambda x: _energy_contract_month_label(x, long=False))
    curve["implied_low"] = front_price + curve["Low"]
    curve["implied_high"] = front_price + curve["High"]
    curve["implied_latest"] = front_price + curve["Latest"]
    fig.add_trace(go.Scatter(
        x=curve["delivery_label"],
        y=curve["implied_low"],
        mode="lines",
        line=dict(color="rgba(148,163,184,0.35)", width=1),
        name="Low range",
        hovertemplate="Low: $%{y:.2f}/bbl<br>%{x}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=curve["delivery_label"],
        y=curve["implied_high"],
        mode="lines",
        line=dict(color="rgba(148,163,184,0.35)", width=1),
        fill="tonexty",
        fillcolor="rgba(59,130,246,0.18)",
        name="High range",
        hovertemplate="High: $%{y:.2f}/bbl<br>%{x}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=curve["delivery_label"],
        y=curve["implied_latest"],
        mode="lines+markers",
        line=dict(color="#fbbf24", width=2.4),
        marker=dict(color="#fbbf24", size=5),
        name="Latest implied price",
        hovertemplate="Latest: $%{y:.2f}/bbl<br>%{x}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Oil Price Forecast — Market's Expected Range", font_size=13),
        xaxis_title="Delivery Month",
        yaxis_title="Price ($/bbl)",
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=360,
        margin=dict(l=50, r=30, t=45, b=45),
        showlegend=False,
    )
    return fig


def make_energy_near_term_spreads_chart(futures_curve):
    fig = go.Figure()
    if futures_curve is None or futures_curve.empty:
        fig.update_layout(
            title=dict(text="How Much Extra Each Month Costs — data unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=320,
        )
        return fig
    front_price = _safe_float(futures_curve.attrs.get("front_price"))
    near = futures_curve[(futures_curve["months_out"] >= 1) & (futures_curve["months_out"] <= 18)].copy()
    near = near.sort_values("months_out")
    if near.empty:
        fig.update_layout(
            title=dict(text="How Much Extra Each Month Costs — near-term data unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=360,
        )
        return fig
    near["delivery_label"] = near["Leg2"].apply(lambda x: _energy_contract_month_label(x, long=False))
    near["monthly_step"] = near["Latest"].diff().fillna(near["Latest"])
    near["implied_price"] = (front_price + near["Latest"]) if front_price is not None else np.nan
    colors = ["#34d399" if step > 0 else "#f87171" if step < 0 else "#94a3b8" for step in near["monthly_step"]]
    fig.add_trace(go.Bar(
        x=near["delivery_label"],
        y=near["monthly_step"],
        marker_color=colors,
        text=[f"${v:+.2f}" for v in near["monthly_step"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Monthly step: $%{y:+.2f}/bbl<br>Implied price: $%{customdata:.2f}/bbl<extra></extra>",
        customdata=near["implied_price"],
    ))
    fig.add_hline(y=0, line_color="#94a3b8", line_width=1, line_dash="dash")
    try:
        peak = near.iloc[near["monthly_step"].abs().argmax()]
        fig.add_annotation(
            x=peak["delivery_label"],
            y=peak["monthly_step"],
            text="Biggest near-term storage premium",
            showarrow=True,
            arrowcolor="#fbbf24",
            font=dict(color="#fbbf24", size=11),
            yshift=20,
        )
    except Exception:
        pass
    fig.update_layout(
        title=dict(text="How Much Extra Each Month Costs (Near-Term)", font_size=13),
        xaxis_title="Delivery Month",
        yaxis_title="$/bbl gained vs prior month",
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=360,
        margin=dict(l=50, r=30, t=45, b=45),
        showlegend=False,
    )
    return fig


def make_energy_wti_brent_chart(futures_curve):
    fig = go.Figure()
    is_rows = futures_curve.attrs.get("intermarket", pd.DataFrame()) if futures_curve is not None else pd.DataFrame()
    if not isinstance(is_rows, pd.DataFrame) or is_rows.empty:
        fig.update_layout(
            title=dict(text="WTI vs Brent Intermarket Spread — data unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=300,
        )
        return fig
    plot_df = is_rows.dropna(subset=["Latest"]).head(24).copy()
    if plot_df.empty:
        fig.update_layout(
            title=dict(text="WTI vs Brent Intermarket Spread — data unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=300,
        )
        return fig
    plot_df["delivery_label"] = plot_df["Leg2"].apply(lambda x: _energy_contract_month_label(x, long=False))
    colors = ["#f87171" if v < 0 else "#34d399" for v in plot_df["Latest"]]
    fig.add_hrect(y0=-3, y1=0, fillcolor="rgba(148,163,184,0.14)", line_width=0)
    fig.add_hrect(y0=-7, y1=-3, fillcolor="rgba(251,191,36,0.16)", line_width=0)
    fig.add_hrect(y0=-50, y1=-7, fillcolor="rgba(248,113,113,0.18)", line_width=0)
    fig.add_trace(go.Bar(
        x=plot_df["delivery_label"],
        y=plot_df["Latest"],
        marker_color=colors,
        text=[f"${v:.2f}" for v in plot_df["Latest"]],
        textposition="outside",
        hovertemplate="WTI is $%{customdata[0]:.2f} cheaper than Brent for %{x}<br>Daily change: %{customdata[1]:+.2f}<extra></extra>",
        customdata=np.column_stack([plot_df["Latest"].abs(), plot_df["Change"].fillna(0)]),
    ))
    fig.add_trace(go.Scatter(
        x=[plot_df["delivery_label"].iloc[-1]],
        y=[-1.5],
        mode="text",
        text=["Normal discount"],
        textfont=dict(color="#94a3b8", size=11),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=[plot_df["delivery_label"].iloc[-1]],
        y=[-5],
        mode="text",
        text=["Growing discount, watch"],
        textfont=dict(color="#fbbf24", size=11),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=[plot_df["delivery_label"].iloc[-1]],
        y=[-8.5],
        mode="text",
        text=["Large US glut or pipeline stress"],
        textfont=dict(color="#f87171", size=11),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.add_hline(y=0, line_color="#94a3b8", line_width=1, line_dash="dash")
    fig.update_layout(
        title=dict(text="US Oil (WTI) vs Global Oil (Brent) — Price Gap", font_size=13),
        xaxis_title="Delivery Month",
        yaxis_title="WTI discount to Brent ($/bbl)",
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=360,
        margin=dict(l=50, r=30, t=45, b=70),
        showlegend=False,
    )
    return fig


def make_energy_signal_scorecard_chart(futures_curve):
    fig = go.Figure()
    if futures_curve is None or futures_curve.empty:
        fig.update_layout(
            title=dict(text="Oil Market 3-Signal Summary — data unavailable", font_size=13),
            template=DARK_TEMPLATE,
            plot_bgcolor=CHART_BG,
            paper_bgcolor=PAPER_BG,
            height=220,
        )
        return fig
    row_1m = _energy_spread_row(futures_curve, 1)
    row_6m = _energy_spread_row(futures_curve, 6)
    is_rows = futures_curve.attrs.get("intermarket", pd.DataFrame())
    front_contract = str(futures_curve.attrs.get("front_contract", "")).upper()
    front_is = None
    if isinstance(is_rows, pd.DataFrame) and not is_rows.empty:
        rows = is_rows[is_rows["Leg1"].astype(str).str.upper() == front_contract]
        if not rows.empty:
            front_is = rows.iloc[0]

    spread_1m = _safe_float(row_1m.get("Latest")) if row_1m is not None else None
    spread_6m = _safe_float(row_6m.get("Latest")) if row_6m is not None else None
    wti_brent = _safe_float(front_is.get("Latest")) if front_is is not None else None

    def _score_curve(v):
        if v is None:
            return 0, "#94a3b8", "N/A"
        if v < 0:
            return min(abs(v) * 12, 100), "#f87171", f"{v:+.2f} supply squeeze"
        return min(v * 12, 100), "#fbbf24" if v <= 5 else "#f87171", f"{v:+.2f} contango / oversupply"

    def _score_steep(v):
        if v is None:
            return 0, "#94a3b8", "N/A"
        if v > 15:
            return min(v * 4, 100), "#f87171", f"{v:+.2f} deep contango"
        if v >= 5:
            return min(v * 4, 100), "#fbbf24", f"{v:+.2f} moderate"
        return min(v * 4, 100), "#34d399", f"{v:+.2f} flat"

    def _score_gap(v):
        if v is None:
            return 0, "#94a3b8", "N/A"
        if v < -7:
            return min(abs(v) * 8, 100), "#f87171", f"{v:+.2f} large US discount"
        if v <= -3:
            return min(abs(v) * 8, 100), "#fbbf24", f"{v:+.2f} normal discount"
        return min(abs(v) * 8, 100), "#34d399", f"{v:+.2f} watch"

    rows = [
        ("Curve Shape", *_score_curve(spread_1m)),
        ("Steepness", *_score_steep(spread_6m)),
        ("WTI-Brent Gap", *_score_gap(wti_brent)),
    ]
    labels = [r[0] for r in rows]
    scores = [r[1] for r in rows]
    colors = [r[2] for r in rows]
    text = [r[3] for r in rows]
    fig.add_trace(go.Bar(
        x=scores,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=text,
        textposition="inside",
        insidetextanchor="middle",
        hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Oil Market 3-Signal Summary", font_size=13),
        xaxis=dict(title="", range=[0, 100], showticklabels=False),
        yaxis_title="",
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=220,
        margin=dict(l=110, r=30, t=45, b=25),
        showlegend=False,
    )
    return fig


def make_vix_term_chart(term_data):
    if not term_data:
        return go.Figure()
    expiries = [item["expiry"] for item in term_data]
    values = [item["iv"] for item in term_data]
    spread = values[-1] - values[0] if len(values) >= 2 else 0
    if spread > 2:
        structure_label = "Contango"
    elif spread > -2:
        structure_label = "Flat"
    else:
        structure_label = "Backwardation"
    colors = []
    for value in values:
        if value < 20:
            colors.append("#34d399")
        elif value <= 28:
            colors.append("#fbbf24")
        else:
            colors.append("#f87171")
    fig = go.Figure(go.Bar(
        x=values,
        y=expiries,
        orientation="h",
        marker_color=colors,
        text=[f"{value:.1f}" for value in values],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Implied Vol: %{x:.1f}<br><extra></extra>",
    ))
    fig.add_vline(
        x=20,
        line_dash="dash",
        line_color="#94a3b8",
        annotation_text="Fear Threshold (20)",
        annotation_position="top",
    )
    if term_data and term_data[0].get("backwardation"):
        fig.add_annotation(
            x=max(values),
            y=expiries[0],
            text="Backwardation",
            showarrow=False,
            xanchor="left",
            font=dict(color="#f87171", size=11),
        )
    fig.update_layout(
        title=dict(
            text=(
                "VIX Term Structure"
                f"<br><sup>9D→1Y spread: {spread:+.1f} vol pts | "
                f"Structure: {structure_label}</sup>"
            ),
            font_size=13,
        ),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=280,
        margin=dict(l=30, r=30, t=62, b=25),
        xaxis_title="Implied Volatility",
        yaxis_title="Expiry",
        showlegend=False,
    )
    return fig


def render_vix_term_structure_badge(term_data):
    if not term_data or len(term_data) < 2:
        return
    try:
        vix_9d = float(term_data[0]["iv"])
        vix_1y = float(term_data[-1]["iv"])
        spread = vix_1y - vix_9d
        if spread > 2:
            text = "✅ Contango — curve is normal, no near-term stress"
            color = "#34d399"
        elif spread > -2:
            text = "⚠️ Flat curve — monitor for inversion"
            color = "#fbbf24"
        else:
            text = "🔴 Backwardation — near-term fear spike detected"
            color = "#f87171"
        st.markdown(
            f'<div style="background:#161b27;border:1px solid {color};border-radius:10px;'
            f'padding:9px 12px;margin:4px 0 8px 0;color:{color};font-weight:700;'
            f'font-size:13px">{text}</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        return


def make_pcr_gauge(pcr_value):
    return make_gauge_chart(
        value=pcr_value,
        title="Put/Call Ratio",
        min_val=0.5,
        max_val=1.8,
        thresholds=[(0.8, "#34d399"), (1.1, "#fbbf24"), (1.8, "#f87171")],
    )


def make_skew_gauge(skew_value):
    return make_gauge_chart(
        value=skew_value,
        title="CBOE SKEW Index",
        min_val=100,
        max_val=160,
        thresholds=[(120, "#34d399"), (140, "#fbbf24"), (160, "#f87171")],
    )


def make_options_signals_bar(opts):
    def _normalize(value, low, high):
        if value is None:
            return None
        return max(0, min(100, (float(value) - low) / (high - low) * 100))

    metrics = [
        ("PCR", _normalize(opts.get("pcr"), 0.5, 1.8), opts.get("pcr")),
        ("VVIX", _normalize(opts.get("vvix"), 80, 140), opts.get("vvix")),
        ("GVZ", _normalize(opts.get("gvz"), 15, 40), opts.get("gvz")),
        ("Skew Proxy", _normalize(opts.get("skew_proxy"), -5, 10), opts.get("skew_proxy")),
    ]
    labels, scores, colors, text = [], [], [], []
    for label, score, raw in metrics:
        if score is None:
            continue
        labels.append(label)
        scores.append(score)
        colors.append("#34d399" if score < 40 else "#fbbf24" if score < 70 else "#f87171")
        if raw is None:
            text.append("N/A")
        elif label == "Skew Proxy":
            text.append(f"{raw:+.2f}")
        else:
            text.append(f"{raw:.2f}")
    if not labels:
        return go.Figure()
    fig = go.Figure(go.Bar(
        x=scores,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=text,
        textposition="outside",
    ))
    fig.update_layout(
        title=dict(text="Options Risk Signals", font_size=13),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=240,
        margin=dict(l=30, r=40, t=45, b=25),
        xaxis_title="Normalized Risk Score",
        showlegend=False,
    )
    return fig



def _option_key_strike_map(chain_data):
    mapping = {}
    for row in chain_data.get("key_strikes", []) or []:
        try:
            mapping[float(row.get("strike"))] = {
                "label": str(row.get("label", "key")).replace("_", " ").title(),
                "color": row.get("color", "#94a3b8"),
            }
        except Exception:
            continue
    return mapping


def make_oi_profile_chart(chain_data):
    """Call/Put Open Interest wall chart by strike — mirrored tornado layout."""
    oi = chain_data.get("oi_profile", [])
    spot = chain_data.get("spot")
    if not oi:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="OI Profile — data unavailable", height=300)
        return fig

    df = pd.DataFrame(oi)
    df = df.sort_values("strike")
    strike_map = _option_key_strike_map(chain_data)
    df["call_oi_k"] = df["call_oi"] / 1000.0
    df["put_oi_k"] = df["put_oi"] / 1000.0

    x_cap = max(float(df["call_oi_k"].max() if not df.empty else 0), float(df["put_oi_k"].max() if not df.empty else 0))
    x_cap = max(5.0, x_cap * 1.15)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["strike"], x=-df["put_oi_k"], orientation="h",
        name="Puts (OI)", marker_color="#f87171",
        hovertemplate="Strike %{y:.0f}<br>Put OI: %{customdata:.1f}K<br>Interpretation: defensive positioning<extra></extra>",
        customdata=df["put_oi_k"],
    ))
    fig.add_trace(go.Bar(
        y=df["strike"], x=df["call_oi_k"], orientation="h",
        name="Calls (OI)", marker_color="#34d399",
        hovertemplate="Strike %{y:.0f}<br>Call OI: %{x:.1f}K<br>Interpretation: upside positioning<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#475569", line_width=1.2)
    if spot:
        fig.add_hline(
            y=spot, line_dash="dash", line_color="#fbbf24", line_width=2,
            annotation_text=f"<b>Spot {spot:.2f}</b>", annotation_position="right"
        )

    for strike, meta in strike_map.items():
        fig.add_hline(y=strike, line_dash="dot", line_color=meta["color"], line_width=1.2, opacity=0.75)

    top_labels = []
    for _, row in df.nlargest(3, "combined_oi").iterrows():
        side = "Call Wall" if row["call_oi"] >= row["put_oi"] else "Put Wall"
        value = max(float(row["call_oi_k"]), float(row["put_oi_k"]))
        x_pos = value if side == "Call Wall" else -value
        align = "left" if side == "Call Wall" else "right"
        top_labels.append((float(row["strike"]), x_pos, side, align))
    for strike, x_pos, side, align in top_labels:
        fig.add_annotation(
            x=x_pos, y=strike,
            text=f"📌 {strike:.0f} — {side}",
            showarrow=False,
            xanchor=align,
            yanchor="bottom",
            font=dict(color="#e2e8f0", size=11),
            bgcolor="rgba(15,23,42,0.85)",
            bordercolor="#1e2d3d",
            borderwidth=1,
        )
    expiry = chain_data.get("expiry", "")
    fig.update_layout(
        barmode="relative",
        title=dict(text=f"OI Wall — {expiry} (Calls right / Puts left)", font_size=13),
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=370,
        margin=dict(l=70, r=30, t=50, b=25),
        xaxis=dict(
            title="Open Interest (thousands)",
            range=[-x_cap, x_cap],
            tickvals=[-x_cap, -x_cap / 2, 0, x_cap / 2, x_cap],
            ticktext=[f"{x_cap:.0f}", f"{x_cap/2:.0f}", "0", f"{x_cap/2:.0f}", f"{x_cap:.0f}"],
        ),
        yaxis_title="Strike",
        legend=dict(orientation="h", y=1.08),
    )
    return fig


def make_iv_smile_chart(chain_data):
    """Implied Volatility smile across strikes with skew band and outlier filtering."""
    calls_sm = chain_data.get("calls_smile", [])
    puts_sm  = chain_data.get("puts_smile", [])
    if not calls_sm and not puts_sm:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="IV Smile — data unavailable", height=260)
        return fig

    def _clean(df):
        if df.empty:
            return df
        df = df.copy()
        df["iv_pct"] = df["impliedVolatility"] * 100.0
        lo = max(0.1, float(df["iv_pct"].quantile(0.05)) * 0.5)
        hi = float(df["iv_pct"].quantile(0.97)) * 1.35
        df = df[(df["iv_pct"] >= lo) & (df["iv_pct"] <= hi)]
        return df.sort_values("moneyness")

    fig = go.Figure()
    c_df = pd.DataFrame()
    p_df = pd.DataFrame()
    if calls_sm:
        c_df = _clean(pd.DataFrame(calls_sm))
        fig.add_trace(go.Scatter(
            x=c_df["moneyness"], y=c_df["iv_pct"],
            mode="lines+markers", name="Calls IV",
            line=dict(color="#34d399", width=2),
            hovertemplate="Call %{x:.1f}% moneyness<br>IV: %{y:.1f}%<extra></extra>",
        ))
    if puts_sm:
        p_df = _clean(pd.DataFrame(puts_sm))
        fig.add_trace(go.Scatter(
            x=p_df["moneyness"], y=p_df["iv_pct"],
            mode="lines+markers", name="Puts IV",
            line=dict(color="#f87171", width=2),
            hovertemplate="Put %{x:.1f}% moneyness<br>IV: %{y:.1f}%<extra></extra>",
        ))

    if not c_df.empty and not p_df.empty:
        x_min = max(float(c_df["moneyness"].min()), float(p_df["moneyness"].min()))
        x_max = min(float(c_df["moneyness"].max()), float(p_df["moneyness"].max()))
        if x_max > x_min:
            grid = np.linspace(x_min, x_max, 80)
            call_interp = np.interp(grid, c_df["moneyness"], c_df["iv_pct"])
            put_interp = np.interp(grid, p_df["moneyness"], p_df["iv_pct"])
            fig.add_trace(go.Scatter(
                x=grid, y=call_interp,
                mode="lines", line=dict(color="rgba(0,0,0,0)"),
                showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=grid, y=put_interp,
                mode="lines",
                line=dict(color="rgba(0,0,0,0)"),
                fill="tonexty",
                fillcolor="rgba(245,158,11,0.10)",
                name="Skew Band",
                hovertemplate="Skew band<br>Moneyness %{x:.1f}%<br>Put premium: %{customdata:.1f} vol pts<extra></extra>",
                customdata=(put_interp - call_interp),
            ))

    fig.add_vline(x=0, line_dash="dash", line_color="#fbbf24", line_width=1,
                  annotation_text="ATM", annotation_position="top")
    strike_map = _option_key_strike_map(chain_data)
    for strike, meta in strike_map.items():
        if chain_data.get("spot"):
            moneyness = (strike / chain_data["spot"] - 1.0) * 100.0
            fig.add_vline(x=moneyness, line_dash="dot", line_color=meta["color"], line_width=1, opacity=0.6)

    try:
        all_df = pd.concat([c_df.assign(side="Call"), p_df.assign(side="Put")], ignore_index=True)
        cheap = all_df.loc[all_df["iv_pct"].idxmin()]
        rich = p_df.loc[p_df["iv_pct"].idxmax()] if not p_df.empty else all_df.loc[all_df["iv_pct"].idxmax()]
        fig.add_annotation(
            x=float(cheap["moneyness"]), y=float(cheap["iv_pct"]),
            text="Cheapest vol",
            showarrow=True, arrowcolor="#94a3b8",
            font=dict(color="#94a3b8", size=11),
            bgcolor="rgba(15,23,42,0.85)",
        )
        fig.add_annotation(
            x=float(rich["moneyness"]), y=float(rich["iv_pct"]),
            text="Expensive protection",
            showarrow=True, arrowcolor="#f87171",
            font=dict(color="#f87171", size=11),
            bgcolor="rgba(15,23,42,0.85)",
        )
    except Exception:
        pass

    expiry = chain_data.get("expiry", "")
    skew_25d = chain_data.get("skew_25d")
    title_text = f"IV Smile — {expiry}"
    if skew_25d is not None:
        title_text += f" · 25Δ Put Skew: {skew_25d:+.1f} vol pts"
    fig.update_layout(
        title=dict(text=title_text, font_size=13),
        xaxis_title="Moneyness (% from spot)",
        yaxis_title="Implied Volatility (%)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=300,
        margin=dict(l=40, r=20, t=45, b=30),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def make_gex_chart(chain_data):
    """
    Dealer Gamma Exposure (GEX) by strike.
    Positive = dealers long gamma (absorb moves); Negative = dealers short gamma (amplify moves).
    Source: Computed from yfinance options chain using Black-Scholes gamma.
    """
    gex_data   = chain_data.get("gex", [])
    spot       = chain_data.get("spot")
    total_gex  = chain_data.get("total_gex", 0)
    if not gex_data:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="GEX — data unavailable", height=280)
        return fig

    df = pd.DataFrame(gex_data).sort_values("strike")
    from plotly.subplots import make_subplots

    df["gex_m"] = df["gex"] / 1e6
    colors = ["#34d399" if v >= 0 else "#f87171" for v in df["gex_m"]]
    strike_map = _option_key_strike_map(chain_data)
    near_df = df.copy()
    if spot:
        near_df = df[(df["strike"] >= spot - 15) & (df["strike"] <= spot + 15)].copy()
        if near_df.empty:
            near_df = df.copy()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.72, 0.28],
        vertical_spacing=0.06,
        subplot_titles=("Full strike map", "Zoom: ±15 strikes around spot"),
    )
    fig.add_trace(go.Bar(
        x=df["strike"], y=df["gex_m"],
        marker_color=colors,
        hovertemplate="Strike %{x:.0f}<br>GEX: %{y:.2f}M<br>Interpretation: %{customdata}<extra></extra>",
        customdata=["Dealers dampen moves here" if v >= 0 else "Dealers amplify moves here" for v in df["gex_m"]],
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=near_df["strike"], y=near_df["gex_m"],
        marker_color=["#34d399" if v >= 0 else "#f87171" for v in near_df["gex_m"]],
        hovertemplate="Strike %{x:.0f}<br>GEX: %{y:.2f}M<extra></extra>",
        showlegend=False,
    ), row=2, col=1)

    y_min = min(float(df["gex_m"].min()), float(near_df["gex_m"].min()), 0.0)
    y_max = max(float(df["gex_m"].max()), float(near_df["gex_m"].max()), 0.0)
    for row in (1, 2):
        fig.add_hrect(y0=min(0, y_min * 1.05), y1=0, fillcolor="rgba(248,113,113,0.08)", line_width=0, row=row, col=1)
        fig.add_hrect(y0=0, y1=max(0, y_max * 1.05), fillcolor="rgba(52,211,153,0.08)", line_width=0, row=row, col=1)
        fig.add_hline(y=0, line_color="#475569", line_width=1, row=row, col=1)
        if spot:
            fig.add_vline(x=spot, line_dash="dash", line_color="#fbbf24", line_width=1.8, row=row, col=1)
        for strike, meta in strike_map.items():
            fig.add_vline(x=strike, line_dash="dot", line_color=meta["color"], line_width=1.2, opacity=0.7, row=row, col=1)

    regime = "🟢 Positive (Dampening)" if total_gex >= 0 else "🔴 Negative (Amplifying)"
    fig.update_layout(
        title=dict(text=f"Gamma Exposure (GEX) by Strike — Net: {regime}", font_size=12),
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=420,
        margin=dict(l=50, r=20, t=60, b=35),
        showlegend=False,
    )
    fig.update_yaxes(title_text="GEX ($M)", row=1, col=1)
    fig.update_yaxes(title_text="Near Spot", row=2, col=1)
    fig.update_xaxes(title_text="Strike", row=2, col=1)
    return fig


def make_gex_flip_timeline_chart(chain_data):
    """
    Historical GEX timeline is unavailable from Yahoo's live chain feed because it does
    not publish prior-day chain snapshots. The dashboard exposes that limitation directly.
    """
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.54, xref="paper", yref="paper",
        text=(
            "Historical GEX flip timeline is not available from the current free source.<br>"
            "Yahoo provides the live chain, but not prior daily chain snapshots.<br>"
            "To show a 20–30 session GEX timeline, this script has to save daily snapshots going forward."
        ),
        showarrow=False,
        font=dict(color="#94a3b8", size=12),
        align="center",
    )
    fig.update_layout(
        title=dict(text="GEX Flip Timeline (source-limited)", font_size=13),
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=230, margin=dict(l=30, r=30, t=45, b=25),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def make_iv_term_structure_chart(chain_data):
    term = chain_data.get("atm_term", [])
    if not term:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="IV Term Structure — data unavailable", height=260)
        return fig

    df = pd.DataFrame(term).sort_values("dte")
    colors = ["#f59e0b" if row["is_current"] else "#3b82f6" for _, row in df.iterrows()]
    fig = go.Figure()
    fig.add_hrect(y0=0, y1=20, fillcolor="rgba(52,211,153,0.06)", line_width=0)
    fig.add_hrect(y0=20, y1=35, fillcolor="rgba(245,158,11,0.06)", line_width=0)
    fig.add_hrect(y0=35, y1=max(40, float(df["atm_iv"].max()) * 1.1), fillcolor="rgba(248,113,113,0.08)", line_width=0)
    fig.add_trace(go.Scatter(
        x=df["dte"], y=df["atm_iv"],
        mode="lines+markers+text",
        text=[r["expiry"][5:] for _, r in df.iterrows()],
        textposition="top center",
        line=dict(color="#3b82f6", width=2),
        marker=dict(size=10, color=colors, line=dict(width=1, color="#0f1117")),
        hovertemplate="Expiry %{customdata}<br>DTE %{x}<br>ATM IV %{y:.1f}%<extra></extra>",
        customdata=df["expiry"],
        name="ATM IV",
    ))
    current = df[df["is_current"]]
    if not current.empty:
        fig.add_annotation(
            x=float(current["dte"].iloc[0]),
            y=float(current["atm_iv"].iloc[0]),
            text="Current expiry",
            showarrow=True,
            arrowcolor="#f59e0b",
            font=dict(color="#f59e0b", size=11),
        )
    fig.update_layout(
        title=dict(text="Volatility Term Structure — ATM IV by Expiry", font_size=13),
        xaxis_title="Days to Expiry",
        yaxis_title="ATM IV (%)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=280, margin=dict(l=45, r=20, t=50, b=35),
        showlegend=False,
    )
    return fig


def make_gex_heatmap_chart(chain_data):
    rows = chain_data.get("gex_heatmap", [])
    spot = chain_data.get("spot")
    if not rows:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Gamma Heatmap — data unavailable", height=280)
        return fig

    df = pd.DataFrame(rows)
    pivot = df.pivot_table(index="strike", columns="expiry", values="gex", aggfunc="sum").sort_index()
    z = pivot.values / 1e6
    max_abs = np.nanmax(np.abs(z)) if z.size else 1.0
    max_abs = max(max_abs, 1.0)
    fig = go.Figure(go.Heatmap(
        x=list(pivot.columns),
        y=list(pivot.index),
        z=z,
        zmin=-max_abs,
        zmax=max_abs,
        colorscale=[
            [0.0, "#7f1d1d"],
            [0.25, "#f87171"],
            [0.5, "#111827"],
            [0.75, "#34d399"],
            [1.0, "#065f46"],
        ],
        colorbar=dict(title="GEX ($M)"),
        hovertemplate="Expiry %{x}<br>Strike %{y:.0f}<br>GEX %{z:.2f}M<extra></extra>",
    ))
    if spot:
        fig.add_trace(go.Scatter(
            x=list(pivot.columns), y=[spot] * len(pivot.columns),
            mode="lines+markers",
            line=dict(color="#fbbf24", width=2, dash="dash"),
            marker=dict(size=5, color="#fbbf24"),
            name=f"Spot {spot:.2f}",
            hovertemplate="Spot %{y:.2f}<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text="Gamma Exposure Heatmap — Strike × Expiry", font_size=13),
        xaxis_title="Expiry",
        yaxis_title="Strike",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=320, margin=dict(l=50, r=20, t=45, b=35),
    )
    return fig


def make_pc_ratio_by_strike_chart(chain_data):
    rows = chain_data.get("pc_ratio_by_strike", [])
    spot = chain_data.get("spot")
    if not rows:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Put/Call OI Ratio — data unavailable", height=260)
        return fig

    df = pd.DataFrame(rows).sort_values("strike")
    df["ratio"] = df["pc_ratio"].clip(upper=4)
    colors = [
        "#f87171" if v > 1.5 else "#fbbf24" if v >= 0.8 else "#34d399"
        for v in df["ratio"]
    ]
    fig = go.Figure(go.Bar(
        x=df["strike"], y=df["ratio"],
        marker_color=colors,
        hovertemplate="Strike %{x:.0f}<br>Put/Call OI Ratio %{y:.2f}<br>Interpretation: %{customdata}<extra></extra>",
        customdata=[
            "Put-heavy defensive positioning" if v > 1.5 else
            "Balanced positioning" if v >= 0.8 else
            "Call-heavy upside positioning"
            for v in df["ratio"]
        ],
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color="#94a3b8", line_width=1.2, annotation_text="Neutral")
    if spot:
        fig.add_vline(x=spot, line_dash="dot", line_color="#fbbf24", line_width=1.5)
    fig.update_layout(
        title=dict(text="Put/Call OI Ratio by Strike", font_size=13),
        xaxis_title="Strike",
        yaxis_title="P/C OI Ratio",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=280, margin=dict(l=40, r=20, t=45, b=30),
        showlegend=False,
    )
    return fig


def make_max_pain_chart(chain_data):
    oi = chain_data.get("oi_profile", [])
    pain = chain_data.get("pinning_curve", [])
    spot = chain_data.get("spot")
    max_pain = chain_data.get("max_pain")
    if not oi or not pain:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Max Pain — data unavailable", height=280)
        return fig

    from plotly.subplots import make_subplots

    oi_df = pd.DataFrame(oi).sort_values("strike")
    pain_df = pd.DataFrame(pain).sort_values("strike")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=oi_df["strike"], y=oi_df["combined_oi"] / 1000.0,
        marker_color="#3b82f6",
        opacity=0.45,
        name="Total OI (K)",
        hovertemplate="Strike %{x:.0f}<br>Total OI %{y:.1f}K<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=pain_df["strike"], y=pain_df["pinning_score"] * 100.0,
        mode="lines+markers",
        line=dict(color="#fbbf24", width=2),
        name="Pinning Pressure Proxy",
        hovertemplate="Strike %{x:.0f}<br>Pinning score %{y:.1f}<extra></extra>",
    ), secondary_y=True)
    if max_pain is not None:
        fig.add_vline(x=max_pain, line_dash="dash", line_color="#f87171", line_width=2, annotation_text=f"Max Pain {max_pain:.0f}")
    if spot:
        fig.add_vline(x=spot, line_dash="dot", line_color="#fbbf24", line_width=1.5, annotation_text=f"Spot {spot:.2f}")
    fig.update_layout(
        title=dict(text="Max Pain & Dealer Pinning Proxy", font_size=13),
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=300, margin=dict(l=45, r=45, t=50, b=35),
        legend=dict(orientation="h", y=1.1),
        xaxis_title="Strike",
    )
    fig.update_yaxes(title_text="Total OI (K)", secondary_y=False)
    fig.update_yaxes(title_text="Pinning Score", secondary_y=True, range=[0, 105])
    return fig


def make_delta_flow_chart(chain_data):
    rows = chain_data.get("delta_flow", [])
    spot = chain_data.get("spot")
    if not rows:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Dealer Hedge Flow — data unavailable", height=260)
        return fig

    df = pd.DataFrame(rows).sort_values("strike")
    df["flow_m"] = df["delta_notional"] / 1e6
    colors = ["#34d399" if v >= 0 else "#f87171" for v in df["flow_m"]]
    fig = go.Figure(go.Bar(
        x=df["strike"], y=df["flow_m"],
        marker_color=colors,
        hovertemplate="Strike %{x:.0f}<br>Dealer hedge flow %{y:.2f}M<br>%{customdata}<extra></extra>",
        customdata=[
            "Positive = dealers need to buy / supportive" if v >= 0 else
            "Negative = dealers need to sell / pressure"
            for v in df["flow_m"]
        ],
    ))
    fig.add_hline(y=0, line_color="#475569", line_width=1)
    if spot:
        fig.add_vline(x=spot, line_dash="dash", line_color="#fbbf24", line_width=1.5)
    fig.update_layout(
        title=dict(text="Delta-Adjusted OI — Dealer Hedge Flow Estimate", font_size=13),
        xaxis_title="Strike",
        yaxis_title="Estimated Hedge Flow ($M)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=280, margin=dict(l=45, r=20, t=45, b=30),
        showlegend=False,
    )
    return fig


def make_pcr_history_chart(pcr_hist):
    """
    30-day Put/Call Ratio history with bearish/extreme threshold lines.
    Source: CBOE daily statistics (scraped) or CBOE CDN CSV.
    """
    if not pcr_hist:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="PCR History — data unavailable (CBOE scrape failed)", height=220)
        return fig

    dates  = [r["date"] for r in pcr_hist]
    values = [r["pcr"]  for r in pcr_hist]
    colors_fill = "rgba(251,191,36,0.15)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values,
        mode="lines+markers",
        line=dict(color="#fbbf24", width=2),
        fill="tozeroy", fillcolor=colors_fill,
        name="Equity PCR",
        hovertemplate="%{x}<br>PCR: %{y:.2f}",
    ))
    fig.add_hline(y=1.2, line_dash="dash", line_color="#f97316", line_width=1,
                  annotation_text="1.2 Bearish", annotation_position="right")
    fig.add_hline(y=1.5, line_dash="dash", line_color="#f87171", line_width=1,
                  annotation_text="1.5 Extreme", annotation_position="right")
    fig.add_hline(y=0.8, line_dash="dot",  line_color="#34d399", line_width=1,
                  annotation_text="0.8 Bullish", annotation_position="right")
    fig.update_layout(
        title=dict(text="Put/Call Ratio — 30D History (CBOE)", font_size=13),
        xaxis_title="Date", yaxis_title="PCR",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=220,
        margin=dict(l=40, r=70, t=45, b=30),
        showlegend=False,
    )
    return fig


def make_pcr_term_chart(chain_data):
    """PCR across expiry dates — from yfinance multi-expiry option chains."""
    pcr_term = chain_data.get("pcr_term", [])
    if not pcr_term:
        fig = go.Figure()
        fig.update_layout(
            template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG,
            title="PCR by Expiry — data unavailable",
            height=220,
        )
        return fig
    expiries = [r["expiry"] for r in pcr_term]
    values   = [r["pcr"]   for r in pcr_term]
    colors   = ["#f87171" if v > 1.2 else "#fbbf24" if v > 0.9 else "#34d399" for v in values]
    fig = go.Figure(go.Bar(
        x=expiries, y=values, marker_color=colors,
        text=[f"{v:.2f}" for v in values], textposition="outside",
        hovertemplate="%{x}<br>PCR: %{y:.2f}",
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color="#94a3b8", line_width=1)
    fig.update_layout(
        title=dict(text="PCR by Expiry (OI-based)", font_size=13),
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=220, margin=dict(l=30, r=20, t=45, b=30),
        xaxis_title="Expiry", yaxis_title="Put/Call OI Ratio",
        showlegend=False,
    )
    return fig


def make_liquidity_stress_chart(fred):
    """
    Dual-line chart: NFCI and STLFSI2 history (90 observations).
    Both are financial conditions / stress indices.
    """
    nfci_hist = fred.get("NFCI_HIST", [])
    stl_hist = fred.get("STLFSI2_HIST", [])
    fig = go.Figure()
    if nfci_hist:
        df = pd.DataFrame(nfci_hist, columns=["value", "date"]).dropna()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().sort_values("date")
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["value"],
            mode="lines", name="NFCI",
            line=dict(color="#3b82f6", width=2),
            hovertemplate="%{x|%Y-%m}<br>NFCI: %{y:.3f}",
        ))
    if stl_hist:
        df2 = pd.DataFrame(stl_hist, columns=["value", "date"]).dropna()
        df2["date"] = pd.to_datetime(df2["date"], errors="coerce")
        df2["value"] = pd.to_numeric(df2["value"], errors="coerce")
        df2 = df2.dropna().sort_values("date")
        fig.add_trace(go.Scatter(
            x=df2["date"], y=df2["value"],
            mode="lines", name="STLFSI2",
            line=dict(color="#fbbf24", width=2),
            hovertemplate="%{x|%Y-%m}<br>STLFSI2: %{y:.3f}",
        ))
    if not fig.data:
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Financial Conditions & Stress Indices — data unavailable", height=280)
        return fig
    fig.add_hline(y=0, line_dash="dash", line_color="#475569", line_width=1,
                  annotation_text="Neutral", annotation_position="right")
    fig.add_hline(y=1.0, line_dash="dot", line_color="#f87171", line_width=1,
                  annotation_text="Stress", annotation_position="right")
    fig.update_layout(
        title=dict(text="Financial Conditions & Stress Indices (90M)", font_size=13),
        xaxis_title="Date", yaxis_title="Index Level",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=280, margin=dict(l=40, r=70, t=45, b=30),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def make_yield_spread_history_chart(fred):
    """
    Line chart showing T10Y3M and T10Y2Y spread history.
    Inversion (negative) = recession risk signal.
    """
    t3m_hist = fred.get("T10Y3M_HIST", [])
    t2y_hist = fred.get("T10Y2Y_HIST", [])
    fig = go.Figure()
    for hist, name, color in [
        (t3m_hist, "10Y-3M", "#34d399"),
        (t2y_hist, "10Y-2Y", "#fbbf24"),
    ]:
        if hist:
            df = pd.DataFrame(hist, columns=["value", "date"]).dropna()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna().sort_values("date")
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["value"],
                mode="lines", name=name,
                line=dict(color=color, width=2),
                hovertemplate=f"%{{x|%Y-%m-%d}}<br>{name}: %{{y:.2f}}%",
            ))
    if not fig.data:
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Yield Spread History — data unavailable", height=280)
        return fig
    fig.add_hline(y=0, line_dash="dash", line_color="#f87171", line_width=1.5,
                  annotation_text="Inversion", annotation_position="right")
    fig.update_layout(
        title=dict(text="Yield Curve Spread History — Inversion = Recession Signal", font_size=13),
        xaxis_title="Date", yaxis_title="Spread (%)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=280, margin=dict(l=40, r=70, t=45, b=30),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def make_amihud_chart(amihud_data):
    """
    Line chart of rolling Amihud illiquidity ratio for SPY.
    Rising = market is becoming less liquid.
    """
    if not amihud_data or not amihud_data.get("series"):
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="Amihud Illiquidity data unavailable", height=220)
        return fig
    series = amihud_data["series"]
    dates = [s["date"] for s in series]
    values = [s["value"] for s in series]
    avg = sum(values) / len(values) if values else 0
    colors_fill = "rgba(251,191,36,0.12)"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values,
        mode="lines", name="Amihud Ratio",
        line=dict(color="#fbbf24", width=2),
        fill="tozeroy", fillcolor=colors_fill,
        hovertemplate="%{x}<br>Illiquidity: %{y:.6f}",
    ))
    fig.add_hline(y=avg, line_dash="dash", line_color="#94a3b8", line_width=1,
                  annotation_text=f"30D avg: {avg:.6f}", annotation_position="right")
    fig.update_layout(
        title=dict(text=f"Amihud Illiquidity Ratio ({amihud_data.get('ticker', 'SPY')}) — Higher = Less Liquid", font_size=12),
        xaxis_title="Date", yaxis_title="Illiquidity (×10⁻⁹)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=220, margin=dict(l=40, r=80, t=45, b=30), showlegend=False,
    )
    return fig


def make_ted_spread_chart(fred):
    """
    TED Spread history: rising = interbank funding stress.
    """
    ted_hist = fred.get("TEDRATE_HIST", [])
    if not ted_hist:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="TED Spread data unavailable", height=220)
        return fig
    df = pd.DataFrame(ted_hist, columns=["value", "date"]).dropna()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna().sort_values("date")
    if df.empty:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="TED Spread data unavailable", height=220)
        return fig

    y_max = max(1.6, float(df["value"].max()) + 0.35)

    def _zone_label(v):
        if v < 0.5:
            return "Normal"
        if v < 1.0:
            return "Watch Zone"
        return "Stress Zone"

    point_colors = [
        "#34d399" if v < 0.5 else "#fbbf24" if v < 1.0 else "#f87171"
        for v in df["value"]
    ]
    point_text = [f"{v:.2f}%" for v in df["value"]]

    fig = go.Figure()
    fig.add_hrect(y0=0.0, y1=0.5, fillcolor="rgba(52,211,153,0.08)", line_width=0, layer="below")
    fig.add_hrect(y0=0.5, y1=1.0, fillcolor="rgba(251,191,36,0.08)", line_width=0, layer="below")
    fig.add_hrect(y0=1.0, y1=y_max, fillcolor="rgba(248,113,113,0.08)", line_width=0, layer="below")

    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["value"],
        mode="lines+markers+text",
        line=dict(color="#cbd5e1", width=2.5),
        marker=dict(size=10, color=point_colors, line=dict(color="#0f172a", width=1.5)),
        text=point_text,
        textposition="top center",
        textfont=dict(size=10, color="#cbd5e1"),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.10)",
        customdata=np.array([[_zone_label(v)] for v in df["value"]], dtype=object),
        hovertemplate="%{x|%Y-%m-%d}<br>TED Spread: %{y:.2f}%<br>Zone: %{customdata[0]}<extra></extra>",
        name="TED Spread",
    ))

    peak = df.loc[df["value"].idxmax()]
    fig.add_annotation(
        x=peak["date"],
        y=float(peak["value"]),
        text="Peak in sample",
        showarrow=True,
        arrowhead=2,
        ax=0,
        ay=-40,
        bgcolor="rgba(15,23,42,0.92)",
        bordercolor="#334155",
        font=dict(color="#f8fafc", size=10),
    )

    fig.add_hline(y=0.5, line_dash="dash", line_color="#fbbf24", line_width=1.5,
                  annotation_text="Watch line · 0.5%", annotation_position="right")
    fig.add_hline(y=1.0, line_dash="dash", line_color="#f87171", line_width=1.5,
                  annotation_text="Stress line · 1.0%", annotation_position="right")
    fig.update_layout(
        title=dict(
            text="TED Spread — Interbank Funding Stress (90M)"
                 "<br><sup>Higher = more stress in bank-to-bank lending; above 1% signals elevated risk</sup>",
            font_size=13,
        ),
        xaxis_title="Observation Date",
        yaxis_title="Spread (%)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=280,
        margin=dict(l=40, r=105, t=70, b=40),
        showlegend=False,
        xaxis=dict(tickformat="%b %Y"),
        yaxis=dict(range=[0, y_max], dtick=0.5),
    )
    return fig


def make_cot_chart(cot_data, market_key="SP500_Emini"):
    """
    Bar chart of net non-commercial positioning for a given futures market.
    Green = net long, Red = net short.
    """
    if not cot_data or market_key not in cot_data:
        fig = go.Figure()
        fig.update_layout(
            template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
            title=f"COT data unavailable for {market_key}", height=240
        )
        return fig

    market = cot_data[market_key]
    history = market.get("history", [])
    label = market.get("label", market_key)

    if not history:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title=f"COT {label} — no history", height=240)
        return fig

    dates = [h["date"] for h in history]
    net_nc = [h["net_nc"] for h in history]
    net_lev = [h["net_lev"] for h in history]
    colors = ["#34d399" if v >= 0 else "#f87171" for v in net_nc]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=net_nc,
        marker_color=colors,
        name="Net Non-Commercial",
        hovertemplate="%{x}<br>Net Position: %{y:,.0f} contracts",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=net_lev,
        mode="lines+markers",
        name="Leveraged Funds",
        line=dict(color="#fbbf24", width=2, dash="dot"),
        hovertemplate="%{x}<br>Leveraged: %{y:,.0f}",
    ))
    fig.add_hline(y=0, line_color="#475569", line_width=1)
    fig.update_layout(
        title=dict(text=f"COT Positioning — {label} (Non-Commercial Net)", font_size=13),
        xaxis_title="Report Date", yaxis_title="Net Contracts",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=260, margin=dict(l=50, r=20, t=45, b=30),
        legend=dict(orientation="h", y=1.1),
        barmode="overlay",
    )
    return fig


def make_vrp_chart(vrp_data):
    """
    Area chart of VIX (implied vol) vs 20-day Realized Vol over 2 years.
    """
    if not vrp_data or not vrp_data.get("history"):
        fig = go.Figure()
        fig.update_layout(
            template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG,
            title="VRP data unavailable",
            height=260,
        )
        return fig

    history = vrp_data["history"]
    dates = [h["date"] for h in history]
    vix = [h["vix"] for h in history]
    rv20 = [h["rv20"] for h in history]
    vrp = [h["vrp"] for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=rv20,
        name="20d Realized Vol",
        line=dict(color="#94a3b8", width=1.5, dash="dot"),
        hovertemplate="RV20: %{y:.1f}%<br>%{x}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=vix,
        name="VIX (Implied Vol)",
        line=dict(color="#3b82f6", width=2),
        fill="tonexty",
        fillcolor="rgba(59,130,246,0.12)",
        hovertemplate="VIX: %{y:.1f}<br>%{x}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=dates,
        y=vrp,
        name="VRP (VIX − RV20)",
        marker_color=["#34d399" if v >= 0 else "#f87171" for v in vrp],
        opacity=0.45,
        yaxis="y2",
        hovertemplate="VRP: %{y:+.1f}pt<br>%{x}<extra></extra>",
    ))
    for level, color, dash in [(0, "#475569", "solid"), (10, "#fbbf24", "dot"), (25, "#f87171", "dot")]:
        fig.add_shape(
            type="line",
            xref="paper",
            yref="y2",
            x0=0,
            x1=1,
            y0=level,
            y1=level,
            line=dict(color=color, width=1, dash=dash),
            opacity=0.5,
        )
    fig.add_annotation(
        xref="paper",
        yref="y2",
        x=0.99,
        y=25,
        text="Extreme Fear Threshold",
        showarrow=False,
        font=dict(color="#f87171", size=11),
        xanchor="right",
        yanchor="bottom",
    )
    fig.update_layout(
        title=dict(text="Volatility Risk Premium — VIX vs 20-Day Realized Vol (SPY)", font_size=13),
        xaxis_title="Date",
        yaxis=dict(title="Volatility (%)", side="left"),
        yaxis2=dict(
            title="VRP (pts)",
            overlaying="y",
            side="right",
            showgrid=False,
            zeroline=True,
            zerolinecolor="#475569",
        ),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=300,
        margin=dict(l=50, r=60, t=45, b=30),
        legend=dict(orientation="h", y=1.12),
        barmode="overlay",
    )
    return fig


def make_gs_panic_gauge(panic_data):
    """
    Gauge chart for GS Panic Proxy score (0–10).
    """
    score = panic_data.get("score", 0) if panic_data else 0
    color = panic_data.get("color", "#94a3b8") if panic_data else "#94a3b8"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": "GS Panic Index Proxy", "font": {"size": 14, "color": "#e2e8f0"}},
        number={"font": {"size": 36, "color": color}, "suffix": "/10"},
        gauge={
            "axis": {
                "range": [0, 10],
                "tickvals": [0, 2, 4, 6, 8, 10],
                "tickfont": {"color": "#94a3b8", "size": 11},
            },
            "bar": {"color": color, "thickness": 0.25},
            "steps": [
                {"range": [0, 4], "color": "rgba(52,211,153,0.15)"},
                {"range": [4, 7], "color": "rgba(251,191,36,0.15)"},
                {"range": [7, 9], "color": "rgba(251,146,60,0.20)"},
                {"range": [9, 10], "color": "rgba(248,113,113,0.25)"},
            ],
            "threshold": {
                "line": {"color": "#f87171", "width": 3},
                "thickness": 0.8,
                "value": 9.0,
            },
            "bgcolor": CHART_BG,
            "bordercolor": "#1e2d3d",
        },
    ))
    fig.update_layout(
        template=DARK_TEMPLATE,
        paper_bgcolor=PAPER_BG,
        height=250,
        margin=dict(l=30, r=30, t=50, b=20),
    )
    return fig


def make_dispersion_chart(mkt):
    """
    KPI chart showing CBOE DSPX (Dispersion Index) and KCJ (Implied Correlation).
    """
    dspx_val = (mkt.get("^DSPX") or {}).get("value")
    kcj_val = (mkt.get("^KCJ") or {}).get("value")

    if dspx_val is None and kcj_val is None:
        fig = go.Figure()
        fig.add_annotation(
            text="DSPX / KCJ data unavailable — Yahoo Finance may not carry these tickers yet.<br>"
                 "Check back or add manually via Barchart / CBOE data portal.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color="#94a3b8", size=13),
            align="center",
        )
        fig.update_layout(
            template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG,
            height=180,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        return fig

    labels = []
    values = []
    colors = []

    if dspx_val is not None:
        labels.append("DSPX (Implied Dispersion)")
        values.append(round(float(dspx_val), 2))
        colors.append("#f87171" if float(dspx_val) >= 15 else "#fbbf24" if float(dspx_val) >= 10 else "#34d399")

    if kcj_val is not None:
        labels.append("KCJ (Implied Correlation)")
        values.append(round(float(kcj_val), 2))
        colors.append("#f87171" if float(kcj_val) >= 60 else "#fbbf24" if float(kcj_val) >= 40 else "#34d399")

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        text=[f"{v:.1f}" for v in values],
        textposition="outside",
        hovertemplate="%{x}<br>Value: %{y:.2f}<extra></extra>",
    ))

    if dspx_val is not None and kcj_val is not None:
        d = float(dspx_val)
        k = float(kcj_val)
        if d >= 15 and k < 40:
            regime_text = "⚠️ High Dispersion + Low Correlation = Hidden Chaos"
            regime_color = "#f87171"
        elif d < 10 and k >= 60:
            regime_text = "📊 Low Dispersion + High Correlation = Macro Dominance"
            regime_color = "#fbbf24"
        else:
            regime_text = "Mixed dispersion regime"
            regime_color = "#94a3b8"
        fig.add_annotation(
            text=regime_text,
            xref="paper",
            yref="paper",
            x=0.5,
            y=1.15,
            showarrow=False,
            font=dict(color=regime_color, size=12),
            align="center",
        )

    fig.update_layout(
        title=dict(text="Stock vs Index Dispersion & Correlation (CBOE)", font_size=13),
        yaxis_title="Index Value",
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=240,
        margin=dict(l=50, r=20, t=60, b=30),
    )
    return fig


def make_sentiment_radar(panic_data, vrp_data, fg, aaii, opts, skew_idx, mkt):
    """
    Radar chart showing all 8 sentiment framework indicators normalized 0–10.
    Higher score = more fear/stress.
    """
    def safe_score(val, low, high, invert=False):
        try:
            v = float(val)
            score = max(0.0, min(10.0, (v - low) / (high - low) * 10))
            return round(10 - score if invert else score, 2)
        except Exception:
            return 5.0

    vix_val = (mkt.get("^VIX") or {}).get("value")
    vvix_val = opts.get("vvix") if opts else None
    move_val = (mkt.get("^MOVE") or {}).get("value")
    fg_val = fg.get("value") if fg else None
    aaii_bear = aaii.get("bear") if aaii else None
    skew_val = skew_idx.get("value") if skew_idx else None
    vrp_val = vrp_data.get("vrp") if vrp_data else None
    panic_score = panic_data.get("score") if panic_data else None

    dimensions = [
        "VIX Level",
        "VVIX (Vol of Vol)",
        "Fear & Greed",
        "AAII Bearish %",
        "Put/Call Skew",
        "MOVE Index",
        "VRP (IV−RV)",
        "GS Panic Proxy",
    ]
    scores = [
        safe_score(vix_val, 10, 80),
        safe_score(vvix_val, 80, 180),
        safe_score(fg_val, 0, 100, invert=True),
        safe_score(aaii_bear, 15, 60),
        safe_score(skew_val, 100, 160),
        safe_score(move_val, 60, 200),
        safe_score(vrp_val, -5, 30),
        safe_score(panic_score, 0, 10),
    ]

    dimensions_closed = dimensions + [dimensions[0]]
    scores_closed = scores + [scores[0]]

    fig = go.Figure(go.Scatterpolar(
        r=scores_closed,
        theta=dimensions_closed,
        fill="toself",
        fillcolor="rgba(248,113,113,0.12)",
        line=dict(color="#f87171", width=2),
        name="Sentiment Fear Score",
        hovertemplate="%{theta}<br>Score: %{r:.1f}/10<extra></extra>",
    ))
    fig.add_trace(go.Scatterpolar(
        r=[5.0] * len(dimensions_closed),
        theta=dimensions_closed,
        mode="lines",
        line=dict(color="#475569", width=1, dash="dot"),
        name="Neutral (5.0)",
        hoverinfo="skip",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                tickvals=[2, 4, 6, 8, 10],
                tickfont=dict(color="#94a3b8", size=10),
                gridcolor="#1e2d3d",
            ),
            angularaxis=dict(
                tickfont=dict(color="#e2e8f0", size=11),
                gridcolor="#1e2d3d",
            ),
            bgcolor=CHART_BG,
        ),
        showlegend=True,
        legend=dict(orientation="h", y=-0.1, font=dict(color="#94a3b8")),
        title=dict(
            text="Sentiment Framework Radar — All 8 Indicators (0=Greed, 10=Extreme Fear)",
            font=dict(size=13, color="#e2e8f0"),
        ),
        template=DARK_TEMPLATE,
        paper_bgcolor=PAPER_BG,
        height=420,
        margin=dict(l=60, r=60, t=60, b=60),
    )
    return fig


def make_mmf_flow_chart(mmf_history):
    """
    Line chart of weekly money market fund inflows/outflows.
    """
    if not mmf_history:
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="MMF flow data unavailable", height=220)
        return fig

    inst = mmf_history.get("institutional", [])
    ret = mmf_history.get("retail", [])

    fig = go.Figure()
    for series, name, color in [(inst, "Institutional MMF", "#3b82f6"), (ret, "Retail MMF", "#fbbf24")]:
        if series:
            dates = [r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])[:10] for r in series]
            flows = [r["flow"] for r in series]
            bar_colors = ["#34d399" if v < 0 else "#f87171" for v in flows]
            fig.add_trace(go.Bar(
                x=dates, y=flows,
                name=name,
                marker_color=bar_colors if name == "Institutional MMF" else color,
                opacity=0.8 if name == "Retail MMF" else 1.0,
                hovertemplate=f"{name}<br>%{{x}}<br>Flow: $%{{y:,.1f}}B",
            ))

    fig.add_hline(y=0, line_color="#475569", line_width=1)
    fig.update_layout(
        title=dict(text="Money Market Fund Weekly Flows — Positive = Into Cash / Risk-Off", font_size=12),
        xaxis_title="Week", yaxis_title="Flow ($B)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=240, margin=dict(l=50, r=20, t=50, b=30),
        barmode="group",
        legend=dict(orientation="h", y=1.12),
    )
    return fig


def make_ici_flows_chart(ici_data):
    """
    Grouped bar chart of ICI equity vs bond fund weekly net flows.
    """
    if not ici_data or not ici_data.get("flows"):
        fig = go.Figure()
        fig.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                          title="ICI fund flow data unavailable", height=240)
        return fig

    flows = ici_data["flows"]
    dates = [f["date"] for f in flows]
    equity = [f.get("equity") for f in flows]
    bond = [f.get("bond") for f in flows]
    mm = [f.get("money_market") for f in flows]

    fig = go.Figure()
    if any(v is not None for v in equity):
        fig.add_trace(go.Bar(
            x=dates, y=equity, name="Equity Funds",
            marker_color=["#34d399" if (v or 0) >= 0 else "#f87171" for v in equity],
            hovertemplate="Equity: $%{y:,.1f}B<br>%{x}",
        ))
    if any(v is not None for v in bond):
        fig.add_trace(go.Bar(
            x=dates, y=bond, name="Bond Funds",
            marker_color="#3b82f6",
            opacity=0.75,
            hovertemplate="Bond: $%{y:,.1f}B<br>%{x}",
        ))
    if any(v is not None for v in mm):
        fig.add_trace(go.Scatter(
            x=dates, y=mm, name="Money Market",
            mode="lines+markers",
            line=dict(color="#fbbf24", width=2),
            hovertemplate="MM: $%{y:,.1f}B<br>%{x}",
        ))
    fig.add_hline(y=0, line_color="#475569", line_width=1)
    fig.update_layout(
        title=dict(text=f"ICI Fund Flows (Weekly) — {ici_data.get('source', 'ICI')}", font_size=13),
        xaxis_title="Week", yaxis_title="Net Flow ($B)",
        template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
        height=260, margin=dict(l=50, r=20, t=45, b=30),
        barmode="group",
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def make_cta_signal_chart(cta_model):
    """
    Horizontal bar chart of per-asset CTA normalized signal.
    -1 = fully short (bearish trend), +1 = fully long (bullish trend).
    Colors: green for long bias, red for short bias, grey near zero.
    """
    if not cta_model or not cta_model.get("assets"):
        fig = go.Figure()
        fig.update_layout(
            template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG,
            title="CTA model data unavailable",
            height=280,
        )
        return fig

    assets = cta_model["assets"]
    labels = [v["label"] for v in assets.values()]
    signals = [v["normalized"] for v in assets.values()]
    colors = [
        "#34d399" if s > 0.15 else "#f87171" if s < -0.15 else "#94a3b8"
        for s in signals
    ]

    fig = go.Figure(go.Bar(
        x=signals,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{s:+.2f}" for s in signals],
        textposition="outside",
        hovertemplate="%{y}<br>Signal: %{x:+.3f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#475569", line_width=1.5)
    fig.add_vline(x=0.5, line_color="#34d399", line_width=1, line_dash="dot", opacity=0.4)
    fig.add_vline(x=-0.5, line_color="#f87171", line_width=1, line_dash="dot", opacity=0.4)
    fig.update_layout(
        title=dict(
            text="CTA Momentum Model — Normalized Position Signal per Asset",
            font_size=13,
        ),
        xaxis=dict(title="Signal (−1 = Max Short → +1 = Max Long)", range=[-1.4, 1.4]),
        yaxis=dict(title=""),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=300,
        margin=dict(l=140, r=60, t=45, b=30),
    )
    return fig


def make_cta_history_chart(cta_model, ticker="SPY"):
    """
    Line chart of CTA normalized signal history for a given asset.
    Shows when the model crosses into long/short territory over time.
    """
    if not cta_model or ticker not in cta_model.get("assets", {}):
        fig = go.Figure()
        fig.update_layout(
            template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG,
            title=f"CTA history unavailable for {ticker}",
            height=220,
        )
        return fig

    history = cta_model["assets"][ticker].get("history", [])
    label = cta_model["assets"][ticker].get("label", ticker)

    if not history:
        fig = go.Figure()
        fig.update_layout(
            template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG,
            title=f"No CTA history for {ticker}",
            height=220,
        )
        return fig

    dates = [h["date"] for h in history]
    signals = [h["signal"] for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=signals,
        mode="lines",
        name="CTA Signal",
        line=dict(color="#3b82f6", width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.10)",
        hovertemplate="%{x}<br>Signal: %{y:+.3f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#475569", line_width=1.5)
    fig.add_hline(y=0.5, line_color="#34d399", line_width=1, line_dash="dot", opacity=0.5)
    fig.add_hline(y=-0.5, line_color="#f87171", line_width=1, line_dash="dot", opacity=0.5)
    fig.update_layout(
        title=dict(text=f"CTA Positioning History — {label} (Weekly, 52 weeks)", font_size=13),
        xaxis_title="Week",
        yaxis=dict(title="Normalized Signal", range=[-1.3, 1.3]),
        template=DARK_TEMPLATE,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=PAPER_BG,
        height=240,
        margin=dict(l=50, r=20, t=45, b=30),
    )
    return fig


def make_cta_ma_table(cta_model):
    """
    Render an HTML table showing price vs. key moving averages for each CTA-tracked asset.
    Green cell = price above MA (uptrend = CTA likely long).
    Red cell = price below MA (downtrend = CTA likely short).
    """
    if not cta_model or not cta_model.get("assets"):
        return "<p style='color:#94a3b8'>No CTA model data available.</p>"

    rows = ""
    for _, data in cta_model["assets"].items():
        def ma_cell(above, ma_val):
            bg = "rgba(52,211,153,0.15)" if above else "rgba(248,113,113,0.15)"
            color = "#34d399" if above else "#f87171"
            arrow = "▲" if above else "▼"
            return (
                f'<td style="background:{bg};color:{color};'
                f'text-align:center;padding:5px 10px;border-radius:4px;">'
                f"{arrow} {ma_val:,.2f}</td>"
            )

        sig = data["normalized"]
        sig_color = "#34d399" if sig > 0.15 else "#f87171" if sig < -0.15 else "#94a3b8"
        rows += (
            f"<tr>"
            f'<td style="color:#e2e8f0;padding:5px 10px;font-weight:600">{data["label"]}</td>'
            f'<td style="color:#94a3b8;text-align:right;padding:5px 10px">{data["price"]:,.2f}</td>'
            f'{ma_cell(data["above_short"], data["ma_short"])}'
            f'{ma_cell(data["above_medium"], data["ma_medium"])}'
            f'{ma_cell(data["above_long"], data["ma_long"])}'
            f'<td style="color:{sig_color};text-align:center;padding:5px 10px;font-weight:700">'
            f"{sig:+.2f}</td>"
            f'<td style="color:#94a3b8;text-align:center;padding:5px 10px">'
            f'{data["vol_annual"]:.1f}%</td>'
            f"</tr>"
        )

    return f"""
    <div style="overflow-x:auto;margin-top:8px">
    <table style="width:100%;border-collapse:collapse;font-size:13px;background:#161b27;border-radius:8px">
      <thead>
        <tr style="border-bottom:1px solid #1e2d3d">
          <th style="color:#94a3b8;padding:8px 10px;text-align:left">Asset</th>
          <th style="color:#94a3b8;padding:8px 10px;text-align:right">Price</th>
          <th style="color:#94a3b8;padding:8px 10px;text-align:center">20d MA</th>
          <th style="color:#94a3b8;padding:8px 10px;text-align:center">63d MA</th>
          <th style="color:#94a3b8;padding:8px 10px;text-align:center">252d MA</th>
          <th style="color:#94a3b8;padding:8px 10px;text-align:center">Signal</th>
          <th style="color:#94a3b8;padding:8px 10px;text-align:center">Ann. Vol</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    </div>
    """


def compute_institutional_participation_score(cot_data, ici_data, mmf_history, fred):
    """
    Composite Institutional Participation Score.
    Higher score = institutions withdrawing from market = less liquidity ahead.
    """
    try:
        scores = {}
        weights = {}

        if mmf_history and mmf_history.get("institutional"):
            flows = [r["flow"] for r in mmf_history["institutional"] if r.get("flow") is not None]
            if len(flows) >= 4:
                recent = flows[-1]
                mean_f = sum(flows) / len(flows)
                std_f = (sum((x - mean_f) ** 2 for x in flows) / len(flows)) ** 0.5
                scores["mmf_flow"] = (recent - mean_f) / std_f if std_f > 0 else 0
                weights["mmf_flow"] = 0.30

        if cot_data and "SP500_Emini" in cot_data:
            hist = cot_data["SP500_Emini"].get("history", [])
            if len(hist) >= 4:
                net_vals = [h["net_nc"] for h in hist]
                recent_nc = net_vals[-1]
                mean_nc = sum(net_vals) / len(net_vals)
                std_nc = (sum((x - mean_nc) ** 2 for x in net_vals) / len(net_vals)) ** 0.5
                scores["cot_sp500"] = -(recent_nc - mean_nc) / std_nc if std_nc > 0 else 0
                weights["cot_sp500"] = 0.25

        if ici_data and ici_data.get("flows"):
            eq_flows = [f["equity"] for f in ici_data["flows"] if f.get("equity") is not None]
            if len(eq_flows) >= 4:
                recent_eq = eq_flows[-1]
                mean_eq = sum(eq_flows) / len(eq_flows)
                std_eq = (sum((x - mean_eq) ** 2 for x in eq_flows) / len(eq_flows)) ** 0.5
                scores["ici_equity"] = -(recent_eq - mean_eq) / std_eq if std_eq > 0 else 0
                weights["ici_equity"] = 0.25

        inst_hist = fred.get("WIMFNS_HIST", []) or fred.get("WIMFSL_HIST", [])
        if inst_hist and len(inst_hist) >= 8:
            vals = [float(v) for v, _ in inst_hist if v is not None]
            try:
                latest_dt = pd.to_datetime(inst_hist[-1][1], errors="coerce")
            except Exception:
                latest_dt = pd.NaT
            if vals and pd.notna(latest_dt) and int((pd.Timestamp(datetime.date.today()) - latest_dt.normalize()).days) <= 120:
                current = vals[-1]
                avg = sum(vals) / len(vals)
                std = (sum((x - avg) ** 2 for x in vals) / len(vals)) ** 0.5
                scores["mmf_level"] = (current - avg) / std if std > 0 else 0
                weights["mmf_level"] = 0.20

        if not scores:
            return {"score": None, "label": "Insufficient data", "color": "#94a3b8", "components": {}}

        total_w = sum(weights[k] for k in scores)
        composite = sum(scores[k] * weights[k] / total_w for k in scores)
        composite = round(composite, 3)

        if composite > 1.5:
            label, color = "🔴 Institutions Exiting", "#f87171"
        elif composite > 0.5:
            label, color = "🟡 Cautious Positioning", "#fbbf24"
        elif composite > -0.5:
            label, color = "🟢 Neutral", "#34d399"
        else:
            label, color = "💧 Fully Invested", "#3b82f6"

        return {
            "score": composite,
            "label": label,
            "color": color,
            "components": {k: round(v, 2) for k, v in scores.items()},
        }
    except Exception:
        return {"score": None, "label": "Error", "color": "#94a3b8", "components": {}}


def compute_composite_liquidity_score(fred, mkt):
    """
    Composite Liquidity Score = weighted z-score of:
      NFCI (30%), TED Spread (20%), MOVE Index (20%), HY Spread (30%)
    Score > +1.5 → Stress | 0 to 1.5 → Tightening | < 0 → Ample
    Returns dict: score, label, color, components
    """
    try:
        nfci = _get_val(fred, "NFCI")
        ted = _get_val(fred, "TEDRATE")
        hy = _get_val(fred, "BAMLH0A0HYM2")
        move = (mkt.get("^MOVE") or {}).get("value")

        baselines = {
            "nfci": (0.0, 0.5),
            "ted": (0.35, 0.25),
            "hy": (400, 200),
            "move": (100, 40),
        }

        def zscore(val, mean, std):
            if val is None or std == 0:
                return None
            return (float(val) - mean) / std

        z_nfci = zscore(nfci, *baselines["nfci"])
        z_ted = zscore(ted, *baselines["ted"])
        z_hy = zscore(hy, *baselines["hy"])
        z_move = zscore(move, *baselines["move"])
        components = {
            "NFCI z": z_nfci,
            "TED z": z_ted,
            "HY z": z_hy,
            "MOVE z": z_move,
        }
        weights = {
            "NFCI z": 0.30,
            "TED z": 0.20,
            "HY z": 0.30,
            "MOVE z": 0.20,
        }
        available_components = {k: v for k, v in components.items() if v is not None}
        if len(available_components) < 2:
            return {
                "score": None,
                "label": "Insufficient data",
                "color": "#94a3b8",
                "components": {},
                "raw": {
                    "NFCI": nfci,
                    "TED": ted,
                    "HY Spread (bp)": hy,
                    "MOVE": move,
                }
            }

        total_weight = sum(weights[k] for k in available_components)
        score = round(sum(available_components[k] * weights[k] for k in available_components) / total_weight, 3)

        if score > 1.5:
            label, color = "🔴 Stress", "#f87171"
        elif score > 0.5:
            label, color = "🟡 Tightening", "#fbbf24"
        elif score > -0.5:
            label, color = "🟢 Neutral", "#34d399"
        else:
            label, color = "💧 Ample", "#3b82f6"

        return {
            "score": score,
            "label": label,
            "color": color,
            "components": {k: round(v, 2) for k, v in available_components.items()},
            "raw": {
                "NFCI": nfci,
                "TED": ted,
                "HY Spread (bp)": hy,
                "MOVE": move,
            }
        }
    except Exception:
        return {"score": None, "label": "Unavailable", "color": "#94a3b8",
                "components": {}, "raw": {}}


# ── HTML REPORT GENERATOR (for download button) ───────────────────────────────
def generate_html_report(
    fred, mkt, treasury, fg, naaim, cape, aaii,
    opts=None, skew_idx=None, chain_data=None, pcr_hist=None,
    sofr_data=None, amihud_data=None, cot_data=None, ici_data=None,
    mmf_history=None, inst13f=None, premarket_data=None, news=None,
    worldmonitor_news=None, bls=None, vix_term=None, vrp_data=None,
    panic_data=None, cta_model=None, sg_cta=None
) -> str:
    """Generate a self-contained HTML snapshot that matches the live dashboard data."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    regime_label, regime_color = _regime(fred, mkt)
    liq = compute_composite_liquidity_score(fred, mkt)
    inst_score = compute_institutional_participation_score(cot_data, ici_data, mmf_history, fred)
    opts = opts or {}
    skew_idx = skew_idx or {}
    chain_data = chain_data or {}
    pcr_hist = pcr_hist or []
    premarket_data = premarket_data or {}
    news = news or []
    worldmonitor_news = worldmonitor_news or {}
    bls = bls or {}
    vix_term = vix_term or []
    vrp_data = vrp_data or {}
    panic_data = panic_data or {}
    cta_model = cta_model or {}
    sg_cta = sg_cta or {}
    composites = compute_gs_style_composites(fred, mkt, fg=fg, opts=opts, cape=cape)
    dxy_trend = compute_dxy_trend(mkt)

    def _esc(text):
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _num(value, suffix="", digits=2, na="N/A"):
        try:
            if value is None:
                return na
            return f"{float(value):,.{digits}f}{suffix}"
        except Exception:
            return na

    def _metric_card(label, value, color="#e2e8f0", subtext=""):
        return (
            '<div class="card metric">'
            f'<div class="label">{_esc(label)}</div>'
            f'<div class="value" style="color:{color}">{_esc(value)}</div>'
            f'<div class="sub">{_esc(subtext)}</div>'
            "</div>"
        )

    def _table_block(title, rows, headers):
        if not rows:
            return (
                f'<h2>{_esc(title)}</h2>'
                '<div class="empty">No data available at export time.</div>'
            )
        header_html = "".join(f"<th>{_esc(h)}</th>" for h in headers)
        body_html = ""
        for row in rows:
            body_html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>\n"
        return (
            f'<h2>{_esc(title)}</h2>'
            f'<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>'
        )

    def _mini_svg(points, color="#3b82f6"):
        vals = []
        for p in points or []:
            v = p.get("value") if isinstance(p, dict) else p
            try:
                vals.append(float(v))
            except Exception:
                continue
        if len(vals) < 2:
            return '<div class="spark-empty">No chart data</div>'
        vals = vals[-90:]
        lo, hi = min(vals), max(vals)
        span = hi - lo or 1.0
        w, h, pad = 240, 72, 8
        coords = []
        for i, v in enumerate(vals):
            x = pad + (w - pad * 2) * i / max(1, len(vals) - 1)
            y = h - pad - ((v - lo) / span) * (h - pad * 2)
            coords.append(f"{x:.1f},{y:.1f}")
        return (
            f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" stroke-width="2.2" />'
            '</svg>'
        )

    def _news_cards(items, limit=8):
        if not items:
            return '<div class="empty">No headlines available at export time.</div>'
        html = '<div class="headline-grid">'
        for item in items[:limit]:
            title = item.get("title", "")
            src = item.get("source", item.get("source_name", ""))
            stamp = item.get("time", item.get("published", item.get("published_at", "")))
            url = item.get("url", "#")
            html += (
                '<a class="headline-card" href="{url}" target="_blank" rel="noopener noreferrer">'
                '<div class="headline-title">{title}</div>'
                '<div class="headline-meta">{src} · {stamp}</div>'
                '</a>'
            ).format(url=_esc(url), title=_esc(title), src=_esc(src), stamp=_esc(stamp))
        html += '</div>'
        return html

    overview_cards = "".join([
        _metric_card("GDP (GDPNow)", _fmt(_get_val(fred, "GDPNOW") or _get_val(fred, "A191RL1Q225SBEA"), "%")),
        _metric_card("CPI Inflation", _fmt(_get_val(fred, "CPIAUCSL"), "%")),
        _metric_card("Unemployment", _fmt(_get_val(fred, "UNRATE"), "%")),
        _metric_card("Fed Funds", _fmt(_get_val(fred, "DFF"), "%")),
        _metric_card("Fear & Greed", f"{fg.get('value'):.0f}" if fg and fg.get("value") is not None else "N/A",
                     "#fbbf24" if fg and fg.get("value") is not None else "#94a3b8",
                     fg.get("label", "") if fg else ""),
        _metric_card("CAPE Ratio", f"{cape.get('value'):.1f}" if cape and cape.get("value") is not None else "N/A",
                     "#f87171" if cape and cape.get("value") and cape.get("value") > 28 else "#34d399"),
    ])

    market_rows = []
    for label, value, sub in [
        ("S&P 500", (mkt.get("^GSPC") or {}).get("value"), f"{(mkt.get('^GSPC') or {}).get('change_pct', 0):+.2f}%" if (mkt.get("^GSPC") or {}).get("change_pct") is not None else "N/A"),
        ("NASDAQ", (mkt.get("^IXIC") or {}).get("value"), f"{(mkt.get('^IXIC') or {}).get('change_pct', 0):+.2f}%" if (mkt.get("^IXIC") or {}).get("change_pct") is not None else "N/A"),
        ("Dow Jones", (mkt.get("^DJI") or {}).get("value"), f"{(mkt.get('^DJI') or {}).get('change_pct', 0):+.2f}%" if (mkt.get("^DJI") or {}).get("change_pct") is not None else "N/A"),
        ("VIX", (mkt.get("^VIX") or {}).get("value"), "Yahoo Finance"),
        ("Dollar Index", (mkt.get("DX-Y.NYB") or {}).get("value"), f"{(mkt.get('DX-Y.NYB') or {}).get('change_pct', 0):+.2f}%" if (mkt.get("DX-Y.NYB") or {}).get("change_pct") is not None else "N/A"),
        ("Bitcoin", (mkt.get("BTC-USD") or {}).get("value"), f"{(mkt.get('BTC-USD') or {}).get('change_pct', 0):+.2f}%" if (mkt.get("BTC-USD") or {}).get("change_pct") is not None else "N/A"),
        ("Treasury 10Y", (treasury.get("10Y") or {}).get("value"), (treasury.get("10Y") or {}).get("date", "")),
        ("Treasury 2Y", (treasury.get("2Y") or {}).get("value"), (treasury.get("2Y") or {}).get("date", "")),
    ]:
        market_rows.append([
            _esc(label),
            _esc("N/A" if value is None else f"{value:,.2f}"),
            _esc(sub),
        ])

    sentiment_rows = [
        [_esc("Fear & Greed"), _esc("N/A" if not fg or fg.get("value") is None else f"{fg['value']:.0f}"), _esc(fg.get("label", "Missing") if fg else "Missing")],
        [_esc("NAAIM"), _esc("N/A" if not naaim or naaim.get("value") is None else f"{naaim['value']:.1f}"), _esc(naaim.get("date", "Missing") if naaim else "Missing")],
        [_esc("AAII Bull/Bear Spread"), _esc("N/A" if not aaii or aaii.get("spread") is None else f"{aaii['spread']:+.1f}"), _esc(aaii.get("date", "Missing") if aaii else "Missing")],
        [_esc("CAPE"), _esc("N/A" if not cape or cape.get("value") is None else f"{cape['value']:.1f}"), _esc(cape.get("source_tag", "Missing") if cape else "Missing")],
    ]

    options_rows = [
        [_esc("PCR"), _esc("N/A" if opts.get("pcr") is None else f"{opts['pcr']:.2f}"), _esc(opts.get("pcr_source") or "Options indicators")],
        [_esc("SKEW Index"), _esc("N/A" if skew_idx.get("value") is None else f"{skew_idx['value']:.1f}"), _esc(skew_idx.get("date", ""))],
        [_esc("VVIX"), _esc("N/A" if opts.get("vvix") is None else f"{opts['vvix']:.1f}"), _esc("Yahoo Finance")],
        [_esc("GVZ"), _esc("N/A" if opts.get("gvz") is None else f"{opts['gvz']:.1f}"), _esc("Yahoo Finance")],
        [_esc("SPY Spot"), _esc("N/A" if chain_data.get("spot") is None else f"{chain_data['spot']:.2f}"), _esc(chain_data.get("expiry", ""))],
        [_esc("Net GEX"), _esc("N/A" if chain_data.get("total_gex") is None else f"${chain_data['total_gex']/1e9:.2f}B"), _esc("Computed from options chain")],
        [_esc("PCR History Points"), _esc(str(len(pcr_hist))), _esc("CBOE history rows")],
    ]

    liquidity_rows = [
        [_esc("Composite Liquidity Score"), _esc("N/A" if liq.get("score") is None else f"{liq['score']:.2f}"), _esc(liq.get("label", "Unavailable"))],
        [_esc("NFCI"), _esc(_fmt(_get_val(fred, "NFCI"), "idx")), _esc("FRED")],
        [_esc("STLFSI2"), _esc(_fmt(_get_val(fred, "STLFSI2"), "idx")), _esc("FRED")],
        [_esc("TED Spread"), _esc(_fmt(_get_val(fred, "TEDRATE"), "%")), _esc("FRED")],
        [_esc("10Y-3M Spread"), _esc(_fmt(_get_val(fred, "T10Y3M"), "%")), _esc("FRED")],
        [_esc("MOVE Index"), _esc("N/A" if (mkt.get("^MOVE") or {}).get("value") is None else f"{(mkt.get('^MOVE') or {}).get('value'):.0f}"), _esc("Yahoo Finance")],
        [_esc("SOFR"), _esc("N/A" if not sofr_data or sofr_data.get("value") is None else f"{sofr_data['value']:.3f}%"), _esc(sofr_data.get("source_tag", "Missing") if sofr_data else "Missing")],
        [_esc("Amihud Illiquidity"), _esc("N/A" if not amihud_data or amihud_data.get("value") is None else f"{amihud_data['value']:.6f}"), _esc(amihud_data.get("ticker", "SPY") if amihud_data else "Missing")],
    ]

    gs_rows = [
        [_esc("FCI Score"), _esc(_num(composites.get("fci", {}).get("score"), suffix="/100", digits=1)), _esc("0=loose, 100=tight")],
        [_esc("Recession Probability Composite"), _esc(_num(composites.get("recession", {}).get("score"), suffix="/100", digits=1)), _esc("Sahm/curve/LEI/credit/labor proxy")],
        [_esc("Risk Appetite"), _esc(_num(composites.get("risk_appetite", {}).get("score"), suffix="/100", digits=1)), _esc(composites.get("risk_appetite", {}).get("label", "Unavailable"))],
        [_esc("Macro Surprise"), _esc(_num(composites.get("macro_surprise", {}).get("score"), digits=2)), _esc("Actual change vs prior release proxy")],
    ]

    global_rows = [
        [_esc("DXY Trend"), _esc(dxy_trend.get("trend", "N/A")), _esc(f"20D {dxy_trend.get('ma20')} / 50D {dxy_trend.get('ma50')}")],
        [_esc("EUR/USD"), _esc(_num((mkt.get("EURUSD=X") or {}).get("value"), digits=4)), _esc("Yahoo Finance")],
        [_esc("USD/CNH"), _esc(_num((mkt.get("CNH=X") or mkt.get("CNY=X") or {}).get("value"), digits=3)), _esc("Yahoo Finance")],
        [_esc("USD/JPY"), _esc(_num((mkt.get("JPY=X") or {}).get("value"), digits=2)), _esc("Yahoo Finance")],
        [_esc("EMB Spread Proxy"), _esc(_fmt(_get_val(fred, "BAMLH0A0HYM2"), "bp")), _esc("HY spread proxy; EM feed not connected")],
    ]

    retail_mmf_entry = (fred.get("WRMFNS") or fred.get("WRMFSL") or {})
    inst_mmf_entry = (fred.get("WIMFNS") or fred.get("WIMFSL") or {})

    institutional_rows = [
        [_esc("Participation Score"), _esc("N/A" if inst_score.get("score") is None else f"{inst_score['score']:.2f}"), _esc(inst_score.get("label", "Unavailable"))],
        [_esc("Retail MMF Assets"), _esc(_fmt(retail_mmf_entry.get("value"), "B")), _esc("FRED WRMFNS")],
        [_esc("Institutional MMF Assets (disc.)"), _esc(_fmt(inst_mmf_entry.get("last_value") or inst_mmf_entry.get("value"), "B")), _esc(f"FRED WIMFNS · last official weekly print {inst_mmf_entry.get('date', 'N/A')}")],
        [_esc("COT S&P Net Non-Comm"), _esc("N/A" if not cot_data or "SP500_Emini" not in cot_data else f"{cot_data['SP500_Emini'].get('net_nc', 0):,.0f}"), _esc(cot_data["SP500_Emini"].get("date", "") if cot_data and "SP500_Emini" in cot_data else "Missing")],
        [_esc("ICI Equity Flow"), _esc("N/A" if not ici_data or ici_data.get("latest_equity") is None else f"${ici_data['latest_equity']:,.1f}B"), _esc(ici_data.get("date", "Missing") if ici_data else "Missing")],
        [_esc("ICI Money Market Flow"), _esc("N/A" if not ici_data or ici_data.get("latest_money_market") is None else f"${ici_data['latest_money_market']:,.1f}B"), _esc(ici_data.get("source", "Missing") if ici_data else "Missing")],
        [_esc("13F Source"), _esc(inst13f.get("source", "Missing") if inst13f else "Missing"), _esc(inst13f.get("note", "") if inst13f else "")],
    ]

    premarket_cards = []
    premarket_order = [
        ("ES=F", "E-Mini S&P"),
        ("DX-Y.NYB", "DXY"),
        ("GC=F", "Gold"),
        ("SI=F", "Silver"),
        ("HG=F", "Copper"),
        ("CL=F", "WTI Crude"),
        ("JPY=X", "USD/JPY"),
        ("ES_GC", "ES/GC"),
        ("GC_SI", "GC/SI"),
    ]
    for key, label in premarket_order:
        d = (premarket_data.get("cards") or {}).get(key) or {}
        chg = d.get("change_pct")
        color = "#34d399" if (chg or 0) > 0 else "#f87171" if (chg or 0) < 0 else "#94a3b8"
        premarket_cards.append(
            '<div class="market-tile">'
            f'<div class="tile-title">{_esc(label)}</div>'
            f'{_mini_svg(d.get("chart_points") or d.get("history") or [], color=color)}'
            f'<div class="tile-row"><span>Close {_esc(_num(d.get("price"), digits=2))}</span>'
            f'<strong style="color:{color}">{_esc(_num(chg, suffix="%", digits=2))}</strong></div>'
            f'<div class="tile-meta">Last print: {_esc(str(d.get("last_time") or "N/A")[:16])}</div>'
            '</div>'
        )
    premarket_html = "".join(premarket_cards)

    labor_rows = [
        [_esc("Unemployment Rate"), _esc(_fmt(_get_val(fred, "UNRATE"), "%")), _esc("FRED")],
        [_esc("Initial Claims"), _esc(_fmt(_get_val(fred, "ICSA"), "K")), _esc("FRED")],
        [_esc("Average Hourly Earnings"), _esc(_fmt(_get_val(fred, "CES0500000003"), "%")), _esc("FRED")],
        [_esc("Personal Savings Rate"), _esc(_fmt(_get_val(fred, "PSAVERT"), "%")), _esc("FRED")],
        [_esc("Real Wage Growth"), _esc(_num(compute_real_wage_growth(fred), suffix="%", digits=2)), _esc("Wage YoY minus CPI YoY")],
        [_esc("Sahm Rule"), _esc(_num(_get_val(fred, "SAHMREALTIME"), suffix=" pts", digits=2)), _esc("0.5 = recession signal")],
        [_esc("Nonfarm Payrolls Change"), _esc(_num(((bls.get("nonfarm_payrolls") or {}).get("value")), suffix="k", digits=0)), _esc((bls.get("nonfarm_payrolls") or {}).get("date", "BLS"))],
    ]

    sentiment_framework_rows = [
        [_esc("Fear & Greed"), _esc("N/A" if not fg or fg.get("value") is None else f"{fg['value']:.0f}"), _esc(fg.get("label", "Missing") if fg else "Missing")],
        [_esc("VIX"), _esc(_num((mkt.get("^VIX") or {}).get("value"), digits=2)), _esc("Yahoo Finance")],
        [_esc("MOVE"), _esc(_num((mkt.get("^MOVE") or {}).get("value"), digits=1)), _esc("Yahoo Finance")],
        [_esc("VRP"), _esc(_num(vrp_data.get("vrp"), suffix="pt", digits=1)), _esc(vrp_data.get("signal", "Unavailable"))],
        [_esc("GS Panic Proxy"), _esc(_num(panic_data.get("score"), suffix="/10", digits=2)), _esc(panic_data.get("label", "Unavailable"))],
        [_esc("VIX Term Points"), _esc(str(len(vix_term))), _esc("Expiry curve rows")],
    ]

    cta_rows = [
        [_esc("CTA Equity Score"), _esc(_num(cta_model.get("equity_score"), digits=2)), _esc(cta_model.get("equity_label", "Unavailable"))],
        [_esc("SG CTA Latest Month"), _esc(_num(sg_cta.get("latest_month_return"), suffix="%", digits=2)), _esc(sg_cta.get("source", "Unavailable"))],
        [_esc("SG CTA YTD"), _esc(_num(sg_cta.get("ytd_return"), suffix="%", digits=2)), _esc(sg_cta.get("signal", "Unavailable"))],
    ]
    for ticker, data in (cta_model.get("assets") or {}).items():
        cta_rows.append([
            _esc(data.get("label", ticker)),
            _esc(_num(data.get("normalized"), digits=2)),
            _esc(f"Price {data.get('price', 'N/A')} · Vol {data.get('vol_annual', 'N/A')}%"),
        ])

    worldmonitor_items = []
    for key in WORLDMONITOR_NEWS_CATEGORY_ORDER:
        for item in (worldmonitor_news.get(key) or [])[:2]:
            worldmonitor_items.append({
                "title": item.get("title", ""),
                "source": f"{WORLDMONITOR_NEWS_CATEGORY_LABELS.get(key, key)} / {item.get('source', '')}",
                "time": item.get("published", item.get("time", "")),
                "url": item.get("url", "#"),
            })

    rows_html = ""
    for sid, (label, cat, unit) in FRED_SERIES.items():
        v = _get_val(fred, sid)
        if v is None:
            continue
        c = _status_color(sid, v) or "#3b82f6"
        rows_html += (
            "<tr>"
            f"<td>{_esc(cat)}</td>"
            f"<td>{_esc(label)}</td>"
            f"<td style='color:{c};font-weight:600'>{_esc(_fmt(v, unit))}</td>"
            "</tr>\n"
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Macro Dashboard — {ts}</title>
<style>
:root {{
  --bg:#0b0e14;
  --bg-elev:#10141d;
  --surface:#141923;
  --surface-2:#1a2030;
  --border:#1f2a3a;
  --border-soft:#172033;
  --text:#e6edf3;
  --muted:#8b95a7;
  --muted-2:#6b7689;
  --accent:#3b82f6;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0;
  font-family:Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background:linear-gradient(180deg, #0b0e14 0%, #0f1420 100%);
  color:var(--text);
  padding:32px;
  line-height:1.5;
}}
.shell {{ max-width:1440px; margin:0 auto; }}
.topbar {{
  display:flex; justify-content:space-between; align-items:flex-end; gap:20px;
  margin-bottom:22px; padding-bottom:18px; border-bottom:1px solid var(--border-soft);
}}
.nav {{
  position:sticky; top:0; z-index:10;
  display:flex; flex-wrap:wrap; gap:8px;
  background:rgba(11,14,20,0.92);
  backdrop-filter:blur(12px);
  border:1px solid var(--border);
  border-radius:14px;
  padding:10px;
  margin-bottom:18px;
}}
.nav a {{
  color:var(--muted);
  text-decoration:none;
  border:1px solid var(--border);
  border-radius:999px;
  padding:6px 10px;
  font-size:12px;
  font-weight:700;
}}
.nav a:hover {{ color:var(--text); border-color:var(--accent); }}
h1 {{ color:var(--text); margin:0; font-size:30px; letter-spacing:-0.02em; }}
h2 {{ margin:0 0 12px 0; color:var(--text); font-size:18px; letter-spacing:-0.01em; }}
.subtitle {{ color:var(--muted); font-size:13px; margin-top:6px; }}
.regime {{
  display:inline-flex; align-items:center; gap:8px;
  background:var(--surface); border:1px solid {regime_color}; color:{regime_color};
  padding:8px 14px; border-radius:999px; font-weight:700; font-size:13px;
}}
.stack {{ display:grid; gap:18px; }}
.section {{
  background:rgba(20,25,35,0.86);
  border:1px solid var(--border);
  border-radius:14px;
  padding:18px;
  box-shadow:0 12px 32px rgba(0,0,0,0.18);
}}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
.wide-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:14px; }}
.card {{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:12px;
  padding:14px 16px;
}}
.metric .label {{
  color:var(--muted);
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.08em;
  font-weight:600;
}}
.metric .value {{
  font-size:24px;
  font-weight:700;
  margin-top:8px;
  font-variant-numeric:tabular-nums;
}}
.metric .sub {{
  color:var(--muted-2);
  font-size:11px;
  margin-top:6px;
  min-height:16px;
}}
table {{
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  overflow:hidden;
  border:1px solid var(--border);
  border-radius:12px;
  background:var(--surface);
}}
th,td {{
  padding:10px 12px;
  border-bottom:1px solid var(--border-soft);
  text-align:left;
  vertical-align:top;
  font-size:13px;
}}
th {{
  background:var(--surface-2);
  color:var(--muted);
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.08em;
}}
tbody tr:last-child td {{ border-bottom:none; }}
.empty {{
  background:var(--surface);
  border:1px dashed var(--border);
  border-radius:12px;
  padding:14px 16px;
  color:var(--muted);
}}
.note {{ color:var(--muted-2); font-size:12px; }}
.market-tile {{
  background:#101725;
  border:1px solid var(--border);
  border-radius:14px;
  padding:12px;
  min-height:150px;
}}
.tile-title {{
  color:#fbbf24;
  font-weight:800;
  letter-spacing:.14em;
  text-transform:uppercase;
  font-size:12px;
  margin-bottom:8px;
}}
.spark {{
  width:100%;
  height:72px;
  display:block;
  background:#0b1626;
  border:1px solid #172033;
  border-radius:10px;
}}
.spark-empty {{
  height:72px;
  display:grid;
  place-items:center;
  color:var(--muted-2);
  background:#0b1626;
  border:1px dashed #172033;
  border-radius:10px;
  font-size:12px;
}}
.tile-row {{
  display:flex;
  justify-content:space-between;
  gap:12px;
  color:var(--muted);
  font-size:12px;
  margin-top:10px;
}}
.tile-meta {{ color:var(--muted-2); font-size:11px; margin-top:5px; }}
.headline-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; }}
.headline-card {{
  display:block;
  color:var(--text);
  text-decoration:none;
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:12px;
  padding:13px 14px;
}}
.headline-title {{ font-weight:700; font-size:13px; line-height:1.35; }}
.headline-meta {{ color:var(--muted-2); font-size:11px; margin-top:8px; }}
@media print {{
  body {{ background:#0b0e14; padding:18px; }}
  .nav {{ position:static; }}
  .section {{ break-inside:avoid; }}
}}
</style>
</head><body>
<div class="shell">
  <div class="topbar">
    <div>
      <h1>Macro Dashboard Report</h1>
      <div class="subtitle">Generated: {ts}</div>
    </div>
    <div class="regime">{_esc(regime_label)}</div>
  </div>

  <nav class="nav">
    <a href="#overview">Overview</a>
    <a href="#premarket">Pre-market</a>
    <a href="#markets">Markets</a>
    <a href="#labor">Labor</a>
    <a href="#sentiment">Sentiment</a>
    <a href="#options">Options</a>
    <a href="#liquidity">Liquidity</a>
    <a href="#composites">Composites</a>
    <a href="#global">Global</a>
    <a href="#flows">Flows</a>
    <a href="#news">News</a>
    <a href="#fred">FRED</a>
  </nav>

  <div class="stack">
    <section class="section" id="overview">
      <h2>Overview</h2>
      <div class="grid">{overview_cards}</div>
    </section>

    <section class="section" id="premarket">
      <h2>Pre-Market & Futures Snapshot</h2>
      <div class="wide-grid">{premarket_html}</div>
    </section>

    <section class="section" id="markets">{_table_block("Markets Snapshot", market_rows, ["Asset", "Value", "Context"])}</section>
    <section class="section" id="labor">{_table_block("Labor & Consumer Snapshot", labor_rows, ["Indicator", "Value", "Context"])}</section>
    <section class="section" id="sentiment">{_table_block("Sentiment Snapshot", sentiment_rows, ["Indicator", "Value", "Context"])}</section>
    <section class="section">{_table_block("Sentiment Framework Snapshot", sentiment_framework_rows, ["Indicator", "Value", "Context"])}</section>
    <section class="section" id="options">{_table_block("Options & Derivatives Snapshot", options_rows, ["Indicator", "Value", "Context"])}</section>
    <section class="section" id="liquidity">{_table_block("Liquidity Conditions Snapshot", liquidity_rows, ["Indicator", "Value", "Context"])}</section>
    <section class="section" id="composites">{_table_block("GS-Style Composites", gs_rows, ["Composite", "Value", "Context"])}</section>
    <section class="section" id="global">{_table_block("International / Global Macro", global_rows, ["Indicator", "Value", "Context"])}</section>
    <section class="section" id="flows">{_table_block("Institutional Flows Snapshot", institutional_rows, ["Indicator", "Value", "Context"])}</section>
    <section class="section">{_table_block("CTA Trend-Following Snapshot", cta_rows, ["Signal", "Value", "Context"])}</section>

    <section class="section" id="news">
      <h2>News & World Monitor Headlines</h2>
      <h3>Macro News</h3>
      {_news_cards(news, limit=8)}
      <h3 style="margin-top:18px">World Monitor</h3>
      {_news_cards(worldmonitor_items, limit=20)}
    </section>

    <section class="section" id="fred">
      <h2>FRED Series Snapshot</h2>
      <table><thead><tr><th>Category</th><th>Indicator</th><th>Value</th></tr></thead>
      <tbody>{rows_html}</tbody></table>
    </section>
  </div>
</div>
</body></html>"""


# ── SMART ALERT CALLOUTS ──────────────────────────────────────────────────────
def render_macro_alerts(fred, energy_curve=None):
    gdp_v  = _get_val(fred, "GDPNOW") or _get_val(fred, "A191RL1Q225SBEA")
    cpi_v  = _get_val(fred, "CPIAUCSL")
    rec_v  = _get_val(fred, "RECPROUSM156N")
    un_v   = _get_val(fred, "UNRATE")
    hy_v   = _get_val(fred, "BAMLH0A0HYM2")
    sahm_v = _get_val(fred, "SAHMREALTIME")
    psavert_v = _get_val(fred, "PSAVERT")
    ig_v = _get_val(fred, "BAMLC0A0CM")
    m2_yoy = compute_m2_yoy_change(fred)
    umich_v = _get_val(fred, "UMCSENT")

    if gdp_v is not None:
        if gdp_v < 0:
            st.error(f"🧊 Recession Warning: GDP contracting at {gdp_v:.1f}%")
        elif gdp_v < 1.5:
            st.warning(f"⚡ Slowdown: Growth losing momentum at {gdp_v:.1f}%")
        else:
            st.success(f"🌤 Economy expanding at {gdp_v:.1f}%")

    if cpi_v is not None:
        if cpi_v > 4:
            st.error(f"🔥 Inflation elevated at {cpi_v:.1f}% — well above 2% target")
        elif cpi_v > 2.5:
            st.warning(f"⚠️ Inflation at {cpi_v:.1f}% — above 2% Fed target")

    if rec_v is not None and rec_v > 50:
        st.error(f"⚠️ Recession probability above 50% ({rec_v:.0f}%)")

    if un_v is not None and un_v > 6:
        st.warning(f"📉 Unemployment elevated at {un_v:.1f}% — labor market weakening")

    if hy_v is not None and hy_v > 500:
        st.error(f"💥 HY credit spread at {hy_v:.0f} bp — credit stress elevated")

    if sahm_v is not None:
        if sahm_v >= 0.5:
            st.error("🔴 Sahm Rule triggered — real-time recession signal fired")
        elif sahm_v >= 0.3:
            st.warning(f"⚠️ Sahm Rule at {sahm_v:.2f} — approaching recession threshold")
    if psavert_v is not None and psavert_v < 3.5:
        st.warning(f"⚠️ Personal savings rate at {psavert_v:.1f}% — consumer buffer critically thin")
    if ig_v is not None:
        if ig_v > 200:
            st.error(f"🔴 IG credit spread at {ig_v:.0f}bp — credit market seizing up")
        elif ig_v > 150:
            st.warning(f"⚠️ IG credit spread at {ig_v:.0f}bp — investment-grade stress building")
    if m2_yoy is not None and m2_yoy < 0:
        st.warning("⚠️ M2 money supply contracting YoY — liquidity headwind")
    if umich_v is not None and umich_v < 65:
        st.warning(f"⚠️ Consumer sentiment at {umich_v:.1f} — household confidence deteriorating")

    if energy_curve is not None and not energy_curve.empty:
        spread_1m_row = _energy_spread_row(energy_curve, 1)
        spread_6m_row = _energy_spread_row(energy_curve, 6)
        spread_1m = _safe_float(spread_1m_row.get("Latest")) if spread_1m_row is not None else None
        spread_6m = _safe_float(spread_6m_row.get("Latest")) if spread_6m_row is not None else None
        is_rows = energy_curve.attrs.get("intermarket", pd.DataFrame())
        front_contract = energy_curve.attrs.get("front_contract")
        front_is = None
        if isinstance(is_rows, pd.DataFrame) and not is_rows.empty:
            rows = is_rows[is_rows["Leg1"].astype(str).str.upper() == str(front_contract).upper()]
            if not rows.empty:
                front_is = rows.iloc[0]
        wti_brent = _safe_float(front_is.get("Latest")) if front_is is not None else None
        bf_rows = energy_curve.attrs.get("butterflies", pd.DataFrame())
        bf_val = None
        if isinstance(bf_rows, pd.DataFrame) and not bf_rows.empty:
            target = bf_rows[
                (bf_rows["Leg1"].astype(str).str.upper() == str(front_contract).upper()) &
                (bf_rows["Leg2"].astype(str).str.upper().str.startswith("CLN")) &
                (bf_rows["Leg3"].astype(str).str.upper().str.startswith("CLQ"))
            ]
            if not target.empty:
                bf_val = _safe_float(target.iloc[0].get("Latest"))

        if spread_1m is not None and spread_1m < 0:
            st.error("🔴 WTI backwardation — supply squeeze signal")
        if spread_1m is not None and spread_6m is not None and spread_1m > 0 and spread_6m > 15:
            st.warning("⚠️ Deep contango — market sees near-term oversupply")
        if wti_brent is not None and wti_brent < -10:
            st.warning("⚠️ Brent premium > $10 — geopolitical risk or US glut")
        if bf_val is not None and bf_val < -1.5:
            st.info("Curve concavity widening — near-term supply easing")


def render_labor_alerts(fred):
    un_v  = _get_val(fred, "UNRATE")
    icsa  = _get_val(fred, "ICSA")
    wage  = _get_val(fred, "CES0500000003")

    if un_v is not None:
        if un_v > 6:
            st.error(f"📉 Unemployment at {un_v:.1f}% — significantly elevated")
        elif un_v > 4.5:
            st.warning(f"⚠️ Unemployment rising to {un_v:.1f}%")
        else:
            st.success(f"✅ Labor market healthy — Unemployment at {un_v:.1f}%")

    if icsa is not None and icsa > 350:
        st.warning(f"📋 Jobless claims elevated: {icsa:,.0f}K/week")


def render_markets_alerts(fred, mkt, fg, cape, opts=None):
    cape_v = cape.get("value") if cape else None
    fg_v   = fg.get("value") if fg else None
    vix_v  = (mkt.get("^VIX") or {}).get("value")

    if cape_v is not None:
        if cape_v > 35:
            st.error(f"🚨 CAPE ratio at {cape_v:.1f} — market significantly overvalued")
        elif cape_v > 28:
            st.warning(f"📈 CAPE ratio elevated at {cape_v:.1f} — above historical average")
        else:
            st.success(f"✅ CAPE ratio at {cape_v:.1f} — within normal range")

    if fg_v is not None:
        if fg_v < 25:
            st.success(f"😨 Extreme Fear ({fg_v:.0f}) — potential contrarian buy signal")
        elif fg_v > 75:
            st.warning(f"🤑 Extreme Greed ({fg_v:.0f}) — elevated correction risk")

    if vix_v is not None and vix_v > 30:
        st.error(f"📊 VIX at {vix_v:.1f} — elevated volatility / fear in markets")

    if opts and opts.get("backwardation"):
        st.error("🚨 VIX term structure in backwardation — options market pricing near-term shock")

    if opts and (opts.get("vvix") or 0) > 100:
        st.warning(f"⚡ VVIX at {opts['vvix']:.1f} — elevated tail risk hedging activity")


def _energy_metric_card(title, row=None, warn_red=False):
    if row is None:
        value_text, delta_text, color = "N/A", "", "#94a3b8"
    else:
        value = _safe_float(row.get("Latest"))
        change = _safe_float(row.get("Change"))
        value_text = f"${value:+.2f}" if value is not None else "N/A"
        delta_text = f"{change:+.2f}" if change is not None else ""
        if warn_red and value is not None and value < -6:
            color = "#f87171"
        else:
            color = "#34d399" if (change or 0) > 0 else "#f87171" if (change or 0) < 0 else "#94a3b8"
    st.markdown(
        f'<div style="background:#161b27;border:1px solid #1e2d3d;border-radius:10px;'
        f'padding:14px 16px;min-height:112px;">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">'
        f'{title}</div>'
        f'<div style="color:{color};font-size:28px;font-weight:800;margin-top:8px;">{value_text}</div>'
        f'<div style="color:#94a3b8;font-size:12px;margin-top:4px;">'
        f'Daily change: <span style="color:{color};font-weight:700">{delta_text or "N/A"}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_energy_futures(futures_curve):
    st.subheader("Energy Futures")
    st.caption(
        "Upload a CME-style futures spreads CSV in the sidebar. The tab reads WTI calendar spreads, "
        "WTI-Brent intermarket spreads, and the front butterfly to summarize oil curve stress."
    )

    if futures_curve is None or futures_curve.empty:
        st.info("Upload a futures spreads CSV in the sidebar to load the Energy Futures dashboard.")
        return

    front_contract = futures_curve.attrs.get("front_contract", "Front")
    curve_regime = get_energy_curve_regime(futures_curve) or "N/A"
    regime_color = {
        "Backwardation": "#f87171",
        "Flat": "#94a3b8",
        "Contango": "#fbbf24",
        "Deep Contango": "#f87171",
    }.get(curve_regime, "#94a3b8")
    st.markdown(
        f'<div style="display:inline-block;background:#161b27;border:1px solid {regime_color};'
        f'color:{regime_color};padding:6px 14px;border-radius:8px;font-weight:700;'
        f'font-size:14px;margin-bottom:12px">WTI Curve Regime: {curve_regime} · Front: {front_contract}</div>',
        unsafe_allow_html=True,
    )

    row_1m = _energy_spread_row(futures_curve, 1)
    row_6m = _energy_spread_row(futures_curve, 6)
    row_12m = _energy_spread_row(futures_curve, 12)
    is_rows = futures_curve.attrs.get("intermarket", pd.DataFrame())
    front_is = None
    if isinstance(is_rows, pd.DataFrame) and not is_rows.empty:
        rows = is_rows[is_rows["Leg1"].astype(str).str.upper() == str(front_contract).upper()]
        if not rows.empty:
            front_is = rows.iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _energy_metric_card("1M Spread (CLN6 vs CLM6)", row_1m)
    with k2:
        _energy_metric_card("6M Spread (CLZ6 vs CLM6)", row_6m)
    with k3:
        _energy_metric_card("12M Spread (CLM7 vs CLM6)", row_12m)
    with k4:
        _energy_metric_card("WTI-Brent Front Spread", front_is, warn_red=True)

    st.caption(
        "Interpretation: positive calendar spreads mean the front WTI contract is priced above the deferred contract in this file. "
        "Negative WTI-Brent means Brent trades at a premium to WTI."
    )

    st.divider()
    st.plotly_chart(
        make_energy_signal_scorecard_chart(futures_curve),
        use_container_width=True,
        key="chart_energy_signal_scorecard",
    )
    st.caption(
        "Start here: this scorecard converts the oil curve, curve steepness, and WTI-Brent gap into plain-language signals."
    )

    st.divider()
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.plotly_chart(
            make_energy_forward_curve_chart(futures_curve),
            use_container_width=True,
            key="chart_energy_forward_curve",
        )
        st.caption("Each point is the implied oil price traders are paying for delivery in that future month.")
    with c2:
        st.plotly_chart(
            make_energy_price_range_chart(futures_curve),
            use_container_width=True,
            key="chart_energy_price_range",
        )
        st.caption("Shaded band shows the high-low range traded for each delivery date; narrower means more agreement.")

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(
            make_energy_near_term_spreads_chart(futures_curve),
            use_container_width=True,
            key="chart_energy_near_term",
        )
        st.caption("Positive bars mean the next delivery month costs more than the prior month.")
    with c4:
        st.plotly_chart(
            make_energy_wti_brent_chart(futures_curve),
            use_container_width=True,
            key="chart_energy_wti_brent",
        )
        st.caption("WTI usually trades below Brent; a very large discount can point to US oversupply or transport bottlenecks.")

    with st.expander("Raw cleaned WTI spread rows"):
        st.dataframe(
            futures_curve[["Leg1", "Leg2", "Type", "months_out", "Latest", "Change", "Previous", "Volume", "Time"]],
            use_container_width=True,
            hide_index=True,
        )


def render_premarket_futures_snapshot(mkt, premarket_data):
    """
    Premarket / futures tape for reading the market before the opening bell.
    """
    premarket_data = premarket_data or {}
    cards = premarket_data.get("cards", {})

    st.subheader("🌅 Pre-Market & Futures Snapshot")
    st.caption(
        "Pre-open macro tape. Replaced the ETF strip with the market cluster from your reference: "
        "E-mini S&P, DXY, Gold, Silver, Copper, WTI Crude, USD/JPY, ES/GC, GC/SI."
    )
    st.caption("Each card now shows a chart of the last 5 sessions, plus the current live move versus the previous close.")
    es_time = (mkt.get("ES=F") or {}).get("last_time")
    if es_time:
        st.caption(f"Latest futures print: {str(es_time).split('+')[0].replace('T', ' ')[:16]} UTC")

    def _fallback_card(sym, label):
        d = mkt.get(sym) or {}
        return {
            "label": label,
            "price": d.get("value"),
            "prev_close": d.get("prev_close"),
            "change_pct": d.get("change_pct"),
            "last_time": d.get("last_time"),
            "history": [],
            "chart_points": [],
            "sessions_5d": [],
        }

    display = {
        "ES=F": cards.get("ES=F") or _fallback_card("ES=F", "E-Mini S&P"),
        "DX-Y.NYB": cards.get("DX-Y.NYB") or _fallback_card("DX-Y.NYB", "DXY"),
        "GC=F": cards.get("GC=F") or _fallback_card("GC=F", "Gold"),
        "SI=F": cards.get("SI=F") or _fallback_card("SI=F", "Silver"),
        "HG=F": cards.get("HG=F") or _fallback_card("HG=F", "Copper"),
        "CL=F": cards.get("CL=F") or _fallback_card("CL=F", "WTI Crude"),
        "JPY=X": cards.get("JPY=X") or _fallback_card("JPY=X", "USD/JPY"),
        "ES_GC": cards.get("ES_GC") or {},
        "GC_SI": cards.get("GC_SI") or {},
    }

    lead_changes = [
        display["ES=F"].get("change_pct"),
        display["DX-Y.NYB"].get("change_pct"),
        display["GC=F"].get("change_pct"),
        display["CL=F"].get("change_pct"),
    ]
    lead_changes = [float(v) for v in lead_changes if v is not None]

    if lead_changes:
        avg_move = sum(lead_changes) / len(lead_changes)
        if display["ES=F"].get("change_pct") is not None and display["ES=F"]["change_pct"] >= 0.5 and display["DX-Y.NYB"].get("change_pct", 0) <= 0:
            st.success("🟢 Risk-on pre-open tape — equities up without a confirming dollar squeeze.")
        elif display["ES=F"].get("change_pct") is not None and display["ES=F"]["change_pct"] <= -0.5 and display["DX-Y.NYB"].get("change_pct", 0) >= 0:
            st.error("🔴 Risk-off pre-open tape — equities down with dollar strength.")
        elif avg_move >= 0.25:
            st.warning(f"🟡 Mixed but constructive tape — average move {avg_move:+.2f}%.")
        elif avg_move <= -0.25:
            st.warning(f"🟡 Mixed but weak tape — average move {avg_move:+.2f}%.")
        else:
            st.info(f"Flat mixed tape — average move {avg_move:+.2f}%.")
    else:
        st.info("Premarket tape loading — Yahoo extended-hours quotes can be delayed.")

    def _fmt_value(key, value):
        if value is None:
            return "N/A"
        if key == "ES=F":
            return f"{value:,.2f}"
        if key in {"DX-Y.NYB", "JPY=X", "ES_GC", "GC_SI"}:
            return f"{value:,.2f}"
        return f"{value:,.2f}"

    order = [
        ("ES=F", "E-MINI S&P"),
        ("DX-Y.NYB", "DXY"),
        ("GC=F", "GOLD"),
        ("SI=F", "SILVER"),
        ("HG=F", "COPPER"),
        ("CL=F", "WTI CRUDE"),
        ("JPY=X", "USD/JPY"),
        ("ES_GC", "ES/GC"),
        ("GC_SI", "GC/SI"),
    ]

    rows = [st.columns(3) for _ in range(3)]
    grid_cols = [col for row in rows for col in row]
    for col, (key, title) in zip(grid_cols, order):
        d = display.get(key) or {}
        price = d.get("price")
        change_pct = d.get("change_pct")
        chart_points = d.get("chart_points") or []
        color = "#34d399" if (change_pct or 0) > 0 else "#f87171" if (change_pct or 0) < 0 else "#94a3b8"
        time_str = str(d.get("last_time", "")).split("+")[0].replace("T", " ")[:16] if d.get("last_time") else "N/A"
        with col:
            st.plotly_chart(
                make_macro_tape_chart(chart_points, title=title, height=150),
                use_container_width=True,
                key=f"chart_macro_tape_{key}",
            )
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:2px">'
                f'<span style="color:#94a3b8;font-size:12px">Close {_fmt_value(key, price)}</span>'
                f'<span style="color:{color};font-size:14px;font-weight:700">'
                f'{"N/A" if change_pct is None else f"{change_pct:+.2f}%"}'
                f'</span></div>'
                f'<div style="color:#64748b;font-size:10px;margin-top:4px">Last print: {time_str}</div>',
                unsafe_allow_html=True,
            )

    st.caption("Ratios are computed live from the underlying instruments. ES/GC tracks equity risk versus gold; GC/SI tracks precious-metals leadership.")
    st.divider()


def render_housing_alerts(fred):
    m30   = _get_val(fred, "MORTGAGE30US")
    hy_v  = _get_val(fred, "BAMLH0A0HYM2")
    cshpi = _get_val(fred, "CSUSHPINSA")

    if m30 is not None:
        if m30 > 7.5:
            st.error(f"🏠 30yr mortgage at {m30:.2f}% — affordability severely constrained")
        elif m30 > 6.5:
            st.warning(f"⚠️ 30yr mortgage at {m30:.2f}% — housing affordability stressed")
        else:
            st.success(f"✅ 30yr mortgage at {m30:.2f}%")

    if hy_v is not None and hy_v > 500:
        st.error(f"💥 HY credit spread at {hy_v:.0f} bp — credit conditions tightening")


def render_metals(mkt):
    metals = [
        ("GC=F", "Gold", "$/oz"),
        ("SI=F", "Silver", "$/oz"),
        ("HG=F", "Copper", "$/lb"),
        ("PL=F", "Platinum", "$/oz"),
        ("PA=F", "Palladium", "$/oz"),
        ("ALI=F", "Aluminum", "$/mt"),
    ]

    gold = (mkt.get("GC=F") or {}).get("value")
    copper = (mkt.get("HG=F") or {}).get("value")
    if gold is not None and gold > 3000:
        st.warning(f"⚠️ Gold at ${gold:,.0f}/oz — elevated safe-haven demand signal.")
    if copper is not None and copper < 3.5:
        st.warning(f"⚠️ Copper at ${copper:.2f}/lb — weak industrial demand signal.")

    kpi_cols = st.columns(len(metals))
    for i, (sym, label, unit) in enumerate(metals):
        d = mkt.get(sym) or {}
        value = d.get("value")
        change_pct = d.get("change_pct")
        with kpi_cols[i]:
            st.metric(
                label=f"{label} ({unit})",
                value=f"{value:,.2f}" if value is not None else "N/A",
                delta=f"{change_pct:+.2f}%" if change_pct is not None else None,
                delta_color="normal",
            )

    st.divider()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(
            make_metals_chart(mkt),
            use_container_width=True,
            key="chart_metals_bar",
        )

    with col2:
        st.subheader("Detail")
        for sym, label, unit in metals:
            d = mkt.get(sym) or {}
            value = d.get("value")
            change_pct = d.get("change_pct")
            change_color = "#34d399" if (change_pct or 0) >= 0 else "#f87171"
            change_str = f"{change_pct:+.2f}%" if change_pct is not None else "—"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                f'border-bottom:1px solid #1e2d3d">'
                f'<span style="color:#94a3b8;font-size:13px">{label}</span>'
                f'<span style="color:#e2e8f0;font-weight:600;font-size:13px">'
                f'{"N/A" if value is None else f"{value:,.2f}"}'
                f'<span style="color:{change_color};font-size:11px;margin-left:6px">{change_str}</span>'
                f'</span></div>',
                unsafe_allow_html=True,
            )

    silver = (mkt.get("SI=F") or {}).get("value")
    if gold is not None and silver is not None and silver > 0:
        ratio = round(gold / silver, 1)
        ratio_color = "#f87171" if ratio > 90 else "#34d399" if ratio < 70 else "#fbbf24"
        ratio_note = "⚠ elevated (>90)" if ratio > 90 else "✓ normal" if ratio < 70 else "→ watch"
        st.markdown(
            f'<div style="margin-top:12px;background:#161b27;border-radius:8px;'
            f'padding:12px 16px;display:inline-block">'
            f'<span style="color:#94a3b8;font-size:12px">Gold/Silver Ratio</span><br>'
            f'<span style="color:{ratio_color};font-size:22px;font-weight:700">{ratio}</span>'
            f'<span style="color:#64748b;font-size:11px;margin-left:6px">{ratio_note}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_gs_style_composites(fred, mkt, fg, opts, cape):
    composites = compute_gs_style_composites(fred, mkt, fg=fg, opts=opts, cape=cape)
    fci = composites["fci"]
    rec = composites["recession"]
    risk = composites["risk_appetite"]
    surprise = composites["macro_surprise"]

    st.subheader("GS-Style Composite Dashboard")
    st.caption(
        "These are public-data approximations of common macro composite frameworks. "
        "They are not official Goldman Sachs indices."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(
            make_composite_gauge(fci.get("score"), "Financial Conditions Index", "0 = loose, 100 = tight", "Loose", "Tight"),
            use_container_width=True,
            key="chart_gs_fci_gauge",
        )
    with c2:
        st.plotly_chart(
            make_composite_gauge(rec.get("score"), "Recession Probability Composite", "Public recession-risk proxy", "Low", "High"),
            use_container_width=True,
            key="chart_gs_recession_gauge",
        )
    with c3:
        st.plotly_chart(
            make_composite_gauge(risk.get("score"), "Risk Appetite Indicator", risk.get("label", ""), "Fear", "Greed"),
            use_container_width=True,
            key="chart_gs_risk_appetite_gauge",
        )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("FCI Score", f"{fci['score']:.1f}/100" if fci.get("score") is not None else "Insufficient data")
    k2.metric("Recession Probability", f"{rec['score']:.1f}/100" if rec.get("score") is not None else "Insufficient data", delta_color="inverse")
    k3.metric("Risk Appetite", f"{risk['score']:.1f}/100" if risk.get("score") is not None else "Insufficient data", delta=risk.get("label"))
    k4.metric("Macro Surprise", f"{surprise['score']:+.2f}" if surprise.get("score") is not None else "Insufficient data")

    st.divider()
    h1, h2 = st.columns(2)
    with h1:
        st.plotly_chart(
            make_composite_history_chart(fci.get("history"), "FCI Proxy — 12 Month History"),
            use_container_width=True,
            key="chart_gs_fci_history",
        )
    with h2:
        st.plotly_chart(
            make_composite_history_chart(rec.get("history"), "Recession Risk Proxy — 12 Month History"),
            use_container_width=True,
            key="chart_gs_recession_history",
        )

    st.divider()
    s1, s2 = st.columns([1, 1])
    with s1:
        st.subheader("Macro Surprise Index")
        st.plotly_chart(
            make_macro_surprise_chart(composites),
            use_container_width=True,
            key="chart_gs_macro_surprise",
        )
    with s2:
        st.subheader("Component Readout")
        for block_name, block in [
            ("Financial Conditions", fci.get("components", {})),
            ("Recession Risk", rec.get("components", {})),
            ("Risk Appetite", risk.get("components", {})),
        ]:
            st.markdown(f"**{block_name}**")
            for label, value in block.items():
                color = "#94a3b8" if value is None else "#34d399" if value < 40 else "#fbbf24" if value < 65 else "#f87171"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;border-bottom:1px solid #1e2d3d;'
                    f'padding:4px 0"><span style="color:#94a3b8">{label}</span>'
                    f'<span style="color:{color};font-weight:700">'
                    f'{"N/A" if value is None else f"{value:.1f}"}</span></div>',
                    unsafe_allow_html=True,
                )


def render_global_macro(fred, mkt):
    dxy = compute_dxy_trend(mkt)
    dxy_v = dxy.get("value")
    eurusd = (mkt.get("EURUSD=X") or {}).get("value")
    usdcnh = (mkt.get("CNH=X") or {}).get("value") or (mkt.get("CNY=X") or {}).get("value")
    usdjpy = (mkt.get("JPY=X") or {}).get("value")
    emb_proxy = _get_val(fred, "BAMLH0A0HYM2")

    if dxy_v is not None and dxy.get("strengthening") and dxy_v > 103:
        st.warning("⚠️ Dollar strengthening — global financial conditions tightening")
    if dxy_v is not None and dxy_v > 107:
        st.error("🔴 DXY above 107 — historical EM stress threshold breached")

    st.subheader("Global Macro Dashboard")
    st.caption("FX, dollar pressure, and global growth placeholders. PMI fields show placeholders where no free stable API is connected.")

    k = st.columns(6)
    k[0].metric("EUR/USD", f"{eurusd:.4f}" if eurusd is not None else "N/A")
    k[1].metric("USD/CNH", f"{usdcnh:.3f}" if usdcnh is not None else "N/A")
    k[2].metric("USD/JPY", f"{usdjpy:.2f}" if usdjpy is not None else "N/A")
    k[3].metric("DXY Trend", dxy.get("trend", "N/A"), delta=f"20D {dxy.get('ma20')} / 50D {dxy.get('ma50')}" if dxy.get("ma20") else None)
    k[4].metric("EMB Spread Proxy", f"{emb_proxy:.0f} bp" if emb_proxy is not None else "N/A", help="Using HY credit spread as a proxy because EM spread feed is not connected.")
    k[5].metric("DXY", f"{dxy_v:.2f}" if dxy_v is not None else "N/A")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        dxy_history = [{"date": p["date"], "value": p["value"]} for p in dxy.get("history", [])]
        fig = go.Figure()
        if dxy_history:
            fig.add_trace(go.Scatter(
                x=[p["date"] for p in dxy_history],
                y=[p["value"] for p in dxy_history],
                mode="lines",
                line=dict(color="#3b82f6", width=2),
                name="DXY",
            ))
            if dxy.get("ma20"):
                fig.add_hline(y=dxy["ma20"], line_dash="dot", line_color="#fbbf24", annotation_text="20D MA")
            if dxy.get("ma50"):
                fig.add_hline(y=dxy["ma50"], line_dash="dot", line_color="#94a3b8", annotation_text="50D MA")
        fig.update_layout(
            title=dict(text="DXY Trend — 20D vs 50D Moving Average", font_size=13),
            template=DARK_TEMPLATE, plot_bgcolor=CHART_BG, paper_bgcolor=PAPER_BG,
            height=300, margin=dict(l=45, r=20, t=45, b=30),
            xaxis_title="Date", yaxis_title="DXY",
        )
        st.plotly_chart(fig, use_container_width=True, key="chart_global_dxy_trend")
    with c2:
        st.markdown(
            """
**Global PMI placeholders**

- Euro Area Composite PMI: connect a licensed S&P Global/Markit feed or approved FRED equivalent when available.
- China PMI: connect Caixin/NBS API or a licensed macro calendar feed.
- Until then, this panel intentionally avoids fabricating PMI values.
            """
        )
        st.info("Euro Area Composite PMI: placeholder — data provider not connected.")
        st.info("China PMI: placeholder — connect Caixin/NBS source when available.")


def render_options_derivatives(mkt, opts, skew_idx, vix_term, vix_v,
                               chain_data=None, pcr_hist=None):
    """
    📉 Options & Derivatives Tab — full layout including:
    OI walls, IV smile, GEX, PCR history, VIX term structure, gauges, signals bar.
    """
    chain_data = chain_data or {}
    pcr_hist   = pcr_hist   or []

    pcr         = opts.get("pcr")          if opts else None
    vvix        = opts.get("vvix")         if opts else None
    gvz         = opts.get("gvz")          if opts else None
    skew_proxy  = opts.get("skew_proxy")   if opts else None
    backwardation = bool(opts.get("backwardation")) if opts else False
    skew_value  = (skew_idx or {}).get("value")
    total_gex   = _effective_total_gex(chain_data)
    spot        = chain_data.get("spot")
    expiry      = chain_data.get("expiry", "N/A")
    oi_profile  = chain_data.get("oi_profile") or []
    gex_rows    = chain_data.get("gex") or []
    calls_smile = chain_data.get("calls_smile") or []
    puts_smile  = chain_data.get("puts_smile") or []
    max_pain    = chain_data.get("max_pain")
    skew_25d    = chain_data.get("skew_25d")
    key_strikes = chain_data.get("key_strikes") or []

    call_wall = None
    put_wall = None
    pos_gex_strike = None
    neg_gex_strike = None
    atm_call_iv = None
    atm_put_iv = None

    if oi_profile:
        try:
            call_wall = max(oi_profile, key=lambda r: float(r.get("call_oi", 0) or 0)).get("strike")
        except Exception:
            call_wall = None
        try:
            put_wall = max(oi_profile, key=lambda r: float(r.get("put_oi", 0) or 0)).get("strike")
        except Exception:
            put_wall = None

    if gex_rows:
        try:
            pos_gex_strike = max(gex_rows, key=lambda r: float(r.get("gex", 0) or 0)).get("strike")
        except Exception:
            pos_gex_strike = None
        try:
            neg_gex_strike = min(gex_rows, key=lambda r: float(r.get("gex", 0) or 0)).get("strike")
        except Exception:
            neg_gex_strike = None

    if calls_smile:
        try:
            atm_call = min(calls_smile, key=lambda r: abs(float(r.get("moneyness", 999))))
            atm_call_iv = float(atm_call.get("impliedVolatility", 0)) * 100
        except Exception:
            atm_call_iv = None
    if puts_smile:
        try:
            atm_put = min(puts_smile, key=lambda r: abs(float(r.get("moneyness", 999))))
            atm_put_iv = float(atm_put.get("impliedVolatility", 0)) * 100
        except Exception:
            atm_put_iv = None

    # ── Row 0: Alert callouts ─────────────────────────────────────────────────
    if backwardation:
        st.error("🚨 VIX Backwardation detected — near-term fear spike, historically precedes sharp drawdowns")
    if pcr is not None and pcr > 1.5:
        st.error(f"🚨 Extreme put buying (PCR {pcr:.2f}) — possible panic hedge or contrarian buy signal")
    elif pcr is not None and pcr > 1.2:
        st.warning(f"📊 Put/Call Ratio elevated at {pcr:.2f} — bearish positioning dominates")
    if skew_value is not None and skew_value > 140:
        st.error(f"⚠️ CBOE SKEW at {skew_value:.0f} — market pricing in significant tail/crash risk")
    if vvix is not None and vvix > 100:
        st.warning(f"⚡ VVIX elevated at {vvix:.1f} — heavy demand for VIX options, institutions hedging tails")
    if total_gex is not None and total_gex < 0:
        st.error(f"⚡ Negative GEX detected (${total_gex/1e9:.2f}B) — dealers SHORT gamma, moves will be AMPLIFIED")

    # ── Row 1: KPI metrics ────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("VIX",        f"{vix_v:.2f}"     if vix_v      is not None else "N/A",
              delta=f"{vix_v - 20:.2f} vs 20"   if vix_v      is not None else None)
    k2.metric("PCR",        f"{pcr:.2f}"        if pcr        is not None else "N/A",
              delta=f"{pcr - 1.0:+.2f} vs 1.0"  if pcr        is not None else None,
              help="Primary source is a CBOE-derived intraday total-options put/call ratio; SPY option-chain open interest is used only as a fallback.")
    k3.metric("SKEW Index", f"{skew_value:.1f}" if skew_value is not None else "N/A",
              delta=f"{skew_value - 120:+.1f} vs calm" if skew_value is not None else None)
    k4.metric("VVIX",       f"{vvix:.1f}"       if vvix       is not None else "N/A",
              delta=f"{vvix - 100:+.1f} vs stress" if vvix    is not None else None)
    k5.metric("GVZ",        f"{gvz:.1f}"        if gvz        is not None else "N/A",
              delta=f"{gvz - 25:+.1f} vs base"  if gvz        is not None else None)
    gex_label = f"${total_gex/1e9:.1f}B" if total_gex is not None else "N/A"
    gex_delta = (
        "Amplifying ⚠"
        if total_gex is not None and total_gex < 0
        else "Dampening ✓"
        if total_gex is not None and total_gex > 0
        else "Balanced"
        if total_gex is not None
        else None
    )
    k6.metric("Net GEX", gex_label, delta=gex_delta,
              delta_color="inverse" if total_gex is not None and total_gex < 0 else "normal")
    if opts.get("pcr_source"):
        pcr_stamp = opts.get("pcr_time") or opts.get("pcr_date") or "latest available"
        st.caption(f"PCR source: {opts.get('pcr_source')} · timestamp: {pcr_stamp}")

    st.divider()

    gex_regime_text, gex_regime_color = _classify_gex_regime(total_gex)
    if gex_regime_text == "Negative (amplifying)":
        gex_regime = "Negative GEX"
    elif gex_regime_text == "Positive (dampening)":
        gex_regime = "Positive GEX"
    elif gex_regime_text == "Neutral / balanced":
        gex_regime = "Neutral GEX"
    else:
        gex_regime = "GEX unavailable"
    skew_text = f"{skew_25d:+.1f} vol pts" if skew_25d is not None else "N/A"
    max_pain_text = f"{max_pain:,.0f}" if max_pain is not None else "N/A"
    spot_text = f"{spot:.2f}" if spot is not None else "N/A"
    if total_gex is None:
        regime_note = "Simple read: the options feed did not return enough usable strikes to infer the dealer hedging regime."
    elif total_gex < 0:
        regime_note = "Simple read: expect faster intraday swings and less pinning."
    elif total_gex > 0:
        regime_note = "Simple read: dealer hedging should resist outsized moves near key strikes."
    else:
        regime_note = "Simple read: dealer hedging looks roughly balanced, so this signal is not leaning strongly in either direction."

    header_c1, header_c2 = st.columns([4, 1.2])
    with header_c1:
        st.markdown(
            f"""
<div style="background:#161b27;border:1px solid {gex_regime_color};border-radius:12px;padding:16px 18px;margin-bottom:8px;">
  <div style="display:flex;flex-wrap:wrap;gap:20px;align-items:flex-end;">
    <div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Spot</div><div style="color:#e2e8f0;font-size:24px;font-weight:700">{spot_text}</div></div>
    <div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Expiry</div><div style="color:#e2e8f0;font-size:24px;font-weight:700">{expiry}</div></div>
    <div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Regime</div><div style="color:{gex_regime_color};font-size:24px;font-weight:700">{gex_regime}</div></div>
    <div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Max Pain</div><div style="color:#e2e8f0;font-size:24px;font-weight:700">{max_pain_text}</div></div>
    <div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">25Δ Skew</div><div style="color:#e2e8f0;font-size:24px;font-weight:700">{skew_text}</div></div>
  </div>
  <div style="margin-top:10px;color:#94a3b8;font-size:13px;">{regime_note}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        if key_strikes:
            pills = "".join(
                f'<span style="display:inline-block;margin:4px 8px 0 0;padding:6px 10px;border-radius:999px;'
                f'border:1px solid {row.get("color","#94a3b8")};color:{row.get("color","#94a3b8")};font-size:12px;">'
                f'{row.get("label","Key").replace("_"," ").title()}: {float(row.get("strike",0)):,.0f}</span>'
                for row in key_strikes
            )
            st.markdown(pills, unsafe_allow_html=True)
    with header_c2:
        local_simple_mode = st.toggle(
            "Simple Mode",
            value=False,
            key="options_simple_mode",
            help="Hide some jargon and focus the notes on plain-language trading implications.",
        )
        st.caption("Toggle this when you want the section to read like a trading brief instead of a derivatives worksheet.")
    simple_mode = is_beginner_mode() or local_simple_mode

    st.divider()

    # ── Section A: VIX Term Structure + Gauges ────────────────────────────────
    st.subheader("📈 VIX Volatility Surface")
    row1_c1, row1_c2 = st.columns([1.2, 1])
    with row1_c1:
        render_vix_term_structure_badge(vix_term)
        st.plotly_chart(make_vix_term_chart(vix_term),
                        use_container_width=True, key="chart_vix_term_structure")
    with row1_c2:
        st.plotly_chart(make_pcr_gauge(pcr),
                        use_container_width=True, key="chart_pcr_gauge")
        st.plotly_chart(make_skew_gauge(skew_value),
                        use_container_width=True, key="chart_skew_gauge")

    st.divider()

    # ── Section B: Options Chain — OI Wall + IV Smile ─────────────────────────
    st.subheader("📊 Options Chain Analysis (SPY)")
    if spot:
        st.caption(f"SPY Spot: **{spot:.2f}** · Near-term expiry: **{expiry}** · Source: Yahoo Finance (yfinance, ~15 min delay)")
    else:
        st.caption("Options chain data unavailable — yfinance may be unreachable.")

    if simple_mode:
        st.info(
            f"Simple read: the biggest call and put walls mark likely sticky levels, "
            f"the IV smile shows where protection is most expensive, and {gex_regime.lower()} means "
            f"{'moves can extend quickly' if total_gex is not None and total_gex < 0 else 'dealer hedging may slow price down near major strikes' if total_gex is not None and total_gex > 0 else 'the feed does not have enough usable options detail to say whether moves should be amplified or dampened'}."
        )
    else:
        st.caption(
            "Read this section in three passes: first locate the open-interest walls, then check where skew is most expensive, "
            "then compare spot with the strongest positive and negative gamma strikes."
        )

    row2_sizes = [1.15, 0.85] if simple_mode else [1.15, 1.1, 0.75]
    row2_cols = st.columns(row2_sizes)
    row2_c1 = row2_cols[0]
    row2_c2 = row2_cols[1] if len(row2_cols) > 1 else None
    row2_c3 = row2_cols[2] if len(row2_cols) > 2 else None
    with row2_c1:
        st.plotly_chart(make_oi_profile_chart(chain_data),
                        use_container_width=True, key="chart_oi_profile")
    if not simple_mode and row2_c2 is not None:
        with row2_c2:
            st.plotly_chart(make_iv_smile_chart(chain_data),
                            use_container_width=True, key="chart_iv_smile")
    with (row2_c2 if simple_mode else row2_c3):
        regime_text = gex_regime_text or "Unavailable"
        simple_sentence = (
            "Price can overshoot through crowded strikes; use walls as acceleration points."
            if total_gex is not None and total_gex < 0 else
            "Price is more likely to mean-revert toward crowded strikes."
            if total_gex is not None and total_gex > 0 else
            "There is not enough options-chain detail to infer whether dealer hedging will amplify or dampen moves."
        )
        st.markdown(
            f"""
<div style="background:#161b27;border:1px solid {gex_regime_color};border-radius:10px;padding:16px 18px;height:100%;">
  <div style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.08em">GEX Regime Panel</div>
  <div style="color:{gex_regime_color};font-size:28px;font-weight:700;margin-top:8px;">{regime_text}</div>
  <div style="color:#94a3b8;font-size:13px;margin-top:10px;">{simple_sentence}</div>
  <div style="margin-top:14px;color:#e2e8f0;font-size:13px;line-height:1.6;">
    <b>Call wall:</b> {f"{call_wall:,.0f}" if call_wall is not None else "N/A"}<br>
    <b>Put wall:</b> {f"{put_wall:,.0f}" if put_wall is not None else "N/A"}<br>
    <b>+GEX strike:</b> {f"{pos_gex_strike:,.0f}" if pos_gex_strike is not None else "N/A"}<br>
    <b>-GEX strike:</b> {f"{neg_gex_strike:,.0f}" if neg_gex_strike is not None else "N/A"}
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

    advanced_label = "Advanced options structure" if simple_mode else None
    advanced_container = st.expander(advanced_label, expanded=False) if simple_mode else st.container()
    with advanced_container:
        st.divider()

        # ── Section C: GEX by Strike ──────────────────────────────────────────────
        st.subheader("⚡ Dealer Gamma Exposure (GEX)")
        st.caption(
            "GEX is computed from Black-Scholes gamma × open interest. "
            "Negative GEX means dealer hedging amplifies moves; positive GEX usually dampens them."
        )
        row3_c1, row3_c2 = st.columns([1.5, 1])
        with row3_c1:
            st.plotly_chart(make_gex_chart(chain_data),
                            use_container_width=True, key="chart_gex")
        with row3_c2:
            if total_gex is None or not chain_data.get("gex"):
                st.info("GEX regime unavailable because the options chain feed returned no usable strikes.")
            else:
                gex_regime, gex_color = _classify_gex_regime(total_gex)
                st.markdown(
                    f"""
<div style="background:#161b27;border:1px solid {gex_color};border-radius:10px;padding:16px 18px;margin-bottom:12px;">
  <div style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.08em">GEX Regime</div>
  <div style="color:{gex_color};font-size:28px;font-weight:700;margin-top:6px;">{gex_regime}</div>
  <div style="color:#94a3b8;font-size:13px;margin-top:8px;">
    {"Dealers are short gamma, so hedging pressure can push price farther in the direction of the move." if total_gex < 0 else "Dealers are long gamma, so hedging pressure can lean against large moves and stabilize price."}
  </div>
</div>

- **What matters most:** {"expect more intraday whipsaws and faster trend extension" if total_gex < 0 else "expect more mean reversion and slower follow-through"}.
- **Key positive gamma strike:** {f"{pos_gex_strike:,.0f}" if pos_gex_strike is not None else "N/A"}.
- **Key negative gamma strike:** {f"{neg_gex_strike:,.0f}" if neg_gex_strike is not None else "N/A"}.
- **How to use it:** compare spot ({spot:.2f} if available in the chart) with these strikes to judge whether price is near a pinning zone or an air pocket.
                """,
                    unsafe_allow_html=True,
                )

        st.divider()

        st.subheader("🧭 Additional Structure Views")
        if simple_mode:
            st.caption(
                "These charts answer three plain questions: is current vol only near-term or across expiries, "
                "where is positioning most defensive, and where is dealer pressure likely to pin or accelerate price."
            )
        else:
            st.caption(
                "Term structure isolates front-end stress, the heatmap shows where gamma is concentrated across expiries, "
                "and the remaining panels translate strike inventory into likely pinning or hedge-flow behavior."
            )

        row4_c1, row4_c2, row4_c3 = st.columns(3)
        with row4_c1:
            st.plotly_chart(make_gex_flip_timeline_chart(chain_data),
                            use_container_width=True, key="chart_gex_flip_timeline")
        with row4_c2:
            st.plotly_chart(make_iv_term_structure_chart(chain_data),
                            use_container_width=True, key="chart_iv_term_structure")
        with row4_c3:
            st.plotly_chart(make_pc_ratio_by_strike_chart(chain_data),
                            use_container_width=True, key="chart_pc_ratio_by_strike")

        row5_c1, row5_c2, row5_c3 = st.columns(3)
        with row5_c1:
            st.plotly_chart(make_gex_heatmap_chart(chain_data),
                            use_container_width=True, key="chart_gex_heatmap")
        with row5_c2:
            st.plotly_chart(make_max_pain_chart(chain_data),
                            use_container_width=True, key="chart_max_pain")
        with row5_c3:
            st.plotly_chart(make_delta_flow_chart(chain_data),
                            use_container_width=True, key="chart_delta_flow")

        st.markdown(
            """
- **How to read it quickly:** start with the summary ribbon, then check the OI wall for crowded strikes, then confirm whether GEX is dampening or amplifying moves.
- **If GEX is negative:** crowded strikes can break harder because dealers hedge with the move rather than against it.
- **If put/call ratio is high at a strike:** traders are defensively positioned there, so protection demand is concentrated.
- **If max pain and spot are close:** expiry pinning risk is higher; if they are far apart, positioning is less likely to pin price cleanly.
        """
        )


def render_liquidity_conditions(fred, mkt, treasury, sofr_data, amihud_data):
    """
    Liquidity Conditions tab.
    Displays composite liquidity score, key stress indicators,
    yield curve inversion, TED spread, NFCI/STLFSI2, Amihud illiquidity,
    MOVE index, and loan officer tightening standards.
    """
    liq = compute_composite_liquidity_score(fred, mkt)

    nfci_v = _get_val(fred, "NFCI")
    stl_v = _get_val(fred, "STLFSI2")
    ted_v = _get_val(fred, "TEDRATE")
    t3m_v = _get_val(fred, "T10Y3M")
    move_v = (mkt.get("^MOVE") or {}).get("value")
    hy_v = _get_val(fred, "BAMLH0A0HYM2")
    drt_v = _get_val(fred, "DRTSCILM")
    liq_score = liq.get("score")
    liq_label = liq.get("label", "Unavailable")
    liq_color = liq.get("color", "#94a3b8")

    if liq_score is not None and liq_score > 1.5:
        st.error(f"🚨 Liquidity Stress: Composite score {liq_score:.2f} — multiple indicators signaling funding pressure.")
    elif liq_score is not None and liq_score > 0.5:
        st.warning(f"⚠️ Liquidity Tightening: Composite score {liq_score:.2f} — conditions are deteriorating.")
    else:
        st.success(f"✅ Liquidity conditions: {liq_label} (score: {liq_score:.2f})" if liq_score is not None else "Liquidity data loading…")

    if t3m_v is not None and t3m_v < 0:
        st.error(f"🔴 Yield Curve Inverted (10Y-3M): {t3m_v:.2f}% — historically precedes recessions by 6–18 months.")
    if ted_v is not None and ted_v > 0.5:
        st.warning(f"⚠️ TED Spread elevated at {ted_v:.3f}% — interbank funding stress signal.")
    if move_v is not None and move_v > 130:
        st.warning(f"⚠️ MOVE Index at {move_v:.0f} — bond market volatility elevated, fixed income liquidity impaired.")
    if drt_v is not None and drt_v > 40:
        st.error(f"🔴 Loan Officer Tightening Standards at {drt_v:.0f}% — credit availability severely restricted.")

    score_text = f"{liq_score:.2f}" if liq_score is not None else "N/A"
    st.markdown(
        f'<div style="background:#161b27;border:1px solid {liq_color};border-radius:10px;'
        f'padding:14px 20px;margin-bottom:16px;display:flex;align-items:center;gap:24px;">'
        f'<span style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.08em">Composite Liquidity Score</span>'
        f'<span style="color:{liq_color};font-size:28px;font-weight:700;">{score_text}</span>'
        f'<span style="color:{liq_color};font-size:16px;font-weight:600;">{liq_label}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("NFCI", f"{nfci_v:.3f}" if nfci_v is not None else "N/A",
              delta=f"{nfci_v:.3f} vs 0" if nfci_v is not None else None,
              delta_color="inverse")
    k2.metric("STLFSI2", f"{stl_v:.3f}" if stl_v is not None else "N/A",
              delta=f"{stl_v:.3f} vs 0" if stl_v is not None else None,
              delta_color="inverse")
    k3.metric("TED Spread", f"{ted_v:.3f}%" if ted_v is not None else "N/A",
              delta=f"{(ted_v or 0) - 0.35:.3f} vs norm" if ted_v is not None else None,
              delta_color="inverse")
    k4.metric("10Y-3M Spread", f"{t3m_v:.2f}%" if t3m_v is not None else "N/A",
              delta=f"{'Inverted' if (t3m_v or 1) < 0 else 'Normal'}" if t3m_v is not None else None,
              delta_color="inverse")
    k5.metric("MOVE Index", f"{move_v:.0f}" if move_v is not None else "N/A",
              delta=f"{(move_v or 0) - 100:.0f} vs 100" if move_v is not None else None,
              delta_color="inverse")
    k6.metric("HY Spread", f"{hy_v:.0f} bp" if hy_v is not None else "N/A",
              delta=f"{(hy_v or 0) - 400:.0f} vs 400" if hy_v is not None else None,
              delta_color="inverse")

    st.divider()

    st.subheader("Financial Conditions & Yield Curve")
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.plotly_chart(make_liquidity_stress_chart(fred), use_container_width=True, key="chart_liq_stress")
    with r2c2:
        st.plotly_chart(make_yield_spread_history_chart(fred), use_container_width=True, key="chart_yield_spread_hist")

    real10 = None
    dgs10 = _get_val(fred, "DGS10")
    breakeven10 = _get_val(fred, "T10YIE")
    if dgs10 is not None and breakeven10 is not None:
        real10 = round(float(dgs10) - float(breakeven10), 2)
    r2k1, r2k2, r2k3 = st.columns(3)
    r2k1.metric(
        "M2 YoY Change",
        f"{compute_m2_yoy_change(fred):+.2f}%" if compute_m2_yoy_change(fred) is not None else "N/A",
        delta="Liquidity drain" if compute_m2_yoy_change(fred) is not None and compute_m2_yoy_change(fred) < 0 else "Liquidity expanding" if compute_m2_yoy_change(fred) is not None else None,
        delta_color="inverse" if compute_m2_yoy_change(fred) is not None and compute_m2_yoy_change(fred) < 0 else "normal",
    )
    r2k2.metric("IG Credit Spread", f"{_get_val(fred, 'BAMLC0A0CM'):.0f} bp" if _get_val(fred, "BAMLC0A0CM") is not None else "N/A", delta_color="inverse")
    r2k3.metric(
        "Real 10Y Yield",
        f"{real10:.2f}%" if real10 is not None else "N/A",
        delta="Restrictive" if real10 is not None and real10 > 2.5 else "Normal" if real10 is not None else None,
        delta_color="inverse" if real10 is not None and real10 > 2.5 else "normal",
    )

    r2c3, r2c4 = st.columns(2)
    with r2c3:
        st.plotly_chart(
            make_fred_history_line_chart(fred, "M2SL_YOY_HIST", "M2 Money Supply YoY Change — 24M", "%", "#3b82f6", zero_line=True),
            use_container_width=True,
            key="chart_liq_m2_yoy",
        )
    with r2c4:
        st.plotly_chart(
            make_credit_spread_comparison_chart(fred),
            use_container_width=True,
            key="chart_liq_ig_hy_spreads",
        )

    st.divider()

    st.subheader("Funding Stress & Market Depth")
    st.caption(
        "Simple read: TED spread shows stress in bank funding markets; Amihud shows how easily equities trade. "
        "If both rise together, liquidity is getting thinner and price moves usually become less stable."
    )

    ted_val = _get_val(fred, "TEDRATE")
    ted_hist = fred.get("TEDRATE_HIST", [])
    ted_peak = None
    if ted_hist:
        try:
            ted_peak = max(float(v) for v, _ in ted_hist if v is not None)
        except Exception:
            ted_peak = None

    if ted_val is not None:
        if ted_val < 0.5:
            ted_zone_label, ted_zone_color = "Normal", "#34d399"
        elif ted_val < 1.0:
            ted_zone_label, ted_zone_color = "Watch Zone", "#fbbf24"
        else:
            ted_zone_label, ted_zone_color = "Stress Zone", "#f87171"
    else:
        ted_zone_label, ted_zone_color = "N/A", "#94a3b8"

    ted_k1, ted_k2, ted_k3 = st.columns(3)
    ted_k1.metric("Current TED Spread", f"{ted_val:.2f}%" if ted_val is not None else "N/A")
    ted_k2.markdown(
        f'<div style="background:#161b27;border:1px solid {ted_zone_color};border-radius:10px;'
        f'padding:16px 18px;height:100%">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Risk Zone</div>'
        f'<div style="color:{ted_zone_color};font-size:24px;font-weight:700;margin-top:4px">{ted_zone_label}</div>'
        f'<div style="color:#94a3b8;font-size:12px;margin-top:6px">'
        f'Below 0.5% = normal · 0.5–1.0% = watch · above 1.0% = stress</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    ted_k3.metric("Peak in Window", f"{ted_peak:.2f}%" if ted_peak is not None else "N/A")

    r3c1, r3c2 = st.columns(2)
    with r3c1:
        st.plotly_chart(make_ted_spread_chart(fred), use_container_width=True, key="chart_ted_spread")
        st.markdown(
            """
            **How to read this:**
            1. Rising TED spread means banks are demanding more premium to lend to each other.
            2. Above `0.5%` means funding is worth watching; above `1.0%` means stress is elevated.
            3. A rising line plus red/yellow zones matters more than any single point.
            """,
        )
    with r3c2:
        st.plotly_chart(make_amihud_chart(amihud_data), use_container_width=True, key="chart_amihud")
        if amihud_data and amihud_data.get("value") is not None:
            st.caption(f"Current Amihud ratio: {amihud_data['value']:.6f} — higher = worse liquidity")

    st.divider()

    st.subheader("Funding Rates & Credit Availability")
    r4c1, r4c2 = st.columns(2)

    with r4c1:
        sofr_val = sofr_data.get("value") if sofr_data else None
        dff_val = _get_val(fred, "DFF")
        st.markdown("**SOFR vs Fed Funds Rate**")
        s1, s2 = st.columns(2)
        s1.metric("SOFR Rate", f"{sofr_val:.3f}%" if sofr_val is not None else "N/A")
        s2.metric("Fed Funds Rate", f"{dff_val:.2f}%" if dff_val is not None else "N/A")
        if sofr_val is not None and dff_val is not None:
            spread_sofr_dff = round(sofr_val - dff_val, 3)
            sc = "#34d399" if abs(spread_sofr_dff) < 0.15 else "#fbbf24"
            st.markdown(
                f'<div style="margin-top:8px;padding:8px;background:#161b27;border-radius:6px;">'
                f'<span style="color:#94a3b8;font-size:12px">SOFR − Fed Funds: </span>'
                f'<b style="color:{sc}">{spread_sofr_dff:+.3f}%</b>'
                f'<span style="color:#64748b;font-size:11px;margin-left:6px">'
                f'{"Normal" if abs(spread_sofr_dff) < 0.15 else "Watch — funding dislocation"}'
                f'</span></div>',
                unsafe_allow_html=True
            )
        st.caption(f"Source: {sofr_data.get('source_tag', '—')} · {sofr_data.get('date', '')}" if sofr_data else "SOFR unavailable")

    with r4c2:
        st.markdown("**Loan Officer Tightening Standards (DRTSCILM)**")
        if drt_v is not None:
            drt_color = "#f87171" if drt_v > 40 else "#fbbf24" if drt_v > 20 else "#34d399"
            st.markdown(
                f'<div style="background:#161b27;border-radius:8px;padding:14px 18px;">'
                f'<span style="color:#94a3b8;font-size:12px">% of banks tightening C&I loan standards</span><br>'
                f'<span style="color:{drt_color};font-size:26px;font-weight:700;">{drt_v:.1f}%</span>'
                f'<span style="color:#64748b;font-size:11px;margin-left:8px">'
                f'{"Severe tightening" if drt_v > 40 else "Moderate tightening" if drt_v > 20 else "Easing / Neutral"}'
                f'</span></div>',
                unsafe_allow_html=True
            )
        else:
            st.info("Loan officer data unavailable (FRED DRTSCILM).")

    st.divider()

    st.subheader("Composite Score Components")
    if liq["components"]:
        comp_cols = st.columns(len(liq["components"]))
        for i, (k, v) in enumerate(liq["components"].items()):
            c = "#f87171" if v > 1 else "#fbbf24" if v > 0 else "#34d399"
            comp_cols[i].markdown(
                f'<div style="background:#161b27;border-radius:8px;padding:10px 14px;text-align:center;">'
                f'<div style="color:#94a3b8;font-size:11px;">{k}</div>'
                f'<div style="color:{c};font-size:20px;font-weight:700;">{v:+.2f}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.caption("Z-scores relative to long-run baselines. >0 = tighter than normal, <0 = looser.")
    else:
        st.info("Composite score components unavailable — check data sources.")

    with st.expander("📖 Liquidity Signal Guide"):
        st.markdown("""
| Indicator | Ample | Watch | Stress |
|---|---|---|---|
| **NFCI** | < −0.5 | −0.5 to +0.5 | > +0.5 |
| **STLFSI2** | < −0.5 | −0.5 to +1.0 | > +1.0 |
| **TED Spread** | < 0.30% | 0.30–0.50% | > 0.50% |
| **10Y-3M Spread** | > +0.5% | 0 to +0.5% | < 0% (inverted) |
| **MOVE Index** | < 80 | 80–130 | > 130 |
| **HY Spread** | < 300 bp | 300–500 bp | > 500 bp |
| **Amihud Ratio** | Low & stable | Rising | Spike |
| **SOFR − Fed Funds** | ±0.10% | ±0.10–0.25% | > ±0.25% |
| **Loan Tightening** | < 20% | 20–40% | > 40% |

**Composite Score Interpretation:**
- `> +1.5` → 🔴 Stress — funding markets under pressure, reduce risk
- `+0.5 to +1.5` → 🟡 Tightening — conditions deteriorating, stay cautious
- `−0.5 to +0.5` → 🟢 Neutral — normal liquidity environment
- `< −0.5` → 💧 Ample — easy financial conditions, supports risk assets
        """)


def render_institutional_flows(fred, cot_data, ici_data, mmf_history, inst13f,
                               cta_model=None, sg_cta=None):
    """
    Institutional Flows tab.
    Shows COT positioning, ICI fund flows, MMF assets/flows, 13F institutional
    ownership summary, and composite institutional participation score.
    """
    inst_score = compute_institutional_participation_score(cot_data, ici_data, mmf_history, fred)
    beginner_mode = is_beginner_mode()

    retail_mmf_entry = (fred.get("WRMFNS") or fred.get("WRMFSL") or {})
    inst_mmf_entry = (fred.get("WIMFNS") or fred.get("WIMFSL") or {})
    wrmfns_v = retail_mmf_entry.get("value")
    wrmfsl_v = retail_mmf_entry.get("last_value") or retail_mmf_entry.get("value")

    if inst_score.get("score") is not None and inst_score["score"] > 1.5:
        st.error("🚨 Institutional Withdrawal: Multiple signals show institutions moving to cash — liquidity risk elevated 4–8 weeks ahead.")
    elif inst_score.get("score") is not None and inst_score["score"] > 0.5:
        st.warning("⚠️ Institutions are reducing equity exposure — watch for liquidity deterioration.")
    else:
        label = inst_score.get("label", "Loading…")
        score = inst_score.get("score")
        st.success(f"✅ Institutional positioning: {label}" + (f" (score: {score:.2f})" if score is not None else ""))

    if wrmfns_v is not None and wrmfns_v > 6000:
        st.error(f"🔴 Retail MMF assets at ${wrmfns_v:,.0f}B — cash levels are historically high and still risk-off.")
    elif wrmfns_v is not None and wrmfns_v > 5000:
        st.warning(f"⚠️ Retail MMF assets at ${wrmfns_v:,.0f}B — elevated cash buildup, monitor for further defensive positioning.")

    if cot_data and "SP500_Emini" in cot_data:
        net = cot_data["SP500_Emini"].get("net_nc", 0)
        if net < -200000:
            st.error(f"🔴 COT: Large specs NET SHORT S&P 500 futures ({net:,.0f} contracts) — extreme bearish institutional positioning.")
        elif net < 0:
            st.warning(f"⚠️ COT: Large specs net short S&P 500 ({net:,.0f}) — defensive positioning.")

    sc = inst_score.get("score")
    lbl = inst_score.get("label", "N/A")
    color = inst_score.get("color", "#94a3b8")
    st.markdown(
        f'<div style="background:#161b27;border:1px solid {color};border-radius:10px;'
        f'padding:14px 20px;margin-bottom:16px;display:flex;align-items:center;gap:24px;">'
        f'<span style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.08em">'
        f'Institutional Participation Score</span>'
        f'<span style="color:{color};font-size:28px;font-weight:700;">'
        f'{sc:.2f}</span>'
        f'<span style="color:{color};font-size:16px;font-weight:600;">{lbl}</span>'
        f'</div>' if sc is not None else
        f'<div style="background:#161b27;border:1px solid #94a3b8;border-radius:10px;padding:14px 20px;margin-bottom:16px;">'
        f'<span style="color:#94a3b8">Institutional score loading — data may be delayed.</span></div>',
        unsafe_allow_html=True
    )

    k1, k2, k3, k4, k5 = st.columns(5)

    cot_sp = cot_data.get("SP500_Emini", {}) if cot_data else {}
    cot_10y = cot_data.get("Treasury_10Y", {}) if cot_data else {}
    ici_eq = ici_data.get("latest_equity") if ici_data else None
    ici_mm = ici_data.get("latest_money_market") if ici_data else None

    k1.metric(
        "S&P 500 Net Non-Comm",
        f"{cot_sp.get('net_nc', 0):,.0f}" if cot_sp else "N/A",
        delta="Long" if (cot_sp.get("net_nc") or 0) > 0 else "Short",
        delta_color="normal" if (cot_sp.get("net_nc") or 0) > 0 else "inverse"
    )
    k2.metric(
        "10Y T-Note Net Lev.",
        f"{cot_10y.get('net_lev', 0):,.0f}" if cot_10y else "N/A",
        delta="Long bonds" if (cot_10y.get("net_lev") or 0) > 0 else "Short bonds",
        delta_color="inverse" if (cot_10y.get("net_lev") or 0) > 0 else "normal"
    )
    k3.metric(
        "ICI Equity Flows",
        f"${ici_eq:,.1f}B" if ici_eq is not None else "N/A",
        delta=f"{'Inflow' if (ici_eq or 0) > 0 else 'Outflow'}",
        delta_color="normal" if (ici_eq or 0) > 0 else "inverse"
    )
    k4.metric(
        "Retail MMF Assets",
        f"${wrmfns_v:,.0f}B" if wrmfns_v is not None else "N/A",
        delta=f"{wrmfns_v - 5000:+.0f}B vs 5T ref" if wrmfns_v is not None else None,
        delta_color="inverse"
    )
    k5.metric(
        "ICI Money Market Flow",
        f"${ici_mm:,.1f}B" if ici_mm is not None else "N/A",
        delta="Into cash" if (ici_mm or 0) > 0 else "Out of cash",
        delta_color="inverse" if (ici_mm or 0) > 0 else "normal"
    )

    st.divider()

    cot_container = st.expander("Advanced futures positioning detail", expanded=False) if beginner_mode else st.container()
    with cot_container:
        st.subheader("CFTC Commitment of Traders — Futures Positioning")
        st.caption("Weekly data (Tuesday positions, published Friday). Non-Commercial = hedge funds + CTAs. Leveraged = hedge funds only.")
        cot_tabs = st.tabs(["S&P 500 E-mini", "10Y T-Note", "VIX Futures", "USD Index"])

        for tab, key in zip(cot_tabs, ["SP500_Emini", "Treasury_10Y", "VIX_Futures", "USD_Index"]):
            with tab:
                st.plotly_chart(
                    make_cot_chart(cot_data, market_key=key),
                    use_container_width=True,
                    key=f"chart_cot_{key}"
                )
                if cot_data and key in cot_data:
                    d = cot_data[key]
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Net Non-Commercial", f"{d.get('net_nc', 0):,.0f}")
                    c2.metric("Net Leveraged Funds", f"{d.get('net_lev', 0):,.0f}")
                    c3.metric("Open Interest", f"{d.get('open_interest', 0):,.0f}")
                    st.caption(f"Report date: {d.get('date', 'N/A')} · Source: CFTC Public Reporting API")
                else:
                    st.info(f"COT data unavailable for {key}. Check CFTC API or network access.")

    st.divider()

    st.subheader("Mutual Fund & ETF Flows")
    st.caption(
        "Read this block in two parts: ICI shows weekly demand for equity and bond funds; "
        "money market flows show whether investors are moving into cash or out of it."
    )

    inst_v = inst_mmf_entry.get("value")
    inst_last_v = inst_mmf_entry.get("last_value") or inst_v
    inst_date = inst_mmf_entry.get("date")
    ret_v = retail_mmf_entry.get("value")
    ici_bond = ici_data.get("bond") if ici_data else None

    flow_k1, flow_k2, flow_k3, flow_k4 = st.columns(4)
    flow_k1.metric(
        "ICI Equity Flow",
        f"${ici_eq:,.1f}B" if ici_eq is not None else "N/A",
        delta=("Inflow" if ici_eq > 0 else "Outflow") if ici_eq is not None else None,
        delta_color="normal" if (ici_eq or 0) > 0 else "inverse",
    )
    flow_k2.metric(
        "ICI Bond Flow",
        f"${ici_bond:,.1f}B" if ici_bond is not None else "N/A",
        delta=("Inflow" if ici_bond > 0 else "Outflow") if ici_bond is not None else None,
        delta_color="normal" if (ici_bond or 0) > 0 else "inverse",
    )
    flow_k3.metric("Institutional MMF (disc.)", f"${inst_last_v:,.0f}B" if inst_last_v is not None else "N/A")
    flow_k4.metric("Retail MMF Total", f"${ret_v:,.0f}B" if ret_v is not None else "N/A")
    st.caption(
        f"Retail MMF uses current FRED WRMFNS. "
        f"Institutional weekly MMF series were discontinued by the Fed after {inst_date or '2021-02-01'}, "
        f"so they are shown only as last-known history."
    )

    if ici_data:
        r3c1, r3c2 = st.columns([1.0, 1.25])
        with r3c1:
            st.plotly_chart(make_ici_flows_chart(ici_data), use_container_width=True, key="chart_ici_flows")
            st.caption(f"Source: {ici_data.get('source', 'ICI')} · Latest week: {ici_data.get('date', 'N/A')}")
        with r3c2:
            st.plotly_chart(make_mmf_flow_chart(mmf_history), use_container_width=True, key="chart_mmf_flows")
            st.caption(
                "Positive MMF flow means cash is being parked defensively. "
                "Negative flow means cash is being redeployed into risk assets."
            )
    else:
        r3c1, r3c2 = st.columns([0.85, 1.55])
        with r3c1:
            st.markdown(
                '<div style="background:#161b27;border:1px solid #1e2d3d;border-radius:10px;'
                'padding:18px 20px;min-height:240px;">'
                '<div style="color:#e2e8f0;font-size:22px;font-weight:700;margin-bottom:10px;">'
                'ICI fund flow data unavailable</div>'
                '<div style="color:#94a3b8;font-size:13px;line-height:1.6;">'
                'The ICI weekly workbook did not load, so equity and bond fund-flow data is missing for this refresh.'
                '<br><br><strong style="color:#e2e8f0;">What you can still use here:</strong>'
                '<br>• Money market fund flows still show whether investors are moving into cash.'
                '<br>• MMF totals still show how much cash remains parked on the sidelines.'
                '<br>• Use the chart on the right as the live read until the ICI feed returns.'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.caption("ICI XLS endpoint may be temporarily down.")
        with r3c2:
            st.plotly_chart(make_mmf_flow_chart(mmf_history), use_container_width=True, key="chart_mmf_flows")
            st.caption(
                "Positive MMF flow means cash is being parked defensively. "
                "Negative flow means cash is being redeployed into risk assets."
            )

    st.divider()

    form13f_container = st.expander("Advanced ownership detail (13F filings)", expanded=False) if beginner_mode else st.container()
    with form13f_container:
        st.subheader("SEC Form 13F — Institutional Ownership")
        if inst13f:
            if inst13f.get("top_holders"):
                st.caption(f"Top institutional holders of SPY · Source: {inst13f.get('source', 'SEC')}")
                holder_cols = st.columns(min(5, len(inst13f["top_holders"])))
                for i, holder in enumerate(inst13f["top_holders"][:5]):
                    chg = holder.get("change", 0)
                    chg_color = "#34d399" if chg > 0 else "#f87171" if chg < 0 else "#94a3b8"
                    with holder_cols[i % 5]:
                        st.markdown(
                            f'<div style="background:#161b27;border-radius:8px;padding:10px 12px;margin-bottom:8px;">'
                            f'<div style="color:#94a3b8;font-size:10px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">'
                            f'{holder["name"][:24]}</div>'
                            f'<div style="color:#e2e8f0;font-size:13px;font-weight:600">'
                            f'{holder["shares"]/1e6:.1f}M sh</div>'
                            f'<div style="color:{chg_color};font-size:11px">'
                            f'{"+" if chg > 0 else ""}{chg/1e3:.0f}K chg</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
            elif inst13f.get("total_filings"):
                st.info(
                    f"📄 {inst13f.get('note', '')} · Source: {inst13f.get('source', 'SEC EDGAR')} · "
                    f"Add a Finnhub API key (FINNHUBAPIKEY) to the sidebar for detailed holder data."
                )
            else:
                st.info("13F data unavailable. Add FINNHUBAPIKEY to sidebar for institutional ownership data.")
        else:
            st.info("13F data unavailable. Add FINNHUBAPIKEY to sidebar for institutional ownership data.")

    st.divider()

    st.subheader("Participation Score Components")
    comp = inst_score.get("components", {})
    comp_labels = {
        "mmf_flow": "MMF Inflow z",
        "cot_sp500": "COT Short z",
        "ici_equity": "Equity Outflow z",
        "mmf_level": "MMF Level z",
    }
    if comp:
        ccols = st.columns(len(comp))
        for i, (k, v) in enumerate(comp.items()):
            c = "#f87171" if v > 1 else "#fbbf24" if v > 0 else "#34d399"
            ccols[i].markdown(
                f'<div style="background:#161b27;border-radius:8px;padding:10px 14px;text-align:center;">'
                f'<div style="color:#94a3b8;font-size:11px;">{comp_labels.get(k, k)}</div>'
                f'<div style="color:{c};font-size:20px;font-weight:700;">{v:+.2f}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.caption("Z-scores vs. rolling window. Positive = more risk-off than average. Score > +1.5 = institutions exiting.")
    else:
        st.info("Score components unavailable — insufficient historical data yet.")

    st.divider()

    with st.expander("CTA Flow Tracker", expanded=True):
        st.subheader("CTA Flow Tracker")
        st.caption(
            "CTAs are systematic trend-followers. Their positions can be modeled from "
            "price vs. moving averages (20d/63d/252d). "
            "Signal +1 = model fully long, −1 = fully short. "
            "Source: computed from yfinance OHLCV + CFTC Leveraged Funds COT."
        )

        if cta_model:
            eq_score = cta_model.get("equity_score", 0)
            eq_label = cta_model.get("equity_label", "N/A")
            eq_color = cta_model.get("equity_color", "#94a3b8")

            sg_strip = ""
            if sg_cta:
                sg_color = sg_cta.get("color", "#94a3b8")
                sg_ret = sg_cta.get("latest_month_return")
                sg_ytd = sg_cta.get("ytd_return")
                sg_src = sg_cta.get("source", "SG CTA Index")
                parts = []
                if sg_ret is not None:
                    parts.append(f'<span style="color:{sg_color}">Latest month: {sg_ret:+.2f}%</span>')
                if sg_ytd is not None:
                    parts.append(f'<span style="color:{sg_color}">YTD: {sg_ytd:+.2f}%</span>')
                if parts:
                    sg_strip = (
                        f'<span style="color:#94a3b8;font-size:11px;margin-left:16px">'
                        f'{sg_src}: {" · ".join(parts)}</span>'
                    )

            st.markdown(
                f'<div style="background:#161b27;border:1px solid {eq_color};border-radius:10px;'
                f'padding:14px 20px;margin-bottom:16px;display:flex;align-items:center;gap:24px;flex-wrap:wrap">'
                f'<span style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.08em">'
                f'CTA Equity Exposure Score</span>'
                f'<span style="color:{eq_color};font-size:28px;font-weight:700;">'
                f"{eq_score:+.2f}</span>"
                f'<span style="color:{eq_color};font-size:16px;font-weight:600;">{eq_label}</span>'
                f"{sg_strip}"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("CTA model building… yfinance data may take a moment on first load.")

        cta_k1, cta_k2, cta_k3, cta_k4, cta_k5 = st.columns(5)

        cot_sp = cot_data.get("SP500_Emini", {}) if cot_data else {}

        cta_k1.metric(
            "Model S&P Signal",
            f'{cta_model["assets"]["SPY"]["normalized"]:+.2f}' if cta_model and "SPY" in cta_model.get("assets", {}) else "N/A",
            delta="Long" if cta_model and cta_model.get("assets", {}).get("SPY", {}).get("normalized", 0) > 0 else "Short",
            delta_color="normal" if cta_model and cta_model.get("assets", {}).get("SPY", {}).get("normalized", 0) > 0 else "inverse",
        )
        cta_k2.metric(
            "Model QQQ Signal",
            f'{cta_model["assets"]["QQQ"]["normalized"]:+.2f}' if cta_model and "QQQ" in cta_model.get("assets", {}) else "N/A",
            delta="Long" if cta_model and cta_model.get("assets", {}).get("QQQ", {}).get("normalized", 0) > 0 else "Short",
            delta_color="normal" if cta_model and cta_model.get("assets", {}).get("QQQ", {}).get("normalized", 0) > 0 else "inverse",
        )
        cta_k3.metric(
            "Model TLT Signal",
            f'{cta_model["assets"]["TLT"]["normalized"]:+.2f}' if cta_model and "TLT" in cta_model.get("assets", {}) else "N/A",
            delta="Long bonds" if cta_model and cta_model.get("assets", {}).get("TLT", {}).get("normalized", 0) > 0 else "Short bonds",
            delta_color="normal" if cta_model and cta_model.get("assets", {}).get("TLT", {}).get("normalized", 0) > 0 else "inverse",
        )
        cta_k4.metric(
            "CFTC Lev. Funds S&P",
            f"{cot_sp.get('net_lev', 0):,.0f}" if cot_sp else "N/A",
            delta="Long" if (cot_sp.get("net_lev") or 0) > 0 else "Short",
            delta_color="normal" if (cot_sp.get("net_lev") or 0) > 0 else "inverse",
        )
        cta_k5.metric(
            "SG CTA YTD",
            f"{sg_cta['ytd_return']:+.2f}%" if sg_cta and sg_cta.get("ytd_return") is not None else "N/A",
            delta="Adding positions" if sg_cta and (sg_cta.get("ytd_return") or 0) > 0 else "Reducing positions",
            delta_color="normal" if sg_cta and (sg_cta.get("ytd_return") or 0) > 0 else "inverse",
        )

        cta_c1, cta_c2 = st.columns(2)
        with cta_c1:
            st.plotly_chart(
                make_cta_signal_chart(cta_model),
                use_container_width=True,
                key="chart_cta_signals",
            )
        with cta_c2:
            if cta_model:
                history_ticker = st.selectbox(
                    "Show CTA signal history for:",
                    options=list(cta_model.get("assets", {}).keys()),
                    format_func=lambda t: cta_model["assets"][t]["label"],
                    key="cta_history_ticker",
                )
                st.plotly_chart(
                    make_cta_history_chart(cta_model, ticker=history_ticker),
                    use_container_width=True,
                    key="chart_cta_history",
                )
            else:
                st.info("CTA history chart unavailable.")

        st.subheader("Price vs. Moving Averages (CTA Trigger Levels)")
        st.caption(
            "CTAs mechanically buy when price crosses above key MAs and sell when it breaks below. "
            "These levels are the actual trigger thresholds the models react to."
        )
        if cta_model:
            st.markdown(make_cta_ma_table(cta_model), unsafe_allow_html=True)
        else:
            st.info("MA table unavailable — model still loading.")

        with st.expander("📊 CFTC Leveraged Funds Detail (CTA Proxy)"):
            st.caption(
                "CFTC 'Leveraged Funds' category = registered CTAs + CPOs + unregistered "
                "systematic funds. This is the official government proxy for CTA positioning. "
                "Updated every Friday (Tuesday positions)."
            )
            cot_tabs2 = st.tabs(["S&P 500 E-mini", "10Y T-Note", "VIX Futures", "USD Index"])
            for tab, key in zip(cot_tabs2, ["SP500_Emini", "Treasury_10Y", "VIX_Futures", "USD_Index"]):
                with tab:
                    st.plotly_chart(
                        make_cot_chart(cot_data, market_key=key),
                        use_container_width=True,
                        key=f"chart_cta_cot_{key}",
                    )

    with st.expander("📖 Institutional Flow Signal Guide"):
        st.markdown("""
| Indicator | Bullish (Liquid) | Neutral | Bearish (Illiquid) |
|---|---|---|---|
| **COT S&P Net Non-Comm** | > +100K long | −50K to +100K | < −50K short |
| **COT 10Y Net Leveraged** | Net long bonds (flight-to-safety) | Neutral | Extreme short bonds |
| **ICI Equity Flows** | Consistent inflows | Mixed | Sustained outflows |
| **ICI Money Market** | Flat / small | Moderate | Large spike inflows |
| **Inst. MMF Assets (WRMFNS)** | < $5T | $5–6T | > $6T |
| **Participation Score** | < −0.5 | −0.5 to +0.5 | > +1.5 |
| **CTA Model Signal (SPY)** | > +0.5 (long) | −0.5 to +0.5 | < −0.5 (short) |
| **CTA Equity Composite** | > +0.5 | −0.1 to +0.5 | < −0.5 |
| **SG CTA YTD Return** | Positive (adding) | Flat | Negative (reducing) |
| **CFTC Leveraged Funds S&P** | Net long > +50K | Neutral | Net short < −50K |

**Why this matters for liquidity:**
- When institutions move to MMFs, they pull bid support from equities and credit — bid-ask spreads widen 2–6 weeks later
- COT extreme short positioning in S&P 500 futures has historically preceded sharp covering rallies (liquidity snapback)
- ICI equity outflows sustained for 3+ weeks signal structural liquidity withdrawal, not just tactical hedging
- The 13F filing lag (45 days after quarter end) makes it a confirmation signal, not a leading one

**How the CTA momentum model works:**
- For each asset, compute price vs. 20d / 63d / 252d moving averages
- Each window gives a ±1 signal (above MA = long, below = short)
- Weighted: 25% short (20d), 50% medium (63d), 25% long (252d)
- Scaled by inverse volatility — volatile assets get smaller position size
- Normalized to −1/+1 using 252d rolling percentile rank
- Signal < −0.5 = CTAs likely selling this asset → watch for liquidity withdrawal

**Key CTA trigger levels to watch:**
- S&P 500: 20d MA, 63d MA, 252d MA — when price breaks these, CTAs flip positions
- When all three MAs are broken to the downside = full CTA short = maximum selling pressure
- Goldman Sachs, BofA, Deutsche Bank all build similar models — their alerts are based on the same MA logic

**Data sources:** CFTC Public Reporting API · ICI.org XLS · SEC EDGAR 13F · FRED WRMFNS/WRMFSL
        """)


def render_sentiment_framework(mkt, opts, skew_idx, fg, aaii, vix_term,
                               pcr_hist, vrp_data, panic_data):
    """
    Sentiment Framework tab — 8-indicator dashboard.
    """
    def safe_norm(val, lo, hi, invert=False):
        try:
            s = max(0.0, min(10.0, (float(val) - lo) / (hi - lo) * 10))
            return round(10 - s if invert else s, 1)
        except Exception:
            return None

    vix_val = (mkt.get("^VIX") or {}).get("value")
    move_val = (mkt.get("^MOVE") or {}).get("value")
    vvix_val = opts.get("vvix") if opts else None
    fg_val = fg.get("value") if fg else None
    aaii_bear = aaii.get("bear") if aaii else None
    skew_val = skew_idx.get("value") if skew_idx else None
    vrp_val = vrp_data.get("vrp") if vrp_data else None
    panic_score = panic_data.get("score") if panic_data else None
    pcr_val = opts.get("pcr") if opts else None
    dspx_val = (mkt.get("^DSPX") or {}).get("value")
    kcj_val = (mkt.get("^KCJ") or {}).get("value")

    aaii_pct_rank = None
    if aaii_bear is not None:
        try:
            lo, hi = INDICATOR_RANGES.get("AAII_BEAR", (10, 55))
            aaii_pct_rank = round(max(0.0, min(100.0, (float(aaii_bear) - lo) / (hi - lo) * 100)), 1)
        except Exception:
            aaii_pct_rank = None

    raw_sub_scores = [
        safe_norm(vix_val, 10, 80),
        safe_norm(vvix_val, 80, 180),
        safe_norm(fg_val, 0, 100, invert=True),
        safe_norm(aaii_bear, 15, 60),
        safe_norm(skew_val, 100, 160),
        safe_norm(move_val, 60, 200),
        safe_norm(vrp_val, -5, 30),
        panic_score,
    ]
    sub_scores = []
    for score in raw_sub_scores:
        if score is None:
            continue
        try:
            sub_scores.append(float(score))
        except Exception:
            continue
    composite_fear = round(sum(sub_scores) / len(sub_scores), 2) if sub_scores else None

    if composite_fear is not None:
        if composite_fear >= 7.5:
            cf_label, cf_color = "🔴 Extreme Fear", "#f87171"
        elif composite_fear >= 5.5:
            cf_label, cf_color = "🟠 Elevated Fear", "#fbbf24"
        elif composite_fear >= 3.5:
            cf_label, cf_color = "🟡 Neutral", "#94a3b8"
        else:
            cf_label, cf_color = "🟢 Greed / Complacency", "#34d399"
    else:
        cf_label, cf_color = "N/A", "#94a3b8"

    if composite_fear is not None and composite_fear >= 7.5:
        st.error(
            "🚨 Sentiment Framework: Composite fear score extremely elevated — "
            "multiple indicators in panic territory simultaneously."
        )
    elif composite_fear is not None and composite_fear >= 5.5:
        st.warning("⚠️ Sentiment Framework: Elevated fear across multiple indicators.")
    else:
        st.success(f"✅ Sentiment: {cf_label}" + (f" (score: {composite_fear:.1f}/10)" if composite_fear is not None else ""))

    st.markdown(
        f'<div style="background:#161b27;border:1px solid {cf_color};border-radius:10px;'
        f'padding:14px 20px;margin-bottom:16px;display:flex;align-items:center;gap:28px;flex-wrap:wrap">'
        f'<span style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.08em">'
        f'Composite Sentiment Fear Score</span>'
        f'<span style="color:{cf_color};font-size:32px;font-weight:700;">'
        f'{composite_fear:.1f}</span>'
        f'<span style="font-size:11px;color:#94a3b8">/10</span>'
        f'<span style="color:{cf_color};font-size:16px;font-weight:600;">{cf_label}</span>'
        f'<span style="color:#94a3b8;font-size:11px;">({len(sub_scores)}/8 indicators available)</span>'
        f'</div>'
        if composite_fear is not None else
        f'<div style="background:#161b27;border:1px solid #94a3b8;border-radius:10px;'
        f'padding:14px 20px;margin-bottom:16px;">'
        f'<span style="color:#94a3b8">Sentiment score loading…</span></div>',
        unsafe_allow_html=True,
    )

    st.subheader("All 8 Indicators — Current Readings")
    k1, k2, k3, k4 = st.columns(4)
    vix_c = "#f87171" if (vix_val or 0) > 30 else "#fbbf24" if (vix_val or 0) > 20 else "#34d399"
    pcr_c = "#f87171" if (pcr_val or 0) > 1.2 else "#34d399" if (pcr_val or 0) < 0.8 else "#fbbf24"
    sk_c = "#f87171" if (skew_val or 0) > 145 else "#34d399" if (skew_val or 0) < 115 else "#fbbf24"
    fg_c = "#f87171" if (fg_val or 50) < 30 else "#34d399" if (fg_val or 50) > 70 else "#fbbf24"
    ps = panic_data.get("score") if panic_data else None
    pc = panic_data.get("color", "#94a3b8") if panic_data else "#94a3b8"

    k1.markdown(
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase">1 · VIX</div>'
        f'<div style="color:{vix_c};font-size:22px;font-weight:700">{vix_val:.1f}</div>'
        f'<div style="color:#94a3b8;font-size:11px">{"⚠️ Backwardation" if (opts or {}).get("backwardation") else "✅ Contango"}</div>'
        f'</div>' if vix_val is not None else
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px">1 · VIX</div><div style="color:#94a3b8">N/A</div></div>',
        unsafe_allow_html=True,
    )
    k2.markdown(
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase">2 · P/C Skew</div>'
        f'<div style="color:{sk_c};font-size:22px;font-weight:700">SKEW {skew_val:.0f}</div>'
        f'<div style="color:{pcr_c};font-size:11px">PCR: {pcr_val:.2f}</div>'
        f'</div>' if (skew_val is not None and pcr_val is not None) else
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px">2 · P/C Skew</div><div style="color:#94a3b8">N/A</div></div>',
        unsafe_allow_html=True,
    )
    k3.markdown(
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase">3 · Fear & Greed</div>'
        f'<div style="color:{fg_c};font-size:22px;font-weight:700">{int(fg_val)}/100</div>'
        f'<div style="color:#94a3b8;font-size:11px">{fg.get("label", "N/A") if fg else "N/A"}</div>'
        f'</div>' if fg_val is not None else
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px">3 · Fear & Greed</div><div style="color:#94a3b8">N/A</div></div>',
        unsafe_allow_html=True,
    )
    k4.markdown(
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase">4 · GS Panic Proxy</div>'
        f'<div style="color:{pc};font-size:22px;font-weight:700">{ps:.2f}/10</div>'
        f'<div style="color:{pc};font-size:11px">{panic_data.get("label", "N/A") if panic_data else "N/A"}</div>'
        f'</div>' if ps is not None else
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px">4 · GS Panic Proxy</div><div style="color:#94a3b8">N/A</div></div>',
        unsafe_allow_html=True,
    )

    k5, k6, k7, k8 = st.columns(4)
    bear_c = "#f87171" if (aaii_bear or 0) > 45 else "#34d399" if (aaii_bear or 0) < 25 else "#fbbf24"
    vrp_c = "#f87171" if (vrp_val or 0) > 25 else "#fbbf24" if (vrp_val or 0) > 10 else "#34d399"
    move_c = "#f87171" if (move_val or 0) > 130 else "#fbbf24" if (move_val or 0) > 100 else "#34d399"
    disp_c = "#f87171" if (dspx_val or 0) >= 15 else "#fbbf24" if (dspx_val or 0) >= 10 else "#34d399"

    k5.markdown(
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase">5 · AAII Bearish %</div>'
        f'<div style="color:{bear_c};font-size:22px;font-weight:700">{aaii_bear:.1f}%</div>'
        f'<div style="color:#94a3b8;font-size:11px">Spread: {aaii.get("spread", 0):+.1f}% · '
        f'{f"{aaii_pct_rank:.0f}th pct" if aaii_pct_rank is not None else "N/A"}</div>'
        f'</div>' if aaii_bear is not None else
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px">5 · AAII Bearish %</div><div style="color:#94a3b8">N/A</div></div>',
        unsafe_allow_html=True,
    )
    k6.markdown(
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase">6 · VRP (IV−RV)</div>'
        f'<div style="color:{vrp_c};font-size:22px;font-weight:700">{vrp_val:+.1f}pt</div>'
        f'<div style="color:#94a3b8;font-size:11px">RV20: {vrp_data.get("rv20", 0):.1f}% · {vrp_data.get("vrp_pct_rank", 0):.0f}th pct</div>'
        f'</div>' if vrp_val is not None and vrp_data else
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px">6 · VRP</div><div style="color:#94a3b8">N/A</div></div>',
        unsafe_allow_html=True,
    )
    k7.markdown(
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase">7 · MOVE Index</div>'
        f'<div style="color:{move_c};font-size:22px;font-weight:700">{move_val:.1f}</div>'
        f'<div style="color:#94a3b8;font-size:11px">{"🔴 Bond vol elevated" if (move_val or 0) > 130 else "🟡 Moderately elevated" if (move_val or 0) > 100 else "🟢 Normal bond vol"}</div>'
        f'</div>' if move_val is not None else
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px">7 · MOVE Index</div><div style="color:#94a3b8">N/A</div></div>',
        unsafe_allow_html=True,
    )
    k8.markdown(
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase">8 · Dispersion/Corr</div>'
        f'<div style="color:{disp_c};font-size:22px;font-weight:700">DSPX {dspx_val:.1f}</div>'
        f'<div style="color:#94a3b8;font-size:11px">KCJ: {kcj_val:.1f} (impl. corr)</div>'
        f'</div>' if (dspx_val is not None and kcj_val is not None) else
        f'<div style="background:#161b27;border-radius:8px;padding:12px 14px;border:1px solid #1e2d3d">'
        f'<div style="color:#94a3b8;font-size:11px">8 · Dispersion/Corr</div>'
        f'<div style="color:#94a3b8">DSPX/KCJ loading — may not be on Yahoo Finance yet</div></div>',
        unsafe_allow_html=True,
    )

    st.divider()

    st.subheader("Sentiment Radar")
    r2c1, r2c2 = st.columns([2, 1])
    with r2c1:
        st.plotly_chart(
            make_sentiment_radar(panic_data, vrp_data, fg, aaii, opts, skew_idx, mkt),
            use_container_width=True,
            key="chart_sentiment_radar",
        )
    with r2c2:
        st.plotly_chart(
            make_gs_panic_gauge(panic_data),
            use_container_width=True,
            key="chart_gs_panic_gauge",
        )
        if panic_data and panic_data.get("components"):
            st.caption("GS Panic Proxy components (percentile rank, available history):")
            comp_labels = {
                "vix_pct": "VIX Percentile",
                "vvix_pct": "VVIX Percentile",
                "skew_pct": "SKEW Percentile",
                "pcr_pct": "PCR Percentile",
            }
            for k_comp, v_comp in panic_data["components"].items():
                c = "#f87171" if v_comp > 85 else "#fbbf24" if v_comp > 65 else "#34d399"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1e2d3d">'
                    f'<span style="color:#94a3b8;font-size:12px">{comp_labels.get(k_comp, k_comp)}</span>'
                    f'<span style="color:{c};font-weight:600;font-size:12px">{v_comp:.0f}th</span></div>',
                    unsafe_allow_html=True,
                )

    st.divider()

    st.subheader("6 · Realized vs Implied Volatility")
    st.caption(
        "VRP = VIX − 20-day Realized Vol. Positive = fear premium (IV expensive). "
        "VRP > 25pt historically = massive warning signal. "
        "VRP < 0 = complacency (realized vol exceeding implied)."
    )
    r3c1, r3c2 = st.columns([2, 1])
    with r3c1:
        st.plotly_chart(make_vrp_chart(vrp_data), use_container_width=True, key="chart_vrp")
    with r3c2:
        if vrp_data:
            st.metric("VRP (Current)", f"{vrp_data['vrp']:+.1f}pt", delta=vrp_data.get("signal", ""))
            st.metric("VIX", f"{vrp_data['vix']:.1f}")
            st.metric("RV 20d", f"{vrp_data['rv20']:.1f}%")
            st.metric("RV 30d", f"{vrp_data['rv30']:.1f}%")
            st.metric("VRP Percentile", f"{vrp_data['vrp_pct_rank']:.0f}th", delta_color="inverse")
        else:
            st.info("VRP data unavailable.")

    st.divider()

    st.subheader("8 · Stock vs Index Dispersion & Correlation")
    r4c1, r4c2 = st.columns(2)
    with r4c1:
        st.plotly_chart(make_dispersion_chart(mkt), use_container_width=True, key="chart_dispersion")
        st.caption(
            "DSPX = CBOE Implied Dispersion. KCJ = CBOE 3-month Implied Correlation. "
            "High DSPX + Low KCJ = hidden chaos. Low DSPX + High KCJ = macro dominance."
        )
    with r4c2:
        st.subheader("1 · VIX Term Structure")
        if vix_term:
            render_vix_term_structure_badge(vix_term)
            st.plotly_chart(
                make_vix_term_chart(vix_term),
                use_container_width=True,
                key="chart_sf_vix_term",
            )
            st.caption("Backwardation is a classic near-term stress signal; contango is the normal state.")
        else:
            st.info("VIX term structure data unavailable.")

    st.divider()

    r5c1, r5c2 = st.columns(2)
    with r5c1:
        st.subheader("5 · AAII Sentiment")
        if aaii:
            bull = aaii.get("bull", 0)
            bear = aaii.get("bear", 0)
            neut = aaii.get("neutral", 0)
            sprd = aaii.get("spread", 0)
            fig_aaii = go.Figure(go.Bar(
                x=["Bullish", "Neutral", "Bearish"],
                y=[bull, neut, bear],
                marker_color=["#34d399", "#94a3b8", "#f87171"],
                text=[f"{bull:.1f}%", f"{neut:.1f}%", f"{bear:.1f}%"],
                textposition="outside",
                hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
            ))
            fig_aaii.add_hline(
                y=45,
                line_color="#f87171",
                line_dash="dot",
                line_width=1,
                opacity=0.6,
                annotation_text="Extreme Bear",
                annotation_font_color="#f87171",
            )
            fig_aaii.add_hline(y=25, line_color="#34d399", line_dash="dot", line_width=1, opacity=0.6)
            fig_aaii.update_layout(
                title=dict(text=f"AAII Sentiment · Bull-Bear Spread: {sprd:+.1f}%", font_size=13),
                yaxis_title="%",
                yaxis=dict(range=[0, 70]),
                template=DARK_TEMPLATE,
                plot_bgcolor=CHART_BG,
                paper_bgcolor=PAPER_BG,
                height=240,
                margin=dict(l=50, r=20, t=45, b=30),
            )
            st.plotly_chart(fig_aaii, use_container_width=True, key="chart_sf_aaii")
            st.caption(
                f"Date: {aaii.get('date', 'N/A')} · "
                f"{f'Bearish percentile: {aaii_pct_rank:.0f}th' if aaii_pct_rank is not None else 'Percentile unavailable'}"
            )
        else:
            st.info("AAII data unavailable.")

    with r5c2:
        st.subheader("7 · MOVE Index (Bond Vol)")
        move_data = mkt.get("^MOVE") or {}
        move_v = move_data.get("value")
        move_chg = move_data.get("change_pct")
        if move_v is not None:
            move_c2 = "#f87171" if move_v > 130 else "#fbbf24" if move_v > 100 else "#34d399"
            move_chg_str = f"{move_chg:+.2f}%" if move_chg is not None else "N/A"
            st.markdown(
                f'<div style="background:#161b27;border-radius:10px;padding:20px 24px;border:1px solid {move_c2};margin-bottom:12px">'
                f'<div style="color:#94a3b8;font-size:12px;text-transform:uppercase">MOVE Index — Bond Market Volatility</div>'
                f'<div style="color:{move_c2};font-size:42px;font-weight:700;margin:8px 0">{move_v:.1f}</div>'
                f'<div style="color:#94a3b8;font-size:13px">Change: {move_chg_str} · '
                f'{"🔴 Elevated — bond vol suppressing equity recovery" if move_v > 130 else "🟡 Moderately elevated — watch oil/CPI" if move_v > 100 else "🟢 Normal bond vol — supportive"}</div>'
                f'<div style="color:#94a3b8;font-size:11px;margin-top:8px">Normal range: 60–100. Above 130 = significant headwind for equities.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("MOVE Index data unavailable.")

    with st.expander("📖 Sentiment Framework Signal Guide (FIN404043)"):
        st.markdown("""
| # | Indicator | Bearish / Fear | Neutral | Bullish / Greed |
|---|---|---|---|---|
| **1** | **VIX Term Structure** | Backwardation (near > long) | Normal contango | Deep contango |
| **2** | **Put/Call Skew (SKEW)** | > 145 (expensive downside) | 115–145 | < 115 |
| **3** | **Fear & Greed** | < 25 (extreme fear) | 25–75 | > 75 (extreme greed) |
| **4** | **GS Panic Proxy** | > 9.0 (institutional panic) | 4.0–7.0 | < 4.0 (complacency) |
| **5** | **AAII Bearish %** | > 45% (contrarian bullish) | 25–45% | < 25% |
| **6** | **VRP (IV − RV)** | > 25pt (extreme fear premium) | 0–10pt normal | < 0 (complacency) |
| **7** | **MOVE Index** | > 130 (bond vol headwind) | 80–130 | < 80 (low bond vol) |
| **8** | **DSPX / KCJ** | High DSPX + Low KCJ = chaos | Mixed | Low DSPX + High KCJ |

**GS Panic Proxy methodology:**
Composite of VIX, VVIX, SKEW, and PCR — each converted to a percentile rank, averaged,
then scaled to 0–10. Above 9 = institutional panic.

**VRP interpretation:**
A large gap between VIX and realized volatility means the market is paying a major premium for protection.
VRP < 0 means realized moves are already exceeding what was priced.

**Sources:** VIX/VVIX/SKEW/MOVE via Yahoo Finance · AAII survey · CNN Fear & Greed ·
CBOE DSPX/KCJ via Yahoo Finance · VRP computed from SPY OHLCV
        """)


AI_MACRO_SNAPSHOT_FILENAME = "dashboard_snapshot.json"
AI_MACRO_ANALYSIS_DIRNAME = "ai_macro_analysis"
AI_MACRO_ANALYSIS_PROMPT_FILENAME = "macro_ai_codex_prompt.md"
AI_MACRO_ANALYSIS_SCHEMA_FILENAME = "macro_ai_codex_schema.json"
AI_MACRO_ANALYSIS_MODEL = "gpt-5.4"

AI_MACRO_REFERENCES = {
    "macro_regime": [
        "Hamilton (1989), Econometrica — Markov-switching recession framework.",
        "Dalio (2012), Bridgewater — All Weather growth/inflation quadrant framing.",
        "Stock & Watson (2003), JEL — asset prices as macro regime signals.",
    ],
    "liquidity": [
        "Brunnermeier & Pedersen (2009), RFS — market liquidity and funding liquidity.",
        "Bernanke & Gertler (1995), JEP — credit channel of monetary policy.",
        "Adrian & Shin (2010), JFI — leverage, dealer balance sheets, and liquidity.",
        "Amihud (2002), JFM — illiquidity and returns.",
    ],
    "options": [
        "Gârleanu, Pedersen & Poteshman (2009), RFS — demand-based option pricing.",
        "Bollen & Whaley (2004), Journal of Finance — net buying pressure and IV shape.",
        "Derman & Kani (1994), RISK — implied volatility smile intuition.",
        "Carr & Wu (2010), RFS — variance risk premium context.",
    ],
    "institutional": [
        "Brunnermeier & Nagel (2004), Journal of Finance — hedge funds and crowded positioning.",
        "Ben-David, Franzoni & Moussawi (2012), RFS — hedge fund trading under stress.",
        "Jylhä, Rinne & Suominen (2014), Review of Finance — hedge funds and immediacy demand.",
        "Frazzini & Lamont (2008), JFE — mutual fund flows and future returns.",
    ],
    "risk": [
        "Shiller (1981), AER — prices, valuation, and excess movement.",
        "Campbell & Shiller (1988), Journal of Finance — valuation and expected returns.",
        "López de Prado (2018) — regime detection and uncertainty framing.",
        "Greenwood & Hanson (2013), RFS — issuer quality and credit-cycle risk.",
    ],
}


def _ai_snapshot_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), AI_MACRO_SNAPSHOT_FILENAME)


def _ai_analysis_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), AI_MACRO_ANALYSIS_DIRNAME)


def _ai_analysis_prompt_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), AI_MACRO_ANALYSIS_PROMPT_FILENAME)


def _ai_analysis_schema_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), AI_MACRO_ANALYSIS_SCHEMA_FILENAME)


def _ensure_ai_analysis_dir():
    path = _ai_analysis_dir()
    os.makedirs(path, exist_ok=True)
    return path


def _safe_timestamp(value=None):
    if value:
        try:
            value = str(value)
            value = value.replace(":", "").replace("-", "").replace(".", "")
            value = value.replace("T", "_").replace("Z", "Z")
            return re.sub(r"[^0-9A-Za-z_]", "", value)
        except Exception:
            pass
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%SZ")


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, pd.DataFrame):
        return _json_safe(value.to_dict(orient="records"))
    if isinstance(value, pd.Series):
        return _json_safe(value.tolist())
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime.datetime, datetime.date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _payload_count(payload):
    if payload is None:
        return 0
    if isinstance(payload, dict):
        return len(payload)
    if isinstance(payload, list):
        return len(payload)
    return 1


def _is_missing_value(value):
    return value is None or value == "" or value == {} or value == []


def _format_ai_value(value, unit=None):
    if _is_missing_value(value):
        return None
    if isinstance(value, (int, float)):
        if unit:
            return _fmt(value, unit)
        if abs(float(value)) >= 1000:
            return f"{float(value):,.0f}"
        return f"{float(value):,.2f}"
    return str(value)


def _chain_key_strike(chain_data, key_label):
    for row in chain_data.get("key_strikes", []) or []:
        if row.get("label") == key_label:
            return row.get("strike")
    return None


def _classify_gex_regime(total_gex):
    if total_gex is None:
        return None, "#94a3b8"
    try:
        total_gex = float(total_gex)
    except Exception:
        return None, "#94a3b8"
    if abs(total_gex) < 1e-9:
        return "Neutral / balanced", "#94a3b8"
    if total_gex < 0:
        return "Negative (amplifying)", "#f87171"
    return "Positive (dampening)", "#34d399"


def _has_usable_options_chain(chain_data):
    chain_data = chain_data or {}
    signals = [
        chain_data.get("calls"),
        chain_data.get("puts"),
        chain_data.get("oi_profile"),
        chain_data.get("gex"),
        chain_data.get("calls_smile"),
        chain_data.get("puts_smile"),
    ]
    return any(bool(v) for v in signals)


def _effective_total_gex(chain_data):
    chain_data = chain_data or {}
    if not _has_usable_options_chain(chain_data):
        return None
    total_gex = chain_data.get("total_gex")
    try:
        return float(total_gex) if total_gex is not None else None
    except Exception:
        return None


def _compute_ai_risk_outlook(fred, mkt, chain_data, liquidity, fear_greed, cta_model):
    vix = (mkt.get("^VIX") or {}).get("value")
    move = (mkt.get("^MOVE") or {}).get("value")
    total_gex = _effective_total_gex(chain_data)
    rec_prob = _get_val(fred, "RECPROUSM156N")
    fg_value = (fear_greed or {}).get("value")
    liq_score = (liquidity or {}).get("score")
    cta_score = (cta_model or {}).get("equity_score")

    evidence_points = [
        v for v in [vix, move, total_gex, rec_prob, fg_value, liq_score, cta_score]
        if v is not None
    ]
    if len(evidence_points) < 3:
        return {
            "volatility_regime": None,
            "directional_bias": None,
            "primary_risk": "Insufficient data for a tactical read",
            "key_levels": None,
            "what_changes_view": "Wait for more live data before treating this section as actionable.",
            "time_horizon": None,
        }

    if (
        (vix is not None and vix > 30)
        or (liq_score is not None and liq_score > 1.5)
        or (move is not None and move > 130)
    ):
        vol_regime = "Crisis"
    elif (
        (vix is not None and vix > 20)
        or (liq_score is not None and liq_score > 0.5)
        or (total_gex is not None and total_gex < 0)
    ):
        vol_regime = "Elevated"
    elif (vix is not None and vix > 16) or (fg_value is not None and fg_value < 40):
        vol_regime = "Transitional"
    else:
        vol_regime = "Low"

    if (
        vol_regime == "Crisis"
        or (rec_prob is not None and rec_prob > 50)
        or (total_gex is not None and total_gex < 0 and fg_value is not None and fg_value < 25)
    ):
        directional_bias = "Tail-Risk Alert"
    elif (
        (liq_score is not None and liq_score > 1.5)
        or (total_gex is not None and total_gex < 0)
        or (fg_value is not None and fg_value < 30)
    ):
        directional_bias = "Bearish"
    elif (
        (cta_score is not None and cta_score > 0.1)
        and (fg_value is None or fg_value >= 40)
        and (vix is None or vix < 20)
    ):
        directional_bias = "Bullish"
    else:
        directional_bias = "Neutral"

    if liq_score is not None and liq_score > 1.5:
        primary_risk = "Funding and market-liquidity deterioration"
    elif total_gex is not None and total_gex < 0:
        primary_risk = "Negative gamma amplification near crowded strikes"
    elif rec_prob is not None and rec_prob > 35:
        primary_risk = "Growth slowdown / recession transition risk"
    else:
        primary_risk = "Signal conflict across macro and positioning inputs"

    levels = []
    spot = chain_data.get("spot")
    if spot is not None:
        levels.append(f"Spot {spot:.2f}")
    if chain_data.get("max_pain") is not None:
        levels.append(f"Max Pain {chain_data['max_pain']:.0f}")
    neg_gex = _chain_key_strike(chain_data, "negative_gex")
    pos_gex = _chain_key_strike(chain_data, "positive_gex")
    if neg_gex is not None:
        levels.append(f"-GEX {neg_gex:.0f}")
    if pos_gex is not None:
        levels.append(f"+GEX {pos_gex:.0f}")
    ted = _get_val(fred, "TEDRATE")
    if ted is not None:
        levels.append(f"TED {ted:.2f}%")

    if directional_bias in {"Bearish", "Tail-Risk Alert"}:
        what_changes = "A move back to positive GEX, lower VIX, and easing liquidity stress would soften the bearish read."
    elif directional_bias == "Bullish":
        what_changes = "A flip to negative GEX, widening credit spreads, or a rise in recession probability would invalidate the constructive read."
    else:
        what_changes = "The view changes if either liquidity stress or dealer gamma becomes one-directional rather than mixed."

    time_horizon = "Near-term (1–5 days)" if total_gex is not None and total_gex < 0 else "Medium-term (2–6 weeks)"

    return {
        "volatility_regime": vol_regime,
        "directional_bias": directional_bias,
        "primary_risk": primary_risk,
        "key_levels": " · ".join(levels) if levels else None,
        "what_changes_view": what_changes,
        "time_horizon": time_horizon,
    }


def export_snapshot_to_json():
    snapshot_path = _ai_snapshot_path()

    fred = fetch_fred()
    treasury = fetch_treasury()
    mkt = fetch_market()
    premarket_data = fetch_premarket_snapshot()
    opts = fetch_options_indicators()
    skew_idx = fetch_skew_index()
    vix_term = fetch_vix_term_structure()
    chain_data = fetch_options_chain_data("SPY")
    pcr_hist = fetch_pcr_history()
    fg = fetch_fear_greed()
    bls = fetch_bls()
    naaim = fetch_naaim()
    cape = fetch_shiller_cape()
    aaii = fetch_aaii()
    news = fetch_news()
    worldmonitor_news = fetch_worldmonitor_news(per_category=5)
    sofr_data = fetch_sofr_spread()
    amihud_data = fetch_amihud_illiquidity("SPY", lookback=30)
    cot_data = fetch_cot_data()
    ici_data = fetch_ici_fund_flows()
    inst13f = fetch_13f_aggregate(top_n=10)
    mmf_history = fetch_mmf_assets_history(fred)
    vrp_data = fetch_vrp_and_realized_vol()
    cta_model = fetch_cta_momentum_model()
    sg_cta = fetch_sg_cta_index_performance()

    panic_data = compute_gs_panic_proxy(mkt, opts, skew_idx, pcr_hist)
    regime_state = compute_regime_state(fred, lookback_days=60)
    quality_rotation = compute_quality_rotation(mkt)
    liquidity = compute_composite_liquidity_score(fred, mkt)
    institutional_participation = compute_institutional_participation_score(
        cot_data, ici_data, mmf_history, fred
    )
    regime_label, regime_color = _regime(fred, mkt)
    risk_outlook = _compute_ai_risk_outlook(
        fred, mkt, chain_data, liquidity, fg, cta_model
    )

    data = {
        "fred": fred,
        "treasury": treasury,
        "market": mkt,
        "premarket_snapshot": premarket_data,
        "options_indicators": opts,
        "skew_index": skew_idx,
        "vix_term_structure": vix_term,
        "options_chain_spy": chain_data,
        "pcr_history": pcr_hist,
        "fear_greed": fg,
        "bls": bls,
        "naaim": naaim,
        "cape": cape,
        "aaii": aaii,
        "news": news,
        "worldmonitor_news": worldmonitor_news,
        "sofr": sofr_data,
        "amihud": amihud_data,
        "cot_data": cot_data,
        "ici_fund_flows": ici_data,
        "inst_13f": inst13f,
        "mmf_history": mmf_history,
        "vrp_data": vrp_data,
        "cta_momentum_model": cta_model,
        "sg_cta_index": sg_cta,
    }
    feed_status = {
        key: {"loaded": bool(value), "count": _payload_count(value)}
        for key, value in data.items()
    }
    snapshot = {
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source_file": os.path.abspath(__file__),
        "snapshot_file": snapshot_path,
        "data": data,
        "derived": {
            "panic_data": panic_data,
            "regime_state": regime_state,
            "quality_rotation": quality_rotation,
            "liquidity": liquidity,
            "institutional_participation": institutional_participation,
            "macro_regime": {"label": regime_label, "color": regime_color},
            "risk_outlook": risk_outlook,
        },
        "meta": {
            "feed_status": feed_status,
            "null_feeds": [key for key, status in feed_status.items() if not status["loaded"]],
        },
    }

    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(_json_safe(snapshot), f, ensure_ascii=False, indent=2)

    print(f"Exported dashboard snapshot to {snapshot_path}")
    print(f"Loaded feeds: {len(data) - len(snapshot['meta']['null_feeds'])}/{len(data)}")
    if snapshot["meta"]["null_feeds"]:
        print("Null feeds:", ", ".join(snapshot["meta"]["null_feeds"]))
    return snapshot


def _read_dashboard_snapshot():
    snapshot_path = _ai_snapshot_path()
    if not os.path.exists(snapshot_path):
        return None
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _latest_ai_analysis_path():
    analysis_dir = _ai_analysis_dir()
    if not os.path.isdir(analysis_dir):
        return None
    candidates = [
        os.path.join(analysis_dir, name)
        for name in os.listdir(analysis_dir)
        if name.startswith("ai_macro_analysis_") and name.endswith(".json")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def _read_latest_ai_analysis():
    path = _latest_ai_analysis_path()
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        record["_path"] = path
        return record
    except Exception:
        return None


def _compose_generated_ai_report(record, snapshot=None):
    record = record or {}
    analysis = record.get("analysis", {}) or {}
    lines = [
        analysis.get("headline") or "AI Macro Analysis",
        f"Generated At: {record.get('generated_at', 'N/A')}",
        f"Model: {record.get('model', AI_MACRO_ANALYSIS_MODEL)}",
    ]
    if snapshot:
        lines.append(f"Snapshot Exported At: {snapshot.get('exported_at', 'N/A')}")
    elif record.get("snapshot_exported_at"):
        lines.append(f"Snapshot Exported At: {record.get('snapshot_exported_at')}")
    lines.append("")
    if analysis.get("plain_english_summary"):
        lines.append("Plain-English Summary")
        lines.append(analysis["plain_english_summary"].strip())
        lines.append("")
    if analysis.get("analyst_detail_markdown"):
        lines.append("Detailed Analyst View")
        lines.append(analysis["analyst_detail_markdown"].strip())
        lines.append("")
    watch_items = analysis.get("key_watch_items") or []
    if watch_items:
        lines.append("Key Watch Items")
        lines.extend([f"- {item}" for item in watch_items])
        lines.append("")
    missing_data = analysis.get("missing_data") or []
    if missing_data:
        lines.append("Missing or Weak Inputs")
        lines.extend([f"- {item}" for item in missing_data])
        lines.append("")
    if analysis.get("data_quality_markdown"):
        lines.append("Data Quality Notes")
        lines.append(analysis["data_quality_markdown"].strip())
        lines.append("")
    confidence_label = analysis.get("confidence_label")
    confidence_reason = analysis.get("confidence_reason")
    if confidence_label or confidence_reason:
        lines.append("Confidence")
        if confidence_label:
            lines.append(f"- Level: {confidence_label}")
        if confidence_reason:
            lines.append(f"- Reason: {confidence_reason}")
        lines.append("")
    return "\n".join(lines).strip()


def _headline_bundle(items, limit=8):
    rows = []
    for item in (items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "title": item.get("title"),
                "source": item.get("source") or item.get("publisher"),
                "published": item.get("published") or item.get("date") or item.get("published_at"),
            }
        )
    return rows


def _build_ai_analysis_bundle(snapshot):
    snapshot = snapshot or {}
    data = snapshot.get("data", {}) or {}
    derived = snapshot.get("derived", {}) or {}
    sections = _build_ai_analysis_sections(snapshot)
    worldmonitor = data.get("worldmonitor_news", {}) or {}
    bundle = {
        "exported_at": snapshot.get("exported_at"),
        "null_feeds": ((snapshot.get("meta", {}) or {}).get("null_feeds") or []),
        "feed_status": (snapshot.get("meta", {}) or {}).get("feed_status") or {},
        "derived": {
            "panic_data": derived.get("panic_data"),
            "regime_state": derived.get("regime_state"),
            "quality_rotation": derived.get("quality_rotation"),
            "liquidity": derived.get("liquidity"),
            "institutional_participation": derived.get("institutional_participation"),
            "macro_regime": derived.get("macro_regime"),
            "risk_outlook": derived.get("risk_outlook"),
        },
        "section_cards": {
            section["title"]: [
                {
                    "label": card.get("label"),
                    "value": card.get("value"),
                    "subtext": card.get("subtext"),
                }
                for card in section.get("cards", [])
            ]
            for section in sections
        },
        "news_headlines": _headline_bundle(data.get("news"), limit=10),
        "worldmonitor_headlines": {
            key: _headline_bundle(value, limit=4)
            for key, value in worldmonitor.items()
            if value
        },
    }
    return _json_safe(bundle)


def _compose_codex_macro_prompt(snapshot_path, bundle_path):
    base_prompt = _read_text_file(_ai_analysis_prompt_path()) or ""
    return (
        f"{base_prompt.strip()}\n\n"
        f"Primary analysis bundle path: {bundle_path}\n"
        f"Raw snapshot path: {snapshot_path}\n"
        f"Support workflow reference: /Users/tazo/.codex/skills/financial-analyst/SKILL.md\n"
        f"Macro framework reference: /Users/tazo/Documents/Playground/macroagent.md\n\n"
        "Execution rules:\n"
        "- Read the compact analysis bundle first.\n"
        "- Use the raw snapshot only if a detail is genuinely needed and present there.\n"
        "- Use only information that is present in those files.\n"
        "- Validate data completeness before interpreting anything.\n"
        "- If a feed is null, stale, conflicting, or obviously unusable, say so explicitly.\n"
        "- Do not cite or mention academic papers, economists, journals, or institutional sources by name.\n"
        "- Do not invent statistics, probabilities, backtests, or historical hit rates.\n"
        "- Keep the first part understandable for non-finance readers.\n"
        "- Keep the second part useful for a professional macro reader.\n"
        "- Return JSON only, matching the provided schema.\n"
    )


def _codex_cli_path():
    cli = shutil.which("codex")
    if cli:
        return cli
    app_cli = "/Applications/Codex.app/Contents/Resources/codex"
    if os.path.exists(app_cli):
        return app_cli
    return None


def _run_codex_macro_analysis_subprocess(snapshot, snapshot_path):
    _ensure_ai_analysis_dir()
    timestamp = _safe_timestamp()
    raw_output_path = os.path.join(_ai_analysis_dir(), f"ai_macro_cli_raw_{timestamp}.json")
    bundle_path = os.path.join(_ai_analysis_dir(), f"ai_macro_bundle_{timestamp}.json")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(_build_ai_analysis_bundle(snapshot), f, ensure_ascii=False, indent=2)
    prompt_text = _compose_codex_macro_prompt(snapshot_path, bundle_path)
    codex_cli = _codex_cli_path()
    if not codex_cli:
        raise FileNotFoundError(
            "Codex CLI executable was not found. Expected either `codex` on PATH or "
            "`/Applications/Codex.app/Contents/Resources/codex`."
        )
    proc = subprocess.run(
        [
            codex_cli,
            "exec",
            "-m",
            AI_MACRO_ANALYSIS_MODEL,
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-C",
            os.path.dirname(os.path.abspath(__file__)),
            "--output-schema",
            _ai_analysis_schema_path(),
            "-o",
            raw_output_path,
            "-",
        ],
        input=prompt_text,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True,
        timeout=600,
    )
    raw_output = _read_text_file(raw_output_path)
    parsed = None
    if raw_output:
        try:
            parsed = json.loads(raw_output)
        except Exception:
            parsed = None
    return {
        "proc": proc,
        "bundle_path": bundle_path,
        "raw_output_path": raw_output_path,
        "raw_output": raw_output,
        "parsed": parsed,
    }


def _save_ai_analysis_record(snapshot, analysis_payload, cli_result):
    analysis_dir = _ensure_ai_analysis_dir()
    generated_at = datetime.datetime.utcnow().isoformat() + "Z"
    stamp = _safe_timestamp(generated_at)
    json_path = os.path.join(analysis_dir, f"ai_macro_analysis_{stamp}.json")
    md_path = os.path.join(analysis_dir, f"ai_macro_analysis_{stamp}.md")
    record = {
        "generated_at": generated_at,
        "model": AI_MACRO_ANALYSIS_MODEL,
        "snapshot_path": _ai_snapshot_path(),
        "snapshot_exported_at": (snapshot or {}).get("exported_at"),
        "prompt_path": _ai_analysis_prompt_path(),
        "schema_path": _ai_analysis_schema_path(),
        "analysis": analysis_payload,
        "bundle_path": cli_result.get("bundle_path"),
        "raw_output_path": cli_result.get("raw_output_path"),
        "cli_stdout": (cli_result.get("proc").stdout if cli_result.get("proc") else ""),
        "cli_stderr": (cli_result.get("proc").stderr if cli_result.get("proc") else ""),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_compose_generated_ai_report(record, snapshot))
    record["_path"] = json_path
    record["_markdown_path"] = md_path
    return record


def _ai_card(label, value, subtext="", color="#e2e8f0", border_color="#1e2d3d"):
    return {
        "label": label,
        "value": value,
        "subtext": subtext,
        "color": color,
        "border_color": border_color,
    }


def _render_ai_cards(cards, columns=3):
    cols = st.columns(columns)
    for idx, card in enumerate(cards):
        missing = _is_missing_value(card.get("value"))
        color = "#fbbf24" if missing else card.get("color", "#e2e8f0")
        border_color = "#fbbf24" if missing else card.get("border_color", "#1e2d3d")
        display_value = "N/A" if missing else str(card.get("value"))
        with cols[idx % columns]:
            st.markdown(
                f'<div style="background:#161b27;border:1px solid {border_color};border-radius:10px;padding:14px 16px;margin-bottom:10px;">'
                f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">{card.get("label","")}</div>'
                f'<div style="color:{color};font-size:24px;font-weight:700;margin-top:8px;">{display_value}</div>'
                f'<div style="color:#94a3b8;font-size:12px;margin-top:8px;min-height:32px;">{card.get("subtext","")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_generated_ai_analysis(record, snapshot=None):
    if not record:
        return
    analysis = record.get("analysis", {}) or {}
    confidence_label = analysis.get("confidence_label") or "Unknown"
    confidence_reason = analysis.get("confidence_reason") or "No confidence note returned."
    st.markdown(
        f'<div style="background:#161b27;border:1px solid #1e2d3d;border-radius:10px;padding:14px 18px;margin-bottom:14px;">'
        f'<div style="display:flex;flex-wrap:wrap;gap:18px;align-items:flex-end;">'
        f'<div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Generated At</div>'
        f'<div style="color:#e2e8f0;font-size:20px;font-weight:700;margin-top:6px;">{record.get("generated_at", "N/A")}</div></div>'
        f'<div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Model</div>'
        f'<div style="color:#e2e8f0;font-size:20px;font-weight:700;margin-top:6px;">{record.get("model", AI_MACRO_ANALYSIS_MODEL)}</div></div>'
        f'<div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Confidence</div>'
        f'<div style="color:#e2e8f0;font-size:20px;font-weight:700;margin-top:6px;">{confidence_label}</div></div>'
        f'</div>'
        f'<div style="color:#94a3b8;font-size:12px;margin-top:10px;">{confidence_reason}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if analysis.get("headline"):
        st.markdown(f"### {analysis['headline']}")
    if analysis.get("plain_english_summary"):
        st.info(analysis["plain_english_summary"])
    if analysis.get("analyst_detail_markdown"):
        st.markdown(analysis["analyst_detail_markdown"])
    watch_items = analysis.get("key_watch_items") or []
    if watch_items:
        st.markdown("**Key Watch Items**")
        for item in watch_items:
            st.markdown(f"- {item}")
    missing_data = analysis.get("missing_data") or []
    if missing_data or analysis.get("data_quality_markdown"):
        with st.expander("Data Quality & Missing Inputs", expanded=False):
            if missing_data:
                for item in missing_data:
                    st.markdown(f"- {item}")
            if analysis.get("data_quality_markdown"):
                st.markdown(analysis["data_quality_markdown"])
    with st.expander("Copyable Generated Report", expanded=False):
        st.text_area(
            "Generated report",
            value=_compose_generated_ai_report(record, snapshot),
            height=460,
            key="ai_macro_generated_report_text",
        )


def _render_ai_references(section_key):
    refs = AI_MACRO_REFERENCES.get(section_key, [])
    if not refs:
        return
    ref_html = "".join(
        f'<div style="color:#64748b;font-size:11px;line-height:1.45;margin-top:4px;">• {ref}</div>'
        for ref in refs
    )
    st.markdown(
        f'<div style="background:#161b27;border:1px solid #1e2d3d;border-radius:10px;padding:12px 14px;margin-top:10px;">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">Academic References</div>'
        f'{ref_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _build_ai_analysis_sections(snapshot):
    data = snapshot.get("data", {}) or {}
    derived = snapshot.get("derived", {}) or {}

    fred = data.get("fred", {}) or {}
    mkt = data.get("market", {}) or {}
    opts = data.get("options_indicators", {}) or {}
    chain = data.get("options_chain_spy", {}) or {}
    cot = data.get("cot_data", {}) or {}
    ici = data.get("ici_fund_flows", {}) or {}
    cta = data.get("cta_momentum_model", {}) or {}
    inst13f = data.get("inst_13f", {}) or {}
    fg = data.get("fear_greed", {}) or {}
    aaii = data.get("aaii", {}) or {}
    vrp = data.get("vrp_data", {}) or {}
    sg_cta = data.get("sg_cta_index", {}) or {}
    liquidity = derived.get("liquidity", {}) or {}
    institutional = derived.get("institutional_participation", {}) or {}
    risk = derived.get("risk_outlook", {}) or {}
    macro_regime = derived.get("macro_regime", {}) or {}

    macro_cards = [
        _ai_card("Macro Regime", macro_regime.get("label"), "Bridgewater-style growth/inflation read", color=macro_regime.get("color", "#e2e8f0"), border_color=macro_regime.get("color", "#1e2d3d")),
        _ai_card("GDPNow", _format_ai_value(_get_val(fred, "GDPNOW") or _get_val(fred, "A191RL1Q225SBEA"), "%"), "Growth impulse proxy"),
        _ai_card("CPI YoY", _format_ai_value(_get_val(fred, "CPIAUCSL"), "%"), "Inflation regime anchor"),
        _ai_card("Fed Funds", _format_ai_value(_get_val(fred, "DFF"), "%"), "Policy stance"),
        _ai_card("10Y-3M Spread", _format_ai_value(_get_val(fred, "T10Y3M"), "%"), "Curve shape / recession lead indicator"),
        _ai_card("Recession Probability", _format_ai_value(_get_val(fred, "RECPROUSM156N"), "%"), "Hamilton-style transition risk"),
    ]

    liquidity_cards = [
        _ai_card("Liquidity Score", _format_ai_value(liquidity.get("score")), liquidity.get("label", "Composite financial-conditions read"), color=liquidity.get("color", "#e2e8f0"), border_color=liquidity.get("color", "#1e2d3d")),
        _ai_card("TED Spread", _format_ai_value(_get_val(fred, "TEDRATE"), "%"), "Interbank funding stress"),
        _ai_card("NFCI", _format_ai_value(_get_val(fred, "NFCI"), "idx"), "Chicago financial conditions index"),
        _ai_card("STLFSI2", _format_ai_value(_get_val(fred, "STLFSI2"), "idx"), "St. Louis stress index"),
        _ai_card("HY Spread", _format_ai_value(_get_val(fred, "BAMLH0A0HYM2"), "bp"), "Credit-risk premium"),
        _ai_card("MOVE Index", _format_ai_value((mkt.get("^MOVE") or {}).get("value")), "Bond-volatility / liquidity proxy"),
        _ai_card("SOFR vs Fed Funds", _format_ai_value((data.get("sofr") or {}).get("spread_to_fed_funds"), "%"), "Repo-market stress spread"),
        _ai_card("Amihud Illiquidity", _format_ai_value((data.get("amihud") or {}).get("value")), "Higher = worse market depth"),
    ]

    neg_gex = _chain_key_strike(chain, "negative_gex")
    pos_gex = _chain_key_strike(chain, "positive_gex")
    total_gex = _effective_total_gex(chain)
    gex_regime, gex_regime_color = _classify_gex_regime(total_gex)
    options_cards = [
        _ai_card("GEX Regime", gex_regime, "Dealer hedging transmission regime", color=gex_regime_color, border_color=gex_regime_color),
        _ai_card("Net GEX", _format_ai_value(total_gex / 1e6 if total_gex is not None else None), "Millions of gamma exposure across strikes"),
        _ai_card("Spot", _format_ai_value(chain.get("spot") if _has_usable_options_chain(chain) else None), "Current SPY spot used in chain analytics"),
        _ai_card("Max Pain", _format_ai_value(chain.get("max_pain") if _has_usable_options_chain(chain) else None), "Potential expiry pinning strike"),
        _ai_card("25Δ Skew", _format_ai_value(chain.get("skew_25d") if _has_usable_options_chain(chain) else None), "Put premium over calls (vol pts)"),
        _ai_card("Negative GEX Strike", _format_ai_value(neg_gex), "Key acceleration zone"),
        _ai_card("Positive GEX Strike", _format_ai_value(pos_gex), "Potential pinning / damping zone"),
        _ai_card("PCR", _format_ai_value((opts or {}).get("pcr")), "Aggregate put/call positioning"),
    ]

    cot_sp = (cot.get("SP500_Emini") or {}).get("net_nc") if cot else None
    cot_tsy = (cot.get("Treasury_10Y") or {}).get("net_lev") if cot else None
    inst_cards = [
        _ai_card("Participation Score", _format_ai_value(institutional.get("score")), institutional.get("label", "Institutional participation composite"), color=institutional.get("color", "#e2e8f0"), border_color=institutional.get("color", "#1e2d3d")),
        _ai_card("COT SPX Net Non-Comm", _format_ai_value(cot_sp), "Large-spec / hedge-fund S&P positioning"),
        _ai_card("COT 10Y Leveraged", _format_ai_value(cot_tsy), "Leveraged-fund Treasury positioning"),
        _ai_card("ICI Equity Flow", _format_ai_value((ici or {}).get("latest_equity"), "B"), "Latest weekly equity-fund flow"),
        _ai_card("ICI Bond Flow", _format_ai_value((ici or {}).get("latest_bond"), "B"), "Latest weekly bond-fund flow"),
        _ai_card("Retail MMF Assets", _format_ai_value(_get_val(fred, "WRMFNS"), "B"), "Current retail cash parked in MMFs"),
        _ai_card("Institutional MMF Assets (disc.)", _format_ai_value((fred.get("WIMFNS") or fred.get("WIMFSL") or {}).get("last_value"), "B"), "Last known institutional weekly MMF series; discontinued in 2021"),
        _ai_card("CTA Equity Score", _format_ai_value((cta or {}).get("equity_score")), (cta or {}).get("equity_label", "Systematic trend score"), color=(cta or {}).get("equity_color", "#e2e8f0"), border_color=(cta or {}).get("equity_color", "#1e2d3d")),
        _ai_card("SG CTA YTD", _format_ai_value((sg_cta or {}).get("ytd_return"), "%"), "Public CTA index performance proxy"),
        _ai_card("13F Source", (inst13f or {}).get("source"), "Institutional holder dataset in use"),
    ]

    risk_cards = [
        _ai_card("Volatility Regime", risk.get("volatility_regime"), "Low / Transitional / Elevated / Crisis"),
        _ai_card("Directional Bias", risk.get("directional_bias"), "Bullish / Neutral / Bearish / Tail-Risk Alert"),
        _ai_card("Primary Risk", risk.get("primary_risk"), "Most important current risk driver"),
        _ai_card("Key Levels", risk.get("key_levels"), "Spot / max pain / gamma and stress triggers"),
        _ai_card("What Changes View", risk.get("what_changes_view"), "Specific conditions that would flip the thesis"),
        _ai_card("Time Horizon", risk.get("time_horizon"), "Primary tactical horizon"),
        _ai_card("Fear & Greed", _format_ai_value(fg.get("value")), fg.get("label", "CNN sentiment gauge") if fg else "CNN sentiment gauge"),
        _ai_card("AAII Bearish %", _format_ai_value(aaii.get("bear"), "%"), "Retail sentiment stress"),
        _ai_card("VRP", _format_ai_value((vrp or {}).get("vrp")), "VIX minus realized vol"),
    ]

    return [
        {"key": "macro_regime", "title": "🌍 Section 1: Macro Regime Classification", "cards": macro_cards},
        {"key": "liquidity", "title": "💧 Section 2: Financial Conditions & Liquidity", "cards": liquidity_cards},
        {"key": "options", "title": "📐 Section 3: Options Market Structure & Dealer Positioning", "cards": options_cards},
        {"key": "institutional", "title": "🏦 Section 4: Institutional Flow Analysis", "cards": inst_cards},
        {"key": "risk", "title": "⚠️  Section 5: Risk Outlook & Tactical Assessment", "cards": risk_cards},
    ]


def _compose_ai_full_report(snapshot):
    sections = _build_ai_analysis_sections(snapshot)
    lines = [
        f"AI Macro Analysis Report",
        f"Exported At: {snapshot.get('exported_at', 'N/A')}",
        "",
    ]
    for section in sections:
        lines.append(section["title"])
        for card in section["cards"]:
            value = "N/A" if _is_missing_value(card.get("value")) else str(card.get("value"))
            lines.append(f"- {card.get('label')}: {value}")
        note_key = f"ai_analysis_notes_{section['key']}"
        notes = st.session_state.get(note_key, "").strip()
        lines.append("Analysis Notes:")
        lines.append(notes if notes else "No notes added.")
        lines.append("Academic References:")
        lines.extend([f"- {ref}" for ref in AI_MACRO_REFERENCES.get(section["key"], [])])
        lines.append("")
    return "\n".join(lines)


def render_ai_macro_analysis():
    st.subheader("🤖 AI Macro Analysis")
    st.caption(
        "Use the latest exported snapshot and run a local Codex CLI analyst pass. The generated output starts with plain English and then goes into a professional macro read."
    )

    snapshot = st.session_state.get("ai_macro_snapshot")
    if snapshot is None:
        snapshot = _read_dashboard_snapshot()
        if snapshot:
            st.session_state["ai_macro_snapshot"] = snapshot
    analysis_record = st.session_state.get("ai_macro_generated_analysis")
    if analysis_record is None:
        analysis_record = _read_latest_ai_analysis()
        if analysis_record:
            st.session_state["ai_macro_generated_analysis"] = analysis_record

    action_c1, action_c2 = st.columns([1.2, 4.8])
    with action_c1:
        run_clicked = st.button("Run Codex Analysis", key="run_ai_macro_analysis", use_container_width=True)
    with action_c2:
        st.caption("This uses the existing `dashboard_snapshot.json`. It does not rerun export.")

    if run_clicked:
        if snapshot is None:
            st.info("Run the export first to load live data")
            return
        with st.status("Running local Codex CLI analysis…", expanded=True) as status:
            status.write("Using the latest saved snapshot without refetching data…")
            try:
                cli_result = _run_codex_macro_analysis_subprocess(snapshot, _ai_snapshot_path())
            except FileNotFoundError as exc:
                status.update(label="CLI not found", state="error", expanded=True)
                st.error(str(exc))
                return
            proc = cli_result.get("proc")
            st.session_state["ai_macro_cli_stdout"] = proc.stdout if proc else ""
            st.session_state["ai_macro_cli_stderr"] = proc.stderr if proc else ""
            if proc is None or proc.returncode != 0:
                status.update(label="CLI analysis failed", state="error", expanded=True)
                st.error("Local Codex analysis failed. Review the CLI output below.")
                if proc and proc.stderr.strip():
                    st.code(proc.stderr)
                if proc and proc.stdout.strip():
                    st.code(proc.stdout)
            elif not cli_result.get("parsed"):
                status.update(label="CLI returned unusable output", state="error", expanded=True)
                st.error("Codex returned output, but it did not match the expected analysis schema.")
                if cli_result.get("raw_output"):
                    st.code(cli_result["raw_output"])
            else:
                analysis_record = _save_ai_analysis_record(snapshot, cli_result["parsed"], cli_result)
                st.session_state["ai_macro_generated_analysis"] = analysis_record
                status.update(label="✅ Codex analysis complete", state="complete", expanded=False)

    snapshot = st.session_state.get("ai_macro_snapshot")
    analysis_record = st.session_state.get("ai_macro_generated_analysis") or _read_latest_ai_analysis()
    if analysis_record and "ai_macro_generated_analysis" not in st.session_state:
        st.session_state["ai_macro_generated_analysis"] = analysis_record
    if snapshot is None:
        st.info("Run the export first to load live data")
        return

    meta = snapshot.get("meta", {}) or {}
    feed_status = meta.get("feed_status", {}) or {}
    st.markdown(
        f'<div style="background:#161b27;border:1px solid #1e2d3d;border-radius:10px;padding:14px 18px;margin-bottom:14px;">'
        f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">Snapshot Status</div>'
        f'<div style="color:#e2e8f0;font-size:22px;font-weight:700;margin-top:8px;">{snapshot.get("exported_at", "N/A")}</div>'
        f'<div style="color:#94a3b8;font-size:12px;margin-top:8px;">Loaded feeds: {len([k for k, v in feed_status.items() if v.get("loaded")])}/{len(feed_status) if feed_status else 0}</div>'
        f'<div style="color:#94a3b8;font-size:12px;margin-top:6px;">Latest saved analysis: {(analysis_record or {}).get("generated_at", "Not run yet")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if analysis_record:
        _render_generated_ai_analysis(analysis_record, snapshot)
    else:
        st.info("No generated macro analysis found yet. Click `Run Codex Analysis` to create one from the latest snapshot.")

    with st.expander("📊 Live Data Snapshot", expanded=False):
        st.json(snapshot)

    with st.expander("Supporting Live Inputs Used By The Analyst", expanded=False):
        sections = _build_ai_analysis_sections(snapshot)
        for section in sections:
            st.markdown(f"#### {section['title']}")
            _render_ai_cards(section["cards"], columns=3)

    cli_stdout = st.session_state.get("ai_macro_cli_stdout", "")
    cli_stderr = st.session_state.get("ai_macro_cli_stderr", "")
    if cli_stdout or cli_stderr:
        with st.expander("CLI Output", expanded=False):
            if cli_stdout:
                st.code(cli_stdout)
            if cli_stderr:
                st.code(cli_stderr)


def _clear_cached_functions(*funcs):
    for func in funcs:
        try:
            func.clear()
        except Exception:
            continue


def _render_section_refresh(section_key, clear_funcs):
    refresh_col, info_col = st.columns([1.1, 5.9])
    with refresh_col:
        if st.button("↻ Refresh section", key=f"refresh_{section_key}", use_container_width=True):
            _clear_cached_functions(*clear_funcs)
            st.rerun()
    with info_col:
        st.caption("Reload only the data used by this section.")


def build_sidebar():
    with st.sidebar:
        st.markdown("## 📊 Macro Dashboard")
        _ensure_ui_mode_state()
        current_mode = st.session_state.get("ui_mode", "professional")
        ui_mode_options = {
            "🔤 Beginner Mode": "beginner",
            "🎓 Professional Mode": "professional",
        }
        reverse_ui_mode_options = {v: k for k, v in ui_mode_options.items()}
        if "ui_mode_selector" not in st.session_state:
            st.session_state["ui_mode_selector"] = reverse_ui_mode_options.get(current_mode, "🎓 Professional Mode")
        selected_mode_label = st.radio(
            "View Mode",
            options=list(ui_mode_options.keys()),
            key="ui_mode_selector",
            horizontal=True,
            label_visibility="collapsed",
        )
        _set_ui_mode(ui_mode_options[selected_mode_label])
        st.caption("Live data from the Federal Reserve, U.S. Treasury, stock markets, and investor surveys. Refreshes automatically. Green = healthy, Yellow = watch, Red = warning.")
        st.divider()

        lookback = st.slider(
            "How many months of history to show (Jobs vs. Inflation chart)",
            min_value=6, max_value=36, value=16, step=1,
        )
        regime_lookback_days = st.slider(
            "How many days to measure trend momentum",
            min_value=20, max_value=120, value=60, step=1,
        )
        st.session_state["regime_roc_lookback_days"] = regime_lookback_days
        futures_csv = st.file_uploader(
            "Upload futures spreads CSV",
            type="csv",
            key="futures_csv",
        )

        all_sections = [
            "🏦 Macro Overview",
            "💼 Labor & Consumer",
            "💱 Markets & Sentiment",
            "Energy Futures",
            "📉 Options & Derivatives",
            "🪙 Metals",
            "🏠 Housing & Credit",
            "📊 Phillips Curve",
            "📰 News & Signals",
            "Liquidity Conditions",
            "Institutional Flows",
            "GS-Style Composites",
            "Global Macro",
            "🤖 AI Macro Analysis",
        ]
        visible_sections = st.multiselect(
            "Show / hide tabs",
            options=all_sections,
            default=all_sections,
            format_func=_display_tab_label,
        )

        st.divider()

        # API keys input panel
        with st.expander("🔐 API Keys"):
            st.caption("Enter your API keys below. Leave blank to use secrets or environment variables.")
            fred_inp   = st.text_input("FRED API Key", value=FRED_API_KEY or "", type="password")
            alpha_inp  = st.text_input("Alpha Vantage Key", value=ALPHA_VANTAGE_KEY or "", type="password")
            bls_inp    = st.text_input("BLS API Key", value=BLS_API_KEY or "", type="password")
            eia_inp    = st.text_input("EIA API Key", value=EIA_API_KEY or "", type="password")
            fmp_inp    = st.text_input("FMP API Key", value=FMP_API_KEY or "", type="password")
            cftc_inp   = st.text_input("CFTC App Token", value=CFTC_APP_TOKEN or "", type="password")
            nasdaq_inp = st.text_input("NASDAQ API Key", value=NASDAQ_API_KEY or "", type="password")
            finnhub_inp = st.text_input("Finnhub API Key (13F data)", value=FINNHUB_API_KEY or "", type="password")
            if st.button("Apply API Keys"):
                # Update session_state so get_api_key() picks up overrides
                keys_map = {
                    "FRED_API_KEY": fred_inp.strip(),
                    "ALPHA_VANTAGE_KEY": alpha_inp.strip(),
                    "BLS_API_KEY": bls_inp.strip(),
                    "EIA_API_KEY": eia_inp.strip(),
                    "FMP_API_KEY": fmp_inp.strip(),
                    "CFTC_APP_TOKEN": cftc_inp.strip(),
                    "NASDAQ_API_KEY": nasdaq_inp.strip(),
                    "FINNHUBAPIKEY": finnhub_inp.strip(),
                }
                for k, v in keys_map.items():
                    if v:
                        st.session_state[k] = v
                # Clear cached data and rerun to pick up new keys
                st.cache_data.clear()
                st.rerun()

        if st.button("🔄 Force Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")

    return lookback, regime_lookback_days, visible_sections, futures_csv


# ── MAIN APP ──────────────────────────────────────────────────────────────────
def main():
    lookback, regime_lookback_days, visible_sections, futures_csv = build_sidebar()

    with st.status("📡 Loading core dashboard data…", expanded=False) as status:
        fred = fetch_fred()
        treasury = fetch_treasury()
        mkt = fetch_market()
        fg = fetch_fear_greed()
        naaim = fetch_naaim()
        cape = fetch_shiller_cape()
        status.update(label="✅ Core dashboard ready", state="complete", expanded=False)

    futures_curve = pd.DataFrame()
    if futures_csv is not None:
        futures_curve = load_futures_spreads(futures_csv)
    else:
        for futures_path in ENERGY_FUTURES_DEFAULT_PATHS:
            if os.path.exists(futures_path):
                futures_curve = load_futures_spreads(futures_path)
                break

    render_data_diagnostics(fred, treasury, mkt, fg, naaim, cape, None, [], None)
    if has_systemic_data_failure(fred, treasury, mkt, fg, naaim, cape):
        st.error(
            "Most live feeds are currently unavailable. Check internet/DNS access first, then verify your API keys in the sidebar."
        )

    # ── REGIME LABEL ────────────────────────────────────────────────────────
    regime_label, regime_color = _regime(fred, mkt)
    energy_curve_regime = compute_regime_state(
        fred,
        lookback_days=regime_lookback_days,
        energy_curve=futures_curve,
    ).get("curve_regime")
    st.markdown(
        f'<div style="display:inline-block;background:#161b27;border:1px solid {regime_color};'
        f'color:{regime_color};padding:6px 18px;border-radius:8px;font-weight:700;'
        f'font-size:15px;margin-bottom:12px">Macro Regime: {regime_label}</div>',
        unsafe_allow_html=True,
    )
    if energy_curve_regime:
        energy_regime_color = {
            "Backwardation": "#f87171",
            "Flat": "#94a3b8",
            "Contango": "#fbbf24",
            "Deep Contango": "#f87171",
        }.get(energy_curve_regime, "#94a3b8")
        st.markdown(
            f'<div style="display:inline-block;background:#161b27;border:1px solid {energy_regime_color};'
            f'color:{energy_regime_color};padding:6px 18px;border-radius:8px;font-weight:700;'
            f'font-size:15px;margin-left:8px;margin-bottom:12px">WTI Curve: {energy_curve_regime}</div>',
            unsafe_allow_html=True,
        )

    # ── KPI ROW ─────────────────────────────────────────────────────────────
    gdp_v  = _get_val(fred, "GDPNOW") or _get_val(fred, "A191RL1Q225SBEA")
    cpi_v  = _get_val(fred, "CPIAUCSL")
    un_v   = _get_val(fred, "UNRATE")
    dff_v  = _get_val(fred, "DFF")
    rec_v  = _get_val(fred, "RECPROUSM156N")
    cape_v = cape.get("value") if cape else None
    t10_v  = (treasury.get("10Y") or {}).get("value")
    t2_v   = (treasury.get("2Y") or {}).get("value")
    spread_2_10 = round(t10_v - t2_v, 2) if t10_v and t2_v else None
    vix_v  = (mkt.get("^VIX") or {}).get("value")

    kpi_cols = st.columns(6)
    with kpi_cols[0]:
        st.metric("GDP (GDPNow)",
                  f"{gdp_v:.1f}%" if gdp_v is not None else "N/A",
                  delta=f"{gdp_v - 2:.1f}% vs 2% trend" if gdp_v is not None else None,
                  delta_color="normal")
    with kpi_cols[1]:
        st.metric("CPI Inflation",
                  f"{cpi_v:.1f}%" if cpi_v is not None else "N/A",
                  delta=f"{cpi_v - 2:.1f}% vs 2% target" if cpi_v is not None else None,
                  delta_color="inverse")
    with kpi_cols[2]:
        st.metric("Unemployment",
                  f"{un_v:.1f}%" if un_v is not None else "N/A",
                  delta=f"{un_v - 4:.1f}% vs 4% natural" if un_v is not None else None,
                  delta_color="inverse")
    with kpi_cols[3]:
        st.metric("Fed Funds Rate",
                  f"{dff_v:.2f}%" if dff_v is not None else "N/A",
                  delta=None)
    with kpi_cols[4]:
        st.metric("Recession Prob",
                  f"{rec_v:.0f}%" if rec_v is not None else "N/A",
                  delta=f"{rec_v - 20:.0f}% vs 20% alert" if rec_v is not None else None,
                  delta_color="inverse")
    with kpi_cols[5]:
        st.metric("CAPE Ratio",
                  f"{cape_v:.1f}" if cape_v is not None else "N/A",
                  delta=f"{cape_v - 25:.1f} vs 25 avg" if cape_v is not None else None,
                  delta_color="inverse")

    st.divider()

    # ── TABS ────────────────────────────────────────────────────────────────
    if "Sentiment Framework" not in visible_sections:
        visible_sections = visible_sections + ["Sentiment Framework"]

    ALL_TABS = [
        "🏦 Macro Overview",
        "💼 Labor & Consumer",
        "💱 Markets & Sentiment",
        "Energy Futures",
        "📉 Options & Derivatives",
        "🪙 Metals",
        "🏠 Housing & Credit",
        "📊 Phillips Curve",
        "📰 News & Signals",
        "Liquidity Conditions",
        "Institutional Flows",
        "GS-Style Composites",
        "Global Macro",
        "Sentiment Framework",
        "🤖 AI Macro Analysis",
    ]
    internal_tab_keys = [t for t in ALL_TABS if t in visible_sections]
    if not internal_tab_keys:
        st.info("All tabs hidden. Use the sidebar to select sections to display.")
        return

    display_tab_labels = [_display_tab_label(t) for t in internal_tab_keys]
    tabs = st.tabs(display_tab_labels)
    tab_map = {label: tab for label, tab in zip(internal_tab_keys, tabs)}

    # ── TAB 1: MACRO OVERVIEW ──────────────────────────────────────────────
    if "🏦 Macro Overview" in tab_map:
        with tab_map["🏦 Macro Overview"]:
            _render_section_refresh(
                "macro_overview",
                [fetch_fred, fetch_treasury, fetch_market, fetch_fear_greed, fetch_naaim, fetch_shiller_cape],
            )
            render_tab_summary("🏦 Macro Overview", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_macro_alerts(fred, futures_curve)

            col1, col2 = st.columns([1.1, 1])
            with col1:
                st.subheader("📈 Growth Indicators")
                growth_data = {
                    "Indicator": ["GDPNow Estimate","Official GDP Growth","Industrial Production",
                                   "Weekly Economic Index","US Leading Index"],
                    "Series ID": ["GDPNOW","A191RL1Q225SBEA","INDPRO","WEI","USSLIND"],
                    "Unit"     : ["%","%","%","idx","%"],
                }
                for name, sid, unit in zip(growth_data["Indicator"], growth_data["Series ID"], growth_data["Unit"]):
                    v = _get_val(fred, sid)
                    c = _status_color(sid, v) or "#94a3b8"
                    val_str = _fmt(v, unit)
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                        f'border-bottom:1px solid #1e2d3d">'
                        f'<span style="color:#94a3b8;font-size:13px">{name}</span>'
                        f'<span style="color:{c};font-weight:600;font-size:13px">{val_str}</span></div>',
                        unsafe_allow_html=True,
                    )

                st.subheader("🔥 Inflation")
                st.plotly_chart(
                    make_inflation_bar_chart(fred),
                    use_container_width=True,
                    key="chart_inflation_bar",
                )

            with col2:
                st.subheader("📉 Yield Curve")
                st.plotly_chart(
                    make_yield_curve_chart(treasury),
                    use_container_width=True,
                    key="chart_yield_curve",
                )
                if spread_2_10 is not None:
                    spread_color = "#34d399" if spread_2_10 > 0 else "#f87171"
                    st.markdown(
                        f'<span style="color:#94a3b8;font-size:12px">2-10Y Spread: </span>'
                        f'<span style="color:{spread_color};font-weight:700">{spread_2_10:+.2f}%</span>',
                        unsafe_allow_html=True,
                    )

            st.subheader("🧮 Recession Probability")
            rc1, rc2 = st.columns(2)
            with rc1:
                st.plotly_chart(
                    make_recession_prob_chart(fred),
                    use_container_width=True,
                    key="chart_recession_prob",
                )
            with rc2:
                ads_v = _get_val(fred, "CFNAI")
                lei_v = _get_val(fred, "USSLIND")
                wei_v = _get_val(fred, "WEI")
                for label, v, unit in [("Business Conditions (CFNAI)", ads_v, "idx"),
                                        ("US Leading Index (LEI)", lei_v, "%"),
                                        ("Weekly Economic Index",  wei_v, "idx")]:
                    c = "#94a3b8"
                    st.markdown(
                        f'<div style="padding:8px 0;border-bottom:1px solid #1e2d3d">'
                        f'<span style="color:#94a3b8;font-size:13px">{label}: </span>'
                        f'<span style="color:{c};font-weight:600">{_fmt(v,unit)}</span></div>',
                        unsafe_allow_html=True,
                    )

    # ── TAB 2: LABOR & CONSUMER ────────────────────────────────────────────
    if "💼 Labor & Consumer" in tab_map:
        with tab_map["💼 Labor & Consumer"]:
            _render_section_refresh("labor_consumer", [fetch_fred, fetch_bls])
            with st.spinner("Loading labor and consumer data…"):
                bls = fetch_bls()
            render_tab_summary("💼 Labor & Consumer", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_labor_alerts(fred)

            lc1, lc2 = st.columns(2)
            with lc1:
                st.subheader("👷 Labor Market")
                labor_items = [
                    ("UNRATE","Unemployment Rate","%"),
                    ("U6RATE","U-6 Underemployment","%"),
                    ("CIVPART","Labor Participation","%"),
                    ("JTSJOL","Job Openings (JOLTS)","k"),
                    ("CES0500000003","Avg Hourly Earnings","$"),
                    ("ICSA","Initial Jobless Claims","k"),
                ]
                # Payrolls from BLS if available
                payrolls_v = (bls.get("nonfarm_payrolls") or {}).get("value")
                if payrolls_v:
                    c = "#34d399" if payrolls_v > 0 else "#f87171"
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                        f'border-bottom:1px solid #1e2d3d">'
                        f'<span style="color:#94a3b8;font-size:13px">Nonfarm Payrolls (MoM)</span>'
                        f'<span style="color:{c};font-weight:600">{payrolls_v:+,.0f}K</span></div>',
                        unsafe_allow_html=True,
                    )
                for sid, label, unit in labor_items:
                    v = _get_val(fred, sid)
                    c = _status_color(sid, v) or "#94a3b8"
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                        f'border-bottom:1px solid #1e2d3d">'
                        f'<span style="color:#94a3b8;font-size:13px">{label}</span>'
                        f'<span style="color:{c};font-weight:600">{_fmt(v,unit)}</span></div>',
                        unsafe_allow_html=True,
                    )

            with lc2:
                st.subheader("🛒 Consumer & Spending")
                consumer_items = [
                    ("UMCSENT","University of Michigan Consumer Sentiment Index","idx"),
                    ("RSXFS","Retail Sales (ex-Auto)","$B"),
                    ("DSPIC96","Real Disposable Income","$B"),
                    ("PSAVERT","Personal Savings Rate","%"),
                    ("TOTALSL","Total Consumer Credit","$B"),
                ]
                for sid, label, unit in consumer_items:
                    v = _get_val(fred, sid)
                    c = _status_color(sid, v) or "#94a3b8"
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                        f'border-bottom:1px solid #1e2d3d">'
                        f'<span style="color:#94a3b8;font-size:13px">{label}</span>'
                        f'<span style="color:{c};font-weight:600">{_fmt(v,unit)}</span></div>',
                        unsafe_allow_html=True,
                    )
                st.subheader("💹 PCE & Retail (KPIs)")
                kc1, kc2 = st.columns(2)
                pce_v  = _get_val(fred, "PCEPILFE")
                ret_v  = _get_val(fred, "RSXFS")
                kc1.metric("Core PCE", f"{pce_v:.2f}%" if pce_v else "N/A",
                           delta=f"{pce_v-2:.2f}% vs 2% target" if pce_v else None,
                           delta_color="inverse")
                kc2.metric("Retail Sales", f"${ret_v:.1f}B" if ret_v else "N/A")

            st.divider()
            st.subheader("Household Buffer & Recession Trigger")
            e1, e2, e3, e4 = st.columns(4)
            psavert_v = _get_val(fred, "PSAVERT")
            psavert_avg = _hist_average(fred, "PSAVERT_HIST", periods=12)
            real_wage = compute_real_wage_growth(fred)
            umich_v = _get_val(fred, "UMCSENT")
            umich_delta = _hist_latest_delta(fred, "UMCSENT_HIST", periods=1)
            sahm_v = _get_val(fred, "SAHMREALTIME")
            e1.metric(
                "Personal Savings Rate",
                f"{psavert_v:.1f}%" if psavert_v is not None else "N/A",
                delta=f"{psavert_v - psavert_avg:+.1f} vs 12M avg" if psavert_v is not None and psavert_avg is not None else None,
            )
            e2.metric(
                "Real Wage Growth",
                f"{real_wage:+.2f}%" if real_wage is not None else "N/A",
                delta="Pay beating inflation" if real_wage is not None and real_wage > 0 else "Inflation beating pay" if real_wage is not None else None,
                delta_color="normal" if real_wage is not None and real_wage > 0 else "inverse",
            )
            e3.metric(
                "University of Michigan Consumer Sentiment Index",
                f"{umich_v:.1f}" if umich_v is not None else "N/A",
                delta=f"{umich_delta:+.1f} vs prior month" if umich_delta is not None else None,
            )
            e4.metric(
                "Sahm Rule",
                f"{sahm_v:.2f}" if sahm_v is not None else "N/A",
                delta="Triggered" if sahm_v is not None and sahm_v >= 0.5 else "Approaching" if sahm_v is not None and sahm_v >= 0.3 else "Below threshold" if sahm_v is not None else None,
                delta_color="inverse" if sahm_v is not None and sahm_v >= 0.5 else "normal",
            )
            le1, le2 = st.columns(2)
            with le1:
                st.plotly_chart(
                    make_fred_history_line_chart(fred, "PSAVERT_HIST", "Personal Savings Rate — 12M Sparkline", "%", "#34d399"),
                    use_container_width=True,
                    key="chart_labor_psavert_history",
                )
            with le2:
                st.plotly_chart(
                    make_sahm_rule_gauge(fred),
                    use_container_width=True,
                    key="chart_labor_sahm_gauge",
                )

    # ── TAB 3: MARKETS & SENTIMENT ─────────────────────────────────────────
    if "💱 Markets & Sentiment" in tab_map:
        with tab_map["💱 Markets & Sentiment"]:
            _render_section_refresh(
                "markets_sentiment",
                [fetch_market, fetch_premarket_snapshot, fetch_fear_greed, fetch_naaim, fetch_shiller_cape, fetch_options_indicators, fetch_aaii],
            )
            with st.spinner("Loading markets and sentiment data…"):
                premarket_data = fetch_premarket_snapshot()
                opts = fetch_options_indicators()
                aaii = fetch_aaii()
            quality_rotation = compute_quality_rotation(mkt)
            render_tab_summary("💱 Markets & Sentiment", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_markets_alerts(fred, mkt, fg, cape, opts)
            render_premarket_futures_snapshot(mkt, premarket_data)

            # Market KPIs row
            sp500  = (mkt.get("^GSPC") or {})
            nasdaq = (mkt.get("^IXIC") or {})
            dji    = (mkt.get("^DJI") or {})
            btc    = (mkt.get("BTC-USD") or {})
            dxy    = (mkt.get("DX-Y.NYB") or {})

            mk1, mk2, mk3, mk4, mk5 = st.columns(5)
            mk1.metric("S&P 500",
                       f"{sp500.get('value',0):,.0f}" if sp500.get("value") else "N/A",
                       delta=f"{sp500.get('change_pct',0):.2f}%" if sp500.get("change_pct") else None)
            mk2.metric("NASDAQ",
                       f"{nasdaq.get('value',0):,.0f}" if nasdaq.get("value") else "N/A",
                       delta=f"{nasdaq.get('change_pct',0):.2f}%" if nasdaq.get("change_pct") else None)
            mk3.metric("Dow Jones",
                       f"{dji.get('value',0):,.0f}" if dji.get("value") else "N/A",
                       delta=f"{dji.get('change_pct',0):.2f}%" if dji.get("change_pct") else None)
            mk4.metric("VIX",
                       f"{vix_v:.1f}" if vix_v else "N/A",
                       delta=None)
            mk5.metric("Dollar Index",
                       f"{dxy.get('value',0):.2f}" if dxy.get("value") else "N/A",
                       delta=f"{dxy.get('change_pct',0):.2f}%" if dxy.get("change_pct") else None)

            st.divider()

            mc1, mc2 = st.columns(2)
            with mc1:
                st.plotly_chart(
                    make_fear_greed_gauge(fg),
                    use_container_width=True,
                    key="chart_fear_greed_gauge",
                )
                st.plotly_chart(
                    make_aaii_bar(aaii),
                    use_container_width=True,
                    key="chart_aaii_bar",
                )
            with mc2:
                st.plotly_chart(
                    make_naaim_gauge(naaim),
                    use_container_width=True,
                    key="chart_naaim_gauge",
                )
                if cape_v:
                    fig_cape = make_gauge_chart(
                        value=cape_v, title="Shiller CAPE Ratio",
                        min_val=10, max_val=45,
                        thresholds=[(20,"#34d399"),(28,"#86efac"),(35,"#fbbf24"),(45,"#f87171")],
                    )
                    st.plotly_chart(fig_cape, use_container_width=True, key="chart_cape_gauge")

            st.subheader("University of Michigan Consumer Sentiment Index")
            st.caption(
                "Monthly survey of U.S. household confidence. Lower readings mean consumers feel worse about "
                "personal finances and the economy; higher readings support spending resilience."
            )
            umich_v = _get_val(fred, "UMCSENT")
            umich_delta = _hist_latest_delta(fred, "UMCSENT_HIST", periods=1)
            umich_avg = _hist_average(fred, "UMCSENT_HIST", periods=12)
            u1, u2 = st.columns([0.35, 0.65])
            with u1:
                st.metric(
                    "University of Michigan Consumer Sentiment Index",
                    f"{umich_v:.1f}" if umich_v is not None else "N/A",
                    delta=f"{umich_delta:+.1f} vs prior month" if umich_delta is not None else None,
                    help="FRED series UMCSENT. Below 60 is weak household confidence; above 80 is healthier sentiment.",
                )
                if umich_v is not None and umich_avg is not None:
                    st.caption(f"12-month average: {umich_avg:.1f}")
            with u2:
                st.plotly_chart(
                    make_fred_history_line_chart(
                        fred,
                        "UMCSENT_HIST",
                        "University of Michigan Consumer Sentiment Index — 36-Month History",
                        "Index",
                        "#3b82f6",
                    ),
                    use_container_width=True,
                    key="chart_markets_umich_sentiment",
                )

            st.subheader("Capital Flow Signal")
            st.caption(
                "This compares two risk-sensitive assets against the S&P 500: "
                "high-yield credit (HYG) and small caps (IWM). "
                "If both lag, money is hiding in quality. If both lead, risk appetite is broadening."
            )
            qr1, qr2 = st.columns([0.55, 1])
            with qr1:
                summary_text = (
                    "Both risk gauges are lagging the S&P 500 today."
                    if quality_rotation["signal"] == "Risk-Off / Quality Bid" else
                    "Both risk gauges are beating the S&P 500 today."
                    if quality_rotation["signal"] == "Risk-On" else
                    "One risk gauge is strong and the other is weak, so the signal is mixed."
                )
                summary_color = quality_rotation["color"]
                hyg_rel = quality_rotation.get("hyg_vs_spy")
                iwm_rel = quality_rotation.get("iwm_vs_spy")
                hyg_color = "#34d399" if (hyg_rel or 0) >= 0 else "#f87171"
                iwm_color = "#34d399" if (iwm_rel or 0) >= 0 else "#f87171"
                hyg_text = "N/A" if hyg_rel is None else f"{hyg_rel:+.2f}% vs SPX"
                iwm_text = "N/A" if iwm_rel is None else f"{iwm_rel:+.2f}% vs SPX"
                st.markdown(
                    f'<div style="background:#161b27;border:1px solid {summary_color};border-radius:10px;'
                    f'padding:14px 16px;margin-bottom:12px;">'
                    f'<div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.08em">'
                    f'Capital Flow Regime</div>'
                    f'<div style="color:{summary_color};font-size:24px;font-weight:700;margin-top:6px;">'
                    f'{quality_rotation["signal"]}</div>'
                    f'<div style="color:#94a3b8;font-size:13px;margin-top:8px;line-height:1.5">'
                    f'{summary_text}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if quality_rotation.get("score") is not None:
                    st.metric("Composite Relative Score", f"{quality_rotation['score']:+.2f}%")
                st.markdown(
                    f'<div style="background:#161b27;border:1px solid #1e2d3d;border-radius:10px;'
                    f'padding:12px 14px;">'
                    f'<div style="display:flex;justify-content:space-between;padding:4px 0;">'
                    f'<span style="color:#94a3b8;font-size:12px">Credit Risk</span>'
                    f'<span style="color:{hyg_color};font-size:12px;font-weight:700">'
                    f'{hyg_text}'
                    f'</span></div>'
                    f'<div style="display:flex;justify-content:space-between;padding:4px 0;">'
                    f'<span style="color:#94a3b8;font-size:12px">Small Caps</span>'
                    f'<span style="color:{iwm_color};font-size:12px;font-weight:700">'
                    f'{iwm_text}'
                    f'</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with qr2:
                st.plotly_chart(
                    make_quality_rotation_chart(mkt),
                    use_container_width=True,
                    key="chart_quality_rotation",
                )
                st.markdown(
                    """
**How to read this**

- `HYG vs SPX`: high-yield bonds versus the S&P 500. Negative means credit is lagging, which is usually defensive.
- `IWM vs SPX`: small caps versus the S&P 500. Negative means investors are avoiding cyclical / higher-beta stocks.
- If both bars are positive: broad risk-on.
- If both bars are negative: quality bid / defensive tape.
- If one is positive and one is negative: mixed signal, so treat it as neutral.
                    """
                )

            st.subheader("💱 FX & Commodities")
            fx_items = [
                ("DX-Y.NYB","Dollar Index (DXY)"),
                ("EURUSD=X","EUR/USD"),
                ("GBPUSD=X","GBP/USD"),
                ("JPY=X","JPY/USD"),
                ("GC=F","Gold"),
                ("CL=F","WTI Crude Oil"),
                ("BTC-USD","Bitcoin"),
            ]
            fx_cols = st.columns(4)
            for i, (sym, label) in enumerate(fx_items):
                d = mkt.get(sym) or {}
                v = d.get("value"); chg = d.get("change_pct")
                color = "#34d399" if (chg or 0) > 0 else "#f87171" if (chg or 0) < 0 else "#94a3b8"
                with fx_cols[i % 4]:
                    st.markdown(
                        f'<div style="background:#161b27;border-radius:8px;padding:10px;margin-bottom:8px">'
                        f'<div style="color:#64748b;font-size:11px">{label}</div>'
                        f'<div style="color:#e2e8f0;font-weight:600;font-size:15px">'
                        f'{"N/A" if v is None else f"{v:,.2f}"}</div>'
                        f'<div style="color:{color};font-size:12px">'
                        f'{"" if chg is None else f"{chg:+.2f}%"}</div></div>',
                        unsafe_allow_html=True,
                    )

    if "Energy Futures" in tab_map:
        with tab_map["Energy Futures"]:
            render_tab_summary("Energy Futures", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_energy_futures(futures_curve)

    # ── TAB 4: OPTIONS & DERIVATIVES ──────────────────────────────────────
    if "📉 Options & Derivatives" in tab_map:
        with tab_map["📉 Options & Derivatives"]:
            _render_section_refresh(
                "options_derivatives",
                [fetch_market, fetch_options_indicators, fetch_skew_index, fetch_vix_term_structure, fetch_options_chain_data, fetch_pcr_history],
            )
            with st.spinner("Loading options and derivatives data…"):
                opts = fetch_options_indicators()
                skew_idx = fetch_skew_index()
                vix_term = fetch_vix_term_structure()
                chain_data = fetch_options_chain_data("SPY")
                pcr_hist = fetch_pcr_history()
            render_tab_summary("📉 Options & Derivatives", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape, extra={"opts": opts, "chain_data": chain_data})
            render_options_derivatives(mkt, opts, skew_idx, vix_term, vix_v, chain_data=chain_data, pcr_hist=pcr_hist)

    # ── TAB 5: METALS ──────────────────────────────────────────────────────
    if "🪙 Metals" in tab_map:
        with tab_map["🪙 Metals"]:
            _render_section_refresh("metals", [fetch_market])
            render_tab_summary("🪙 Metals", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_metals(mkt)

    # ── TAB 6: HOUSING & CREDIT ────────────────────────────────────────────
    if "🏠 Housing & Credit" in tab_map:
        with tab_map["🏠 Housing & Credit"]:
            _render_section_refresh("housing_credit", [fetch_fred, fetch_treasury, fetch_market])
            regime_state = compute_regime_state(fred, lookback_days=regime_lookback_days)
            render_tab_summary("🏠 Housing & Credit", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape, extra={"regime_state": regime_state})
            render_housing_alerts(fred)

            st.subheader("Macro Regime Quadrant")
            st.markdown(
                f'<div style="display:inline-block;background:#161b27;border:1px solid {regime_state["color"]};'
                f'color:{regime_state["color"]};padding:6px 14px;border-radius:8px;font-weight:700;'
                f'font-size:14px;margin-bottom:10px">{regime_state["regime"]}</div>',
                unsafe_allow_html=True,
            )
            rq1, rq2 = st.columns([1.1, 1])
            with rq1:
                st.plotly_chart(
                    make_regime_quadrant_chart(regime_state),
                    use_container_width=True,
                    key="chart_regime_quadrant",
                )
            with rq2:
                st.plotly_chart(
                    make_regime_history_chart(regime_state),
                    use_container_width=True,
                    key="chart_regime_history",
                )

            rm1, rm2, rm3 = st.columns(3)
            with rm1:
                st.markdown(
                    f'<div style="color:{regime_state["color"]};font-size:12px;font-weight:700">◉ Credit ROC (bp)</div>',
                    unsafe_allow_html=True,
                )
                st.metric(" ", f"{regime_state['credit_roc']:+.1f}" if regime_state.get("credit_roc") is not None else "N/A")
            with rm2:
                st.markdown(
                    f'<div style="color:{regime_state["color"]};font-size:12px;font-weight:700">◉ Inflation ROC (bp)</div>',
                    unsafe_allow_html=True,
                )
                st.metric(" ", f"{regime_state['inflation_roc']:+.1f}" if regime_state.get("inflation_roc") is not None else "N/A")
            with rm3:
                st.markdown(
                    f'<div style="color:{regime_state["color"]};font-size:12px;font-weight:700">◉ Days in Regime</div>',
                    unsafe_allow_html=True,
                )
                st.metric(" ", f"{regime_state['days_in_regime']}" if regime_state.get("days_in_regime") is not None else "N/A")

            st.divider()

            hc1, hc2 = st.columns(2)
            with hc1:
                st.subheader("🏠 Housing Market")
                housing_items = [
                    ("HOUST","Housing Starts","k"),
                    ("PERMIT","Building Permits","k"),
                    ("MSPUS","Median Home Price","$"),
                    ("CSUSHPINSA","Case-Shiller HPI (YoY)","%"),
                    ("MORTGAGE30US","30yr Mortgage Rate","%"),
                    ("MORTGAGE15US","15yr Mortgage Rate","%"),
                ]
                for sid, label, unit in housing_items:
                    v = _get_val(fred, sid)
                    c = _status_color(sid, v) or "#94a3b8"
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                        f'border-bottom:1px solid #1e2d3d">'
                        f'<span style="color:#94a3b8;font-size:13px">{label}</span>'
                        f'<span style="color:{c};font-weight:600">{_fmt(v,unit)}</span></div>',
                        unsafe_allow_html=True,
                    )
                mtg_spread = _get_val(fred, "MTG_SPREAD")
                if mtg_spread:
                    st.metric("30yr vs 15yr Spread", f"{mtg_spread:.0f} bp")

            with hc2:
                st.subheader("🔒 Credit Markets")
                st.plotly_chart(
                    make_credit_spreads_chart(fred),
                    use_container_width=True,
                    key="chart_credit_spreads",
                )

                credit_items = [
                    ("BAMLH0A0HYM2","HY Credit Spread","bp"),
                    ("BAMLC0A0CM","IG Credit Spread","bp"),
                    ("NFCI","Chicago Financial Conditions","idx"),
                    ("STLFSI2","St. Louis Stress Index","idx"),
                ]
                for sid, label, unit in credit_items:
                    v = _get_val(fred, sid)
                    c = _status_color(sid, v) or "#94a3b8"
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                        f'border-bottom:1px solid #1e2d3d">'
                        f'<span style="color:#94a3b8;font-size:13px">{label}</span>'
                        f'<span style="color:{c};font-weight:600">{_fmt(v,unit)}</span></div>',
                        unsafe_allow_html=True,
                    )

                st.subheader("🌐 Global Central Banks")
                cb_items = [
                    ("DFF","US Fed Funds Rate","%"),
                    ("ECBDFR","ECB Deposit Rate","%"),
                    ("BOERUKM","Bank of England Rate","%"),
                    ("IRSTCI01JPM156N","Bank of Japan Rate","%"),
                ]
                cb_cols = st.columns(4)
                for i, (sid, label, unit) in enumerate(cb_items):
                    v = _get_val(fred, sid)
                    with cb_cols[i]:
                        st.metric(label.replace(" Rate",""), f"{v:.2f}%" if v else "N/A")

    # ── TAB 7: PHILLIPS CURVE ──────────────────────────────────────────────
    if "📊 Phillips Curve" in tab_map:
        with tab_map["📊 Phillips Curve"]:
            _render_section_refresh("phillips_curve", [fetch_fred])
            render_tab_summary("📊 Phillips Curve", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            st.subheader("📉 Phillips Curve — Unemployment vs Inflation")
            st.markdown(
                """
                The **Phillips Curve** illustrates the classic macroeconomic trade-off between unemployment
                and inflation. In theory, lower unemployment corresponds with higher inflation as the
                tight labor market pushes wages (and prices) up.

                - 🔴 **Star** = Current reading
                - 🔵 **Circles** = Prior months (lookback window set in sidebar)
                - **Dotted gold line** = OLS trend line
                - **Green dashed line** = Fed's 2% inflation target
                """,
            )
            st.plotly_chart(
                make_phillips_curve_chart(fred, lookback_months=lookback),
                use_container_width=True,
                key="chart_phillips_curve",
            )

            # Interpretation block
            cpi_curr  = _get_val(fred, "CPIAUCSL")
            un_curr   = _get_val(fred, "UNRATE")
            if cpi_curr and un_curr:
                if cpi_curr > 3 and un_curr < 4.5:
                    st.warning(
                        f"⚡ **Overheating zone**: tight labor market ({un_curr:.1f}% unemployment) "
                        f"with elevated inflation ({cpi_curr:.1f}%). Classic Phillips trade-off in play — "
                        f"the Fed must weigh cooling prices vs. protecting jobs."
                    )
                elif cpi_curr < 2.5 and un_curr < 4.5:
                    st.success(
                        f"🌤 **Goldilocks zone**: low unemployment ({un_curr:.1f}%) without runaway "
                        f"inflation ({cpi_curr:.1f}%). Relatively rare and desirable macro condition."
                    )
                elif cpi_curr < 2 and un_curr > 5:
                    st.error(
                        f"🧊 **Stagflation risk / Slackening**: rising unemployment ({un_curr:.1f}%) "
                        f"while inflation ({cpi_curr:.1f}%) falls toward deflationary territory."
                    )
                else:
                    st.info(
                        f"📊 Unemployment: **{un_curr:.1f}%** — CPI Inflation: **{cpi_curr:.1f}%**. "
                        f"Monitor for directional shifts in coming months."
                    )

    # ── TAB 8: NEWS & SIGNALS ──────────────────────────────────────────────
    if "📰 News & Signals" in tab_map:
        with tab_map["📰 News & Signals"]:
            _render_section_refresh("news_signals", [fetch_fred, fetch_market, fetch_news, fetch_worldmonitor_news])
            with st.spinner("Loading news and signal data…"):
                news = fetch_news()
                worldmonitor_news = fetch_worldmonitor_news(
                    per_category=6,
                    category_keys=WORLDMONITOR_NEWS_CATEGORY_ORDER,
                )
            render_tab_summary("📰 News & Signals", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            regime_label, regime_color = _regime(fred, mkt)
            st.markdown(
                f'<div style="background:#161b27;border-left:4px solid {regime_color};'
                f'padding:12px 18px;border-radius:0 8px 8px 0;margin-bottom:16px">'
                f'<span style="color:#94a3b8;font-size:12px;text-transform:uppercase;'
                f'letter-spacing:.08em">Current Macro Regime</span><br>'
                f'<span style="color:{regime_color};font-size:20px;font-weight:700">'
                f'{regime_label}</span></div>',
                unsafe_allow_html=True,
            )

            render_worldmonitor_news_section(worldmonitor_news)
            st.divider()

            if news:
                st.subheader("📰 Latest Macro News (Alpha Vantage)")
                for item in news:
                    sentiment_color = item["color"]
                    st.markdown(
                        f'<div style="background:#161b27;border-radius:8px;padding:14px;'
                        f'margin-bottom:10px;border-left:3px solid {sentiment_color}">'
                        f'<a href="{item["url"]}" target="_blank" rel="noopener noreferrer" style="color:#e2e8f0;'
                        f'font-weight:600;text-decoration:none;font-size:14px">'
                        f'{item["title"]}</a><br>'
                        f'<span style="color:#64748b;font-size:11px">'
                        f'{item["source"]}  ·  {item["time"]}  ·  </span>'
                        f'<span style="color:{sentiment_color};font-size:11px;font-weight:600">'
                        f'{item["sentiment"]}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No news data available. Check your Alpha Vantage API key in `.streamlit/secrets.toml`.")

            st.divider()
            st.subheader("🎯 Signal Summary")
            sig_cols = st.columns(3)
            with sig_cols[0]:
                st.markdown("**Growth Signals**")
                for sid, label in [("GDPNOW","GDPNow"),("USSLIND","LEI"),("CFNAI","CFNAI")]:
                    v = _get_val(fred, sid)
                    c = _status_color(sid, v) or "⚪"
                    dot = "🟢" if c=="#34d399" else "🔴" if c=="#f87171" else "🟡"
                    st.markdown(f"{dot} {label}: **{_fmt(v,'%')}**")
            with sig_cols[1]:
                st.markdown("**Inflation Signals**")
                for sid, label in [("CPIAUCSL","CPI"),("PCEPILFE","Core PCE"),("T10YIE","Breakeven")]:
                    v = _get_val(fred, sid)
                    c = _status_color(sid, v) or "⚪"
                    dot = "🟢" if c=="#34d399" else "🔴" if c=="#f87171" else "🟡"
                    st.markdown(f"{dot} {label}: **{_fmt(v,'%')}**")
            with sig_cols[2]:
                st.markdown("**Risk/Credit Signals**")
                for sid, unit, label in [("BAMLH0A0HYM2","bp","HY Spread"),
                                          ("RECPROUSM156N","%","Rec. Prob"),
                                          ("NFCI","idx","NFCI")]:
                    v = _get_val(fred, sid)
                    c = _status_color(sid, v) or "⚪"
                    dot = "🟢" if c=="#34d399" else "🔴" if c=="#f87171" else "🟡"
                    st.markdown(f"{dot} {label}: **{_fmt(v,unit)}**")

    if "Liquidity Conditions" in tab_map:
        with tab_map["Liquidity Conditions"]:
            _render_section_refresh(
                "liquidity_conditions",
                [fetch_fred, fetch_market, fetch_treasury, fetch_sofr_spread, fetch_amihud_illiquidity],
            )
            with st.spinner("Loading liquidity conditions data…"):
                sofr_data = fetch_sofr_spread()
                amihud_data = fetch_amihud_illiquidity("SPY", lookback=30)
            render_tab_summary("Liquidity Conditions", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_liquidity_conditions(fred, mkt, treasury, sofr_data, amihud_data)

    if "Institutional Flows" in tab_map:
        with tab_map["Institutional Flows"]:
            _render_section_refresh(
                "institutional_flows",
                [fetch_fred, fetch_cot_data, fetch_ici_fund_flows, fetch_13f_aggregate, fetch_mmf_assets_history, fetch_cta_momentum_model, fetch_sg_cta_index_performance],
            )
            with st.spinner("Loading institutional flow data…"):
                cot_data = fetch_cot_data()
                ici_data = fetch_ici_fund_flows()
                inst13f = fetch_13f_aggregate(top_n=10)
                mmf_history = fetch_mmf_assets_history(fred)
                cta_model = fetch_cta_momentum_model()
                sg_cta = fetch_sg_cta_index_performance()
            inst_score = compute_institutional_participation_score(cot_data, ici_data, mmf_history, fred)
            render_tab_summary("Institutional Flows", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape, extra={"inst_score": inst_score})
            render_institutional_flows(
                fred, cot_data, ici_data, mmf_history, inst13f,
                cta_model=cta_model, sg_cta=sg_cta
            )

    if "GS-Style Composites" in tab_map:
        with tab_map["GS-Style Composites"]:
            _render_section_refresh(
                "gs_style_composites",
                [fetch_fred, fetch_market, fetch_options_indicators, fetch_fear_greed, fetch_shiller_cape],
            )
            with st.spinner("Loading composite inputs…"):
                opts = fetch_options_indicators()
            render_tab_summary("GS-Style Composites", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_gs_style_composites(fred, mkt, fg, opts, cape)

    if "Global Macro" in tab_map:
        with tab_map["Global Macro"]:
            _render_section_refresh("global_macro", [fetch_fred, fetch_market])
            render_tab_summary("Global Macro", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_global_macro(fred, mkt)

    if "Sentiment Framework" in tab_map:
        with tab_map["Sentiment Framework"]:
            _render_section_refresh(
                "sentiment_framework",
                [fetch_market, fetch_options_indicators, fetch_skew_index, fetch_vix_term_structure, fetch_fear_greed, fetch_aaii, fetch_pcr_history, fetch_vrp_and_realized_vol],
            )
            with st.spinner("Loading sentiment framework data…"):
                opts = fetch_options_indicators()
                skew_idx = fetch_skew_index()
                vix_term = fetch_vix_term_structure()
                aaii = fetch_aaii()
                pcr_hist = fetch_pcr_history()
                vrp_data = fetch_vrp_and_realized_vol()
            panic_data = compute_gs_panic_proxy(mkt, opts, skew_idx, pcr_hist)
            render_tab_summary("Sentiment Framework", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_sentiment_framework(
                mkt, opts, skew_idx, fg, aaii, vix_term,
                pcr_hist, vrp_data, panic_data
            )

    if "🤖 AI Macro Analysis" in tab_map:
        with tab_map["🤖 AI Macro Analysis"]:
            render_tab_summary("🤖 AI Macro Analysis", fred, treasury=treasury, mkt=mkt, fg=fg, naaim=naaim, cape=cape)
            render_ai_macro_analysis()

    # ── DOWNLOAD BUTTON ──────────────────────────────────────────────────────
    st.divider()
    st.caption("Offline dashboard generation is on-demand so normal reruns do not wait for every downstream feed.")
    if st.button("Prepare Full Offline Dashboard (HTML)", key="prepare_html_report"):
        with st.status("Preparing offline dashboard…", expanded=True) as status:
            status.write("Loading all section-specific data for the offline file…")
            report_premarket = fetch_premarket_snapshot()
            report_opts = fetch_options_indicators()
            report_skew_idx = fetch_skew_index()
            report_chain_data = fetch_options_chain_data("SPY")
            report_pcr_hist = fetch_pcr_history()
            report_vix_term = fetch_vix_term_structure()
            report_aaii = fetch_aaii()
            report_news = fetch_news()
            report_worldmonitor_news = fetch_worldmonitor_news(per_category=5)
            report_bls = fetch_bls()
            report_vrp_data = fetch_vrp_and_realized_vol()
            report_panic_data = compute_gs_panic_proxy(mkt, report_opts, report_skew_idx, report_pcr_hist)
            report_sofr_data = fetch_sofr_spread()
            report_amihud_data = fetch_amihud_illiquidity("SPY", lookback=30)
            report_cot_data = fetch_cot_data()
            report_ici_data = fetch_ici_fund_flows()
            report_inst13f = fetch_13f_aggregate(top_n=10)
            report_mmf_history = fetch_mmf_assets_history(fred)
            report_cta_model = fetch_cta_momentum_model()
            report_sg_cta = fetch_sg_cta_index_performance()
            st.session_state["prepared_html_report"] = generate_html_report(
                fred, mkt, treasury, fg, naaim, cape, report_aaii,
                opts=report_opts,
                skew_idx=report_skew_idx,
                chain_data=report_chain_data,
                pcr_hist=report_pcr_hist,
                sofr_data=report_sofr_data,
                amihud_data=report_amihud_data,
                cot_data=report_cot_data,
                ici_data=report_ici_data,
                mmf_history=report_mmf_history,
                inst13f=report_inst13f,
                premarket_data=report_premarket,
                news=report_news,
                worldmonitor_news=report_worldmonitor_news,
                bls=report_bls,
                vix_term=report_vix_term,
                vrp_data=report_vrp_data,
                panic_data=report_panic_data,
                cta_model=report_cta_model,
                sg_cta=report_sg_cta,
            )
            status.update(label="✅ Offline dashboard HTML ready", state="complete", expanded=False)
    prepared_html_report = st.session_state.get("prepared_html_report")
    if prepared_html_report:
        st.download_button(
            label="⬇️ Download Full Offline Dashboard (HTML)",
            data=prepared_html_report.encode("utf-8"),
            file_name=f"macro_dashboard_offline_{datetime.date.today()}.html",
            mime="text/html",
            use_container_width=False,
        )


if __name__ == "__main__":
    if "--export" in sys.argv:
        export_snapshot_to_json()
        raise SystemExit(0)
    main()
