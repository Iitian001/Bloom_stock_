from enum import Enum
from typing import List

from pydantic import BaseModel

from bloom_stock.packages.domain.enums import SignalDirection
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.schemas.signals import StrategyCandidate


class BarrierHit(str, Enum):
    PROFIT = "PROFIT"
    STOP = "STOP"
    TIME = "TIME"
    EXPIRED = "EXPIRED"


class LabelResult(BaseModel):
    barrier: BarrierHit
    gross_return: float
    net_return: float  # After estimated costs
    bars_held: int
    is_successful: bool  # True if net_return > 0 and barrier == PROFIT


class TripleBarrierLabeler:
    """Applies triple-barrier labeling to trade candidates for ML training."""
    
    def __init__(self, cost_bps: float = 5.0):
        self.cost_bps = cost_bps  # Estimated round-trip cost in basis points
        
    def apply_barriers(
        self,
        candidate: StrategyCandidate,
        future_candles: List[Candle],
        profit_multiplier: float = 1.0,
        stop_multiplier: float = 1.0,
        max_bars: int = 45
    ) -> LabelResult:
        """Evaluate a candidate against future price action.
        
        Args:
            candidate: The entry signal
            future_candles: Ordered list of subsequent 1-min candles
            profit_multiplier: Scale initial target
            stop_multiplier: Scale protective stop
            max_bars: Time barrier
            
        Returns:
            LabelResult containing the hit barrier and returns
        """
        entry_price = float(candidate.entry_price)
        initial_target = float(candidate.initial_target)
        protective_stop = float(candidate.protective_stop)
        
        # Calculate target distance and stop distance
        target_dist = abs(initial_target - entry_price) * profit_multiplier
        stop_dist = abs(entry_price - protective_stop) * stop_multiplier
        
        if candidate.direction == SignalDirection.LONG:
            upper_barrier = entry_price + target_dist
            lower_barrier = entry_price - stop_dist
        elif candidate.direction == SignalDirection.SHORT:
            upper_barrier = entry_price + stop_dist
            lower_barrier = entry_price - target_dist
        else:
            return LabelResult(
                barrier=BarrierHit.EXPIRED,
                gross_return=0.0,
                net_return=0.0,
                bars_held=0,
                is_successful=False
            )
            
        barrier_hit = BarrierHit.TIME
        exit_price = entry_price
        bars_held = 0
        
        for i, candle in enumerate(future_candles):
            if i >= max_bars:
                break
                
            bars_held += 1
            high = float(candle.high)
            low = float(candle.low)
            
            if candidate.direction == SignalDirection.LONG:
                if low <= lower_barrier:
                    barrier_hit = BarrierHit.STOP
                    exit_price = lower_barrier
                    break
                elif high >= upper_barrier:
                    barrier_hit = BarrierHit.PROFIT
                    exit_price = upper_barrier
                    break
            else:  # SHORT
                if high >= upper_barrier:
                    barrier_hit = BarrierHit.STOP
                    exit_price = upper_barrier
                    break
                elif low <= lower_barrier:
                    barrier_hit = BarrierHit.PROFIT
                    exit_price = lower_barrier
                    break
                    
        if barrier_hit == BarrierHit.TIME and bars_held > 0:
            exit_price = float(future_candles[bars_held - 1].close)
            
        if bars_held == 0:
            return LabelResult(
                barrier=BarrierHit.EXPIRED,
                gross_return=0.0,
                net_return=0.0,
                bars_held=0,
                is_successful=False
            )
            
        if candidate.direction == SignalDirection.LONG:
            gross_return = (exit_price - entry_price) / entry_price
        else:
            gross_return = (entry_price - exit_price) / entry_price
            
        cost_fraction = self.cost_bps / 10000.0
        net_return = gross_return - cost_fraction
        
        is_successful = net_return > 0 and barrier_hit == BarrierHit.PROFIT
        
        return LabelResult(
            barrier=barrier_hit,
            gross_return=gross_return,
            net_return=net_return,
            bars_held=bars_held,
            is_successful=is_successful
        )
