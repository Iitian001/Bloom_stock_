from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from loguru import logger

from bloom_stock.packages.domain.enums import StrategyFamily, SignalDirection, RegimeType
from bloom_stock.packages.domain.schemas.signals import StrategyCandidate
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.schemas.regime import RegimeClassification
from bloom_stock.packages.strategy_families.base import StrategyFamilyBase


class VWAPPullbackConfig(BaseModel):
    pullback_vwap_distance_max_atr: float = 0.3  # Max distance from VWAP in ATR units
    min_trend_ema_alignment: bool = True  # EMA 9 > 21 > 50 for uptrend
    min_adx: float = 20.0  # Minimum ADX for trend confirmation
    volume_contraction_threshold: float = 0.8  # Pullback volume < 80% avg
    bounce_volume_threshold: float = 1.2  # Bounce volume > 120% avg
    pullback_max_depth_atr: float = 2.0  # Max pullback depth
    pullback_max_duration_bars: int = 20  # Max pullback duration
    time_stop_minutes: int = 45
    target_method: str = 'SWING'  # SWING or VOLATILITY_TRAIL
    stop_method: str = 'VWAP_LOSS'  # Stop if VWAP lost with confirmation
    config_version: str = "1.0.0"


class VWAPInstrumentState(BaseModel):
    """Tracks per-instrument state for VWAP Pullback."""
    skip_reasons: list[str] = []
    pullback_started_bars_ago: int = 0
    in_pullback: bool = False
    pullback_direction: Optional[SignalDirection] = None


class VWAPPullback(StrategyFamilyBase):
    """Family B — VWAP Trend Pullback Strategy."""
    
    def __init__(self, config: Optional[VWAPPullbackConfig] = None):
        self._config = config or VWAPPullbackConfig()
        self._instrument_state: dict[str, VWAPInstrumentState] = {}
        
    @property
    def family(self) -> StrategyFamily:
        return StrategyFamily.VWAP_PULLBACK
        
    @property
    def compatible_regimes(self) -> list[str]:
        return [RegimeType.TREND_UP.value, RegimeType.TREND_DOWN.value]
        
    def is_compatible(self, regime: RegimeClassification) -> bool:
        return regime.regime.value in self.compatible_regimes
        
    def reset_session(self, instrument_id: str):
        self._instrument_state[instrument_id] = VWAPInstrumentState()
        
    def get_skip_reasons(self, instrument_id: str) -> list[str]:
        state = self._instrument_state.get(instrument_id)
        if state:
            return state.skip_reasons
        return []
        
    def _get_state(self, instrument_id: str) -> VWAPInstrumentState:
        if instrument_id not in self._instrument_state:
            self._instrument_state[instrument_id] = VWAPInstrumentState()
        return self._instrument_state[instrument_id]
        
    def on_candle(
        self,
        instrument_id: str,
        candle: Candle,
        features: dict,
        regime: RegimeClassification,
    ) -> Optional[StrategyCandidate]:
        state = self._get_state(instrument_id)
        
        if state.skip_reasons:
            return None
            
        price = float(candle.close)
        vwap = features.get('vwap')
        atr = features.get('atr', 0.0)
        adx = features.get('adx', 0.0)
        ema9 = features.get('ema_9')
        ema21 = features.get('ema_21')
        ema50 = features.get('ema_50')
        vol_ratio = features.get('volume_ratio_20', 1.0) # Assume 1.0 if missing
        
        if vwap is None or atr == 0.0:
            return None
            
        # 1. Trend Confirmation
        if adx < self._config.min_adx:
            state.in_pullback = False
            return None
            
        is_uptrend = False
        is_downtrend = False
        
        if self._config.min_trend_ema_alignment and ema9 is not None and ema21 is not None and ema50 is not None:
            is_uptrend = ema9 > ema21 > ema50 and price > vwap
            is_downtrend = ema9 < ema21 < ema50 and price < vwap
        else:
            is_uptrend = regime.regime == RegimeType.TREND_UP and price > vwap
            is_downtrend = regime.regime == RegimeType.TREND_DOWN and price < vwap
            
        if not is_uptrend and not is_downtrend:
            state.in_pullback = False
            return None
            
        trend_dir = SignalDirection.LONG if is_uptrend else SignalDirection.SHORT
        
        # 2. Pullback Detection
        distance_to_vwap = abs(price - vwap)
        distance_atr = distance_to_vwap / atr
        
        if distance_atr > self._config.pullback_max_depth_atr:
            state.in_pullback = False
            return None
            
        # Within strike distance of VWAP
        if distance_atr <= self._config.pullback_vwap_distance_max_atr:
            if not state.in_pullback:
                state.in_pullback = True
                state.pullback_started_bars_ago = 0
                state.pullback_direction = trend_dir
            else:
                state.pullback_started_bars_ago += 1
                
            if state.pullback_started_bars_ago > self._config.pullback_max_duration_bars:
                state.in_pullback = False
                return None
                
            # Volume contraction during pullback
            if vol_ratio > self._config.volume_contraction_threshold:
                # Not contracting enough yet
                return None
        else:
            # We are outside strike distance. If we were in pullback, maybe this is a bounce?
            if state.in_pullback and state.pullback_direction == trend_dir:
                # 3. Bounce Confirmation
                is_bounce_long = trend_dir == SignalDirection.LONG and float(candle.close) > float(candle.open)
                is_bounce_short = trend_dir == SignalDirection.SHORT and float(candle.close) < float(candle.open)
                
                if (is_bounce_long or is_bounce_short) and vol_ratio >= self._config.bounce_volume_threshold:
                    # Valid Candidate
                    stop_price = vwap - (0.5 * atr) if trend_dir == SignalDirection.LONG else vwap + (0.5 * atr)
                    risk = abs(price - stop_price)
                    target_price = price + (2 * risk) if trend_dir == SignalDirection.LONG else price - (2 * risk)
                    
                    reason_codes = ["VWAP_PULLBACK_BOUNCE", f"ADX_{adx:.1f}"]
                    if self._config.min_trend_ema_alignment:
                        reason_codes.append("EMA_ALIGNED")
                        
                    logger.info(f"[{instrument_id}] VWAP Pullback {trend_dir.value} Candidate. Entry: {price}, Stop: {stop_price}")
                    
                    state.in_pullback = False
                    return StrategyCandidate(
                        instrument_id=instrument_id,
                        family=self.family,
                        direction=trend_dir,
                        entry_price=candle.close,
                        protective_stop=stop_price,
                        initial_target=target_price,
                        confidence=0.75,
                        features=features,
                        reason_codes=reason_codes,
                        timestamp=candle.end_timestamp,
                        regime=regime.regime,
                        config_version=self._config.config_version,
                    )
                    
        return None
