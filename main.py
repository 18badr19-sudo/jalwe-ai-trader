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
last_error = "النظام يعمل بكفاءة مع إدارة المخاطر الآلية 🛡️🧠"

# إعدادات نسبة جني الأرباح ووقف الخسارة
TAKE_PROFIT_PCT = 0.03  # جني الأرباح عند تحقيق 3% ربح
STOP_LOSS_PCT = 0.02    # وقف الخسارة عند بلوغ 2% خسارة

def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت المتعلم")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    btn_status = KeyboardButton("🔍 فحص نموذج التعلم الآلي")
    btn_prices = KeyboardButton("📊 أسعار الأسهم")
    markup.add(btn_start, btn_stop, btn_status, btn_prices)
    return markup

# ==================== 1. رادار السيولة المفاجئة (Market Scanner) ====================
def liquidity_radar_scanner():
    try:
        assets = alpaca.list_assets(status='active', asset_class='us_equity')
        tradable_symbols = [
            asset.symbol for asset in assets 
            if asset.tradable and asset.exchange in ['NASDAQ', 'NYSE'] and "/" not in asset.symbol and len(asset.symbol) <= 5
        ]
        
        import random
        sample_symbols = random.sample(tradable_symbols, min(20, len(tradable_symbols)))
        
        hot_stocks = []
        for symbol in sample_symbols:
            try:
                bars = alpaca.get_bars(symbol, tradeapi.TimeFrame.Day, limit=5).df
                if not bars.empty and len(bars) >= 5:
                    avg_volume = bars['volume'][:-1].mean()
                    latest_volume = bars['volume'].iloc[-1]
                    if avg_volume > 0 and latest_volume > (avg_volume * 1.5):
                        hot_stocks.append(symbol)
            except Exception:
                continue
                
        if hot_stocks:
            return hot_stocks[:6]
        else:
            return ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]
            
    except Exception as e:
        print(f"Error in liquidity radar: {e}")
        return ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]

def send_status_report(chat_id):
    global bot_running, last_error
    try:
        account = alpaca.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        state_text = "🟢 النظام نشط (الرادار + الذكاء + إدارة المخاطر)" if bot_running else "🛑 متوقف مؤقتاً"
        
        report = (
            f"🛡️ **تقرير نظام الحماية وإدارة المخاطر - JALWE AI**\n\n"
            f"• **حالة النظام:** {state_text}\n"
            f"• **إجمالي المحفظة:** `${equity:.2f}`\n"
            f"• **السيولة المتاحة:** `${cash:.2f}`\n"
            f"• **جني الأرباح (Take Profit):** `+{TAKE_PROFIT_PCT*100}%`\n"
            f"• **وقف الخسارة (Stop Loss):** `-{STOP_LOSS_PCT*100}%`\n"
            f"• **سجل الحالة:**\n`{last_error}`"
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
        bot.send_message(chat_id, "🟢 **تم تفعيل البوت بالكامل (الرادار + الذكاء الاصطناعي + حماية المخاطر).**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "فحص نموذج التعلم الآلي" in text:
        send_status_report(chat_id)
    elif "أسعار الأسهم" in text:
        bot.send_message(chat_id, "⏳ جاري فحص الأسعار مع رادار السيولة...", reply_markup=get_control_keyboard())
        try:
            active_watchlist = liquidity_radar_scanner()
            prices_msg = "📊 **أسعار الأسهم المرصودة (مباشر):**\n\n"
            for symbol in active_watchlist[:6]:
                bar = alpaca.get_bars(symbol, tradeapi.TimeFrame.Minute, limit=1).df
                if not bar.empty:
                    current_price = bar['close'].iloc[-1]
                    prices_msg += f"• `{symbol}` : `${current_price:.2f}` 🛡️\n"
                else:
                    prices_msg += f"• `{symbol}` : `غير متاح`\n"
            bot.send_message(chat_id, prices_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ في جلب الأسعار: {e}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "استخدم الأزرار أدناه للتحكم:", reply_markup=get_control_keyboard())

# ==================== 2. عقل التحليل والقرار (Random Forest) ====================
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

# ==================== 3. دورة الفحص وإدارة المخاطر والتداول ====================
def ai_learning_trading_cycle():
    global bot_running, last_error
    if not bot_running:
        return
    try:
        account = alpaca.get_account()
        cash = float(account.cash)
        last_error = "النظام يعمل بكفاءة مع المراقبة الآلية للحماية ✅"
        
        positions = alpaca.list_positions()
        for p in positions:
            symbol = p.symbol
            avg_entry_price = float(p.avg_entry_price)
            current_price = float(p.current_price)
            pnl_pct = (current_price - avg_entry_price) / avg_entry_price
            
            if pnl_pct >= TAKE_PROFIT_PCT:
                alpaca.close_position(symbol)
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🎯💰 **تم جني الأرباح بنجاح (Take Profit)**\n📌 السهم: `{symbol}`\n📈 نسبة الربح: `+{pnl_pct*100:.2f}%`", parse_mode="Markdown", reply_markup=get_control_keyboard())
            elif pnl_pct <= -STOP_LOSS_PCT:
                alpaca.close_position(symbol)
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🛡️🛑 **تفعيل وقف الخسارة لحماية رأس المال (Stop Loss)**\n📌 السهم: `{symbol}`\n📉 نسبة الخسارة: `{pnl_pct*100:.2f}%`", parse_mode="Markdown", reply_markup=get_control_keyboard())

        dynamic_watchlist = liquidity_radar_scanner()
        active_symbols = [p.symbol for p in positions]
        
        for symbol in dynamic_watchlist:
            prediction = ml_predict_signal(symbol)
            if prediction == 1 and symbol not in active_symbols and cash > 20:
                alpaca.submit_order(symbol=symbol, qty=1, side='buy', type='market', time_in_force='gtc')
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🚨📊 **رادار السيولة (شراء جديد)**\n📌 السهم: `{symbol}`\n💡 دخول سيولة + تأكيد نموذج الذكاء الاصطناعي!", parse_mode="Markdown", reply_markup=get_control_keyboard())
            elif prediction == 0 and symbol in active_symbols:
                alpaca.close_position(symbol)
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🧠🔄 **JALWE AI (إغلاق الصفقة لتغير الاتجاه)**\n📌 السهم: `{symbol}`", parse_mode="Markdown", reply_markup=get_control_keyboard())
    except Exception as e:
        last_error = str(e)

schedule.every(20).minutes.do(ai_learning_trading_cycle)

if __name__ == "__main__":
    print("INFO - JALWE Dual-AI Liquid Radar Trader with Risk Management Online 24/7")
    
    # تشغيل الجدول الزمني في الخلفية عبر Thread منفصل لضمان عدم تعارض الـ Polling
    import threading
    def schedule_thread():
        while True:
            schedule.run_pending()
            time.sleep(1)

    t_schedule = threading.Thread(target=schedule_thread)
    t_schedule.daemon = True
    t_schedule.start()

    # تشغيل البوت الأساسي مباشرة بدون تعارضات
    while True:
        try:
            print("Starting Telegram polling...")
            bot.infinity_polling(skip_pending=True, none_stop=True)
        except Exception as ex:
            print(f"Polling restart due to: {ex}")
            time.sleep(5)
