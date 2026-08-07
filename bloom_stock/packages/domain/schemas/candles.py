from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.enums import DataQuality
from bloom_stock.packages.domain.types import InstrumentId, Price, Volume, Timestamp


class CandleInterval(str, Enum):
    """Time interval for a candle."""
    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"


class Candle(BaseModel):
    """Domain model for a price candle (OHLCV)."""
    model_config = ConfigDict(from_attributes=True)

    instrument_id: InstrumentId = Field(..., description="ID of the instrument")
    interval: str = Field(..., description="Candle interval (e.g., '1m')")
    start_timestamp: Timestamp = Field(..., description="Candle start time")
    end_timestamp: Timestamp = Field(..., description="Candle end time")
    open: Price = Field(..., description="Open price")
    high: Price = Field(..., description="High price")
    low: Price = Field(..., description="Low price")
    close: Price = Field(..., description="Close price")
    volume: Volume = Field(..., description="Traded volume")
    trade_count: Optional[int] = Field(None, description="Number of trades")
    source: str = Field(..., description="Data source")
    first_event_sequence: Optional[int] = Field(None, description="Sequence number of the first tick")
    last_event_sequence: Optional[int] = Field(None, description="Sequence number of the last tick")
    is_complete: bool = Field(False, description="Whether the candle is closed")
    quality_status: DataQuality = Field(..., description="Data quality status")
    created_at: Timestamp = Field(default_factory=datetime.utcnow, description="Record creation time")
    corrected_at: Optional[Timestamp] = Field(None, description="When the candle was corrected, if applicable")


class Tick(BaseModel):
    """Domain model for a market tick."""
    model_config = ConfigDict(from_attributes=True)

    instrument_id: InstrumentId = Field(..., description="ID of the instrument")
    ltp: Price = Field(..., description="Last traded price")
    ltq: Volume = Field(..., description="Last traded quantity")
    volume: Volume = Field(..., description="Cumulative volume")
    timestamp: Timestamp = Field(..., description="Local processing time")
    sequence_number: int = Field(..., description="Sequence number of the tick")
    exchange_timestamp: Timestamp = Field(..., description="Exchange provided timestamp")
