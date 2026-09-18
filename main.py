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

# حالة البوت ومحفظة المراقبة
bot_running = True
last_error = "لا توجد أخطاء، النظام يعمل بسلامة تامّة ✅"

# قائمة الأسهم المستهدفة للمسح والتداول الآلي
WATCHLIST = ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]

# ==================== لوحة المفاتيح الثابتة (أزرار التحكم) ====================
def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    btn_status = KeyboardButton("🔍 فحص حالة البوت")
    markup.add(btn_start, btn_stop, btn_status)
    return markup

# ==================== إرسال تقرير الحالة المفصلة ====================
def send_status_report(chat_id):
    global bot_running, last_error
    try:
        account = alpaca.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        state_text = "🟢 يعمل بشكل طبيعي (نشط)" if bot_running else "🛑 متوقف مؤقتاً بناءً على طلبك"
        
        report = (
            f"📊 **تقرير حالة نظام JALWE AI TRADER V4**\n\n"
            f"• **حالة البوت:** {state_text}\n"
            f"• **إجمالي المحفظة:** `${equity:.2f}`\n"
            f"• **السيولة المتاحة:** `${cash:.2f}`\n"
            f"• **حالة الاتصال بـ Alpaca:** متصل بنجاح 🌐\n"
            f"• **آخر الأخطاء المسجلة:**\n`{last_error}`"
        )
        bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ خطأ أثناء جلب الحالة: {e}", reply_markup=get_control_keyboard())

# ==================== الاستماع لأزرار التحكم في تليجرام ====================
@bot.message_handler(func=lambda message: True)
def handle_control_buttons(message):
    global bot_running
    text = message.text
    chat_id = message.chat.id

    if "تشغيل البوت" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل وتشغيل نظام التداول الآلي بنجاح.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف نظام التداول مؤقتاً.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "فحص حالة البوت" in text:
        send_status_report(chat_id)
    else:
        bot.send_message(chat_id, "استخدم الأزرار أدناه للتحكم بحالة البوت:", reply_markup=get_control_keyboard())

# ==================== حساب مؤشر RSI الاستراتيجي ====================
def calculate_rsi(symbol, period=14):
    try:
        barset = alpaca.get_bars(symbol, tradeapi.TimeFrame.Day, limit=period + 5).df
        if barset.empty:
            return 50.0
        close_prices = barset['close']
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])
    except Exception as e:
        print(f"Error calculating RSI for {symbol}: {e}")
        return 50.0

# ==================== دورة مسح السوق والتنفيذ الآلي ====================
def market_scanning_cycle():
    global bot_running, last_error
    if not bot_running:
        return

    print("INFO - Autonomous trading & market scanning cycle executing...")
    
    try:
        account = alpaca.get_account()
        cash = float(account.cash)
        last_error = "لا توجد أخطاء، النظام يعمل بسلامة تامّة ✅"
        
        for symbol in WATCHLIST:
            rsi_value = calculate_rsi(symbol)
            print(f"Symbol: {symbol} | RSI: {rsi_value:.2f}")
            
            # جلب الصفقات الحالية في المحفظة لهذا السهم
            positions = [p.symbol for p in alpaca.list_positions()]
            
            # استراتيجية الشراء: إذا كان المؤشر أقل من 30 وليس لدينا السهم، ولديك سيولة كافية
            if rsi_value < 30 and symbol not in positions and cash > 20:
                # نشتري بقيمة جزء من المحفظة (مثلاً سهم واحد أو جزء منه)
                alpaca.submit_order(
                    symbol=symbol,
                    qty=1,
                    side='buy',
                    type='market',
                    time_in_force='gtc'
                )
                buy_msg = (
                    f"🛒 **تنفيذ صفقة شراء آلي - JALWE AI V4**\n"
                    f"📌 السهم: `{symbol}`\n"
                    f"📊 مؤشر RSI: `{rsi_value:.2f}` (منطقة شراء)\n"
                    f"✅ الحالة: تم إرسال أمر الشراء بنجاح."
                )
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, buy_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
            
            # استراتيجية البيع: إذا كان السهم مملوكاً ومؤشر RSI أعلى من 70 (جني أرباح)
            elif rsi_value > 70 and symbol in positions:
                alpaca.close_position(symbol)
                sell_msg = (
                    f"💰 **تنفيذ صفقة بيع (جني أرباح) - JALWE AI V4**\n"
                    f"📌 السهم: `{symbol}`\n"
                    f"📊 مؤشر RSI: `{rsi_value:.2f}` (منطقة بيع)\n"
                    f"✅ الحالة: تم إغلاق الصفقة وجني الأرباح."
                )
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, sell_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
            
    except Exception as e:
        err_msg = str(e)
        last_error = err_msg
        print(f"Error in autonomous trading scan: {err_msg}")
        if TELEGRAM_CHAT_ID:
            bot.send_message(
                TELEGRAM_CHAT_ID, 
                f"⚠️ **تنبيه خطأ في نظام التداول الآلي!**\n`{err_msg}`", 
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
            f"✅ حالة النظام: التداول الآلي يعمل باستقرار تام."
        )
        bot.send_message(TELEGRAM_CHAT_ID, summary_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        print(f"Error sending EOD summary: {e}")

# جدولة المهام (فحص السوق كل 15 دقيقة وتقرير يومي)
schedule.every(15).minutes.do(market_scanning_cycle)
schedule.every().day.at("23:00").do(send_end_of_day_summary)

# رسالة البداية عند التشغيل
if TELEGRAM_CHAT_ID:
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            "🚀 **JALWE AI TRADER V4 Autonomous Mode Online**\nتم تفعيل استراتيجية التداول الذكي (RSI) والربط الفعلي مع Alpaca بنجاح.",
            parse_mode="Markdown",
            reply_markup=get_control_keyboard()
        )
    except Exception as e:
        print(f"Startup message error: {e}")

# تشغيل البوت وتلقي التحديثات في الخلفية
if __name__ == "__main__":
    print("INFO - JALWE AI TRADER V4 Autonomous Mode Online 24/7")
    
    import threading
    def polling_thread():
        bot.infinity_polling(none_stop=True)
    
    t = threading.Thread(target=polling_thread)
    t.daemon = True
    t.start()

    while True:
        schedule.run_pending()
        time.sleep(1)
