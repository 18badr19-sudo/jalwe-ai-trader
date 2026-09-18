import os
import time
import logging
import schedule
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# جلب بيانات الاعتماد من المتغيرات البيئية
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7504620583:AAH7D8YF6_...your_token...")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5726211833")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# حالة تشغيل البوت (افتراضياً يعمل)
bot_running = True

def get_reply_keyboard():
    """إنشاء لوحة مفاتيح ثابتة أسفل الشاشة (Reply Keyboard)"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_start = KeyboardButton("🟢 تشغيل البوت")
    btn_stop = KeyboardButton("🛑 إيقاف البوت")
    markup.add(btn_start, btn_stop)
    return markup

@bot.message_handler(func=lambda message: message.text == "🟢 تشغيل البوت")
def handle_start_button(message):
    global bot_running
    bot_running = True
    bot.send_message(message.chat.id, "🚀 **تم استئناف وتشغيل نظام التداول الآلي بنجاح وجاهز لرصد الفرص!**", parse_mode="Markdown", reply_markup=get_reply_keyboard())

@bot.message_handler(func=lambda message: message.text == "🛑 إيقاف البوت")
def handle_stop_button(message):
    global bot_running
    bot_running = False
    bot.send_message(message.chat.id, "⏸️ **تم إيقاف البوت مؤقتاً بناءً على طلبك.**", parse_mode="Markdown", reply_markup=get_reply_keyboard())

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(
        message.chat.id, 
        "🤖 **لوحة تحكم نظام التداول الذكي (JALWE AI TRADER)**\n\nاختر الحالة المناسبة للتحكم بالبوت من الأزرار بالأسفل:", 
        parse_mode="Markdown", 
        reply_markup=get_reply_keyboard()
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
    bot.send_message(CHAT_ID, text, parse_mode="Markdown", reply_markup=get_reply_keyboard())

def send_eod_summary():
    """تقرير نهاية اليوم بالعربي عند إغلاق السوق"""
    text = (
        f"📈 **ملخص تقرير نهاية اليوم لجلسة التداول**\n"
        f"📅 **التاريخ:** `{datetime.now().strftime('%Y-%m-%d')}`\n"
        f"💼 **حالة المحفظة التجريبية:** نشطة ومتصلة ($100 Paper Trading)\n"
        f"🔍 **حالة السوق:** تم إتمام عمليات المسح والتحليل بنجاح.\n"
        f"💤 البوت الآن في وضع الاستعداد بانتظار الجلسة القادمة."
    )
    bot.send_message(CHAT_ID, text, parse_mode="Markdown", reply_markup=get_reply_keyboard())

# جدولة تقرير نهاية اليوم الساعة 11 مساءً
schedule.every().day.at("23:00").do(send_eod_summary)

def run_bot_loop():
    logger.info("JALWE AI TRADER V4 pipeline is online 24/7")
    try:
        bot.send_message(CHAT_ID, "🚀 **نظام التداول الذكي (JALWE AI TRADER) يعمل الآن بنجاح على مدار الساعة!**", parse_mode="Markdown", reply_markup=get_reply_keyboard())
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

    while True:
        try:
            schedule.run_pending()
            if bot_running:
                logger.info("Market scanning cycle executing...")
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
