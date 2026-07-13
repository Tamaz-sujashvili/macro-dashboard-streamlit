"""
Interactive Finviz-style stock market treemap (heatmap) using:
  - OpenBB Platform SDK v4.x (`openbb`, imported as `from openbb import obb`)
  - Plotly Express (`plotly`)

This script supports two data sources:
  1) --source sdk : calls OpenBB locally in Python (requires `openbb` installed in this env)
  2) --source api : calls your local OpenBB API server over HTTP (recommended if you've already
                    configured provider API keys in the OpenBB app/server)

Key idea for "more real-time":
  - Universe metadata (sector/industry/market cap) changes slowly -> refresh rarely.
  - Quotes / % change change constantly -> refresh frequently and recolor the treemap.

Install (example)
  pip install "openbb>=4" plotly pandas requests

Live mode (optional)
  pip install dash

Run (static HTML + opens a browser window)
  python3 stock_treemap_openbb_plotly.py --provider finviz
  python3 stock_treemap_openbb_plotly.py --provider fmp

Run (LIVE dashboard, updates quotes every 30s; best with OpenBB API + stored keys)
  python3 stock_treemap_openbb_plotly.py --source api --universe-provider finviz --quote-provider fmp --live
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Iterable, Optional

import pandas as pd
import plotly.express as px
import requests


def _pick_column(df: pd.DataFrame, candidates: Iterable[str]) -> str:
    """Return the first matching column name from candidates (case-insensitive)."""
    cols_by_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        hit = cols_by_lower.get(cand.lower())
        if hit is not None:
            return hit
    raise KeyError(
        f"None of these columns were found: {list(candidates)}. "
        f"Available columns: {list(df.columns)}"
    )


_MC_MULTIPLIERS = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _parse_market_cap_usd(x) -> float:
    """
    Parse market cap into a float USD value.
    Handles numeric values and common human formats like '1.23T', '550B', '$12.4B'.
    """
    if pd.isna(x):
        return float("nan")
    if isinstance(x, (int, float)):
        return float(x)

    s = str(x).strip().upper()
    if s in {"", "N/A", "NA", "NONE", "NULL", "-"}:
        return float("nan")

    s = s.replace("$", "").replace(",", "")
    m = re.match(r"^(-?\d+(?:\.\d+)?)([KMBT])?$", s)
    if not m:
        return float("nan")

    val = float(m.group(1))
    suffix = m.group(2)
    if suffix:
        val *= _MC_MULTIPLIERS[suffix]
    return val


def _parse_percent(x) -> float:
    """Parse percent strings like '-2.34%' or numeric values into float percentage points."""
    if pd.isna(x):
        return float("nan")
    if isinstance(x, (int, float)):
        return float(x)

    s = str(x).strip()
    if s in {"", "N/A", "NA", "NONE", "NULL", "-"}:
        return float("nan")
    s = s.replace("%", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def fetch_screener_df_sdk(*, provider: str, limit: int) -> pd.DataFrame:
    """Fetch screener data via OpenBB SDK and return a DataFrame."""
    try:
        from openbb import obb  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "OpenBB is not installed (or failed to import). Install with:\n"
            "  pip install \"openbb>=4\"\n"
            "Then rerun, or use --source api to call your OpenBB API server."
        ) from e

    res = obb.equity.screener(provider=provider, limit=limit)
    df = res.to_df()
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    return df


def _http_get_json(url: str, *, params: dict, headers: dict, timeout_s: int = 30) -> dict:
    r = requests.get(url, params=params, headers=headers, timeout=timeout_s)
    r.raise_for_status()
    return r.json()


def _openbb_api_discover_paths(base_url: str) -> dict:
    """
    Discover OpenBB API paths for equity screener and quote by reading openapi.json.
    This makes the script resilient to prefixes like `/api` or `/api/v1`.
    """
    base = base_url.rstrip("/")
    schema = _http_get_json(f"{base}/openapi.json", params={}, headers={})
    paths = schema.get("paths", {}) or {}

    def find_path(needle: str) -> tuple[str, str]:
        for p, methods in paths.items():
            if needle in p:
                if "get" in methods:
                    return p, "get"
                for m in ("post", "put", "patch", "delete"):
                    if m in methods:
                        return p, m
        raise KeyError(f"Could not find an OpenBB API path containing '{needle}'.")

    screener_path, screener_method = find_path("/equity/screener")
    quote_path, quote_method = find_path("/equity/price/quote")
    return {
        "screener": {"path": screener_path, "method": screener_method},
        "quote": {"path": quote_path, "method": quote_method},
    }


def _openbb_api_extract_results(payload) -> pd.DataFrame:
    """Normalize common OpenBB API response shapes into a DataFrame."""
    if isinstance(payload, dict) and "results" in payload:
        payload = payload["results"]
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], list):
        payload = payload["data"]
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        return pd.DataFrame([payload])
    return pd.DataFrame(payload)


def fetch_screener_df_api(*, base_url: str, provider: str, limit: int, auth_token: str | None) -> pd.DataFrame:
    """Fetch screener via the local OpenBB API (HTTP)."""
    discovered = _openbb_api_discover_paths(base_url)
    path = discovered["screener"]["path"]
    method = discovered["screener"]["method"]

    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    url = f"{base_url.rstrip('/')}{path}"
    params = {"provider": provider, "limit": limit}
    r = requests.request(method.upper(), url, params=params, headers=headers, timeout=60)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        body = (r.text or "").strip()
        raise RuntimeError(
            "OpenBB API screener request failed.\n"
            f"  URL: {r.url}\n"
            f"  Status: {r.status_code}\n"
            f"  Body: {body[:2000]}\n\n"
            "Common fixes:\n"
            "  - If `fmp` fails with 502, try `--universe-provider finviz --quote-provider fmp`.\n"
            "  - Reduce `--limit` (timeouts/backends can struggle with huge screener pulls).\n"
            "  - Verify `fmp_api_key` is configured for the *OpenBB API server* environment.\n"
        ) from e
    return _openbb_api_extract_results(r.json())


def fetch_quotes_df_api(
    *,
    base_url: str,
    provider: str,
    symbols: list[str],
    auth_token: str | None,
    batch_size: int = 200,
) -> pd.DataFrame:
    """Fetch latest quotes in batches via the OpenBB API."""
    discovered = _openbb_api_discover_paths(base_url)
    path = discovered["quote"]["path"]
    method = discovered["quote"]["method"]

    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    url = f"{base_url.rstrip('/')}{path}"
    frames: list[pd.DataFrame] = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        params = {"provider": provider, "symbol": ",".join(batch)}
        r = requests.request(method.upper(), url, params=params, headers=headers, timeout=60)
        r.raise_for_status()
        frames.append(_openbb_api_extract_results(r.json()))

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def fetch_quotes_df_fmp_http(*, api_key: str, symbols: list[str], batch_size: int = 200) -> pd.DataFrame:
    """
    Direct FMP fallback for "real-time-ish" quotes (bypasses OpenBB).

    Endpoint:
      https://financialmodelingprep.com/api/v3/quote/{symbols}?apikey=...

    Returns a DataFrame containing at least:
      symbol, change_percent
    """
    if not api_key:
        raise ValueError("Missing FMP API key.")
    base = "https://financialmodelingprep.com/api/v3/quote"

    frames: list[pd.DataFrame] = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        url = f"{base}/" + ",".join(batch)
        r = requests.get(url, params={"apikey": api_key}, timeout=30)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data if isinstance(data, list) else [])
        if not df.empty:
            sym_col = _pick_column(df, ["symbol"])
            # FMP tends to return `changesPercentage` as a percent value like -1.23 (not -0.0123).
            chg_col = _pick_column(df, ["changesPercentage", "changePercent", "change_percent"])
            frames.append(
                pd.DataFrame(
                    {
                        "symbol": df[sym_col].astype(str).str.upper().str.strip(),
                        "change_percent": df[chg_col].map(_parse_percent),
                    }
                )
            )

    if not frames:
        return pd.DataFrame(columns=["symbol", "change_percent"])
    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="last")
    return out


def fetch_quote_df_alpha_vantage_http(*, api_key: str, symbols: list[str]) -> pd.DataFrame:
    """
    Direct Alpha Vantage fallback (very rate limited for many symbols).

    Endpoint (per symbol):
      https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=...&apikey=...

    This is only practical for small symbol lists; otherwise you will hit throttling.
    """
    if not api_key:
        raise ValueError("Missing Alpha Vantage API key.")
    if len(symbols) > 20:
        raise RuntimeError(
            "Alpha Vantage GLOBAL_QUOTE is rate-limited; refusing to fetch >20 symbols. "
            "Use FMP for bulk quotes."
        )
    base = "https://www.alphavantage.co/query"
    rows: list[dict] = []
    for s in symbols:
        r = requests.get(
            base,
            params={"function": "GLOBAL_QUOTE", "symbol": s, "apikey": api_key},
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json() or {}
        gq = payload.get("Global Quote", {}) or {}
        # `10. change percent` looks like '-1.23%'
        chg = gq.get("10. change percent")
        rows.append({"symbol": s, "change_percent": _parse_percent(chg)})
    return pd.DataFrame(rows)


def clean_and_filter(df_raw: pd.DataFrame, *, min_market_cap_usd: float) -> pd.DataFrame:
    """
    Normalize column names/values and filter to large/mega caps.

    Output columns:
      symbol, sector, industry, market_cap, change_percent, root
    """
    df = df_raw.copy()

    symbol_col = _pick_column(df, ["symbol", "ticker"])
    sector_col = _pick_column(df, ["sector"])
    industry_col = _pick_column(df, ["industry", "subindustry", "sub_industry"])
    market_cap_col = _pick_column(
        df,
        ["market_cap", "marketcap", "mktcap", "mkt_cap", "marketCapitalization", "marketcapitalization"],
    )
    change_col = _pick_column(
        df,
        [
            "change_percent",
            "change",
            "changePct",
            "change_pct",
            "changesPercentage",
            "changes_percentage",
        ],
    )

    out = pd.DataFrame(
        {
            "symbol": df[symbol_col].astype(str).str.upper().str.strip(),
            "sector": df[sector_col],
            "industry": df[industry_col],
            "market_cap": df[market_cap_col].map(_parse_market_cap_usd),
            "change_percent": df[change_col].map(_parse_percent),
        }
    )

    out = out.dropna(subset=["market_cap", "sector", "industry", "change_percent"])
    out = out[out["market_cap"] > float(min_market_cap_usd)]

    out["root"] = "US Stock Market"
    out["sector"] = out["sector"].astype(str).str.strip()
    out["industry"] = out["industry"].astype(str).str.strip()
    return out


def build_treemap(df: pd.DataFrame, *, title: str):
    """Build Plotly Express treemap sized by market cap and colored by daily % change."""
    fig = px.treemap(
        df,
        path=["root", "sector", "industry", "symbol"],
        values="market_cap",
        color="change_percent",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        custom_data=["sector", "industry", "symbol"],
    )

    fig.update_traces(
        texttemplate="%{label}<br>%{color:+.2f}%",
        textposition="middle center",
        hovertemplate=(
            "Ticker: <b>%{label}</b><br>"
            "Sector: %{customdata[0]}<br>"
            "Industry: %{customdata[1]}<br>"
            "Change: %{color:+.2f}%<extra></extra>"
        ),
    )

    fig.update_layout(
        title=title,
        template="plotly_white",
        margin=dict(l=10, r=10, t=60, b=10),
        coloraxis_colorbar=dict(title="Daily %"),
        uniformtext=dict(minsize=10, mode="hide"),
    )

    return fig


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an interactive Finviz-style stock market treemap using OpenBB v4 + Plotly."
    )
    parser.add_argument(
        "--source",
        default="sdk",
        choices=["sdk", "api"],
        help="Fetch from OpenBB SDK (sdk) or from OpenBB API over HTTP (api).",
    )
    parser.add_argument(
        "--openbb-api-url",
        default="http://127.0.0.1:6900",
        help="Base URL for OpenBB API (only used when --source api).",
    )
    parser.add_argument(
        "--openbb-api-token",
        default=None,
        help="Optional bearer token for OpenBB API (if protected).",
    )

    parser.add_argument(
        "--provider",
        default="finviz",
        choices=["finviz", "fmp"],
        help="Default provider for universe + quotes (can be overridden).",
    )
    parser.add_argument(
        "--universe-provider",
        default=None,
        choices=["finviz", "fmp"],
        help="Provider for the universe (sector/industry/market cap). Defaults to --provider.",
    )
    parser.add_argument(
        "--quote-provider",
        default=None,
        choices=["finviz", "fmp"],
        help="Provider for quotes (% change). Defaults to --provider.",
    )
    parser.add_argument(
        "--fmp-api-key",
        default=None,
        help="Optional FMP API key for direct HTTP quote fallback (or set env var FMP_API_KEY).",
    )
    parser.add_argument(
        "--alpha-vantage-api-key",
        default=None,
        help="Optional Alpha Vantage key for small-list quote fallback (or set env var ALPHA_VANTAGE_API_KEY).",
    )

    parser.add_argument("--live", action="store_true", help="Run a live (Dash) refreshing treemap.")
    parser.add_argument("--refresh-seconds", type=int, default=30, help="Live refresh interval seconds.")

    parser.add_argument("--limit", type=int, default=5000, help="Max rows to request (provider-specific).")
    parser.add_argument(
        "--min-market-cap",
        type=float,
        default=10e9,
        help="Minimum market cap in USD (default: 10e9 = $10B).",
    )
    parser.add_argument(
        "--output-html",
        default="us_stock_market_treemap.html",
        help="HTML output path (static mode).",
    )
    args = parser.parse_args(argv)

    universe_provider = args.universe_provider or args.provider
    quote_provider = args.quote_provider or args.provider
    fmp_api_key = args.fmp_api_key or os.getenv("FMP_API_KEY") or ""
    av_api_key = args.alpha_vantage_api_key or os.getenv("ALPHA_VANTAGE_API_KEY") or ""

    def fetch_universe() -> pd.DataFrame:
        if args.source == "api":
            return fetch_screener_df_api(
                base_url=args.openbb_api_url,
                provider=universe_provider,
                limit=args.limit,
                auth_token=args.openbb_api_token,
            )
        return fetch_screener_df_sdk(provider=universe_provider, limit=args.limit)

    def fetch_quotes(symbols: list[str]) -> pd.DataFrame:
        if args.source == "api":
            try:
                return fetch_quotes_df_api(
                    base_url=args.openbb_api_url,
                    provider=quote_provider,
                    symbols=symbols,
                    auth_token=args.openbb_api_token,
                )
            except Exception:
                # If the OpenBB API/provider fails, fall back to direct provider HTTP if configured.
                if quote_provider == "fmp" and fmp_api_key:
                    return fetch_quotes_df_fmp_http(api_key=fmp_api_key, symbols=symbols)
                if av_api_key:
                    return fetch_quote_df_alpha_vantage_http(api_key=av_api_key, symbols=symbols)
                raise

        from openbb import obb  # type: ignore

        q = obb.equity.price.quote(symbol=symbols, provider=quote_provider)
        return q.to_df()

    # Universe (slow-moving)
    df_raw = fetch_universe()
    universe = clean_and_filter(df_raw, min_market_cap_usd=args.min_market_cap)
    if universe.empty:
        raise RuntimeError("No rows left after cleaning/filtering. Try lowering --min-market-cap or raising --limit.")

    if args.live:
        try:
            from dash import Dash, dcc, html  # type: ignore
            from dash.dependencies import Input, Output  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Live mode requires Dash. Install with: pip install dash") from e

        universe_symbols = universe["symbol"].tolist()

        app = Dash(__name__)
        app.layout = html.Div(
            [
                html.H2("US Stock Market Treemap (Large & Mega Caps)", style={"margin": "8px 8px 0 8px"}),
                html.Div(id="last-updated", style={"margin": "0 8px 8px 8px", "color": "#666"}),
                dcc.Graph(id="treemap", style={"height": "86vh"}),
                dcc.Interval(id="interval", interval=args.refresh_seconds * 1000, n_intervals=0),
                dcc.Interval(id="universe-interval", interval=30 * 60 * 1000, n_intervals=0),
            ],
            style={"margin": 0, "padding": 0},
        )

        @app.callback(Output("last-updated", "children"), Input("interval", "n_intervals"))
        def _ts(_n):
            import datetime as _dt

            return f"Last updated: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        @app.callback(Output("treemap", "figure"), Input("interval", "n_intervals"))
        def _update(_n):
            qdf = fetch_quotes(universe_symbols)
            if qdf.empty:
                return build_treemap(universe, title="US Stock Market Treemap (Large & Mega Caps)")

            # If we already have normalized columns (e.g., direct FMP fallback), use them.
            if set(["symbol", "change_percent"]).issubset(set(c.lower() for c in qdf.columns)):
                # Keep case-sensitive original names intact if present.
                sym_col = _pick_column(qdf, ["symbol"])
                chg_col = _pick_column(qdf, ["change_percent", "changesPercentage", "changePercent"])
                quotes = pd.DataFrame(
                    {
                        "symbol": qdf[sym_col].astype(str).str.upper().str.strip(),
                        "change_percent": qdf[chg_col].map(_parse_percent),
                    }
                ).dropna(subset=["symbol"])
            else:
                sym_col = _pick_column(qdf, ["symbol", "ticker"])
                chg_col = _pick_column(qdf, ["change_percent", "changePercent", "change_pct", "changesPercentage"])
                quotes = pd.DataFrame(
                    {
                        "symbol": qdf[sym_col].astype(str).str.upper().str.strip(),
                        "change_percent": qdf[chg_col].map(_parse_percent),
                    }
                ).dropna(subset=["symbol"])

            merged = universe.drop(columns=["change_percent"], errors="ignore").merge(
                quotes, on="symbol", how="left"
            )
            merged["change_percent"] = merged["change_percent"].fillna(0.0)
            return build_treemap(merged, title="US Stock Market Treemap (Large & Mega Caps)")

        @app.callback(Output("treemap", "figure"), Input("universe-interval", "n_intervals"))
        def _refresh_universe(_n):
            nonlocal universe, universe_symbols
            u_raw = fetch_universe()
            u = clean_and_filter(u_raw, min_market_cap_usd=args.min_market_cap)
            if not u.empty:
                universe = u
                universe_symbols = universe["symbol"].tolist()
            return build_treemap(universe, title="US Stock Market Treemap (Large & Mega Caps)")

        # Dash >= 2.14+ uses `app.run(...)` (run_server is obsolete).
        app.run(debug=False, port=8050)
        return 0

    fig = build_treemap(universe, title="US Stock Market Treemap (Large & Mega Caps)")
    fig.write_html(args.output_html, include_plotlyjs="cdn", full_html=True)
    fig.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
