import time
import logging
import schedule
from datetime import datetime
from market_data_engine import MarketDataEngine
from technical_indicators import TechnicalIndicators
from risk_manager import RiskManager
from execution_engine import ExecutionEngine
from telegram_notifier import send_telegram_message

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize engines
data_engine = MarketDataEngine()
indicators_engine = TechnicalIndicators()
risk_manager = RiskManager()
execution_engine = ExecutionEngine()

# Target stocks to monitor
TARGET_STOCKS = ["AAPL", "TSLA", "MSFT"]

def job_run_trading_bot():
    """
    Main scheduled trading bot job that fetches data, evaluates indicators,
    checks risk rules, executes orders, and reports via Telegram.
    """
    logging.info("Starting JALWE AI TRADER V4 market scanning cycle...")
    account_balance = execution_engine.get_account_balance()
    logging.info(f"Current Paper Trading Account Balance: ${account_balance:.2f}")

    for symbol in TARGET_STOCKS:
        try:
            logging.info(f"Analyzing market data for {symbol}...")
            df = data_engine.fetch_latest_bars(symbol, limit=50)
            
            if not data_engine.validate_data_quality(df):
                logging.warning(f"Data quality check failed for {symbol}. Skipping.")
                continue

            # Calculate technical indicators and generate signals
            df_analyzed = indicators_engine.generate_signals(df)
            latest_row = df_analyzed.iloc[-1]
            current_price = float(latest_row["close"])
            signal = latest_row["signal"]
            rsi_val = float(latest_row["rsi"])

            logging.info(f"Symbol: {symbol} | Price: ${current_price:.2f} | RSI: {rsi_val:.2f} | Signal: {signal}")

            # Validate risk and execute trade if signal is generated
            if risk_manager.validate_trade_risk(symbol, signal, current_price, account_balance):
                shares = risk_manager.calculate_position_shares(current_price, account_balance)
                if shares > 0 and signal in ["BUY", "SELL"]:
                    logging.info(f"Executing {signal} order for {shares} shares of {symbol}...")
                    execution_engine.execute_order(symbol, shares, signal)
                else:
                    logging.info(f"Calculated shares for {symbol} is 0 or invalid signal action.")
            else:
                logging.info(f"No trade executed for {symbol}. Conditions or risk limits not met.")

        except Exception as e:
            logging.error(f"Error processing trading cycle for {symbol}: {e}")

    logging.info("Trading cycle completed. Sleeping until next schedule...")

def main():
    """
    Main entry point for 24/7 cloud deployment on Railway.
    """
    startup_msg = "🚀 *JALWE AI TRADER V4* is now online and running on Railway 24/7 with $100 Paper Budget!"
    logging.info(startup_msg)
    send_telegram_message(startup_msg)

    # Run immediately once on startup
    job_run_trading_bot()

    # Schedule the job to run every 10 minutes
    schedule.every(10).minutes.do(job_run_trading_bot)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
