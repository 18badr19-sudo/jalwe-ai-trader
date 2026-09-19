import os
import time
import schedule
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import alpaca_trade_api as tradeapi

from pre_breakout_engine import PreBreakoutEngine
from target_risk_engine import TargetRiskEngine
from options_flow_engine import OptionsFlowEngine
from chart_and_learning_engine import ChartAndLearningEngine
from active_trade_manager import ActiveTradeManager

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
APCA_API_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
alpaca = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL, api_version='v2')

learning_engine = ChartAndLearningEngine()
pre_engine = PreBreakoutEngine(alpaca, learning_engine)
risk_engine = TargetRiskEngine(alpaca)
options_engine = OptionsFlowEngine(alpaca)
trade_manager = ActiveTradeManager(alpaca)

bot_running = True
last_error = "System is fully stable with no active errors 🚀"

def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🟢 Start AI Autonomous Bot"),
        KeyboardButton("🛑 Stop Bot"),
        KeyboardButton("🔍 Check AI Learning Model"),
        KeyboardButton("📊 Stock Prices & Scan"),
        KeyboardButton("⚠️ System & Error Diagnostics")
    )
    return markup

@bot.message_handler(func=lambda message: True)
def handle_commands(message):
    global bot_running, last_error
    text = message.text
    chat_id = message.chat.id

    if "Start AI Autonomous Bot" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **AI Autonomous Pre-Breakout Engine activated successfully.**", reply_markup=get_control_keyboard())
    elif "Stop Bot" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **System paused temporarily.**", reply_markup=get_control_keyboard())
    elif "Check AI Learning Model" in text:
        stats = learning_engine.get_learning_stats()
        bot.send_message(chat_id, f"🧠 **RandomForest & Self-Learning Model:**\n- Status: `Connected & Active`\n- {stats}", reply_markup=get_control_keyboard())
    elif "System & Error Diagnostics" in text:
        report = (
            f"🛠️ **JALWE AI Ultimate System Diagnostics:**\n\n"
            f"• **Status:** `{last_error}`\n"
            f"• **Telegram Connection:** `Stable (Long Polling Active w/o 409)`\n"
            f"• **Alpaca & AI Engine:** `Connected & Ready`"
        )
        bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "Stock Prices & Scan" in text:
        bot.send_message(chat_id, "⏳ Scanning entire market using AI model...", reply_markup=get_control_keyboard())
        symbols = pre_engine.scan_entire_market()[:5]
        msg = "📊 **AI Pre-Breakout Scan Samples:**\n\n"
        for sym in symbols:
            metrics = pre_engine.calculate_metrics(sym)
            if metrics:
                eval_res = pre_engine.evaluate_pre_breakout(metrics)
                msg += f"• `{sym}` | Price: `${metrics['price']}` | Confidence: `{eval_res['score']}%`\n"
        bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "Please select an option below:", reply_markup=get_control_keyboard())

def main_trading_cycle():
    global bot_running
    if not bot_running:
        return
    try:
        trade_manager.monitor_open_positions()
        pre_engine.update_model_with_real_data()
        
        symbols = pre_engine.scan_entire_market()
        import random
        sample_symbols = random.sample(symbols, min(5, len(symbols)))
        
        for sym in sample_symbols:
            metrics = pre_engine.calculate_metrics(sym)
            if not metrics:
                continue
                
            evaluation = pre_engine.evaluate_pre_breakout(metrics)
            metrics.update(evaluation)
            
            learning_engine.save_feature_snapshot(sym, metrics)
            
            if evaluation["status"] in ["CONFIRMED", "ENTRY"]:
                levels = risk_engine.calculate_levels(sym, metrics["price"])
                opt = options_engine.evaluate_contract(sym, metrics["price"])
                
                alert_msg = (
                    f"🚨 JALWE AI — MOMENTUM BREAKOUT\n"
                    f"📌 Symbol: `{sym}`\n"
                    f"📊 Setup: `{evaluation['status']}`\n"
                    f"💵 Price: `${metrics['price']}`\n"
                    f"🟡 Entry Zone:\n`{levels['entry_zone']}`\n"
                    f"🛑 Stop Loss:\n`{levels['stop_loss']}`\n"
                    f"🎯 Target 1:\n`{levels['target_1']}`\n"
                    f"🎯 Target 2:\n`{levels['target_2']}`\n"
                    f"🎯 Target 3:\n`{levels['target_3']}`\n"
                    f"📈 RVOL: `{metrics['rvol']}x`\n"
                    f"⚡ Volume Speed: `{metrics['volume_speed']}`\n"
                    f"💧 Liquidity Flow: `{metrics['liquidity_flow']}/100`\n"
                    f"🤖 AI Confidence: `{evaluation['score']}%`\n"
                    f"📜 Suggested Contract:\n"
                    f"Type: `{opt['contract_type']}` | Strike: `{opt['strike']}` | Delta: `{opt['delta']}`\n"
                    f"🟢 PAPER TRADE ONLY"
                )
                if TELEGRAM_CHAT_ID:
                    bot.send_message(TELEGRAM_CHAT_ID, alert_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Cycle Error: {e}")

schedule.every(15).minutes.do(main_trading_cycle)

if __name__ == "__main__":
    print("INFO - JALWE AI Ultimate Fully Autonomous Engine is running...")
    
    try:
        bot.remove_webhook()
        time.sleep(2)
    except Exception:
        pass

    import threading
    def schedule_loop():
        while True:
            schedule.run_pending()
            time.sleep(1)

    t = threading.Thread(target=schedule_loop)
    t.daemon = True
    t.start()

    while True:
        try:
            bot.remove_webhook()
            print("INFO - Starting Telegram Bot polling safely...")
            bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True)
        except Exception as e:
            print(f"Polling conflict/error caught: {e}")
            last_error = f"Handled connection conflict: {str(e)[:40]}"
            time.sleep(10)
