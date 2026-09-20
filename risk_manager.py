import logging

# تفعيل إعدادات السجلات لتسجيل التحذيرات والأخطاء بوضوح
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class RiskEngine:
    def __init__(self, max_daily_loss: float = 10.0, max_drawdown: float = 20.0):
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.circuit_breaker_active = False

    def check_circuit_breaker(self, current_daily_pnl: float, current_drawdown: float) -> bool:
        """
        Triggers the circuit breaker to stop new entries if daily losses or drawdown exceed limits.
        """
        if current_daily_pnl <= -self.max_daily_loss or current_drawdown >= self.max_drawdown:
            self.circuit_breaker_active = True
            logging.critical("CIRCUIT BREAKER TRIGGERED! Halting new trade entries due to risk limits.")
            return True
        
        self.circuit_breaker_active = False
        return False

    def validate_new_trade(self, portfolio_balance: float, trade_risk_amount: float) -> bool:
        """
        Validates whether a new trade complies with strict risk management rules.
        """
        if self.circuit_breaker_active:
            logging.warning("Trade rejected: Circuit breaker is currently active.")
            return False
            
        # Ensure single trade doesn't risk more than 5% of total portfolio
        if trade_risk_amount > (portfolio_balance * 0.05):
            logging.warning("Trade risk exceeds 5% limit of portfolio balance. Rejected.")
            return False
            
        return True

# إنشاء كائن عام (Global Instance) لتكون الدالة التوافقية متصلة بنفس الحالة
_global_risk_engine = RiskEngine()

def check_risk_limits(daily_pnl: float, drawdown: float) -> bool:
    return _global_risk_engine.check_circuit_breaker(daily_pnl, drawdown)
