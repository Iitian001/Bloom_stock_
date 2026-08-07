"""Deterministic Regime Classifier.

Classifies market state into one of 5 regimes per Sections 6.1 and 6.2 of the master plan.
"""

from typing import Dict, Optional
from datetime import datetime
from pydantic import BaseModel

from bloom_stock.packages.domain.enums import RegimeType
from bloom_stock.packages.domain.schemas.regime import RegimeClassification, RegimeFeatures


class RegimeDetectorConfig(BaseModel):
    min_confidence_threshold: float = 0.4
    vix_trend_up_max: float = 20.0
    vix_trend_down_max: float = 25.0
    vix_range_max: float = 18.0
    vix_high_vol_min: float = 22.0
    vix_disordered_min: float = 30.0


class RegimeDetector:
    """Deterministic regime classifier.
    
    Classifies market state into one of 5 regimes:
    - TREND_UP: Nifty above VWAP, positive breadth, VIX stable
    - TREND_DOWN: Nifty below VWAP, negative breadth, VIX rising
    - RANGE_LOW_VOL: Low ADX, narrow range, stable VIX
    - HIGH_VOLATILITY: High VIX, wide ranges, unclear direction
    - DISORDERED_NO_TRADE: Feed issues, extreme volatility, system problems
    """
    
    def __init__(self, config: Optional[RegimeDetectorConfig] = None):
        self._config = config or RegimeDetectorConfig()
        self.version = "1.0.0"
        
    def classify(self, features: RegimeFeatures) -> RegimeClassification:
        """Classify current market regime from features.
        Returns regime with probability estimates."""
        
        scores: Dict[RegimeType, float] = {
            RegimeType.TREND_UP: 0.0,
            RegimeType.TREND_DOWN: 0.0,
            RegimeType.RANGE_LOW_VOL: 0.0,
            RegimeType.HIGH_VOLATILITY: 0.0,
            RegimeType.DISORDERED_NO_TRADE: 0.0
        }
        
        # Hard limits for DISORDERED_NO_TRADE
        if float(features.feed_health_score) < 0.5 or float(features.india_vix) > self._config.vix_disordered_min:
            scores[RegimeType.DISORDERED_NO_TRADE] = 1.0
        else:
            # TREND_UP Rules
            if (float(features.nifty_return) > 0 and 
                float(features.pct_above_vwap) > 0.55 and 
                float(features.trend_strength) > 0.3 and 
                float(features.india_vix) < self._config.vix_trend_up_max):
                scores[RegimeType.TREND_UP] += 0.8
                
            # TREND_DOWN Rules
            if (float(features.nifty_return) < 0 and 
                float(features.pct_above_vwap) < 0.45 and 
                float(features.trend_strength) > 0.3 and 
                float(features.india_vix) < self._config.vix_trend_down_max):
                scores[RegimeType.TREND_DOWN] += 0.8
                
            # RANGE_LOW_VOL Rules
            if (float(features.trend_strength) < 0.2 and 
                float(features.dispersion) < 0.5 and 
                float(features.india_vix) < self._config.vix_range_max):
                scores[RegimeType.RANGE_LOW_VOL] += 0.8
                
            # HIGH_VOLATILITY Rules
            if (float(features.india_vix) > self._config.vix_high_vol_min or 
                float(features.dispersion) > 1.0):
                scores[RegimeType.HIGH_VOLATILITY] += 0.8
                
        # Normalize scores to probabilities
        total_score = sum(scores.values())
        if total_score > 0:
            probs = {k: v / total_score for k, v in scores.items()}
        else:
            probs = {k: 0.2 for k in scores}
            
        # Select best regime
        best_regime = max(probs.items(), key=lambda x: x[1])
        selected_regime, confidence = best_regime
        
        if confidence < self._config.min_confidence_threshold:
            selected_regime = RegimeType.DISORDERED_NO_TRADE
            
        return RegimeClassification(
            regime=selected_regime,
            probabilities=probs,
            model_version=self.version,
            timestamp=datetime.utcnow(),
            confidence=confidence
        )
