import os
import requests
from event_engine import EventEngine

# Use your existing active Telegram credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_jalwe_alert():
    event_eng = EventEngine()
    event_status = event_eng.check_event_risk("PORTFOLIO")
    
    if event_status["event_risk"] == "HIGH":
        message = (
            f"🚨 *JALWE AI TRADER V4 - INSTITUTIONAL ALERT* 🚨\n\n"
            f"🌐 *Macro Event Risk:* HIGH\n"
            f"⚙️ *Action Required:* `{event_status['action']}`\n"
            f"📝 *Reason:* {event_status['reason']}\n\n"
            f"_Capital protection mode engaged automatically._"
        )
    else:
        message = (
            f"🟢 *JALWE AI TRADER V4 - STATUS UPDATE*\n\n"
            f"🌐 *Macro Event Risk:* NORMAL\n"
            f"⚙️ *Action:* `{event_status['action']}`"
        )
        
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
        print(f"Error sending alert: {e}")
        return False

if __name__ == "__main__":
    send_jalwe_alert()
