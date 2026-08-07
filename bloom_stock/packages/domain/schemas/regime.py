from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.enums import RegimeType
from bloom_stock.packages.domain.types import Timestamp


class RegimeClassification(BaseModel):
    """Model output classifying the current market regime."""
    model_config = ConfigDict(from_attributes=True)

    regime: RegimeType = Field(..., description="The predicted market regime")
    probabilities: dict[RegimeType, float] = Field(..., description="Probabilities for each regime type")
    model_version: str = Field(..., description="Version of the regime model used")
    timestamp: Timestamp = Field(..., description="Time of classification")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the classification")


class RegimeFeatures(BaseModel):
    """Features used to determine the market regime."""
    model_config = ConfigDict(from_attributes=True)

    nifty_return: Decimal = Field(..., description="Return of the Nifty index")
    nifty_vwap_distance: Decimal = Field(..., description="Distance of Nifty from its VWAP")
    realized_volatility: Decimal = Field(..., description="Realized volatility measure")
    india_vix: Decimal = Field(..., description="India VIX level")
    advance_decline_ratio: Decimal = Field(..., description="Advance-decline ratio of the market")
    pct_above_vwap: Decimal = Field(..., description="Percentage of stocks trading above their VWAP")
    dispersion: Decimal = Field(..., description="Market dispersion metric")
    intraday_correlation: Decimal = Field(..., description="Intraday correlation metric")
    opening_gap: Decimal = Field(..., description="Market opening gap percentage")
    trend_strength: Decimal = Field(..., description="Trend strength indicator value")
    breadth_acceleration: Decimal = Field(..., description="Acceleration of market breadth")
    feed_health_score: float = Field(..., ge=0.0, le=1.0, description="Health score of the data feed used for calculation")
