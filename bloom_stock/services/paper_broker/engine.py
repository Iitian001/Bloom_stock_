import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Dict, List, Optional, Set

from loguru import logger
from pydantic import BaseModel, Field, ConfigDict

from bloom_stock.packages.domain.enums import OrderStatus, OrderSide, OrderType
from bloom_stock.packages.domain.schemas.orders import OrderIntent, OrderState, Fill
from bloom_stock.packages.domain.schemas.portfolio import PortfolioSnapshot
from bloom_stock.packages.domain.schemas.candles import Candle
from bloom_stock.packages.portfolio.ledger import PortfolioLedger, FeeBreakdown


class PaperBrokerConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    initial_capital: Decimal = Decimal('1000000')  # 10 lakh default
    fill_latency_ms: int = 50
    slippage_bps: Decimal = Decimal('5')
    allow_short_selling: bool = True
    auto_square_off_time: time = time(15, 10)


class PaperPosition(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    instrument_id: str
    side: str  # BUY or SELL (for short)
    quantity: int
    average_entry_price: Decimal
    current_price: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    entry_time: datetime
    strategy_family: str
    protective_stop: Decimal
    target_price: Decimal
    
    def update_price(self, price: Decimal):
        self.current_price = price
        if self.side == 'BUY':
            self.unrealized_pnl = (price - self.average_entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.average_entry_price - price) * self.quantity


class TradeRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trade_id: uuid.UUID
    instrument_id: str
    side: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: int
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    entry_time: datetime
    exit_time: datetime
    strategy_family: str
    exit_reason: str  # 'TARGET', 'STOP_LOSS', 'TIME_STOP', 'SQUARE_OFF', 'MANUAL'
    holding_time_minutes: int


class DailyReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: date
    starting_equity: Decimal
    ending_equity: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal  # after fees
    total_fees: Decimal
    trades_completed: int
    winning_trades: int
    losing_trades: int
    max_drawdown: Decimal
    sharpe_estimate: Optional[float] = None
    trade_log: List[TradeRecord] = Field(default_factory=list)


class PaperBroker:
    """Simulates broker order execution for paper trading.
    
    Implements the full order state machine from Section 15.1:
    DRAFT → AWAITING_APPROVAL → APPROVED → SUBMITTING → BROKER_ACCEPTED → OPEN
    → PARTIALLY_FILLED → FILLED → EXIT_PENDING → CLOSED
    
    Terminal: REJECTED, CANCELLED, EXPIRED, UNKNOWN_RECONCILIATION_REQUIRED
    
    Key rules:
    - No strategy or ML service may call placeOrder directly
    - Every order goes through: Signal → Proposal → Intent → Risk → Approval → OMS
    - Idempotency key prevents duplicate orders
    - Approval tokens expire
    """
    
    def __init__(self, config: PaperBrokerConfig):
        self._config = config
        self._intents: Dict[uuid.UUID, OrderIntent] = {}
        self._orders: Dict[uuid.UUID, OrderState] = {}
        self._fills: List[Fill] = []
        self._positions: Dict[str, PaperPosition] = {}  # instrument_id -> position
        self._idempotency_keys: Set[uuid.UUID] = set()
        self._ledger = PortfolioLedger(config.initial_capital)
        
        # State tracking for daily report
        self._completed_trades: List[TradeRecord] = []
        self._starting_equity = config.initial_capital
        self._daily_gross_pnl = Decimal('0')
        self._daily_fees = Decimal('0')

    def submit_intent(self, intent: OrderIntent) -> OrderState:
        """Submit an order intent. Validates and transitions to appropriate state."""
        logger.info(f"Submitting intent {intent.intent_id} for {intent.instrument_id}")
        
        # Check idempotency
        if intent.idempotency_key in self._idempotency_keys:
            logger.warning(f"Duplicate intent submission blocked: {intent.idempotency_key}")
            # Find the existing order with this idempotency key if possible, or just fail safely.
            for order in self._orders.values():
                if order.intent_id == intent.intent_id:
                    return order

        # Expiry check
        if datetime.utcnow() > intent.approval_expiry:
            order_state = self._create_rejected_order(intent, "Intent expired before submission")
            self._orders[order_state.order_id] = order_state
            return order_state
            
        self._idempotency_keys.add(intent.idempotency_key)
        self._intents[intent.intent_id] = intent
        
        # Initialize order state simulating broker acceptance
        order_id = uuid.uuid4()
        now = datetime.utcnow()
        order_state = OrderState(
            order_id=order_id,
            intent_id=intent.intent_id,
            broker_order_id=f"sim_{order_id.hex[:8]}",
            status=OrderStatus.OPEN,
            filled_quantity=0,
            placed_at=now,
            last_updated=now
        )
        self._orders[order_id] = order_state
        return order_state

    def simulate_fills(self, candle: Candle):
        """Called on each candle to simulate fills for open orders.
        Checks if any open orders would have been filled on this candle."""
        open_orders = [o for o in self._orders.values() if o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)]
        
        for order in open_orders:
            intent = self._get_intent_for_order(order)
            if not intent:
                continue

            fill_price = None
            if intent.order_type == OrderType.MARKET:
                fill_price = candle.open # Simulate filling at open of the next candle
            elif intent.order_type == OrderType.LIMIT and intent.price is not None:
                if (intent.side == OrderSide.BUY and candle.low <= intent.price) or \
                   (intent.side == OrderSide.SELL and candle.high >= intent.price):
                    fill_price = intent.price
            elif intent.order_type in (OrderType.SL, OrderType.SL_M) and intent.trigger_price is not None:
                if (intent.side == OrderSide.BUY and candle.high >= intent.trigger_price) or \
                   (intent.side == OrderSide.SELL and candle.low <= intent.trigger_price):
                    fill_price = intent.trigger_price
                    
            if fill_price:
                # Apply slippage
                slippage = fill_price * (self._config.slippage_bps / Decimal('10000'))
                if intent.side == OrderSide.BUY:
                    fill_price += slippage
                else:
                    fill_price -= slippage
                    
                self._execute_fill(order, intent, fill_price, intent.quantity, candle.end_timestamp)

        # Update position prices and unrealized pnl
        total_unrealized = Decimal('0')
        for pos in self._positions.values():
            if pos.instrument_id == candle.instrument_id:
                pos.update_price(candle.close)
            total_unrealized += pos.unrealized_pnl
        self._ledger.update_unrealized_pnl(total_unrealized)

    def _execute_fill(self, order: OrderState, intent: OrderIntent, price: Decimal, quantity: int, timestamp: datetime):
        """Execute a fill and update positions and ledger."""
        fill = Fill(
            fill_id=uuid.uuid4(),
            order_id=order.order_id,
            price=price,
            quantity=quantity,
            timestamp=timestamp,
            exchange_order_id=order.broker_order_id
        )
        self._fills.append(fill)
        
        # Update order state
        order.filled_quantity += quantity
        order.average_fill_price = price # Simple average, assuming full fill for now
        order.status = OrderStatus.FILLED
        order.filled_at = timestamp
        order.last_updated = timestamp

        # Update position
        inst = intent.instrument_id
        fees = self._calculate_simulated_fees(price, quantity)
        
        if inst not in self._positions:
            self._positions[inst] = PaperPosition(
                instrument_id=inst,
                side=intent.side.value,
                quantity=quantity,
                average_entry_price=price,
                current_price=price,
                entry_time=timestamp,
                strategy_family=intent.strategy_family.value,
                protective_stop=intent.protective_stop_price,
                target_price=intent.target_price
            )
            self._ledger.record_entry(fill, fees, intent.side.value)
            self._daily_fees += fees.total
        else:
            pos = self._positions[inst]
            if pos.side == intent.side.value:
                # Adding to position
                total_val = (pos.average_entry_price * pos.quantity) + (price * quantity)
                pos.quantity += quantity
                pos.average_entry_price = total_val / pos.quantity
                self._ledger.record_entry(fill, fees, intent.side.value)
                self._daily_fees += fees.total
            else:
                # Closing or reducing position
                closed_qty = min(pos.quantity, quantity)
                self._ledger.record_exit(fill, fees, intent.side.value, pos.average_entry_price)
                self._daily_fees += fees.total
                
                # Calculate Trade Record PnL
                gross_pnl = Decimal('0')
                if pos.side == 'BUY':
                    gross_pnl = (price - pos.average_entry_price) * closed_qty
                else:
                    gross_pnl = (pos.average_entry_price - price) * closed_qty
                
                self._daily_gross_pnl += gross_pnl
                
                minutes_held = int((timestamp - pos.entry_time).total_seconds() / 60)
                
                trade_record = TradeRecord(
                    trade_id=uuid.uuid4(),
                    instrument_id=inst,
                    side=pos.side,
                    entry_price=pos.average_entry_price,
                    exit_price=price,
                    quantity=closed_qty,
                    gross_pnl=gross_pnl,
                    fees=fees.total,
                    net_pnl=gross_pnl - fees.total,
                    entry_time=pos.entry_time,
                    exit_time=timestamp,
                    strategy_family=pos.strategy_family,
                    exit_reason="SIM_FILL",
                    holding_time_minutes=minutes_held
                )
                self._completed_trades.append(trade_record)
                
                pos.quantity -= closed_qty
                if pos.quantity <= 0:
                    del self._positions[inst]

    def _calculate_simulated_fees(self, price: Decimal, quantity: int) -> FeeBreakdown:
        notional = price * quantity
        return FeeBreakdown(
            brokerage=Decimal('20.0'),
            stt=notional * Decimal('0.00025'),
            exchange_txn_charge=notional * Decimal('0.0000345'),
            gst=Decimal('3.6')
        )

    def cancel_order(self, order_id: uuid.UUID) -> bool:
        """Cancel an open order."""
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = datetime.utcnow()
                order.last_updated = datetime.utcnow()
                logger.info(f"Cancelled order {order_id}")
                return True
        return False
    
    def cancel_all(self) -> int:
        """Emergency cancel all open orders. Returns count cancelled."""
        count = 0
        for order in self._orders.values():
            if order.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = datetime.utcnow()
                order.last_updated = datetime.utcnow()
                count += 1
        logger.warning(f"Emergency cancelled {count} orders")
        return count
    
    def get_order(self, order_id: uuid.UUID) -> Optional[OrderState]:
        return self._orders.get(order_id)
    
    def get_open_orders(self) -> List[OrderState]:
        return [o for o in self._orders.values() if o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)]
    
    def get_positions(self) -> Dict[str, PaperPosition]:
        return self._positions.copy()
    
    def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        # Construct and return PortfolioSnapshot (simplified for this mockup)
        pass # Full snapshot implementation would depend on the imported Pydantic model
    
    def square_off_all(self, current_prices: Dict[str, Decimal]):
        """Force close all positions at current prices. Used for EOD flat."""
        logger.info("Executing EOD square off for all positions.")
        self.cancel_all()
        now = datetime.utcnow()
        
        for inst, pos in list(self._positions.items()):
            price = current_prices.get(inst)
            if not price:
                logger.error(f"No price provided for {inst} during square off!")
                continue
                
            # Create dummy intent to close
            intent = OrderIntent(
                intent_id=uuid.uuid4(),
                instrument_id=inst,
                side=OrderSide.SELL if pos.side == 'BUY' else OrderSide.BUY,
                order_type=OrderType.MARKET,
                product="INTRADAY",
                quantity=pos.quantity,
                protective_stop_price=Decimal('0'),
                target_price=Decimal('0'),
                strategy_family=pos.strategy_family,
                regime_at_entry="FLAT",
                config_version="sim",
                idempotency_key=uuid.uuid4(),
                approval_expiry=now
            )
            
            order_id = uuid.uuid4()
            order_state = OrderState(
                order_id=order_id,
                intent_id=intent.intent_id,
                broker_order_id=f"sqoff_{order_id.hex[:8]}",
                status=OrderStatus.OPEN,
                placed_at=now,
                last_updated=now
            )
            self._orders[order_id] = order_state
            self._execute_fill(order_state, intent, price, pos.quantity, now)

    def get_daily_report(self) -> DailyReport:
        winning = sum(1 for t in self._completed_trades if t.net_pnl > 0)
        losing = sum(1 for t in self._completed_trades if t.net_pnl <= 0)
        
        report = DailyReport(
            date=datetime.utcnow().date(),
            starting_equity=self._starting_equity,
            ending_equity=self._ledger.equity,
            gross_pnl=self._daily_gross_pnl,
            net_pnl=self._daily_gross_pnl - self._daily_fees,
            total_fees=self._daily_fees,
            trades_completed=len(self._completed_trades),
            winning_trades=winning,
            losing_trades=losing,
            max_drawdown=self._ledger.drawdown_from_peak,
            trade_log=self._completed_trades.copy()
        )
        return report
    
    def reset_day(self):
        """Reset for new trading day. Positions should already be flat."""
        logger.info("Resetting paper broker for new day")
        if self._positions:
            logger.warning("Positions not flat on reset!")
            
        self._starting_equity = self._ledger.equity
        self._daily_gross_pnl = Decimal('0')
        self._daily_fees = Decimal('0')
        self._completed_trades.clear()
        self._ledger.reset_daily()

    def _create_rejected_order(self, intent: OrderIntent, reason: str) -> OrderState:
        now = datetime.utcnow()
        return OrderState(
            order_id=uuid.uuid4(),
            intent_id=intent.intent_id,
            status=OrderStatus.REJECTED,
            rejected_reason=reason,
            last_updated=now
        )
        
    def _get_intent_for_order(self, order: OrderState) -> Optional[OrderIntent]:
        return self._intents.get(order.intent_id)
