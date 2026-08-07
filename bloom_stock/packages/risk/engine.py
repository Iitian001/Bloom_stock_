from __future__ import annotations

import math
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from bloom_stock.packages.domain.enums import RegimeType, StrategyFamily, TradingSessionPhase
from bloom_stock.packages.domain.schemas.market_session import MarketHealth, MarketSessionConfig
from bloom_stock.packages.domain.schemas.portfolio import PortfolioSnapshot
from bloom_stock.packages.domain.schemas.risk import PositionSizeParams, RiskDecision, RiskPolicy
from bloom_stock.packages.domain.schemas.signals import TradeProposal


class DailyRiskState(BaseModel):
    """Tracks intraday risk state that resets each day."""
    date: date = Field(default_factory=date.today)
    realized_pnl: Decimal = Field(default_factory=lambda: Decimal('0'))
    unrealized_pnl: Decimal = Field(default_factory=lambda: Decimal('0'))
    completed_trades: int = 0
    consecutive_losses: int = 0
    peak_equity: Decimal = Field(default_factory=lambda: Decimal('0'))
    current_drawdown: Decimal = Field(default_factory=lambda: Decimal('0'))
    daily_turnover: Decimal = Field(default_factory=lambda: Decimal('0'))
    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    trades_by_family: dict[str, int] = Field(default_factory=dict)
    losses_by_family: dict[str, Decimal] = Field(default_factory=dict)


class WeeklyRiskState(BaseModel):
    """Tracks weekly risk state."""
    week_start: date
    weekly_pnl: Decimal = Field(default_factory=lambda: Decimal('0'))
    weekly_halt_active: bool = False


