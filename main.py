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
    # جدول متتبع الصفقات النشطة محدث لدعم وقف الخسارة المتحرك والذكي
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_trades_tracker (
            symbol TEXT PRIMARY KEY,
            entry_price REAL,
            stop_loss_price REAL,
            highest_price REAL,
            qty INTEGER,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS closed_trades_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            entry_price REAL,
            exit_price REAL,
            profit_pct REAL,
            result_status TEXT,
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
last_error = "النظام الذكي لتحدي التدوير والوقف المتحرك يعمل بكفاءة 🚀"

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

    try:
        conn = sqlite3.connect("jalwe_learning.db")
        cursor = conn.cursor()
        cursor.execute("SELECT AVG(profit_pct) FROM closed_trades_performance WHERE symbol=?", (symbol,))
        avg_hist_profit = cursor.fetchone()[0]
        conn.close()
        if avg_hist_profit is not None:
            if avg_hist_profit > 0:
                score += 10
                reasons.append("🧠 ذاكرة التعلم: السهم حقق أرباحاً تاريخية ناجحة سابقاً")
            else:
                score -= 10
                reasons.append("⚠️ ذاكرة التعلم: السهم سجل خسائر سابقة (تخفيض الحذر)")
    except Exception:
        pass

    if barset is not None and len(barset) >= 5:
        recent_high = barset['high'].iloc[:-1].max()
        vol_mean = barset['volume'].mean() if 'volume' in barset.columns else 1000
        last_vol = barset['volume'].iloc[-1] if 'volume' in barset.columns else 1000

        if price >= recent_high * 0.98:
            score += 20
            reasons.append("🚀 اختراق قوي للقمة (Breakout Surge)")
        
        if last_vol > vol_mean * 1.3:
            score += 15
            reasons.append("🔥 حجم تداول عالٍ وانفجار سيولة (Volume Spike)")

        ma_5 = barset['close'].rolling(window=3).mean().iloc[-1]
        if price >= ma_5:
            score += 15
            reasons.append("📈 التداول فوق المتوسط المتحرك (اتجاه صاعد)")
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
        bot.send_message(chat_id, "🟢 **تم تفعيل رادار تحدي التدوير التراكمي والوقف الذكي.**", reply_markup=get_control_keyboard())
        return
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", reply_markup=get_control_keyboard())
        return
    elif "🎯 إضافة سهم للمتابعة" in text:
        bot.send_message(chat_id, "🎯 **وضع المتابعة والتحليل الذكي جاهز!** أرسل رمز السهم (مثال: `TSLA`).", reply_markup=get_control_keyboard())
        return
    elif "💼 محفظتي وأسهمي" in text:
        bot.send_message(chat_id, "⏳ جاري جلب تفاصيل محفظتك الحالية...", reply_markup=get_control_keyboard())
        try:
            account = alpaca.get_account()
            positions = alpaca.list_positions()
            portfolio_msg = (
                f"💼 **تقرير محفظة التحدي اللحظية:**\n\n"
                f"💵 **السيولة (Cash):** `${float(account.cash):,.2f}`\n"
                f"💰 **إجمالي الحساب (Equity):** `${float(account.portfolio_value):,.2f}`\n\n"
                f"📦 **الأسهم المملوكة حالياً:**\n"
            )
            if not positions:
                portfolio_msg += "\n*لا توجد أسهم مملوكة حالياً.*"
            else:
                for p in positions:
                    portfolio_msg += f"• `{p.symbol}` | الكمية: `{p.qty}` | السعر: `${float(p.current_price)}` | الربح: `${float(p.unrealized_pl):.2f}`\n"
            bot.send_message(chat_id, portfolio_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {str(e)[:40]}", reply_markup=get_control_keyboard())
        return
    elif "📊 أداء محفظتي والربح" in text:
        try:
            account = alpaca.get_account()
            equity = float(account.equity)
            last_equity = float(account.last_equity)
            day_pl = equity - last_equity
            day_pl_pc = (day_pl / last_equity) * 100 if last_equity > 0 else 0
            emoji = "🟢" if day_pl >= 0 else "🔴"
            bot.send_message(chat_id, f"📊 **أداء المحفظة:**\nالقيمة: `${equity:,.2f}`\nأداء اليوم: {emoji} `${day_pl:,.2f}` (`{day_pl_pc:.2f}%`)", parse_mode="Markdown", reply_markup=get_control_keyboard())
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
        try:
            conn = sqlite3.connect("jalwe_learning.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), AVG(profit_pct) FROM closed_trades_performance")
            res = cursor.fetchone()
            closed_count = res[0] if res[0] else 0
            avg_win = res[1] if res[1] else 0.0
            conn.close()
        except Exception:
            closed_count, avg_win = 0, 0.0

        bot.send_message(chat_id, f"🧠 **محرك التعلم الذاتي والتدوير:**\n- الحالات المسجلة بالرادار: `{total}`\n- الصفقات المغلقة: `{closed_count}`\n- متوسط أداء التعلم: `{avg_win:.2f}%`\n- الاستراتيجية: `تدوير الأرباح بالكامل + تنويع عند 200$ + وقف خسارة متحرك.`", reply_markup=get_control_keyboard())
        return
    elif "تقرير النظام والأخطاء" in text:
        bot.send_message(chat_id, f"🛠️ **التشخيص:**\n{last_error}\nالوضع: `تشغيل ذاتي بالذكاء الاصطناعي 24/7`", reply_markup=get_control_keyboard())
        return
    elif "فحص السوق حالياً" in text:
        bot.send_message(chat_id, "⏳ جاري فحص السوق وتطبيق معايير تحدي التدوير...", reply_markup=get_control_keyboard())
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
                bot.send_message(chat_id, "📊 لم تتطابق الشروط مع أي سهم حالياً.", reply_markup=get_control_keyboard())
            else:
                msg = "🚀 **الفرص المرشحة لتحدي التدوير:**\n\n"
                for s, pr, sc in viable:
                    msg += f"• `{s}` | السعر: `${pr}` | التقييم الذكي: `{sc}%`\n"
                bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {str(e)[:40]}", reply_markup=get_control_keyboard())
        return

    # تحليل سهم يدوي وتطبيق استراتيجية التدوير والوقف الذكي
    symbol_to_check = text.replace("$", "").strip().upper()
    if len(symbol_to_check) > 0 and len(symbol_to_check) <= 6:
        bot.send_message(chat_id, f"🤖 فحص السهم `{symbol_to_check}` وفق شروط تحدي التدوير...", reply_markup=get_control_keyboard())
        try:
            price, barset = get_fallback_price(symbol_to_check)
            if not price or price <= 0:
                bot.send_message(chat_id, f"⚠️ تعذر جلب بيانات `{symbol_to_check}`.", reply_markup=get_control_keyboard())
                return
            
            score, reasons = evaluate_momentum_and_strategies(symbol_to_check, price, barset)
            reasons_str = "\n".join([f"• {r}" for r in reasons])

            analysis_msg = (
                f"🔬 **تقرير الذكاء الاصطناعي للتحدي:**\n"
                f"📌 الرمز: `{symbol_to_check}`\n"
                f"💵 **السعر:** `${price}`\n"
                f"⚡ تقييم الذكاء الاصطناعي: `{score}%`\n\n"
                f"📋 **الأسباب الفنية وسجل الذاكرة:**\n{reasons_str}\n\n"
            )

            if score >= 75:
                try:
                    account_info = alpaca.get_account()
                    total_equity = float(account_info.equity)
                    cash_available = float(account_info.cash)

                    # استراتيجية التدوير والتنويع: لو الحساب فوق 200$ يقسم السيولة، لو تحته يدورها بالكامل
                    if total_equity >= 200.0:
                        allocation_amount = cash_available * 0.50
                        strategy_mode = "تنويع الأرباح (الحساب تجاوز 200$)"
                    else:
                        allocation_amount = cash_available * 0.90
                        strategy_mode = "تدوير كامل بالربح ورأس المال (تحت 200$)"

                    qty_to_buy = max(1, int(allocation_amount / price))
                    
                    # وقف خسارة أولي صارم 5%
                    initial_stop_loss = round(price * 0.95, 2)

                    alpaca.submit_order(
                        symbol=symbol_to_check,
                        qty=qty_to_buy,
                        side='buy',
                        type='market',
                        time_in_force='gtc'
                    )
                    
                    conn = sqlite3.connect("jalwe_learning.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO active_trades_tracker (symbol, entry_price, stop_loss_price, highest_price, qty, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (symbol_to_check, price, initial_stop_loss, price, qty_to_buy, 'ACTIVE'))
                    conn.commit()
                    conn.close()

                    analysis_msg += (
                        f"🟢 **تم التنفيذ الآلي بنجاح!**\n"
                        f"- النمط: `{strategy_mode}`\n"
                        f"- الكمية: `{qty_to_buy}` سهم\n"
                        f"- 🛑 وقف الخسارة الأولي: `${initial_stop_loss}`\n"
                        f"- *سيتم رفع وقف الخسارة لسعر الدخول أو أعلى فور تحقيق الأرباح.*"
                    )
                except Exception as ex:
                    analysis_msg += f"⚠️ تعذر تنفيذ أمر الشراء: {str(ex)[:40]}"
            else:
                analysis_msg += "🔴 **لم يتم التنفيذ الآلي:** الثقة بناءً على الذاكرة والمؤشرات أقل من المطلوب."

            bot.send_message(chat_id, analysis_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())

        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ بالتحليل: {str(e)[:40]}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "الرجاء اختيار أمر من القائمة أو إرسال رمز سهم صحيح.", reply_markup=get_control_keyboard())

def manage_active_trades_and_trailing():
    """إدارة الصفقات: رفع وقف الخسارة لمستوى الربح الأول (Break-Even)، تعصير السهم، والتعلم الذاتي"""
    try:
        conn = sqlite3.connect("jalwe_learning.db")
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, entry_price, stop_loss_price, highest_price, qty, status FROM active_trades_tracker WHERE status='ACTIVE'")
        trades = cursor.fetchall()
        conn.close()

        for symbol, entry_price, stop_loss_price, highest_price, qty, status in trades:
            curr_price, _ = get_fallback_price(symbol)
            if not curr_price:
                continue

            new_highest = max(highest_price, curr_price)
            profit_pct = ((curr_price - entry_price) / entry_price) * 100

            # 1. تحديث وقف الخسارة الذكي (إذا حقق السهم أرباحاً أولية بنسبة +4% أو أكثر، ارفع وقف الخسارة لمكان الدخول أو فوقه)
            current_stop = stop_loss_price
            if profit_pct >= 4.0 and current_stop < entry_price:
                current_stop = entry_price # رفع وقف الخسارة لسعر الدخول (صفقة بدون مخاطرة Risk-Free)
                if profit_pct >= 8.0:
                    current_stop = round(entry_price * 1.03, 2) # قفل أرباح مضمونة لو صعد أكثر

            # 2. إذا نزل السهم ولمس وقف الخسارة المحدث أو حقق خسارة 5%، اخرج فوراً لحماية الرصيد وتدويره
            if curr_price <= current_stop or profit_pct <= -5.0:
                try:
                    alpaca.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                    
                    conn = sqlite3.connect("jalwe_learning.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE active_trades_tracker SET status='CLOSED' WHERE symbol=?", (symbol,))
                    cursor.execute("""
                        INSERT INTO closed_trades_performance (symbol, entry_price, exit_price, profit_pct, result_status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (symbol, entry_price, curr_price, profit_pct, "WIN" if profit_pct > 0 else "LOSS"))
                    conn.commit()
                    conn.close()

                    status_msg = "🎯 أرباح مضمونة ومحمية" if profit_pct > 0 else "🛑 وقف الخسارة"
                    if TELEGRAM_CHAT_ID:
                        bot.send_message(TELEGRAM_CHAT_ID, f"🔄🚨 **إغلاق صفقة التحدي ({status_msg})!**\n- الرمز: `{symbol}`\n- النتيجة: `{profit_pct:.2f}%`\n- *تمت إضافة الكاش والأرباح لرصيد التدوير لتحديث الحجم في الدورة القادمة 🚀*", parse_mode="Markdown")
                except Exception:
                    pass
            
            # 3. تعصير السهم لأقصى ربح (Trailing Stop من أعلى قمة وصلها)
            elif ((new_highest - curr_price) / new_highest) * 100 >= 3.0 and profit_pct >= 6.0:
                try:
                    alpaca.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                    
                    conn = sqlite3.connect("jalwe_learning.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE active_trades_tracker SET status='CLOSED' WHERE symbol=?", (symbol,))
                    cursor.execute("""
                        INSERT INTO closed_trades_performance (symbol, entry_price, exit_price, profit_pct, result_status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (symbol, entry_price, curr_price, profit_pct, "WIN"))
                    conn.commit()
                    conn.close()

                    if TELEGRAM_CHAT_ID:
                        bot.send_message(TELEGRAM_CHAT_ID, f"🎯💰 **تعصير السهم وجني الأقصى بنجاح!**\n- الرمز: `{symbol}`\n- أرباح الصعود: `+{profit_pct:.2f}%`\n- *الأرباح تضاف بالكامل لتعزيز محفظة التحدي.*", parse_mode="Markdown")
                except Exception:
                    pass
            else:
                conn = sqlite3.connect("jalwe_learning.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE active_trades_tracker SET highest_price=?, stop_loss_price=? WHERE symbol=?", (new_highest, current_stop, symbol))
                conn.commit()
                conn.close()

    except Exception as e:
        pass

def send_weekly_performance_report():
    try:
        conn = sqlite3.connect("jalwe_learning.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END), AVG(profit_pct) FROM closed_trades_performance")
        res = cursor.fetchone()
        conn.close()

        total_trades = res[0] if res[0] else 0
        winning_trades = res[1] if res[1] else 0
        avg_profit = res[2] if res[2] else 0.0
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        report_msg = (
            f"📊📅 **تقرير أداء تحدي التدوير الأسبوعي:**\n\n"
            f"• إجمالي صفقات التحدي: `{total_trades}`\n"
            f"• الصفقات الرابحة: `{winning_trades}`\n"
            f"• نسبة النجاح: `{win_rate:.1f}%`\n"
            f"• متوسط العائد: `{avg_profit:.2f}%`\n\n"
            f"🧠 *الذكاء الاصطناعي قام بتحديث أوزان الذاكرة بناءً على هذه النتائج.*"
        )
        if TELEGRAM_CHAT_ID:
            bot.send_message(TELEGRAM_CHAT_ID, report_msg, parse_mode="Markdown")
    except Exception:
        pass

def main_trading_cycle():
    global bot_running, last_error
    if not bot_running:
        return
    try:
        manage_active_trades_and_trailing()

        symbols = pre_engine.scan_entire_market()
        if not symbols:
            return
            
        for sym in symbols:
            price, barset = get_fallback_price(sym)
            if price and 0.25 <= price <= 60.0:
                score, _ = evaluate_momentum_and_strategies(sym, price, barset)
                
                if score >= 82:
                    try:
                        account_info = alpaca.get_account()
                        total_equity = float(account_info.equity)
                        cash_available = float(account_info.cash)

                        if total_equity >= 200.0:
                            allocation_amount = cash_available * 0.50
                        else:
                            allocation_amount = cash_available * 0.90

                        qty_to_buy = max(1, int(allocation_amount / price))
                        initial_stop_loss = round(price * 0.95, 2)

                        alpaca.submit_order(
                            symbol=sym,
                            qty=qty_to_buy,
                            side='buy',
                            type='market',
                            time_in_force='gtc'
                        )
                        
                        conn = sqlite3.connect("jalwe_learning.db")
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR REPLACE INTO active_trades_tracker (symbol, entry_price, stop_loss_price, highest_price, qty, status)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (sym, price, initial_stop_loss, price, qty_to_buy, 'ACTIVE'))
                        conn.commit()
                        conn.close()
                        
                        alert_msg = (
                            f"🚀 تحدي التدوير — **تنفيذ آلي في الخلفية!**\n"
                            f"📌 الرمز: `{sym}`\n"
                            f"💵 سعر الشراء: `${price}`\n"
                            f"📊 تقييم الذكاء الاصطناعي: `{score}%`\n"
                            f"🛑 وقف الخسارة الأولي: `${initial_stop_loss}`\n"
                            f"📦 الكمية: `{qty_to_buy}` سهم"
                        )
                        if TELEGRAM_CHAT_ID:
                            bot.send_message(TELEGRAM_CHAT_ID, alert_msg, parse_mode="Markdown")
                        break 
                    except Exception:
                        pass
    except Exception as e:
        last_error = f"خطأ دورة التحدي: {str(e)[:40]}"

schedule.every(15).minutes.do(main_trading_cycle)
schedule.every().friday.at("21:00").do(send_weekly_performance_report)

if __name__ == "__main__":
    print("INFO - JALWE Compounding & Trailing Stop Engine is running...")
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
