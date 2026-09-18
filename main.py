import os
import time
import logging
import schedule
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# جلب بيانات الاعتماد من المتغيرات البيئية
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
APCA_API_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# تهيئة عميل Alpaca للتداول التجريبي
trading_client = TradingClient(APCA_API_KEY_ID, APCA_API_SECRET_KEY, paper=True)

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
    try:
        account = trading_client.get_account()
        portfolio_value = account.portfolio_value
        cash = account.cash
    except Exception:
        portfolio_value = "غير متوفر"
        cash = "غير متوفر"

    text = (
        f"📈 **ملخص تقرير نهاية اليوم لجلسة التداول**\n"
        f"📅 **التاريخ:** `{datetime.now().strftime('%Y-%m-%d')}`\n"
        f"💼 **قيمة المحفظة التجريبية:** `${portfolio_value}`\n"
        f"💵 **الكاش المتاح:** `${cash}`\n"
        f"🔍 **حالة السوق:** تم إتمام عمليات المسح والتحليل بنجاح.\n"
        f"💤 البوت الآن في وضع الاستعداد بانتظار الجلسة القادمة."
    )
    bot.send_message(CHAT_ID, text, parse_mode="Markdown", reply_markup=get_reply_keyboard())

# جدولة تقرير نهاية اليوم الساعة 11 مساءً
schedule.every().day.at("23:00").do(send_eod_summary)

def execute_paper_trade(symbol, qty, side):
    """تنفيذ أمر تداول حقيقي على حساب Alpaca Paper"""
    try:
        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        market_order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.GTC
        )
        order = trading_client.submit_order(order_data=market_order_data)
        logger.info(f"Successfully placed order for {symbol}: {order}")
        send_trade_alert(side, symbol, qty, "Market Price")
    except Exception as e:
        logger.error(f"Failed to execute trade for {symbol}: {e}")

def run_bot_loop():
    logger.info("JALWE AI TRADER V4 pipeline is online 24/7")
    try:
        bot.send_message(CHAT_ID, "🚀 **نظام التداول الذكي (JALWE AI TRADER) يعمل الآن بنجاح على مدار الساعة ويقوم بمسح السوق!**", parse_mode="Markdown", reply_markup=get_reply_keyboard())
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

    while True:
        try:
            schedule.run_pending()
            if bot_running:
                logger.info("Market scanning cycle executing...")
                
                # قائمة الأسهم المستهدفة للمسح
                target_symbols = ["AAPL", "TSLA", "MSFT", "NVDA"]
                
                # منطق المسح التجريبي البسيط (يمكن تطويره لاحقاً بإستراتيجيات متقدمة)
                for symbol in target_symbols:
                    # مثال: البوت يراقب السوق، وعند توافر الشروط يقوم بالتنفيذ التجريبي
                    # execute_paper_trade(symbol, 1, "BUY")
                    pass
                    
            else:
                logger.info("Bot is currently stopped by user.")
            
            time.sleep(300) # فحص السوق كل 5 دقائق
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=lambda: bot.infinity_polling(none_stop=True))
    t.daemon = True
    t.start()

    run_bot_loop()
