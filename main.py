import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from ai_engine import AIEngine
from news_engine import fetch_market_news
from market_data_engine import get_latest_stock_quote
from execution_engine import execute_trade_order
from risk_manager import RiskManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ai_engine = AIEngine()
risk_manager = RiskManager(max_loss_percentage=2.0, max_position_size=100.0)

def evaluate_and_execute_strategy(symbol: str):
    """
    Evaluate hybrid trading strategy and execute orders securely with risk management.
    """
    try:
        # 1. Fetch latest market quote
        quote = get_latest_stock_quote(symbol)
        current_price = float(quote.ap) if quote and hasattr(quote, 'ap') else 0.0
        if current_price == 0.0:
            logging.warning(f"⚠️ Could not fetch valid price for {symbol}")
            return

        # 2. Fetch news sentiment and AI evaluation
        sentiment = fetch_market_news(symbol)
        evaluation = ai_engine.evaluate_opportunity(symbol)
        
        ai_score = evaluation.get('ai_score', 0)
        ai_decision = evaluation.get('decision', 'HOLD')
        
        logging.info(f"Scanned {symbol} | Price: ${current_price} | Sentiment: {sentiment} | AI Score: {ai_score} | Decision: {ai_decision}")
        
        qty = 1  # Default trade quantity
        
        # 3. Decision making and risk validation
        if ai_decision == 'BUY' and ai_score >= 70:
            logging.info(f"🚀 BUY signal confirmed for {symbol}!")
            
            # Validate trade through RiskManager
            if risk_manager.validate_trade(symbol, current_price, qty):
                stop_loss, take_profit = risk_manager.calculate_stop_loss_and_take_profit(current_price)
                logging.info(f"🛡️ Risk parameters set for {symbol} -> Stop Loss: ${stop_loss} | Take Profit: ${take_profit}")
                
                # Execute order via Alpaca
                execute_trade_order(symbol=symbol, qty=qty, side="buy", order_type="market")
            else:
                logging.warning(f"❌ Trade for {symbol} blocked by Risk Manager.")
                
        elif ai_decision == 'SELL' or ai_score < 40:
            logging.info(f"📉 SELL signal triggered for {symbol}. Executing close order...")
            execute_trade_order(symbol=symbol, qty=qty, side="sell", order_type="market")
        else:
            logging.info(f"⏸️ Market stable for {symbol} - HOLD (No action taken).")
            
    except Exception as e:
        logging.error(f"❌ Error executing strategy for {symbol}: {e}")

def scheduled_market_scan():
    """
    Background job that runs periodically to scan markets and execute trading strategies.
    """
    logging.info("Starting scheduled background market scan & execution...")
    symbols = ["AAPL", "TSLA", "BTCUSD", "ETHUSD", "NVDA"]
    
    for symbol in symbols:
        evaluate_and_execute_strategy(symbol)
        
    logging.info("Background market scan and execution completed successfully.")

if __name__ == "__main__":
    logging.info("Initializing JALWE AI TRADER V4 Full Execution & Risk Engine...")
    
    # Initialize background scheduler
    scheduler = BackgroundScheduler()
    # Run market scan & execution every 10 minutes automatically
    scheduler.add_job(scheduled_market_scan, 'interval', minutes=10)
    scheduler.start()
    
    logging.info("Background scheduler is running. Pipeline is fully active 24/7.")
    
    try:
        # Keep the main process alive
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logging.info("Scheduler shut down safely.")
