from typing import Dict, Any
from loguru import logger

class LiveTradingDisabledError(Exception):
    """Exception raised when live trading is attempted but disabled."""
    pass

class SafetyGate:
    """
    Safety gate to enforce paper trading mode and prevent accidental live orders.
    """
    def __init__(self, config: Dict[str, Any]):
        self.execution_config = config.get("execution", {})
        self.live_enabled = self.execution_config.get("live_enabled", False)
        self.paper_mode = self.execution_config.get("paper_mode", True)
        self.env = config.get("environment", "paper")
        
        logger.info(f"SafetyGate initialized: Env={self.env}, Live={self.live_enabled}, Paper={self.paper_mode}")
        
    def assert_paper_only(self) -> None:
        """
        Assert that the system is operating in paper mode.
        Raises LiveTradingDisabledError if live mode is attempted.
        """
        # We explicitly enforce paper mode in v1
        if self.env != "paper":
            logger.critical(f"Safety Check Failed: Environment is not 'paper', it is '{self.env}'.")
            raise LiveTradingDisabledError("Environment must be 'paper'")
            
        if self.live_enabled:
            logger.critical("Safety Check Failed: live_enabled is True.")
            raise LiveTradingDisabledError("Live trading is explicitly disabled in the codebase.")
            
        if not self.paper_mode:
            logger.critical("Safety Check Failed: paper_mode is False.")
            raise LiveTradingDisabledError("Paper mode must be enabled.")
            
        logger.debug("Safety check passed: Paper mode verified.")
        
    def can_place_live_order(self) -> bool:
        """
        Check if a live order can be placed.
        Always returns False in v1.
        """
        logger.info("Checking can_place_live_order...")
        
        try:
            self.assert_paper_only()
            # Even if assertions pass, we return False for v1 to guarantee no live execution
            logger.info("Safety check passed, but live orders are always disabled in v1.")
            return False
            
        except LiveTradingDisabledError as e:
            logger.warning(f"Safety gate blocked live order check: {e}")
            return False
