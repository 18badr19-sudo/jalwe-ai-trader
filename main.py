import os
import time
import sqlite3
import threading
from contextlib import contextmanager

import schedule
import telebot
import alpaca_trade_api as tradeapi
import pandas as pd

from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from pre_breakout_engine import PreBreakoutEngine
from target_risk_engine import TargetRiskEngine
from options_flow_engine import OptionsFlowEngine
from chart_and_learning_engine import ChartAndLearningEngine
from active_trade_manager import ActiveTradeManager


# ============================================================
# CONFIG
# ============================================================

DB_PATH = os.getenv("JALWE_DB_PATH", "jalwe_learning.db")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")

# Paper Trading ONLY
APCA_API_BASE_URL = os.getenv(
    "APCA_API_BASE_URL",
    "https://paper-api.alpaca.markets"
)

# Risk settings
MAX_DAILY_LOSS_PCT = 4.0
MAX_OPEN_POSITIONS = 3

RISK_PER_TRADE_PCT = 0.50
MAX_POSITION_ALLOCATION_PCT = 20.0

MIN_STOCK_PRICE = 0.50
MAX_STOCK_PRICE = 100.0

MIN_SIGNAL_SCORE = 82.0

MARKET_SCAN_INTERVAL_MINUTES = 5
ACTIVE_TRADE_CHECK_SECONDS = 30


# ============================================================
# SAFETY CHECKS
# ============================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN غير موجود في البيئة.")

if not APCA_API_KEY_ID or not APCA_API_SECRET_KEY:
    raise RuntimeError("Alpaca API credentials غير موجودة.")

# منع التشغيل على الحساب الحقيقي
if "paper-api.alpaca.markets" not in APCA_API_BASE_URL.lower():
    raise RuntimeError(
        "تم إيقاف النظام: JALWE V4 يعمل Paper Trading فقط. "
        "لا تستخدم Live Trading URL."
    )


# ============================================================
# CLIENTS
# ============================================================

bot = telebot.TeleBot(
    TELEGRAM_TOKEN,
    threaded=False
)

alpaca = tradeapi.REST(
    APCA_API_KEY_ID,
    APCA_API_SECRET_KEY,
    APCA_API_BASE_URL,
    api_version="v2"
)


# ============================================================
# ENGINES
# ============================================================

learning_engine = ChartAndLearningEngine()

pre_engine = PreBreakoutEngine(
    alpaca,
    learning_engine
)

risk_engine = TargetRiskEngine(alpaca)

options_engine = OptionsFlowEngine(alpaca)

trade_manager = ActiveTradeManager(alpaca)


# ============================================================
# GLOBAL STATE
# ============================================================

bot_running = True

last_error = "لا توجد أخطاء مسجلة."

last_cycle_started = None
last_cycle_finished = None

cycle_lock = threading.Lock()


# ============================================================
# DATABASE
# ============================================================

