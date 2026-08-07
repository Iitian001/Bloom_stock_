from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

from bloom_stock.packages.domain.schemas.market_session import MarketSessionConfig
from bloom_stock.packages.domain.schemas.risk import RiskPolicy


class ProviderCapability(BaseModel):
    """Capabilities and rate limits of a broker or data provider."""
    model_config = ConfigDict(from_attributes=True)

    provider: str = Field(..., description="Name of the provider")
    historical_rps: int = Field(..., description="Historical data requests per second limit")
    historical_rpm: int = Field(..., description="Historical data requests per minute limit")
    historical_rph: int = Field(..., description="Historical data requests per hour limit")
    ws_max_connections: int = Field(..., description="Max allowed WebSocket connections")
    ws_max_tokens_per_connection: int = Field(..., description="Max instrument tokens per WebSocket connection")
    order_internal_rps: int = Field(..., description="Internal orders placed per second limit")
    auth_daily_rotation: bool = Field(..., description="Whether auth tokens must be rotated daily")
    static_ip_required: bool = Field(..., description="Whether a static IP is required for API access")


class BloomConfig(BaseSettings):
    """Root configuration for the Bloom_Stock trading engine."""
    model_config = SettingsConfigDict(
        env_prefix="BLOOM_",
        env_nested_delimiter="__",
        case_sensitive=False
    )

    environment: str = Field(..., description="Environment running (paper, shadow, live)")
    session: MarketSessionConfig = Field(..., description="Market session timings")
    risk: RiskPolicy = Field(..., description="Risk management policy limits")
    provider: ProviderCapability = Field(..., description="Provider capability configurations")
    models: Dict[str, str] = Field(..., description="Dictionary of active model versions (regime, ranker, meta_labeler)")
    execution_live_enabled: bool = Field(False, description="Flag to enable live execution")
    human_approval_required: bool = Field(True, description="Flag requiring human approval for orders")
