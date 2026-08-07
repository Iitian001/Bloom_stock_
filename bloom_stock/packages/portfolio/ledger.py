from datetime import datetime
from decimal import Decimal
import uuid
from typing import Dict, Any, List

from loguru import logger
from pydantic import BaseModel, Field

from bloom_stock.packages.domain.schemas.orders import Fill

class FeeBreakdown(BaseModel):
    brokerage: Decimal = Decimal('0')
    stt: Decimal = Decimal('0')
    exchange_txn_charge: Decimal = Decimal('0')
    sebi_turnover_fee: Decimal = Decimal('0')
    stamp_duty: Decimal = Decimal('0')
    gst: Decimal = Decimal('0')
    
    @property
    def total(self) -> Decimal:
        return (self.brokerage + self.stt + self.exchange_txn_charge + 
                self.sebi_turnover_fee + self.stamp_duty + self.gst)

class LedgerEntry(BaseModel):
    entry_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime
    entry_type: str  # 'BUY', 'SELL', 'FEE', 'ADJUSTMENT'
    instrument_id: str | None = None
    quantity: int = 0
    price: Decimal = Decimal('0')
    cash_change: Decimal = Decimal('0')  # positive = cash in, negative = cash out
    description: str = ''

class PortfolioLedger:
    """Double-entry portfolio ledger that tracks all cash and position changes.
    Every fill produces balanced ledger entries."""
    
    def __init__(self, initial_capital: Decimal):
        self._initial_capital = initial_capital
        self._cash = initial_capital
        self._entries: List[LedgerEntry] = []
        self._daily_pnl: Decimal = Decimal('0')
        self._weekly_pnl: Decimal = Decimal('0')
        self._total_realized_pnl: Decimal = Decimal('0')
        self._peak_equity: Decimal = initial_capital
        self._open_unrealized_pnl: Decimal = Decimal('0')
    
    def record_entry(self, fill: Fill, fees: FeeBreakdown, side: str):
        """Record a position entry."""
        logger.info(f"Ledger: Recording entry for {fill.quantity} units of {fill.order_id} ({side})")
        
        notional = fill.price * fill.quantity
        if side == 'BUY':
            cash_change = -notional
        else:
            cash_change = notional
            
        trade_entry = LedgerEntry(
            timestamp=fill.timestamp,
            entry_type=side,
            instrument_id=fill.exchange_order_id,
            quantity=fill.quantity,
            price=fill.price,
            cash_change=cash_change,
            description=f"Entry {side} {fill.quantity} @ {fill.price}"
        )
        self._cash += cash_change
        self._entries.append(trade_entry)
        
        self._record_fees(fill, fees)
        self._update_peak_equity()
    
    def record_exit(self, fill: Fill, fees: FeeBreakdown, side: str, 
                    entry_price: Decimal):
        """Record a position exit and calculate P&L."""
        logger.info(f"Ledger: Recording exit for {fill.quantity} units of {fill.order_id} ({side})")
        
        notional = fill.price * fill.quantity
        if side == 'SELL':
            cash_change = notional
            realized_pnl = (fill.price - entry_price) * fill.quantity
        else:
            cash_change = -notional
            realized_pnl = (entry_price - fill.price) * fill.quantity
            
        trade_entry = LedgerEntry(
            timestamp=fill.timestamp,
            entry_type=side,
            instrument_id=fill.exchange_order_id,
            quantity=fill.quantity,
            price=fill.price,
            cash_change=cash_change,
            description=f"Exit {side} {fill.quantity} @ {fill.price}"
        )
        self._cash += cash_change
        self._entries.append(trade_entry)
        
        self._record_fees(fill, fees)
        
        net_pnl = realized_pnl - fees.total
        self._total_realized_pnl += net_pnl
        self._daily_pnl += net_pnl
        self._weekly_pnl += net_pnl
        
        self._update_peak_equity()

    def _record_fees(self, fill: Fill, fees: FeeBreakdown):
        if fees.total > Decimal('0'):
            fee_entry = LedgerEntry(
                timestamp=fill.timestamp,
                entry_type='FEE',
                instrument_id=fill.exchange_order_id,
                cash_change=-fees.total,
                description="Transaction fees and taxes"
            )
            self._cash -= fees.total
            self._entries.append(fee_entry)

    def update_unrealized_pnl(self, unrealized_pnl: Decimal):
        """Update the aggregate unrealized P&L from open positions."""
        self._open_unrealized_pnl = unrealized_pnl
        self._update_peak_equity()
    
    @property
    def cash(self) -> Decimal:
        return self._cash
    
    @property
    def equity(self) -> Decimal:
        """Cash + unrealized P&L of open positions."""
        return self._initial_capital + self._total_realized_pnl + self._open_unrealized_pnl
    
    @property
    def drawdown_from_peak(self) -> Decimal:
        if self._peak_equity <= Decimal('0'):
            return Decimal('0')
        return (self._peak_equity - self.equity) / self._peak_equity

    def _update_peak_equity(self):
        if self.equity > self._peak_equity:
            self._peak_equity = self.equity
    
    def get_snapshot(self) -> dict:
        return {
            "cash": self.cash,
            "equity": self.equity,
            "daily_pnl": self._daily_pnl,
            "weekly_pnl": self._weekly_pnl,
            "total_realized_pnl": self._total_realized_pnl,
            "unrealized_pnl": self._open_unrealized_pnl,
            "peak_equity": self._peak_equity,
            "drawdown": self.drawdown_from_peak,
            "entry_count": len(self._entries)
        }
    
    def reset_daily(self):
        self._daily_pnl = Decimal('0')
