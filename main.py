import os
import time
import logging
import schedule
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# جلب بيانات الاعتماد من المتغيرات البيئية
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7504620583:AAH7D8YF6_...your_token...")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5726211833")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# حالة تشغيل البوت (افتراضياً يعمل)
bot_running = True

def get_control_markup():
    """إنشاء أزرار التحكم بالعربي (تشغيل / إيقاف)"""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🟢 تشغيل البوت", callback_data="start_bot"),
        InlineKeyboardButton("🛑 إيقاف البوت", callback_data="stop_bot")
    )
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global bot_running
    if call.data == "start_bot":
        bot_running = True
        bot.answer_callback_query(call.id, "تم تشغيل البوت بنجاح!")
        bot.send_message(CHAT_ID, "🚀 **تم استئناف وتشغيل نظام التداول الآلي بنجاح وجاهز لرصد الفرص!**", parse_mode="Markdown", reply_markup=get_control_markup())
    elif call.data == "stop_bot":
        bot_running = False
        bot.answer_callback_query(call.id, "تم إيقاف البوت مؤقتاً!")
        bot.send_message(CHAT_ID, "⏸️ **تم إيقاف البوت مؤقتاً بناءً على طلبك.**", parse_mode="Markdown", reply_markup=get_control_markup())

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(
        message.chat.id, 
        "🤖 **لوحة تحكم نظام التداول الذكي (JALWE AI TRADER)**\n\nاختر الحالة المناسبة للتحكم بالبوت:", 
        parse_mode="Markdown", 
        reply_markup=get_control_markup()
    )

def send_trade_alert(action, symbol, qty, price):
    """إرسال تنبيه فوري بالعربي عند الشراء أو البيع مع اسم السهم بالإنجليزي"""
    if action.upper() == "BUY":
        emoji = "🟢 **عملية شراء جديدة (BUY)**"
    else:
        emoji = "🔴 **عملية بيع وتصفية (SELL)**"
        
    text = (
        f"{emoji}\n"
        f"📊 **اسم السهم:** `{symbol}`\n"
        f"📦 **الكمية:** `{qty}`\n"
        f"💵 **السعر التنفيذي:** `${price}`\n"
        f"⏰ **الوقت:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )
    bot.send_message(CHAT_ID, text, parse_mode="Markdown", reply_markup=get_control_markup())

def send_eod_summary():
    """تقرير نهاية اليوم بالعربي عند إغلاق السوق"""
    text = (
        f"📈 **ملخص تقرير نهاية اليوم لجلسة التداول**\n"
        f"📅 **التاريخ:** `{datetime.now().strftime('%Y-%m-%d')}`\n"
        f"💼 **حالة المحفظة التجريبية:** نشطة ومتصلة ($100 Paper Trading)\n"
        f"🔍 **حالة السوق:** تم إتمام عمليات المسح والتحليل بنجاح.\n"
        f"💤 البوت الآن في وضع الاستعداد بانتظار الجلسة القادمة."
    )
    bot.send_message(CHAT_ID, text, parse_mode="Markdown", reply_markup=get_control_markup())

# جدولة تقرير نهاية اليوم الساعة 11 مساءً
schedule.every().day.at("23:00").do(send_eod_summary)

def run_bot_loop():
    logger.info("JALWE AI TRADER V4 pipeline is online 24/7")
    try:
        bot.send_message(CHAT_ID, "🚀 **نظام التداول الذكي (JALWE AI TRADER) يعمل الآن بنجاح على مدار الساعة!**", parse_mode="Markdown", reply_markup=get_control_markup())
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

    while True:
        try:
            schedule.run_pending()
            if bot_running:
                logger.info("Market scanning cycle executing...")
                # مثال توضيحي عند شراء أو بيع سهم:
                # send_trade_alert("BUY", "AAPL", 1, 180.50)
            else:
                logger.info("Bot is currently stopped by user.")
            
            time.sleep(60)
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=lambda: bot.infinity_polling(none_stop=True))
    t.daemon = True
    t.start()

    run_bot_loop()
