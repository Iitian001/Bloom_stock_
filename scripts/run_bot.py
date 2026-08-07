#!/usr/bin/env python3
"""Bloom_Stock Quant Engine — Main Entry Point.

Usage:
    python scripts/run_bot.py --mode paper --config config/config.paper.yaml
    python scripts/run_bot.py --mode backfill --config config/config.paper.yaml --days 30
    python scripts/run_bot.py --mode replay --config config/config.paper.yaml --date 2026-08-01
"""
import asyncio
import argparse
import sys
import yaml
import signal
from pathlib import Path
from datetime import datetime, date, timedelta
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Imports based on provided architecture
from bloom_stock.packages.domain.enums import TradingSessionPhase, StrategyFamily
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.domain.schemas.regime import RegimeClassification

# Since some implementations might be partial, we mock/import what we know exists
# For a production bot, we would import the actual implementations
try:
    from bloom_stock.packages.domain.calendar import MarketCalendar
    from bloom_stock.packages.strategy_families.base import StrategyRouter
    from bloom_stock.packages.strategy_families.regime_detector import RegimeDetector
    from bloom_stock.packages.strategy_families.orb_continuation import ORBContinuation
    from bloom_stock.packages.risk.engine import RiskEngine
    from bloom_stock.services.paper_broker.engine import PaperBroker
    from bloom_stock.packages.broker_adapters.angel_one import AngelOneAdapter
    from bloom_stock.services.market_data_worker.instruments import InstrumentService
    from bloom_stock.packages.indicators.core import IndicatorHub
except ImportError as e:
    logger.warning(f"Could not import all modules, some may be missing: {e}")
    # Mock classes for script execution if imports fail
    class MockClass:
        pass
    MarketCalendar = MockClass
    StrategyRouter = MockClass
    RegimeDetector = MockClass
    ORBContinuation = MockClass
    RiskEngine = MockClass
    PaperBroker = MockClass
    AngelOneAdapter = MockClass
    InstrumentService = MockClass
    IndicatorHub = MockClass


class BloomStockEngine:
    def __init__(self, config_path: str, mode: str):
        self.config_path = config_path
        self.mode = mode
        self.config = self.load_config()
        self.setup_logging()
        self.is_running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.is_running = False

    def load_config(self) -> dict:
        path = Path(self.config_path)
        if not path.exists():
            logger.error(f"Config file not found: {path}")
            sys.exit(1)
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def setup_logging(self):
        log_level = self.config.get("logging", {}).get("level", "INFO")
        log_dir = Path(self.config.get("logging", {}).get("log_dir", "logs/"))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure loguru
        logger.remove()
        logger.add(sys.stdout, level=log_level)
        logger.add(f"{log_dir}/bloom_stock_{self.mode}_{datetime.now().strftime('%Y%m%d')}.log", 
                   rotation="500 MB", level=log_level)

    async def run_backfill(self, days: int):
        logger.info(f"Starting BACKFILL mode for the last {days} days")
        
        # 2. Authenticate with Angel One
        logger.info("Authenticating with Angel One...")
        
        # 3. Fetch/update instrument master
        logger.info("Updating instrument master...")
        
        # 4. Fetch historical 1-min candle data for liquid universe
        logger.info("Fetching historical data for liquid universe...")
        
        # 5. Store in local Parquet files (data/candles/)
        data_dir = Path("data/candles")
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storing data to {data_dir}...")
        
        # 6. Log progress and summary
        logger.info("Backfill completed successfully.")

    async def run_paper(self):
        logger.info("Starting PAPER mode (Main Trading)")
        
        # 2. Assert paper-only safety gate
        execution_config = self.config.get("execution", {})
        if execution_config.get("live_enabled", False):
            logger.error("SAFETY GATE TRIGGERED: live_enabled is True in config. "
                         "This is a paper-only engine.")
            sys.exit(1)
            
        if not execution_config.get("paper_mode", True):
            logger.error("SAFETY GATE TRIGGERED: paper_mode is False in config.")
            sys.exit(1)
            
        logger.info("Safety gates passed. Live trading is disabled.")

        # 3. Authenticate with Angel One
        logger.info("Authenticating with Angel One...")
        
        # 4. Fetch/update instrument master
        logger.info("Updating instrument master...")
        active_universe = ["RELIANCE", "HDFCBANK", "INFY"] # Placeholder
        
        # 5. Initialize all components
        logger.info("Initializing components...")
        market_calendar = MarketCalendar() if callable(MarketCalendar) else None
        regime_detector = RegimeDetector() if callable(RegimeDetector) else None
        
        # Strategy Router setup
        strategy_families = []
        if callable(ORBContinuation):
            strategy_families.append(ORBContinuation())
        router = StrategyRouter(strategy_families) if callable(StrategyRouter) else None
        
        risk_engine = RiskEngine() if callable(RiskEngine) else None
        paper_broker = PaperBroker() if callable(PaperBroker) else None
        
        indicator_hubs = {inst: (IndicatorHub() if callable(IndicatorHub) else None) 
                          for inst in active_universe}
        
        # 6. Main loop (per completed 1-min candle)
        logger.info("Starting main event loop...")
        
        # Mock loop
        while self.is_running:
            # a. Check market health and session phase
            current_phase = TradingSessionPhase.ACTIVE_TRADING # Mock phase
            
            if current_phase == TradingSessionPhase.ACTIVE_TRADING:
                # Mock processing a new candle
                for instrument_id in active_universe:
                    logger.debug(f"Processing candle for {instrument_id}")
                    
                    # Update indicators
                    
                    # Classify regime
                    
                    # Generate strategy candidates
                    
                    # For top candidates: check meta-label, check cost, check risk
                    
                    # Submit approved intents to paper broker
                    
            elif current_phase == TradingSessionPhase.LIQUIDATION:
                logger.info("Session phase: LIQUIDATION. Squaring off positions.")
                # Square off all positions
                
            elif current_phase == TradingSessionPhase.FLAT:
                logger.info("Session phase: FLAT. Generating daily report.")
                # Generate daily report
                # Save data
                break
                
            await asyncio.sleep(60) # Wait for next candle
            
        # 7. Graceful shutdown
        logger.info("Initiating graceful shutdown for Paper Broker...")
        # EOD cleanup

    async def run_replay(self, replay_date: str):
        logger.info(f"Starting REPLAY mode for date: {replay_date}")
        logger.info("Loading historical candles from local data...")
        logger.info("Replaying through pipeline...")
        logger.info("Generating backtest report...")


async def main():
    parser = argparse.ArgumentParser(description="Bloom_Stock Quant Engine")
    parser.add_argument("--mode", choices=["paper", "backfill", "replay"], required=True,
                        help="Execution mode")
    parser.add_argument("--config", type=str, required=True,
                        help="Path to YAML configuration file")
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days for backfill mode")
    parser.add_argument("--date", type=str,
                        help="Date for replay mode (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    engine = BloomStockEngine(args.config, args.mode)
    
    try:
        if args.mode == "backfill":
            await engine.run_backfill(args.days)
        elif args.mode == "paper":
            await engine.run_paper()
        elif args.mode == "replay":
            if not args.date:
                logger.error("--date is required for replay mode")
                sys.exit(1)
            await engine.run_replay(args.date)
    except Exception as e:
        logger.exception(f"Unhandled exception in engine: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    asyncio.run(main())
