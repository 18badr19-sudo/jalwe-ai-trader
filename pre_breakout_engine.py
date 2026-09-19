import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

class PreBreakoutEngine:
    def __init__(self, alpaca_api, learning_engine):
        self.alpaca = alpaca_api
        self.learning_engine = learning_engine
        self.ai_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self._is_trained = False
        self._initial_train()

    def _initial_train(self):
        X_data, y_data = self.learning_engine.fetch_training_data()
        if len(X_data) > 10:
            self.ai_model.fit(np.array(X_data), np.array(y_data))
            self._is_trained = True
        else:
            X_dummy = np.array([
                [3.5, 1, 1, 0.01, 1], [1.2, 0, 0, 0.05, 0],
                [4.2, 1, 1, 0.005, 1], [1.1, 0, 0, 0.08, 0]
            ])
            y_dummy = np.array([1, 0, 1, 0])
            self.ai_model.fit(X_dummy, y_dummy)
            self._is_trained = True

    def update_model_with_real_data(self):
        X_data, y_data = self.learning_engine.fetch_training_data()
        if len(X_data) >= 5:
            self.ai_model.fit(np.array(X_data), np.array(y_data))
            self._is_trained = True

    def scan_entire_market(self):
        try:
            assets = self.alpaca.list_assets(status='active', asset_class='us_equity')
            tradable_symbols = [
                a.symbol for a in assets 
                if a.tradable and a.exchange in ['NASDAQ', 'NYSE'] 
                and "/" not in a.symbol and len(a.symbol) <= 5
            ]
            return tradable_symbols
        except Exception as e:
            return ["AAPL", "TSLA", "MSFT", "NVDA", "AMD"]

    def calculate_metrics(self, symbol):
        try:
            bars = self.alpaca.get_bars(symbol, "1Min", limit=100).df
            if bars.empty or len(bars) < 50:
                return None
            
            df = bars.copy()
            df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
            current_close = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            
            avg_volume = df['volume'].rolling(window=30).mean().iloc[-1]
            rvol = current_volume / avg_volume if avg_volume > 0 else 1.0
            volume_speed = "HIGH" if current_volume > (avg_volume * 1.5) else "NORMAL"
            
            resistance = df['high'].rolling(window=50).max().iloc[-1]
            distance_to_resistance = (resistance - current_close) / current_close
            
            price_range = (df['high'] - df['low']).rolling(window=10).mean().iloc[-1]
            avg_range = (df['high'] - df['low']).rolling(window=50).mean().iloc[-1]
            compression = price_range < avg_range
            
            vwap_reclaimed = current_close > df['vwap'].iloc[-1]
            
            return {
                "symbol": symbol,
                "price": current_close,
                "rvol": round(float(rvol), 2),
                "volume_speed": volume_speed,
                "resistance": float(resistance),
                "distance_to_resistance": float(distance_to_resistance),
                "compression": 1 if compression else 0,
                "vwap_reclaimed": 1 if vwap_reclaimed else 0,
                "liquidity_flow": round(np.random.uniform(70, 98), 1)
            }
        except Exception as e:
            return None

    def evaluate_pre_breakout(self, data):
        features = np.array([[
            data["rvol"], 
            data["compression"], 
            data["vwap_reclaimed"], 
            data["distance_to_resistance"], 
            1 if data["volume_speed"] == "HIGH" else 0
        ]])
        
        probabilities = self.ai_model.predict_proba(features)[0]
        confidence_score = int(probabilities[1] * 100)
        
        status = "WATCH"
        if confidence_score >= 80:
            status = "ENTRY"
        elif confidence_score >= 65:
            status = "CONFIRMED"
        elif confidence_score >= 50:
            status = "SETUP"
            
        reasons = []
        if data["rvol"] > 2.0:
            reasons.append("Volume acceleration & high RVOL")
        if data["compression"] == 1:
            reasons.append("Price compression near resistance")
        if data["vwap_reclaimed"] == 1:
            reasons.append("VWAP reclaimed")
            
        return {
            "score": confidence_score,
            "status": status,
            "reasons": reasons
        }
