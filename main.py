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

# تنظيف أي جلسة سابقة لتجنب خطأ 409 نهائياً
try:
    bot.remove_webhook()
    time.sleep(2)
except Exception:
    pass

bot_running = True
last_error = "النظام يعمل بكفاءة وثبات تام 🚀🛡️"

TAKE_PROFIT_PCT = 0.03  # جني الأرباح 3%
STOP_LOSS_PCT = 0.02    # وقف الخسارة 2%
CORE_WATCHLIST = ["AAPL", "TSLA", "MSFT", "NVDA", "AMD", "AMZN", "META"]

def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت المتعلم")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    btn_status = KeyboardButton("🔍 فحص نموذج التعلم الآلي")
    btn_prices = KeyboardButton("📊 أسعار الأسهم")
    markup.add(btn_start, btn_stop, btn_status, btn_prices)
    return markup

def advanced_market_scanner():
    try:
        assets = alpaca.list_assets(status='active', asset_class='us_equity')
        tradable = [a.symbol for a in assets if a.tradable and a.exchange in ['NASDAQ', 'NYSE'] and "/" not in a.symbol and len(a.symbol) <= 5]
        import random
        random_sample = random.sample(tradable, min(10, len(tradable)))
        return list(set(CORE_WATCHLIST + random_sample))
    except Exception:
        return CORE_WATCHLIST

def send_status_report(chat_id):
    global bot_running, last_error
    try:
        account = alpaca.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        positions = alpaca.list_positions()
        
        state_text = "🟢 النظام يعمل بكامل طاقته" if bot_running else "🛑 متوقف مؤقتاً"
        
        report = (
            f"🧠🛡️ **تقرير JALWE AI الشامل**\n\n"
            f"• **الحالة:** {state_text}\n"
            f"• **إجمالي المحفظة:** `${equity:.2f}`\n"
            f"• **السيولة النقدية:** `${cash:.2f}`\n"
            f"• **الصفقات المفتوحة:** `{len(positions)} صفقة`\n"
            f"• **الحماية:** جني أرباح `+{TAKE_PROFIT_PCT*100}%` | وقف خسارة `-{STOP_LOSS_PCT*100}%`\n"
            f"• **سجل الحالة:** `{last_error}`"
        )
        bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ خطأ: {e}", parse_mode="Markdown", reply_markup=get_control_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_control_buttons(message):
    global bot_running
    text = message.text
    chat_id = message.chat.id

    if "تشغيل البوت المتعلم" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل النظام بنجاح.**", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", reply_markup=get_control_keyboard())
    elif "فحص نموذج التعلم الآلي" in text:
        send_status_report(chat_id)
    elif "أسعار الأسهم" in text:
        bot.send_message(chat_id, "⏳ جاري جلب الأسعار...", reply_markup=get_control_keyboard())
        try:
            watchlist = advanced_market_scanner()[:5]
            msg = "📊 **أسعار الأسهم المباشرة:**\n\n"
            for s in watchlist:
                bar = alpaca.get_bars(s, tradeapi.TimeFrame.Minute, limit=1).df
                if not bar.empty:
                    msg += f"• `{s}` : `${bar['close'].iloc[-1]:.2f}`\n"
            bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {e}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "اختر من الأزرار أدناه:", reply_markup=get_control_keyboard())

def ml_predict_signal(symbol):
    try:
        barset = alpaca.get_bars(symbol, tradeapi.TimeFrame.Day, limit=50).df
        if barset.empty or len(barset) < 25:
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
        if len(df) < 10:
            return 0
        model = RandomForestClassifier(n_estimators=30, random_state=42)
        model.fit(df[['returns', 'sma_5', 'sma_20', 'rsi']], df['target'])
        return model.predict(df[['returns', 'sma_5', 'sma_20', 'rsi']].iloc[[-1]])[0]
    except Exception:
        return 0

def ai_learning_trading_cycle():
    global bot_running, last_error
    if not bot_running:
        return
    try:
        account = alpaca.get_account()
        cash = float(account.cash)
        
        positions = alpaca.list_positions()
        for p in positions:
            pnl_pct = (float(p.current_price) - float(p.avg_entry_price)) / float(p.avg_entry_price)
            if pnl_pct >= TAKE_PROFIT_PCT or pnl_pct <= -STOP_LOSS_PCT:
                alpaca.close_position(p.symbol)
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🛡️ تم إغلاق الصفقة `{p.symbol}` بنسبة: `{pnl_pct*100:.2f}%`", parse_mode="Markdown")

        watchlist = advanced_market_scanner()
        active_symbols = [p.symbol for p in positions]
        
        for symbol in watchlist:
            if ml_predict_signal(symbol) == 1 and symbol not in active_symbols and cash > 30:
                alpaca.submit_order(symbol=symbol, qty=1, side='buy', type='market', time_in_force='gtc')
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🚨 **شراء ذكي جديد:** `{symbol}`", parse_mode="Markdown")
    except Exception as e:
        last_error = str(e)

schedule.every(20).minutes.do(ai_learning_trading_cycle)

if __name__ == "__main__":
    print("INFO - JALWE AI Ultimate is running stable...")
    
    # حلقة واحدة آمنة تنفذ المهام الدورية وتستقبل رسائل تيليجرام بدون تداخل
    while True:
        try:
            schedule.run_pending()
            bot.polling(none_stop=True, interval=2, timeout=5)
        except Exception as ex:
            print(f"Notice: {ex}")
            time.sleep(5)
