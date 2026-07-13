"""Streamlit UI layer for the regime-detection engine.

Keeps all presentation code separate from the pure-computation
``modules.regime_engine``.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.config import COLORS, apply_house_style, fmt_pct
from modules.data_fetch import fetch_spy_vix_history
from modules.regime_engine import (
    RegimeSignal,
    compute_consensus,
    hmm_detector,
    liquidity_regime_detector,
    macro_quadrant_adapter,
    trend_vol_detector,
    vol_regime_detector,
)

_GRID_COLOR = "#1e2733"

_STATE_COLORS = {
    # TrendVol
    ("TrendVol", "Trend Confirmed"): COLORS["risk_on"],
    ("TrendVol", "Trend Weak"): COLORS["neutral"],
    ("TrendVol", "Below Trend"): COLORS["risk_off"],
    # HMM
    ("HMM", "Low-Vol Bull"): COLORS["risk_on"],
    ("HMM", "Moderate"): COLORS["neutral"],
    ("HMM", "High-Vol Stress"): COLORS["risk_off"],
    # VolRegime (Stressed is a watch state, amber)
    ("VolRegime", "Calm"): COLORS["risk_on"],
    ("VolRegime", "Stressed"): COLORS["neutral"],
    ("VolRegime", "Crisis"): COLORS["risk_off"],
    # Liquidity (Stressed is risk-off, red)
    ("Liquidity", "Loose"): COLORS["risk_on"],
    ("Liquidity", "Tightening"): COLORS["neutral"],
    ("Liquidity", "Stressed"): COLORS["risk_off"],
    # Macro
    ("MacroQuadrant", "Goldilocks"): COLORS["risk_on"],
    ("MacroQuadrant", "Reflation"): COLORS["neutral"],
    ("MacroQuadrant", "Stagflation"): COLORS["risk_off"],
    ("MacroQuadrant", "Recession"): COLORS["risk_off"],
    ("MacroQuadrant", "Mixed / Uncertain"): COLORS["muted"],
    # Generic
    ("*", "No Data"): COLORS["muted"],
}


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"


def _score_color(score: Optional[float]) -> str:
    if score is None:
        return COLORS["muted"]
    if score > 0.3:
        return COLORS["risk_on"]
    if score < -0.3:
        return COLORS["risk_off"]
    return COLORS["neutral"]


def _state_color(detector_name: str, state: str) -> str:
    return _STATE_COLORS.get(
        (detector_name, state), _STATE_COLORS.get(("*", state), COLORS["muted"])
    )


def _label_from_score(score: float) -> str:
    if score > 0.3:
        return "Risk-On"
    if score < -0.3:
        return "Risk-Off"
    return "Neutral"


# ---------------------------------------------------------------------------
# Cached data / signal boundary
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def _cached_fetch_spy_vix_history() -> Dict[str, Optional[pd.DataFrame]]:
    """Cache 10-year SPY/^VIX history for one hour."""
    raw = fetch_spy_vix_history(period="10y", interval="1d") or {}
    ts = datetime.datetime.now()
    for key in ("spy", "vix"):
        df = raw.get(key)
        if df is not None and hasattr(df, "attrs"):
            df.attrs["_fetched_at"] = ts
    return raw


@st.cache_data(ttl=3600)
def _cached_compute_signals(
    spy_df: pd.DataFrame,
    vix_value: Optional[float],
    term_structure: Mapping[str, Optional[float]],
    fred: Mapping[str, Any],
) -> List[RegimeSignal]:
    """Run all regime detectors; cached so the UI stays snappy on reruns."""
    signals: List[RegimeSignal] = []

    signals.append(trend_vol_detector(spy_df, timeframe="D"))
    signals.append(trend_vol_detector(spy_df, timeframe="W"))
    signals.append(hmm_detector(spy_df))
    signals.append(vol_regime_detector(vix_value, term_structure, spy_df))
    signals.append(liquidity_regime_detector(fred))
    signals.append(macro_quadrant_adapter(fred))
    return signals


@st.cache_data(ttl=3600)
def get_regime_consensus(
    fred: Mapping[str, Any], mkt: Mapping[str, Any]
) -> Tuple[List[RegimeSignal], Dict[str, Dict[str, Any]], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Fetch data, run detectors, and return signals + consensus.

    This is the single cached entry point used by both the page header and the
    Regime Monitor tab so the work is never duplicated.
    """
    spy_vix = _cached_fetch_spy_vix_history()
    spy_df = spy_vix.get("spy") if spy_vix else None
    vix_df = spy_vix.get("vix") if spy_vix else None

    vix_value = (mkt.get("^VIX") or {}).get("value")
    term_structure = {
        "^VIX9D": (mkt.get("^VIX9D") or {}).get("value"),
        "^VIX3M": (mkt.get("^VIX3M") or {}).get("value"),
        "^VIX6M": (mkt.get("^VIX6M") or {}).get("value"),
    }

    if spy_df is None:
        spy_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    else:
        spy_df = spy_df.copy()

    signals = _cached_compute_signals(spy_df, vix_value, term_structure, fred)
    consensus = compute_consensus(signals)
    return signals, consensus, spy_df, vix_df


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_consensus_scoreboard(consensus: Mapping[str, Mapping[str, Any]]) -> None:
    st.subheader("Consensus Scoreboard")
    timeframes = [tf for tf in ["D", "W", "M"] if tf in consensus]
    if not timeframes:
        st.info("No consensus available.")
        return

    cols = st.columns(len(timeframes))
    label_map = {"D": "Daily", "W": "Weekly", "M": "Monthly"}
    for col, tf in zip(cols, timeframes):
        c = consensus[tf]
        score = c.get("risk_score", 0.0)
        label = c.get("label", "No Data")
        agreement = c.get("agreement", 0.0)
        n = c.get("n", 0)
        color = _score_color(score) if label != "No Data" else COLORS["muted"]
        with col:
            st.markdown(
                f'<div style="background:{COLORS["panel"]}; border:1px solid {COLORS["border"]}; '
                f'border-top:2px solid {color}; border-radius:4px; padding:14px; text-align:center;">'
                f'<div style="font-family:JetBrains Mono, monospace; font-size:10px; font-weight:500; '
                f'letter-spacing:0.08em; text-transform:uppercase; color:{COLORS["muted"]}; margin-bottom:6px;">'
                f'{label_map.get(tf, tf)}</div>'
                f'<div style="font-family:JetBrains Mono, monospace; font-size:32px; font-weight:600; '
                f'color:{COLORS["text"]}; font-variant-numeric:tabular-nums;">{score:+.2f}</div>'
                f'<div style="font-family:JetBrains Mono, monospace; font-size:12px; font-weight:600; '
                f'color:{color}; margin-top:2px;">{label}</div>'
                f'<div style="font-family:JetBrains Mono, monospace; font-size:10px; '
                f'color:{COLORS["muted"]}; margin-top:6px;">'
                f'agreement {fmt_pct(agreement * 100, 0)} · {n} detectors</div></div>',
                unsafe_allow_html=True,
            )


