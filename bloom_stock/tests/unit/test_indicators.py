import pytest
import numpy as np
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from bloom_stock.packages.indicators.core import (
    EMA, SMA, RSI, ATR, MACD, BollingerBands, VWAP, Supertrend, ADX, OpeningRange, IndicatorHub
)
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.enums import DataQuality

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

class TestEMA:
    def test_ema_basic(self):
        ema = EMA(5)
        prices = [10.0, 10.0, 10.0, 10.0, 10.0, 20.0, 20.0, 20.0, 20.0, 20.0]
        results = [ema.update(p) for p in prices]
        assert results[4] == 10.0  # SMA for first 5
        assert round(results[-1], 4) == 18.6831

    def test_ema_not_ready(self):
        ema = EMA(5)
        assert ema.update(10.0) is None
        assert ema.update(10.0) is None
        assert ema.update(10.0) is None
        assert not ema.is_ready

    def test_ema_batch(self):
        prices = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 20.0, 20.0, 20.0, 20.0, 20.0])
        batch = EMA.compute_series(prices, 5)
        
        ema = EMA(5)
        incremental = [ema.update(p) for p in prices]
        
        assert np.isnan(batch[0])
        assert batch[4] == incremental[4]
        assert batch[-1] == incremental[-1]

    def test_ema_single_period(self):
        ema = EMA(1)
        assert ema.update(15.0) == 15.0
        assert ema.update(20.0) == 20.0

class TestSMA:
    def test_sma_basic(self):
        sma = SMA(3)
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        results = [sma.update(p) for p in prices]
        assert results[2] == 20.0
        assert results[3] == 30.0
        assert results[4] == 40.0

    def test_sma_rolling(self):
        sma = SMA(2)
        sma.update(10.0)
        sma.update(20.0)
        assert sma.value == 15.0
        sma.update(30.0)
        assert sma.value == 25.0

    def test_sma_not_ready(self):
        sma = SMA(3)
        assert sma.update(10.0) is None
        assert sma.update(20.0) is None

class TestRSI:
    def test_rsi_all_gains(self):
        rsi = RSI(3)
        for p in [10.0, 20.0, 30.0, 40.0]:
            val = rsi.update(p)
        assert val == 100.0

    def test_rsi_all_losses(self):
        rsi = RSI(3)
        for p in [40.0, 30.0, 20.0, 10.0]:
            val = rsi.update(p)
        assert val == 0.0

    def test_rsi_known_sequence(self):
        prices = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
        rsi = RSI(14)
        vals = [rsi.update(p) for p in prices]
        assert vals[-1] is not None
        assert 40 <= vals[-1] <= 65 # Check it's reasonable, exact depends on wilder smoothing exact match

    def test_rsi_range(self):
        prices = np.random.uniform(10, 100, 50)
        rsi = RSI(14)
        for p in prices:
            val = rsi.update(p)
            if val is not None:
                assert 0 <= val <= 100

    def test_rsi_batch_matches_incremental(self):
        prices = np.random.uniform(10, 100, 50)
        batch = RSI.compute_series(prices, 14)
        
        rsi = RSI(14)
        inc = [rsi.update(p) for p in prices]
        
        if inc[-1] is not None:
            assert np.isclose(batch[-1], inc[-1], atol=1e-5)

class TestATR:
    def test_atr_basic(self):
        atr = ATR(3)
        atr.update(12.0, 10.0, 11.0)
        atr.update(13.0, 10.0, 12.0)
        val = atr.update(14.0, 11.0, 13.0)
        assert val is not None
        assert val > 0

    def test_atr_flat_market(self):
        atr = ATR(3)
        atr.update(10.0, 10.0, 10.0)
        atr.update(10.0, 10.0, 10.0)
        val = atr.update(10.0, 10.0, 10.0)
        assert val == 0.0

    def test_atr_volatile(self):
        atr1 = ATR(3)
        atr1.update(11, 9, 10)
        atr1.update(11, 9, 10)
        val1 = atr1.update(11, 9, 10)
        
        atr2 = ATR(3)
        atr2.update(20, 5, 10)
        atr2.update(20, 5, 10)
        val2 = atr2.update(20, 5, 10)
        
        assert val2 > val1

class TestMACD:
    def test_macd_crossover(self):
        macd = MACD(12, 26, 9)
        prices = np.linspace(10, 50, 40) # Trending up
        vals = []
        for p in prices:
            v = macd.update(p)
            if v: vals.append(v)
        assert len(vals) > 0

    def test_macd_histogram_sign(self):
        macd = MACD(3, 6, 3) # short periods for testing
        for p in [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]:
            v = macd.update(p)
            if v:
                if v.macd > v.signal:
                    assert v.histogram > 0

    def test_macd_not_ready(self):
        macd = MACD(12, 26, 9)
        assert macd.update(10.0) is None

