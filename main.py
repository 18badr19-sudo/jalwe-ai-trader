import os
import time
import sqlite3
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
last_error = "النظام الذكي الشامل (متعدد الأطر + تحليل الأخبار) يعمل بكفاءة 🚀"

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

# (تحديث 1): جلب البيانات على أكثر من فريم زمني
def get_market_data(symbol):
    price = None
    bars_day = None
    bars_15m = None
    try:
        bars_day = alpaca.get_bars(symbol.upper(), tradeapi.TimeFrame.Day, limit=10).df
        bars_15m = alpaca.get_bars(symbol.upper(), tradeapi.TimeFrame(15, tradeapi.TimeFrameUnit.Minute), limit=10).df
        if not bars_day.empty:
            price = float(bars_day['close'].iloc[-1])
    except Exception:
        pass
    
    if not price:
        try:
            trade = alpaca.get_latest_trade(symbol.upper())
            if trade and hasattr(trade, 'price'):
                price = float(trade.price)
        except Exception:
            pass
    
    return price, bars_day, bars_15m

# (تحديث 2): محرك تحليل الأخبار والمشاعر
def get_news_sentiment(symbol):
    score = 0
    reasons = []
    try:
        news = alpaca.get_news(symbol.upper(), limit=5)
        if not news:
            return 0, []
        
        positive_words = ['surge', 'jump', 'up', 'target', 'beat', 'profit', 'win', 'contract', 'buy', 'growth', 'upgrade', 'high']
        negative_words = ['drop', 'down', 'miss', 'loss', 'lawsuit', 'downgrade', 'sell', 'crash', 'risk', 'low']
        
        pos_count = 0
        neg_count = 0
        
        for n in news:
            headline = n.headline.lower()
            for w in positive_words:
                if w in headline: pos_count += 1
            for w in negative_words:
                if w in headline: neg_count += 1
        
        if pos_count > neg_count:
            score += 15
            reasons.append(f"📰 أخبار إيجابية: زخم إعلامي داعم ({pos_count} إشارات)")
        elif neg_count > pos_count:
            score -= 15
            reasons.append(f"⚠️ أخبار سلبية: تحذير من ضغط إعلامي أو مالي")
    except Exception:
        pass
    return score, reasons

