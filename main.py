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
    # جدول لتتبع الوقف المتحرك والقمم السعرية لكل صفقة آلية
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_trades_tracker (
            symbol TEXT PRIMARY KEY,
            entry_price REAL,
            highest_price REAL,
            qty INTEGER,
            status TEXT
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
last_error = "النظام الذكي لتعظيم الأرباح يعمل بكفاءة تامة 🚀"

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
    try:
        barset = alpaca.get_bars(symbol.upper(), tradeapi.TimeFrame.Day, limit=10).df
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

def evaluate_momentum_and_strategies(symbol, price, barset):
    score = 50
    reasons = []

    if barset is not None and len(barset) >= 5:
        recent_high = barset['high'].iloc[:-1].max()
        vol_mean = barset['volume'].mean() if 'volume' in barset.columns else 1000
        last_vol = barset['volume'].iloc[-1] if 'volume' in barset.columns else 1000

        # فحص الزخم وانفجار السيولة لتعظيم الربح
        if price >= recent_high * 0.98:
            score += 20
            reasons.append("🚀 اختراق قوي للقمة (Breakout Surge)")
        
        if last_vol > vol_mean * 1.3:
            score += 15
            reasons.append("🔥 حجم تداول عالٍ جداً (Volume Spike - انطلاقة قوية)")

        ma_5 = barset['close'].rolling(window=3).mean().iloc[-1]
        if price >= ma_5:
            score += 15
            reasons.append("📈 التداول فوق المتوسط المتحرك (اتجاه صاعد واضح)")
    else:
        score += 12
        reasons.append("⚡ زخم سعري افتراضي مرتفع")

    score = max(20, min(98, score))
    return score, reasons

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    global bot_running, last_error
    text = message.text.strip() if message.text else ""
    chat_id = message.chat.id

    if "تشغيل الرادار المستقل" in text or "تشغيل البوت المتعلم" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل رادار تعظيم الأرباح والتنفيذ الذاتي بالكامل.**", reply_markup=get_control_keyboard())
        return
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", reply_markup=get_control_keyboard())
        return
    elif "🎯 إضافة سهم للمتابعة" in text:
        bot.send_message(chat_id, "🎯 **وضع المتابعة والتحليل جاهز!** أرسل رمز السهم (مثال: `TSLA`).", reply_markup=get_control_keyboard())
        return
    elif "💼 محفظتي وأسهمي" in text:
        bot.send_message(chat_id, "⏳ جاري جلب تفاصيل محفظتك الحالية...", reply_markup=get_control_keyboard())
        try:
            account = alpaca.get_account()
            positions = alpaca.list_positions()
            portfolio_msg = (
                f"💼 **تقرير محفظتك الاستثمارية اللحظية:**\n\n"
                f"💵 **السيولة (Cash):** `${float(account.cash):,.2f}`\n"
                f"💰 **إجمالي الحساب:** `${float(account.portfolio_value):,.2f}`\n\n"
                f"📦 **الأسهم المملوكة حالياً:**\n"
            )
            if not positions:
                portfolio_msg += "\n*لا توجد أسهم مملوكة حالياً.*"
            else:
                for p in positions:
                    portfolio_msg += f"• `{p.symbol}` | الكمية: `{p.qty}` | السعر: `${float(p.current_price)}` | الربح/الخسارة: `{float(p.unrealized_pl):.2f}$`\n"
            bot.send_message(chat_id, portfolio_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ تعذر جلب المحفظة: {str(e)[:50]}", reply_markup=get_control_keyboard())
        return
    elif "📊 أداء محفظتي والربح" in text:
        try:
            account = alpaca.get_account()
            equity = float(account.equity)
            last_equity = float(account.last_equity)
            day_pl = equity - last_equity
            day_pl_pc = (day_pl / last_equity) * 100 if last_equity > 0 else 0
            emoji = "🟢" if day_pl >= 0 else "🔴"
            bot.send_message(chat_id, f"📊 **أداء المحفظة:**\nالقيمة الإجمالية: `${equity:,.2f}`\nأداء اليوم: {emoji} `${day_pl:,.2f}` (`{day_pl_pc:.2f}%`)", parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {str(e)[:40]}", reply_markup=get_control_keyboard())
        return
    elif "⚙️ حالة الأوامر المفتوحة" in text:
        try:
            orders = alpaca.list_orders(status='open')
            msg = "⚙️ **الأوامر المفتوحة:**\n"
            if not orders:
                msg += "*لا توجد أوامر معلقة.*"
            else:
                for o in orders:
                    msg += f"• `{o.symbol}` | {o.side} | {o.qty}\n"
            bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {str(e)[:40]}", reply_markup=get_control_keyboard())
        return
    elif "فحص نموذج التعلم الذاتي" in text:
        total = get_saved_snapshots_count()
        bot.send_message(chat_id, f"🧠 **محرك تعظيم الأرباح:**\n- الصفقات والحالات المسجلة: `{total}`\n- الميزة الفعالة: `Trailing Stop-Loss + Scale-Out (الوقف المتحرك والخروج الجزئي مفعلان بالكامل).`", reply_markup=get_control_keyboard())
        return
    elif "تقرير النظام والأخطاء" in text:
        bot.send_message(chat_id, f"🛠️ **التشخيص:**\n{last_error}\nالوضع: `تشغيل ذاتي لتعظيم الأرباح 24/7`", reply_markup=get_control_keyboard())
        return
    elif "فحص السوق حالياً" in text:
        bot.send_message(chat_id, "⏳ جاري فحص السوق للبحث عن فرص ذات زخم عالٍ وانفجار سعري...", reply_markup=get_control_keyboard())
        try:
            symbols = pre_engine.scan_entire_market()
            viable = []
            for sym in symbols:
                p, bs = get_fallback_price(sym)
                if p and 0.25 <= p <= 60.0:
                    sc, _ = evaluate_momentum_and_strategies(sym, p, bs)
                    if sc >= 72:
                        viable.append((sym, p, sc))
                if len(viable) >= 3:
                    break
            if not viable:
                bot.send_message(chat_id, "📊 لم تتطابق شروط الزخم العالي مع أي سهم حالياً.", reply_markup=get_control_keyboard())
            else:
                msg = "🚀 **أفضل الفرص لانفجار سعري وتعظيم الأرباح:**\n\n"
                for s, pr, sc in viable:
                    msg += f"• `{s}` | السعر: `${pr}` | التقييم: `{sc}%`\n"
                bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {str(e)[:40]}", reply_markup=get_control_keyboard())
        return

    # تحليل السهم اليدوي والشراء الآلي مع استراتيجية تعظيم الأرباح
    symbol_to_check = text.replace("$", "").strip().upper()
    if len(symbol_to_check) > 0 and len(symbol_to_check) <= 6:
        bot.send_message(chat_id, f"🤖 فحص السهم `{symbol_to_check}` لتعظيم الربح...", reply_markup=get_control_keyboard())
        try:
            price, barset = get_fallback_price(symbol_to_check)
            if not price or price <= 0:
                bot.send_message(chat_id, f"⚠️ تعذر جلب بيانات `{symbol_to_check}`.", reply_markup=get_control_keyboard())
                return
            
            score, reasons = evaluate_momentum_and_strategies(symbol_to_check, price, barset)
            reasons_str = "\n".join([f"• {r}" for r in reasons])

            analysis_msg = (
                f"🔬 **تقرير تعظيم الأرباح:**\n"
                f"📌 الرمز: `{symbol_to_check}`\n"
                f"💵 **السعر:** `${price}`\n"
                f"⚡ تقييم الزخم: `{score}%`\n\n"
                f"📋 **الأسباب:**\n{reasons_str}\n\n"
            )

            # إذا كان التقييم عالي، ينفذ الشراء ويخزنه في متتبع الوقف المتحرك
            if score >= 75:
                try:
                    qty_to_buy = max(2, int(150 / price)) # كمية تسمح بالبيع الجزئي لاحقاً
                    alpaca.submit_order(
                        symbol=symbol_to_check,
                        qty=qty_to_buy,
                        side='buy',
                        type='market',
                        time_in_force='gtc'
                    )
                    
                    # حفظ الصفقة في متتبع الوقف المتحرك (Trailing Stop)
                    conn = sqlite3.connect("jalwe_learning.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO active_trades_tracker (symbol, entry_price, highest_price, qty, status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (symbol_to_check, price, price, qty_to_buy, 'ACTIVE'))
                    conn.commit()
                    conn.close()

                    analysis_msg += f"🟢 **تم التنفيذ الآلي بنجاح!**\n- تم شراء `{qty_to_buy}` سهم من `{symbol_to_check}`.\n- **مفعل:** الوقف المتحرك (Trailing Stop) والخروج الجزئي لضمان أقصى ربح."
                except Exception as ex:
                    analysis_msg += f"⚠️ تعذر إرسال أمر الشراء: {str(ex)[:40]}"
            else:
                analysis_msg += "🔴 **لم يتم التنفيذ الآلي:** الزخم غير كافٍ لتعظيم الربح (أقل من 75%)."

            bot.send_message(chat_id, analysis_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())

        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ بالتحليل: {str(e)[:40]}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "الرجاء اختيار أمر من القائمة أو إرسال رمز سهم.", reply_markup=get_control_keyboard())

def manage_active_trades_and_trailing():
    """الدورة الذاتية لمتابعة الوقف المتحرك (Trailing Stop) وجني الأرباح الجزئي لعصر أقصى ربح"""
    try:
        conn = sqlite3.connect("jalwe_learning.db")
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, entry_price, highest_price, qty, status FROM active_trades_tracker WHERE status='ACTIVE'")
        trades = cursor.fetchall()
        conn.close()

        for symbol, entry_price, highest_price, qty, status in trades:
            curr_price, _ = get_fallback_price(symbol)
            if not curr_price:
                continue

            # تحديث أعلى سعر وصل له السهم منذ الشراء (لتتبع الموجة الصاعدة)
            new_highest = max(highest_price, curr_price)
            profit_pct = ((curr_price - entry_price) / entry_price) * 100

            # 1. الخروج الجزئي: إذا حقق السهم ربح +5% يبيع نصف الكمية لجني أرباح مضمونة ويترك الباقي يصعد بحرية
            if profit_pct >= 5.0 and qty >= 2:
                half_qty = max(1, qty // 2)
                try:
                    alpaca.submit_order(symbol=symbol, qty=half_qty, side='sell', type='market', time_in_force='gtc')
                    remaining_qty = qty - half_qty
                    
                    # تحديث الكمية في قاعدة البيانات
                    conn = sqlite3.connect("jalwe_learning.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE active_trades_tracker SET qty=?, highest_price=? WHERE symbol=?", (remaining_qty, new_highest, symbol))
                    conn.commit()
                    conn.close()

                    if TELEGRAM_CHAT_ID:
                        bot.send_message(TELEGRAM_CHAT_ID, f"💰 **جني أرباح جزئي (Scale-Out)!**\n- الرمز: `{symbol}`\n- تم بيع نصف الكمية (`{half_qty}` سهم) بربح `{profit_pct:.2f}%`.\n- الباقي مستمر مع الوقف المتحرك لتعظيم الأرباح المطلقة 🚀", parse_mode="Markdown")
                except Exception:
                    pass

            # 2. الوقف المتحرك (Trailing Stop): لو صعد السهم ثم تراجع بنسبة 3% من أعلى قمة وصلها، يقفل الصفقة فوراً ليحميك ويحافظ على أرباحك
            drop_from_peak = ((new_highest - curr_price) / new_highest) * 100
            if drop_from_peak >= 3.0 and profit_pct > 1.0:
                try:
                    alpaca.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                    
                    conn = sqlite3.connect("jalwe_learning.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE active_trades_tracker SET status='CLOSED' WHERE symbol=?", (symbol,))
                    conn.commit()
                    conn.close()

                    if TELEGRAM_CHAT_ID:
                        bot.send_message(TELEGRAM_CHAT_ID, f"🎯🔒 **إغلاق الصفقة بالوقف المتحرك (Trailing Stop)!**\n- الرمز: `{symbol}`\n- صافي الأرباح المحققة: `{profit_pct:.2f}%`\n- *تم الحفاظ على المكسب الأعلى بنجاح.*", parse_mode="Markdown")
                except Exception:
                    pass
            else:
                # تحديث أعلى قمة في قاعدة البيانات
                conn = sqlite3.connect("jalwe_learning.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE active_trades_tracker SET highest_price=? WHERE symbol=?", (new_highest, symbol))
                conn.commit()
                conn.close()

    except Exception as e:
        pass

def main_trading_cycle():
    global bot_running, last_error
    if not bot_running:
        return
    try:
        # تشغيل مراقبة الوقف المتحرك للصفقات النشطة أولاً
        manage_active_trades_and_trailing()

        symbols = pre_engine.scan_entire_market()
        if not symbols:
            return
            
        for sym in symbols:
            price, barset = get_fallback_price(sym)
            if price and 0.25 <= price <= 60.0:
                score, _ = evaluate_momentum_and_strategies(sym, price, barset)
                
                # إذا وجد فرصة بانفجار سعري فوق 82% يشتريها آلياً ويعصر أرباحها
                if score >= 82:
                    try:
                        qty_to_buy = max(2, int(150 / price))
                        alpaca.submit_order(
                            symbol=sym,
                            qty=qty_to_buy,
                            side='buy',
                            type='market',
                            time_in_force='gtc'
                        )
                        
                        # حفظ الصفقة في متتبع الوقف المتحرك
                        conn = sqlite3.connect("jalwe_learning.db")
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR REPLACE INTO active_trades_tracker (symbol, entry_price, highest_price, qty, status)
                            VALUES (?, ?, ?, ?, ?)
                        """, (sym, price, price, qty_to_buy, 'ACTIVE'))
                        conn.commit()
                        conn.close()
                        
                        alert_msg = (
                            f"🚀🔥 **تنفيذ آلي لتعظيم الأرباح في الخلفية!**\n"
                            f"📌 الرمز: `{sym}`\n"
                            f"💵 سعر الشراء: `${price}`\n"
                            f"📊 تقييم الزخم: `{score}%`\n"
                            f"📦 الكمية: `{qty_to_buy}` سهم\n\n"
                            f"⚡ *تم تفعيل الوقف المتحرك والخروج الجزئي آلياً.*"
                        )
                        if TELEGRAM_CHAT_ID:
                            bot.send_message(TELEGRAM_CHAT_ID, alert_msg, parse_mode="Markdown")
                        break 
                    except Exception:
                        pass
    except Exception as e:
        last_error = f"خطأ دورة تعظيم الأرباح: {str(e)[:40]}"

schedule.every(15).minutes.do(main_trading_cycle)

if __name__ == "__main__":
    print("INFO - JALWE Profit Maximization & Autonomous Trading Engine is running...")
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
            bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True)
        except Exception as e:
            last_error = f"تعارض وتم تجاوزه: {str(e)[:40]}"
            time.sleep(10)
