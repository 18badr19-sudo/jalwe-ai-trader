import streamlit as st
import time
import requests
from event_engine import EventEngine

# --- Telegram Bot Direct Configuration (Verified Correct Credentials) ---
TELEGRAM_BOT_TOKEN = "8830107385:AAEUAOf3lPFPX_dmLHrLc6RXKaFCNe9y9JA"
TELEGRAM_CHAT_ID = "709594771"

def send_streamlit_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"Telegram response status: {response.status_code}")
        print(f"Telegram response body: {response.text}")
    except Exception as e:
        print(f"Telegram error: {e}")

# Trigger startup alert once when dashboard loads (in Arabic)
if "alert_sent" not in st.session_state:
    send_streamlit_telegram_alert("🟢 نظام جالوه آي تريدر V4 - متصل الآن\n\nحالة النظام: واجهة الويب ومحرك التنبيهات يعملان بكفاءة تامة يا بدر.")
    st.session_state["alert_sent"] = True

# --- Streamlit Dashboard Interface ---
st.set_page_config(page_title="JALWE AI TRADER V4", layout="wide")

st.title("🏛️ JALWE AI TRADER V4 - لوحة تحكم كمية مؤسسية")
st.markdown("---")

# Sidebar for controls
st.sidebar.header("لوحة التحكم")
mode = st.sidebar.selectbox("وضع التشغيل", ["Institutional Live", "Paper Trading", "Strategy Lab"])

# Main Dashboard Layout
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="قيمة المحفظة", value="$104,580.00", delta="+2.4%")

with col2:
    st.metric(label="مخاطر الأحداث الكبرى", value="طبيعي", delta="مستقر")

with col3:
    st.metric(label="الاستراتيجيات الفعالة", value="4 عمليات", delta="أفضل أداء")

st.markdown("### 📊 حالة نظام السوق ومحرك الأحداث")
event_eng = EventEngine()
event_status = event_eng.check_event_risk("PORTFOLIO")

st.info(f"**بروتوكول الإجراء الحالي:** {event_status['action']} \n\n**السبب:** {event_status['reason']}")

if st.button("🚨 إرسال تنبيه طوارئ يدوي عبر تيليجرام"):
    alert_msg = "🚨 جالوه آي تريدر V4 - تنبيه طوارئ يدوي 🚨\n\nتم تفعيل بروتوكول حماية رأس المال يدوياً عبر لوحة التحكم بنجاح يا بدر!"
    send_streamlit_telegram_alert(alert_msg)
    st.success("تم إرسال تنبيه الطوارئ بنجاح إلى تيليجرام!")

st.markdown("---")
st.caption("JALWE AI TRADER V4 • أنظمة ذاتية مؤسسية متقدمة")
