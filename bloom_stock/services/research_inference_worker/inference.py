from typing import List, Dict, Optional, Any
from loguru import logger

from bloom_stock.packages.domain.schemas.signals import StrategyCandidate
from bloom_stock.packages.domain.schemas.regime import RegimeClassification
from bloom_stock.packages.domain.enums import StrategyFamily, RegimeType

# These will be imported when their modules are implemented
try:
    from bloom_stock.packages.ml.ranker import MLRanker
except ImportError:
    MLRanker = Any

try:
    from bloom_stock.packages.ml.meta_labeler import MetaLabeler
except ImportError:
    MetaLabeler = Any


class ExecutionPolicy:
    """Configuration for when to accept an ML-scored candidate."""
    
    def __init__(self) -> None:
        # Base probability thresholds per regime (e.g., higher bar in high vol)
        self.regime_thresholds: Dict[RegimeType, float] = {
            RegimeType.TREND_UP: 0.55,
            RegimeType.TREND_DOWN: 0.55,
            RegimeType.RANGE_LOW_VOL: 0.60,
            RegimeType.HIGH_VOLATILITY: 0.65,
            RegimeType.DISORDERED_NO_TRADE: 1.0 # Never trade
        }
        
    def get_threshold(self, regime: RegimeClassification, family: StrategyFamily) -> float:
        """Return the minimum required probability to execute a trade."""
        base_threshold = self.regime_thresholds.get(regime.regime, 0.60)
        
        # Mean Reversion in trending markets might need a higher threshold
        if family == StrategyFamily.MEAN_REVERSION and regime.regime in (RegimeType.TREND_UP, RegimeType.TREND_DOWN):
            base_threshold += 0.15
            
        # Momentum in ranging markets might need a higher threshold
        if family == StrategyFamily.MOMENTUM and regime.regime == RegimeType.RANGE_LOW_VOL:
            base_threshold += 0.10
            
        # Cap at 1.0
        return min(base_threshold, 1.0)


class InferenceGateway:
    """Central gateway that scores and filters strategy candidates using ML models."""
    
    def __init__(self, ranker: MLRanker, meta_labeler: MetaLabeler, policy: ExecutionPolicy) -> None:
        self.ranker = ranker
        self.meta_labeler = meta_labeler
        self.policy = policy
        
    def process_candidates(
        self, 
        candidates: List[StrategyCandidate], 
        features: Dict[str, Dict[str, float]], 
        regime: RegimeClassification,
        top_k: int = 10
    ) -> List[StrategyCandidate]:
        """Rank, filter, and approve candidates for execution.
        
        Args:
            candidates: Raw candidates from StrategyRouter
            features: ML feature dictionary for all instruments
            regime: Current market regime
            top_k: Maximum number of candidates to process
            
        Returns:
            Filtered list of approved candidates
        """
        if not candidates:
            return []
            
        # Rank candidates
        ranked_candidates = self.ranker.rank(candidates, features)
        
        # Take the top top_k candidates
        top_candidates = ranked_candidates[:top_k]
        
        approved_candidates: List[StrategyCandidate] = []
        
        for candidate in top_candidates:
            # Type is StrategyCandidate or RankedCandidate depending on ranker output.
            instrument_id = str(candidate.instrument_id)
            
            # Extract feature vector
            feature_vector = features.get(instrument_id, {})
            
            # Get meta-labeling result
            meta_result = self.meta_labeler.predict(candidate, feature_vector)
            
            # Determine threshold based on regime and strategy family
            threshold = self.policy.get_threshold(regime, candidate.family)
            
            if meta_result.take_probability >= threshold:
                approved_candidates.append(candidate)
                logger.info(
                    f"Candidate APPROVED: {instrument_id} | Family: {candidate.family.value} | "
                    f"Prob: {meta_result.take_probability:.4f} >= Threshold: {threshold:.4f}"
                )
            else:
                logger.info(
                    f"Candidate REJECTED: {instrument_id} | Family: {candidate.family.value} | "
                    f"Prob: {meta_result.take_probability:.4f} < Threshold: {threshold:.4f}"
                )
                
        return approved_candidates