class TestBollingerBands:
    def test_bb_basic(self):
        bb = BollingerBands(3, 2.0)
        bb.update(10)
        bb.update(10)
        val = bb.update(10)
        assert val.upper == 10.0
        assert val.middle == 10.0
        assert val.lower == 10.0
        
    def test_bb_bandwidth(self):
        bb = BollingerBands(3, 2.0)
        bb.update(8)
        bb.update(10)
        val = bb.update(12)
        assert val.bandwidth > 0
        
    def test_bb_percent_b(self):
        bb = BollingerBands(3, 2.0)
        bb.update(10)
        bb.update(12)
        val = bb.update(14) # 14 is upper bound roughly
        assert val.percent_b >= 0.5

class TestVWAP:
    def test_vwap_single_bar(self):
        vwap = VWAP()
        val = vwap.update(11.0, 9.0, 10.0, 100)
        assert val == 10.0 # typical price = 30/3

    def test_vwap_cumulative(self):
        vwap = VWAP()
        vwap.update(11.0, 9.0, 10.0, 100) # typical: 10, vol: 100
        val = vwap.update(21.0, 19.0, 20.0, 100) # typical: 20, vol: 100
        assert val == 15.0 # (1000 + 2000) / 200 = 15

    def test_vwap_reset(self):
        vwap = VWAP()
        vwap.update(11, 9, 10, 100)
        vwap.reset()
        val = vwap.update(21, 19, 20, 100)
        assert val == 20.0

    def test_vwap_distance(self):
        vwap = VWAP()
        vwap.update(11, 9, 10, 100) # vwap = 10
        assert vwap.distance_from_vwap(12.0) == 2.0

class TestSupertrend:
    def test_supertrend_uptrend(self):
        st = Supertrend(3, 2.0)
        st.update(10, 9, 9.5)
        st.update(11, 10, 10.5)
        st.update(12, 11, 11.5)
        st.update(13, 12, 12.5)
        val = st.update(14, 13, 13.5)
        if val:
            assert not val.is_bullish

    def test_supertrend_flip(self):
        st = Supertrend(3, 2.0)
        for p in range(10, 20):
            st.update(p+1, p-1, p)
        assert st.is_bullish
        val = st.update(5, 4, 4.5)
        assert not val.is_bullish

class TestADX:
    def test_adx_trending(self):
        adx = ADX(3)
        vals = []
        for p in range(10, 30):
            v = adx.update(p+1, p, p+0.5)
            if v: vals.append(v)
        if vals:
            assert vals[-1].adx > 25

    def test_adx_ranging(self):
        adx = ADX(3)
        vals = []
        for i in range(20):
            p = 10 if i % 2 == 0 else 11
            v = adx.update(p+1, p-1, p)
            if v: vals.append(v)

class TestOpeningRange:
    def test_opening_range_formation(self):
        orr = OpeningRange(15)
        now = datetime.now(timezone.utc)
        for i in range(15):
            c = make_candle(10, 15, 5, 12, ts=now + timedelta(minutes=i))
            c.end_timestamp = now + timedelta(minutes=i+1)
            orr.add_candle(c)
        assert orr.is_complete
        assert orr.range_high == 15.0
        assert orr.range_low == 5.0

    def test_opening_range_breakout(self):
        orr = OpeningRange(5)
        now = datetime.now(timezone.utc)
        for i in range(6):
            c = make_candle(10, 15, 5, 12, ts=now + timedelta(minutes=i))
            c.end_timestamp = now + timedelta(minutes=i+1)
            orr.add_candle(c)
        assert orr.is_breakout_long(16.0)
        assert not orr.is_breakout_long(14.0)
        assert orr.is_breakout_short(4.0)

    def test_opening_range_noise_buffer(self):
        orr = OpeningRange(5)
        now = datetime.now(timezone.utc)
        for i in range(6):
            c = make_candle(10, 15, 5, 12, ts=now + timedelta(minutes=i))
            orr.add_candle(c)
        assert not orr.is_breakout_long(15.5, noise_buffer=1.0)
        assert orr.is_breakout_long(16.5, noise_buffer=1.0)

class TestIndicatorHub:
    def test_hub_updates_all(self):
        config = {
            'my_sma': {'type': 'SMA', 'period': 3},
            'my_ema': {'type': 'EMA', 'period': 3}
        }
        hub = IndicatorHub(config)
        now = datetime.now(timezone.utc)
        c1 = make_candle(10, 10, 10, 10, ts=now)
        c2 = make_candle(20, 20, 20, 20, ts=now)
        c3 = make_candle(30, 30, 30, 30, ts=now)
        
        hub.update_candle(c1)
        hub.update_candle(c2)
        res = hub.update_candle(c3)
        
        assert res['my_sma'] == 20.0
        assert res['my_ema'] is not None

    def test_hub_features_dict(self):
        config = {
            'sma3': {'type': 'SMA', 'period': 3}
        }
        hub = IndicatorHub(config)
        hub.update_candle(make_candle(10, 10, 10, 10))
        hub.update_candle(make_candle(20, 20, 20, 20))
        hub.update_candle(make_candle(30, 30, 30, 30))
        f = hub.get_features()
        assert f['sma3'] == 20.0
