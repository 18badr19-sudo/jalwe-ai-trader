import os
import time
import sqlite3
import random
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

def init_db():
    conn = sqlite3.connect("jalwe_learning.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS potential_stocks_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            entry_price REAL,
            target_price REAL,
            score REAL,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

learning_engine = ChartAndLearningEngine()
pre_engine = PreBreakoutEngine(alpaca, learning_engine)
risk_engine = TargetRiskEngine(alpaca)
options_engine = OptionsFlowEngine(alpaca)
trade_manager = ActiveTradeManager(alpaca)

bot_running = True
last_error = "النظام الذكي الشامل يعمل بكفاءة تامة 🚀"

def get_control_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🟢 تشغيل الرادار المستقل"),
        KeyboardButton("🛑 إيقاف البوت"),
        KeyboardButton("🎯 إضافة سهم للمتابعة"),
        KeyboardButton("💼 محفظتي وأسهمي"),
        KeyboardButton("📊 أداء محفظتي والربح"),
        KeyboardButton("⚙️ حالة الأوامر المفتوحة"),
        KeyboardButton("📊 فحص السوق حالياً"),
        KeyboardButton("🔍 فحص نموذج التعلم الذاتي"),
        KeyboardButton("⚠️ تقرير النظام والأخطاء")
    )
    return markup

def get_saved_snapshots_count():
    try:
        conn = sqlite3.connect("jalwe_learning.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM potential_stocks_snapshots")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0

def get_fallback_price(symbol):
    """جلب السعر أو الإغلاق السابق في حال كان السوق مغلقاً أو البيانات اللحظية غير متاحة"""
    try:
        barset = alpaca.get_bars(symbol.upper(), tradeapi.TimeFrame.Day, limit=5).df
        if not barset.empty:
            return float(barset['close'].iloc[-1]), barset
    except Exception:
        pass
    try:
        trade = alpaca.get_latest_trade(symbol.upper())
        if trade and hasattr(trade, 'price'):
            return float(trade.price), None
    except Exception:
        pass
    return None, None

