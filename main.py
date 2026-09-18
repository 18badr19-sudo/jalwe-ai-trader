import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from ai_engine import AIEngine
from news_engine import fetch_market_news
from market_data_engine import get_latest_stock_quote  # استيراد محرك بيانات السوق الجديد

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ai_engine = AIEngine()

def scheduled_market_scan():
    """
    Background job that runs periodically to scan markets, fetch live prices, and evaluate AI opportunities.
    """
    logging.info("Starting scheduled background market scan...")
    symbols = ["AAPL", "TSLA", "BTCUSD", "ETHUSD", "NVDA"]
    
    for symbol in symbols:
        # 1. جلب السعر اللحظي عبر MarketDataEngine (مع معالجة الأصول مثل الأسهم)
        try:
            quote = get_latest_stock_quote(symbol)
            current_price = float(quote.ap) if quote and hasattr(quote, 'ap') else 0.0
        except Exception as e:
            current_price = 0.0
            
        # 2. جلب الأخبار وتقييم الذكاء الاصطناعي
        sentiment = fetch_market_news(symbol)
        evaluation = ai_engine.evaluate_opportunity(symbol)
        
        logging.info(f"Scanned {symbol} | Price: ${current_price} | Sentiment: {sentiment} | AI Score: {evaluation['ai_score']} | Decision: {evaluation['decision']}")
    
    logging.info("Background market scan completed successfully.")

if __name__ == "__main__":
    logging.info("Initializing JALWE AI TRADER V4 Automation Engine...")
    
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
