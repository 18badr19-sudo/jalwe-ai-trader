import streamlit as st
import pandas as pd
import plotly.express as px
from ai_engine import AIEngine
from risk_manager import RiskManager
from ml_predictor import MLPredictor
from options_engine import OptionsEngine
from strategy_lab import StrategyLab
from learning_engine import LearningEngine
from market_regime import MarketRegimeDetector

st.set_page_config(page_title="JALWE AI TRADER V4", layout="wide")

st.title("🏛️ JALWE AI TRADER V4 - Institutional Quantitative Dashboard")
st.markdown("Autonomous paper-trading ecosystem integrated with Options Intelligence, Strategy Lab, Learning Engine & Market Regime Detection.")

# Initialize Engines
ai_engine = AIEngine()
risk_manager = RiskManager()
ml_predictor = MLPredictor()
options_engine = OptionsEngine()
strategy_lab = StrategyLab()
learning_engine = LearningEngine()
regime_detector = MarketRegimeDetector()

# Detect Market Regime
regime_data = regime_detector.detect_regime(spy_price_change=0.85, vix_level=18.5)

# Metrics overview
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Account Balance", "$10,000.00")
with col2:
    st.metric("Market Regime", regime_data["market_regime"])
with col3:
    st.metric("Risk Profile", regime_data["recommended_risk_profile"])
with col4:
    st.metric("V4 Architecture", "Fully Operational")

st.markdown("---")

# Portfolio Equity Curve
st.subheader("📈 Institutional Portfolio Equity Curve")
chart_data = pd.DataFrame({
    "Time": ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00"],
    "Equity ($)": [10000, 10220, 10180, 10450, 10620, 10910]
})
fig = px.line(chart_data, x="Time", y="Equity ($)", markers=True, title="V4 Quantitative Paper Trading Performance")
fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("⚡ Options Flow & AI Multi-Model Evaluation")

symbols = ["AAPL", "TSLA", "NVDA"]
comprehensive_data = []

for symbol in symbols:
    ai_eval = ai_engine.evaluate_opportunity(symbol)
    entry_price = 175.0 if symbol == "AAPL" else (240.0 if symbol == "TSLA" else 630.0)
    risk_eval = risk_manager.evaluate_risk(symbol, entry_price, "BUY")
    opt_eval = options_engine.evaluate_option_chain(symbol, entry_price, strike=180.0, option_type="CALL", dte=21, iv=0.45, delta=0.55, volume=1200, open_interest=700)
    
    comprehensive_data.append({
        "Symbol": symbol,
        "AI Score": ai_eval["ai_score"],
        "Sentiment": ai_eval["sentiment"],
        "Option Quality": opt_eval["contract_quality"],
        "Vol/OI Ratio": opt_eval["vol_oi_ratio"],
        "Action": opt_eval["recommendation"],
        "Stop Loss": risk_eval["stop_loss"],
        "Position Size": risk_eval["position_size"]
    })

df_comp = pd.DataFrame(comprehensive_data)
st.dataframe(df_comp, use_container_width=True)

st.markdown("---")
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("🧬 Strategy Lab Discovery")
    new_strat = strategy_lab.discover_new_strategy_variation()
    st.write(f"**Candidate ID:** {new_strat['candidate_id']}")
    st.json(new_strat["features"])

with col_b:
    st.subheader("🧠 Learning Engine Insight")
    sample_learning = learning_engine.analyze_completed_trade("TRD_101", "AAPL", "Breakout", "WIN", 3.4, {})
    st.success(sample_learning["lesson"])
    st.info(f"Action: {sample_learning['action_required']})")
