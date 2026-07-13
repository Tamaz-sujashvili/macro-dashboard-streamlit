"""Streamlit UI layer for the regime-detection engine.

Keeps all presentation code separate from the pure-computation
``modules.regime_engine``.
"""

from __future__ import annotations

import datetime
import html
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

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


_LW_SCRIPT = "https://unpkg.com/lightweight-charts@4/dist/lightweight-charts.standalone.production.js"


def render_lw_chart(config: Dict[str, Any], height: int, key: str) -> None:
    """Render a terminal-themed TradingView lightweight-charts iframe.

    The component owns its controls and state, so timeframe/range changes never
    cause a Streamlit rerun. All data is serialized before entering the iframe.
    """
    payload = json.dumps(config, default=str).replace("</", "<\\/")
    dom_id = f"lw-{''.join(ch if ch.isalnum() else '-' for ch in key)}"
    component_html = f"""
    <div id="{dom_id}" data-component-key="{html.escape(key)}" style="height:{height}px;position:relative;background:#0d1117;border:1px solid #1e2733;font-family:'JetBrains Mono',monospace;overflow:hidden"></div>
    <script src="{_LW_SCRIPT}"></script>
    <script>
    const payload = {payload};
    const root = document.getElementById('{dom_id}');
    function boot() {{
      if (!window.LightweightCharts) {{ root.innerHTML='<div style="padding:12px;color:#94a3b8">CHART LIBRARY UNAVAILABLE</div>'; return; }}
      const C = window.LightweightCharts;
      const chart = C.createChart(root, {{
        width: root.clientWidth, height: {height},
        layout: {{ background: {{ color: '#0d1117' }}, textColor: '#94a3b8', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }},
        grid: {{ vertLines: {{ color: 'rgba(148,163,184,0.08)' }}, horzLines: {{ color: 'rgba(148,163,184,0.08)' }} }},
        rightPriceScale: {{ borderColor: '#1e2733' }}, timeScale: {{ borderColor: '#1e2733', timeVisible: true }},
        crosshair: {{ mode: C.CrosshairMode.Normal }}, watermark: {{ visible: false }}, attributionLogo: false,
      }});
      const title = document.createElement('div'); title.textContent = payload.title; title.style.cssText='position:absolute;top:10px;left:12px;color:#e6edf3;font-size:11px;font-weight:700;letter-spacing:.07em;pointer-events:none;z-index:3'; root.appendChild(title);
      const controls = document.createElement('div'); controls.style.cssText='position:absolute;top:31px;left:10px;z-index:4;display:flex;gap:4px'; root.appendChild(controls);
      const readout = document.createElement('div'); readout.style.cssText='position:absolute;top:11px;right:12px;color:#94a3b8;font-size:10px;z-index:4'; root.appendChild(readout);
      const button = (label, fn) => {{ const b=document.createElement('button'); b.textContent=label; b.style.cssText='background:#11161f;color:#94a3b8;border:1px solid #1e2733;border-radius:3px;padding:3px 6px;font:10px JetBrains Mono,monospace;cursor:pointer'; b.onclick=fn; controls.appendChild(b); return b; }};
      let active = payload.defaultTimeframe || '1D'; let main, bands;
      class StateBlockRenderer {{
        constructor() {{ this.data=null; this.options=null; }}
        update(data, options) {{ this.data=data; this.options=options; }}
        draw(target) {{
          target.useMediaCoordinateSpace(scope => {{
            if (!this.data || !this.data.bars.length || this.data.visibleRange===null) return;
            const ctx=scope.context, bars=this.data.bars, height=scope.mediaSize.height;
            const start=Math.max(0, this.data.visibleRange.from), end=Math.min(bars.length, this.data.visibleRange.to);
            for(let i=start;i<end;i++) {{
              const bar=bars[i], point=bar.originalData, half=Math.max(1,this.data.barSpacing/2+.5);
              const alpha=Math.min(.64, .18 + Math.abs(point.value || 0)*.45);
              const color=point.state==='Risk-On' ? `rgba(52,211,153,${{alpha}})` : point.state==='Risk-Off' ? `rgba(248,113,113,${{alpha}})` : `rgba(148,163,184,${{Math.max(.13,alpha*.55)}})`;
              ctx.fillStyle=color; ctx.fillRect(Math.floor(bar.x-half), 8, Math.ceil(half*2), Math.max(1,height-16));
              const prior=i>0 ? bars[i-1].originalData : null;
              if (!prior || prior.state!==point.state) {{
                ctx.fillStyle='rgba(230,237,243,.78)'; ctx.fillRect(Math.round(bar.x-half), 7, 1, Math.max(1,height-14));
                ctx.beginPath(); ctx.arc(bar.x, 8, 2.5, 0, Math.PI*2); ctx.fill();
              }}
            }}
          }});
        }}
      }}
      class StateBlockSeries {{
        constructor() {{ this.rendererImpl=new StateBlockRenderer(); }}
        priceValueBuilder(row) {{ return [1, 0, .5]; }}
        isWhitespace(row) {{ return row.value===undefined; }}
        renderer() {{ return this.rendererImpl; }}
        update(data, options) {{ this.rendererImpl.update(data, options); }}
        defaultOptions() {{ return {{...C.customSeriesDefaultOptions}}; }}
      }}
      function clearSeries() {{ if(main) chart.removeSeries(main); if(bands) chart.removeSeries(bands); }}
      function draw(tf) {{
        active=tf; clearSeries(); const d=payload.datasets[tf];
        if(payload.kind==='candles') {{
          bands=chart.addHistogramSeries({{ priceScaleId:'regime', lastValueVisible:false, priceLineVisible:false, base:0 }});
          chart.priceScale('regime').applyOptions({{ scaleMargins:{{top:0,bottom:0}}, visible:false }}); bands.setData(d.bands);
          main=chart.addCandlestickSeries({{ upColor:'#34d399',downColor:'#f87171',borderUpColor:'#34d399',borderDownColor:'#f87171',wickUpColor:'#34d399',wickDownColor:'#f87171' }}); main.setData(d.candles);
        }} else if(payload.kind==='stateblocks') {{
          main=chart.addCustomSeries(new StateBlockSeries(), {{priceLineVisible:false,lastValueVisible:false}});
          main.setData(d.values);
          chart.priceScale('right').applyOptions({{visible:false, scaleMargins:{{top:.06,bottom:.06}}}});
        }} else {{
          main=chart.addBaselineSeries({{ baseValue:{{type:'price',price:0}}, topLineColor:'#34d399',topFillColor1:'rgba(52,211,153,.22)',topFillColor2:'rgba(52,211,153,.02)',bottomLineColor:'#f87171',bottomFillColor1:'rgba(248,113,113,.02)',bottomFillColor2:'rgba(248,113,113,.22)',lineWidth:2 }});
          main.setData(d.values); main.createPriceLine({{price:.3,color:'rgba(52,211,153,.55)',lineStyle:C.LineStyle.Dotted,lineWidth:1,axisLabelVisible:false}}); main.createPriceLine({{price:-.3,color:'rgba(248,113,113,.55)',lineStyle:C.LineStyle.Dotted,lineWidth:1,axisLabelVisible:false}});
        }}
        chart.timeScale().fitContent();
      }}
      Object.keys(payload.datasets).forEach(tf => button(tf, () => draw(tf)));
      if(payload.kind==='candles') ['1Y','3Y','5Y','ALL'].forEach(range => button(range, () => {{ const data=payload.datasets[active].candles; if(range==='ALL') return chart.timeScale().fitContent(); const n={{'1Y':252,'3Y':756,'5Y':1260}}[range]; const from=data[Math.max(0,data.length-n)]?.time; const to=data[data.length-1]?.time; if(from&&to) chart.timeScale().setVisibleRange({{from,to}}); }}));
      chart.subscribeCrosshairMove(param => {{ if(!param.time || !main) {{readout.textContent='';return;}} const v=param.seriesData.get(main); if(payload.kind==='candles' && v) readout.textContent=`O ${{v.open?.toFixed(2)}} H ${{v.high?.toFixed(2)}} L ${{v.low?.toFixed(2)}} C ${{v.close?.toFixed(2)}} · ${{payload.regimeByTime?.[param.time] || ''}}`; else if(payload.kind==='stateblocks' && v) readout.textContent=`${{v.state || 'Neutral'}} · RISK ${{v.value?.toFixed(2)}}`; else if(v) readout.textContent=`RISK SCORE ${{v.value?.toFixed(2)}}`; }});
      new ResizeObserver(() => chart.applyOptions({{width:root.clientWidth}})).observe(root); draw(active);
      // Lightweight Charts v4 may inject an attribution link despite the
      // attributionLogo option. This terminal embeds no watermark.
      const hideAttribution = () => root.querySelectorAll('a[href*="tradingview"]').forEach(a => a.style.display='none');
      hideAttribution(); setTimeout(hideAttribution, 50);
    }}
    if (window.LightweightCharts) boot(); else window.addEventListener('load', boot, {{once:true}});
    </script>"""
    # ``components.html`` lacks a key= parameter on older Streamlit releases;
    # the namespaced DOM id above keeps the component instances unique.
    components.html(component_html, height=height)


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


