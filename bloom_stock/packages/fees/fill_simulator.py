from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

from bloom_stock.packages.domain.enums import OrderType, OrderSide
from bloom_stock.packages.domain.schemas.candles import Candle

class FillSimulatorConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    latency_ms: int = 50  # simulated order latency
    slippage_model: str = 'FIXED'  # FIXED, PROPORTIONAL, VOLUME_DEPENDENT  
    fixed_slippage_bps: Decimal = Decimal('5')  # 5 basis points
    max_participation_rate: Decimal = Decimal('0.05')  # max 5% of bar volume
    partial_fill_enabled: bool = False
    reject_if_gap_through_stop: bool = True

class SimulatedFill(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    fill_price: Decimal
    fill_quantity: int
    slippage: Decimal  # in price terms
    slippage_bps: Decimal  # in basis points
    is_partial: bool = False
    fill_timestamp: datetime
    reject_reason: Optional[str] = None

class FillSimulator:
    """Simulates order fills for backtesting with realistic execution modeling."""
    def __init__(self, config: FillSimulatorConfig):
        self.config = config
        
    def simulate_fill(
        self,
        order_type: OrderType,
        side: OrderSide,
        price: Decimal,
        quantity: int,
        candle: Candle,
        spread_estimate: Decimal = Decimal('0.0005'),
    ) -> Optional[SimulatedFill]:
        """
        Simulate whether and at what price an order would fill.
        Returns None if the order would not fill on this candle.
        """
        max_fill_qty = int(candle.volume * self.config.max_participation_rate)
        if max_fill_qty == 0:
            return None
            
        fill_qty = min(quantity, max_fill_qty)
        is_partial = fill_qty < quantity
        if is_partial and not self.config.partial_fill_enabled:
            return None
            
        slippage_bps = self.config.fixed_slippage_bps if self.config.slippage_model == 'FIXED' else Decimal('0')
        slippage_multiplier = slippage_bps / Decimal('10000')

        if order_type == OrderType.MARKET:
            base_price = candle.close
            slippage = base_price * slippage_multiplier
            fill_price = base_price + slippage if side == OrderSide.BUY else base_price - slippage
            return SimulatedFill(
                fill_price=fill_price,
                fill_quantity=fill_qty,
                slippage=slippage,
                slippage_bps=slippage_bps,
                is_partial=is_partial,
                fill_timestamp=candle.end_timestamp
            )
            
        elif order_type == OrderType.LIMIT:
            # Conservative mode: touching target does not guarantee a fill.
            if side == OrderSide.BUY:
                if candle.low < price:
                    return SimulatedFill(
                        fill_price=price,
                        fill_quantity=fill_qty,
                        slippage=Decimal('0'),
                        slippage_bps=Decimal('0'),
                        is_partial=is_partial,
                        fill_timestamp=candle.end_timestamp
                    )
            else:
                if candle.high > price:
                    return SimulatedFill(
                        fill_price=price,
                        fill_quantity=fill_qty,
                        slippage=Decimal('0'),
                        slippage_bps=Decimal('0'),
                        is_partial=is_partial,
                        fill_timestamp=candle.end_timestamp
                    )
            return None
            
        elif order_type in (OrderType.SL, OrderType.SL_M):
            trigger = price
            
            if side == OrderSide.BUY:
                if candle.open > trigger:
                    if self.config.reject_if_gap_through_stop:
                        return SimulatedFill(
                            fill_price=Decimal('0'),
                            fill_quantity=0,
                            slippage=Decimal('0'),
                            slippage_bps=Decimal('0'),
                            fill_timestamp=candle.start_timestamp,
                            reject_reason="GAP_THROUGH_STOP"
                        )
                    base_price = candle.open
                elif candle.high >= trigger:
                    base_price = trigger
                else:
                    return None
            else:
                if candle.open < trigger:
                    if self.config.reject_if_gap_through_stop:
                        return SimulatedFill(
                            fill_price=Decimal('0'),
                            fill_quantity=0,
                            slippage=Decimal('0'),
                            slippage_bps=Decimal('0'),
                            fill_timestamp=candle.start_timestamp,
                            reject_reason="GAP_THROUGH_STOP"
                        )
                    base_price = candle.open
                elif candle.low <= trigger:
                    base_price = trigger
                else:
                    return None
                    
            slippage = base_price * slippage_multiplier
            fill_price = base_price + slippage if side == OrderSide.BUY else base_price - slippage
            return SimulatedFill(
                fill_price=fill_price,
                fill_quantity=fill_qty,
                slippage=slippage,
                slippage_bps=slippage_bps,
                is_partial=is_partial,
                fill_timestamp=candle.end_timestamp
            )
            
        return None
