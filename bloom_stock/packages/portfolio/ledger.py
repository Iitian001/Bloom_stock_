"""
Portfolio Ledger
Tracks positions and cash transactions using SQLAlchemy models.
"""
from loguru import logger
from sqlalchemy.future import select

from bloom_stock.packages.storage.db import AsyncSessionLocal
from bloom_stock.packages.storage.models import PositionModel, LedgerEntryModel

class PortfolioLedger:
    """Async Portfolio Ledger backed by DB."""
    
    @staticmethod
    async def update_position(instrument_id: str, qty_change: int, price: float) -> None:
        """Updates or creates a PositionModel."""
        async with AsyncSessionLocal() as session:
            stmt = select(PositionModel).filter_by(instrument_id=instrument_id)
            result = await session.execute(stmt)
            position = result.scalar_one_or_none()
            
            if position is None:
                position = PositionModel(
                    instrument_id=instrument_id,
                    average_price=price,
                    net_quantity=qty_change,
                    realized_pnl=0.0
                )
                session.add(position)
                logger.info(f"Created new position for {instrument_id}")
            else:
                if (position.net_quantity > 0 and qty_change > 0) or (position.net_quantity < 0 and qty_change < 0):
                    total_val = (position.average_price * position.net_quantity) + (price * qty_change)
                    position.net_quantity += qty_change
                    if position.net_quantity != 0:
                        position.average_price = total_val / position.net_quantity
                else:
                    closed_qty = min(abs(position.net_quantity), abs(qty_change))
                    direction = 1 if position.net_quantity > 0 else -1
                    pnl = (price - position.average_price) * closed_qty * direction
                    position.realized_pnl += pnl
                    position.net_quantity += qty_change
                    if position.net_quantity == 0:
                        position.average_price = 0.0
                logger.info(f"Updated position for {instrument_id}, net_qty: {position.net_quantity}")
            
            await session.commit()
            
    @staticmethod
    async def record_transaction(type: str, amount: float, notes: str) -> None:
        """Appends to LedgerEntryModel."""
        async with AsyncSessionLocal() as session:
            entry = LedgerEntryModel(
                transaction_type=type,
                amount=amount,
                notes=notes
            )
            session.add(entry)
            await session.commit()
            logger.info(f"Recorded transaction: {type} amount: {amount}")
