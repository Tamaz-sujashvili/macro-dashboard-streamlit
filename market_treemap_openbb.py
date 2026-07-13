import pandas as pd
import plotly.express as px
from openbb import obb

# =============================================================================
# CONFIGURATION & SETTINGS
# =============================================================================
# Set your OpenBB API keys here if required by the provider (e.g., FMP)
# obb.user.credentials.fmp_api_key = "YOUR_API_KEY"

MARKET_CAP_THRESHOLD = 10_000_000_000  # $10 Billion for Large/Mega Cap
COLOR_SCALE = "RdYlGn"                 # Red-Yellow-Green
ROOT_NAME = "US Stock Market"          # Root node for the hierarchy

def build_market_treemap():
    print("Fetching data from OpenBB...")

    try:
        # 1. DATA INGESTION
        # Using the 'fmp' (Financial Modeling Prep) provider for comprehensive screener data
        # We fetch equity screener data which includes market cap, sector, and price change
        res = obb.equity.screener(provider="fmp")

        # Convert the OpenBB result object to a Pandas DataFrame
        df = res.to_df()

    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # 2. DATA CLEANING
    print("Cleaning and filtering data...")

    # Define required columns for our visualization
    required_cols = ['symbol', 'market_cap', 'sector', 'industry', 'change']

    # Drop rows missing essential data
    df = df.dropna(subset=required_cols)

    # Ensure market_cap is numeric
    df['market_cap'] = pd.to_numeric(df['market_cap'], errors='coerce')
    df = df.dropna(subset=['market_cap'])

    # Filter for Large-Cap and Mega-Cap stocks only (> $10B)
    # This prevents the treemap from becoming cluttered with thousands of tiny boxes
    df = df[df['market_cap'] > MARKET_CAP_THRESHOLD].copy()

    # Add a constant column for the root node of the treemap
    df['market_root'] = ROOT_NAME

    # 3. VISUALIZATION
    print("Generating Plotly Treemap...")

    # We define the hierarchical path: Root -> Sector -> Industry -> Ticker
    fig = px.treemap(
        df, 
        path=[px.Constant(ROOT_NAME), 'sector', 'industry', 'symbol'], 
        values='market_cap', 
        color='change',
        color_continuous_scale=COLOR_SCALE,
        color_continuous_midpoint=0,  # Ensures 0% is yellow, <0 is red, >0 is green
        labels={'change': 'Daily Change %', 'market_cap': 'Market Cap'},
    )

    # 4. STYLING AND LABELS
    # Customizing the text inside the boxes
    # %{label} refers to the node name (Sector/Industry/Symbol)
    # %{color:.2f}% displays the color value (change) formatted to 2 decimal places
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{color:.2f}%", 
        hovertemplate="<b>Ticker:</b> %{label}<br>"
                      "<b>Sector:</b> %{customdata[0]}<br>"
                      "<b>Industry:</b> %{customdata[1]}<br>"
                      "<b>Change:</b> %{color:.2f}%<extra></extra>",
        customdata=df[['sector', 'industry']]  # Passing extra data for the hovertemplate
    )

    # Layout polishing
    fig.update_layout(
        title={
            'text': "Market Heatmap: Large & Mega Cap Stocks (Size by Market Cap, Color by Change)",
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(size=20)
        },
        margin=dict(t=50, l=10, r=10, b=10),
        coloraxis_colorbar=dict(title="Change %")
    )

    print("Done! Displaying map...")
    fig.show()

if __name__ == "__main__":
    build_market_treemap()
