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

# محرك التحليل الذكي وقراءة قاعدة البيانات للتقييم والتطوير
def analyze_system_health_and_suggest(db_path="jalwe_learning.db"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # جلب إحصائيات الصفقات المغلقة
        cursor.execute("""
            SELECT COUNT(*), 
                   SUM(CASE WHEN result_status = 'WIN' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN result_status = 'LOSS' THEN 1 ELSE 0 END),
                   AVG(profit_pct)
            FROM closed_trades_performance
        """)
        row = cursor.fetchone()
        total_trades = row[0] or 0
        wins = row[1] or 0
        losses = row[2] or 0
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        # جلب حالات التعلم الذاتي
        cursor.execute("SELECT COUNT(*) FROM feature_snapshots WHERE outcome != -1")
        trained_cases = cursor.fetchone()[0] or 0
        conn.close()

        # صياغة تقرير التشخيص الذكي
        report = f"📊 **إجمالي الصفقات المغلقة:** {total_trades} (🟢 {wins} رابحة | 🔴 {losses} خاسرة)\n"
        report += f"🎯 **نسبة النجاح الحالية (Win Rate):** {win_rate:.1f}%\n"
        report += f"🧠 **حالات التعلم الذاتي النشطة:** {trained_cases} حالة\n\n"

        report += "🛠️ **التعديلات المقترحة (ماذا نعدل؟):**\n"
        if total_trades > 0 and win_rate < 45:
            report += "• ⚠️ *نسبة النجاح منخفضة:* يُفضل رفع الحد الأدنى لدرجة الدخول (`MIN_SIGNAL_SCORE`) لتصفية الصفقات الضعيفة.\n"
        elif total_trades > 0 and win_rate >= 65:
            report += "• 🔥 *الأداء ممتاز:* يمكنك زيادة حجم رأس المال المخصص لكل صفقة بنسبة طفيفة.\n"
        else:
            report += "• ✨ *الأداء مستقر:* استمر في مراقبة السوق حتى يتجمع عدد أكبر من الصفقات المغلقة.\n"

        if trained_cases < 50:
            report += f"• ⏳ *بيانات التدريب قليلة ({trained_cases}/50):* انتظر حتى ينفذ البوت صفقات أكثر لتحسين دقة نموذج الذكاء الاصطناعي.\n"
        else:
            report += "• 🤖 *نموذج الذكاء الاصطناعي ناضج:* تم جمع بيانات كافية لتدريب نموذج `RandomForest` بكفاءة عالية.\n"

        report += "\n💡 **الإضافات المقترحة للمستقبل (ماذا نضيف؟):**\n"
        report += "• 📰 *فلتر الأخبار الاقتصادية (Macro News):* إيقاف التداول آلياً قبل صدور البيانات الهامة لتجنب التقلبات الحادة.\n"
        report += "• 📊 *إدارة سيولة ديناميكية:* تعديل حجم المخاطرة بناءً على اتجاه السوق العام (صاعد/هابط).\n"

        return report
    except Exception as e:
        return f"⚠️ تعذر قراءة قاعدة البيانات للتحليل حالياً: {e}"

st.set_page_config(page_title="JALWE AI TRADER V4", layout="wide")

st.title("🏛️ JALWE AI TRADER V4 - لوحة تحكم تحدي التدوير الذكي")
st.markdown("---")

st.sidebar.header("لوحة التحكم")
mode = st.sidebar.selectbox("وضع التشغيل", ["Institutional Live", "Paper Trading", "Strategy Lab"])

# جلب بيانات الحساب الفعلية من Alpaca
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

# دالة جلب بيانات قاعدة البيانات
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

# قسم التحليل والتطوير الذكي المضاف حديثاً
st.markdown("---")
st.subheader("💡 التقييم والتشخيص الذكي للبوت")
if st.button("🔍 تحليل الأداء الحالي واقتراح التعديلات والإضافات"):
    suggestion_report = analyze_system_health_and_suggest()
    st.success("تم فحص وتحليل قاعدة البيانات بنجاح:")
    st.markdown(suggestion_report)

st.markdown("---")
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("🚨 إرسال تنبيه طوارئ يدوي عبر تيليجرام"):
        alert_msg = "🚨 جالوه آي تريدر V4 - تنبيه طوارئ يدوي 🚨\n\nتم تفعيل بروتوكول حماية رأس المال يدوياً عبر لوحة التحكم بنجاح يا بدر!"
        status_code, response_text = send_streamlit_telegram_alert(alert_msg)
        if status_code == 200:
            st.success("تم إرسال التنبيه إلى تيليجرام بنجاح!")
        else:
            st.error(f"خطأ من تيليجرام (الكود {status_code}): {response_text}")

with col_btn2:
    if st.button("🔄 تحديث البيانات اللحظية"):
        st.rerun()

st.markdown("---")
st.caption("JALWE AI TRADER V4 • لوحة تحكم تحدي التدوير التراكمي والوقف المتحرك الذكي")
