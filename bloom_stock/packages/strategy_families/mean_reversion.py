"""Mean Reversion Strategy Family.

Per Section 7.3 of the master plan. Mean reversion MUST NOT run in strong trend conditions.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from loguru import logger

from bloom_stock.packages.domain.enums import SignalDirection, StrategyFamily, RegimeType
from bloom_stock.packages.domain.schemas.signals import StrategyCandidate
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.types import InstrumentId, Price
from bloom_stock.packages.indicators.core import IndicatorHub


class MeanReversionConfig(BaseModel):
    min_adx_below: float = 25.0  # ADX must be BELOW this (range-bound)
    min_price_zscore: float = -2.0  # Significant negative deviation for longs
    max_price_zscore: float = 2.0  # Significant positive deviation for shorts
    rsi_oversold_percentile: float = 25.0  # RSI below this for longs
    rsi_overbought_percentile: float = 75.0  # RSI above this for shorts
    min_bb_percent_b_long: float = 0.0  # BB %B below 0 for longs
    max_bb_percent_b_short: float = 1.0  # BB %B above 1 for shorts
    vwap_distance_min_atr: float = 1.0  # Min distance from VWAP in ATR units
    reversal_candle_required: bool = True  # Must see reversal candle
    target_method: str = 'VWAP'  # VWAP, MIDDLE_BB, or FIXED_R
    target_r: float = 1.5
    time_stop_minutes: int = 30
    no_averaging_down: bool = True  # PROHIBITED
    no_second_entry_before_close: bool = True  # PROHIBITED


class MeanReversionStrategy:
    """Range Mean Reversion Strategy."""
    
    def __init__(self, config: Optional[MeanReversionConfig] = None):
        self.config = config or MeanReversionConfig()
        self.family = StrategyFamily.MEAN_REVERSION
        self.version = "1.0.0"
        self._active_positions: Dict[InstrumentId, bool] = {}
        
    def evaluate(self, instrument_id: InstrumentId, candles: List[Candle], indicator_hub: IndicatorHub, current_regime: RegimeType) -> Optional[StrategyCandidate]:
        """Evaluate market conditions and generate a signal if appropriate."""
        if len(candles) < 2:
            return None
            
        # Enforce regime constraint
        if current_regime not in [RegimeType.RANGE_LOW_VOL]:
            logger.debug(f"[{instrument_id}] Skipping mean reversion: Invalid regime {current_regime}")
            return None
            
        # Prevent multiple entries (no_second_entry_before_close / no_averaging_down)
        if self.config.no_second_entry_before_close and self._active_positions.get(instrument_id, False):
            logger.debug(f"[{instrument_id}] Skipping mean reversion: Active position exists")
            return None
            
        features = indicator_hub.get_features()
        
        adx = features.get('ADX_adx')
        if adx is None or adx >= self.config.min_adx_below:
            return None
            
        rsi = features.get('RSI')
        bb_percent_b = features.get('BollingerBands_percent_b')
        vwap = features.get('VWAP')
        atr = features.get('ATR')
        
        if any(x is None for x in [rsi, bb_percent_b, vwap, atr]):
            return None
            
        current_candle = candles[-1]
        prev_candle = candles[-2]
        close_price = float(current_candle.close)
        
        # Calculate normalized features
        distance_from_vwap = close_price - vwap
        distance_from_vwap_in_atr = distance_from_vwap / atr if atr > 0 else 0
        
        # Determine candidate direction
        direction = SignalDirection.NO_TRADE
        reason_codes = []
        
        # Long conditions
        long_cond = (
            distance_from_vwap_in_atr <= -self.config.vwap_distance_min_atr and
            rsi <= self.config.rsi_oversold_percentile and
            bb_percent_b <= self.config.min_bb_percent_b_long
        )
        
        # Short conditions
        short_cond = (
            distance_from_vwap_in_atr >= self.config.vwap_distance_min_atr and
            rsi >= self.config.rsi_overbought_percentile and
            bb_percent_b >= self.config.max_bb_percent_b_short
        )
        
        # Reversal candle check
        current_green = current_candle.close > current_candle.open
        prev_red = prev_candle.close < prev_candle.open
        current_red = current_candle.close < current_candle.open
        prev_green = prev_candle.close > prev_candle.open
        
        reversal_long = current_green and prev_red and current_candle.low > prev_candle.low
        reversal_short = current_red and prev_green and current_candle.high < prev_candle.high
        
        if self.config.reversal_candle_required:
            long_cond = long_cond and reversal_long
            short_cond = short_cond and reversal_short
            
        if long_cond and not short_cond:
            direction = SignalDirection.LONG
            reason_codes.append("OVERSOLD_VWAP_DEVIATION")
        elif short_cond and not long_cond:
            direction = SignalDirection.SHORT
            reason_codes.append("OVERBOUGHT_VWAP_DEVIATION")
            
        if direction == SignalDirection.NO_TRADE:
            return None
            
        entry_price = Price(current_candle.close)
        
        if direction == SignalDirection.LONG:
            protective_stop = current_candle.low - Decimal(str(atr * 0.5))
            initial_target = vwap
        else:
            protective_stop = current_candle.high + Decimal(str(atr * 0.5))
            initial_target = vwap
            
        return StrategyCandidate(
            instrument_id=instrument_id,
            family=self.family,
            direction=direction,
            entry_price=entry_price,
            protective_stop=Price(protective_stop),
            initial_target=Price(initial_target),
            confidence=0.7,
            features={
                'adx': adx,
                'rsi': rsi,
                'bb_percent_b': bb_percent_b,
                'distance_from_vwap_in_atr': distance_from_vwap_in_atr
            },
            reason_codes=reason_codes,
            timestamp=current_candle.end_timestamp,
            regime=current_regime,
            config_version=self.version
        )
