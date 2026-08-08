"""
Stateful Paper Broker Engine
Uses SQLAlchemy database to store orders and state.
"""
from datetime import datetime
from typing import Optional
from loguru import logger
from sqlalchemy.future import select

from bloom_stock.packages.domain.enums import OrderStatus
from bloom_stock.packages.domain.schemas.orders import OrderIntent, OrderState
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.storage.db import AsyncSessionLocal
from bloom_stock.packages.storage.models import OrderModel
from bloom_stock.packages.portfolio.ledger import PortfolioLedger


class FillSimulator:
    @staticmethod
    def check_fill(order: OrderModel, candle: Candle) -> Optional[float]:
        """Simple fill simulator."""
        if order.instrument_id != candle.instrument_id:
            return None
            
        # Simplistic fill logic, filling at candle close for simplicity
        if order.side == "BUY":
            return float(candle.close)
        elif order.side == "SELL":
            return float(candle.close)
            
        return None


class PaperBroker:
    """Async Paper Broker using DB models."""
    
    def __init__(self):
        self.ledger = PortfolioLedger()
        
    async def submit_order(self, intent: OrderIntent) -> OrderState:
        """Inserts a new OrderModel with state NEW."""
        async with AsyncSessionLocal() as session:
            order = OrderModel(
                instrument_id=intent.instrument_id,
                side=intent.side.value if hasattr(intent.side, 'value') else str(intent.side),
                quantity=intent.quantity,
                price=float(intent.price) if intent.price else 0.0,
                state="NEW"
            )
            session.add(order)
            await session.commit()
            
            logger.info(f"Submitted new order for {intent.instrument_id}")
            
            return OrderState(
                order_id=intent.intent_id,
                intent_id=intent.intent_id,
                broker_order_id=f"sim_{intent.instrument_id}",
                status=OrderStatus.NEW,
                filled_quantity=0,
                placed_at=datetime.utcnow(),
                last_updated=datetime.utcnow()
            )
            
    async def process_market_data(self, candle: Candle) -> None:
        """
        Queries all OPEN or NEW orders from the database.
        Uses the FillSimulator to check for fills.
        If filled, updates the state to FILLED in the database,
        and calls ledger methods.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(OrderModel).where(OrderModel.state.in_(["NEW", "OPEN"]))
            result = await session.execute(stmt)
            active_orders = result.scalars().all()
            
            for order in active_orders:
                fill_price = FillSimulator.check_fill(order, candle)
                if fill_price is not None:
                    logger.info(f"Order {order.id} filled at {fill_price}")
                    order.state = "FILLED"
                    
                    qty_change = order.quantity if order.side == "BUY" else -order.quantity
                    await self.ledger.update_position(
                        instrument_id=order.instrument_id,
                        qty_change=qty_change,
                        price=fill_price
                    )
                    
                    fees = float(fill_price * order.quantity) * 0.0001
                    await self.ledger.record_transaction(
                        type="FEE",
                        amount=-fees,
                        notes=f"Fees for order {order.id}"
                    )
                    
            await session.commit()
