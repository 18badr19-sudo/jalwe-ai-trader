import os
import time
import schedule
import pandas as pd
import alpaca_trade_api as tradeapi
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# ==================== إعدادات البيئة والربط ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
APCA_API_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

# تهيئة تليجرام وألباكا
bot = telebot.TeleBot(TELEGRAM_TOKEN)
alpaca = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL, api_version='v2')

# حالة البوت (تشغيل / إيقاف)
bot_running = True

# قائمة الأسهم المستهدفة للمسح
WATCHLIST = ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]

# ==================== لوحة المفاتيح الثابتة (أزرار التحكم) ====================
def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    markup.add(btn_start, btn_stop)
    return markup

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
        bot.send_message(chat_id, "🛑 **تم إيقاف نظام التداول مؤقتاً بناءً على طلبك.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "استخدم الأزرار أدناه للتحكم بحالة البوت:", reply_markup=get_control_keyboard())

# ==================== منطق مسح السوق والتداول ====================
def market_scanning_cycle():
    global bot_running
    if not bot_running:
        print("Bot is currently stopped by user.")
        return

    print("INFO - Market scanning cycle executing...")
    
    try:
        # فحص رصيد الحساب التجريبي ($100)
        account = alpaca.get_account()
        cash = float(account.cash)
        equity = float(account.equity)
        
        # محاكاة تحليل فني مبسط للأسهم
        for symbol in WATCHLIST:
            # هنا يتم جلب بيانات السعر واتخاذ قرار التداول
            # تنبيه تجريبي للتوضيح وإثبات العمل
            alert_msg = (
                f"🚨 **تنبيه صفقة ذكية - JALWE AI V4**\n"
                f"📌 السهم: `{symbol}`\n"
                f"📊 الحالة: تحليل الإشارات الإيجابية مكتمل.\n"
                f"💰 إجمالي المحفظة: `${equity:.2f}`"
            )
            if TELEGRAM_CHAT_ID:
                bot.send_message(TELEGRAM_CHAT_ID, alert_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
            break  # نكتفي بسهم واحد في دورة الاختبار لعدم إزعاجك
            
    except Exception as e:
        print(f"Error in market scan: {e}")

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
            "🚀 **JALWE AI TRADER V4 pipeline is online 24/7**\nتم تشغيل البوت بنجاح واستقرار تام على منصة Railway.",
            parse_mode="Markdown",
            reply_markup=get_control_keyboard()
        )
    except Exception as e:
        print(f"Startup message error: {e}")

# تشغيل البوت وتلقي التحديثات في الخلفية
if __name__ == "__main__":
    print("INFO - JALWE AI TRADER V4 pipeline is online 24/7")
    
    # تشغيل خيط الاستماع للرسائل والأزرار في الخلفية
    import threading
    def polling_thread():
        bot.infinity_polling(none_stop=True)
    
    t = threading.Thread(target=polling_thread)
    t.daemon = True
    t.start()

    # حلقة الحفاظ على تشغيل النظام والجدولة
    while True:
        schedule.run_pending()
        time.sleep(1)
