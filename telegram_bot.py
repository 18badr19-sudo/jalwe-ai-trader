import time
import requests
import logging

# Direct institutional configuration using verified Telegram credentials
TELEGRAM_BOT_TOKEN = "7917757905:AAEUw7U_X0w8gT91Z3f8xQ9"
TELEGRAM_CHAT_ID = "6124128003"

def send_telegram_alert(message: str) -> bool:
    """Sends a formatted message to the authorized Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            logging.info("Telegram alert sent successfully.")
            return True
        else:
            logging.error(f"Failed to send Telegram alert. Status code: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Exception encountered while sending Telegram alert: {e}")
        return False

# Compatibility alias for external modules
def send_telegram_message(message: str) -> bool:
    return send_telegram_alert(message)

def run_jalwe_bot_loop():
    """Runs the main monitoring loop for JALWE AI Trader V4."""
    logging.info("Jalwe AI Trader V4 Telegram Worker Active...")
    
    # Send an immediate startup confirmation message to your active chat upon execution
    startup_msg = (
        f"🟢 *JALWE AI TRADER V4 - ONLINE*\n\n"
        f"🏛️ *System Status:* Institutional Engine Connected\n"
        f"📱 *Telegram Dispatcher:* Active and monitoring macro risks."
    )
    send_telegram_alert(startup_msg)
    
    # Safe import for EventEngine
    try:
        from event_engine import EventEngine
        event_eng = EventEngine()
    except ImportError:
        logging.warning("event_engine module not found. Macro event checks will be simulated.")
        event_eng = None
    
    while True:
        try:
            if event_eng and hasattr(event_eng, "check_event_risk"):
                event_status = event_eng.check_event_risk("PORTFOLIO")
                
                if event_status.get("event_risk") == "HIGH":
                    alert_msg = (
                        f"🚨 *JALWE AI TRADER V4 - INSTITUTIONAL ALERT* 🚨\n\n"
                        f"🌐 *Macro Event Risk:* HIGH\n"
                        f"⚙️ *Action Required:* `{event_status.get('action', 'REVIEW')}`\n"
                        f"📝 *Reason:* {event_status.get('reason', 'High volatility detected')}\n\n"
                        f"_Capital protection mode engaged automatically._"
                    )
                    send_telegram_alert(alert_msg)
            
            # Check every 60 minutes
            time.sleep(3600)
            
        except Exception as e:
            logging.error(f"Error in JALWE bot loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # Force immediate dispatch on script run
    run_jalwe_bot_loop()
