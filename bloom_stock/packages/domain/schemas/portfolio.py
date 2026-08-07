from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.enums import OrderSide, StrategyFamily
from bloom_stock.packages.domain.types import InstrumentId, Price, Quantity, Timestamp


class Position(BaseModel):
    """An open or closed position in an instrument."""
    model_config = ConfigDict(from_attributes=True)

    position_id: UUID = Field(..., description="Unique ID for the position")
    instrument_id: InstrumentId = Field(..., description="ID of the instrument")
    side: OrderSide = Field(..., description="Long or Short position")
    entry_price: Price = Field(..., description="Average entry price")
    quantity: Quantity = Field(..., description="Current holding quantity")
    current_price: Optional[Price] = Field(None, description="Current market price")
    unrealized_pnl: Decimal = Field(Decimal("0"), description="Unrealized Profit/Loss")
    realized_pnl: Decimal = Field(Decimal("0"), description="Realized Profit/Loss")
    entry_time: Timestamp = Field(..., description="Time of initial entry")
    strategy_family: StrategyFamily = Field(..., description="Strategy that opened the position")
    protective_stop: Price = Field(..., description="Current protective stop level")
    target_price: Price = Field(..., description="Current target price")


class PortfolioSnapshot(BaseModel):
    """A snapshot of the entire portfolio state."""
    model_config = ConfigDict(from_attributes=True)

    timestamp: Timestamp = Field(..., description="Time of snapshot")
    positions: list[Position] = Field(..., description="List of current positions")
    total_equity: Decimal = Field(..., description="Total account equity (cash + unrealized PnL)")
    daily_pnl: Decimal = Field(..., description="PnL for the current day")
    weekly_pnl: Decimal = Field(..., description="PnL for the current week")
    gross_exposure: Decimal = Field(..., description="Total absolute notional exposure")
    net_exposure: Decimal = Field(..., description="Total net notional exposure (Longs - Shorts)")
    sector_exposure: dict[str, Decimal] = Field(..., description="Exposure by sector")
    completed_trades_today: int = Field(..., description="Number of closed trades today")
    consecutive_losses: int = Field(..., description="Current streak of losing trades")
    drawdown_from_peak: Decimal = Field(..., description="Current drawdown fraction from peak equity")
