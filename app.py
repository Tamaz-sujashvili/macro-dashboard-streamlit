import pandas as pd
import streamlit as st
import plotly.express as px

# ------------------ Page setup ------------------
st.set_page_config(
    page_title="Macro Regime & Recession Risk Dashboard",
    layout="wide"
)

st.title("Macro Regime & Recession Risk Dashboard")
st.caption("Data source: Federal Reserve Economic Data (FRED)")

# ------------------ Load data ------------------
@st.cache_data
def load_signals():
    df = pd.read_csv("data/signals.csv", index_col=0, parse_dates=True)
    return df.sort_index()

signals = load_signals()

# ------------------ Sidebar controls ------------------
st.sidebar.header("Controls")

min_date = signals.index.min().date()
max_date = signals.index.max().date()

start_date, end_date = st.sidebar.date_input(
    "Select date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

mask = (signals.index.date >= start_date) & (signals.index.date <= end_date)
s = signals.loc[mask].copy()

# ------------------ Current status ------------------
latest = signals.iloc[-1]
risk_now = int(latest["recession_risk_flag"])
status = "ELEVATED" if risk_now == 1 else "LOW"

st.markdown(
    f"## {'Recession Risk: ELEVATED' if risk_now else 'Recession Risk: LOW'}"
)

c1, c2, c3 = st.columns(3)
c1.metric("Yield curve inverted?", "Yes" if int(latest["yield_curve_inverted"]) else "No")
c2.metric("Unemployment trend up?", "Yes" if int(latest["unrate_trend_up"]) else "No")
c3.metric("Fed Funds Rate (%)", f"{latest['fedfunds']:.2f}")

st.divider()

# ------------------ Charts ------------------
left, right = st.columns(2)

with left:
    fig1 = px.line(
        s,
        x=s.index,
        y="unrate_ma3",
        title="Unemployment Rate (3-Month Moving Average)",
        labels={"unrate_ma3": "Percent", "index": "Date"},
    )
    st.plotly_chart(fig1, use_container_width=True)

with right:
    fig2 = px.line(
        s,
        x=s.index,
        y="cpi_yoy_pct",
        title="Inflation (CPI Year-over-Year %)",
        labels={"cpi_yoy_pct": "Percent", "index": "Date"},
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

fig3 = px.area(
    s,
    x=s.index,
    y="recession_risk_flag",
    title="Recession Risk Flag (1 = Elevated)",
    range_y=[-0.05, 1.05],
)
st.plotly_chart(fig3, use_container_width=True)

# ------------------ Download ------------------
st.download_button(
    label="Download filtered signals",
    data=s.to_csv().encode("utf-8"),
    file_name="signals_filtered.csv",
    mime="text/csv",
)