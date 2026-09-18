import requests
import logging

def get_top_trending_stocks(limit=10):
    """
    Fetch top trending and gaining stocks from Yahoo Finance (External Radar).
    """
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&lang=en-US&region=US&scrIds=day_gainers&count={limit}"
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        quotes = data['finance']['result'][0]['quotes']
        symbols = [q['symbol'] for q in quotes]
        
        # Clean complex symbols that Alpaca might not accept
        clean_symbols = [sym for sym in symbols if '^' not in sym and '-' not in sym]
        
        logging.info(f"🌐 External Scanner detected trending stocks today: {clean_symbols}")
        return clean_symbols
        
    except Exception as e:
        logging.error(f"❌ External scanner failed, falling back to emergency list: {e}")
        return ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]
