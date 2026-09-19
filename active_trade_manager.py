class ActiveTradeManager:
    def __init__(self, alpaca_api):
        self.alpaca = alpaca_api

    def monitor_open_positions(self):
        """مراقبة الصفقات النشطة وإدارة الخروج الجزئي أو الوقف المتحرك"""
        try:
            positions = self.alpaca.list_positions()
            for pos in positions:
                symbol = pos.symbol
                current_price = float(pos.current_price)
                avg_entry = float(pos.avg_entry_price)
                profit_pct = (current_price - avg_entry) / avg_entry
                
                # إدارة متقدمة: إذا تجاوز الربح 4%، يتم إرسال تنبيه أو ضبط حماية للصفقة
                if profit_pct >= 0.04:
                    print(f"Target 1 reached for {symbol}! Managing trailing/partial exit.")
        except Exception as e:
            print(f"Error in Trade Manager: {e}")