def _render_detector_matrix(signals: Sequence[RegimeSignal]) -> None:
    st.subheader("Detector Matrix")

    # Group signals by detector, keep timeframe columns.
    detectors: Dict[str, Dict[str, RegimeSignal]] = {}
    for sig in signals:
        detectors.setdefault(sig.detector_name, {})[sig.timeframe] = sig

    timeframes = sorted({sig.timeframe for sig in signals}, key=lambda x: {"D": 0, "W": 1, "M": 2}.get(x, 3))
    if not timeframes:
        st.info("No detector signals available.")
        return

    detector_names = sorted(detectors.keys())
    header = ["Detector"] + [tf for tf in timeframes]
    cell_values: List[List[str]] = [[] for _ in header]
    cell_colors: List[List[str]] = [[] for _ in header]

    cell_values[0] = detector_names
    cell_colors[0] = [COLORS["panel"]] * len(detector_names)

    for col_idx, tf in enumerate(timeframes, start=1):
        vals = []
        colors = []
        for name in detector_names:
            sig = detectors[name].get(tf)
            if sig is None:
                vals.append("—")
                colors.append(COLORS["panel"])
            else:
                state = sig.state
                score = sig.risk_score
                vals.append(f"{state}\n({score:+.2f})")
                colors.append(_rgba(_score_color(score) if state != "No Data" else COLORS["muted"], 0.25))
        cell_values[col_idx] = vals
        cell_colors[col_idx] = colors

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=header,
                    fill_color=COLORS["panel"],
                    align="center",
                    font=dict(
                        family="JetBrains Mono, monospace",
                        color=COLORS["muted"],
                        size=10,
                    ),
                    line_color=COLORS["border"],
                    line_width=1,
                    height=36,
                ),
                cells=dict(
                    values=cell_values,
                    fill_color=cell_colors,
                    align="center",
                    font=dict(
                        family="JetBrains Mono, monospace",
                        color=COLORS["text"],
                        size=11,
                    ),
                    line_color=COLORS["border"],
                    line_width=1,
                    height=34,
                ),
                columnwidth=[120] + [100] * len(timeframes),
            )
        ]
    )
    apply_house_style(fig, height=60 + 38 * len(detector_names))
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch", key="chart_regime_detector_matrix")


