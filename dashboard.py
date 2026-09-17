import streamlit as st
import pandas as pd
from ai_engine import AIEngine

st.set_page_config(page_title="JALWE AI TRADER V3", layout="wide")

st.title("🚀 JALWE AI TRADER V3 - Live Dashboard")
st.markdown("Real-time monitoring for automated paper trading pipeline with advanced AI scoring.")

ai_engine = AIEngine()

# Metrics overview
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Scanned", "104")
with col2:
    st.metric("Active Positions", "67")
with col3:
    st.metric("AI Status", "Active & Optimized")

st.markdown("---")
st.subheader("🤖 Live AI Opportunity Evaluation")

# Example symbols to evaluate in real-time using AI engine
symbols = ["AAPL", "TSLA", "BTCUSD", "ETHUSD", "NVDA"]
ai_data = []

for symbol in symbols:
    evaluation = ai_engine.evaluate_opportunity(symbol)
    ai_data.append(evaluation)

df_ai = pd.DataFrame(ai_data)
st.dataframe(df_ai, use_container_width=True)

st.markdown("---")
st.subheader("📊 Executed Trades Log")
# Dummy trade log representation
dummy_trades = pd.DataFrame({
    "id": [1, 2, 3],
    "timestamp": ["2026-09-18 12:00", "2026-09-18 12:15", "2026-09-18 12:30"],
    "symbol": ["AAPL", "TSLA", "BTCUSD"],
    "direction": ["BUY", "BUY", "HOLD"],
    "entry_price": [175.5, 240.2, 63000.0],
    "status": ["Active", "Active", "Pending"]
})
st.dataframe(dummy_trades, use_container_width=True)