@contextmanager
def db_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():

    with db_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS potential_stocks_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT NOT NULL,

                entry_price REAL,
                target_price REAL,

                score REAL,

                status TEXT,

                timeframe TEXT,

                reasons TEXT,

                rvol REAL,
                volume REAL,
                vwap REAL,

                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_trades_tracker (
                symbol TEXT PRIMARY KEY,

                order_id TEXT,

                entry_price REAL,

                stop_loss_price REAL,

                target1_price REAL,
                target2_price REAL,
                target3_price REAL,

                highest_price REAL,

                qty INTEGER,

                status TEXT,

                strategy TEXT,

                signal_score REAL,

                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS closed_trades_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT,

                entry_price REAL,
                exit_price REAL,

                profit_pct REAL,
                profit_usd REAL,

                result_status TEXT,

                exit_reason TEXT,

                signal_score REAL,

                strategy TEXT,

                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                event_type TEXT,

                symbol TEXT,

                message TEXT,

                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # إضافة أعمدة للـ DB القديمة إذا كانت موجودة
        ensure_columns(
            conn,
            "active_trades_tracker",
            {
                "order_id": "TEXT",
                "target1_price": "REAL",
                "target2_price": "REAL",
                "target3_price": "REAL",
                "strategy": "TEXT",
                "signal_score": "REAL",
                "timestamp": "DATETIME"
            }
        )

        ensure_columns(
            conn,
            "closed_trades_performance",
            {
                "profit_usd": "REAL",
                "exit_reason": "TEXT",
                "signal_score": "REAL",
                "strategy": "TEXT"
            }
        )


def ensure_columns(conn, table_name, columns):

    cursor = conn.cursor()

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    existing_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    for column_name, column_type in columns.items():

        if column_name not in existing_columns:

            cursor.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN {column_name} {column_type}
                """
            )


init_db()


# ============================================================
# TELEGRAM UI
# ============================================================

def get_control_keyboard():

    markup = ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    markup.add(
        KeyboardButton("🟢 تشغيل الرادار المستقل"),
        KeyboardButton("🛑 إيقاف البوت"),

        KeyboardButton("🎯 إضافة سهم للمتابعة"),
        KeyboardButton("💼 محفظتي وأسهمي"),

        KeyboardButton("📊 أداء محفظتي والربح"),
        KeyboardButton("⚙️ حالة الأوامر المفتوحة"),

        KeyboardButton("🔍 فحص السوق حالياً"),
        KeyboardButton("🧠 فحص نموذج التعلم الذاتي"),

        KeyboardButton("⚠️ تقرير النظام والأخطاء")
    )

    return markup


# ============================================================
# DATABASE HELPERS
# ============================================================

def log_event(event_type, message, symbol=None):

    try:

        with db_connection() as conn:

            conn.execute(
                """
                INSERT INTO system_events
                (event_type, symbol, message)
                VALUES (?, ?, ?)
                """,
                (
                    event_type,
                    symbol,
                    message
                )
            )

    except Exception:
        pass


def get_saved_snapshots_count():

    try:

        with db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM potential_stocks_snapshots"
            )

            return cursor.fetchone()[0]

    except Exception:
        return 0


def get_active_symbols():

    try:

        with db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT symbol
                FROM active_trades_tracker
                WHERE status='ACTIVE'
                """
            )

            return {
                row[0]
                for row in cursor.fetchall()
            }

    except Exception:
        return set()


# ============================================================
# MARKET DATA
# ============================================================

def get_market_data(symbol):

    symbol = symbol.upper().strip()

    price = None

    bars_5m = None
    bars_15m = None
    bars_1h = None

    try:

        bars_5m = alpaca.get_bars(
            symbol,
            tradeapi.TimeFrame(
                5,
                tradeapi.TimeFrameUnit.Minute
            ),
            limit=300
        ).df

        if bars_5m is not None and not bars_5m.empty:

            bars_5m = bars_5m.sort_index()

            price = float(
                bars_5m["close"].iloc[-1]
            )

            bars_15m = (
                bars_5m
                .resample("15min")
                .agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum"
                })
                .dropna()
            )

            bars_1h = (
                bars_5m
                .resample("1h")
                .agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum"
                })
                .dropna()
            )

    except Exception as e:

        log_event(
            "MARKET_DATA_ERROR",
            str(e)[:500],
            symbol
        )

    if price is None:

        try:

            trade = alpaca.get_latest_trade(symbol)

            if trade and hasattr(trade, "price"):

                price = float(trade.price)

        except Exception:
            pass

    return (
        price,
        bars_1h,
        bars_15m,
        bars_5m
    )


# ============================================================
# BASIC FEATURES
# ============================================================

def calculate_rvol(bars):

    if bars is None or len(bars) < 20:
        return None

    try:

        average_volume = (
            bars["volume"]
            .iloc[-21:-1]
            .mean()
        )

        current_volume = bars["volume"].iloc[-1]

        if average_volume <= 0:
            return None

        return float(
            current_volume / average_volume
        )

    except Exception:
        return None


def calculate_vwap(bars):

    if bars is None or bars.empty:
        return None

    try:

        typical_price = (
            bars["high"]
            + bars["low"]
            + bars["close"]
        ) / 3

        volume = bars["volume"]

        cumulative_volume = volume.cumsum()

        if cumulative_volume.iloc[-1] <= 0:
            return None

        vwap = (
            typical_price * volume
        ).cumsum() / cumulative_volume

        return float(vwap.iloc[-1])

    except Exception:
        return None


def calculate_atr(bars, period=14):

    if bars is None or len(bars) < period + 1:
        return None

    try:

        previous_close = bars["close"].shift(1)

        tr = pd.concat(
            [
                bars["high"] - bars["low"],
                (bars["high"] - previous_close).abs(),
                (bars["low"] - previous_close).abs()
            ],
            axis=1
        ).max(axis=1)

        atr = tr.rolling(period).mean().iloc[-1]

        if pd.isna(atr):
            return None

        return float(atr)

    except Exception:
        return None


