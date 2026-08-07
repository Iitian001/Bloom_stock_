from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from loguru import logger

from bloom_stock.packages.domain.enums import StrategyFamily, SignalDirection, RegimeType
from bloom_stock.packages.domain.schemas.signals import StrategyCandidate
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.schemas.regime import RegimeClassification
from bloom_stock.packages.strategy_families.base import StrategyFamilyBase


class ORBContinuationConfig(BaseModel):
    """Configuration for Opening Range Breakout strategy."""
    opening_range_minutes: int = 15  # Test 5, 10, 15
    noise_buffer_pct: float = 0.0005  # 0.05% minimum
    noise_buffer_atr_fraction: float = 0.10  # 0.10 x ATR_14
    min_volume_zscore: float = 1.5  # Breakout volume z-score threshold
    max_range_atr_percentile: float = 0.90  # Skip if range too wide
    max_gap_atr: float = 3.0  # Skip if gap > 3 ATR
    partial_exit_r: float = 1.0  # Book 50% at 1R
    trail_method: str = 'STRUCTURE'  # STRUCTURE or VOLATILITY
    time_stop_minutes: int = 60  # Max holding time
    max_entries_per_day: int = 2  # Per instrument
    entry_cutoff_minutes_from_open: int = 120  # No entries after 2hr from open
    stop_candidates: list[str] = ['OPPOSITE_RANGE', 'CANDLE_STRUCTURE', 'ATR']
    stop_atr_min: float = 0.8
    stop_atr_max: float = 1.2
    config_version: str = "1.0.0"


class ORBInstrumentState(BaseModel):
    """Tracks per-instrument state for ORB."""
    range_high: float = -float('inf')
    range_low: float = float('inf')
    range_complete: bool = False
    entries_today: int = 0
    triggered_direction: Optional[SignalDirection] = None
    skip_reasons: list[str] = []
    session_start_time: Optional[datetime] = None


class ORBContinuation(StrategyFamilyBase):
    """Family A — Opening Range Continuation Strategy.
    
    Uses the opening range (first N minutes) to identify breakout
    opportunities confirmed by volume, VWAP alignment, and relative strength.
    """
    
    def __init__(self, config: Optional[ORBContinuationConfig] = None):
        self._config = config or ORBContinuationConfig()
        self._instrument_state: dict[str, ORBInstrumentState] = {}
        
    @property
    def family(self) -> StrategyFamily:
        return StrategyFamily.ORB_CONTINUATION
        
    @property
    def compatible_regimes(self) -> list[str]:
        return [RegimeType.TREND_UP.value, RegimeType.TREND_DOWN.value]
        
    def is_compatible(self, regime: RegimeClassification) -> bool:
        return regime.regime.value in self.compatible_regimes
        
    def reset_session(self, instrument_id: str):
        self._instrument_state[instrument_id] = ORBInstrumentState()
        
    def get_skip_reasons(self, instrument_id: str) -> list[str]:
        state = self._instrument_state.get(instrument_id)
        if state:
            return state.skip_reasons
        return []
        
    def _get_state(self, instrument_id: str) -> ORBInstrumentState:
        if instrument_id not in self._instrument_state:
            self._instrument_state[instrument_id] = ORBInstrumentState()
        return self._instrument_state[instrument_id]
        
    def on_candle(
        self,
        instrument_id: str,
        candle: Candle,
        features: dict,
        regime: RegimeClassification,
    ) -> Optional[StrategyCandidate]:
        state = self._get_state(instrument_id)
        
        if state.session_start_time is None:
            state.session_start_time = candle.start_timestamp
            
        minutes_from_open = (candle.end_timestamp - state.session_start_time).total_seconds() / 60.0
        
        # 1. Update ORB range if not complete
        if not state.range_complete:
            state.range_high = max(state.range_high, float(candle.high))
            state.range_low = min(state.range_low, float(candle.low))
            
            if minutes_from_open >= self._config.opening_range_minutes:
                state.range_complete = True
            return None
            
        # If skip reasons exist, do not trade
        if state.skip_reasons:
            return None
            
        # Check max entries
        if state.entries_today >= self._config.max_entries_per_day:
            return None
            
        # Check time cutoff
        if minutes_from_open > self._config.entry_cutoff_minutes_from_open:
            return None
            
        atr = features.get('atr', 0.0)
        if atr <= 0:
            return None
            
        # Calculate noise buffer
        price = float(candle.close)
        buffer_pct_val = price * self._config.noise_buffer_pct
        buffer_atr_val = atr * self._config.noise_buffer_atr_fraction
        noise_buffer = max(buffer_pct_val, buffer_atr_val)
        
        vwap = features.get('vwap')
        volume_zscore = features.get('volume_zscore', 0.0)
        
        # Determine Breakout Direction
        is_long = price > state.range_high + noise_buffer
        is_short = price < state.range_low - noise_buffer
        
        if not is_long and not is_short:
            return None
            
        direction = SignalDirection.LONG if is_long else SignalDirection.SHORT
        
        # Validate Regime
        if direction == SignalDirection.LONG and regime.regime != RegimeType.TREND_UP:
            return None
        if direction == SignalDirection.SHORT and regime.regime != RegimeType.TREND_DOWN:
            return None
            
        # Check VWAP alignment
        if vwap is not None:
            if direction == SignalDirection.LONG and price <= vwap:
                return None
            if direction == SignalDirection.SHORT and price >= vwap:
                return None
                
        # Check Volume Z-Score
        if volume_zscore < self._config.min_volume_zscore:
            return None
            
        # Evaluate stop loss
        range_height = state.range_high - state.range_low
        stop_price = state.range_low if direction == SignalDirection.LONG else state.range_high
        
        stop_distance = abs(price - stop_price)
        min_stop_distance = atr * self._config.stop_atr_min
        max_stop_distance = atr * self._config.stop_atr_max
        
        if stop_distance < min_stop_distance:
            stop_distance = min_stop_distance
        elif stop_distance > max_stop_distance:
            stop_distance = max_stop_distance
            
        stop_price = price - stop_distance if direction == SignalDirection.LONG else price + stop_distance
        
        risk = abs(price - stop_price)
        target_price = price + risk if direction == SignalDirection.LONG else price - risk
        
        # Increment entries
        state.entries_today += 1
        state.triggered_direction = direction
        
        reason_codes = ["ORB_BREAKOUT", "VWAP_ALIGNED", "VOLUME_CONFIRMED", f"ZSCORE_{volume_zscore:.2f}"]
        
        logger.info(f"[{instrument_id}] ORB {direction.value} Candidate generated. Entry: {price}, Stop: {stop_price}")
        
        return StrategyCandidate(
            instrument_id=instrument_id,
            family=self.family,
            direction=direction,
            entry_price=candle.close,
            protective_stop=stop_price,
            initial_target=target_price,
            confidence=0.8,
            features=features,
            reason_codes=reason_codes,
            timestamp=candle.end_timestamp,
            regime=regime.regime,
            config_version=self._config.config_version,
        )
