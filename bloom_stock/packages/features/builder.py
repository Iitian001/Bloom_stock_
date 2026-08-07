import numpy as np
from typing import Dict, Any, List
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.schemas.regime import RegimeClassification

class FeatureBuilder:
    """Transforms raw IndicatorHub output and cross-sectional data into a flat ML feature vector."""
    
    @staticmethod
    def build_features(
        instrument_id: str,
        candle: Candle,
        indicator_features: Dict[str, Any],
        cross_sectional_data: Dict[str, float],
        regime: RegimeClassification
    ) -> Dict[str, float]:
        """Build a flat dictionary of numerical features for ML."""
        features: Dict[str, float] = {}
        
        # 1. Time Features
        dt = candle.start_timestamp
        # Assuming typical trading start is 09:15
        minute_from_open = (dt.hour * 60 + dt.minute) - (9 * 60 + 15)
        features["minute_from_open"] = float(minute_from_open)
        features["day_of_week"] = float(dt.weekday())
        
        # 2. Volatility
        close_price = float(candle.close)
        vwap = indicator_features.get("VWAP")
        atr = indicator_features.get("ATR")
        
        if vwap is not None and atr is not None and atr > 0:
            features["distance_from_vwap_atr"] = (close_price - float(vwap)) / float(atr)
        else:
            features["distance_from_vwap_atr"] = 0.0
            
        tr = float(candle.high - candle.low)
        if atr is not None and atr > 0:
            features["true_range_normalized"] = tr / float(atr)
        else:
            features["true_range_normalized"] = 0.0
            
        # 3. Liquidity
        features["volume_zscore"] = float(cross_sectional_data.get("volume_zscore", 0.0))
        
        # 4. Strategy Features
        # Extract features safely
        features["rsi"] = float(indicator_features.get("RSI") or 0.0)
        features["macd_hist"] = float(indicator_features.get("MACD_histogram") or 0.0)
        features["supertrend_direction"] = float(indicator_features.get("Supertrend_direction") or 0.0)
        features["bb_percent_b"] = float(indicator_features.get("BollingerBands_percent_b") or 0.0)
        
        # 5. Cross-sectional
        features["sector_relative_return"] = float(cross_sectional_data.get("sector_relative_return", 0.0))
        features["index_relative_return"] = float(cross_sectional_data.get("index_relative_return", 0.0))
        
        # Include regime probabilities if available
        if regime and regime.probabilities:
            for regime_type, prob in regime.probabilities.items():
                # Assuming regime_type is an Enum, we take its value or name
                features[f"regime_prob_{regime_type.value}"] = float(prob)
                
        return features
