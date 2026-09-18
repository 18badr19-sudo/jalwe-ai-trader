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

# إيقاف أي جلسة سابقة لمنع خطأ التعارض 409
try:
    bot.remove_webhook()
    time.sleep(1)
except Exception:
    pass

bot_running = True
last_error = "النظام مستقر ويعمل بدون خيوط متداخلة ✅"

TAKE_PROFIT_PCT = 0.03  # جني الأرباح 3%
STOP_LOSS_PCT = 0.02    # وقف الخسارة 2%

def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت المتعلم")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    btn_status = KeyboardButton("🔍 فحص نموذج التعلم الآلي")
    btn_prices = KeyboardButton("📊 أسعار الأسهم")
    markup.add(btn_start, btn_stop, btn_status, btn_prices)
    return markup

# ==================== 1. رادار السيولة المفاجئة ====================
def liquidity_radar_scanner():
    try:
        assets = alpaca.list_assets(status='active', asset_class='us_equity')
        tradable_symbols = [
            asset.symbol for asset in assets 
            if asset.tradable and asset.exchange in ['NASDAQ', 'NYSE'] and "/" not in asset.symbol and len(asset.symbol) <= 5
        ]
        
        import random
        sample_symbols = random.sample(tradable_symbols, min(15, len(tradable_symbols)))
        
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
                
        return hot_stocks[:5] if hot_stocks else ["AAPL", "TSLA", "MSFT", "NVDA"]
    except Exception as e:
        print(f"Error in radar: {e}")
        return ["AAPL", "TSLA", "MSFT"]

def send_status_report(chat_id):
    global bot_running, last_error
    try:
        account = alpaca.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        state_text = "🟢 النظام نشط" if bot_running else "🛑 متوقف"
        
        report = (
            f"🛡️ **تقرير نظام JALWE AI**\n\n"
            f"• **الحالة:** {state_text}\n"
            f"• **إجمالي المحفظة:** `${equity:.2f}`\n"
            f"• **الكاش المتاح:** `${cash:.2f}`\n"
            f"• **جني الأرباح:** `+{TAKE_PROFIT_PCT*100}%` | **وقف الخسارة:** `-{STOP_LOSS_PCT*100}%`\n"
            f"• **الحالة:** `{last_error}`"
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
        bot.send_message(chat_id, "🟢 **تم تفعيل البوت بنجاح.**", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", reply_markup=get_control_keyboard())
    elif "فحص نموذج التعلم الآلي" in text:
        send_status_report(chat_id)
    elif "أسعار الأسهم" in text:
        bot.send_message(chat_id, "⏳ جاري الفحص...", reply_markup=get_control_keyboard())
        try:
            watchlist = liquidity_radar_scanner()
            msg = "📊 **الأسهم المرصودة:**\n\n"
            for s in watchlist:
                bar = alpaca.get_bars(s, tradeapi.TimeFrame.Minute, limit=1).df
                if not bar.empty:
                    msg += f"• `{s}` : `${bar['close'].iloc[-1]:.2f}`\n"
            bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {e}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "اختر من الأزرار:", reply_markup=get_control_keyboard())

# ==================== 2. الذكاء الاصطناعي والتداول ====================
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
                    bot.send_message(TELEGRAM_CHAT_ID, f"🛡️ تم إغلاق الصفقة `{p.symbol}` بنسبة ربح/خسارة: `{pnl_pct*100:.2f}%`", parse_mode="Markdown")

        watchlist = liquidity_radar_scanner()
        active_symbols = [p.symbol for p in positions]
        
        for symbol in watchlist:
            if ml_predict_signal(symbol) == 1 and symbol not in active_symbols and cash > 20:
                alpaca.submit_order(symbol=symbol, qty=1, side='buy', type='market', time_in_force='gtc')
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, f"🚨 **شراء سهم جديد:** `{symbol}`", parse_mode="Markdown")
    except Exception as e:
        last_error = str(e)

# ربط الجداول
schedule.every(20).minutes.do(ai_learning_trading_cycle)

if __name__ == "__main__":
    print("INFO - Bot is running cleanly...")
    
    # حلقة التشغيل الأساسية مع معالجة الجدول الزمني والرسائل بشكل آمن
    while True:
        try:
            schedule.run_pending()
            # استخدام polling بمدة قصيرة لكي لا يحدث تعارض مع الجدول
            bot.polling(none_stop=True, interval=1, timeout=3)
        except Exception as ex:
            print(f"Polling loop notice: {ex}")
            time.sleep(3)
