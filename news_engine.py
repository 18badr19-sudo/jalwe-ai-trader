import random

def fetch_market_news(symbol):
    """
    Simulates fetching and analyzing financial news sentiment for a given asset.
    """
    sentiments = ["Bullish", "Bearish", "Neutral"]
    # Weights towards active directional sentiment for paper-trading simulations
    return random.choice(sentiments)
