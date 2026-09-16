"""
JALWE AI TRADER V3
Market Scanner Engine
"""
from dataclasses import dataclass, field
from typing import List, Optional
import logging

from config import (
    MIN_STOCK_PRICE,
    MAX_STOCK_PRICE,
    TIMEFRAME,
    CANDLE_COUNT,
    ATR_PERIOD,
    MIN_RVOL,
    RVOL_THRESHOLD,
    HIGH_RVOL_THRESHOLD,
    RVOL_LOOKBACK_PERIOD,
    VOLUME_ACCELERATION_MIN,
    VOLUME_ACCELERATION_THRESHOLD,
    VOLUME_SPEED_WINDOW,
    LIQUIDITY_SCORE_MIN,
    MIN_VOLUME_THRESHOLD,
    MIN_DAILY_DOLLAR_VOLUME,
    MAX_SPREAD_PERCENT,
    VWAP_ENABLED,
    RSI_PERIOD,
    EMA_FAST,
    EMA_SLOW,
    SMA_200,
)

logger = logging.getLogger(__name__)


@dataclass
class TechnicalData:
    symbol: str
    price: float
    volume: int
    rvol: float
    atr: float
    spread_percent: float
    volume_acceleration: float
    liquidity_score: float
    vwap: Optional[float] = None
    rsi: Optional[float] = None


@dataclass
class MarketCandidate:
    symbol: str
    direction: str
    technical: TechnicalData


# Alias to support imports looking for OpportunityCandidate
OpportunityCandidate = MarketCandidate


class MarketDataProvider:
    def get_candidates(self) -> List[TechnicalData]:
        raise NotImplementedError


class DummyDataProvider(MarketDataProvider):
    """
    Simulated Market Data Provider for Paper Trading & Dry Runs.
    """
    def get_candidates(self) -> List[TechnicalData]:
        return [
            TechnicalData(
                symbol="SOUN",
                price=5.50,
                volume=1500000,
                rvol=2.8,
                atr=0.35,
                spread_percent=0.1,
                volume_acceleration=1.5,
                liquidity_score=85.0,
                vwap=5.45,
                rsi=58.0
            ),
            TechnicalData(
                symbol="BBAI",
                price=3.20,
                volume=2200000,
                rvol=3.2,
                atr=0.25,
                spread_percent=0.15,
                volume_acceleration=1.8,
                liquidity_score=78.0,
                vwap=3.18,
                rsi=62.0
            ),
        ]


class MarketScanner:
    def __init__(self, provider: Optional[MarketDataProvider] = None):
        self.provider = provider or DummyDataProvider()

    def scan_market(self) -> List[MarketCandidate]:
        raw_candidates = self.provider.get_candidates()
        approved = []

        for candidate in raw_candidates:
            rsi_valid = candidate.rsi is None or (40.0 <= candidate.rsi <= 70.0)
            
            if (
                MIN_STOCK_PRICE <= candidate.price <= MAX_STOCK_PRICE
                and candidate.rvol >= MIN_RVOL
                and candidate.spread_percent <= MAX_SPREAD_PERCENT
                and rsi_valid
            ):
                approved.append(
                    MarketCandidate(
                        symbol=candidate.symbol,
                        direction="CALL",
                        technical=candidate,
                    )
                )

        logger.info(f"Market Scanner filtered {len(approved)} valid candidates with technical criteria.")
        return approved