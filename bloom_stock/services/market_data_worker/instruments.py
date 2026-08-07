import json
import httpx
import polars as pl
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from loguru import logger

from bloom_stock.packages.domain.schemas.instruments import Instrument, InstrumentFilter
from bloom_stock.packages.domain.enums import Exchange, Segment
from bloom_stock.packages.domain.constants import INSTRUMENT_MASTER_URL


class InstrumentService:
    """Manages NSE/BSE instrument master data.
    
    Responsibilities:
    - Download daily instrument master from Angel One
    - Parse and normalize to internal Instrument schema
    - Filter liquid universe (Tier 1)
    - Provide fast lookups: symbol -> token, token -> symbol
    - Cache locally with date-stamped files
    """
    
    def __init__(self, cache_dir: Path = Path('data/instruments')):
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._instruments: dict[str, Instrument] = {}  # token -> Instrument
        self._symbol_to_token: dict[str, str] = {}  # symbol -> token
        self._df: Optional[pl.DataFrame] = None
    
    async def fetch_and_cache(self) -> int:
        """Download instrument master, parse, cache. Returns count of instruments."""
        logger.info(f"Downloading instrument master from {INSTRUMENT_MASTER_URL}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(INSTRUMENT_MASTER_URL, timeout=30.0)
            response.raise_for_status()
            raw_data = response.json()
            
        logger.info(f"Downloaded {len(raw_data)} raw instruments. Parsing and filtering...")
        
        parsed_instruments = []
        for item in raw_data:
            if item.get('exch_seg') == 'NSE' and item.get('instrumenttype') == 'EQ':
                try:
                    tick_size_raw = item.get('tick_size', '0.05')
                    # Angel one specifies tick size in string format often
                    tick_size = Decimal(str(tick_size_raw))
                    
                    token = item.get('token')
                    symbol = item.get('symbol')
                    
                    instrument = Instrument(
                        bloom_id=f"NSE_{symbol}",
                        exchange=Exchange.NSE,
                        symbol=symbol,
                        isin=item.get('name', ''),  # Sometimes name holds ISIN or symbol text
                        broker_token=token,
                        segment=Segment.EQUITY,
                        tick_size=tick_size,
                        lot_size=int(item.get('lotsize', 1)),
                        is_active=True
                    )
                    parsed_instruments.append(instrument)
                    self._instruments[token] = instrument
                    self._symbol_to_token[symbol] = token
                except (ValueError, TypeError) as e:
                    logger.debug(f"Skipping instrument {item.get('symbol')} due to parsing error: {e}")
                    
        # Convert to polars
        if parsed_instruments:
            # Using model_dump to extract dictionary
            dicts = [inst.model_dump() for inst in parsed_instruments]
            self._df = pl.DataFrame(dicts)
            
            # Save parquet
            today_str = date.today().isoformat()
            cache_path = self._cache_dir / f"instruments_{today_str}.parquet"
            self._df.write_parquet(cache_path)
            logger.info(f"Cached {len(parsed_instruments)} NSE equity instruments to {cache_path}")
        
        return len(self._instruments)
    
    def load_cached(self, for_date: Optional[date] = None) -> bool:
        """Load from local cache. Returns True if successful."""
        target_date = for_date or date.today()
        cache_path = self._cache_dir / f"instruments_{target_date.isoformat()}.parquet"
        
        if not cache_path.exists():
            logger.warning(f"Cache file not found: {cache_path}")
            return False
            
        try:
            self._df = pl.read_parquet(cache_path)
            
            self._instruments.clear()
            self._symbol_to_token.clear()
            
            for row in self._df.to_dicts():
                # Reconstruct Instrument
                inst = Instrument(**row)
                self._instruments[inst.broker_token] = inst
                self._symbol_to_token[inst.symbol] = inst.broker_token
                
            logger.info(f"Loaded {len(self._instruments)} instruments from cache {cache_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load cache from {cache_path}: {e}")
            return False
    
    def get_liquid_universe(self, filter_config: InstrumentFilter) -> list[Instrument]:
        """Filter instruments by liquidity criteria (Tier 1)."""
        if self._df is None:
            return []
            
        # In a real setup, we would join with historical volume/price data. 
        # Here we just apply basic static filters available on Instrument.
        liquid = []
        for inst in self._instruments.values():
            if filter_config.min_price and inst.tick_size > 0: 
                # This is a placeholder since current price isn't in master.
                pass
            
            # Simple active check and restriction check
            if not inst.is_active:
                continue
                
            has_excluded_restriction = any(
                r in filter_config.excluded_restrictions for r in inst.restrictions
            )
            if has_excluded_restriction:
                continue
                
            liquid.append(inst)
            
        return liquid
    
    def get_nse_equity(self) -> list[Instrument]:
        """Get all NSE cash equity instruments."""
        return [
            inst for inst in self._instruments.values() 
            if inst.exchange == Exchange.NSE and inst.segment == Segment.EQUITY
        ]
    
    def token_to_instrument(self, token: str) -> Optional[Instrument]:
        return self._instruments.get(token)
    
    def symbol_to_instrument(self, symbol: str) -> Optional[Instrument]:
        token = self._symbol_to_token.get(symbol)
        return self._instruments.get(token) if token else None
    
    def symbol_to_token(self, symbol: str) -> Optional[str]:
        return self._symbol_to_token.get(symbol)
    
    @property
    def count(self) -> int:
        return len(self._instruments)
    
    @property
    def dataframe(self) -> Optional[pl.DataFrame]:
        return self._df
