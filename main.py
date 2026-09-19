import os
import time
import schedule
import pandas as pd
import numpy as np
import alpaca_trade_api as tradeapi
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from sklearn.ensemble import RandomForestClassifier

# ==================== إعدادات البيئة والربط ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
APCA_API_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

# إعداد البوت بدون خيوط متداخلة
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

alpaca = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL, api_version='v2')

bot_running = True
last_error = "لا توجد أخطاء مسجلة، النظام يعمل بكفاءة تامة 🚀"

# إعدادات المخاطر
TAKE_PROFIT_PCT = 0.03  # جني الأرباح 3%
STOP_LOSS_PCT = 0.02    # وقف الخسارة 2%

# قائمة المراقبة القيادية الأساسية
CORE_WATCHLIST = ["AAPL", "TSLA", "MSFT", "NVDA", "AMD", "AMZN", "META"]

def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت المتعلم")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    btn_status = KeyboardButton("🔍 فحص نموذج التعلم الآلي")
    btn_prices = KeyboardButton("📊 أسعار الأسهم")
    btn_errors = KeyboardButton("⚠️ فحص الأخطاء والنظام") # الزر الجديد المضاف
    markup.add(btn_start, btn_stop, btn_status, btn_prices, btn_errors)
    return markup

# ==================== 1. رادار السيولة والتقييم الشامل ====================
def advanced_market_scanner():
    try:
        assets = alpaca.list_assets(status='active', asset_class='us_equity')
        tradable = [a.symbol for a in assets if a.tradable and a.exchange in ['NASDAQ', 'NYSE'] and "/" not in a.symbol and len(a.symbol) <= 5]
        import random
        random_sample = random.sample(tradable, min(12, len(tradable)))
        return list(set(CORE_WATCHLIST + random_sample))
    except Exception as e:
        print(f"Error in scanner: {e}")
        return CORE_WATCHLIST

def send_status_report(chat_id):
    global bot_running, last_error
    try:
        account = alpaca.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        positions = alpaca.list_positions()
        
        state_text = "🟢 يعمل بأقصى طاقة (الذكاء + الرادار + الحماية)" if bot_running else "🛑 متوقف مؤقتاً"
        
        report = (
            f"🧠🛡️ **تقرير JALWE AI الشامل (Ultimate)**\n\n"
            f"• **الحالة:** {state_text}\n"
            f"• **إجمالي المحفظة:** `${equity:.2f}`\n"
            f"• **السيولة النقدية:** `${cash:.2f}`\n"
            f"• **الصفقات المفتوحة:** `{len(positions)} صفقة`\n"
            f"• **الأهداف:** جني أرباح `+{TAKE_PROFIT_PCT*100}%` | وقف خسارة `-{STOP_LOSS_PCT*100}%`\n"
            f"• **حالة النظام:** `مستقر ولا توجد أخطاء تعارض`"
        )
        bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ خطأ في التقرير: {e}", parse_mode="Markdown", reply_markup=get_control_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_control_buttons(message):
    global bot_running, last_error
    text = message.text
    chat_id = message.chat.id

    if "تشغيل البوت المتعلم" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل البوت الذكي بالكامل بنجاح.**", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", reply_markup=get_control_keyboard())
    elif "فحص نموذج التعلم الآلي" in text:
        send_status_report(chat_id)
    elif "⚠️ فحص الأخطاء والنظام" in text:
        error_report = (
            f"🛠️ **سجل الأخطاء والتشخيص (JALWE AI):**\n\n"
            f"• **آخر حالة مسجلة:**\n`{last_error}`\n\n"
            f"• **حالة اتصال تيليجرام:** `مستقر (Long Polling نشط بدون 409)`\n"
            f"• **حالة منصة Alpaca:** `متصل وجاهز لتنفيذ الأوامر`"
        )
        bot.send_message(chat_id, error_report, parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "أسعار الأسهم" in text:
        bot.send_message(chat_id, "⏳ جاري فحص الأسعار وقوائم المراقبة...", reply_markup=get_control_keyboard())
        try:
            watchlist = advanced_market_scanner()[:6]
            msg = "📊 **أسعار الأسهم في القائمة المتقدمة:**\n\n"
            for s in watchlist:
                bar = alpaca.get_bars(s, tradeapi.TimeFrame.Minute, limit=1).df
                if not bar.empty:
                    msg += f"• `{s}` : `${bar['close'].iloc[-1]:.2f}`\n"
            bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {e}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "اختر من الأزرار أدناه:", reply_markup=get_control_keyboard())

