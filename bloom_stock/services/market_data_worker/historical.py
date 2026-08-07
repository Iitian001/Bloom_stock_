import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Callable
from loguru import logger

from bloom_stock.packages.domain.schemas.candles import Candle, CandleInterval
from bloom_stock.packages.domain.enums import DataQuality
from bloom_stock.packages.broker_adapters.base import BrokerAdapter


class HistoricalDataFetcher:
    """Fetches historical OHLCV candle data from broker API.
    
    Rate-limit aware:
    - 3 requests/second (configurable)
    - 180 requests/minute (configurable)
    - Max 500 candles per request
    - Automatic chunking for large date ranges
    - Exponential backoff on errors
    """
    
    def __init__(
        self,
        broker: BrokerAdapter,
        requests_per_second: int = 3,
        requests_per_minute: int = 180,
    ):
        self._broker = broker
        self._rps = requests_per_second
        self._rpm = requests_per_minute
        self._semaphore = asyncio.Semaphore(requests_per_second)
        self._minute_counter = 0
        self._minute_reset_time = datetime.now()
        
    async def _throttle(self):
        """Enforce rate limits."""
        now = datetime.now()
        if (now - self._minute_reset_time).total_seconds() > 60:
            self._minute_counter = 0
            self._minute_reset_time = now
            
        if self._minute_counter >= self._rpm:
            sleep_time = 60.0 - (now - self._minute_reset_time).total_seconds()
            if sleep_time > 0:
                logger.debug(f"Minute rate limit reached. Sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
            self._minute_counter = 0
            self._minute_reset_time = datetime.now()
            
        self._minute_counter += 1
        
        # We also enforce RPS using the semaphore in _fetch_single_chunk
        await asyncio.sleep(1.0 / self._rps)
    
    async def _fetch_single_chunk(
        self, symbol_token: str, exchange: str, interval: CandleInterval, from_dt: datetime, to_dt: datetime
    ) -> List[Dict]:
        """Make a single API call within rate limits."""
        async with self._semaphore:
            await self._throttle()
            max_retries = 3
            base_backoff = 2.0
            
            for attempt in range(max_retries):
                try:
                    # Map domain interval to broker specific string (e.g., ONE_MINUTE)
                    broker_interval = "ONE_MINUTE" if interval == CandleInterval.ONE_MINUTE else "FIVE_MINUTE"
                    
                    data = await self._broker.get_historical_candles(
                        symbol_token=symbol_token,
                        exchange=exchange,
                        interval=broker_interval,
                        from_dt=from_dt,
                        to_dt=to_dt
                    )
                    return data
                except Exception as e:
                    logger.warning(f"Error fetching data chunk (attempt {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(base_backoff ** attempt)
                    else:
                        logger.error(f"Failed to fetch chunk after {max_retries} retries.")
                        return []
        return []
        
    async def fetch_candles(
        self,
        symbol_token: str,
        exchange: str,
        interval: CandleInterval,
        from_dt: datetime,
        to_dt: datetime,
    ) -> List[Candle]:
        """Fetch candles for a single instrument.
        Automatically chunks if date range exceeds 500 candle limit."""
        
        # Max 500 candles per request.
        # For 1-minute interval, a day is 375 minutes, so 1 day per chunk is safe.
        interval_td = timedelta(days=1)
        
        all_candles = []
        current_from = from_dt
        
        while current_from < to_dt:
            current_to = min(current_from + interval_td, to_dt)
            raw_data = await self._fetch_single_chunk(
                symbol_token, exchange, interval, current_from, current_to
            )
            
            for row in raw_data:
                try:
                    dt = datetime.fromisoformat(row[0]) if isinstance(row[0], str) else row[0]
                    candle = Candle(
                        instrument_id=symbol_token, # Using token as id
                        interval=interval.value,
                        start_timestamp=dt,
                        end_timestamp=dt + timedelta(minutes=1),
                        open=Decimal(str(row[1])),
                        high=Decimal(str(row[2])),
                        low=Decimal(str(row[3])),
                        close=Decimal(str(row[4])),
                        volume=int(row[5]),
                        source="BROKER_HISTORICAL",
                        quality_status=DataQuality.GOOD,
                        is_complete=True
                    )
                    all_candles.append(candle)
                except (IndexError, ValueError, TypeError) as e:
                    logger.error(f"Error parsing historical candle row {row}: {e}")
                    
            current_from = current_to + timedelta(seconds=1) # Advance to avoid overlap
            
        return all_candles
    
    async def fetch_day(
        self,
        symbol_token: str,
        exchange: str,
        trading_date: date,
    ) -> List[Candle]:
        """Fetch all 1-minute candles for one trading day (9:15-15:30)."""
        from_dt = datetime.combine(trading_date, datetime.min.time().replace(hour=9, minute=15))
        to_dt = datetime.combine(trading_date, datetime.min.time().replace(hour=15, minute=30))
        return await self.fetch_candles(
            symbol_token, exchange, CandleInterval.ONE_MINUTE, from_dt, to_dt
        )
    
    async def backfill_multiple(
        self,
        instruments: List[Tuple[str, str]],  # (token, exchange) pairs
        from_date: date,
        to_date: date,
        interval: CandleInterval = CandleInterval.ONE_MINUTE,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, List[Candle]]:
        """Backfill historical data for multiple instruments.
        Rate-limit aware batching."""
        results = {}
        total = len(instruments)
        
        from_dt = datetime.combine(from_date, datetime.min.time())
        to_dt = datetime.combine(to_date, datetime.max.time())
        
        logger.info(f"Starting backfill for {total} instruments from {from_date} to {to_date}")
        
        for idx, (token, exchange) in enumerate(instruments, 1):
            candles = await self.fetch_candles(token, exchange, interval, from_dt, to_dt)
            results[token] = candles
            
            if progress_callback:
                progress_callback(idx, total)
                
            logger.info(f"Backfilled {len(candles)} candles for {token} ({idx}/{total})")
            
        return results
