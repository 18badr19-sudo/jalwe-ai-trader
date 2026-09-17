import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from ai_engine import AIEngine
from news_engine import fetch_market_news

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ai_engine = AIEngine()

def scheduled_market_scan():
    """
    Background job that runs periodically to scan markets and evaluate AI opportunities.
    """
    logging.info("Starting scheduled background market scan...")
    symbols = ["AAPL", "TSLA", "BTCUSD", "ETHUSD", "NVDA"]
    
    for symbol in symbols:
        sentiment = fetch_market_news(symbol)
        evaluation = ai_engine.evaluate_opportunity(symbol)
        logging.info(f"Scanned {symbol} | Sentiment: {sentiment} | AI Score: {evaluation['ai_score']} | Decision: {evaluation['decision']}")
    
    logging.info("Background market scan completed successfully.")

if __name__ == "__main__":
    logging.info("Initializing JALWE AI TRADER V3 Automation Engine...")
    
    # Initialize background scheduler
    scheduler = BackgroundScheduler()
    # Run market scan every 10 minutes automatically
    scheduler.add_job(scheduled_market_scan, 'interval', minutes=10)
    scheduler.start()
    
    logging.info("Background scheduler is running. Pipeline is active 24/7.")
    
    try:
        # Keep the main process alive
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logging.info("Scheduler shut down safely.")