# ============================================================
# NEWS
# ============================================================

def get_news_sentiment(symbol):

    score = 0
    reasons = []

    try:

        news = alpaca.get_news(
            symbol.upper(),
            limit=10
        )

        if not news:
            return 0, []

        positive_words = [
            "surge",
            "jump",
            "beat",
            "profit",
            "contract",
            "buy",
            "growth",
            "upgrade",
            "approval",
            "partnership",
            "guidance"
        ]

        negative_words = [
            "drop",
            "miss",
            "loss",
            "lawsuit",
            "downgrade",
            "sell",
            "crash",
            "risk",
            "offering",
            "dilution",
            "bankruptcy"
        ]

        positive = 0
        negative = 0

        for item in news:

            headline = (
                getattr(item, "headline", "")
                or ""
            ).lower()

            positive += sum(
                word in headline
                for word in positive_words
            )

            negative += sum(
                word in headline
                for word in negative_words
            )

        difference = positive - negative

        if difference > 0:

            score = min(15, difference * 3)

            reasons.append(
                f"📰 محفزات إيجابية: {positive}"
            )

        elif difference < 0:

            score = max(-20, difference * 3)

            reasons.append(
                f"⚠️ محفزات سلبية: {negative}"
            )

    except Exception as e:

        log_event(
            "NEWS_ERROR",
            str(e)[:500],
            symbol
        )

    return score, reasons


# ============================================================
# TECHNICAL / OPPORTUNITY ANALYSIS
# ============================================================

def evaluate_momentum_and_strategies(
    symbol,
    price,
    bars_1h,
    bars_15m,
    bars_5m
):

    score = 40.0
    reasons = []

    rvol = calculate_rvol(bars_5m)
    vwap = calculate_vwap(bars_5m)
    atr = calculate_atr(bars_5m)

    # --------------------------------------------
    # Trend
    # --------------------------------------------

    if bars_1h is not None and len(bars_1h) >= 20:

        ma20 = (
            bars_1h["close"]
            .rolling(20)
            .mean()
            .iloc[-1]
        )

        if price > ma20:

            score += 10

            reasons.append(
                "📈 السعر فوق متوسط 20 شمعة على الساعة"
            )

        else:

            score -= 8

            reasons.append(
                "📉 السعر تحت متوسط 20 شمعة على الساعة"
            )

    # --------------------------------------------
    # RVOL
    # --------------------------------------------

    if rvol is not None:

        if rvol >= 2.0:

            score += 18

            reasons.append(
                f"🔥 RVOL قوي: {rvol:.2f}x"
            )

        elif rvol >= 1.3:

            score += 10

            reasons.append(
                f"📊 RVOL مرتفع: {rvol:.2f}x"
            )

        elif rvol < 0.7:

            score -= 8

            reasons.append(
                f"⚠️ RVOL ضعيف: {rvol:.2f}x"
            )

    # --------------------------------------------
    # VWAP
    # --------------------------------------------

    if vwap is not None:

        if price > vwap:

            score += 10

            reasons.append(
                f"🟢 السعر فوق VWAP: ${vwap:.2f}"
            )

        else:

            score -= 5

            reasons.append(
                f"🔴 السعر تحت VWAP: ${vwap:.2f}"
            )

    # --------------------------------------------
    # 15m Volume
    # --------------------------------------------

    if bars_15m is not None and len(bars_15m) >= 10:

        avg_volume = (
            bars_15m["volume"]
            .iloc[-11:-1]
            .mean()
        )

        current_volume = (
            bars_15m["volume"]
            .iloc[-1]
        )

        if avg_volume > 0:

            volume_ratio = (
                current_volume /
                avg_volume
            )

            if volume_ratio >= 1.5:

                score += 12

                reasons.append(
                    f"🔥 تسارع حجم 15m: {volume_ratio:.2f}x"
                )

    # --------------------------------------------
    # Breakout proximity
    # --------------------------------------------

    if bars_5m is not None and len(bars_5m) >= 20:

        resistance = (
            bars_5m["high"]
            .iloc[-21:-1]
            .max()
        )

        if price >= resistance * 0.995:

            score += 15

            reasons.append(
                f"🎯 السعر قريب جدًا من المقاومة: ${resistance:.2f}"
            )

        elif price >= resistance * 0.98:

            score += 8

            reasons.append(
                "👀 السعر يقترب من منطقة الاختراق"
            )

    # --------------------------------------------
    # News
    # --------------------------------------------

    news_score, news_reasons = (
        get_news_sentiment(symbol)
    )

    score += news_score
    reasons.extend(news_reasons)

    score = max(
        0.0,
        min(100.0, score)
    )

    return {
        "score": round(score, 2),
        "rvol": rvol,
        "vwap": vwap,
        "atr": atr,
        "reasons": reasons
    }


