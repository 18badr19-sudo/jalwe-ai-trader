import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from ai_engine import AIEngine
from news_engine import fetch_market_news
from market_data_engine import get_latest_stock_quote
from execution_engine import execute_trade_order  # استيراد محرك التنفيذ الآلي

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ai_engine = AIEngine()

def evaluate_and_execute_strategy(symbol: str):
    """
    تقييم الاستراتيجية المزدوجة وتنفيذ الأمر إذا تحقق الشرط
    """
    try:
        # 1. جلب السعر اللحظي
        quote = get_latest_stock_quote(symbol)
        current_price = float(quote.ap) if quote and hasattr(quote, 'ap') else 0.0
        if current_price == 0.0:
            return

        # 2. جلب الأخبار وتقييم الذكاء الاصطناعي
        sentiment = fetch_market_news(symbol)
        evaluation = ai_engine.evaluate_opportunity(symbol)
        
        ai_score = evaluation.get('ai_score', 0)
        ai_decision = evaluation.get('decision', 'HOLD')
        
        logging.info(f"Scanned {symbol} | Price: ${current_price} | Sentiment: {sentiment} | AI Score: {ai_score} | Decision: {ai_decision}")
        
        # 3. اتخاذ القرار وتنفيذ الأمر الآلي
        if ai_decision == 'BUY' and ai_score >= 70:
            logging.info(f"🚀 إشارة شراء مؤكدة للسهم {symbol}! جاري إرسال أمر التنفيذ...")
            # تنفيذ أمر شراء حقيقي على حساب التجربة (مثلاً بكمية سهم واحد للاختبار)
            execute_trade_order(symbol=symbol, qty=1, side="buy", order_type="market")
            
        elif ai_decision == 'SELL' or ai_score < 40:
            logging.info(f"📉 إشارة بيع للسهم {symbol}! جاري إغلاق المراكز أو إرسال أمر بيع...")
            execute_trade_order(symbol=symbol, qty=1, side="sell", order_type="market")
        else:
            logging.info(f"⏸️ السوق مستقر للسهم {symbol} - القرار: HOLD (لا توجد صفقات جديدة).")
            
    except Exception as e:
        logging.error(f"❌ خطأ أثناء تنفيذ الاستراتيجية للسهم {symbol}: {e}")

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
    logging.info("Initializing JALWE AI TRADER V4 Full Execution Engine...")
    
    # Initialize background scheduler
    scheduler = BackgroundScheduler()
    # Run market scan & execution every 10 minutes automatically
    scheduler.add_job(scheduled_market_scan, 'interval', minutes=10)
    scheduler.start()
    
    logging.info("Background scheduler is running. Trading pipeline & execution is active 24/7.")
    
    try:
        # Keep the main process alive
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logging.info("Scheduler shut down safely.")
