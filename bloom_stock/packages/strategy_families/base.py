from abc import ABC, abstractmethod
from typing import Optional
from bloom_stock.packages.domain.schemas.signals import StrategyCandidate
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.schemas.regime import RegimeClassification
from bloom_stock.packages.domain.enums import StrategyFamily, SignalDirection


class StrategyFamilyBase(ABC):
    """Abstract base class for all strategy families.
    
    Each strategy family:
    - Has a unique StrategyFamily enum value
    - Operates on a specific set of regime conditions
    - Generates StrategyCandidate objects when conditions are met
    - Has configurable parameters loaded from config
    - Has skip conditions that prevent trading
    - Tracks its own state per instrument
    """
    
    @property
    @abstractmethod
    def family(self) -> StrategyFamily:
        """The strategy family enum this implementation belongs to."""
        ...
    
    @property
    @abstractmethod
    def compatible_regimes(self) -> list[str]:
        """List of RegimeType values this family operates under."""
        ...
    
    @abstractmethod
    def is_compatible(self, regime: RegimeClassification) -> bool:
        """Check if current regime is compatible with this family."""
        ...
    
    @abstractmethod
    def on_candle(
        self,
        instrument_id: str,
        candle: Candle,
        features: dict,
        regime: RegimeClassification,
    ) -> Optional[StrategyCandidate]:
        """Process a new candle and optionally generate a trade candidate.
        
        Args:
            instrument_id: The Bloom instrument ID
            candle: The completed 1-min or 5-min candle
            features: Pre-computed indicator features from IndicatorHub
            regime: Current regime classification
            
        Returns:
            StrategyCandidate if conditions are met, None otherwise
        """
        ...
    
    @abstractmethod
    def reset_session(self, instrument_id: str):
        """Reset state for a new trading session."""
        ...
    
    @abstractmethod
    def get_skip_reasons(self, instrument_id: str) -> list[str]:
        """Return list of reasons this family is currently skipping an instrument."""
        ...


class StrategyRouter:
    """Routes candles to the appropriate strategy family based on regime.
    
    Only ONE family should control a stock at a time.
    The router selects the best family based on regime and context.
    """
    
    def __init__(self, families: list[StrategyFamilyBase]):
        self._families = {f.family: f for f in families}
    
    def generate_candidates(
        self,
        instrument_id: str,
        candle: Candle,
        features: dict,
        regime: RegimeClassification,
    ) -> list[StrategyCandidate]:
        """Generate candidates from all compatible families.
        Returns at most one candidate per family."""
        candidates = []
        for family in self._families.values():
            if family.is_compatible(regime):
                candidate = family.on_candle(instrument_id, candle, features, regime)
                if candidate is not None:
                    candidates.append(candidate)
        return candidates
    
    def reset_all_sessions(self, instrument_id: str):
        for family in self._families.values():
            family.reset_session(instrument_id)
