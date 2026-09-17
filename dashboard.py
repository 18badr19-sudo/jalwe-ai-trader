import streamlit as st
import pandas as pd
import plotly.express as px
from ai_engine import AIEngine
from risk_manager import RiskManager

st.set_page_config(page_title="JALWE AI TRADER V3", layout="wide")

st.title("🚀 JALWE AI TRADER V3 - Advanced Dashboard")
st.markdown("Real-time automated paper trading pipeline integrated with AI Scoring & Risk Management.")

ai_engine = AIEngine()
risk_manager = RiskManager()

# Metrics overview
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Account Balance", "$10,000.00")
with col2:
    st.metric("Active Positions", "67")
with col3:
    st.metric("Risk Status", "Protected (2% Max)")

st.markdown("---")

# Portfolio Equity Curve
st.subheader("📈 Portfolio Performance & Equity Curve")
chart_data = pd.DataFrame({
    "Time": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00"],
    "Equity ($)": [10000, 10150, 10120, 10340, 10450, 10680]
})
fig = px.line(chart_data, x="Time", y="Equity ($)", markers=True, title="Simulated Paper Trading Growth")
fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("🤖 AI Opportunities & Risk Evaluation")

symbols = ["AAPL", "TSLA", "BTCUSD", "ETHUSD", "NVDA"]
combined_data = []

for symbol in symbols:
    ai_eval = ai_engine.evaluate_opportunity(symbol)
    # Estimate sample entry price based on symbol
    entry_price = 175.0 if symbol == "AAPL" else (240.0 if symbol == "TSLA" else 63000.0)
    risk_eval = risk_manager.evaluate_risk(symbol, entry_price, ai_eval["decision"] if ai_eval["decision"] in ["BUY", "SELL"] else "BUY")
    
    combined_data.append({
        "symbol": symbol,
        "ai_score": ai_eval["ai_score"],
        "sentiment": ai_eval["sentiment"],
        "decision": ai_eval["decision"],
        "entry_price": entry_price,
        "stop_loss": risk_eval["stop_loss"],
        "take_profit": risk_eval["take_profit"],
        "position_size": risk_eval["position_size"]
    })

df_combined = pd.DataFrame(combined_data)
st.dataframe(df_combined, use_container_width=True)
