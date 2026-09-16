"""
JALWE AI TRADER V3
Automation Scheduler Module

Responsibilities:
- Run automated background tasks at scheduled times.
- Coordinate market scans, trade monitoring, and daily reporting.
"""

from __future__ import annotations

import logging
import time
import schedule

logger = logging.getLogger("JALWE_SCHEDULER")


def job_market_scan() -> None:
    """
    Task to execute automated market scanning for opportunities.
    """
    logger.info("[SCHEDULER] Running scheduled market scan...")
    # Trigger market scanner functions here (e.g., market_scanner)


def job_trade_monitoring() -> None:
    """
    Task to check active trades and enforce risk management rules.
    """
    logger.info("[SCHEDULER] Running scheduled trade monitor check...")
    # Trigger trade monitoring and stop-loss/take-profit checks here (e.g., trade_monitor)


def job_daily_report() -> None:
    """
    Task to generate and send daily performance summary via Telegram.
    """
    logger.info("[SCHEDULER] Generating daily performance summary...")
    # Trigger daily report delivery via Telegram here (e.g., telegram_bot)


def start_scheduler() -> None:
    """
    Starts the continuous background scheduling loop.
    """
    logger.info("JALWE Scheduler initialized and running in background...")

    # Configure execution intervals and times (Adjust as needed)
    schedule.every(10).minutes.do(job_market_scan)
    schedule.every(2).minutes.do(job_trade_monitoring)
    schedule.every().day.at("16:30").do(job_daily_report)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # Test run
    try:
        logger.info("Starting scheduler test loop. Press Ctrl+C to exit.")
        # Uncomment below for immediate test execution
        # job_market_scan()
        start_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")