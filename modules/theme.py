"""Terminal-futuristic dark theme injection for the Streamlit macro dashboard.

Exports a single function ``inject_theme()`` that writes one global <style> block
via ``st.markdown(..., unsafe_allow_html=True)``. Called once at app start.
"""

from __future__ import annotations

import streamlit as st

import pandas as pd


_BG = "#0a0e14"
_PANEL = "#11161f"
_BORDER = "#1e2733"
_TEXT = "#e6edf3"
_SECONDARY = "#8b98a9"
_ACCENT = "#22d3ee"
_RISK_ON = "#34d399"
_RISK_OFF = "#f87171"
_NEUTRAL = "#fbbf24"


def terminal_badge(text: str, level: str = "info") -> None:
    """Render a compact terminal-style verdict badge.

    level: "success" | "error" | "warning" | "info"
    """
    color_map = {
        "success": _RISK_ON,
        "error": _RISK_OFF,
        "warning": _NEUTRAL,
        "info": _ACCENT,
    }
    color = color_map.get(level, _ACCENT)
    st.markdown(
        f'<div style="display:inline-block; background:{_PANEL}; border:1px solid {_BORDER}; '
        f'border-left:2px solid {color}; border-radius:4px; padding:6px 10px; '
        f'font-family:JetBrains Mono, monospace; font-size:11px; font-weight:600; '
        f'letter-spacing:0.06em; text-transform:uppercase; color:{_TEXT}; margin:2px 0;">'
        f'{text}</div>',
        unsafe_allow_html=True,
    )


def kpi_tile(label: str, value: str, delta: str | None = None, delta_color: str = "normal") -> None:
    """Render a terminal-style KPI tile with big mono value and optional delta."""
    delta_color_map = {
        "normal": _RISK_ON,
        "inverse": _RISK_OFF,
        "off": _RISK_OFF,
    }
    top_color = delta_color_map.get(delta_color, _ACCENT)
    delta_html = ""
    if delta:
        # Replace any unicode arrows with +/- prefixes if not already signed.
        clean_delta = delta.replace("▲", "+").replace("▼", "-").replace("↑", "+").replace("↓", "-")
        if not clean_delta.startswith(("+", "-")) and any(c.isdigit() for c in clean_delta):
            clean_delta = "+" + clean_delta
        delta_html = (
            f'<div style="font-family:JetBrains Mono, monospace; font-size:12px; '
            f'color:{top_color}; margin-top:4px;">{clean_delta}</div>'
        )
    st.markdown(
        f'<div style="background:{_PANEL}; border:1px solid {_BORDER}; '
        f'border-top:2px solid {top_color}; border-radius:4px; padding:12px; height:100%;">'
        f'<div style="font-family:JetBrains Mono, monospace; font-size:10px; font-weight:500; '
        f'letter-spacing:0.08em; text-transform:uppercase; color:{_SECONDARY}; margin-bottom:4px;">'
        f'{label}</div>'
        f'<div style="font-family:JetBrains Mono, monospace; font-size:22px; font-weight:600; '
        f'color:{_TEXT}; font-variant-numeric:tabular-nums;">{value}</div>'
        f'{delta_html}</div>',
        unsafe_allow_html=True,
    )


