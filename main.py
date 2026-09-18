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

bot = telebot.TeleBot(TELEGRAM_TOKEN)
alpaca = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL, api_version='v2')

# إيقاف أي ويب هوك أو جلسة سابقة لمنع تعارض 409
try:
    bot.remove_webhook()
    time.sleep(1)
except Exception:
    pass

bot_running = True
last_error = "لا توجد أخطاء، عقل التعلم الآلي يعمل بذكاء 🧠✅"
WATCHLIST = ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]

def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت المتعلم")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    btn_status = KeyboardButton("🔍 فحص نموذج التعلم الآلي")
    markup.add(btn_start, btn_stop, btn_status)
    return markup

def send_status_report(chat_id):
    global bot_running, last_error
    try:
        account = alpaca.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        state_text = "🟢 يتعلم ويتداول بذكاء (نشط)" if bot_running else "🛑 متوقف مؤقتاً"
        
        report = (
            f"🧠 **تقرير نموذج التعلم الآلي - JALWE AI**\n\n"
            f"• **حالة النظام:** {state_text}\n"
            f"• **إجمالي المحفظة:** `${equity:.2f}`\n"
            f"• **السيولة المتاحة:** `${cash:.2f}`\n"
            f"• **نموذج الذكاء:** Random Forest Classifier\n"
            f"• **سجل الحالة:**\n`{last_error}`"
        )
        bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ خطأ: {e}", reply_markup=get_control_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_control_buttons(message):
    global bot_running
    text = message.text
    chat_id = message.chat.id

    if "تشغيل البوت المتعلم" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل عقل التعلم الآلي وبدء التدريب والتداول.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "فحص نموذج التعلم الآلي" in text:
        send_status_report(chat_id)
    else:
        bot.send_message(chat_id, "استخدم الأزرار أدناه للتحكم:", reply_markup=get_control_keyboard())

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
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        df = df.dropna()
        if len(df) < 15:
            return 0
        features = ['returns', 'sma_5', 'sma_20', 'rsi']
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(df[features], df['target'])
        return model.predict(df[features].iloc[[-1]])[0]
    except Exception as e:
        print(f"Error in ML prediction for {symbol}: {e}")
        return 0

def ai_learning_trading_cycle():
    global bot_running, last_error
    if not bot_running:
        return
    try:
        account = alpaca.get_account()
        cash = float(account.cash)
        last_error = "لا توجد أخطاء، نموذج التعلم الآلي يعمل بكفاءة ✅"
        for symbol in WATCHLIST:
            prediction = ml_predict_signal(symbol)
            positions = [p.symbol for p in alpaca.list_positions()]
            if prediction == 1 and symbol not in positions and cash > 20:
                alpaca.submit_order(symbol=symbol, qty=1, side='buy', type='market', time_in_force='gtc')
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🧠🤖 **JALWE AI (شراء ذكي)**\n📌 السهم: `{symbol}`", parse_mode="Markdown", reply_markup=get_control_keyboard())
            elif prediction == 0 and symbol in positions:
                alpaca.close_position(symbol)
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🧠💰 **JALWE AI (بيع وجني أرباح)**\n📌 السهم: `{symbol}`", parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        last_error = str(e)

schedule.every(20).minutes.do(ai_learning_trading_cycle)

if __name__ == "__main__":
    print("INFO - JALWE ML Trader Online 24/7")
    import threading
    
    def polling_thread():
        while True:
            try:
                print("Starting Telegram polling...")
                # التعديل هنا: إضافة skip_pending=True لمنع خطأ 409
                bot.infinity_polling(skip_pending=True)
            except Exception as ex:
                print(f"Polling restart due to: {ex}")
                time.sleep(5)
    
    t = threading.Thread(target=polling_thread)
    t.daemon = True
    t.start()

    while True:
        schedule.run_pending()
        time.sleep(1)
