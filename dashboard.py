import streamlit as st
import pandas as pd
import plotly.express as px
from ai_engine import AIEngine

st.set_page_config(page_title="JALWE AI TRADER V3", layout="wide")

st.title("🚀 JALWE AI TRADER V3 - Live Dashboard")
st.markdown("Real-time monitoring for automated paper trading pipeline with advanced AI scoring & analytics.")

ai_engine = AIEngine()

# Metrics overview
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Scanned", "104")
with col2:
    st.metric("Active Positions", "67")
with col3:
    st.metric("AI Engine Status", "Active & Optimized")

st.markdown("---")

# Interactive Plotly Equity Curve Section
st.subheader("📈 Portfolio Performance & Equity Curve")
chart_data = pd.DataFrame({
    "Time": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00"],
    "Equity ($)": [10000, 10150, 10120, 10340, 10450, 10680]
})
fig = px.line(chart_data, x="Time", y="Equity ($)", markers=True, title="Simulated Paper Trading Growth")
fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("🤖 Live AI Opportunity Evaluation")

symbols = ["AAPL", "TSLA", "BTCUSD", "ETHUSD", "NVDA"]
ai_data = []

for symbol in symbols:
    evaluation = ai_engine.evaluate_opportunity(symbol)
    ai_data.append(evaluation)

df_ai = pd.DataFrame(ai_data)
st.dataframe(df_ai, use_container_width=True)

st.markdown("---")
st.subheader("📊 Executed Trades Log")
dummy_trades = pd.DataFrame({
    "id": [1, 2, 3],
    "timestamp": ["2026-09-18 12:00", "2026-09-18 12:15", "2026-09-18 12:30"],
    "symbol": ["AAPL", "TSLA", "BTCUSD"],
    "direction": ["BUY", "BUY", "HOLD"],
    "entry_price": [175.5, 240.2, 63000.0],
    "status": ["Active", "Active", "Pending"]
})
st.dataframe(dummy_trades, use_container_width=True)
