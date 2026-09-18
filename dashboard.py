import os
import streamlit as st
import requests
from event_engine import EventEngine

# قراءة التوكن ومعرف الشات من متغيرات النظام في Railway لتجنب أي خطأ في النسخ
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8830107385:AAFuIYgvlHjGC8EHe-JzcsLB-Z4S-jPTLE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "709594771")

def send_streamlit_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code, response.text
    except Exception as e:
        return 500, str(e)

st.set_page_config(page_title="JALWE AI TRADER V4", layout="wide")

st.title("🏛️ JALWE AI TRADER V4 - لوحة تحكم كمية مؤسسية")
st.markdown("---")

st.sidebar.header("لوحة التحكم")
mode = st.sidebar.selectbox("وضع التشغيل", ["Institutional Live", "Paper Trading", "Strategy Lab"])

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
    status_code, response_text = send_streamlit_telegram_alert(alert_msg)
    
    if status_code == 200:
        st.success("تم إرسال التنبيه إلى تيليجرام بنجاح!")
    else:
        st.error(f"خطأ من تيليجرام (الكود {status_code}): {response_text}")

st.markdown("---")
st.caption("JALWE AI TRADER V4 • أنظمة ذاتية مؤسسية متقدمة")