# ============================================================
# POSITION SIZING
# ============================================================

def calculate_position_size(
    price,
    stop_price
):

    try:

        account = alpaca.get_account()

        equity = float(account.equity)
        cash = float(account.cash)

        if equity <= 0 or cash <= 0:
            return 0

        # أقصى خسارة مسموحة للصفقة
        max_risk_usd = (
            equity *
            (RISK_PER_TRADE_PCT / 100)
        )

        risk_per_share = (
            price - stop_price
        )

        if risk_per_share <= 0:
            return 0

        qty_by_risk = int(
            max_risk_usd /
            risk_per_share
        )

        max_allocation = (
            equity *
            (MAX_POSITION_ALLOCATION_PCT / 100)
        )

        qty_by_allocation = int(
            max_allocation /
            price
        )

        qty_by_cash = int(
            (cash * 0.90) /
            price
        )

        qty = min(
            qty_by_risk,
            qty_by_allocation,
            qty_by_cash
        )

        return max(0, qty)

    except Exception as e:

        log_event(
            "POSITION_SIZE_ERROR",
            str(e)[:500]
        )

        return 0


# ============================================================
# DUPLICATE / POSITION CHECK
# ============================================================

def can_open_new_trade(symbol):

    try:

        active_symbols = get_active_symbols()

        if symbol in active_symbols:
            return False, "السهم لديه صفقة مفتوحة."

        positions = alpaca.list_positions()

        if any(
            p.symbol == symbol
            for p in positions
        ):
            return False, "السهم موجود في المحفظة."

        if len(positions) >= MAX_OPEN_POSITIONS:
            return False, "تم الوصول للحد الأقصى للصفقات."

        return True, "OK"

    except Exception as e:

        return False, str(e)


# ============================================================
# SAVE OPPORTUNITY SNAPSHOT
# ============================================================

def save_snapshot(
    symbol,
    price,
    score,
    status,
    analysis
):

    try:

        reasons = " | ".join(
            analysis.get("reasons", [])
        )

        with db_connection() as conn:

            conn.execute(
                """
                INSERT INTO potential_stocks_snapshots
                (
                    symbol,
                    entry_price,
                    target_price,
                    score,
                    status,
                    timeframe,
                    reasons,
                    rvol,
                    volume,
                    vwap
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    price,
                    None,
                    score,
                    status,
                    "5m/15m/1h",
                    reasons[:2000],
                    analysis.get("rvol"),
                    None,
                    analysis.get("vwap")
                )
            )

    except Exception as e:

        log_event(
            "SNAPSHOT_ERROR",
            str(e)[:500],
            symbol
        )


# ============================================================
# OPEN TRADE
# ============================================================

def open_stock_trade(
    symbol,
    price,
    analysis
):

    score = analysis["score"]
    atr = analysis["atr"]

    if atr is None or atr <= 0:

        # fallback محافظ
        stop_price = price * 0.95

    else:

        # الوقف مبني على ATR بدل 5% ثابت
        stop_price = price - (
            atr * 1.5
        )

    stop_price = round(
        max(0.01, stop_price),
        2
    )

    qty = calculate_position_size(
        price,
        stop_price
    )

    if qty <= 0:

        return False, (
            "حجم الصفقة المحسوب = 0 "
            "بسبب إدارة المخاطر."
        )

    allowed, reason = can_open_new_trade(
        symbol
    )

    if not allowed:

        return False, reason

    try:

        order = alpaca.submit_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            type="market",
            time_in_force="day"
        )

        order_id = str(order.id)

        # نحفظ سعر الإشارة مؤقتًا.
        # سيتم لاحقًا تحديثه بسعر التنفيذ الفعلي.
        target1 = round(
            price + ((price - stop_price) * 1.5),
            2
        )

        target2 = round(
            price + ((price - stop_price) * 2.5),
            2
        )

        target3 = round(
            price + ((price - stop_price) * 4.0),
            2
        )

        with db_connection() as conn:

            conn.execute(
                """
                INSERT OR REPLACE INTO
                active_trades_tracker
                (
                    symbol,
                    order_id,
                    entry_price,
                    stop_loss_price,
                    target1_price,
                    target2_price,
                    target3_price,
                    highest_price,
                    qty,
                    status,
                    strategy,
                    signal_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    order_id,
                    price,
                    stop_price,
                    target1,
                    target2,
                    target3,
                    price,
                    qty,
                    "ACTIVE",
                    "PRE_BREAKOUT",
                    score
                )
            )

        return True, {
            "order_id": order_id,
            "qty": qty,
            "stop": stop_price,
            "target1": target1,
            "target2": target2,
            "target3": target3
        }

    except Exception as e:

        log_event(
            "ORDER_ERROR",
            str(e)[:500],
            symbol
        )

        return False, str(e)


