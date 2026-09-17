class LearningEngine:
    def __init__(self):
        self.learning_history = []

    def analyze_completed_trade(self, trade_id: str, symbol: str, setup_type: str, result: str, pnl_pct: float, features_used: dict) -> dict:
        """
        Analyzes closed trades (WIN/LOSS) to extract lessons and adjust future confidence weights.
        """
        insight = ""
        if result == "WIN":
            insight = f"Successful setup using {setup_type}. Feature alignment was optimal."
        else:
            insight = f"Failed setup on {symbol}. Possible fake breakout or spread expansion. Review RVOL threshold."

        record = {
            "trade_id": trade_id,
            "symbol": symbol,
            "result": result,
            "pnl_pct": pnl_pct,
            "lesson": insight,
            "action_required": "Tighten Stop Loss" if result == "LOSS" else "Maintain Parameters"
        }
        
        self.learning_history.append(record)
        return record