# (تحديث 3): دمج كل الذكاء في التقييم
def evaluate_momentum_and_strategies(symbol, price, bars_day, bars_15m):
    score = 40 # درجة البداية
    reasons = []

    # 1. ذاكرة التعلم (Reinforcement Learning)
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

    # 2. تحليل الأطر الزمنية المتعددة (Multi-Timeframe)
    if bars_day is not None and len(bars_day) >= 5:
        recent_high = bars_day['high'].iloc[:-1].max()
        vol_mean = bars_day['volume'].mean() if 'volume' in bars_day.columns else 1000
        last_vol = bars_day['volume'].iloc[-1] if 'volume' in bars_day.columns else 1000

        if price >= recent_high * 0.98:
            score += 15
            reasons.append("🚀 اختراق قوي للقمة اليومية (Breakout Surge)")
        
        if last_vol > vol_mean * 1.3:
            score += 10
            reasons.append("🔥 حجم تداول عالٍ وانفجار سيولة يومي")

    # فحص الزخم اللحظي (15 دقيقة) - مفيد لاقتناص الدخول
    if bars_15m is not None and len(bars_15m) >= 5:
        ma_5_15m = bars_15m['close'].rolling(window=5).mean().iloc[-1]
        if price >= ma_5_15m:
            score += 15
            reasons.append("⏱️ تقاطع إيجابي لحظي (15 دقيقة) - سيولة تدخل الآن")
        else:
            score -= 5
            reasons.append("📉 السهم يشهد ضغط بيع لحظي مؤقت")
    else:
        score += 10

    # 3. تحليل الأخبار (News Sentiment)
    news_score, news_reasons = get_news_sentiment(symbol)
    score += news_score
    reasons.extend(news_reasons)

    score = max(20, min(98, score))
    return score, reasons

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    global bot_running, last_error
    text = message.text.strip() if message.text else ""
    chat_id = message.chat.id

    if "تشغيل الرادار المستقل" in text or "تشغيل البوت المتعلم" in text:
        bot_running = True
        bot.send_message(chat_id, "🟢 **تم تفعيل رادار تحدي التدوير التراكمي الشامل.**", reply_markup=get_control_keyboard())
        return
    elif "إيقاف البوت" in text:
        bot_running = False
        bot.send_message(chat_id, "🛑 **تم إيقاف النظام مؤقتاً.**", reply_markup=get_control_keyboard())
        return
    elif "🎯 إضافة سهم للمتابعة" in text:
        bot.send_message(chat_id, "🎯 **وضع التحليل الشامل جاهز!** أرسل رمز السهم (مثال: `TSLA`).", reply_markup=get_control_keyboard())
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

        bot.send_message(chat_id, f"🧠 **محرك التعلم الذاتي والتدوير:**\n- الحالات المسجلة: `{total}`\n- الصفقات المغلقة: `{closed_count}`\n- متوسط أداء التعلم: `{avg_win:.2f}%`\n- الميزات: `تحليل أطر متعددة + قراءة أخبار + وقف متحرك.`", reply_markup=get_control_keyboard())
        return
    elif "تقرير النظام والأخطاء" in text:
        bot.send_message(chat_id, f"🛠️ **التشخيص:**\n{last_error}\nالوضع: `تشغيل ذاتي بالذكاء الاصطناعي 24/7`", reply_markup=get_control_keyboard())
        return
    elif "فحص السوق حالياً" in text:
        bot.send_message(chat_id, "⏳ جاري فحص السوق وتطبيق معايير الذكاء المتقدمة...", reply_markup=get_control_keyboard())
        try:
            symbols = pre_engine.scan_entire_market()
            viable = []
            for sym in symbols:
                p, bs_day, bs_15m = get_market_data(sym)
                if p and 0.25 <= p <= 60.0:
                    sc, _ = evaluate_momentum_and_strategies(sym, p, bs_day, bs_15m)
                    if sc >= 72:
                        viable.append((sym, p, sc))
                if len(viable) >= 3:
                    break
            if not viable:
                bot.send_message(chat_id, "📊 لم تتطابق الشروط الصارمة مع أي سهم حالياً.", reply_markup=get_control_keyboard())
            else:
                msg = "🚀 **الفرص المرشحة لتحدي التدوير (شامل الأخبار والزخم):**\n\n"
                for s, pr, sc in viable:
                    msg += f"• `{s}` | السعر: `${pr}` | التقييم الذكي: `{sc}%`\n"
                bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ: {str(e)[:40]}", reply_markup=get_control_keyboard())
        return

    # تحليل سهم يدوي
    symbol_to_check = text.replace("$", "").strip().upper()
    if len(symbol_to_check) > 0 and len(symbol_to_check) <= 6:
        bot.send_message(chat_id, f"🤖 فحص السهم `{symbol_to_check}` وفق التحليل المتقدم...", reply_markup=get_control_keyboard())
        try:
            price, bars_day, bars_15m = get_market_data(symbol_to_check)
            if not price or price <= 0:
                bot.send_message(chat_id, f"⚠️ تعذر جلب بيانات `{symbol_to_check}`.", reply_markup=get_control_keyboard())
                return
            
            score, reasons = evaluate_momentum_and_strategies(symbol_to_check, price, bars_day, bars_15m)
            reasons_str = "\n".join([f"• {r}" for r in reasons])

            analysis_msg = (
                f"🔬 **تقرير الذكاء الاصطناعي الشامل:**\n"
                f"📌 الرمز: `{symbol_to_check}`\n"
                f"💵 **السعر:** `${price}`\n"
                f"⚡ تقييم الذكاء الاصطناعي: `{score}%`\n\n"
                f"📋 **الأسباب الفنية، الأخبار، والذاكرة:**\n{reasons_str}\n\n"
            )

            if score >= 75:
                try:
                    account_info = alpaca.get_account()
                    total_equity = float(account_info.equity)
                    cash_available = float(account_info.cash)

                    if total_equity >= 200.0:
                        allocation_amount = cash_available * 0.50
                        strategy_mode = "تنويع الأرباح (الحساب تجاوز 200$)"
                    else:
                        allocation_amount = cash_available * 0.90
                        strategy_mode = "تدوير كامل بالربح ورأس المال (تحت 200$)"

                    qty_to_buy = max(1, int(allocation_amount / price))
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
                    )
                except Exception as ex:
                    analysis_msg += f"⚠️ تعذر تنفيذ أمر الشراء: {str(ex)[:40]}"
            else:
                analysis_msg += "🔴 **لم يتم التنفيذ الآلي:** المؤشرات (زخم/أخبار) غير كافية."

            bot.send_message(chat_id, analysis_msg, parse_mode="Markdown", reply_markup=get_control_keyboard())

        except Exception as e:
            bot.send_message(chat_id, f"⚠️ خطأ بالتحليل: {str(e)[:40]}", reply_markup=get_control_keyboard())
    else:
        bot.send_message(chat_id, "الرجاء اختيار أمر من القائمة أو إرسال رمز سهم صحيح.", reply_markup=get_control_keyboard())

