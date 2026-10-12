class TargetRiskEngine:
    def __init__(self, alpaca_api):
        self.alpaca = alpaca_api

    def calculate_levels(self, symbol, current_price):
        """مستويات بحثية قديمة من متوسط النطاق اليومي؛ ليست ATR أو أوامر JALWE"""
        try:
            bars = self.alpaca.get_bars(symbol, "1Day", limit=14).df
            if bars.empty:
                raise ValueError('Daily price evidence is unavailable.')
            else:
                high_low = bars['high'] - bars['low']
                atr = high_low.mean()
                
            entry_min = round(current_price * 0.995, 2)
            entry_max = round(current_price * 1.005, 2)
            
            # وقف الخسارة أسفل الهيكل أو بناءً على الـ ATR
            stop_loss = round(current_price - (atr * 1.5), 2)
            
            # الأهداف متعددة ومحسوبة ديناميكياً
            target_1 = round(current_price + (atr * 2.0), 2)
            target_2 = round(current_price + (atr * 3.5), 2)
            target_3 = "Dynamic / Trailing"
            
            return {
                "entry_zone": f"${entry_min} – ${entry_max}",
                "stop_loss": f"${stop_loss}",
                "target_1": f"${target_1}",
                "target_2": f"${target_2}",
                "target_3": f"{target_3}"
            }
        except Exception as e:
            return {"status": "UNAVAILABLE", "reason": type(e).__name__,
                    "entry_zone": None, "stop_loss": None,
                    "target_1": None, "target_2": None, "target_3": None}
