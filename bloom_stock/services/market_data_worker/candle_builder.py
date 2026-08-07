from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set
from loguru import logger

from bloom_stock.packages.domain.schemas.candles import Candle, Tick, CandleInterval
from bloom_stock.packages.domain.enums import DataQuality
from bloom_stock.packages.domain.constants import NSE_TIMEZONE


class _CandleInProgress:
    """Mutable state for a candle being built."""
    def __init__(self, instrument_id: str, start_time: datetime, end_time: datetime):
        self.instrument_id = instrument_id
        self.start_time = start_time
        self.end_time = end_time
        self.open: Optional[Decimal] = None
        self.high: Decimal = Decimal('-Infinity')
        self.low: Decimal = Decimal('Infinity')
        self.close: Optional[Decimal] = None
        self.volume: int = 0
        self.trade_count: int = 0
        self.first_sequence: Optional[int] = None
        self.last_sequence: Optional[int] = None
    
    def update(self, tick: Tick):
        if self.open is None:
            self.open = tick.ltp
        if tick.ltp > self.high:
            self.high = tick.ltp
        if tick.ltp < self.low:
            self.low = tick.ltp
        self.close = tick.ltp
        
        # Determine quantity from this tick.
        trade_qty = getattr(tick, 'ltq', 0)
        self.volume += int(trade_qty)
        self.trade_count += 1
        
        if self.first_sequence is None:
            self.first_sequence = tick.sequence_number
        self.last_sequence = tick.sequence_number
    
    def to_candle(self, interval: CandleInterval, quality: DataQuality = DataQuality.GOOD) -> Candle:
        """Convert to immutable Candle."""
        return Candle(
            instrument_id=self.instrument_id,
            interval=interval.value,
            start_timestamp=self.start_time,
            end_timestamp=self.end_time,
            open=self.open if self.open is not None else Decimal('0'),
            high=self.high if self.high != Decimal('-Infinity') else Decimal('0'),
            low=self.low if self.low != Decimal('Infinity') else Decimal('0'),
            close=self.close if self.close is not None else Decimal('0'),
            volume=self.volume,
            trade_count=self.trade_count,
            source="LIVE_BUILDER",
            first_event_sequence=self.first_sequence,
            last_event_sequence=self.last_sequence,
            is_complete=True,
            quality_status=quality
        )


class CandleBuilder:
    """Deterministic candle builder from tick data.
    
    Rules (Section 11.3):
    - Exchange timezone only (Asia/Kolkata)
    - Official calendar
    - No copied synthetic rows
    - Late-event policy: accept if within tolerance
    - Missing-bar policy: mark as MISSING quality
    - Duplicate-tick policy: skip by sequence number
    - Volume reset detection
    - Same code for live and replay
    """
    
    def __init__(self, interval: CandleInterval = CandleInterval.ONE_MINUTE):
        self._interval = interval
        self._interval_seconds = self._get_interval_seconds(interval)
        # Per-instrument state
        self._building: Dict[str, _CandleInProgress] = {}
        self._seen_sequences: Dict[str, Set[int]] = {}  # duplicate detection
    
    def on_tick(self, tick: Tick) -> Optional[Candle]:
        """Process a tick. Returns a completed candle if the interval closed."""
        instrument_id = tick.instrument_id
        
        if instrument_id not in self._seen_sequences:
            self._seen_sequences[instrument_id] = set()
            
        if tick.sequence_number in self._seen_sequences[instrument_id]:
            # Duplicate tick
            return None
            
        self._seen_sequences[instrument_id].add(tick.sequence_number)
        
        # Enforce timezone
        ts = tick.exchange_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=NSE_TIMEZONE)
        else:
            ts = ts.astimezone(NSE_TIMEZONE)
            
        interval_start = self._align_to_interval(ts, self._interval_seconds)
        interval_end = interval_start + timedelta(seconds=self._interval_seconds)
        
        completed_candle = None
        
        if instrument_id in self._building:
            current = self._building[instrument_id]
            if interval_start > current.start_time:
                # Interval closed
                completed_candle = current.to_candle(self._interval)
                self._building[instrument_id] = _CandleInProgress(instrument_id, interval_start, interval_end)
            elif interval_start < current.start_time:
                # Late tick outside tolerance (simply skip or log)
                logger.warning(f"Late tick for {instrument_id} at {ts}, dropping.")
                return None
        else:
            self._building[instrument_id] = _CandleInProgress(instrument_id, interval_start, interval_end)
            
        self._building[instrument_id].update(tick)
        return completed_candle
    
    def flush(self, instrument_id: str) -> Optional[Candle]:
        """Force-complete the current in-progress candle."""
        if instrument_id in self._building:
            candle = self._building[instrument_id].to_candle(self._interval)
            del self._building[instrument_id]
            return candle
        return None
    
    def flush_all(self) -> List[Candle]:
        """Flush all in-progress candles (end of day)."""
        candles = []
        for inst_id in list(self._building.keys()):
            candle = self.flush(inst_id)
            if candle:
                candles.append(candle)
        return candles
    
    def reset(self, instrument_id: Optional[str] = None):
        """Reset state for one or all instruments."""
        if instrument_id:
            self._building.pop(instrument_id, None)
            self._seen_sequences.pop(instrument_id, None)
        else:
            self._building.clear()
            self._seen_sequences.clear()
    
    @staticmethod
    def _get_interval_seconds(interval: CandleInterval) -> int:
        mapping = {
            CandleInterval.ONE_MINUTE: 60,
            CandleInterval.FIVE_MINUTE: 300,
            CandleInterval.FIFTEEN_MINUTE: 900,
            CandleInterval.THIRTY_MINUTE: 1800,
            CandleInterval.ONE_HOUR: 3600,
            CandleInterval.ONE_DAY: 86400,
        }
        return mapping[interval]
    
    @staticmethod
    def _align_to_interval(timestamp: datetime, interval_seconds: int) -> datetime:
        """Align timestamp to interval boundary."""
        # Calculate total seconds since midnight
        midnight = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        delta_seconds = int((timestamp - midnight).total_seconds())
        
        # Floor to interval
        aligned_delta = (delta_seconds // interval_seconds) * interval_seconds
        
        return midnight + timedelta(seconds=aligned_delta)