def manage_active_trades_and_trailing():
    try:
        conn = sqlite3.connect("jalwe_learning.db")
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, entry_price, stop_loss_price, highest_price, qty, status FROM active_trades_tracker WHERE status='ACTIVE'")
        trades = cursor.fetchall()
        conn.close()

        for symbol, entry_price, stop_loss_price, highest_price, qty, status in trades:
            curr_price, _, _ = get_market_data(symbol)
            if not curr_price:
                continue

            new_highest = max(highest_price, curr_price)
            profit_pct = ((curr_price - entry_price) / entry_price) * 100

            current_stop = stop_loss_price
            if profit_pct >= 4.0 and current_stop < entry_price:
                current_stop = entry_price 
                if profit_pct >= 8.0:
                    current_stop = round(entry_price * 1.03, 2) 

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
                        bot.send_message(TELEGRAM_CHAT_ID, f"🔄🚨 **إغلاق صفقة ({status_msg})!**\n- الرمز: `{symbol}`\n- النتيجة: `{profit_pct:.2f}%`", parse_mode="Markdown")
                except Exception:
                    pass
            
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
                        bot.send_message(TELEGRAM_CHAT_ID, f"🎯💰 **تعصير السهم وجني الأقصى بنجاح!**\n- الرمز: `{symbol}`\n- أرباح: `+{profit_pct:.2f}%`", parse_mode="Markdown")
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
            f"📊📅 **تقرير الأداء الأسبوعي:**\n\n"
            f"• إجمالي الصفقات: `{total_trades}`\n"
            f"• نسبة النجاح: `{win_rate:.1f}%`\n"
            f"• متوسط العائد: `{avg_profit:.2f}%`\n\n"
            f"🧠 *الذكاء الاصطناعي قام بتحديث أوزان الذاكرة.*"
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
            price, bars_day, bars_15m = get_market_data(sym)
            if price and 0.25 <= price <= 60.0:
                score, _ = evaluate_momentum_and_strategies(sym, price, bars_day, bars_15m)
                
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
                            f"🚀 تحدي التدوير — **تنفيذ آلي!**\n"
                            f"📌 الرمز: `{sym}`\n"
                            f"💵 سعر الشراء: `${price}`\n"
                            f"📊 التقييم الشامل: `{score}%`\n"
                            f"🛑 الوقف الأولي: `${initial_stop_loss}`"
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
    print("INFO - JALWE V4 AI Engine (Multi-TF & News) is running...")
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
