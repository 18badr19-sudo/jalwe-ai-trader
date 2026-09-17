import streamlit as st
import time
import requests
from event_engine import EventEngine

# --- Telegram Bot Direct Configuration ---
TELEGRAM_BOT_TOKEN = "7917757905:AAEUw7U_X0w8gT91Z3f8xQ9"
TELEGRAM_CHAT_ID = "6124128003"

def send_streamlit_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=3)
    except Exception as e:
        print(f"Telegram error: {e}")

# Trigger startup alert once when dashboard loads
if "alert_sent" not in st.session_state:
    send_streamlit_telegram_alert("🟢 *JALWE AI TRADER V4 - DASHBOARD ONLINE*\n\n🏛️ *System Status:* Web UI & Telegram Dispatcher Active.")
    st.session_state["alert_sent"] = True

# --- Streamlit Dashboard Interface ---
st.set_page_config(page_title="JALWE AI TRADER V4", layout="wide")

st.title("🏛️ JALWE AI TRADER V4 - Institutional Quantitative Dashboard")
st.markdown("---")

# Sidebar for controls
st.sidebar.header("Control Panel")
mode = st.sidebar.selectbox("Operating Mode", ["Institutional Live", "Paper Trading", "Strategy Lab"])

# Main Dashboard Layout
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Portfolio Value", value="$104,580.00", delta="+2.4%")

with col2:
    st.metric(label="Macro Event Risk", value="NORMAL", delta="Stable")

with col3:
    st.metric(label="Active Strategies", value="4 Operational", delta="Optimal")

st.markdown("### 📊 Market Regime & Event Engine Status")
event_eng = EventEngine()
event_status = event_eng.check_event_risk("PORTFOLIO")

st.info(f"**Current Action Protocol:** {event_status['action']} \n\n**Reason:** {event_status['reason']}")

if st.button("🚨 Trigger Manual Emergency Risk Alert"):
    alert_msg = "🚨 *JALWE AI TRADER V4 - MANUAL EMERGENCY ALERT* 🚨\n\nCapital protection protocol triggered manually via Dashboard."
    send_streamlit_telegram_alert(alert_msg)
    st.success("Emergency alert dispatched successfully to Telegram!")

st.markdown("---")
st.caption("JALWE AI TRADER V4 • Institutional Grade Autonomous Systems")