# ============================================================
# ACTIVE TRADE MANAGEMENT
# ============================================================

def manage_active_trades():

    try:

        with db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    symbol,
                    order_id,
                    entry_price,
                    stop_loss_price,
                    target1_price,
                    target2_price,
                    target3_price,
                    highest_price,
                    qty,
                    signal_score,
                    strategy
                FROM active_trades_tracker
                WHERE status='ACTIVE'
                """
            )

            trades = cursor.fetchall()

        for trade in trades:

            (
                symbol,
                order_id,
                entry_price,
                stop_loss,
                target1,
                target2,
                target3,
                highest_price,
                qty,
                signal_score,
                strategy
            ) = trade

            price, _, _, bars_5m = (
                get_market_data(symbol)
            )

            if not price:
                continue

            new_highest = max(
                highest_price or entry_price,
                price
            )

            profit_pct = (
                (price - entry_price) /
                entry_price
            ) * 100

            current_stop = stop_loss

            # ----------------------------------------
            # Move stop to breakeven
            # ----------------------------------------

            if (
                target1
                and price >= target1
                and current_stop < entry_price
            ):

                current_stop = entry_price

            # ----------------------------------------
            # Lock profit
            # ----------------------------------------

            if (
                target2
                and price >= target2
            ):

                current_stop = max(
                    current_stop,
                    target1
                )

            # ----------------------------------------
            # Trailing stop
            # ----------------------------------------

            if (
                profit_pct >= 8
                and new_highest > 0
            ):

                trailing_stop = (
                    new_highest * 0.97
                )

                current_stop = max(
                    current_stop,
                    trailing_stop
                )

            should_exit = False
            exit_reason = ""

            # Stop
            if price <= current_stop:

                should_exit = True
                exit_reason = "STOP/TRAILING_STOP"

            # Target 3
            elif (
                target3
                and price >= target3
            ):

                should_exit = True
                exit_reason = "TARGET_3"

            if should_exit:

                try:

                    alpaca.submit_order(
                        symbol=symbol,
                        qty=qty,
                        side="sell",
                        type="market",
                        time_in_force="day"
                    )

                    profit_usd = (
                        (price - entry_price) *
                        qty
                    )

                    result = (
                        "WIN"
                        if profit_pct > 0
                        else "LOSS"
                    )

                    with db_connection() as conn:

                        conn.execute(
                            """
                            UPDATE active_trades_tracker
                            SET status='CLOSED'
                            WHERE symbol=?
                            """,
                            (symbol,)
                        )

                        conn.execute(
                            """
                            INSERT INTO
                            closed_trades_performance
                            (
                                symbol,
                                entry_price,
                                exit_price,
                                profit_pct,
                                profit_usd,
                                result_status,
                                exit_reason,
                                signal_score,
                                strategy
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                symbol,
                                entry_price,
                                price,
                                profit_pct,
                                profit_usd,
                                result,
                                exit_reason,
                                signal_score,
                                strategy
                            )
                        )

                    send_telegram(
                        f"🔄 **إغلاق الصفقة**\n\n"
                        f"📌 `{symbol}`\n"
                        f"💵 الدخول: `${entry_price:.2f}`\n"
                        f"💵 الخروج: `${price:.2f}`\n"
                        f"📊 النتيجة: `{profit_pct:+.2f}%`\n"
                        f"🎯 السبب: `{exit_reason}`"
                    )

                except Exception as e:

                    log_event(
                        "CLOSE_ERROR",
                        str(e)[:500],
                        symbol
                    )

            else:

                with db_connection() as conn:

                    conn.execute(
                        """
                        UPDATE active_trades_tracker
                        SET
                            highest_price=?,
                            stop_loss_price=?
                        WHERE symbol=?
                        """,
                        (
                            new_highest,
                            current_stop,
                            symbol
                        )
                    )

    except Exception as e:

        log_event(
            "TRADE_MANAGER_ERROR",
            str(e)[:500]
        )


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    if not TELEGRAM_CHAT_ID:
        return

    try:

        bot.send_message(
            TELEGRAM_CHAT_ID,
            message,
            parse_mode="Markdown"
        )

    except Exception as e:

        log_event(
            "TELEGRAM_ERROR",
            str(e)[:500]
        )


