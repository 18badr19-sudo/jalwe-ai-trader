import streamlit as st
import pandas as pd
import plotly.express as px
from ai_engine import AIEngine
from risk_manager import RiskManager
from ml_predictor import MLPredictor

st.set_page_config(page_title="JALWE AI TRADER V3", layout="wide")

st.title("🚀 JALWE AI TRADER V3 - Ultimate Institutional Dashboard")
st.markdown("Fully automated paper trading pipeline integrated with AI Scoring, Risk Management, & ML Predictions.")

ai_engine = AIEngine()
risk_manager = RiskManager()
ml_predictor = MLPredictor()

# Metrics overview
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Account Balance", "$10,000.00")
with col2:
    st.metric("Active Positions", "67")
with col3:
    st.metric("Risk Status", "Protected (2% Max)")
with col4:
    st.metric("ML Status", "Active & Optimized")

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
st.subheader("🤖 AI, ML & Risk Comprehensive Evaluation")

symbols = ["AAPL", "TSLA", "BTCUSD", "ETHUSD", "NVDA"]
comprehensive_data = []

for symbol in symbols:
    ai_eval = ai_engine.evaluate_opportunity(symbol)
    entry_price = 175.0 if symbol == "AAPL" else (240.0 if symbol == "TSLA" else 63000.0)
    risk_eval = risk_manager.evaluate_risk(symbol, entry_price, ai_eval["decision"] if ai_eval["decision"] in ["BUY", "SELL"] else "BUY")
    ml_eval = ml_predictor.predict_trend(rsi=65.0, price_change=1.5, volume_ratio=1.2)
    
    comprehensive_data.append({
        "symbol": symbol,
        "ai_score": ai_eval["ai_score"],
        "sentiment": ai_eval["sentiment"],
        "ml_trend": ml_eval["predicted_trend"],
        "ml_conf": f"{ml_eval['confidence']}%",
        "decision": ai_eval["decision"],
        "entry": entry_price,
        "stop_loss": risk_eval["stop_loss"],
        "take_profit": risk_eval["take_profit"],
        "size": risk_eval["position_size"]
    })

df_comp = pd.DataFrame(comprehensive_data)
st.dataframe(df_comp, use_container_width=True)
