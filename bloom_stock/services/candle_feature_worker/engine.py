import asyncio
from typing import Dict, List, Any
from collections import defaultdict
from loguru import logger

from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.features.builder import FeatureBuilder
from bloom_stock.packages.domain.schemas.regime import RegimeClassification

class CrossSectionalEngine:
    """Computes features that require data from the entire universe of stocks.
    Example: Index-relative returns, breadth, sector momentum.
    """
    
    def __init__(self):
        self._latest_returns: Dict[str, float] = {}
        self._index_return: float = 0.0
        self._prev_closes: Dict[str, float] = {}
        
    def update_snapshot(self, candles: List[Candle]):
        """Update internal state with the latest 1-min snapshot of all active stocks."""
        returns = []
        
        for candle in candles:
            inst_id = str(candle.instrument_id)
            close = float(candle.close)
            
            if inst_id in self._prev_closes:
                prev_close = self._prev_closes[inst_id]
                if prev_close > 0:
                    ret = (close - prev_close) / prev_close
                    self._latest_returns[inst_id] = ret
                    returns.append(ret)
            else:
                self._latest_returns[inst_id] = 0.0
                
            self._prev_closes[inst_id] = close
            
        if returns:
            self._index_return = sum(returns) / len(returns)
        else:
            self._index_return = 0.0
        
    def get_features(self, instrument_id: str) -> Dict[str, float]:
        """Return cross-sectional features for a specific instrument."""
        inst_return = self._latest_returns.get(instrument_id, 0.0)
        idx_rel_return = inst_return - self._index_return
        
        # Mocking other cross sectional features for now
        return {
            "index_relative_return": idx_rel_return,
            "sector_relative_return": idx_rel_return,
            "volume_zscore": 0.0,
        }

class FeatureWorker:
    """Coordinates IndicatorHubs and CrossSectionalEngine to produce final ML features."""
    
    def __init__(self, indicator_hubs: dict):
        self.hubs = indicator_hubs  # Dict[instrument_id, IndicatorHub]
        self.cross_sectional = CrossSectionalEngine()
        
    def process_bar(self, timestamp: Any, candles: List[Candle], regime: RegimeClassification) -> Dict[str, Dict[str, float]]:
        """Process a 1-minute bar for all stocks.
        Returns: Dict[instrument_id, feature_vector]
        """
        # 1. Update cross-sectional engine
        self.cross_sectional.update_snapshot(candles)
        
        features_batch = {}
        
        for candle in candles:
            inst_id = str(candle.instrument_id)
            if inst_id not in self.hubs:
                logger.warning(f"No IndicatorHub found for {inst_id}")
                continue
                
            hub = self.hubs[inst_id]
            
            # 2. Get indicator features
            indicator_features = hub.update_candle(candle)
            
            # 3. Get cross-sectional features
            cs_features = self.cross_sectional.get_features(inst_id)
            
            # 4. Build final features
            ml_features = FeatureBuilder.build_features(
                instrument_id=inst_id,
                candle=candle,
                indicator_features=indicator_features,
                cross_sectional_data=cs_features,
                regime=regime
            )
            features_batch[inst_id] = ml_features
            
        return features_batch