# ============================================================
# MAIN MARKET CYCLE
# ============================================================

def main_trading_cycle():

    global last_error
    global last_cycle_started
    global last_cycle_finished

    if not bot_running:
        return

    if not cycle_lock.acquire(
        blocking=False
    ):
        return

    try:

        last_cycle_started = time.time()

        # أول شيء: إدارة الصفقات الحالية
        manage_active_trades()

        # ----------------------------------------
        # فحص السوق
        # ----------------------------------------

        symbols = (
            pre_engine.scan_entire_market()
        )

        if not symbols:

            last_cycle_finished = time.time()

            return

        active_symbols = get_active_symbols()

        candidates = []

        for symbol in symbols:

            symbol = symbol.upper()

            if symbol in active_symbols:
                continue

            price, bars_1h, bars_15m, bars_5m = (
                get_market_data(symbol)
            )

            if not price:
                continue

            if not (
                MIN_STOCK_PRICE
                <= price
                <= MAX_STOCK_PRICE
            ):
                continue

            analysis = (
                evaluate_momentum_and_strategies(
                    symbol,
                    price,
                    bars_1h,
                    bars_15m,
                    bars_5m
                )
            )

            score = analysis["score"]

            # حفظ كل فرصة وليس فقط الصفقات
            save_snapshot(
                symbol,
                price,
                score,
                "WATCH",
                analysis
            )

            if score >= MIN_SIGNAL_SCORE:

                candidates.append(
                    (
                        symbol,
                        price,
                        analysis
                    )
                )

        # ----------------------------------------
        # ترتيب الفرص
        # ----------------------------------------

        candidates.sort(
            key=lambda x: x[2]["score"],
            reverse=True
        )

        if not candidates:
            last_cycle_finished = time.time()
            return

        # ----------------------------------------
        # اختيار أفضل فرصة متوافقة مع المخاطر
        # ----------------------------------------

        for symbol, price, analysis in candidates:

            allowed, reason = (
                can_open_new_trade(symbol)
            )

            if not allowed:
                continue

            success, result = open_stock_trade(
                symbol,
                price,
                analysis
            )

            if not success:
                log_event(
                    "TRADE_REJECTED",
                    str(result),
                    symbol
                )
                continue

            send_telegram(
                f"🚨 **JALWE V4 — فرصة مؤكدة**\n\n"
                f"📌 السهم: `{symbol}`\n"
                f"💵 السعر: `${price:.2f}`\n"
                f"🧠 Score: `{analysis['score']:.1f}/100`\n"
                f"📊 RVOL: `{analysis['rvol'] if analysis['rvol'] else 'N/A'}`\n"
                f"📈 VWAP: `${analysis['vwap']:.2f}`\n\n"
                f"🟢 Entry: `${price:.2f}`\n"
                f"🛑 Stop: `${result['stop']:.2f}`\n"
                f"🎯 Target 1: `${result['target1']:.2f}`\n"
                f"🎯 Target 2: `${result['target2']:.2f}`\n"
                f"🎯 Target 3: `${result['target3']:.2f}`\n\n"
                f"⚙️ Strategy: `PRE_BREAKOUT`\n"
                f"📦 Qty: `{result['qty']}`"
            )

            break

        last_cycle_finished = time.time()

    except Exception as e:

        last_error = (
            f"{type(e).__name__}: "
            f"{str(e)[:300]}"
        )

        log_event(
            "MAIN_CYCLE_ERROR",
            last_error
        )

    finally:

        cycle_lock.release()


# ============================================================
# TELEGRAM COMMANDS
# ============================================================

