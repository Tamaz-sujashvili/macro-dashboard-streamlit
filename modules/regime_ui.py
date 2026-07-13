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
from modules.breadth import breadth_detector, compute_breadth, fetch_polygon_grouped, load_dma_snapshot, update_breadth_history
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

REGIME_COLORS = {
    "Goldilocks": "#34d399",
    "Reflation": "#fbbf24",
    "Stagflation": "#f87171",
    "Recession": "#94a3b8",
}

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
    ("Breadth", "Broad"): COLORS["risk_on"],
    ("Breadth", "Narrow"): COLORS["neutral"],
    ("Breadth", "Deteriorating"): COLORS["risk_off"],
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


def make_regime_quadrant_chart(regime_state: Mapping[str, Any]) -> go.Figure:
    """Terminal-styled credit/inflation macro quadrant."""
    credit_roc = regime_state.get("credit_roc")
    inflation_roc = regime_state.get("inflation_roc")
    fig = go.Figure()
    max_abs = max(abs(credit_roc or 0), abs(inflation_roc or 0), 25)
    axis_limit = round(max_abs * 1.25, 0)
    quadrants = [
        (-axis_limit, 0, 0, axis_limit, "Reflation", "left", "top"),
        (0, axis_limit, 0, axis_limit, "Stagflation", "right", "top"),
        (-axis_limit, 0, -axis_limit, 0, "Goldilocks", "left", "bottom"),
        (0, axis_limit, -axis_limit, 0, "Recession", "right", "bottom"),
    ]
    for x0, x1, y0, y1, label, xanchor, yanchor in quadrants:
        color = REGIME_COLORS[label]
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, line=dict(width=0), fillcolor=color, opacity=0.10, layer="below")
        fig.add_annotation(x=x0 + 6 if xanchor == "left" else x1 - 6, y=y1 - 6 if yanchor == "top" else y0 + 6,
                           text=label.upper(), showarrow=False, font=dict(family="JetBrains Mono, monospace", size=10, color=color), xanchor=xanchor, yanchor=yanchor)
    fig.add_hline(y=0, line_dash="dot", line_color=COLORS["border"], line_width=1)
    fig.add_vline(x=0, line_dash="dot", line_color=COLORS["border"], line_width=1)
    if credit_roc is not None and inflation_roc is not None:
        regime = str(regime_state.get("regime", "Current"))
        fig.add_trace(go.Scatter(x=[credit_roc], y=[inflation_roc], mode="markers+text", name="Current",
            marker=dict(size=16, color=REGIME_COLORS.get(regime, COLORS["accent"]), line=dict(color=COLORS["text"], width=1)),
            text=[regime.upper()], textposition="top center", hovertemplate="Credit ROC: %{x:.1f} bp<br>Inflation ROC: %{y:.1f} bp<extra></extra>"))
    apply_house_style(fig, title="Macro Regime Quadrant", height=350)
    fig.update_layout(showlegend=False, margin=dict(l=30, r=20, t=40, b=30))
    fig.update_xaxes(title="Credit ROC (bp)", range=[-axis_limit, axis_limit], zeroline=False)
    fig.update_yaxes(title="Inflation ROC (bp)", range=[-axis_limit, axis_limit], zeroline=False)
    return fig


def make_regime_history_chart(regime_state: Mapping[str, Any]) -> go.Figure:
    """Full-width colored macro-regime history ribbon."""
    history = regime_state.get("history", [])
    if isinstance(history, pd.DataFrame):
        df = history.copy()
    else:
        df = pd.DataFrame(history)
    fig = go.Figure()
    if df.empty or "date" not in df or "regime" not in df:
        apply_house_style(fig, title="Macro Regime History", height=120)
        fig.update_layout(margin=dict(l=10, r=10, t=35, b=20))
        return fig
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    start = 0
    for index in range(1, len(df) + 1):
        if index == len(df) or df.loc[index, "regime"] != df.loc[start, "regime"]:
            regime = str(df.loc[start, "regime"])
            begin, end = df.loc[start, "date"], df.loc[index - 1, "date"] + pd.offsets.MonthBegin(1)
            color = REGIME_COLORS.get(regime, COLORS["muted"])
            fig.add_vrect(x0=begin, x1=end, fillcolor=color, opacity=0.82, line_width=0, layer="below")
            midpoint = begin + (end - begin) / 2
            fig.add_trace(go.Scatter(x=[midpoint], y=[0.5], mode="markers", marker=dict(size=18, color=color, opacity=0.01),
                                     hovertemplate=f"{regime}<br>{begin:%Y-%m} to {end:%Y-%m}<extra></extra>", showlegend=False))
            start = index
    apply_house_style(fig, title="Macro Regime History", height=120)
    fig.update_layout(margin=dict(l=10, r=10, t=35, b=20), showlegend=False)
    fig.update_xaxes(showgrid=False, tickformat="%Y-%m")
    fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False, range=[0, 1])
    return fig


