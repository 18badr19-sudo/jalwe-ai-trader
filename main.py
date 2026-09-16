"""
JALWE AI TRADER V3
Main Orchestrator
Responsibilities:
- Initialize all components (DB, Scanner, News, AI, Risk, Execution).
- Run the continuous trading loop.
- Gracefully handle shutdowns.
"""

import logging
import time
from datetime import datetime, timezone

from config import (
    MARKET_DATA_PROVIDER,
    SCAN_INTERVAL_SECONDS,
    LOG_LEVEL
)
from database import Database
from market_scanner import MarketScanner, DummyDataProvider
from news_engine import NewsEngine
from ai_engine import AIEngine
from risk_manager import RiskManager
from execution_engine import ExecutionEngine

# ============================================================
# LOGGING SETUP
# ============================================================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("JALWE_MAIN")


def main():
    logger.info("Initializing JALWE AI TRADER V3...")

    # 1. Initialize Database
    db = Database()
    
    # 2. Initialize Data Providers (Replace Dummy with Alpaca/Polygon when ready)
    if MARKET_DATA_PROVIDER == "DUMMY":
        data_provider = DummyDataProvider()
    else:
        # Fallback to dummy for safety until API keys are set
        logger.warning(f"Provider {MARKET_DATA_PROVIDER} not wired yet. Using DUMMY.")
        data_provider = DummyDataProvider()

    # 3. Initialize Engines
    news_engine = NewsEngine()
    scanner = MarketScanner(provider=data_provider)
    ai_engine = AIEngine(news_engine=news_engine, database=db)
    risk_manager = RiskManager(news_engine=news_engine)
    execution_engine = ExecutionEngine(database=db)

    logger.info("All components initialized successfully. Starting trading loop.")
    logger.info(f"Scan interval set to {SCAN_INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.")

    try:
        while True:
            logger.info("--- Starting New Market Scan Cycle ---")
            
            # Step 1: Scan Market for Opportunities
            candidates = scanner.scan_market()
            logger.info(f"Scanner found {len(candidates)} potential candidates.")

            # Step 2 & 3: AI Engine Evaluates Candidates (Technical + News)
            for candidate in candidates:
                # Save raw opportunity to database
                db.save_opportunity(candidate)
                
                decision = ai_engine.evaluate_candidate(candidate)
                
                if not decision.is_approved:
                    logger.debug(f"AI Rejected {candidate.symbol}: {decision.rejection_reasons}")
                    continue
                
                logger.info(f"AI APPROVED {candidate.symbol} | Confidence: {decision.confidence_score}%")

                # Mock Account Variables for Risk Management (In production, fetch from Broker API)
                account_equity = 10000.00
                current_open_positions = 0
                daily_pnl = 0.0
                atr_value = candidate.technical.atr

                # Step 4: Risk Manager Assesses the Approved AI Decision
                risk_assessment = risk_manager.evaluate_trade(
                    decision=decision,
                    account_equity=account_equity,
                    current_open_positions=current_open_positions,
                    daily_realized_pnl=daily_pnl,
                    atr=atr_value
                )

                if not risk_assessment.approved:
                    logger.warning(f"Risk Manager REJECTED {candidate.symbol}: {risk_assessment.rejection_reasons}")
                    continue

                logger.info(f"Risk Manager APPROVED {candidate.symbol}. Proceeding to execution.")

                # Step 5: Execution Engine Places the Trade
                execution_engine.execute_trade(risk_assessment)

            logger.info("--- Scan Cycle Complete ---")
            time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down gracefully...")
    except Exception as e:
        logger.exception(f"Critical error in main loop: {e}")
    finally:
        logger.info("JALWE AI TRADER V3 Offline.")


if __name__ == "__main__":
    main()