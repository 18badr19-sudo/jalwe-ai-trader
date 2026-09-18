import time
import logging
import schedule
from datetime import datetime

# Import core modules matching exact repository filenames
from database_manager import DatabaseManager
from market_scanner import MarketScanner
from liquidity_engine import LiquidityEngine
from options_engine import OptionsEngine
from news_engine import NewsEngine
from regime_detector import RegimeDetector
from strategy_lab import StrategyLab
from learning_engine import LearningEngine
from risk_manager import RiskEngine  # Matched with your repository filename risk_manager.py
from position_manager import PositionManager
from execution_engine import ExecutionEngine
from telegram_notifier import send_telegram_message
from market_data_engine import MarketDataEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize all core engines
db = DatabaseManager()
scanner = MarketScanner()
liquidity_engine = LiquidityEngine()
options_engine = OptionsEngine()
news_engine = NewsEngine()
regime_detector = RegimeDetector()
strategy_lab = StrategyLab()
learning_engine = LearningEngine()
risk_engine = RiskEngine()
position_manager = PositionManager()
execution_engine = ExecutionEngine()
data_engine = MarketDataEngine()

def run_quant_ai_pipeline():
    """
    Main scheduled 24/7 Quant/AI Research and Paper Trading pipeline.
    Executes multi-stage scanning, regime detection, risk validation, and AI execution.
    """
    logging.info("🚀 Starting JALWE AI TRADER V4 Quant AI pipeline cycle...")
    
    # 1. Get Account Balance & Check Circuit Breaker
    account_balance = execution_engine.get_account_balance()
    if risk_engine.check_circuit_breaker(current_daily_pnl=0.0, current_drawdown=0.0):
        logging.warning("Circuit breaker active. Skipping trading cycle.")
        return

    # 2. Market Regime Detection (using benchmark proxy)
    regime = regime_detector.detect_market_regime(None)
    logging.info(f"Detected Market Regime: {regime}")

    # 3. Multi-Stage Market Scan
    active_symbols = scanner.quick_scan()
    logging.info(f"Scanned active universe pool: {active_symbols}")

    for symbol in active_symbols[:3]: # Evaluate top candidates
        try:
            logging.info(f"Deep analyzing symbol: {symbol}")
            
            # Fetch data & check liquidity
            df = data_engine.fetch_latest_bars(symbol, limit=40)
            
            if df is None or len(df) < 20:
                continue

            liquidity_data = liquidity_engine.calculate_liquidity_flow(df)
            news_data = news_engine.fetch_symbol_news(symbol)

            # Feature Snapshot for AI Learning Store
            feature_snapshot = {
                "symbol": symbol,
                "regime": regime,
                "liquidity_score": liquidity_data.get("liquidity_score", 0.0),
                "rvol": liquidity_data.get("rvol", 1.0),
                "sentiment": news_data.get("sentiment_score", 0.0)
            }
            db.save_features(symbol, feature_snapshot, regime)

            # Evaluate strategy criteria & execute if conditions met
            if liquidity_data.get("liquidity_score", 0.0) > 2.0 and news_data.get("sentiment_score", -1.0) >= 0.0:
                logging.info(f"Opportunity validated for {symbol}! Executing paper trade...")
                
                shares = 1 # Conservative sizing for $100 paper budget
                current_price = float(df["close"].iloc[-1])
                
                if risk_engine.validate_new_trade(account_balance, current_price * shares):
                    order_res = execution_engine.execute_order(symbol, shares, "BUY")
                    
                    # Log trade in Database & Learning Engine
                    db.log_trade(symbol, "BUY", shares, current_price, "OPEN", feature_snapshot)
                    
                    send_telegram_message(f"🚨 *JALWE AI Paper Trade Executed*\nSymbol: {symbol}\nAction: BUY\nPrice: ${current_price:.2f}\nRegime: {regime}")
                else:
                    logging.info(f"Trade for {symbol} rejected by Risk Engine.")
            else:
                logging.info(f"No high-conviction setup found for {symbol}.")

        except Exception as e:
            logging.error(f"Error processing pipeline for {symbol}: {e}")

    logging.info("JALWE AI TRADER V4 cycle completed successfully.")

def main():
    startup_msg = "🔥 *JALWE AI TRADER V4 (Quant & AI Engine)* is now fully online on Railway 24/7!"
    logging.info(startup_msg)
    send_telegram_message(startup_msg)

    # Run immediately on startup
    run_quant_ai_pipeline()

    # Schedule to run every 15 minutes
    schedule.every(15).minutes.do(run_quant_ai_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