def _consensus_history(signals: Sequence[RegimeSignal], index: pd.DatetimeIndex) -> pd.Series:
    """Forward-fill each detector's causal score and form a daily consensus."""
    series = []
    for signal in signals:
        history = signal.history
        if history is None or history.empty or not {"date", "risk_score"}.issubset(history.columns):
            continue
        values = history[["date", "risk_score"]].copy()
        values["date"] = pd.to_datetime(values["date"], errors="coerce")
        if getattr(values["date"].dt, "tz", None) is not None:
            values["date"] = values["date"].dt.tz_localize(None)
        values = values.dropna().drop_duplicates("date", keep="last").set_index("date")["risk_score"]
        series.append(values.reindex(index, method="ffill"))
    return pd.concat(series, axis=1).mean(axis=1) if series else pd.Series(0.0, index=index)


def make_spy_regime_chart(spy_df: pd.DataFrame, signals: Sequence[RegimeSignal]) -> go.Figure:
    """TradingView-style SPY close with full-height consensus-regime bands."""
    fig = go.Figure()
    if spy_df is None or spy_df.empty or "close" not in spy_df:
        apply_house_style(fig, title="SPY Price and Consensus Regime", height=420)
        return fig
    prices = spy_df.copy()
    prices.index = pd.to_datetime(prices.index)
    if getattr(prices.index, "tz", None) is not None:
        prices.index = prices.index.tz_localize(None)
    prices = prices.sort_index()
    scores = _consensus_history(signals, prices.index)
    states = pd.Series(np.select([scores > 0.3, scores < -0.3], ["Risk-On", "Risk-Off"], default="Neutral"), index=prices.index)
    colors = {"Risk-On": "rgba(52,211,153,0.10)", "Risk-Off": "rgba(248,113,113,0.10)", "Neutral": "rgba(148,163,184,0.06)"}
    start = 0
    for i in range(1, len(states) + 1):
        if i == len(states) or states.iloc[i] != states.iloc[start]:
            fig.add_vrect(x0=states.index[start], x1=states.index[i - 1] + pd.Timedelta(days=1), fillcolor=colors[states.iloc[start]], line_width=0, layer="below")
            start = i
    fig.add_trace(go.Scatter(x=prices.index, y=prices["close"], name="SPY close", line=dict(color=COLORS["accent"], width=1.8), hovertemplate="%{x|%Y-%m-%d}<br>SPY %{y:,.2f}<extra></extra>"))
    for label, color in [("Risk-On", COLORS["risk_on"]), ("Neutral", COLORS["muted"]), ("Risk-Off", COLORS["risk_off"])]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=label, marker=dict(size=8, color=color)))
    apply_house_style(fig, title="SPY Price and Consensus Regime", height=420)
    fig.update_layout(legend=dict(orientation="h", y=1.01, x=1, xanchor="right"), margin=dict(l=40, r=20, t=45, b=30))
    fig.update_yaxes(title="SPY")
    return fig


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
    breadth = update_breadth_history(compute_breadth(fetch_polygon_grouped(), load_dma_snapshot()))
    signals.append(breadth_detector(breadth))
    consensus = compute_consensus(signals)
    return signals, consensus, spy_df, vix_df


def _render_breadth_panel(signals: Sequence[RegimeSignal]) -> None:
    """Terminal breadth panel. Missing Polygon/DMA data remains non-fatal."""
    breadth = next((s for s in signals if s.detector_name == "Breadth"), None)
    st.subheader("BREADTH")
    if breadth is None or breadth.state == "No Data":
        st.caption("Polygon breadth awaiting cached close and 200DMA snapshot.")
        return
    hist = breadth.history
    pct = float(hist["pct_above_200"].dropna().iloc[-1]) if "pct_above_200" in hist and hist["pct_above_200"].notna().any() else None
    ad = float(hist["ad_line"].dropna().iloc[-1]) if "ad_line" in hist and hist["ad_line"].notna().any() else None
    cols = st.columns(3)
    cols[0].metric("ADVANCE / DECLINE", f"{ad:+.0f}" if ad is not None else "N/A")
    cols[1].metric("ABOVE 200DMA", fmt_pct(pct) if pct is not None else "N/A")
    cols[2].metric("STATE", breadth.state)
    if not hist.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist["date"], y=hist["ad_line"], name="A/D line", line=dict(color=COLORS["accent"])))
        if pct is not None:
            fig.add_trace(go.Scatter(x=hist["date"], y=hist["pct_above_200"], name="% > 200DMA", yaxis="y2", line=dict(color=COLORS["risk_on"])))
            fig.add_hline(y=40, line_dash="dot", line_color=COLORS["risk_off"], yref="y2")
            fig.add_hline(y=60, line_dash="dot", line_color=COLORS["risk_on"], yref="y2")
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="% > 200DMA"))
        apply_house_style(fig, title="Breadth", height=260)
        st.plotly_chart(fig, width="stretch", key="chart_regime_breadth")


