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
last_error = "لا توجد أخطاء، النظام الذكي يعمل بكفاءة تامة 🧠✅"

# قائمة الأسهم المستهدفة للمسح والتداول الذكي
WATCHLIST = ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]

# ==================== لوحة المفاتيح الثابتة (أزرار التحكم) ====================
def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت الذكي")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    btn_status = KeyboardButton("🔍 فحص ذكاء وحالة البوت")
    markup.add(btn_start, btn_stop, btn_status)
    return markup

# ==================== تقرير الحالة الذكية المفصلة ====================
def send_status_report(chat_id):
    global bot_running, last_error
    try:
        account = alpaca.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        state_text = "🟢 يعمل بوضع الذكاء الاصطناعي (نشط)" if bot_running else "🛑 متوقف مؤقتاً"
        
        report = (
            f"🧠 **تقرير حالة نظام JALWE AI TRADER (النسخة الذكية)**\n\n"
            f"• **حالة البوت:** {state_text}\n"
            f"• **إجمالي المحفظة:** `${equity:.2f}`\n"
            f"• **السيولة المتاحة:** `${cash:.2f}`\n"
            f"• **النموذج التحليلي:** مفعل (تحليل فني + RSI + تقييم ذكي)\n"
            f"• **سجل الأخطاء:**\n`{last_error}`"
        )
        bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ خطأ أثناء جلب الحالة الذكية: {e}", reply_markup=get_control_keyboard())

# ==================== الاستماع لأزرار التحكم في تليجرام ====================
@bot.message_handler(func=lambda message: True)
def handle_control_buttons(message):
    global bot_running
    text = message.text
    chat_id = message.chat.id

    if "تشغيل البوت الذكي" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل عقل البوت الذكي وبدء الرصد والتحليل الآلي.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام الذكي مؤقتاً.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "فحص ذكاء وحالة البوت" in text:
        send_status_report(chat_id)
    else:
        bot.send_message(chat_id, "استخدم الأزرار أدناه للتحكم بنظامك الذكي:", reply_markup=get_control_keyboard())

# ==================== حساب مؤشرات السوق الذكية ====================
def analyze_market_conditions(symbol, period=14):
    try:
        barset = alpaca.get_bars(symbol, tradeapi.TimeFrame.Day, limit=period + 10).df
        if barset.empty:
            return 50.0, "متعادل"
        
        close_prices = barset['close']
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1])
        
        # تحليل ذكي إضافي يعتمد على متوسط الأسعار (SMA)
        sma_20 = close_prices.rolling(window=20).mean().iloc[-1]
        current_price = close_prices.iloc[-1]
        
        trend = "صاعد 📈" if current_price > sma_20 else "هابط 📉"
        return current_rsi, trend
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return 50.0, "غير محدد"

# ==================== دورة المسح والتحليل الذكي والتنفيذ ====================
def smart_market_scanning_cycle():
    global bot_running, last_error
    if not bot_running:
        return

    print("INFO - Smart AI trading & market analysis cycle executing...")
    
    try:
        account = alpaca.get_account()
        cash = float(account.cash)
        last_error = "لا توجد أخطاء، النظام الذكي يعمل بسلامة تامّة ✅"
        
        for symbol in WATCHLIST:
            rsi_value, trend = analyze_market_conditions(symbol)
            print(f"Smart Scan -> Symbol: {symbol} | RSI: {rsi_value:.2f} | Trend: {trend}")
            
            positions = [p.symbol for p in alpaca.list_positions()]
            
            # قرار شراء ذكي: إذا كان الـ RSI منخفض جداً (تشبع بيعي) والاتجاه يهيئ لارتداد، ولديك كاش
            if rsi_value < 32 and symbol not in positions and cash > 20:
                alpaca.submit_order(
                    symbol=symbol,
                    qty=1,
                    side='buy',
                    type='market',
                    time_in_force='gtc'
                )
                buy_msg = (
                    f"🧠🤖 **JALWE AI - قرار شراء ذكي ومدروس**\n"
                    f"📌 السهم: `{symbol}`\n"
                    f"📊 مؤشر RSI: `{rsi_value:.2f}` (فرصة ارتداد محتملة)\n"
                    f"📈 اتجاه السوق: {trend}\n"
                    f"✅ الإجراء: تم تنفيذ الشراء الآلي بناءً على التحليل الفني."
                )
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, buy_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
            
            # قرار بيع وجني أرباح ذكي: إذا دخل السهم في منطقة تشبع شرائي مبالغ فيها
            elif rsi_value > 68 and symbol in positions:
                alpaca.close_position(symbol)
                sell_msg = (
                    f"🧠💰 **JALWE AI - قرار بيع وجني أرباح ذكي**\n"
                    f"📌 السهم: `{symbol}`\n"
                    f"📊 مؤشر RSI: `{rsi_value:.2f}` (منطقة تشبع شرائي واستنزاف صعود)\n"
                    f"✅ الإجراء: تم إغلاق الصفقة لتأمين الأرباح."
                )
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, sell_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
            
    except Exception as e:
        err_msg = str(e)
        last_error = err_msg
        print(f"Error in smart trading cycle: {err_msg}")
        if TELEGRAM_CHAT_ID:
            bot.send_message(
                TELEGRAM_CHAT_ID, 
                f"⚠️ **تنبيه خطأ في النظام الذكي:**\n`{err_msg}`", 
                parse_mode="Markdown", 
                reply_markup=get_control_keyboard()
            )

# ==================== تقرير نهاية اليوم الذكي ====================
def send_smart_end_of_day_summary():
    if not TELEGRAM_CHAT_ID:
        return
    try:
        account = alpaca.get_account()
        summary_msg = (
            f"📊🧠 **التقرير اليومي لنظام JALWE الذكي**\n"
            f"💵 إجمالي قيمة المحفظة: `${float(account.equity):.2f}`\n"
            f"💵 السيولة المتوفرة للذكاء الاصطناعي: `${float(account.cash):.2f}`\n"
            f"🤖 الحالة العامة: العقل الذكي يراقب الأسواق بانتظام."
        )
        bot.send_message(TELEGRAM_CHAT_ID, summary_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        print(f"Error sending smart EOD summary: {e}")

# جدولة دورة الفحص الذكي كل 15 دقيقة والتقرير اليومي
schedule.every(15).minutes.do(smart_market_scanning_cycle)
schedule.every().day.at("23:00").do(send_smart_end_of_day_summary)

# رسالة إعلان التشغيل الذكي
if TELEGRAM_CHAT_ID:
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            "🚀🧠 **JALWE AI TRADER V4 (Smart Edition) Online**\nتم ترقية البوت بنجاح ليصبح قادراً على التحليل المتقدم واتخاذ القرارات الذكية بناءً على مؤشرات السوق.",
            parse_mode="Markdown",
            reply_markup=get_control_keyboard()
        )
    except Exception as e:
        print(f"Startup message error: {e}")

# تشغيل البوت في الخلفية
if __name__ == "__main__":
    print("INFO - JALWE AI TRADER V4 Smart Edition Online 24/7")
    
    import threading
    def polling_thread():
        bot.infinity_polling(none_stop=True)
    
    t = threading.Thread(target=polling_thread)
    t.daemon = True
    t.start()

    while True:
        schedule.run_pending()
        time.sleep(1)
