# Macro Regime Dashboard

Most dashboards show prices. This one helps you see what regime you are in and whether the signals behind that view agree.

I built this Streamlit dashboard for top-down macro work. It brings growth, inflation, liquidity, positioning, options and cross-asset data into one place, then compares several regime detectors. It is a research tool: it does not pick securities or turn a regime label into portfolio weights.

[Try the demo](https://macro.quantalphalabs.io/) | [Read the setup guide](SETUP.md) | [Original post](https://x.com/suja_Labarum/status/2062536311144149122)

## How I use it

I start with growth, inflation, labor and the yield curve. Then I check whether rates, currencies, commodities, equities and volatility confirm that picture. Liquidity, positioning and options add context.

Agreement matters, but disagreement can be just as useful. A strong composite score with low agreement tells a different story from a score backed by several independent signals.

## Regime monitor

The monitor combines six approaches:

- **Macro Quadrant:** credit and inflation momentum, mapped to Goldilocks, Reflation, Stagflation or Recession.
- **Trend and volatility:** price relative to its 200-day average, an ADX trend filter and realized volatility.
- **Hidden Markov Model:** a Gaussian model of SPY returns that estimates market states using a forward-only approach.
- **Volatility:** VIX, term structure and historical volatility.
- **Liquidity and credit:** financial conditions and high-yield spreads, including their direction of change.
- **Breadth:** advance/decline data and the share of the market above its 200-day average.

The consensus view groups readings by daily, weekly and monthly timeframes. It shows a composite score and an agreement percentage, so you can see both the direction and how much support it has. Availability depends on the underlying data.

## What is in the dashboard

- **Macro overview:** growth, inflation, labor, consumption, housing, recession indicators and the yield curve.
- **Markets and sentiment:** equities, currencies, commodities, investor surveys and cross-asset context.
- **Options and derivatives:** put/call data, volatility term structure, skew and options-chain analysis.
- **Liquidity and flows:** funding conditions, Treasury and market-depth proxies, CFTC positioning, fund flows and trend models.
- **Global macro and calendar:** policy context, economic releases and earnings events.
- **Additional tools:** energy futures, X intelligence and an AI macro analysis view. Some features depend on local configuration or external data.

The dashboard includes diagnostics for data providers. Free tiers are enough to get started, but feeds can be delayed, unavailable or rate-limited. Fallbacks exist for some sources; they do not guarantee that every panel will be populated.

## Run locally

Clone the repo and install the dependencies:

```bash
git clone https://github.com/Tamaz-sujashvili/macro-dashboard-streamlit.git
cd macro-dashboard-streamlit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate`.

Copy the example secrets file and add the keys you need:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Start with a [free FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html). It is needed for many of the macro series. Other keys are optional and depend on the panels you use. You can also set keys as environment variables. Keep `.streamlit/secrets.toml` private and do not commit it.

```bash
export MACRO_DASHBOARD_MODE=local
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501). Local mode enables personal features and should only be used on a trusted, private machine. The default public mode reads server-side keys without displaying them and disables local-only tools. If a panel is empty, check the provider diagnostics, your keys and network access. The first load can take time while the app fetches data.

## Data sources

The dashboard draws on public data and providers with free tiers, including FRED, BLS, U.S. Treasury, NY Fed, CFTC, EIA, ICI, Yahoo Finance, Alpha Vantage, Tiingo and Finnhub. Access, coverage and rate limits vary by provider. See [SETUP.md](SETUP.md) for configuration and troubleshooting.

## Tests

```bash
pip install pytest
python -m pytest tests/ -q
```

## Where I want to take it

Next I want to build a regime-conditional playbook: measure what assets did after each regime without look-ahead, then compare those results with the textbook expectations.

If you use the dashboard, fork it and adapt the signals to your own process. Contributions and feedback are welcome.

This project is for research and education. Its outputs are not investment advice.
