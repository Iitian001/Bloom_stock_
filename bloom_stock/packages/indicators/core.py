import math
from collections import deque, namedtuple
from typing import Optional, Dict, Any, List
from datetime import datetime
import numpy as np

from bloom_stock.packages.domain.schemas.candles import Candle


MACDResult = namedtuple('MACDResult', ['macd', 'signal', 'histogram'])
BBResult = namedtuple('BBResult', ['upper', 'middle', 'lower', 'bandwidth', 'percent_b'])
SupertrendResult = namedtuple('SupertrendResult', ['value', 'direction', 'is_bullish'])
ADXResult = namedtuple('ADXResult', ['adx', 'plus_di', 'minus_di'])


class EMA:
    """Exponential Moving Average."""
    def __init__(self, period: int):
        self.period = period
        self.k = 2.0 / (period + 1)
        self._value: Optional[float] = None
        self._count = 0
        self._sum = 0.0

    def update(self, price: float) -> Optional[float]:
        if self._value is None:
            self._count += 1
            self._sum += price
            if self._count == self.period:
                self._value = self._sum / self.period
        else:
            self._value = price * self.k + self._value * (1.0 - self.k)
        return self._value

    @property
    def value(self) -> Optional[float]:
        return self._value

    @property
    def is_ready(self) -> bool:
        return self._value is not None

    @classmethod
    def compute_series(cls, prices: np.ndarray, period: int) -> np.ndarray:
        if len(prices) < period:
            return np.full_like(prices, np.nan, dtype=float)
        
        ema = np.full_like(prices, np.nan, dtype=float)
        sma = np.mean(prices[:period])
        ema[period - 1] = sma
        k = 2.0 / (period + 1)
        
        val = sma
        for i in range(period, len(prices)):
            val = prices[i] * k + val * (1.0 - k)
            ema[i] = val
        return ema
        
    @classmethod
    def compute(cls, candles: List[Candle], period: int) -> np.ndarray:
        prices = np.array([float(c.close) for c in candles])
        return cls.compute_series(prices, period)


class SMA:
    """Simple Moving Average."""
    def __init__(self, period: int):
        self.period = period
        self.buffer: deque[float] = deque(maxlen=period)
        self._sum = 0.0

    def update(self, price: float) -> Optional[float]:
        if len(self.buffer) == self.period:
            self._sum -= self.buffer[0]
        self.buffer.append(price)
        self._sum += price
        if len(self.buffer) == self.period:
            return self._sum / self.period
        return None

    @property
    def value(self) -> Optional[float]:
        if len(self.buffer) == self.period:
            return self._sum / self.period
        return None

    @property
    def is_ready(self) -> bool:
        return len(self.buffer) == self.period

    @classmethod
    def compute_series(cls, prices: np.ndarray, period: int) -> np.ndarray:
        out = np.full_like(prices, np.nan, dtype=float)
        if len(prices) < period:
            return out
        cumsum = np.cumsum(prices, dtype=float)
        cumsum[period:] = cumsum[period:] - cumsum[:-period]
        out[period - 1:] = cumsum[period - 1:] / period
        return out

    @classmethod
    def compute(cls, candles: List[Candle], period: int) -> np.ndarray:
        prices = np.array([float(c.close) for c in candles])
        return cls.compute_series(prices, period)


