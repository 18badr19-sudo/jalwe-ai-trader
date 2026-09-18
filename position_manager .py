import logging

class PositionManager:
    def __init__(self):
        pass

    def evaluate_open_position(self, position_data: dict) -> str:
        """
        Monitors open positions for dynamic exits, stop loss tightening, 
        or profit targets based on market movement and MFE/MAE.
        """
        unrealized_pnl_pct = position_data.get("unrealized_pnl_pct", 0.0)
        regime = position_data.get("market_regime", "NORMAL")

        # Dynamic exit rules
        if unrealized_pnl_pct <= -0.03:
            return "EXIT_STOP_LOSS"
        elif unrealized_pnl_pct >= 0.06:
            return "EXIT_TAKE_PROFIT"
        elif regime == "HIGH_VOLATILITY":
            return "EXIT_VOLATILITY_SPIKE"

        return "HOLD"

# Compatibility helper
def manage_position(position_data: dict) -> str:
    manager = PositionManager()
    return manager.evaluate_open_position(position_data)
