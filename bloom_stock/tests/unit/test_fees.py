import pytest
from datetime import date
from decimal import Decimal
from bloom_stock.packages.fees.engine import FeeEngine, TradeForFee, default_angel_one_equity_intraday

@pytest.fixture
def fee_engine():
    schedule = default_angel_one_equity_intraday()
    return FeeEngine([schedule])

class TestFees:
    def test_angel_one_intraday_buy(self, fee_engine):
        trade = TradeForFee(
            side='BUY',
            price=Decimal('500'),
            quantity=100,
            broker='ANGEL_ONE',
            segment='EQUITY',
            product='INTRADAY',
            trade_date=date(2023, 5, 1)
        )
        fees = fee_engine.calculate(trade)
        
        turnover = Decimal('50000')
        assert fees.brokerage == min(Decimal('20.00'), turnover * Decimal('0.0003'))
        assert fees.brokerage == Decimal('15.00')
        assert fees.stt == Decimal('0')
        assert round(fees.exchange_transaction_charges, 2) == round(turnover * Decimal('0.0000345'), 2)
        
        expected_gst = (fees.brokerage + fees.exchange_transaction_charges) * Decimal('0.18')
        assert round(fees.gst, 2) == round(expected_gst, 2)
        
        expected_sebi = (turnover / Decimal('10000000')) * Decimal('10.00')
        assert fees.sebi_charges == expected_sebi
        
        expected_stamp_duty = round(turnover * Decimal('0.00003'))
        assert fees.stamp_duty == Decimal(expected_stamp_duty)

    def test_angel_one_intraday_sell(self, fee_engine):
        trade = TradeForFee(
            side='SELL',
            price=Decimal('510'),
            quantity=100,
            broker='ANGEL_ONE',
            segment='EQUITY',
            product='INTRADAY',
            trade_date=date(2023, 5, 1)
        )
        fees = fee_engine.calculate(trade)
        
        turnover = Decimal('51000')
        expected_stt = round(turnover * Decimal('0.00025'))
        assert fees.stt == Decimal(expected_stt)
        assert fees.stamp_duty == Decimal('0')

    def test_round_trip_cost(self, fee_engine):
        cost = fee_engine.round_trip_cost(
            buy_price=Decimal('500'),
            sell_price=Decimal('510'),
            quantity=100,
            broker='ANGEL_ONE',
            segment='EQUITY',
            product='INTRADAY',
            trade_date=date(2023, 5, 1)
        )
        
        assert cost.buy_side_total is not None
        assert cost.sell_side_total is not None
        assert cost.total == cost.buy_side_total + cost.sell_side_total
        assert cost.total_as_percentage > 0

    def test_fee_schedule_date_range(self):
        s1 = default_angel_one_equity_intraday()
        s1.effective_from = date(2022, 1, 1)
        s1.effective_to = date(2022, 12, 31)
        
        s2 = default_angel_one_equity_intraday()
        s2.effective_from = date(2023, 1, 1)
        
        engine = FeeEngine([s1, s2])
        
        # Test 2022 trade
        t1 = TradeForFee(side='BUY', price=Decimal('100'), quantity=1, broker='ANGEL_ONE', segment='EQUITY', product='INTRADAY', trade_date=date(2022, 5, 5))
        f1 = engine.calculate(t1)
        assert f1 is not None
        
        # Test 2023 trade
        t2 = TradeForFee(side='BUY', price=Decimal('100'), quantity=1, broker='ANGEL_ONE', segment='EQUITY', product='INTRADAY', trade_date=date(2023, 5, 5))
        f2 = engine.calculate(t2)
        assert f2 is not None

    def test_zero_quantity(self, fee_engine):
        trade = TradeForFee(
            side='BUY',
            price=Decimal('500'),
            quantity=0,
            broker='ANGEL_ONE',
            segment='EQUITY',
            product='INTRADAY',
            trade_date=date(2023, 5, 1)
        )
        fees = fee_engine.calculate(trade)
        assert fees.total == 0

    def test_high_value_trade(self, fee_engine):
        trade = TradeForFee(
            side='BUY',
            price=Decimal('5000'),
            quantity=1000,
            broker='ANGEL_ONE',
            segment='EQUITY',
            product='INTRADAY',
            trade_date=date(2023, 5, 1)
        )
        fees = fee_engine.calculate(trade)
        # turnover is 5,000,000. 0.03% is 1500. Cap is 20.
        assert fees.brokerage == Decimal('20.00')