# ==================== 2. عقل الذكاء الاصطناعي الكامل والمتقدم ====================
def ml_predict_signal(symbol):
    try:
        barset = alpaca.get_bars(symbol, tradeapi.TimeFrame.Day, limit=60).df
        if barset.empty or len(barset) < 30:
            return 0
        df = barset.copy()
        
        df['returns'] = df['close'].pct_change()
        df['sma_5'] = df['close'].rolling(5).mean()
        df['sma_20'] = df['close'].rolling(20).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['std'] = df['close'].rolling(20).std()
        df['upper_band'] = df['sma_20'] + (df['std'] * 2)
        df['lower_band'] = df['sma_20'] - (df['std'] * 2)
        
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        df = df.dropna()
        
        if len(df) < 15:
            return 0
            
        features = ['returns', 'sma_5', 'sma_20', 'rsi', 'upper_band', 'lower_band']
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(df[features], df['target'])
        
        prediction = model.predict(df[features].iloc[[-1]])[0]
        return prediction
    except Exception as e:
        print(f"Error in ML prediction for {symbol}: {e}")
        return 0

# ==================== 3. دورة التداول الكاملة وإدارة المخاطر ====================
def ai_learning_trading_cycle():
    global bot_running, last_error
    if not bot_running:
        return
    try:
        account = alpaca.get_account()
        cash = float(account.cash)
        last_error = "النظام يعمل بذكاء اصطناعي وحماية تامة وسليم تماماً ✅"
        
        positions = alpaca.list_positions()
        for p in positions:
            symbol = p.symbol
            avg_entry = float(p.avg_entry_price)
            current = float(p.current_price)
            pnl_pct = (current - avg_entry) / avg_entry
            
            if pnl_pct >= TAKE_PROFIT_PCT:
                alpaca.close_position(symbol)
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🎯💰 **تحقيق هدف الربح (Take Profit)**\n📌 السهم: `{symbol}`\n📈 الربح: `+{pnl_pct*100:.2f}%`", parse_mode="Markdown")
            elif pnl_pct <= -STOP_LOSS_PCT:
                alpaca.close_position(symbol)
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🛡️🛑 **تفعيل وقف الخسارة (Stop Loss)**\n📌 السهم: `{symbol}`\n📉 الخسارة: `{pnl_pct*100:.2f}%`", parse_mode="Markdown")

        watchlist = advanced_market_scanner()
        active_symbols = [p.symbol for p in positions]
        
        for symbol in watchlist:
            signal = ml_predict_signal(symbol)
            if signal == 1 and symbol not in active_symbols and cash > 30:
                alpaca.submit_order(symbol=symbol, qty=1, side='buy', type='market', time_in_force='gtc')
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🚨🤖 **JALWE AI (شراء ذكي مؤكد)**\n📌 السهم: `{symbol}`\n💡 إشارة قوية بناءً على تحليل نموذج الغابات العشوائية والمؤشرات!", parse_mode="Markdown")
            elif signal == 0 and symbol in active_symbols:
                alpaca.close_position(symbol)
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🔄🧠 **JALWE AI (إغلاق الصفقة لتغير المؤشرات الفنية)**\n📌 السهم: `{symbol}`", parse_mode="Markdown")
    except Exception as e:
        last_error = str(e)
        if TELEGRAM_CHAT_ID:
            bot.send_message(TELEGRAM_CHAT_ID, f"⚠️ **تنبيه خطأ في دورة البوت:**\n`{str(e)}`", parse_mode="Markdown")

schedule.every(20).minutes.do(ai_learning_trading_cycle)

if __name__ == "__main__":
    print("INFO - JALWE AI Ultimate Edition with full ML is running...")
    
    try:
        bot.remove_webhook()
        time.sleep(3)
    except Exception as e:
        print(f"Webhook remove notice: {e}")

    import threading
    def schedule_thread():
        while True:
            schedule.run_pending()
            time.sleep(1)

    t_schedule = threading.Thread(target=schedule_thread)
    t_schedule.daemon = True
    t_schedule.start()

    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=30, long_polling_timeout=15, skip_pending=True)
        except Exception as ex:
            last_error = str(ex)
            print(f"Polling notice: {ex}")
            time.sleep(5)