@bot.message_handler(
    func=lambda message: True
)
def handle_messages(message):

    global bot_running

    text = (
        message.text.strip()
        if message.text
        else ""
    )

    chat_id = message.chat.id

    # ----------------------------------------
    # START
    # ----------------------------------------

    if "تشغيل الرادار المستقل" in text:

        bot_running = True

        bot.send_message(
            chat_id,
            "🟢 تم تشغيل رادار JALWE V4.",
            reply_markup=get_control_keyboard()
        )

        return

    # ----------------------------------------
    # STOP
    # ----------------------------------------

    if "إيقاف البوت" in text:

        bot_running = False

        bot.send_message(
            chat_id,
            "🛑 تم إيقاف التداول الآلي مؤقتًا.",
            reply_markup=get_control_keyboard()
        )

        return

    # ----------------------------------------
    # PORTFOLIO
    # ----------------------------------------

    if "محفظتي وأسهمي" in text:

        try:

            account = alpaca.get_account()
            positions = alpaca.list_positions()

            message_text = (
                "💼 **المحفظة**\n\n"
                f"💵 Cash: `${float(account.cash):,.2f}`\n"
                f"💰 Equity: `${float(account.equity):,.2f}`\n\n"
            )

            if not positions:

                message_text += (
                    "لا توجد صفقات مفتوحة."
                )

            else:

                for position in positions:

                    message_text += (
                        f"• `{position.symbol}` "
                        f"| Qty: `{position.qty}` "
                        f"| P/L: "
                        f"`${float(position.unrealized_pl):,.2f}`\n"
                    )

            bot.send_message(
                chat_id,
                message_text,
                parse_mode="Markdown",
                reply_markup=get_control_keyboard()
            )

        except Exception as e:

            bot.send_message(
                chat_id,
                f"⚠️ خطأ: {str(e)[:100]}",
                reply_markup=get_control_keyboard()
            )

        return

    # ----------------------------------------
    # OPEN ORDERS
    # ----------------------------------------

    if "حالة الأوامر المفتوحة" in text:

        try:

            orders = alpaca.list_orders(
                status="open"
            )

            msg = "⚙️ **الأوامر المفتوحة**\n\n"

            if not orders:

                msg += "لا توجد أوامر معلقة."

            else:

                for order in orders:

                    msg += (
                        f"• `{order.symbol}` "
                        f"| `{order.side}` "
                        f"| Qty `{order.qty}`\n"
                    )

            bot.send_message(
                chat_id,
                msg,
                parse_mode="Markdown",
                reply_markup=get_control_keyboard()
            )

        except Exception as e:

            bot.send_message(
                chat_id,
                f"⚠️ خطأ: {str(e)[:100]}",
                reply_markup=get_control_keyboard()
            )

        return

    # ----------------------------------------
    # MARKET SCAN
    # ----------------------------------------

    if "فحص السوق حالياً" in text:

        bot.send_message(
            chat_id,
            "🔍 جاري فحص السوق...",
            reply_markup=get_control_keyboard()
        )

        try:

            symbols = (
                pre_engine.scan_entire_market()
            )

            if not symbols:

                bot.send_message(
                    chat_id,
                    "لا توجد فرص حالياً."
                )

                return

            msg = (
                "🔍 **أبرز النتائج**\n\n"
            )

            for symbol in symbols[:10]:

                price, _, _, _ = (
                    get_market_data(symbol)
                )

                if price:

                    msg += (
                        f"• `{symbol}` "
                        f"${price:.2f}\n"
                    )

            bot.send_message(
                chat_id,
                msg,
                parse_mode="Markdown",
                reply_markup=get_control_keyboard()
            )

        except Exception as e:

            bot.send_message(
                chat_id,
                f"⚠️ خطأ: {str(e)[:100]}",
                reply_markup=get_control_keyboard()
            )

        return

    # ----------------------------------------
    # LEARNING STATUS
    # ----------------------------------------

    if "فحص نموذج التعلم الذاتي" in text:

        try:

            with db_connection() as conn:

                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        COUNT(*),
                        AVG(profit_pct)
                    FROM closed_trades_performance
                    """
                )

                trades, avg_profit = (
                    cursor.fetchone()
                )

            snapshots = (
                get_saved_snapshots_count()
            )

            bot.send_message(
                chat_id,
                (
                    "🧠 **حالة التعلم**\n\n"
                    f"📚 Snapshots: `{snapshots}`\n"
                    f"📊 الصفقات المغلقة: `{trades or 0}`\n"
                    f"📈 متوسط الأداء: "
                    f"`{avg_profit or 0:.2f}%`\n\n"
                    "⚠️ هذه الإحصائيات لا تعني أن النموذج "
                    "يدرّب نفسه تلقائياً؛ التدريب الحقيقي "
                    "سيتم ربطه بـ Learning/Strategy Lab."
                ),
                parse_mode="Markdown",
                reply_markup=get_control_keyboard()
            )

        except Exception as e:

            bot.send_message(
                chat_id,
                f"⚠️ خطأ: {str(e)[:100]}",
                reply_markup=get_control_keyboard()
            )

        return

    # ----------------------------------------
    # SYSTEM STATUS
    # ----------------------------------------

    if "تقرير النظام والأخطاء" in text:

        bot.send_message(
            chat_id,
            (
                "🛠️ **حالة النظام**\n\n"
                f"الحالة: "
                f"`{'RUNNING' if bot_running else 'STOPPED'}`\n"
                f"آخر خطأ: `{last_error}`\n"
                f"آخر دورة: "
                f"`{last_cycle_finished or 'N/A'}`"
            ),
            parse_mode="Markdown",
            reply_markup=get_control_keyboard()
        )

        return

    # ----------------------------------------
    # SYMBOL ANALYSIS
    # ----------------------------------------

    symbol = (
        text
        .replace("$", "")
        .strip()
        .upper()
    )

    if 1 <= len(symbol) <= 6 and symbol.isalpha():

        bot.send_message(
            chat_id,
            f"🔬 جاري تحليل `{symbol}`...",
            reply_markup=get_control_keyboard()
        )

        try:

            price, bars_1h, bars_15m, bars_5m = (
                get_market_data(symbol)
            )

            if not price:

                bot.send_message(
                    chat_id,
                    f"⚠️ تعذر جلب بيانات `{symbol}`."
                )

                return

            analysis = (
                evaluate_momentum_and_strategies(
                    symbol,
                    price,
                    bars_1h,
                    bars_15m,
                    bars_5m
                )
            )

            reasons = "\n".join(
                f"• {reason}"
                for reason in analysis["reasons"]
            )

            bot.send_message(
                chat_id,
                (
                    f"🔬 **تحليل {symbol}**\n\n"
                    f"💵 السعر: `${price:.2f}`\n"
                    f"🧠 Score: `{analysis['score']:.1f}/100`\n"
                    f"📊 RVOL: "
                    f"`{analysis['rvol'] or 'N/A'}`\n"
                    f"📈 VWAP: "
                    f"`{analysis['vwap']:.2f}`\n\n"
                    f"📋 **الأسباب:**\n"
                    f"{reasons or 'لا توجد إشارات كافية'}\n\n"
                    "ℹ️ التحليل اليدوي لا ينفذ صفقة تلقائياً."
                ),
                parse_mode="Markdown",
                reply_markup=get_control_keyboard()
            )

        except Exception as e:

            bot.send_message(
                chat_id,
                f"⚠️ خطأ: {str(e)[:100]}",
                reply_markup=get_control_keyboard()
            )

        return

    bot.send_message(
        chat_id,
        "اختر أمرًا من القائمة أو أرسل رمز سهم صحيح.",
        reply_markup=get_control_keyboard()
    )


# ============================================================
# SCHEDULER
# ============================================================

schedule.every(
    MARKET_SCAN_INTERVAL_MINUTES
).minutes.do(
    main_trading_cycle
)


# ============================================================
# ACTIVE TRADE LOOP
# ============================================================

def active_trade_loop():

    while True:

        try:

            if bot_running:

                manage_active_trades()

        except Exception as e:

            log_event(
                "ACTIVE_LOOP_ERROR",
                str(e)[:500]
            )

        time.sleep(
            ACTIVE_TRADE_CHECK_SECONDS
        )


# ============================================================
# SCHEDULE LOOP
# ============================================================

def schedule_loop():

    while True:

        try:

            schedule.run_pending()

        except Exception as e:

            log_event(
                "SCHEDULER_ERROR",
                str(e)[:500]
            )

        time.sleep(1)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print(
        "JALWE V4 — Paper Trading Engine Started"
    )

    try:

        bot.remove_webhook()

    except Exception:
        pass

    threading.Thread(
        target=schedule_loop,
        daemon=True
    ).start()

    threading.Thread(
        target=active_trade_loop,
        daemon=True
    ).start()

    # تشغيل أول دورة مباشرة
    threading.Thread(
        target=main_trading_cycle,
        daemon=True
    ).start()

    while True:

        try:

            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=30,
                skip_pending=True
            )

        except Exception as e:

            last_error = (
                f"{type(e).__name__}: "
                f"{str(e)[:300]}"
            )

            time.sleep(10)