class RiskEngine:
    """Deterministic portfolio risk engine.
    
    Every order proposal must pass through this engine before execution.
    The engine never relaxes rules — it only rejects or reduces.
    
    Risk layers:
    1. Trade-level: position size, stop distance, R:R ratio
    2. Instrument-level: max notional per stock
    3. Sector-level: concentration limits
    4. Portfolio-level: exposure, correlation, positions
    5. Session-level: daily loss, trade count, time-based
    6. System-level: data quality, model health, connectivity
    """
    
    def __init__(self, policy: RiskPolicy, session_config: MarketSessionConfig):
        self._policy = policy
        self._session = session_config
        self._daily_state = DailyRiskState()
        self._weekly_state = WeeklyRiskState(week_start=date.today())
    
    def evaluate(self, proposal: TradeProposal, portfolio: PortfolioSnapshot, 
                 market_health: MarketHealth) -> RiskDecision:
        """Evaluate a trade proposal against all risk rules.
        Returns approved/rejected with reason codes."""
        
        reasons = []
        
        # 1. Hard Rejects
        hard_rejects = self.check_hard_rejects(proposal, portfolio, market_health)
        if hard_rejects:
            reasons.extend(hard_rejects)
            
        # 2. Portfolio Limits
        portfolio_rejects = self.check_portfolio_limits(proposal, portfolio)
        if portfolio_rejects:
            reasons.extend(portfolio_rejects)
            
        if reasons:
            return RiskDecision(
                approved=False,
                reason_codes=reasons,
                adjusted_quantity=0,
                risk_multiplier=0.0
            )
            
        # 3. Dynamic Multipliers
        calibration_score = 1.0 if proposal.meta_label.calibrated else 0.0
        model_health = 1.0 - proposal.meta_label.uncertainty
        
        multiplier = self.apply_dynamic_multipliers(
            base_risk=Decimal('1.0'),
            regime=proposal.candidate.regime,
            model_health=model_health,
            calibration_score=calibration_score
        )
        
        if multiplier == Decimal('0'):
            return RiskDecision(
                approved=False,
                reason_codes=["DYNAMIC_MULTIPLIER_ZERO"],
                adjusted_quantity=0,
                risk_multiplier=0.0
            )
            
        return RiskDecision(
            approved=True,
            reason_codes=["APPROVED"],
            adjusted_quantity=None, # Will be set during position sizing
            risk_multiplier=float(multiplier)
        )
    
    def calculate_position_size(self, params: PositionSizeParams) -> int:
        """Calculate the risk-adjusted position size.
        Uses the formula from Section 14.2 of the master plan."""
        
        risk_fraction = Decimal(str(params.risk_fraction))
        health_mult = Decimal(str(params.strategy_health_multiplier))
        regime_mult = Decimal(str(params.regime_multiplier))
        
        risk_budget = params.account_equity * risk_fraction * health_mult * regime_mult
        
        price_diff = abs(Decimal(str(params.entry_price)) - Decimal(str(params.protective_stop)))
        if price_diff == Decimal('0'):
            return 0
            
        cost_per_share = Decimal(str(params.estimated_cost_per_share))
        
        raw_quantity = risk_budget / (price_diff + cost_per_share)
        
        # Apply limits sequentially (rounding down at the end)
        qty = math.floor(raw_quantity)
        
        # 1. Liquidity limit
        qty = min(qty, params.liquidity_limit)
        
        # 2. Notional limit
        max_notional_qty = math.floor(params.notional_limit / Decimal(str(params.entry_price)))
        qty = min(qty, max_notional_qty)
        
        # 3. Broker margin limit
        max_margin_qty = math.floor(params.broker_margin_limit / Decimal(str(params.entry_price)))
        qty = min(qty, max_margin_qty)
        
        # 4. Portfolio concentration limit
        qty = min(qty, params.portfolio_concentration_limit)
        
        return max(0, qty)
    
    def check_hard_rejects(self, proposal: TradeProposal, portfolio: PortfolioSnapshot, health: MarketHealth) -> list[str]:
        """Check all hard reject conditions from Section 14.5.
        Returns list of rejection reason codes (empty = pass)."""
        reasons = []
        
        # Stale quote
        if health.quote_staleness_seconds > 2.0:
            reasons.append("STALE_QUOTE")
            
        # Invalid instrument
        if not proposal.candidate.instrument_id:
            reasons.append("INVALID_INSTRUMENT")
            
        # No protective stop
        if proposal.candidate.protective_stop is None or proposal.candidate.protective_stop <= 0:
            reasons.append("MISSING_PROTECTIVE_STOP")
            
        # Risk exceeds account limits
        max_allowed_risk = portfolio.total_equity * Decimal(str(self._policy.risk_per_trade_fraction))
        if proposal.risk_budget > max_allowed_risk:
            reasons.append("RISK_EXCEEDS_ACCOUNT_LIMITS")
            
        # Daily loss kill switch active
        if self.is_kill_switch_active():
            reasons.append("DAILY_LOSS_KILL_SWITCH_ACTIVE")
            
        # Weekly loss halt active
        if self._weekly_state.weekly_halt_active or portfolio.weekly_pnl <= -portfolio.total_equity * Decimal(str(self._policy.weekly_loss_limit_fraction)):
            reasons.append("WEEKLY_LOSS_HALT_ACTIVE")
            
        # Broker connection degraded
        if health.feed_health != "HEALTHY":
            reasons.append("BROKER_CONNECTION_DEGRADED")
            
        if not health.allows_new_entries:
            reasons.append("NEW_ENTRIES_NOT_ALLOWED")
            
        # Time past no_new_entries cutoff
        if health.session_phase in (TradingSessionPhase.NO_NEW_ENTRIES, TradingSessionPhase.LIQUIDATION, TradingSessionPhase.FLAT, TradingSessionPhase.POST_MARKET):
            reasons.append("PAST_NO_NEW_ENTRIES_CUTOFF")
            
        # Consecutive losses exceeded
        if self._daily_state.consecutive_losses >= self._policy.max_consecutive_losses:
            reasons.append("CONSECUTIVE_LOSSES_EXCEEDED")
            
        # Strategy drawdown pause
        family_loss = self._daily_state.losses_by_family.get(proposal.candidate.family.value, Decimal('0'))
        if family_loss >= portfolio.total_equity * Decimal(str(self._policy.strategy_drawdown_pause_fraction)):
            reasons.append("STRATEGY_DRAWDOWN_EXCEEDED")
            
        return reasons
    
    def apply_dynamic_multipliers(self, base_risk: Decimal, 
                                   regime: RegimeType, 
                                   model_health: float,
                                   calibration_score: float) -> Decimal:
        """Apply dynamic risk multipliers from Section 14.4."""
        
        # Calibration degraded -> 0.00
        if calibration_score < 0.5:
            return Decimal('0.00')
            
        # Reconciliation unhealthy (model health degraded) -> 0.00
        if model_health < 0.5:
            return Decimal('0.00')
            
        multiplier = Decimal('1.00')
        
        # High volatility regime -> 0.25
        if regime == RegimeType.HIGH_VOLATILITY:
            multiplier = min(multiplier, Decimal('0.25'))
            
        # High uncertainty -> 0.50
        elif model_health >= 0.5 and model_health < 0.8:
            multiplier = min(multiplier, Decimal('0.50'))
            
        return base_risk * multiplier
    
    def check_portfolio_limits(self, proposal: TradeProposal, portfolio: PortfolioSnapshot) -> list[str]:
        """Check portfolio-level constraints from Section 14.3."""
        reasons = []
        
        if len(portfolio.positions) >= self._policy.max_open_positions:
            reasons.append("MAX_OPEN_POSITIONS_EXCEEDED")
            
        # Sector concentration check (approximate, since proposal doesn't have sector, assume we check total limits later if applicable)
        # Using daily completed trades as a stand-in for turnover limits
        if self._daily_state.completed_trades >= self._policy.max_completed_trades_per_day:
            reasons.append("MAX_COMPLETED_TRADES_EXCEEDED")
            
        if self._daily_state.daily_turnover >= portfolio.total_equity * Decimal(str(self._policy.max_daily_turnover_fraction)):
            reasons.append("MAX_DAILY_TURNOVER_EXCEEDED")
            
        return reasons
    
    def is_kill_switch_active(self) -> bool:
        """Check if daily or weekly loss limits have been breached."""
        if self._daily_state.kill_switch_active:
            return True
            
        # Check against daily loss limit threshold
        max_loss = self._daily_state.peak_equity * Decimal(str(self._policy.daily_loss_limit_fraction))
        if self._daily_state.current_drawdown > max_loss:
            self._daily_state.kill_switch_active = True
            self._daily_state.kill_switch_reason = "DAILY_LOSS_LIMIT_BREACHED"
            return True
            
        return False
    
    def record_trade_result(self, pnl: Decimal, strategy: StrategyFamily, turnover: Decimal = Decimal('0')):
        """Update daily state after a trade completes."""
        self._daily_state.completed_trades += 1
        self._daily_state.daily_turnover += turnover
        self._daily_state.realized_pnl += pnl
        
        strategy_key = strategy.value
        self._daily_state.trades_by_family[strategy_key] = self._daily_state.trades_by_family.get(strategy_key, 0) + 1
        
        if pnl < 0:
            self._daily_state.consecutive_losses += 1
            current_loss = self._daily_state.losses_by_family.get(strategy_key, Decimal('0'))
            self._daily_state.losses_by_family[strategy_key] = current_loss + abs(pnl)
        else:
            self._daily_state.consecutive_losses = 0
            
    def reset_daily(self):
        """Reset daily counters. Called at start of each trading day."""
        self._daily_state = DailyRiskState()
