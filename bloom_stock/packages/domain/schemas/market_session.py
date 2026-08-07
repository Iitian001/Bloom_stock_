from __future__ import annotations

from datetime import time, timedelta
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.enums import TradingSessionPhase


class MarketSessionConfig(BaseModel):
    """Configuration for the trading session timings."""
    model_config = ConfigDict(from_attributes=True)

    timezone: str = Field(..., description="Timezone for market hours (e.g., 'Asia/Kolkata')")
    market_open: time = Field(..., description="Market open time")
    market_close: time = Field(..., description="Market close time")
    no_new_entries_after: time = Field(..., description="Time after which no new positions are taken")
    begin_liquidation_at: time = Field(..., description="Time to start liquidating open intraday positions")
    hard_flat_at: time = Field(..., description="Time when all positions must be closed")
    opening_range_end_default: timedelta = Field(default=timedelta(minutes=15), description="Default duration for the opening range")


class MarketHealth(BaseModel):
    """Real-time health status of the market connection and session."""
    model_config = ConfigDict(from_attributes=True)

    allows_new_entries: bool = Field(..., description="Whether new entries are currently allowed")
    session_phase: TradingSessionPhase = Field(..., description="Current phase of the trading session")
    feed_health: str = Field(..., description="Status of the data feed")
    quote_staleness_seconds: float = Field(..., description="Staleness of quotes in seconds")
    reconnect_count: int = Field(..., description="Number of WebSocket reconnections")
    data_quality_score: float = Field(..., ge=0.0, le=1.0, description="Overall data quality score (0 to 1)")
