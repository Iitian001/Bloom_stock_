from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.enums import OrderSide, OrderType, OrderProduct, OrderStatus, StrategyFamily, RegimeType
from bloom_stock.packages.domain.types import InstrumentId, Price, Quantity, Timestamp


class OrderIntent(BaseModel):
    """The intent to place an order, representing the internal request."""
    model_config = ConfigDict(from_attributes=True)

    intent_id: UUID = Field(..., description="Unique ID for this intent")
    instrument_id: InstrumentId = Field(..., description="Instrument ID")
    side: OrderSide = Field(..., description="Order side (BUY/SELL)")
    order_type: OrderType = Field(..., description="Order type (MARKET/LIMIT/etc)")
    product: OrderProduct = Field(..., description="Product type (INTRADAY/CNC)")
    quantity: Quantity = Field(..., description="Order quantity")
    price: Optional[Price] = Field(None, description="Limit price if applicable")
    trigger_price: Optional[Price] = Field(None, description="Trigger price for stop loss orders")
    protective_stop_price: Price = Field(..., description="Protective stop loss price")
    target_price: Price = Field(..., description="Target exit price")
    strategy_family: StrategyFamily = Field(..., description="Strategy family originating the intent")
    regime_at_entry: RegimeType = Field(..., description="Market regime when intent was created")
    config_version: str = Field(..., description="Version of the strategy config")
    idempotency_key: UUID = Field(..., description="Key to ensure idempotent order placement")
    created_at: Timestamp = Field(default_factory=datetime.utcnow, description="Time intent was created")
    approval_expiry: Timestamp = Field(..., description="Time when the intent expires if not approved")
    reason_codes: list[str] = Field(default_factory=list, description="Reason codes associated with the intent")


class OrderState(BaseModel):
    """The current state of an order in the system."""
    model_config = ConfigDict(from_attributes=True)

    order_id: UUID = Field(..., description="Internal unique order ID")
    intent_id: UUID = Field(..., description="ID of the originating intent")
    broker_order_id: Optional[str] = Field(None, description="Order ID assigned by the broker")
    status: OrderStatus = Field(..., description="Current status of the order")
    filled_quantity: int = Field(0, description="Quantity filled so far")
    average_fill_price: Optional[Decimal] = Field(None, description="Average price of the filled quantity")
    placed_at: Optional[Timestamp] = Field(None, description="Time the order was placed with the broker")
    filled_at: Optional[Timestamp] = Field(None, description="Time the order was fully filled")
    cancelled_at: Optional[Timestamp] = Field(None, description="Time the order was cancelled")
    rejected_reason: Optional[str] = Field(None, description="Reason if the order was rejected")
    last_updated: Timestamp = Field(default_factory=datetime.utcnow, description="Last update time of this state")


class Fill(BaseModel):
    """A single fill (execution) for an order."""
    model_config = ConfigDict(from_attributes=True)

    fill_id: UUID = Field(..., description="Unique ID for the fill")
    order_id: UUID = Field(..., description="Associated internal order ID")
    price: Price = Field(..., description="Execution price")
    quantity: Quantity = Field(..., description="Executed quantity")
    timestamp: Timestamp = Field(..., description="Time of execution")
    exchange_order_id: Optional[str] = Field(None, description="Order ID from the exchange")
