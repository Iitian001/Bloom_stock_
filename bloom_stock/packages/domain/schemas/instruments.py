from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.enums import Exchange, Segment
from bloom_stock.packages.domain.types import BloomInstrumentId, ISIN, SymbolToken


class Instrument(BaseModel):
    """Domain model for a tradable instrument."""
    model_config = ConfigDict(from_attributes=True)

    bloom_id: BloomInstrumentId = Field(..., description="Unique internal identifier")
    exchange: Exchange = Field(..., description="Exchange (e.g., NSE, BSE)")
    symbol: str = Field(..., description="Trading symbol")
    isin: ISIN = Field(..., description="ISIN code")
    broker_token: SymbolToken = Field(..., description="Broker specific token")
    segment: Segment = Field(..., description="Market segment")
    tick_size: Decimal = Field(..., description="Minimum price movement")
    lot_size: int = Field(..., description="Minimum trading quantity")
    price_band_upper: Optional[Decimal] = Field(None, description="Upper circuit limit")
    price_band_lower: Optional[Decimal] = Field(None, description="Lower circuit limit")
    sector: Optional[str] = Field(None, description="Sector name")
    industry: Optional[str] = Field(None, description="Industry name")
    is_active: bool = Field(True, description="Whether the instrument is active")
    restrictions: list[str] = Field(default_factory=list, description="Any trading restrictions")
    active_from: Optional[datetime] = Field(None, description="Active from date")
    active_to: Optional[datetime] = Field(None, description="Active to date")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Record last update time")


class InstrumentFilter(BaseModel):
    """Filter criteria for instruments."""
    min_traded_value: Optional[Decimal] = Field(None, description="Minimum traded value")
    min_median_spread: Optional[Decimal] = Field(None, description="Minimum median spread")
    min_trading_days: Optional[int] = Field(None, description="Minimum number of trading days")
    min_price: Optional[Decimal] = Field(None, description="Minimum price")
    min_market_cap: Optional[Decimal] = Field(None, description="Minimum market capitalization")
    excluded_restrictions: list[str] = Field(default_factory=list, description="Restrictions to exclude")
