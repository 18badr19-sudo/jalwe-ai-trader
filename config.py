"""
JALWE AI TRADER V3
Configuration Module
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Trading Safety Switch
LIVE_TRADING_ENABLED = False  # Strict paper trading safety gate

# System Architecture & Logging Config
MARKET_DATA_PROVIDER = "alpaca"
SCAN_INTERVAL_SECONDS = 10  # Time interval between market scans
LOG_LEVEL = "INFO"

# Scanner Filtering & Technical Thresholds
MIN_STOCK_PRICE = 1.0
MAX_STOCK_PRICE = 500.0
MIN_VOLUME = 100000
MIN_VOLUME_THRESHOLD = 100000
MIN_DAILY_DOLLAR_VOLUME = 1000000.0
MAX_SPREAD_PERCENT = 1.0
VWAP_ENABLED = True
TIMEFRAME = "1Min"
CANDLE_COUNT = 100
ATR_PERIOD = 14
RSI_PERIOD = 14
EMA_FAST = 9
EMA_SLOW = 21
SMA_50 = 50
SMA_200 = 200
MIN_RVOL = 1.5
RVOL_THRESHOLD = 1.5
HIGH_RVOL_THRESHOLD = 3.0
HIGH_RVOD_THRESHOLD = 3.0
RVOL_LOOKBACK_PERIOD = 20
VOLUME_ACCELERATION_MIN = 1.0
VOLUME_ACCELERATION_THRESHOLD = 1.0
VOLUME_SPEED_WINDOW = 5
LIQUIDITY_SCORE_MIN = 50.0

# Risk Management Parameters
MAX_DAILY_LOSS_PERCENT = 5.0
MAX_POSITION_SIZE_PERCENT = 10.0
MAX_POSITION_SIZE_DOLLARS = 5000.0
MAX_OPEN_POSITIONS = 5
MAX_RISK_PER_TRADE_PERCENT = 1.0
STOP_LOSS_ATR_MULTIPLIER = 2.0
TAKE_PROFIT_ATR_MULTIPLIER = 3.0
MIN_RISK_REWARD_RATIO = 1.5

# Alpaca API Credentials
APAL_API_KEY = os.getenv("APEX_API_KEY", os.getenv("ALPACA_API_KEY", ""))
APAL_SECRET_KEY = os.getenv("APEX_SECRET_KEY", os.getenv("ALPACA_SECRET_KEY", ""))

# Base URLs
APAL_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
APAL_DATA_BASE_URL = "https://data.alpaca.markets"

# Telegram Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")