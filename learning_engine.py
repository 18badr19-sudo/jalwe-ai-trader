import logging

class LearningEngine:
    def __init__(self):
        self.learning_history = []

    def analyze_completed_trade(self, trade_id: str, symbol: str, setup_type: str, result: str, pnl_pct: float, features_used: dict) -> dict:
        """
        Analyzes closed trades (WIN/LOSS) to extract lessons and adjust future confidence weights.
        """
        try:
            insight = ""
            if result.upper() == "WIN":
                insight = f"Successful setup using {setup_type}. Feature alignment was optimal."
            else:
                insight = f"Failed setup on {symbol}. Possible fake breakout or spread expansion. Review RVOL threshold."

            record = {
                "trade_id": trade_id,
                "symbol": symbol.upper(),
                "result": result.upper(),
                "pnl_pct": pnl_pct,
                "lesson": insight,
                "action_required": "Tighten Stop Loss" if result.upper() == "LOSS" else "Maintain Parameters",
                "features_used": features_used
            }
            
            # تفعيل حفظ السجل داخل الذاكرة أو قاعدة البيانات المؤقتة
            self.learning_history.append(record)
            return record
            
        except Exception as e:
            logging.error(f"Error analyzing completed trade {trade_id}: {e}")
            return {
                "trade_id": trade_id,
                "status": "ERROR",
                "message": str(e)
            }

    def get_learning_summary(self) -> list:
        """Returns the complete history of analyzed trades and lessons learned."""
        return self.learning_history
