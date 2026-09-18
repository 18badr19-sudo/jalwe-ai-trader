import os
import requests
import logging

def send_telegram_message(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        logging.warning("Telegram token or chat ID missing in environment variables.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logging.info("Telegram notification sent successfully.")
        else:
            logging.error(f"Failed to send Telegram message: {response.text}")
    except Exception as e:
        logging.error(f"Error sending Telegram notification: {e}")