def _macro_regime_state(signals: Sequence[RegimeSignal]) -> Dict[str, Any]:
    macro = next((signal for signal in signals if signal.detector_name == "MacroQuadrant"), None)
    if macro is None:
        return {"history": []}
    history = macro.history.copy() if macro.history is not None else pd.DataFrame()
    if history.empty:
        return {"regime": macro.state, "color": macro.color, "history": []}
    history["regime"] = history.get("state", macro.state)
    latest = history.iloc[-1]
    return {
        "regime": macro.state,
        "color": macro.color,
        "credit_roc": latest.get("credit_roc"),
        "inflation_roc": latest.get("inflation_roc"),
        "history": history.to_dict("records"),
    }


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


def _render_detector_history_charts(signals: Sequence[RegimeSignal]) -> None:
    """Render each detector's historical risk score as a standalone chart.

    These charts deliberately live outside expanders.  Streamlit had a
    rendering bug where Plotly figures nested inside expanders could leave
    later tabs blank after a rerun.
    """
    st.subheader("Detector History")
    chartable: List[tuple[RegimeSignal, pd.DataFrame]] = []

    for sig in signals:
        history = sig.history.copy()
        if history.empty or not {"date", "risk_score"}.issubset(history.columns):
            continue
        history["date"] = pd.to_datetime(history["date"], errors="coerce")
        history["risk_score"] = pd.to_numeric(history["risk_score"], errors="coerce")
        history = history.dropna(subset=["date", "risk_score"]).sort_values("date")
        if not history.empty:
            chartable.append((sig, history))

    if not chartable:
        st.info("Historical detector series are not available yet.")
        return

    for sig, history in chartable:
        fig = go.Figure()
        hover_state = history["state"].astype(str) if "state" in history else None
        fig.add_trace(
            go.Scatter(
                x=history["date"],
                y=history["risk_score"],
                mode="lines",
                name="Risk score",
                line=dict(color=sig.color or _score_color(sig.risk_score), width=2),
                customdata=hover_state,
                hovertemplate=(
                    "%{x|%Y-%m-%d}<br>Risk score: %{y:.2f}<br>State: %{customdata}<extra></extra>"
                    if hover_state is not None
                    else "%{x|%Y-%m-%d}<br>Risk score: %{y:.2f}<extra></extra>"
                ),
            )
        )
        fig.add_hline(y=0, line_color=_GRID_COLOR, line_dash="dot", line_width=1)
        fig.add_hline(y=0.3, line_color=_rgba(COLORS["risk_on"], 0.45), line_dash="dot", line_width=1)
        fig.add_hline(y=-0.3, line_color=_rgba(COLORS["risk_off"], 0.45), line_dash="dot", line_width=1)
        apply_house_style(fig, title=f"{sig.detector_name} · {sig.timeframe} risk score", height=260)
        fig.update_layout(
            yaxis=dict(range=[-1.05, 1.05], title="Risk score"),
            xaxis=dict(title=None),
            showlegend=False,
            margin=dict(l=48, r=18, t=42, b=38),
        )
        chart_key = f"chart_regime_history_{sig.detector_name.lower()}_{sig.timeframe.lower()}"
        st.plotly_chart(fig, width="stretch", key=chart_key)

    # Detectors without a historical series still get a visible current read.
    history_names = {(sig.detector_name, sig.timeframe) for sig, _ in chartable}
    no_history = [sig for sig in signals if (sig.detector_name, sig.timeframe) not in history_names]
    if no_history:
        st.caption("Current-only detectors")
        cols = st.columns(min(3, len(no_history)))
        for col, sig in zip(cols * ((len(no_history) + len(cols) - 1) // len(cols)), no_history):
            with col:
                st.metric(
                    f"{sig.detector_name} · {sig.timeframe}",
                    sig.state,
                    f"score {sig.risk_score:+.2f} · confidence {sig.confidence:.0%}",
                )


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
    spy_source = spy_df.attrs.get("source", "yfinance") if spy_df is not None and hasattr(spy_df, "attrs") else "yfinance"
    sources = [
        ("FRED macro data", fred.get("_fetched_at"), 3600),
        ("Yahoo market quotes", mkt.get("_fetched_at"), 900),
        (f"SPY history ({spy_source})", spy_ts, 3600),
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
    macro_state = _macro_regime_state(signals)
    st.plotly_chart(make_regime_history_chart(macro_state), width="stretch", key="chart_regime_history_ribbon")
    st.plotly_chart(make_spy_regime_chart(spy_df, signals), width="stretch", key="chart_regime_spy_bands")
    st.plotly_chart(make_regime_quadrant_chart(macro_state), width="stretch", key="chart_regime_monitor_quadrant")
    st.divider()
    _render_detector_matrix(signals)
    st.divider()
    _render_breadth_panel(signals)
    st.divider()
    _render_detector_history_charts(signals)
    st.divider()
    _render_timeline_heatmap(signals)
    st.divider()
    _render_freshness_footer(fred, mkt, spy_df)
