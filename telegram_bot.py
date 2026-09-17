import os
import time
import requests
from event_engine import EventEngine

# Get tokens from environment variables (configured in Railway)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram tokens are missing in environment variables!")
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

def run_alert_loop():
    print("Telegram alert worker started...")
    event_eng = EventEngine()
    
    # Send startup message to confirm it's connected
    send_telegram_alert("🟢 *JALWE AI TRADER V4* - Telegram Alert System Online & Monitoring!")
    
    while True:
        try:
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
            
            # Check every 60 minutes
            time.sleep(3600)
        except Exception as e:
            print(f"Error in alert loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_alert_loop()
