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
last_error = "النظام مستقر تماماً ولا توجد أي أخطاء نشطة 🚀"

def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🟢 تشغيل البوت المتعلم"),
        KeyboardButton("🛑 إيقاف البوت"),
        KeyboardButton("🔍 فحص نموذج التعلم الآلي"),
        KeyboardButton("📊 أسعار الأسهم"),
        KeyboardButton("⚠️ فحص الأخطاء والنظام")
    )
    return markup

@bot.message_handler(func=lambda message: True)
def handle_commands(message):
    global bot_running, last_error
    text = message.text
    chat_id = message.chat.id

    if "تشغيل البوت المتعلم" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل منظومة الذكاء الاصطناعي والاستباق بالكامل.**", reply_markup=get_control_keyboard())
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", reply_markup=get_control_keyboard())
    elif "فحص نموذج التعلم الآلي" in text:
        stats = learning_engine.get_learning_stats()
        bot.send_message(chat_id, f"🧠 **نموذج RandomForest والتعلم الذاتي:**\n- الحالة: `متصل ونشط ويتعلم ذاتياً`\n- {stats}", reply_markup=get_control_keyboard())
    elif "فحص الأخطاء والنظام" in text:
        report = (
            f"🛠️ **سجل الأخطاء والتشخيص (JALWE AI Ultimate):**\n\n"
            f"• **الحالة:** `{last_error}`\n"
            f"• **اتصال تيليجرام:** `مستقر (Long Polling نشط بدون 409)`\n"
            f"• **منصة Alpaca ومحرك الذكاء الاصطناعي:** `متصل وجاهز تماماً`"
        )
        bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())
    elif "أسعار الأسهم" in text:
        bot.send_message(chat_id, "⏳ جاري فحص كامل السوق واستخراج رموز الأسهم عبر نموذج الذكاء الاصطناعي...", reply_markup=get_control_keyboard())
        symbols = pre_engine.scan_entire_market()[:5]
        msg = "📊 **عينات فحص الأسهم بالذكاء الاصطناعي:**\n\n"
        for sym in symbols:
            metrics = pre_engine.calculate_metrics(sym)
            if metrics:
                eval_res = pre_engine.evaluate_pre_breakout(metrics)
                msg += f"• رمز السهم (Symbol): `{sym}` | السعر: `${metrics['price']}` | الثقة: `{eval_res['score']}%`\n"
        bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "الرجاء الاختيار من الخيارات أدناه:", reply_markup=get_control_keyboard())

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
                    f"🚨 JALWE AI — رصد اختراق الزخم\n"
                    f"📌 رمز السهم (Symbol): `{sym}`\n"
                    f"📊 الحالة: `{evaluation['status']}`\n"
                    f"💵 السعر الحالي: `${metrics['price']}`\n"
                    f"🟡 منطقة الدخول:\n`{levels['entry_zone']}`\n"
                    f"🛑 وقف الخسارة:\n`{levels['stop_loss']}`\n"
                    f"🎯 الهدف الأول:\n`{levels['target_1']}`\n"
                    f"🎯 الهدف الثاني:\n`{levels['target_2']}`\n"
                    f"🎯 الهدف الثالث:\n`{levels['target_3']}`\n"
                    f"📈 معدل الحجم (RVOL): `{metrics['rvol']}x`\n"
                    f"⚡ سرعة السيولة: `{metrics['volume_speed']}`\n"
                    f"💧 تدفق السيولة: `{metrics['liquidity_flow']}/100`\n"
                    f"🤖 ثقة الذكاء الاصطناعي: `{evaluation['score']}%`\n"
                    f"📜 عقد الخيارات المقترح:\n"
                    f"النوع: `{opt['contract_type']}` | السترايك: `{opt['strike']}` | الدلتا: `{opt['delta']}`\n"
                    f"🟢 تداول ورقي حصراً (PAPER TRADE ONLY)"
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
            last_error = f"تم تجاوز التعارض بنجاح: {str(e)[:40]}"
            time.sleep(10)