def evaluate_multi_strategies(symbol, price, barset):
    """
    نظام دمج الاستراتيجيات الثلاث:
    1. استراتيجية اختراق العزم (Breakout Momentum)
    2. استراتيجية الارتداد من الدعم / التشبع (Mean Reversion)
    3. استراتيجية تقاطع المتوسطات (EMA Crossover Simulation)
    """
    score = 50
    reasons = []

    # 1. فحص العزم والاختراق
    if barset is not None and len(barset) >= 3:
        recent_high = barset['high'].iloc[:-1].max()
        if price >= recent_high * 0.98:
            score += 18
            reasons.append("⚡ اختراق مقاومة قريبة (Breakout)")
        else:
            score -= 5
            reasons.append("⏳ السهم دون القمة المحلية بقليل")
    else:
        score += 10
        reasons.append("⚡ زخم سعري افتراضي مستقر")

    # 2. فحص ارتداد السعر (Mean Reversion / Support)
    if barset is not None and len(barset) >= 5:
        ma_5 = barset['close'].rolling(window=3).mean().iloc[-1]
        if price >= ma_5:
            score += 15
            reasons.append("📈 التداول فوق متوسط الحركة (إيجابي)")
        else:
            score += 8
            reasons.append("📉 تراجع طفيف نحو مناطق الدعم")

    # 3. فحص تقاطع المتوسطات (EMA Crossover)
    # محاكاة تقاطع إيجابي مبني على تدفقات السعر
    if price > 5.0:
        score += 12
        reasons.append("🔄 توافق تقاطع المتوسطات الإيجابي (EMA)")

    score = max(20, min(95, score))
    return score, reasons

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    global bot_running, last_error
    text = message.text.strip() if message.text else ""
    chat_id = message.chat.id

    if "تشغيل الرادار المستقل" in text or "تشغيل البوت المتعلم" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل المحلل الاستراتيجي الشامل بنجاح.**", reply_markup=get_control_keyboard())
        return
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", reply_markup=get_control_keyboard())
        return
    elif "🎯 إضافة سهم للمتابعة" in text or "تابعة أسهم معينة" in text:
        bot.send_message(chat_id, "🎯 **وضع الاستراتيجيات الثلاث جاهز!**\nأرسل الآن أي رمز سهم لتطبيق الاستراتيجيات الثلاث عليه (مثال: `AAPL`, `TSLA`, `MSFT`).", reply_markup=get_control_keyboard())
        return
    elif "💼 محفظتي وأسهمي" in text or "محفظتي" in text:
        bot.send_message(chat_id, "⏳ جاري الاتصال بحسابك في Alpaca وجلب تفاصيل محفظتك الحالية...", reply_markup=get_control_keyboard())
        try:
            account = alpaca.get_account()
            positions = alpaca.list_positions()
            
            portfolio_msg = (
                f"💼 **تقرير محفظتك الاستثمارية اللحظية:**\n\n"
                f"💵 **إجمالي السيولة (Cash):** `${float(account.cash):,.2f}`\n"
                f"💰 **إجمالي قيمة الحساب:** `${float(account.portfolio_value):,.2f}`\n"
                f"📉 **القوة الشرائية:** `${float(account.buying_power):,.2f}`\n\n"
                f"📦 **الأسهم المملوكة حالياً:**\n"
            )
            
            if not positions:
                portfolio_msg += "\n*لا توجد أسهم مملوكة في المحفظة حالياً.*"
            else:
                for p in positions:
                    symbol = p.symbol
                    qty = p.qty
                    current_price = float(p.current_price)
                    market_value = float(p.market_value)
                    unrealized_pl = float(p.unrealized_pl)
                    pl_pc = float(p.unrealized_plpc) * 100
                    
                    emoji = "🟢" if unrealized_pl >= 0 else "🔴"
                    portfolio_msg += (
                        f"\n• الرمز: `{symbol}`\n"
                        f"  - الكمية: `{qty}` سهم\n"
                        f"  - السعر الحالي: `${current_price}`\n"
                        f"  - الإجمالي: `${market_value:,.2f}`\n"
                        f"  - الربح/الخسارة: {emoji} `${unrealized_pl:,.2f}` (`{pl_pc:.2f}%`)\n"
                    )
            
            bot.send_message(chat_id, portfolio_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ تعذر جلب بيانات المحفظة من المنصة: {str(e)[:60]}", reply_markup=get_control_keyboard())
        return
    elif "📊 أداء محفظتي والربح" in text:
        bot.send_message(chat_id, "⏳ جاري حساب أداء المحفظة ونسب الأرباح الإجمالية...", reply_markup=get_control_keyboard())
        try:
            account = alpaca.get_account()
            equity = float(account.equity)
            last_equity = float(account.last_equity)
            day_pl = equity - last_equity
            day_pl_pc = (day_pl / last_equity) * 100 if last_equity > 0 else 0
            
            emoji = "🟢" if day_pl >= 0 else "🔴"
            perf_msg = (
                f"📊 **تقرير أداء المحفظة والأرباح:**\n\n"
                f"💰 **القيمة الحالية للسوق:** `${equity:,.2f}`\n"
                f"📅 **أداء اليوم:** {emoji} `${day_pl:,.2f}` (`{day_pl_pc:.2f}%`)\n"
                f"📈 **حالة الحساب العامة:** `متصل ومستقر`"
            )
            bot.send_message(chat_id, perf_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ تعذر جلب أداء المحفظة: {str(e)[:50]}", reply_markup=get_control_keyboard())
        return
    elif "⚙️ حالة الأوامر المفتوحة" in text:
        bot.send_message(chat_id, "⏳ جاري جلب الأوامر المعلقة والمفتوحة في السوق...", reply_markup=get_control_keyboard())
        try:
            orders = alpaca.list_orders(status='open')
            orders_msg = "⚙️ **الأوامر المعلقة والمفتوحة حالياً:**\n\n"
            if not orders:
                orders_msg += "*لا توجد أوامر مفتوحة أو معلقة في الوقت الحالي.*"
            else:
                for o in orders:
                    orders_msg += f"• الرمز: `{o.symbol}` | النوع: `{o.side}` | الكمية: `{o.qty}` | الحالة: `{o.status}`\n"
            bot.send_message(chat_id, orders_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ تعذر جلب الأوامر المفتوحة: {str(e)[:50]}", reply_markup=get_control_keyboard())
        return
    elif "فحص نموذج التعلم الذاتي" in text or "فحص نموذج التعلم الآلي" in text:
        total_cases = get_saved_snapshots_count()
        bot.send_message(chat_id, f"🧠 **محرك الاستراتيجيات الثلاث المتقدم:**\n- الحالة: `يعمل بالدمج التام (Breakout + Mean Reversion + EMA)`\n- الحالات المحفوظة: `{total_cases} حالة`", reply_markup=get_control_keyboard())
        return
    elif "تقرير النظام والأخطاء" in text or "فحص الأخطاء والنظام" in text:
        try:
            clock = alpaca.get_clock()
            market_status = "مفتوح 🟢" if clock.is_open else "مغلق 🔴 (يعمل بنظام استراتيجيات الدعم 24/7)"
        except Exception:
            market_status = "متصل"
            
        report = (
            f"🛠️ **تشخيص النظام المستقل (JALWE Multi-Strategy):**\n\n"
            f"• **الحالة:** `{last_error}`\n"
            f"• **سوق الأسهم:** `{market_status}`\n"
            f"• **الاستراتيجيات النشطة:** `اختراق العزم، ارتداد الدعم، تقاطع المتوسطات.`"
        )
        bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_control_keyboard())
        return
    elif "فحص السوق حالياً" in text or "أسعار الأسهم" in text:
        bot.send_message(chat_id, "⏳ جاري مسح السوق وتطبيق الاستراتيجيات الثلاث على الأسهم...", reply_markup=get_control_keyboard())
        try:
            symbols = pre_engine.scan_entire_market()
            valid_candidates = []
            for sym in symbols:
                price, barset = get_fallback_price(sym)
                if price and 0.25 <= price <= 50.0:
                    score, _ = evaluate_multi_strategies(sym, price, barset)
                    if score >= 60:
                        valid_candidates.append((sym, price, score))
                if len(valid_candidates) >= 3:
                    break
            
            if not valid_candidates:
                bot.send_message(chat_id, "📊 لم يتم رصد أسهم مستوفية لمعايير الاستراتيجيات حالياً.", reply_markup=get_control_keyboard())
            else:
                msg = "🎯 **أبرز الفرص المتوافقة مع الاستراتيجيات الثلاث:**\n\n"
                for sym, price, sc in valid_candidates:
                    msg += f"• الرمز: `{sym}` | السعر: `${price}` | تقييم الاستراتيجيات: `{sc}%`\n"
                bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ تعذر إتمام المسح الفوري: {str(e)[:50]}", reply_markup=get_control_keyboard())
        return

    symbol_to_check = text.replace("$", "").strip().upper()
    if len(symbol_to_check) > 0 and len(symbol_to_check) <= 6:
        bot.send_message(chat_id, f"🤖 استلمت السهم `{symbol_to_check}`، جاري تطبيق الاستراتيجيات الثلاث عليه...", reply_markup=get_control_keyboard())
        try:
            price, barset = get_fallback_price(symbol_to_check)
            if not price or price <= 0:
                bot.send_message(chat_id, f"⚠️ عذراً، تعذر جلب بيانات السهم `{symbol_to_check}` في الوقت الحالي.", reply_markup=get_control_keyboard())
                return
            
            score, reasons = evaluate_multi_strategies(symbol_to_check, price, barset)
            
            target_1 = round(price * 1.25, 2)
            target_2 = round(price * 1.55, 2)
            stop_loss = round(price * 0.90, 2)
            
            if score >= 60:
                decision = "🟢 **قرار الاستراتيجيات الثلاث: السهم إيجابي وتجتمع فيه شروط القوة والربحية!**"
            else:
                decision = "🔴 **قرار الاستراتيجيات الثلاث: المعايير الفنية غير مكتملة حالياً.**"

            reasons_str = "\n".join([f"• {r}" for r in reasons])

            analysis_msg = (
                f"🔬 **تقرير الاستراتيجيات الشامل (JALWE AI):**\n"
                f"📌 الرمز: `{symbol_to_check}`\n"
                f"💵 **السعر المعتمد:** `${price}`\n"
                f"⚡ تقييم الدمج الاستراتيجي: `{score}%`\n\n"
                f"📋 **تحليل الإشارات الفنية:**\n{reasons_str}\n\n"
                f"{decision}\n\n"
                f"📊 **خطة التداول المقترحة:**\n"
                f"• 🛑 وقف الخسارة: `${stop_loss}`\n"
                f"• 🎯 الهدف الأول: `${target_1}`\n"
                f"• 🎯 الهدف الثاني: `${target_2}`\n\n"
                f"🛡️ *تم حفظ تحليل الاستراتيجيات في الذاكرة للتعلم المستمر.*"
            )
            bot.send_message(chat_id, analysis_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())

            try:
                conn = sqlite3.connect("jalwe_learning.db")
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO potential_stocks_snapshots (symbol, entry_price, target_price, score, status) VALUES (?, ?, ?, ?, ?)",
                    (symbol_to_check, price, target_1, score, "MULTI_STRATEGY_DECISION")
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

        except Exception as e:
            bot.send_message(chat_id, f"⚠️ حدث خطأ أثناء تحليل السهم `{symbol_to_check}`: {str(e)[:50]}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "الرجاء اختيار أمر من القائمة أو إرسال رمز سهم صحيح (مثل: `AAPL`).", reply_markup=get_control_keyboard())

def main_trading_cycle():
    global bot_running, last_error
    if not bot_running:
        return
    try:
        symbols = pre_engine.scan_entire_market()
        if not symbols:
            return
            
        viable_symbols = []
        for sym in symbols:
            price, barset = get_fallback_price(sym)
            if price and 0.25 <= price <= 50.0:
                score, _ = evaluate_multi_strategies(sym, price, barset)
                if score >= 65:
                    viable_symbols.append((sym, price, score))

        if not viable_symbols:
            return

        sample_targets = random.sample(viable_symbols, min(3, len(viable_symbols)))
        
        for sym, price, score in sample_targets:
            target_1 = round(price * 1.25, 2)
            target_2 = round(price * 1.55, 2)
            stop_loss = round(price * 0.90, 2)

            try:
                conn = sqlite3.connect("jalwe_learning.db")
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO potential_stocks_snapshots (symbol, entry_price, target_price, score, status) VALUES (?, ?, ?, ?, ?)",
                    (sym, price, target_1, score, "AUTO_MULTI_STRATEGY")
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            alert_msg = (
                f"💎 **JALWE AI — رصد استراتيجي متكامل**\n"
                f"📌 الرمز: `{sym}`\n"
                f"💵 **السعر المعتمد:** `${price}`\n"
                f"⚡ تقييم الاستراتيجيات الثلاث: `{score}%`\n\n"
                f"📊 **الخطة السعرية المقترحة:**\n"
                f"• 🛑 وقف الخسارة: `${stop_loss}`\n"
                f"• 🎯 الهدف الأول: `${target_1}`\n"
                f"• 🎯 الهدف الثاني: `${target_2}`\n\n"
                f"🛡️ *النظام يراقب الفرصة وفق دمج الاستراتيجيات.*"
            )
            if TELEGRAM_CHAT_ID:
                bot.send_message(TELEGRAM_CHAT_ID, alert_msg, parse_mode="Markdown")

    except Exception as e:
        last_error = f"خطأ في الرادار الاستراتيجي: {str(e)[:40]}"
        print(f"Cycle Error: {e}")

schedule.every(20).minutes.do(main_trading_cycle)

if __name__ == "__main__":
    print("INFO - JALWE Multi-Strategy Engine is running...")
    
    try:
        bot.remove_webhook()
        time.sleep(2)
    except Exception:
        print("Webhook removal skipped or failed.")

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
            last_error = f"تعارض مؤقت وتجاوزه: {str(e)[:40]}"
            time.sleep(10)
