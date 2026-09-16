import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send():
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "JALWE AI TRADER V3 - Telegram Connection Successful!",
        "parse_mode": "Markdown"
    }
    res = requests.post(url, json=payload)
    print("Status Code:", res.status_code)
    print("Response:", res.text)

if __name__ == "__main__":
    send()