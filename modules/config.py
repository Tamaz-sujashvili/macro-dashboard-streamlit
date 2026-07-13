"""Shared configuration, styling, and formatting helpers for the macro dashboard.

Centralizes magic numbers used across recession alerts, valuation, labour,
inflation and trend assumptions, plus the shared dark visual identity.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

import plotly.graph_objects as go


THRESHOLDS = {
    "recession_alert": 20,       # probability (%) that triggers a recession alert
    "cape_avg": 25,              # long-run average CAPE ratio used for normalisation
    "unemployment_natural": 4.0, # assumed natural rate of unemployment (%)
    "cpi_target": 2.0,           # central bank CPI inflation target (%)
    "gdp_trend": 2.0,            # potential/trend real GDP growth (%)
}


COLORS = {
    "risk_on": "#34d399",
    "risk_off": "#f87171",
    "neutral": "#fbbf24",
    "accent": "#22d3ee",
    "muted": "#8b98a9",
    "background": "#0a0e14",
    "panel": "#11161f",
    "border": "#1e2733",
    "text": "#e6edf3",
}


PLOTLY_LAYOUT = {
    "template": "plotly_dark",
    "font": {"family": "JetBrains Mono, monospace", "color": COLORS["text"], "size": 12},
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 40, "r": 20, "t": 40, "b": 30},
    "hovermode": "x unified",
    "colorway": ["#22d3ee", "#34d399", "#f87171", "#fbbf24", "#8b98a9", "#60a5fa"],
    "xaxis": {
        "gridcolor": "#1e2733",
        "zerolinecolor": "#1e2733",
        "griddash": "dot",
        "showline": True,
        "linecolor": "#1e2733",
        "linewidth": 1,
        "tickfont": {"family": "JetBrains Mono, monospace", "color": COLORS["muted"], "size": 10},
    },
    "yaxis": {
        "gridcolor": "#1e2733",
        "zerolinecolor": "#1e2733",
        "griddash": "dot",
        "showline": True,
        "linecolor": "#1e2733",
        "linewidth": 1,
        "tickfont": {"family": "JetBrains Mono, monospace", "color": COLORS["muted"], "size": 10},
    },
    "legend": {
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "right",
        "x": 1,
        "font": {"family": "JetBrains Mono, monospace", "color": COLORS["muted"], "size": 10},
        "bgcolor": "rgba(0,0,0,0)",
        "bordercolor": "rgba(0,0,0,0)",
    },
}


def apply_house_style(fig: go.Figure, title: Optional[str] = None, height: Optional[int] = None) -> go.Figure:
    """Apply the shared terminal-futuristic style to a Plotly figure.

    This is the final styling step for every chart. It overrides any
    conflicting template, background, or font settings set by callers.
    """
    layout = deepcopy(PLOTLY_LAYOUT)

    if title is not None:
        layout["title"] = {
            "text": title.upper(),
            "x": 0.0,
            "xanchor": "left",
            "font": {
                "family": "JetBrains Mono, monospace",
                "size": 11,
                "color": COLORS["muted"],
            },
        }
    else:
        # Plotly.js can render an empty/missing title object as the literal string
        # "undefined". If the caller did not set a title, force it to a single
        # space so the title area collapses cleanly. If the caller already set
        # one, preserve it.
        existing_title = getattr(fig.layout.title, "text", None)
        if not existing_title:
            layout["title"] = {"text": " "}

    if height is not None:
        layout["height"] = height

    # Force transparent backgrounds and the dark template regardless of caller.
    layout["template"] = "plotly_dark"
    layout["paper_bgcolor"] = "rgba(0,0,0,0)"
    layout["plot_bgcolor"] = "rgba(0,0,0,0)"

    fig.update_layout(layout)

    # Ensure axis styling is applied even if traces added custom axes.
    fig.update_xaxes(
        gridcolor="#1e2733",
        zerolinecolor="#1e2733",
        griddash="dot",
        showline=True,
        linecolor="#1e2733",
        linewidth=1,
        tickfont={"family": "JetBrains Mono, monospace", "color": COLORS["muted"], "size": 10},
    )
    fig.update_yaxes(
        gridcolor="#1e2733",
        zerolinecolor="#1e2733",
        griddash="dot",
        showline=True,
        linecolor="#1e2733",
        linewidth=1,
        tickfont={"family": "JetBrains Mono, monospace", "color": COLORS["muted"], "size": 10},
    )

    return fig


def fmt_pct(value: Optional[float], decimals: int = 1, signed: bool = False) -> str:
    """Format a percentage value (already in percent units, e.g. 3.2)."""
    if value is None:
        return "N/A"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def fmt_bp(value: Optional[float]) -> str:
    """Format a basis-point value."""
    if value is None:
        return "N/A"
    return f"{value:.0f} bp"


def fmt_dollar(value: Optional[float], decimals: int = 0) -> str:
    """Format a large dollar amount with thousands separators."""
    if value is None:
        return "N/A"
    return f"${value:,.{decimals}f}"
