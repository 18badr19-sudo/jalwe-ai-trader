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

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
alpaca = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL, api_version='v2')

try:
    bot.remove_webhook()
    time.sleep(2)
except Exception:
    pass

bot_running = True
last_error = "النظام يعمل بثبات واستقرار تام 🚀"

TAKE_PROFIT_PCT = 0.03
STOP_LOSS_PCT = 0.02
CORE_WATCHLIST = ["AAPL", "TSLA", "MSFT", "NVDA", "AMD"]

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
        return list(set(CORE_WATCHLIST + random.sample(tradable, min(8, len(tradable)))))
    except Exception:
        return CORE_WATCHLIST

def send_status_report(chat_id):
    global bot_running, last_error
    try:
        account = alpaca.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        positions = alpaca.list_positions()
        
        report = (
            f"🧠🛡️ **تقرير JALWE AI**\n\n"
            f"• **الحالة:** {'🟢 يعمل' if bot_running else '🛑 متوقف'}\n"
            f"• **إجمالي المحفظة:** `${equity:.2f}`\n"
            f"• **السيولة النقدية:** `${cash:.2f}`\n"
            f"• **الصفقات المفتوحة:** `{len(positions)}`\n"
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
            msg = "📊 **أسعار الأسهم:**\n\n"
            for s in watchlist:
                bar = alpaca.get_bars(s, tradeapi.TimeFrame.Minute, limit=1).df
                if not bar.empty:
                    msg += f"• `{s}` : `${bar['close'].iloc[-1]:.2f}`\n"
            bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {e}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "اختر من الأزرار:", reply_markup=get_control_keyboard())

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
    except Exception as e:
        last_error = str(e)

schedule.every(20).minutes.do(ai_learning_trading_cycle)

if __name__ == "__main__":
    print("JALWE AI is starting without threads...")
    while True:
        try:
            schedule.run_pending()
            # استخدام infinity_polling مع تععطيل الـ threads لمنع التعارض نهائياً
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as ex:
            print(f"Polling error: {ex}")
            time.sleep(5)
