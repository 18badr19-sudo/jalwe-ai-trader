import pandas as pd
import logging

class RiskManager:
    def __init__(self, max_portfolio_risk: float = 0.05, max_position_size: float = 20.0):
        """
        Initializes risk management parameters for $100 paper trading budget.
        - max_portfolio_risk: Maximum allowed risk per trade (e.g., 5%)
        - max_position_size: Maximum dollar amount allocated per single trade ($20)
        """
        self.max_portfolio_risk = max_portfolio_risk
        self.max_position_size = max_position_size

    def calculate_position_shares(self, current_price: float, account_balance: float = 100.0) -> int:
        """
        Calculates how many shares to buy based on the $100 balance and position limit.
        """
        if current_price <= 0:
            return 0
        
        # Allocate a safe fraction of the balance (e.g., max $20 per position)
        allocated_capital = min(self.max_position_size, account_balance * 0.5)
        shares = int(allocated_capital / current_price)
        
        return max(shares, 0)

    def validate_trade_risk(self, symbol: str, signal: str, current_price: float, account_balance: float) -> bool:
        """
        Validates whether a trade is safe to execute based on current account balance and risk rules.
        """
        if account_balance <= 5.0:
            logging.warning("Account balance too low for safe trading.")
            return False
            
        if signal not in ["BUY", "SELL"]:
            return False
            
        return True

# Compatibility helper function
def check_risk_limits(symbol: str, signal: str, price: float, balance: float = 100.0) -> bool:
    rm = RiskManager()
    return rm.validate_trade_risk(symbol, signal, price, balance)
