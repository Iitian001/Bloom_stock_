# Bloom_Stock Quant Engine

**Production-grade Intraday Quant Trading Engine for NSE**

Bloom_Stock is an event-driven, fully automated quantitative trading engine designed for the National Stock Exchange of India (NSE). It focuses on rigorous risk management, statistically validated intraday strategies, and strict state machine transitions.

> **DISCLAIMER:** This software is for educational and research purposes only. The current implementation operates in a paper-trading sandbox by default. Live trading involves significant financial risk. The authors are not responsible for any financial losses incurred from using this software.

## Architecture Overview

```text
================================================================================
|                              BLOOM_STOCK ENGINE                              |
================================================================================
|                                                                              |
|  [Data Workers]      [Core Pipeline]                [Execution & Risk]       |
|                                                                              |
|  Angel One WS  --->  CandleBuilder    --->          RiskEngine               |
|       |                   |                             |                    |
|       v                   v                             v                    |
|  Data Quality  --->  IndicatorHub     --->        PaperBroker / Gateway      |
|                       |        |                        |                    |
|                       v        v                        v                    |
|                 RegimeModel  StrategyRouter         Ledger / DB              |
|                                                                              |
================================================================================
```

## Quick Start

### Prerequisites
- Python 3.11+
- Poetry or `pip` for dependency management
- Redis (optional, for caching)
- PostgreSQL (optional, for persistence)
- Angel One Developer Account

### Installation

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd eager-rutherford
   ```

2. Install dependencies (assuming a virtual environment):
   ```bash
   pip install -r requirements.txt
   ```

3. Setup Configuration:
   ```bash
   cp config/config.example.yaml config/config.paper.yaml
   # Edit config.paper.yaml with your Angel One API credentials
   ```

### Running the Engine

The main entry point is `scripts/run_bot.py` which supports three modes:

**1. Backfill Mode**
Fetches historical data to build the local parquet database.
```bash
python scripts/run_bot.py --mode backfill --config config/config.paper.yaml --days 30
```

**2. Paper Trading Mode (Sandbox)**
Runs the main execution loop connected to real-time data but executes trades via the internal PaperBroker.
```bash
python scripts/run_bot.py --mode paper --config config/config.paper.yaml
```

**3. Replay (Backtest) Mode**
Replays historical data through the exact same strategy and risk pipeline to generate backtest reports.
```bash
python scripts/run_bot.py --mode replay --config config/config.paper.yaml --date 2024-01-15
```

## Strategy Families

Bloom_Stock employs a multi-strategy approach routed by a Regime Classifier:

1. **ORB Continuation:** Operates in morning trend regimes. Targets momentum breakouts.
2. **VWAP Pullback:** Operates in mid-day established trends. Targets mean-reversion to moving averages.
3. **Mean Reversion:** Operates in range-bound, low-volatility regimes.
4. **Gap Event:** Trades at the open based on overnight gaps (fade or continuation).

## Risk Management

Risk is managed at multiple tiers by the `RiskEngine`:
- **Per-Trade:** Position sizing is strictly derived from stop-loss distance and fractional account risk.
- **Per-Instrument:** Limits maximum notional exposure on any single asset.
- **Sector Limits:** Prevents over-concentration in highly correlated sectors.
- **Daily Drawdown:** Enforces strict daily stop-loss limit (e.g., -1%) to halt the bot for the day.

## Configuration Guide

All numerical values, risk limits, and structural parameters are defined in YAML configuration files located in the `config/` directory. **No magic numbers exist in the code.**
Refer to `config/config.example.yaml` for a complete schema of acceptable configurations.
