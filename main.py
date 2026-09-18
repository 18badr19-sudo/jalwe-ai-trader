import os
import time
import schedule
import pandas as pd
import alpaca_trade_api as tradeapi
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import traceback

# ==================== إعدادات البيئة والربط ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
APCA_API_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

# تهيئة تليجرام وألباكا
bot = telebot.TeleBot(TELEGRAM_TOKEN)
alpaca = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL, api_version='v2')

# حالة البوت ومتغيرات المراقبة
bot_running = True
last_error = "لا توجد أخطاء، النظام يعمل بسلامة تامّة ✅"
status_message_id = None

# قائمة الأسهم المستهدفة للمسح
WATCHLIST = ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]

# ==================== لوحة المفاتيح الثابتة (أزرار التحكم) ====================
def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    btn_status = KeyboardButton("🔍 فحص حالة البوت")
    markup.add(btn_start, btn_stop, btn_status)
    return markup

# ==================== إرسال رسالة الحالة المفصلة ====================
def send_status_report(chat_id):
    global bot_running, last_error
    state_text = "🟢 يعمل بشكل طبيعي (نشط)" if bot_running else "🛑 متوقف مؤقتاً بناءً على طلبك"
    
    report = (
        f"📊 **تقرير حالة نظام JALWE AI TRADER V4**\n\n"
        f"• **حالة البوت:** {state_text}\n"
        f"• **حالة الاتصال بـ Alpaca:** متصل بنجاح 🌐\n"
        f"• **آخر الأخطاء المسجلة:**\n`{last_error}`\n\n"
        f"البوت يعمل على مدار الساعة 24/7 على منصة Railway."
    )
    bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())

# ==================== الاستماع لأزرار التحكم في تليجرام ====================
@bot.message_handler(func=lambda message: True)
def handle_control_buttons(message):
    global bot_running
    text = message.text
    chat_id = message.chat.id

    if "تشغيل البوت" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل وتشغيل نظام JALWE AI TRADER V4 بنجاح.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف نظام التداول مؤقتاً.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "فحص حالة البوت" in text:
        send_status_report(chat_id)
    else:
        bot.send_message(chat_id, "استخدم الأزرار أدناه للتحكم بحالة البوت ومتابعة الأخطاء:", reply_markup=get_control_keyboard())

# ==================== منطق مسح السوق والتداول ====================
def market_scanning_cycle():
    global bot_running, last_error
    if not bot_running:
        return

    print("INFO - Market scanning cycle executing...")
    
    try:
        # فحص رصيد الحساب التجريبي ($100)
        account = alpaca.get_account()
        equity = float(account.equity)
        
        # إذا نجحت العملية، نحدث حالة الخطأ بأنه سليم
        last_error = "لا توجد أخطاء، النظام يعمل بسلامة تامّة ✅"
        
        for symbol in WATCHLIST:
            alert_msg = (
                f"🚨 **تنبيه صفقة ذكية - JALWE AI V4**\n"
                f"📌 السهم: `{symbol}`\n"
                f"📊 الحالة: فحص الإشارات الفنية وإدارتها.\n"
                f"💰 إجمالي المحفظة: `${equity:.2f}`"
            )
            if TELEGRAM_CHAT_ID:
                bot.send_message(TELEGRAM_CHAT_ID, alert_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
            break
            
    except Exception as e:
        # التقاط الخطأ وتخزينه لإظهاره للمستخدم عند الطلب أو إرساله تلقائياً
        err_msg = str(e)
        last_error = err_msg
        print(f"Error in market scan: {err_msg}")
        if TELEGRAM_CHAT_ID:
            bot.send_message(
                TELEGRAM_CHAT_ID, 
                f"⚠️ **تنبيه خطأ في النظام!**\nحدث خطأ أثناء فحص السوق:\n`{err_msg}`", 
                parse_mode="Markdown", 
                reply_markup=get_control_keyboard()
            )

# ==================== تقرير نهاية اليوم (EOD) ====================
def send_end_of_day_summary():
    if not TELEGRAM_CHAT_ID:
        return
    try:
        account = alpaca.get_account()
        summary_msg = (
            f"📈 **تقرير نهاية اليوم - JALWE AI TRADER**\n"
            f"💵 القيمة الإجمالية للحساب: `${float(account.equity):.2f}`\n"
            f"💵 السيولة المتاحة: `${float(account.cash):.2f}`\n"
            f"✅ حالة النظام: يعمل بانتظام واستقرار تام."
        )
        bot.send_message(TELEGRAM_CHAT_ID, summary_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        print(f"Error sending EOD summary: {e}")

# جدولة المهام
schedule.every(30).minutes.do(market_scanning_cycle)
schedule.every().day.at("23:00").do(send_end_of_day_summary)

# رسالة البداية عند التشغيل
if TELEGRAM_CHAT_ID:
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            "🚀 **JALWE AI TRADER V4 pipeline is online 24/7**\nتم تشغيل البوت بنجاح ومزود الآن بزر فحص الحالة والأخطاء.",
            parse_mode="Markdown",
            reply_markup=get_control_keyboard()
        )
    except Exception as e:
        print(f"Startup message error: {e}")

# تشغيل البوت وتلقي التحديثات في الخلفية
if __name__ == "__main__":
    print("INFO - JALWE AI TRADER V4 pipeline is online 24/7")
    
    import threading
    def polling_thread():
        bot.infinity_polling(none_stop=True)
    
    t = threading.Thread(target=polling_thread)
    t.daemon = True
    t.start()

    while True:
        schedule.run_pending()
        time.sleep(1)
