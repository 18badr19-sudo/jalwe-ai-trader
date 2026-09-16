"""
JALWE AI TRADER V3
Telegram Notification Module

Responsibilities:
- Send real-time alerts for trade entries, exits, profits, and errors directly to Telegram.
"""

from __future__ import annotations

import logging
import requests

logger = logging.getLogger("JALWE_TELEGRAM")


class TelegramNotifier:
    """
    Handles sending messages to a Telegram chat via Bot API.
    """

    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            logger.warning("Telegram Notifier is disabled (Missing token or chat_id). Running in log-only mode.")

    def send_message(self, message: str) -> bool:
        """
        Sends a text message to the configured Telegram chat.
        """
        if not self.enabled:
            logger.info("[TELEGRAM MOCK] %s", message)
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully.")
                return True
            else:
                logger.error("Failed to send Telegram message: %s", response.text)
                return False
        except Exception:
            logger.exception("Error connecting to Telegram API.")
            return False

    def notify_trade_execution(self, symbol: str, direction: str, price: float, qty: float) -> None:
        msg = (
            f"🚀 *JALWE AI TRADER - New Trade Executed*\n\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Action:* `{direction}`\n"
            f"• *Price:* `{price}`\n"
            f"• *Quantity:* `{qty}`"
        )
        self.send_message(msg)

    def notify_trade_closed(self, symbol: str, pnl: float, result_type: str) -> None:
        emoji = "🟢" if result_type == "WIN" else "🔴"
        msg = (
            f"{emoji} *JALWE AI TRADER - Trade Closed*\n\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Result:* `{result_type}`\n"
            f"• *PnL:* `${pnl}`"
        )
        self.send_message(msg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    notifier = TelegramNotifier()
    notifier.send_message("⚡ *JALWE AI TRADER V3* Telegram Module Initialized Successfully!")