def _render_detector_expanders(signals: Sequence[RegimeSignal]) -> None:
    """Show per-detector metrics inside expanders.

    Detail charts were removed because rendering Plotly figures inside
    expanders caused subsequent Streamlit tabs to render blank panels.
    The Regime Monitor tab still provides the matrix, scoreboard, and
    (when enabled) timeline heatmap visualizations.
    """
    st.subheader("Detector Detail")
    for sig in signals:
        with st.expander(f"{sig.detector_name} ({sig.timeframe}) — {sig.state}"):
            m1, m2, m3 = st.columns(3)
            m1.metric("State", sig.state)
            m2.metric("Risk score", f"{sig.risk_score:+.2f}")
            m3.metric("Confidence", fmt_pct(sig.confidence * 100, 0))


def _render_timeline_heatmap(signals: Sequence[RegimeSignal]) -> None:
    st.subheader("Regime Timeline Heatmap")
    cutoff = pd.Timestamp.now().normalize() - pd.DateOffset(years=3)

    rows: Dict[str, pd.Series] = {}
    for sig in signals:
        hist = sig.history.copy()
        if hist.empty or "date" not in hist.columns or "risk_score" not in hist.columns:
            continue
        hist["date"] = pd.to_datetime(hist["date"])
        hist = hist[hist["date"] >= cutoff].sort_values("date").set_index("date")
        if not hist.empty:
            label = f"{sig.detector_name} ({sig.timeframe})"
            rows[label] = hist["risk_score"].resample("B").last().ffill()

    if len(rows) < 2:
        st.info("Not enough historical detector data for a timeline heatmap.")
        return

    df = pd.DataFrame(rows).T
    df = df.ffill(axis=1).fillna(0.0)

    # Dark-friendly colorscale: risk-off red -> dark neutral -> risk-on green.
    dark_colorscale = [
        [0.0, COLORS["risk_off"]],
        [0.35, "#7f1d1d"],
        [0.5, COLORS["background"]],
        [0.65, "#064e3b"],
        [1.0, COLORS["risk_on"]],
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=df.values,
            x=df.columns.strftime("%Y-%m-%d").tolist(),
            y=df.index.tolist(),
            colorscale=dark_colorscale,
            zmin=-1.0,
            zmax=1.0,
            colorbar=dict(
                title=dict(text="Risk score", font=dict(family="JetBrains Mono, monospace", size=10, color=COLORS["muted"])),
                tickfont=dict(family="JetBrains Mono, monospace", size=10, color=COLORS["muted"]),
                tickvals=[-1, -0.5, 0, 0.5, 1],
            ),
            hovertemplate="%{x}<br>%{y}<br>score: %{z:.2f}<extra></extra>",
        )
    )
    apply_house_style(fig, title="3-year detector score alignment", height=80 + 30 * len(rows))
    fig.update_layout(
        xaxis=dict(gridcolor=_GRID_COLOR, title="Date"),
        yaxis=dict(gridcolor=_GRID_COLOR, title=None),
        margin=dict(l=140, r=20, t=40, b=40),
    )
    st.plotly_chart(fig, width="stretch", key="chart_regime_timeline_heatmap")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _render_freshness_footer(
    fred: Mapping[str, Any],
    mkt: Mapping[str, Any],
    spy_df: Optional[pd.DataFrame],
) -> None:
    """Show per-source last-updated timestamps and stale warnings."""
    now = datetime.datetime.now()
    spy_ts = spy_df.attrs.get("_fetched_at") if spy_df is not None and hasattr(spy_df, "attrs") else None
    sources = [
        ("FRED macro data", fred.get("_fetched_at"), 3600),
        ("Yahoo market quotes", mkt.get("_fetched_at"), 900),
        ("SPY/^VIX history", spy_ts, 3600),
    ]

    rows = []
    any_stale = False
    for label, ts, ttl in sources:
        if ts is None:
            rows.append((label, "No timestamp", COLORS["muted"], False))
            continue
        if isinstance(ts, str):
            try:
                ts = pd.to_datetime(ts)
            except Exception:
                rows.append((label, ts, COLORS["muted"], False))
                continue
        age_sec = (now - ts).total_seconds()
        stale = age_sec > 2 * ttl
        any_stale = any_stale or stale
        color = COLORS["risk_off"] if stale else COLORS["risk_on"]
        age_str = f"{int(age_sec // 60)}m ago" if age_sec < 3600 else f"{int(age_sec // 3600)}h ago"
        ts_str = ts.strftime("%Y-%m-%d %H:%M") if isinstance(ts, datetime.datetime) else str(ts)
        rows.append((label, f"{ts_str} ({age_str})", color, stale))

    st.caption("Data freshness")
    cols = st.columns(len(rows))
    for col, (label, text, color, stale) in zip(cols, rows):
        with col:
            st.markdown(
                f'<div style="font-size:12px;color:{COLORS["muted"]};">{label}</div>'
                f'<div style="font-size:13px;font-weight:600;color:{color};">{text}</div>',
                unsafe_allow_html=True,
            )
    if any_stale:
        st.warning("One or more data sources are older than twice their refresh interval. Values may be stale.")


def render_regime_monitor(
    fred: Mapping[str, Any],
    mkt: Mapping[str, Any],
    precomputed: Optional[Tuple[List[RegimeSignal], Dict[str, Dict[str, Any]], Optional[pd.DataFrame], Optional[pd.DataFrame]]] = None,
) -> None:
    """Render the full Regime Monitor tab.

    ``precomputed`` is the output of ``get_regime_consensus`` computed once in
    ``main()`` so the tab renders instantly without re-running detectors.
    """
    st.subheader("Regime Monitor")
    st.caption(
        "Multi-timeframe, multi-detector view of macro/market risk-on / risk-off posture. "
        "All data is fetched once per hour and cached."
    )

    signals, consensus, spy_df, vix_df = precomputed if precomputed is not None else get_regime_consensus(fred, mkt)

    _render_consensus_scoreboard(consensus)
    st.divider()
    _render_detector_matrix(signals)
    st.divider()
    _render_detector_expanders(signals)
    st.divider()
    # _render_timeline_heatmap(signals)
    # st.divider()
    _render_freshness_footer(fred, mkt, spy_df)