def style_dataframe(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply terminal styling to a DataFrame for st.dataframe."""
    # Identify numeric columns for right alignment and signed coloring.
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    def _color_signed(val):
        if pd.isna(val):
            return "color:#8b98a9"
        if isinstance(val, (int, float)):
            if val > 0:
                return f"color:{_RISK_ON}"
            if val < 0:
                return f"color:{_RISK_OFF}"
        return f"color:{_TEXT}"

    styler = (
        df.style
        .set_properties(**{
            "font-family": "JetBrains Mono, monospace",
            "font-size": "12px",
            "color": _TEXT,
            "background-color": _PANEL,
        })
        .set_table_styles([
            {"selector": "th", "props": [
                ("font-family", "JetBrains Mono, monospace"),
                ("font-size", "10px"),
                ("font-weight", "600"),
                ("letter-spacing", "0.06em"),
                ("text-transform", "uppercase"),
                ("color", _SECONDARY),
                ("background-color", _PANEL),
                ("border-bottom", f"1px solid {_BORDER}"),
            ]},
            {"selector": "td", "props": [
                ("border-bottom", f"1px solid {_BORDER}"),
            ]},
        ])
    )

    if numeric_cols:
        styler = styler.format({col: "{:,.2f}" for col in numeric_cols}, na_rep="N/A")
        styler = styler.map(_color_signed, subset=numeric_cols)
        styler = styler.set_properties(subset=numeric_cols, **{"text-align": "right"})

    return styler


def inject_theme() -> None:
    """Render the global terminal-futuristic CSS."""
    css = f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

      :root {{
        --md-bg: {_BG};
        --md-panel: {_PANEL};
        --md-border: {_BORDER};
        --md-text: {_TEXT};
        --md-secondary: {_SECONDARY};
        --md-accent: {_ACCENT};
        --md-risk-on: {_RISK_ON};
        --md-risk-off: {_RISK_OFF};
        --md-neutral: {_NEUTRAL};
      }}

      html, body, .stApp, .main, .block-container,
      [data-testid="stAppViewContainer"] {{
        background-color: {_BG} !important;
        color: {_TEXT} !important;
        font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif !important;
      }}

      /* Hide Streamlit chrome */
      #MainMenu {{ display: none !important; }}
      footer {{ display: none !important; }}
      header[data-testid="stHeader"] {{ display: none !important; }}
      .stDeployButton {{ display: none !important; }}

      /* Typography */
      h1, h2, h3, h4, h5, h6 {{
        font-family: 'Space Grotesk', sans-serif !important;
        color: {_TEXT} !important;
        font-weight: 600 !important;
        letter-spacing: 0 !important;
      }}
      p, li, span, div, label {{
        color: {_TEXT} !important;
      }}

      /* Links */
      a, a:visited {{
        color: {_ACCENT} !important;
      }}
      a:hover {{
        color: {_TEXT} !important;
      }}

      /* Numbers, tickers, timestamps: mono */
      [data-testid="stMetricValue"],
      [data-testid="stMetricDelta"],
      .mono, code, pre, kbd, .stCode {{
        font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace !important;
        font-variant-numeric: tabular-nums !important;
      }}

      /* Tabs: terminal nav */
      .stTabs [data-baseweb="tab-list"] {{
        background: transparent !important;
        border: none !important;
        border-bottom: 1px solid {_BORDER} !important;
        border-radius: 0 !important;
        padding: 0 !important;
        gap: 0 !important;
      }}
      .stTabs [data-baseweb="tab"] {{
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        color: {_SECONDARY} !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11px !important;
        font-weight: 500 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        padding: 10px 16px !important;
        margin: 0 !important;
        border-bottom: 2px solid transparent !important;
      }}
      .stTabs [data-baseweb="tab"]:hover {{
        color: {_TEXT} !important;
        border-bottom-color: {_BORDER} !important;
      }}
      .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        color: {_ACCENT} !important;
        border-bottom-color: {_ACCENT} !important;
      }}

      /* Metric cards */
      [data-testid="stMetric"] {{
        background: {_PANEL} !important;
        border: 1px solid {_BORDER} !important;
        border-radius: 4px !important;
        padding: 12px !important;
      }}
      [data-testid="stMetricLabel"] p {{
        font-family: 'JetBrains Mono', monospace !important;
        color: {_SECONDARY} !important;
        font-size: 10px !important;
        font-weight: 500 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
      }}
      [data-testid="stMetricValue"] {{
        font-family: 'JetBrains Mono', monospace !important;
        color: {_TEXT} !important;
        font-size: 22px !important;
        font-weight: 600 !important;
      }}
      [data-testid="stMetricDelta"] {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
      }}

      /* Alert boxes (success/error/warning/info) */
      .stAlert {{
        background: {_PANEL} !important;
        border: none !important;
        border-radius: 4px !important;
        padding: 12px 14px !important;
        color: {_TEXT} !important;
      }}
      .stAlert [data-testid="stAlertContent"] {{
        color: {_TEXT} !important;
      }}
      .stAlert [data-testid="stAlertContent"] .icon {{
        display: none !important;
      }}
      .stAlert[data-kind="success"] {{ border-left: 2px solid {_RISK_ON} !important; }}
      .stAlert[data-kind="error"] {{ border-left: 2px solid {_RISK_OFF} !important; }}
      .stAlert[data-kind="warning"] {{ border-left: 2px solid {_NEUTRAL} !important; }}
      .stAlert[data-kind="info"] {{ border-left: 2px solid {_ACCENT} !important; }}

      /* Expanders */
      [data-testid="stExpander"] {{
        border: 1px solid {_BORDER} !important;
        border-radius: 4px !important;
        background: {_PANEL} !important;
      }}
      [data-testid="stExpander"] summary {{
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 13px !important;
        color: {_TEXT} !important;
      }}
      [data-testid="stExpander"] summary:hover {{
        color: {_ACCENT} !important;
      }}
      [data-testid="stExpander"] summary svg {{
        color: {_ACCENT} !important;
      }}

      /* Dataframes / tables */
      .stDataFrame, [data-testid="stDataFrame"] {{
        border: 1px solid {_BORDER} !important;
        border-radius: 4px !important;
      }}
      .stDataFrame table, [data-testid="stTable"] table {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
      }}
      .stDataFrame th, [data-testid="stTable"] th {{
        background: {_PANEL} !important;
        color: {_SECONDARY} !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        font-size: 10px !important;
      }}
      .stDataFrame td, [data-testid="stTable"] td {{
        color: {_TEXT} !important;
        border-color: {_BORDER} !important;
      }}

      /* Sidebar */
      [data-testid="stSidebar"] {{
        background: #0d1219 !important;
        border-right: 1px solid {_BORDER} !important;
      }}
      [data-testid="stSidebar"] .stRadio > label,
      [data-testid="stSidebar"] .stCheckbox > label,
      [data-testid="stSidebar"] .stSelectbox > label,
      [data-testid="stSidebar"] .stMultiSelect > label,
      [data-testid="stSidebar"] h1,
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] h3 {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11px !important;
        color: {_SECONDARY} !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
      }}
      [data-testid="stSidebar"] .stRadio > div > label,
      [data-testid="stSidebar"] .stCheckbox > div > label {{
        color: {_TEXT} !important;
        text-transform: none !important;
      }}

      /* Buttons */
      .stButton > button {{
        background: transparent !important;
        border: 1px solid {_BORDER} !important;
        border-radius: 4px !important;
        color: {_TEXT} !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
      }}
      .stButton > button:hover {{
        border-color: {_ACCENT} !important;
        color: {_ACCENT} !important;
      }}
      .stButton > button:active {{
        background: rgba(34, 211, 238, 0.1) !important;
      }}

      /* Dividers */
      hr {{
        border: 0 !important;
        border-top: 1px solid {_BORDER} !important;
        margin: 12px 0 !important;
      }}
      .stDivider {{
        border-color: {_BORDER} !important;
      }}

      /* Block container */
      .block-container {{
        padding-top: 0.75rem !important;
        padding-bottom: 2rem !important;
        max-width: 1600px !important;
      }}

      /* Streamlit spinner/progress */
      .stSpinner > div {{
        border-color: {_ACCENT} transparent transparent transparent !important;
      }}
      .stProgress > div > div {{
        background-color: {_ACCENT} !important;
      }}

      /* Input / select widgets */
      .stTextInput > div > div > input,
      .stSelectbox > div > div > select,
      .stNumberInput > div > div > input,
      .stTextArea > div > div > textarea {{
        background: {_PANEL} !important;
        border: 1px solid {_BORDER} !important;
        color: {_TEXT} !important;
        font-family: 'JetBrains Mono', monospace !important;
        border-radius: 4px !important;
      }}
      .stTextInput > div > div > input:focus,
      .stSelectbox > div > div > select:focus {{
        border-color: {_ACCENT} !important;
      }}

      /* Tooltips / markdown code */
      code, pre {{
        background: {_PANEL} !important;
        border: 1px solid {_BORDER} !important;
        color: {_ACCENT} !important;
        border-radius: 3px !important;
      }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
