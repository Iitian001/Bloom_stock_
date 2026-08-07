from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.types import Fraction, Price


class RiskPolicy(BaseModel):
    """Configuration for global and per-trade risk limits."""
    model_config = ConfigDict(from_attributes=True)

    risk_per_trade_fraction: Fraction = Field(..., description="Fraction of equity risked per trade")
    max_notional_per_stock_fraction: Fraction = Field(..., description="Max fraction of equity exposed to a single stock")
    max_open_positions: int = Field(..., description="Maximum number of open positions allowed")
    max_positions_per_sector: int = Field(..., description="Maximum number of positions per sector")
    max_completed_trades_per_day: int = Field(..., description="Maximum completed trades allowed per day")
    daily_loss_limit_fraction: Fraction = Field(..., description="Fraction of equity for max daily loss")
    weekly_loss_limit_fraction: Fraction = Field(..., description="Fraction of equity for max weekly loss")
    strategy_drawdown_pause_fraction: Fraction = Field(..., description="Drawdown fraction to pause a strategy")
    max_consecutive_losses: int = Field(..., description="Max consecutive losses before pausing")
    max_daily_turnover_fraction: Fraction = Field(..., description="Max daily turnover as fraction of equity")


class RiskDecision(BaseModel):
    """Result of evaluating a trade proposal against risk policies."""
    model_config = ConfigDict(from_attributes=True)

    approved: bool = Field(..., description="Whether the trade is approved by risk checks")
    reason_codes: list[str] = Field(default_factory=list, description="Reasons for approval or rejection")
    adjusted_quantity: Optional[int] = Field(None, description="Quantity adjusted by risk constraints")
    risk_multiplier: float = Field(1.0, description="Multiplier applied to risk based on current conditions")


class PositionSizeParams(BaseModel):
    """Parameters used to calculate the position size for a trade."""
    model_config = ConfigDict(from_attributes=True)

    account_equity: Decimal = Field(..., description="Current account equity")
    risk_fraction: Fraction = Field(..., description="Fraction of equity to risk")
    strategy_health_multiplier: float = Field(..., description="Multiplier based on strategy health")
    regime_multiplier: float = Field(..., description="Multiplier based on market regime")
    entry_price: Price = Field(..., description="Proposed entry price")
    protective_stop: Price = Field(..., description="Protective stop loss price")
    estimated_cost_per_share: Decimal = Field(..., description="Estimated cost per share (slippage, fees)")
    liquidity_limit: int = Field(..., description="Max quantity based on liquidity")
    notional_limit: Decimal = Field(..., description="Max notional value allowed")
    broker_margin_limit: Decimal = Field(..., description="Max margin available from broker")
    portfolio_concentration_limit: int = Field(..., description="Max quantity based on portfolio concentration")
