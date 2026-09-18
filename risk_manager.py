import logging

class RiskManager:
    def __init__(self, max_loss_percentage=2.0, max_position_size=100.0):
        self.max_loss_percentage = max_loss_percentage
        self.max_position_size = max_position_size
        
    def validate_trade(self, symbol: str, price: float, qty: int) -> bool:
        """
        Validate if the trade order size and cost comply with risk management limits.
        """
        total_cost = price * qty
        if total_cost > self.max_position_size:
            logging.warning(f"⚠️ Trade rejected for {symbol}: Total cost (${total_cost}) exceeds max position limit (${self.max_position_size}).")
            return False
            
        logging.info(f"✅ Trade for {symbol} passed risk management validation.")
        return True

    def calculate_stop_loss_and_take_profit(self, entry_price: float):
        """
        Calculate stop loss and take profit prices based on the entry price.
        """
        stop_loss = entry_price * (1 - (self.max_loss_percentage / 100))
        take_profit = entry_price * (1 + (self.max_loss_percentage * 2 / 100))
        
        return round(stop_loss, 2), round(take_profit, 2)
