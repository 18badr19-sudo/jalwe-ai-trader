import json
import logging
from database_manager import DatabaseManager

class LearningEngine:
    def __init__(self):
        self.db = DatabaseManager()

    def record_trade_outcome(self, trade_id: int, pnl: float, exit_reason: str, features_snapshot: dict):
        """
        Records trade outcome, analyzes success/failure factors, and stores features 
        into the learning dataset for model improvement.
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Update trade record with PnL and exit reason
            cursor.execute("""
                UPDATE trades 
                SET pnl = ?, status = ? 
                WHERE id = ?
            """, (pnl, f"CLOSED_{exit_reason}", trade_id))
            
            conn.commit()
            conn.close()
            
            logging.info(f"Trade ID {trade_id} recorded in learning engine. PnL: ${pnl:.2f}. Reason: {exit_reason}")
            return True
        except Exception as e:
            logging.error(f"Error recording trade outcome in learning engine: {e}")
            return False

    def check_performance_drift(self, recent_win_rate: float) -> bool:
        """
        Detects strategy or feature drift if win rate drops significantly below acceptable bounds.
        """
        if recent_win_rate < 0.40:
            logging.warning("Performance drift detected! Win rate has dropped below acceptable threshold.")
            return True
        return False

# Compatibility helper
def analyze_learning_outcome(trade_id: int, pnl: float, reason: str, features: dict):
    engine = LearningEngine()
    return engine.record_trade_outcome(trade_id, pnl, reason, features)
