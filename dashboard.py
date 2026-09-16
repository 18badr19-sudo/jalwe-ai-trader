"""
JALWE AI TRADER V3
Streamlit Dashboard
"""
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="JALWE AI Trader Dashboard",
    page_icon="📈",
    layout="wide"
)

# Title and header
st.title("🚀 JALWE AI TRADER V3 - Live Dashboard")
st.markdown("Real-time monitoring for automated algorithmic paper-trading pipeline.")

# Database connection
DB_PATH = "jalwe_trader.db"

def load_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        trades_df = pd.read_sql("SELECT * FROM trades", conn)
        opportunities_df = pd.read_sql("SELECT * FROM opportunities", conn)
        conn.close()
        return trades_df, opportunities_df
    except Exception as e:
        st.error(f"Error loading data from database: {e}")
        return pd.DataFrame(), pd.DataFrame()

trades_df, opportunities_df = load_data()

# Sidebar metrics
st.sidebar.header("Control Panel")
refresh_button = st.sidebar.button("Refresh Data")

# Main metrics overview
col1, col2, col3 = st.columns(3)

total_trades = len(trades_df) if not trades_df.empty else 0
open_trades = len(trades_df[trades_df['status'] == 'OPEN']) if not trades_df.empty and 'status' in trades_df.columns else 0
total_opportunities = len(opportunities_df) if not opportunities_df.empty else 0

col1.metric("Total Trades Executed", total_trades)
col2.metric("Active Open Trades", open_trades)
col3.metric("Scanned Opportunities", total_opportunities)

st.markdown("---")

# Trades table section
st.subheader("📋 Executed Trades History")
if not trades_df.empty:
    st.dataframe(trades_df, use_container_width=True)
else:
    st.info("No trades executed yet. Run `main.py` to start the bot.")

# Opportunities table section
st.subheader("🤖 AI Market Opportunities Log")
if not opportunities_df.empty:
    st.dataframe(opportunities_df, use_container_width=True)
else:
    st.info("No opportunities recorded yet.")

# Visualizations
if not trades_df.empty and 'entry_price' in trades_df.columns:
    st.markdown("---")
    st.subheader("📊 Performance Analytics")
    fig = px.bar(trades_df, x='symbol', y='shares', color='direction', title="Shares Allocated per Symbol")
    st.plotly_chart(fig, use_container_width=True)