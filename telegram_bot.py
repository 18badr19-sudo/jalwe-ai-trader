"""
APEX Telegram compatibility helper.

Credentials are read from environment variables only.
No token/chat ID is stored in source code.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request


logger = logging.getLogger(__name__)


TELEGRAM_BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    or os.getenv("TELEGRAM_TOKEN", "").strip()
)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def send_telegram_alert(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials are not configured.")
        return False

    url = (
        "https://api.telegram.org/bot"
        + TELEGRAM_BOT_TOKEN
        + "/sendMessage"
    )

    payload = urllib.parse.urlencode(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": str(message),
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            return response.status == 200
    except Exception as exc:
        logger.warning("Telegram alert failed: %s", exc)
        return False


def send_telegram_message(message: str) -> bool:
    return send_telegram_alert(message)


def run_jalwe_bot_loop() -> None:
    raise RuntimeError(
        "Legacy Telegram worker is retired. "
        "Use the supported Apex research runtime."
    )


if __name__ == "__main__":
    run_jalwe_bot_loop()
