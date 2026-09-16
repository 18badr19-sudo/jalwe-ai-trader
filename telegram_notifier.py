"""
JALWE AI TRADER V3
Telegram Notifier Module
"""
import requests
import logging

class TelegramNotifier:
    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)
        if not self.enabled:
            logging.warning("TelegramNotifier is disabled because token or chat_id is missing.")

    def send_message(self, message: str):
        if not self.enabled:
            logging.info(f"[Telegram Mock] {message}")
            return
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code != 200:
                logging.error(f"Failed to send Telegram message: {response.text}")
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")