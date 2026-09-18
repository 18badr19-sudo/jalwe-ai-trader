import time
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from alpaca_trade_api.rest import REST, TimeFrame

from ai_engine import AIEngine
from news_engine import fetch_market_news
from market_data_engine import get_latest_stock_quote
from execution_engine import execute_trade_order
from risk_manager import RiskManager
from technical_indicators import calculate_rsi, calculate_macd
from external_scanner import get_top_trending_stocks

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ai_engine = AIEngine()
risk_manager = RiskManager(max_loss_percentage=2.0, max_position_size=100.0)

# Initialize Alpaca REST API to fetch historical data for technical indicators
alpaca_api = REST(
    os.getenv("APCA_API_KEY_ID"),
    os.getenv("APCA_API_SECRET_KEY"),
    base_url=os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
)

def get_historical_close_prices(symbol: str, limit: int = 40):
    """Fetch historical closing prices for RSI and MACD calculations."""
    try:
        bars = alpaca_api.get_bars(symbol, TimeFrame.Day, limit=limit).df
        if not bars.empty:
            return bars['close'].tolist()
    except Exception as e:
        logging.error(f"Failed to fetch historical data for {symbol}: {e}")
    return []

def evaluate_and_execute_strategy(symbol: str):
    """
    Evaluate hybrid trading strategy (AI + Technicals) and execute orders securely.
    """
    try:
        # 1. Fetch latest market quote
        quote = get_latest_stock_quote(symbol)
        current_price = float(quote.ap) if quote and hasattr(quote, 'ap') else 0.0
        if current_price == 0.0:
            logging.warning(f"⚠️ Could not fetch valid price for {symbol}")
            return

        # 2. Fetch Historical Prices & Calculate Technical Indicators
        historical_prices = get_historical_close_prices(symbol)
        rsi = calculate_rsi(historical_prices)
        macd, macd_signal = calculate_macd(historical_prices)

        # 3. Fetch news sentiment and AI evaluation
        sentiment = fetch_market_news(symbol)
        evaluation = ai_engine.evaluate_opportunity(symbol)
        
        ai_score = evaluation.get('ai_score', 0)
        ai_decision = evaluation.get('decision', 'HOLD')
        
        logging.info(f"📊 {symbol} | Price: ${current_price} | RSI: {rsi} | MACD: {macd}")
        logging.info(f"🧠 {symbol} | AI Score: {ai_score} | Sentiment: {sentiment} | Decision: {ai_decision}")
        
        qty = 1  # Default trade quantity
        
        # 4. Advanced Decision Making (AI + Technicals) & Risk Validation
        if ai_decision == 'BUY' and ai_score >= 70 and rsi < 70:
            logging.info(f"🚀 Strong BUY signal confirmed for {symbol} (AI + Technicals)!")
            
            if risk_manager.validate_trade(symbol, current_price, qty):
                stop_loss, take_profit = risk_manager.calculate_stop_loss_and_take_profit(current_price)
                logging.info(f"🛡️ Risk parameters set -> SL: ${stop_loss} | TP: ${take_profit}")
                execute_trade_order(symbol=symbol, qty=qty, side="buy", order_type="market")
            else:
                logging.warning(f"❌ Trade for {symbol} blocked by Risk Manager.")
                
        elif ai_decision == 'SELL' or ai_score < 40 or rsi >= 80:
            logging.info(f"📉 SELL signal triggered for {symbol}. Executing close order...")
            execute_trade_order(symbol=symbol, qty=qty, side="sell", order_type="market")
        else:
            logging.info(f"⏸️ Market stable for {symbol} - HOLD.")
            
    except Exception as e:
        logging.error(f"❌ Error executing strategy for {symbol}: {e}")

def scheduled_market_scan():
    logging.info("Starting dual scan (External Radar + Internal AI/Tech Analysis)...")
    
    # 1. Fetch trending stocks from outside the platform
    trending_symbols = get_top_trending_stocks(limit=10)
    
    # 2. Evaluate them using AI and Technical Indicators
    for symbol in trending_symbols:
        evaluate_and_execute_strategy(symbol)
        
    logging.info("Hunting cycle completed successfully.")

if __name__ == "__main__":
    logging.info("Initializing JALWE AI TRADER V4 (AI + Technicals + Risk + External Radar)...")
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_market_scan, 'interval', minutes=10)
    scheduler.start()
    
    logging.info("Background scheduler is running 24/7.")
    
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logging.info("Scheduler shut down safely.")
