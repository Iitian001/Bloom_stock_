"""Gap/Event Response Strategy Family.

Per Section 7.4 of the master plan. Replaces simple first-candle-color logic with proper classification.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from loguru import logger

from bloom_stock.packages.domain.enums import SignalDirection, StrategyFamily, RegimeType, GapClass
from bloom_stock.packages.domain.schemas.signals import StrategyCandidate
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.types import InstrumentId, Price
from bloom_stock.packages.indicators.core import IndicatorHub


class GapEventConfig(BaseModel):
    min_gap_pct: float = 1.0  # Minimum gap size in percent
    min_gap_atr: float = 0.5  # Minimum gap in ATR units
    first_candle_window_minutes: int = 5  # First N minutes for classification
    min_relative_volume: float = 2.0  # Volume must be 2x average
    max_gap_atr_no_trade: float = 5.0  # Too large gap = skip
    continuation_target_gap_multiple: float = 2.0  # Target = 2x gap size
    fade_target: str = 'PREVIOUS_CLOSE'  # Gap fill level
    time_stop_minutes: int = 45


class GapEventStrategy:
    """Gap and Event Response Strategy."""
    
    def __init__(self, config: Optional[GapEventConfig] = None):
        self.config = config or GapEventConfig()
        self.family = StrategyFamily.GAP_EVENT
        self.version = "1.0.0"
        
    def classify_gap(self, gap_pct: float, gap_atr: float, first_candle: Candle, avg_volume: float, vwap: float) -> GapClass:
        """Classify the opening gap into one of the GapClass categories."""
        if abs(gap_atr) > self.config.max_gap_atr_no_trade:
            return GapClass.NO_TRADE
            
        if abs(gap_pct) < self.config.min_gap_pct or abs(gap_atr) < self.config.min_gap_atr:
            return GapClass.NO_TRADE
            
        rel_vol = float(first_candle.volume) / avg_volume if avg_volume > 0 else 0
        if rel_vol < self.config.min_relative_volume:
            return GapClass.NO_TRADE
            
        is_green = first_candle.close > first_candle.open
        is_red = first_candle.close < first_candle.open
        above_vwap = float(first_candle.close) > vwap
        below_vwap = float(first_candle.close) < vwap
        
        # gap_pct > 0 means gap up
        if gap_pct > 0:
            if is_green and above_vwap:
                return GapClass.CONTINUATION_LONG
            elif is_red: # Gap up but red close -> fade short
                return GapClass.FADE_SHORT
        elif gap_pct < 0:
            if is_red and below_vwap:
                return GapClass.CONTINUATION_SHORT
            elif is_green: # Gap down but green close -> fade long
                return GapClass.FADE_LONG
                
        return GapClass.NO_TRADE
        
    def evaluate(self, instrument_id: InstrumentId, candles: List[Candle], indicator_hub: IndicatorHub, current_regime: RegimeType, prev_day_close: float, avg_volume: float) -> Optional[StrategyCandidate]:
        """Evaluate the opening gap."""
        if len(candles) == 0:
            return None
            
        # Evaluate only on the first few candles
        first_candle = candles[0]
        
        features = indicator_hub.get_features()
        atr = features.get('ATR')
        vwap = features.get('VWAP')
        
        if atr is None or vwap is None or atr == 0:
            return None
            
        open_price = float(first_candle.open)
        gap_val = open_price - prev_day_close
        gap_pct = (gap_val / prev_day_close) * 100
        gap_atr = gap_val / atr
        
        gap_class = self.classify_gap(gap_pct, gap_atr, first_candle, avg_volume, vwap)
        
        direction = SignalDirection.NO_TRADE
        reason_codes = []
        target_price = prev_day_close
        stop_price = float(first_candle.low) if gap_pct > 0 else float(first_candle.high)
        
        if gap_class == GapClass.CONTINUATION_LONG:
            direction = SignalDirection.LONG
            reason_codes.append("GAP_CONTINUATION_LONG")
            target_price = float(first_candle.close) + (abs(gap_val) * self.config.continuation_target_gap_multiple)
            stop_price = float(first_candle.low)
        elif gap_class == GapClass.CONTINUATION_SHORT:
            direction = SignalDirection.SHORT
            reason_codes.append("GAP_CONTINUATION_SHORT")
            target_price = float(first_candle.close) - (abs(gap_val) * self.config.continuation_target_gap_multiple)
            stop_price = float(first_candle.high)
        elif gap_class == GapClass.FADE_LONG:
            direction = SignalDirection.LONG
            reason_codes.append("GAP_FADE_LONG")
            target_price = prev_day_close
            stop_price = float(first_candle.low)
        elif gap_class == GapClass.FADE_SHORT:
            direction = SignalDirection.SHORT
            reason_codes.append("GAP_FADE_SHORT")
            target_price = prev_day_close
            stop_price = float(first_candle.high)
            
        if direction == SignalDirection.NO_TRADE:
            return None
            
        return StrategyCandidate(
            instrument_id=instrument_id,
            family=self.family,
            direction=direction,
            entry_price=Price(first_candle.close),
            protective_stop=Price(stop_price),
            initial_target=Price(target_price),
            confidence=0.8,
            features={
                'gap_pct': gap_pct,
                'gap_atr': gap_atr,
                'gap_class': gap_class.value
            },
            reason_codes=reason_codes,
            timestamp=first_candle.end_timestamp,
            regime=current_regime,
            config_version=self.version
        )