def _naive_index(index: pd.Index) -> pd.DatetimeIndex:
    parsed = pd.DatetimeIndex(pd.to_datetime(index, errors="coerce"))
    return parsed.tz_localize(None) if parsed.tz is not None else parsed


def _ohlc_for_timeframe(prices: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    rule = {"1D": None, "1W": "W-FRI", "1M": "MS"}[timeframe]
    if rule is None:
        return prices
    return prices.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def _time_value(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _render_spy_lightweight_chart(spy_df: pd.DataFrame, signals: Sequence[RegimeSignal]) -> None:
    if spy_df is None or spy_df.empty or not {"open", "high", "low", "close"}.issubset(spy_df.columns):
        st.markdown('<div class="mono" style="color:#94a3b8">SPY PRICE HISTORY UNAVAILABLE</div>', unsafe_allow_html=True)
        return
    prices = spy_df[["open", "high", "low", "close"]].copy()
    prices.index = _naive_index(prices.index)
    prices = prices[~prices.index.isna()].sort_index()
    scores = _consensus_history(signals, prices.index).fillna(0.0)
    datasets, labels = {}, {}
    band_colors = {"Risk-On": "rgba(52,211,153,0.10)", "Risk-Off": "rgba(248,113,113,0.10)", "Neutral": "rgba(148,163,184,0.06)"}
    for timeframe in ("1D", "1W", "1M"):
        ohlc = _ohlc_for_timeframe(prices, timeframe)
        sampled_scores = scores.reindex(ohlc.index, method="ffill").fillna(0.0)
        states = np.select([sampled_scores > .3, sampled_scores < -.3], ["Risk-On", "Risk-Off"], default="Neutral")
        candles = [{"time": _time_value(date), "open": float(row.open), "high": float(row.high), "low": float(row.low), "close": float(row.close)} for date, row in ohlc.iterrows()]
        bands = [{"time": _time_value(date), "value": 1, "color": band_colors[state]} for date, state in zip(ohlc.index, states)]
        datasets[timeframe] = {"candles": candles, "bands": bands}
        labels.update({_time_value(date): state for date, state in zip(ohlc.index, states)})
    render_lw_chart({"kind": "candles", "title": "SPY PRICE AND CONSENSUS REGIME", "datasets": datasets, "regimeByTime": labels, "defaultTimeframe": "1D"}, 480, "lw_regime_spy")


def _render_regime_history_ribbon(regime_state: Mapping[str, Any]) -> None:
    history = pd.DataFrame(regime_state.get("history", []))
    if history.empty or not {"date", "regime"}.issubset(history.columns):
        st.caption("MACRO REGIME HISTORY UNAVAILABLE")
        return
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history = history.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    if len(history) < 2:
        st.caption("MACRO REGIME HISTORY AWAITING MULTI-MONTH DATA")
        return
    segments = []
    start = 0
    for pos in range(1, len(history) + 1):
        if pos == len(history) or history.loc[pos, "regime"] != history.loc[start, "regime"]:
            begin = history.loc[start, "date"]
            end = history.loc[pos, "date"] if pos < len(history) else history.loc[pos - 1, "date"] + pd.offsets.MonthBegin(1)
            regime = str(history.loc[start, "regime"])
            duration = max(1, (end - begin).days)
            segments.append((regime, begin, end, duration))
            start = pos
    total = sum(item[3] for item in segments)
    # The state is deliberately encoded with restrained terminal textures rather
    # than a saturated categorical palette. Labels and tooltips carry the meaning.
    patterns = {
        "Goldilocks": "#121820",
        "Reflation": "repeating-linear-gradient(135deg,rgba(148,163,184,.18) 0 1px,transparent 1px 7px),#121820",
        "Stagflation": "repeating-linear-gradient(0deg,rgba(148,163,184,.16) 0 1px,transparent 1px 6px),#121820",
        "Recession": "radial-gradient(rgba(148,163,184,.20) 1px,transparent 1px),#121820",
    }
    def _block(regime: str, begin: pd.Timestamp, end: pd.Timestamp, duration: int) -> str:
        label = ""
        if duration / total >= 0.075:
            label = (
                "<span style='font:700 9px JetBrains Mono,monospace;color:#9aa9b9;"
                f"letter-spacing:.06em;white-space:nowrap'>{html.escape(regime.upper())}</span>"
            )
        return (
            f'<div title="{html.escape(regime)} · {begin:%Y-%m} to {end:%Y-%m}" '
            f'style="flex:{duration};min-width:3px;background:{patterns.get(regime, "#121820")};'
            "border-left:1px solid #3a4654;display:flex;align-items:center;"
            f'justify-content:center;overflow:hidden">{label}</div>'
        )

    blocks = "".join(_block(regime, begin, end, duration) for regime, begin, end, duration in segments)
    years = sorted({date.year for date in history["date"]})
    labels = "".join(f'<span>{year}</span>' for year in years[::max(1, len(years)//6)])
    st.markdown(f'''<div style="margin:4px 0 18px"><div style="font:700 11px JetBrains Mono,monospace;color:#e6edf3;letter-spacing:.07em;margin-bottom:8px">MACRO REGIME HISTORY</div><div style="height:44px;display:flex;border:1px solid #293241;border-radius:3px;overflow:hidden;background:#0d1117">{blocks}</div><div style="display:flex;justify-content:space-between;font:10px JetBrains Mono,monospace;color:#94a3b8;margin-top:5px">{labels}</div></div>''', unsafe_allow_html=True)


def _render_detector_lightweight_charts(signals: Sequence[RegimeSignal]) -> None:
    st.subheader("Detector History")
    unavailable: List[RegimeSignal] = []
    for sig in signals:
        history = sig.history.copy() if sig.history is not None else pd.DataFrame()
        if history.empty or not {"date", "risk_score"}.issubset(history.columns):
            unavailable.append(sig)
            continue
        history["date"] = pd.to_datetime(history["date"], errors="coerce")
        history["risk_score"] = pd.to_numeric(history["risk_score"], errors="coerce")
        history = history.dropna(subset=["date", "risk_score"]).sort_values("date").drop_duplicates("date", keep="last")
        if len(history) < 2:
            unavailable.append(sig)
            continue
        def _state(score: float) -> str:
            if score > 0.3:
                return "Risk-On"
            if score < -0.3:
                return "Risk-Off"
            return "Neutral"

        values = [
            {"time": _time_value(row.date), "value": float(row.risk_score), "state": _state(float(row.risk_score))}
            for row in history.itertuples()
        ]
        render_lw_chart(
            {
                "kind": "stateblocks",
                "title": f"{sig.detector_name.upper()} · {sig.timeframe} STATE HISTORY",
                "datasets": {"HISTORY": {"values": values}},
                "defaultTimeframe": "HISTORY",
            },
            132,
            f"lw_detector_{sig.detector_name.lower()}_{sig.timeframe.lower()}",
        )
    if unavailable:
        st.caption("CURRENT-ONLY / UNAVAILABLE DETECTORS")
        cols = st.columns(min(3, len(unavailable)))
        for col, sig in zip(cols * ((len(unavailable) + len(cols) - 1) // len(cols)), unavailable):
            with col:
                if sig.state == "No Data":
                    st.markdown(f'<div style="border:1px solid #1e2733;border-left:2px solid #94a3b8;padding:8px;font:11px JetBrains Mono,monospace;color:#94a3b8">{sig.detector_name.upper()} · {sig.timeframe}<br>UNAVAILABLE</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="border:1px solid #1e2733;border-left:2px solid {_score_color(sig.risk_score)};padding:8px;font:11px JetBrains Mono,monospace;color:#e6edf3">{sig.detector_name.upper()} · {sig.timeframe}<br>{sig.state.upper()} · {sig.risk_score:+.2f}</div>', unsafe_allow_html=True)


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
        agreement_text = "1 detector" if n == 1 else f"agreement {fmt_pct(agreement * 100, 0)} · {n} detectors"
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
                f'{agreement_text}</div></div>',
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
    _render_regime_history_ribbon(macro_state)
    _render_spy_lightweight_chart(spy_df, signals)
    st.divider()
    _render_detector_matrix(signals)
    st.divider()
    _render_breadth_panel(signals)
    st.divider()
    _render_detector_lightweight_charts(signals)
    st.divider()
    _render_timeline_heatmap(signals)
    st.divider()
    _render_freshness_footer(fred, mkt, spy_df)
