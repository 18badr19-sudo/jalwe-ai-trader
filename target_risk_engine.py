class TargetRiskEngine:
    def __init__(self, alpaca_api):
        self.alpaca = alpaca_api

    def calculate_levels(self, symbol, current_price):
        """حساب الدخول، وقف الخسارة، والأهداف بناءً على الهيكلة الفنية وATR"""
        try:
            bars = self.alpaca.get_bars(symbol, "1Day", limit=14).df
            if bars.empty:
                # قيم افتراضية آمنة في حال عدم توفر البيانات اليومية الكافية
                atr = current_price * 0.02
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
            return {
                "entry_zone": f"${current_price}",
                "stop_loss": f"${round(current_price * 0.98, 2)}",
                "target_1": f"${round(current_price * 1.05, 2)}",
                "target_2": f"${round(current_price * 1.10, 2)}",
                "target_3": "Dynamic"
            }
