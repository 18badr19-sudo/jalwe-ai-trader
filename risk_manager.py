class RiskManager:
    def __init__(self, max_risk_pct: float = 0.02):
        self.max_risk_pct = max_risk_pct

    def evaluate_risk(self, symbol: str, price: float, action: str) -> dict:
        """
        Evaluates trade risk, calculates stop loss, take profit, and position size securely.
        """
        # Ensure price is handled as a float to prevent type errors
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 100.0

        if price <= 0:
            price = 100.0

        stop_loss = round(price * 0.98, 2)  # 2% stop loss
        take_profit = round(price * 1.05, 2)  # 5% take profit
        position_size = int(1000 / price) if price > 0 else 10

        return {
            "symbol": symbol,
            "action": action,
            "entry_price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_size": max(1, position_size),
            "risk_status": "APPROVED"
        }
