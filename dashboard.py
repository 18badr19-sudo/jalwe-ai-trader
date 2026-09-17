import streamlit as st
import pandas as pd
from event_engine import EventEngine

st.set_page_config(page_title="JALWE AI TRADER V4", layout="wide")

# Initialize Engines
event_eng = EventEngine()

# Main Header
st.markdown("# 🏛️ JALWE AI TRADER V4 - Institutional Quantitative Dashboard")
st.markdown("Autonomous paper-trading ecosystem integrated with Options Intelligence, Strategy Lab, Learning Engine, Market Regime Detection & Macro Event Engine.")

# Top Status Metrics Bar
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Account Balance", "$10,000.00")
with col2:
    st.metric("Market Regime", "BULL TREND")
with col3:
    st.metric("Risk Profile", "AGGRESSIVE GROWTH")
with col4:
    st.metric("V4 Architecture", "Fully Operational")

st.markdown("---")

# Macro Event Risk Section (Event Engine)
st.markdown("### 🌐 Macroeconomic Event Risk & Catalyst Monitor (Event Engine)")
event_status = event_eng.check_event_risk("PORTFOLIO")

if event_status["event_risk"] == "HIGH":
    st.error(f"⚠️ Event Risk: {event_status['event_risk']} — Action: {event_status['action']} ({event_status['reason']})")
else:
    st.success(f"✅ Event Risk: {event_status['event_risk']} — Action: {event_status['action']} ({event_status['reason']})")

st.markdown("---")

# Portfolio Equity Curve
st.markdown("### 📈 Institutional Portfolio Equity Curve")
chart_data = pd.DataFrame({
    'Time': ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00'],
    'Equity ($)': [10000, 10100, 10080, 10300, 10500, 10800]
})
st.line_chart(chart_data.set_index('Time'))

st.markdown("### ⚡ Options Flow & Multi-Model AI Evaluation")
data = {
    "Symbol": ["AAPL", "TSLA", "NVDA"],
    "AI Score": [63.88, 49.9, 49.11],
    "Sentiment": ["Neutral", "Bearish", "Bearish"],
    "Option Quality": ["HIGH", "HIGH", "HIGH"],
    "Vol/OI Ratio": [1.71, 1.71, 1.71],
    "Action": ["TRADE", "TRADE", "TRADE"],
    "Stop Loss": [171.5, 235.2, 617.4],
    "Position Size": [5, 4, 1]
}
st.dataframe(pd.DataFrame(data), use_container_width+True)
