from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.enums import SignalDirection, StrategyFamily
from bloom_stock.packages.domain.schemas.regime import RegimeType
from bloom_stock.packages.domain.types import InstrumentId, Price, Timestamp


class StrategyCandidate(BaseModel):
    """A generated signal from a strategy."""
    model_config = ConfigDict(from_attributes=True)

    instrument_id: InstrumentId = Field(..., description="Instrument ID for the candidate")
    family: StrategyFamily = Field(..., description="Strategy family that generated the signal")
    direction: SignalDirection = Field(..., description="Direction of the signal (LONG/SHORT/NO_TRADE)")
    entry_price: Price = Field(..., description="Proposed entry price")
    protective_stop: Price = Field(..., description="Proposed protective stop loss price")
    initial_target: Price = Field(..., description="Initial target price")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Strategy confidence score")
    features: dict[str, Any] = Field(..., description="Features used by the strategy")
    reason_codes: list[str] = Field(default_factory=list, description="Reason codes for the signal")
    timestamp: Timestamp = Field(..., description="Time the signal was generated")
    regime: RegimeType = Field(..., description="Market regime at the time of signal generation")
    config_version: str = Field(..., description="Version of the strategy configuration")


class RankedCandidate(StrategyCandidate):
    """A strategy candidate after cross-sectional ranking."""
    rank_score: float = Field(..., description="Score assigned by the ranker")
    rank_percentile: float = Field(..., ge=0.0, le=100.0, description="Percentile rank among candidates")
    horizon_minutes: int = Field(..., description="Expected holding horizon in minutes")
    ranker_version: str = Field(..., description="Version of the ranker model used")


class MetaLabelResult(BaseModel):
    """Result of the meta-labeling model evaluating a candidate."""
    model_config = ConfigDict(from_attributes=True)

    take_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of taking the trade")
    calibrated: bool = Field(..., description="Whether the probability is calibrated")
    uncertainty: float = Field(..., description="Uncertainty metric of the prediction")
    model_version: str = Field(..., description="Version of the meta-labeling model")


class TradeProposal(BaseModel):
    """A final trade proposal combining ranking and meta-labeling."""
    model_config = ConfigDict(from_attributes=True)

    candidate: RankedCandidate = Field(..., description="The ranked candidate")
    meta_label: MetaLabelResult = Field(..., description="The meta-labeling result")
    estimated_cost: Decimal = Field(..., description="Estimated cost of the trade (slippage, fees)")
    expected_edge: Decimal = Field(..., description="Expected edge of the trade")
    risk_budget: Decimal = Field(..., description="Risk budget allocated to this trade")
