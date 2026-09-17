import time
import requests
from event_engine import EventEngine

# Direct configuration using your active verified Telegram credentials
TELEGRAM_BOT_TOKEN = "7917757905:AAEUw7U_X0w8gT91Z3f8xQ9..."
TELEGRAM_CHAT_ID = "6124128003"

def send_telegram_alert(message: str):
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

def run_jalwe_bot_loop():
    print("Jalwe AI Trader V4 Telegram Worker Active...")
    
    # Send an immediate startup confirmation message to your active chat
    startup_msg = (
        f"🟢 *JALWE AI TRADER V4 - ONLINE*\n\n"
        f"🏛️ *System Status:* Institutional Engine Connected\n"
        f"📱 *Telegram Dispatcher:* Active and monitoring macro risks."
    )
    send_telegram_alert(startup_msg)
    
    event_eng = EventEngine()
    
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
            print(f"Error in bot loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_jalwe_bot_loop()
