import os
import requests
from event_engine import EventEngine
from strategy_lab import StrategyLab

# Telegram Configuration (Uses environment variables or hardcoded tokens if configured)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

def send_telegram_alert(message: str):
    """
    Sends an instant institutional alert directly to your Telegram chat.
    """
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Telegram token not configured. Skipping live dispatch.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False

def check_and_dispatch_institutional_alerts():
    """
    Evaluates current macro risks and strategy candidates, then dispatches alerts.
    """
    event_eng = EventEngine()
    
    # Check Macro Event Engine Risk
    event_status = event_eng.check_event_risk("PORTFOLIO")
    
    if event_status["event_risk"] == "HIGH":
        alert_msg = (
            f"🚨 *JALWE AI TRADER V4 - INSTITUTIONAL ALERT* 🚨\n\n"
            f"🌐 *Macro Event Risk:* HIGH\n"
            f"⚙️ *Action Required:* `{event_status['action']}`\n"
            f"📝 *Reason:* {event_status['reason']}\n\n"
            f"_Capital protection mode engaged automatically._"
        )
        send_telegram_alert(alert_msg)
        return alert_msg
    else:
        return "Market conditions normal. No macro emergency triggered."

if __name__ == "__main__":
    # Test dispatch execution
    result = check_and_dispatch_institutional_alerts()
    print(result)
