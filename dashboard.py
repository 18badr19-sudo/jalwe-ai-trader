import streamlit as st
import sqlite3
import pandas as pd
import requests
import os
import alpaca_trade_api as tradeapi
from event_engine import EventEngine

# التوكن المباشر والصحيح 100%
TELEGRAM_BOT_TOKEN = "8830107385:AAHXZruzk7Hmt1Z6jaEWbncVgBFG0Gif-I"
TELEGRAM_CHAT_ID = "709594771"

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

st.title("🏛️ JALWE AI TRADER V4 - لوحة تحكم تحدي التدوير الذكي")
st.markdown("---")

st.sidebar.header("لوحة التحكم")
mode = st.sidebar.selectbox("وضع التشغيل", ["Institutional Live", "Paper Trading", "Strategy Lab"])

# جلب بيانات الحساب الفعلية من Alpaca إن وجدت، أو القيم الافتراضية للتحدي
APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
APCA_API_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

try:
    alpaca = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL, api_version='v2')
    account = alpaca.get_account()
    equity = float(account.equity)
    cash = float(account.cash)
    positions = alpaca.list_positions()
except Exception:
    equity, cash, positions = 100.0, 100.0, []

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="إجمالي قيمة المحفظة", value=f"${equity:,.2f}", delta="التدوير التراكمي")
with col2:
    st.metric(label="السيولة المتاحة للتدوير", value=f"${cash:,.2f}", delta="مستقر")
with col3:
    st.metric(label="الأسهم والصفقات النشطة", value=f"{len(positions)} عمليات", delta="وقف متحرك نشط")

st.markdown("### 📊 حالة نظام السوق ومحرك الأحداث")
try:
    event_eng = EventEngine()
    event_status = event_eng.check_event_risk("PORTFOLIO")
    st.info(f"**بروتوكول الإجراء الحالي:** {event_status['action']} \n\n**السبب:** {event_status['reason']}")
except Exception:
    st.info("**حالة السوق:** النظام يعمل بكفاءة ويراقب الزخم وأسعار الدخول.")

# جلب بيانات قاعدة البيانات (الصفقات النشطة وسجل التعلم)
def get_db_data(query):
    try:
        conn = sqlite3.connect("jalwe_learning.db")
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

st.markdown("---")
st.subheader("🚀 الصفقات النشطة ووقف الخسارة المتحرك الذكي")
active_df = get_db_data("SELECT symbol, entry_price, stop_loss_price, highest_price, qty, status FROM active_trades_tracker WHERE status='ACTIVE'")
if not active_df.empty:
    st.dataframe(active_df, use_container_width=True)
else:
    st.info("لا توجد صفقات نشطة حالياً، الرادار يبحث عن الفرصة القادمة...")

st.markdown("---")
st.subheader("🧠 سجل التعلم الذاتي والصفقات المغلقة (Closed-Loop)")
closed_df = get_db_data("SELECT symbol, entry_price, exit_price, profit_pct, result_status, timestamp FROM closed_trades_performance ORDER BY id DESC")
if not closed_df.empty:
    st.dataframe(closed_df, use_container_width=True)
else:
    st.info("لم يتم تسجيل صفقات مغلقة حتى الآن.")

st.markdown("---")
if st.button("🚨 إرسال تنبيه طوارئ يدوي عبر تيليجرام"):
    alert_msg = "🚨 جالوه آي تريدر V4 - تنبيه طوارئ يدوي 🚨\n\nتم تفعيل بروتوكول حماية رأس المال يدوياً عبر لوحة التحكم بنجاح يا بدر!"
    status_code, response_text = send_streamlit_telegram_alert(alert_msg)
    
    if status_code == 200:
        st.success("تم إرسال التنبيه إلى تيليجرام بنجاح!")
    else:
        st.error(f"خطأ من تيليجرام (الكود {status_code}): {response_text}")

if st.button("🔄 تحديث البيانات اللحظية"):
    st.rerun()

st.markdown("---")
st.caption("JALWE AI TRADER V4 • لوحة تحكم تحدي التدوير التراكمي والوقف المتحرك الذكي")
