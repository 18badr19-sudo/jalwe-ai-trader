import time
import urllib.parse
import urllib.request
import alpaca_trade_api as tradeapi
import pandas as pd

TELEGRAM_BOT_TOKEN = "8830107385:AAEUA0f3lPFPX_dmLHrLc6RXKaFCNe9y9JA"
TELEGRAM_CHAT_ID = "709594771"

API_KEY = "PKZH7LNTI3TMTNPMZZXY4P2XJG".strip()
API_SECRET = "EAjqHomEwD4azP9gHycvC7W9egsYWH1BsP9AE9HdSSmn".strip()
BASE_URL = "https://paper-api.alpaca.markets"

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

TRADE_AMOUNT_USD = 90.0

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': message}).encode('utf-8')
        urllib.request.urlopen(url, data=data)
    except Exception as e:
        print(f"Telegram Error: {e}")

def scan_market_globally():
    try:
        positions = api.list_positions()
        if len(positions) > 0:
            print(f"Active position found in ({positions[0].symbol}). Waiting for target or stop-loss closure...")
            return

        print("Scanning global market watchlist for high volume inflows and momentum...")
        
        dynamic_list = [
            "SOFI", "PLTR", "NIO", "F", "CCL", "SNAP", "INTC", "AMD", "PFE", "BAC",
            "AMC", "GME", "RIVN", "LCID", "X", "CLF", "AAL", "UAL", "JBLU", "NOK",
            "BB", "UBER", "LYFT", "HOOD", "COIN", "MARA", "RIOT", "PLUG", "ENPH", "PYPL",
            "TSLA", "AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "SPY", "QQQ"
        ]

        for symbol in dynamic_list:
            bars = api.get_bars(symbol, tradeapi.TimeFrame.Minute, limit=30, feed='iex').df
            if bars.empty or len(bars) < 20:
                continue

            close_prices = bars['close']
            current_price = close_prices.iloc[-1]
            ema_20 = close_prices.ewm(span=20).mean().iloc[-1]
            
            current_volume = bars['volume'].iloc[-1]
            avg_volume = bars['volume'].rolling(20).mean().iloc[-1]

            high_low = bars['high'] - bars['low']
            high_close = (bars['high'] - close_prices.shift()).abs()
            low_close = (bars['low'] - close_prices.shift()).abs()
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean().iloc[-1]

            if current_price > ema_20 and current_volume > (avg_volume * 2.0):
                print(f"High volume breakout detected on symbol: {symbol}!")
                
                qty = round(TRADE_AMOUNT_USD / current_price, 4)
                stop_loss_price = round(current_price - (1.5 * atr), 2)
                take_profit_price = round(current_price + (2.5 * atr), 2)

                order = api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side='buy',
                    type='market',
                    time_in_force='gtc',
                    order_class='bracket',
                    stop_loss={'stop_price': stop_loss_price},
                    take_profit={'limit_price': take_profit_price}
                )
                
                msg = (
                    f"🚨 Institutional Momentum Alert!\n"
                    f"📈 Symbol: {symbol}\n"
                    f"💵 Entry Price: {current_price} | Qty: {qty}\n"
                    f"🛑 Stop Loss: {stop_loss_price}\n"
                    f"🎯 Take Profit: {take_profit_price}"
                )
                send_telegram_message(msg)
                print(f"Order successfully executed for {symbol} and Telegram alert sent!")
                break

    except Exception as e:
        print(f"Error during market scan: {e}")

if __name__ == "__main__":
    print("Global market scanning & momentum bot activated securely...")
    send_telegram_message("🤖 Autonomous trading bot activated and monitoring global market liquidity!")
    
    while True:
        try:
            clock = api.get_clock()
            if clock.is_open:
                print("Market is open. Scanning global liquidity...")
                scan_market_globally()
            else:
                print("Market is closed. Monitoring pre-market conditions...")
        except Exception as e:
            print(f"Loop Error: {e}")
        time.sleep(60)