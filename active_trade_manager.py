class ActiveTradeManager:
    def __init__(self, alpaca_api):
        self.alpaca = alpaca_api

    def monitor_open_positions(self):
        try:
            positions = self.alpaca.list_positions()
            for pos in positions:
                symbol = pos.symbol
                current_price = float(pos.current_price)
                avg_entry = float(pos.avg_entry_price)
                qty = float(pos.qty)
                profit_pct = (current_price - avg_entry) / avg_entry
                
                if profit_pct >= 0.05 and qty > 1:
                    sell_qty = int(qty / 2)
                    self.alpaca.submit_order(
                        symbol=symbol,
                        qty=sell_qty,
                        side='sell',
                        type='market',
                        time_in_force='gtc'
                    )
                    print(f"ActiveTradeManager: Partial take profit executed for {symbol} at +5%")
        except Exception as e:
            print(f"Error in ActiveTradeManager: {e}")