class RSI:
    """Relative Strength Index with Wilder's Smoothing."""
    def __init__(self, period: int = 14):
        self.period = period
        self.prev_price: Optional[float] = None
        self.avg_gain: Optional[float] = None
        self.avg_loss: Optional[float] = None
        self._value: Optional[float] = None
        self._count = 0
        self._sum_gain = 0.0
        self._sum_loss = 0.0

    def update(self, price: float) -> Optional[float]:
        if self.prev_price is None:
            self.prev_price = price
            return None
        
        change = price - self.prev_price
        self.prev_price = price
        
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0
        
        if self.avg_gain is None:
            self._count += 1
            self._sum_gain += gain
            self._sum_loss += loss
            if self._count == self.period:
                self.avg_gain = self._sum_gain / self.period
                self.avg_loss = self._sum_loss / self.period
                self._calculate_rsi()
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
            self._calculate_rsi()
            
        return self._value

    def _calculate_rsi(self):
        if self.avg_loss == 0.0:
            self._value = 100.0
        else:
            rs = self.avg_gain / self.avg_loss
            self._value = 100.0 - (100.0 / (1.0 + rs))

    @property
    def value(self) -> Optional[float]:
        return self._value

    @property
    def is_ready(self) -> bool:
        return self._value is not None

    @classmethod
    def compute_series(cls, prices: np.ndarray, period: int = 14) -> np.ndarray:
        out = np.full_like(prices, np.nan, dtype=float)
        if len(prices) <= period:
            return out
        diff = np.diff(prices)
        gains = np.where(diff > 0, diff, 0.0)
        losses = np.where(diff < 0, -diff, 0.0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        if avg_loss == 0:
            out[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[period] = 100.0 - (100.0 / (1.0 + rs))
            
        for i in range(period, len(diff)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                out[i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                out[i + 1] = 100.0 - (100.0 / (1.0 + rs))
        return out

    @classmethod
    def compute(cls, candles: List[Candle], period: int = 14) -> np.ndarray:
        prices = np.array([float(c.close) for c in candles])
        return cls.compute_series(prices, period)


class ATR:
    """Average True Range with Wilder's Smoothing."""
    def __init__(self, period: int = 14):
        self.period = period
        self.prev_close: Optional[float] = None
        self._value: Optional[float] = None
        self._count = 0
        self._sum_tr = 0.0

    def update(self, high: float, low: float, close: float) -> Optional[float]:
        if self.prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - self.prev_close), abs(low - self.prev_close))
            
        self.prev_close = close
        
        if self._value is None:
            self._count += 1
            self._sum_tr += tr
            if self._count == self.period:
                self._value = self._sum_tr / self.period
        else:
            self._value = (self._value * (self.period - 1) + tr) / self.period
            
        return self._value

    @property
    def value(self) -> Optional[float]:
        return self._value

    @property
    def is_ready(self) -> bool:
        return self._value is not None

    @classmethod
    def compute_series(cls, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        out = np.full_like(highs, np.nan, dtype=float)
        if len(highs) < period:
            return out
            
        trs = np.zeros_like(highs, dtype=float)
        trs[0] = highs[0] - lows[0]
        
        hl = highs[1:] - lows[1:]
        hc = np.abs(highs[1:] - closes[:-1])
        lc = np.abs(lows[1:] - closes[:-1])
        trs[1:] = np.maximum(hl, np.maximum(hc, lc))
        
        out[period - 1] = np.mean(trs[:period])
        val = out[period - 1]
        
        for i in range(period, len(highs)):
            val = (val * (period - 1) + trs[i]) / period
            out[i] = val
            
        return out

    @classmethod
    def compute(cls, candles: List[Candle], period: int = 14) -> np.ndarray:
        highs = np.array([float(c.high) for c in candles])
        lows = np.array([float(c.low) for c in candles])
        closes = np.array([float(c.close) for c in candles])
        return cls.compute_series(highs, lows, closes, period)


class MACD:
    """Moving Average Convergence Divergence."""
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.ema_fast = EMA(fast)
        self.ema_slow = EMA(slow)
        self.ema_signal = EMA(signal)
        self._result: Optional[MACDResult] = None

    def update(self, price: float) -> Optional[MACDResult]:
        fast_val = self.ema_fast.update(price)
        slow_val = self.ema_slow.update(price)
        
        if fast_val is not None and slow_val is not None:
            macd_val = fast_val - slow_val
            sig_val = self.ema_signal.update(macd_val)
            
            if sig_val is not None:
                hist_val = macd_val - sig_val
                self._result = MACDResult(macd_val, sig_val, hist_val)
                return self._result
        return None

    @property
    def value(self) -> Optional[MACDResult]:
        return self._result

    @property
    def is_ready(self) -> bool:
        return self._result is not None
        
    @classmethod
    def compute_series(cls, prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        fast_ema = EMA.compute_series(prices, fast)
        slow_ema = EMA.compute_series(prices, slow)
        macd_line = fast_ema - slow_ema
        
        valid_macd = macd_line[~np.isnan(macd_line)]
        signal_line = np.full_like(prices, np.nan)
        
        if len(valid_macd) > 0:
            sig = EMA.compute_series(valid_macd, signal)
            signal_line[-len(sig):] = sig
            
        histogram = macd_line - signal_line
        return {'macd': macd_line, 'signal': signal_line, 'histogram': histogram}

    @classmethod
    def compute(cls, candles: List[Candle], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        prices = np.array([float(c.close) for c in candles])
        return cls.compute_series(prices, fast, slow, signal)


class BollingerBands:
    """Bollinger Bands."""
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev
        self.buffer: deque[float] = deque(maxlen=period)
        self._result: Optional[BBResult] = None

    def update(self, price: float) -> Optional[BBResult]:
        self.buffer.append(price)
        
        if len(self.buffer) == self.period:
            middle = sum(self.buffer) / self.period
            variance = sum((x - middle) ** 2 for x in self.buffer) / self.period
            std = math.sqrt(variance)
            
            upper = middle + self.std_dev * std
            lower = middle - self.std_dev * std
            bandwidth = (upper - lower) / middle if middle != 0 else 0.0
            percent_b = (price - lower) / (upper - lower) if upper != lower else 0.0
            
            self._result = BBResult(upper, middle, lower, bandwidth, percent_b)
            return self._result
        return None

    @property
    def value(self) -> Optional[BBResult]:
        return self._result

    @property
    def is_ready(self) -> bool:
        return self._result is not None

    @classmethod
    def compute_series(cls, prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Dict[str, np.ndarray]:
        n = len(prices)
        middle = SMA.compute_series(prices, period)
        std = np.full_like(prices, np.nan)
        
        for i in range(period - 1, n):
            std[i] = np.std(prices[i - period + 1 : i + 1])
            
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        with np.errstate(divide='ignore', invalid='ignore'):
            bandwidth = np.where(middle != 0, (upper - lower) / middle, 0.0)
            percent_b = np.where(upper != lower, (prices - lower) / (upper - lower), 0.0)
            
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'bandwidth': bandwidth,
            'percent_b': percent_b
        }

    @classmethod
    def compute(cls, candles: List[Candle], period: int = 20, std_dev: float = 2.0) -> Dict[str, np.ndarray]:
        prices = np.array([float(c.close) for c in candles])
        return cls.compute_series(prices, period, std_dev)


class VWAP:
    """Volume Weighted Average Price. Resets daily."""
    def __init__(self):
        self.cum_vol_price = 0.0
        self.cum_vol = 0.0
        self._value: Optional[float] = None

    def reset(self):
        self.cum_vol_price = 0.0
        self.cum_vol = 0.0
        self._value = None

    def update(self, high: float, low: float, close: float, volume: int) -> Optional[float]:
        typical_price = (high + low + close) / 3.0
        self.cum_vol_price += typical_price * volume
        self.cum_vol += volume
        
        if self.cum_vol > 0:
            self._value = self.cum_vol_price / self.cum_vol
            return self._value
        return None

    def distance_from_vwap(self, price: float) -> float:
        if self._value is None:
            return 0.0
        return price - self._value

    def distance_from_vwap_atr(self, price: float, atr: float) -> float:
        if self._value is None or atr == 0.0:
            return 0.0
        return (price - self._value) / atr

    @property
    def value(self) -> Optional[float]:
        return self._value

    @property
    def is_ready(self) -> bool:
        return self._value is not None

    @classmethod
    def compute_series(cls, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        typical_prices = (highs + lows + closes) / 3.0
        cum_vp = np.cumsum(typical_prices * volumes)
        cum_v = np.cumsum(volumes)
        
        with np.errstate(divide='ignore', invalid='ignore'):
            vwap = np.where(cum_v > 0, cum_vp / cum_v, np.nan)
        return vwap

    @classmethod
    def compute(cls, candles: List[Candle]) -> np.ndarray:
        highs = np.array([float(c.high) for c in candles])
        lows = np.array([float(c.low) for c in candles])
        closes = np.array([float(c.close) for c in candles])
        volumes = np.array([int(c.volume) for c in candles])
        return cls.compute_series(highs, lows, closes, volumes)


class Supertrend:
    """Supertrend Indicator."""
    def __init__(self, atr_period: int = 7, multiplier: float = 2.0):
        self.atr = ATR(atr_period)
        self.multiplier = multiplier
        self.prev_close: Optional[float] = None
        self.upper_band: Optional[float] = None
        self.lower_band: Optional[float] = None
        self.is_bullish = True
        self._result: Optional[SupertrendResult] = None

    def update(self, high: float, low: float, close: float) -> Optional[SupertrendResult]:
        atr_val = self.atr.update(high, low, close)
        
        if atr_val is None:
            self.prev_close = close
            return None
            
        hl2 = (high + low) / 2.0
        basic_upper = hl2 + self.multiplier * atr_val
        basic_lower = hl2 - self.multiplier * atr_val
        
        if self.upper_band is None or self.lower_band is None:
            self.upper_band = basic_upper
            self.lower_band = basic_lower
            self.is_bullish = close > self.upper_band
        else:
            if basic_upper < self.upper_band or self.prev_close > self.upper_band:
                self.upper_band = basic_upper
                
            if basic_lower > self.lower_band or self.prev_close < self.lower_band:
                self.lower_band = basic_lower
                
        if self.is_bullish and close <= self.lower_band:
            self.is_bullish = False
        elif not self.is_bullish and close >= self.upper_band:
            self.is_bullish = True
            
        res_value = self.lower_band if self.is_bullish else self.upper_band
        res_direction = 1 if self.is_bullish else -1
        
        self.prev_close = close
        self._result = SupertrendResult(res_value, res_direction, self.is_bullish)
        return self._result

    @property
    def value(self) -> Optional[SupertrendResult]:
        return self._result

    @property
    def is_ready(self) -> bool:
        return self._result is not None

    @classmethod
    def compute(cls, candles: List[Candle], atr_period: int = 7, multiplier: float = 2.0) -> Dict[str, np.ndarray]:
        highs = np.array([float(c.high) for c in candles])
        lows = np.array([float(c.low) for c in candles])
        closes = np.array([float(c.close) for c in candles])
        
        n = len(closes)
        out_value = np.full(n, np.nan)
        out_dir = np.full(n, np.nan)
        out_bullish = np.zeros(n, dtype=bool)
        
        st = cls(atr_period, multiplier)
        for i in range(n):
            res = st.update(highs[i], lows[i], closes[i])
            if res is not None:
                out_value[i] = res.value
                out_dir[i] = res.direction
                out_bullish[i] = res.is_bullish
                
        return {'value': out_value, 'direction': out_dir, 'is_bullish': out_bullish}


class ADX:
    """Average Directional Index."""
    def __init__(self, period: int = 14):
        self.period = period
        self.prev_high: Optional[float] = None
        self.prev_low: Optional[float] = None
        self.atr = ATR(period)
        
        self._count = 0
        self._sum_pdm = 0.0
        self._sum_ndm = 0.0
        
        self.smooth_pdm: Optional[float] = None
        self.smooth_ndm: Optional[float] = None
        
        self.adx_count = 0
        self._sum_dx = 0.0
        self.adx_val: Optional[float] = None
        
        self._result: Optional[ADXResult] = None

    def update(self, high: float, low: float, close: float) -> Optional[ADXResult]:
        atr_val = self.atr.update(high, low, close)
        
        if self.prev_high is None:
            self.prev_high = high
            self.prev_low = low
            return None
            
        up_move = high - self.prev_high
        down_move = self.prev_low - low
        
        self.prev_high = high
        self.prev_low = low
        
        pdm = up_move if up_move > down_move and up_move > 0 else 0.0
        ndm = down_move if down_move > up_move and down_move > 0 else 0.0
        
        if self.smooth_pdm is None:
            self._count += 1
            self._sum_pdm += pdm
            self._sum_ndm += ndm
            
            if self._count == self.period:
                self.smooth_pdm = self._sum_pdm / self.period
                self.smooth_ndm = self._sum_ndm / self.period
        else:
            self.smooth_pdm = (self.smooth_pdm * (self.period - 1) + pdm) / self.period
            self.smooth_ndm = (self.smooth_ndm * (self.period - 1) + ndm) / self.period
            
        if self.smooth_pdm is not None and atr_val is not None and atr_val > 0:
            plus_di = 100.0 * (self.smooth_pdm / atr_val)
            minus_di = 100.0 * (self.smooth_ndm / atr_val)
            
            dx = 100.0 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0.0
            
            if self.adx_val is None:
                self.adx_count += 1
                self._sum_dx += dx
                if self.adx_count == self.period:
                    self.adx_val = self._sum_dx / self.period
            else:
                self.adx_val = (self.adx_val * (self.period - 1) + dx) / self.period
                
            if self.adx_val is not None:
                self._result = ADXResult(self.adx_val, plus_di, minus_di)
                return self._result
                
        return None

    @property
    def value(self) -> Optional[ADXResult]:
        return self._result

    @property
    def is_ready(self) -> bool:
        return self._result is not None

    @classmethod
    def compute(cls, candles: List[Candle], period: int = 14) -> Dict[str, np.ndarray]:
        highs = np.array([float(c.high) for c in candles])
        lows = np.array([float(c.low) for c in candles])
        closes = np.array([float(c.close) for c in candles])
        
        n = len(closes)
        out_adx = np.full(n, np.nan)
        out_pdi = np.full(n, np.nan)
        out_mdi = np.full(n, np.nan)
        
        inst = cls(period)
        for i in range(n):
            res = inst.update(highs[i], lows[i], closes[i])
            if res is not None:
                out_adx[i] = res.adx
                out_pdi[i] = res.plus_di
                out_mdi[i] = res.minus_di
                
        return {'adx': out_adx, 'plus_di': out_pdi, 'minus_di': out_mdi}


class OpeningRange:
    """Opening Range Indicator."""
    def __init__(self, duration_minutes: int = 15):
        self.duration_minutes = duration_minutes
        self._range_high = -float('inf')
        self._range_low = float('inf')
        self.start_time: Optional[datetime] = None
        self._is_complete = False

    def add_candle(self, candle: Candle) -> bool:
        if self._is_complete:
            return True
            
        if self.start_time is None:
            self.start_time = candle.start_timestamp
            
        elapsed = (candle.end_timestamp - self.start_time).total_seconds() / 60.0
        
        if elapsed <= self.duration_minutes:
            self._range_high = max(self._range_high, float(candle.high))
            self._range_low = min(self._range_low, float(candle.low))
            
        if elapsed >= self.duration_minutes:
            self._is_complete = True
            
        return self._is_complete

    def reset(self):
        self._range_high = -float('inf')
        self._range_low = float('inf')
        self.start_time = None
        self._is_complete = False

    @property
    def is_complete(self) -> bool:
        return self._is_complete

    @property
    def range_high(self) -> float:
        return self._range_high if self._range_high != -float('inf') else 0.0

    @property
    def range_low(self) -> float:
        return self._range_low if self._range_low != float('inf') else 0.0

    @property
    def range_size(self) -> float:
        if self._range_high != -float('inf') and self._range_low != float('inf'):
            return self._range_high - self._range_low
        return 0.0

    @property
    def range_midpoint(self) -> float:
        if self._range_high != -float('inf') and self._range_low != float('inf'):
            return (self._range_high + self._range_low) / 2.0
        return 0.0

    def is_breakout_long(self, price: float, noise_buffer: float = 0.0) -> bool:
        if not self._is_complete:
            return False
        return price > (self.range_high + noise_buffer)

    def is_breakout_short(self, price: float, noise_buffer: float = 0.0) -> bool:
        if not self._is_complete:
            return False
        return price < (self.range_low - noise_buffer)


class IndicatorHub:
    """Manages all indicators for a single instrument."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.indicators: Dict[str, Any] = {}
        
        for name, params in config.items():
            ind_type = params.get('type')
            if ind_type == 'EMA':
                self.indicators[name] = EMA(params.get('period', 14))
            elif ind_type == 'SMA':
                self.indicators[name] = SMA(params.get('period', 14))
            elif ind_type == 'RSI':
                self.indicators[name] = RSI(params.get('period', 14))
            elif ind_type == 'ATR':
                self.indicators[name] = ATR(params.get('period', 14))
            elif ind_type == 'MACD':
                self.indicators[name] = MACD(
                    params.get('fast', 12), 
                    params.get('slow', 26), 
                    params.get('signal', 9)
                )
            elif ind_type == 'BollingerBands':
                self.indicators[name] = BollingerBands(
                    params.get('period', 20),
                    params.get('std_dev', 2.0)
                )
            elif ind_type == 'VWAP':
                self.indicators[name] = VWAP()
            elif ind_type == 'Supertrend':
                self.indicators[name] = Supertrend(
                    params.get('atr_period', 7),
                    params.get('multiplier', 2.0)
                )
            elif ind_type == 'ADX':
                self.indicators[name] = ADX(params.get('period', 14))
            elif ind_type == 'OpeningRange':
                self.indicators[name] = OpeningRange(params.get('duration_minutes', 15))

    def update_candle(self, candle: Candle) -> Dict[str, Any]:
        results = {}
        c_open = float(candle.open)
        c_high = float(candle.high)
        c_low = float(candle.low)
        c_close = float(candle.close)
        c_vol = int(candle.volume)
        
        for name, ind in self.indicators.items():
            if isinstance(ind, EMA) or isinstance(ind, SMA) or isinstance(ind, RSI):
                ind.update(c_close)
                results[name] = ind.value
            elif isinstance(ind, MACD) or isinstance(ind, BollingerBands):
                ind.update(c_close)
                res = ind.value
                if res:
                    for k, v in res._asdict().items():
                        results[f"{name}_{k}"] = v
                else:
                    results[name] = None
            elif isinstance(ind, ATR) or isinstance(ind, Supertrend) or isinstance(ind, ADX):
                ind.update(c_high, c_low, c_close)
                res = ind.value
                if res:
                    if hasattr(res, '_asdict'):
                        for k, v in res._asdict().items():
                            results[f"{name}_{k}"] = v
                    else:
                        results[name] = res
                else:
                    results[name] = None
            elif isinstance(ind, VWAP):
                ind.update(c_high, c_low, c_close, c_vol)
                results[name] = ind.value
            elif isinstance(ind, OpeningRange):
                ind.add_candle(candle)
                if ind.is_complete:
                    results[f"{name}_high"] = ind.range_high
                    results[f"{name}_low"] = ind.range_low
                    results[f"{name}_mid"] = ind.range_midpoint
                else:
                    results[f"{name}_high"] = None
        
        return results

    def get_features(self) -> Dict[str, Any]:
        features = {}
        for name, ind in self.indicators.items():
            if isinstance(ind, EMA) or isinstance(ind, SMA) or isinstance(ind, RSI) or isinstance(ind, ATR) or isinstance(ind, VWAP):
                features[name] = ind.value
            elif isinstance(ind, MACD) or isinstance(ind, BollingerBands) or isinstance(ind, Supertrend) or isinstance(ind, ADX):
                res = ind.value
                if res:
                    for k, v in res._asdict().items():
                        features[f"{name}_{k}"] = v
            elif isinstance(ind, OpeningRange):
                if ind.is_complete:
                    features[f"{name}_high"] = ind.range_high
                    features[f"{name}_low"] = ind.range_low
                    features[f"{name}_mid"] = ind.range_midpoint
        return features

    def reset(self):
        for ind in self.indicators.values():
            if isinstance(ind, VWAP) or isinstance(ind, OpeningRange):
                ind.reset()
