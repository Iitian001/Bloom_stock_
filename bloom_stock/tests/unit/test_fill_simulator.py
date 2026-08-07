import pytest
from decimal import Decimal
from datetime import datetime, timezone
from bloom_stock.packages.fees.fill_simulator import FillSimulator, FillSimulatorConfig
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.enums import OrderType, OrderSide, DataQuality

def make_candle(o, h, l, c, v=1000, ts=None):
    return Candle(
        instrument_id='TEST', interval='1m',
        start_timestamp=ts or datetime.now(timezone.utc),
        end_timestamp=ts or datetime.now(timezone.utc),
        open=Decimal(str(o)), high=Decimal(str(h)),
        low=Decimal(str(l)), close=Decimal(str(c)),
        volume=v, source='test', is_complete=True,
        quality_status=DataQuality.GOOD,
        created_at=datetime.now(timezone.utc)
    )

@pytest.fixture
def sim():
    config = FillSimulatorConfig(
        fixed_slippage_bps=Decimal('5'),
        max_participation_rate=Decimal('0.10'),
        partial_fill_enabled=True,
        reject_if_gap_through_stop=True
    )
    return FillSimulator(config)

class TestFillSimulator:
    def test_market_order_fill(self, sim):
        c = make_candle(100, 105, 95, 102, 1000)
        fill = sim.simulate_fill(OrderType.MARKET, OrderSide.BUY, Decimal('0'), 10, c)
        
        assert fill is not None
        assert fill.fill_quantity == 10
        # buy gets positive slippage added to price
        assert fill.fill_price > Decimal('102')

    def test_limit_order_fill(self, sim):
        c = make_candle(100, 105, 95, 102, 1000)
        fill = sim.simulate_fill(OrderType.LIMIT, OrderSide.BUY, Decimal('98'), 10, c)
        assert fill is not None
        assert fill.fill_price == Decimal('98')

    def test_limit_order_no_fill(self, sim):
        c = make_candle(100, 105, 95, 102, 1000)
        fill = sim.simulate_fill(OrderType.LIMIT, OrderSide.BUY, Decimal('90'), 10, c)
        assert fill is None

    def test_sl_order_trigger(self, sim):
        c = make_candle(100, 105, 95, 102, 1000)
        fill = sim.simulate_fill(OrderType.SL, OrderSide.BUY, Decimal('103'), 10, c)
        assert fill is not None
        assert fill.fill_price > Decimal('103') # has slippage

    def test_participation_rate(self, sim):
        c = make_candle(100, 105, 95, 102, 100) # vol is 100
        # max participation is 10%, so 10 shares
        fill = sim.simulate_fill(OrderType.MARKET, OrderSide.BUY, Decimal('0'), 50, c)
        assert fill is not None
        assert fill.fill_quantity == 10
        assert fill.is_partial

    def test_gap_through_stop(self, sim):
        # Stop loss buy at 100
        # Market opens at 105 (gap up)
        c = make_candle(105, 110, 104, 108, 1000)
        fill = sim.simulate_fill(OrderType.SL, OrderSide.BUY, Decimal('100'), 10, c)
        
        assert fill is not None
        assert fill.reject_reason == "GAP_THROUGH_STOP"
        assert fill.fill_quantity == 0
