from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

class FeeSchedule(BaseModel):
    """Versioned fee configuration for a specific broker/segment combination."""
    model_config = ConfigDict(from_attributes=True)
    
    broker: str
    segment: str  # EQUITY, F&O, etc.
    product: str  # INTRADAY, DELIVERY
    effective_from: date
    effective_to: Optional[date] = None
    
    # Brokerage
    brokerage_per_order: Decimal  # flat fee, e.g. 20
    brokerage_percentage: Decimal  # percentage, e.g. 0.03%
    brokerage_type: str  # 'FLAT', 'PERCENTAGE', 'LOWER_OF_BOTH'
    
    # Statutory charges
    stt_buy_percentage: Decimal  # STT on buy side
    stt_sell_percentage: Decimal  # STT on sell side
    exchange_transaction_charge_percentage: Decimal
    gst_percentage: Decimal  # GST on brokerage + exchange charges
    sebi_turnover_fee_per_crore: Decimal
    stamp_duty_buy_percentage: Decimal

class TradeForFee(BaseModel):
    side: str  # BUY or SELL
    price: Decimal
    quantity: int
    broker: str
    segment: str
    product: str  # INTRADAY or DELIVERY
    trade_date: date

class FeeBreakdown(BaseModel):
    brokerage: Decimal
    stt: Decimal
    exchange_transaction_charges: Decimal
    gst: Decimal
    sebi_charges: Decimal
    stamp_duty: Decimal
    total: Decimal
    total_as_percentage: Decimal  # of turnover
    
    # Round-trip fields (optional)
    buy_side_total: Optional[Decimal] = None
    sell_side_total: Optional[Decimal] = None

class FeeEngine:
    """A versioned, configurable fee engine for Indian equity markets."""
    def __init__(self, schedules: list[FeeSchedule]):
        self.schedules = schedules
        
    def _get_schedule(self, broker: str, segment: str, product: str, trade_date: date) -> FeeSchedule:
        for schedule in self.schedules:
            if (schedule.broker == broker and 
                schedule.segment == segment and 
                schedule.product == product):
                if schedule.effective_from <= trade_date:
                    if schedule.effective_to is None or trade_date <= schedule.effective_to:
                        return schedule
        raise ValueError(f"No fee schedule found for {broker}, {segment}, {product} on {trade_date}")

    def calculate(self, trade: TradeForFee) -> FeeBreakdown:
        """Calculate all applicable fees for a trade."""
        schedule = self._get_schedule(trade.broker, trade.segment, trade.product, trade.trade_date)
        turnover = trade.price * Decimal(trade.quantity)
        
        # Brokerage
        if schedule.brokerage_type == 'FLAT':
            brokerage = schedule.brokerage_per_order
        elif schedule.brokerage_type == 'PERCENTAGE':
            brokerage = turnover * (schedule.brokerage_percentage / Decimal('100'))
        elif schedule.brokerage_type == 'LOWER_OF_BOTH':
            brokerage = min(schedule.brokerage_per_order, turnover * (schedule.brokerage_percentage / Decimal('100')))
        else:
            raise ValueError(f"Unknown brokerage type: {schedule.brokerage_type}")
            
        # STT
        if trade.side == 'BUY':
            stt = turnover * (schedule.stt_buy_percentage / Decimal('100'))
        else:
            stt = turnover * (schedule.stt_sell_percentage / Decimal('100'))
        stt = round(stt)
        
        # Exchange Transaction Charges
        exchange_charges = turnover * (schedule.exchange_transaction_charge_percentage / Decimal('100'))
        
        # GST
        gst = (brokerage + exchange_charges) * (schedule.gst_percentage / Decimal('100'))
        
        # SEBI Charges
        sebi_charges = (turnover / Decimal('10000000')) * schedule.sebi_turnover_fee_per_crore
        
        # Stamp Duty
        if trade.side == 'BUY':
            stamp_duty = turnover * (schedule.stamp_duty_buy_percentage / Decimal('100'))
            stamp_duty = round(stamp_duty)
        else:
            stamp_duty = Decimal('0')
            
        total_fees = brokerage + Decimal(stt) + exchange_charges + gst + sebi_charges + Decimal(stamp_duty)
        total_fees_percentage = (total_fees / turnover) * Decimal('100') if turnover > 0 else Decimal('0')
        
        return FeeBreakdown(
            brokerage=brokerage,
            stt=Decimal(stt),
            exchange_transaction_charges=exchange_charges,
            gst=gst,
            sebi_charges=sebi_charges,
            stamp_duty=Decimal(stamp_duty),
            total=total_fees,
            total_as_percentage=total_fees_percentage
        )

    def round_trip_cost(self, buy_price: Decimal, sell_price: Decimal, quantity: int, broker: str, segment: str, product: str, trade_date: date) -> FeeBreakdown:
        """Calculate total round-trip cost (buy + sell)."""
        buy_trade = TradeForFee(side='BUY', price=buy_price, quantity=quantity, broker=broker, segment=segment, product=product, trade_date=trade_date)
        sell_trade = TradeForFee(side='SELL', price=sell_price, quantity=quantity, broker=broker, segment=segment, product=product, trade_date=trade_date)
        
        buy_fees = self.calculate(buy_trade)
        sell_fees = self.calculate(sell_trade)
        
        total = buy_fees.total + sell_fees.total
        total_turnover = (buy_price * quantity) + (sell_price * quantity)
        total_as_percentage = (total / total_turnover) * Decimal('100') if total_turnover > 0 else Decimal('0')
        
        return FeeBreakdown(
            brokerage=buy_fees.brokerage + sell_fees.brokerage,
            stt=buy_fees.stt + sell_fees.stt,
            exchange_transaction_charges=buy_fees.exchange_transaction_charges + sell_fees.exchange_transaction_charges,
            gst=buy_fees.gst + sell_fees.gst,
            sebi_charges=buy_fees.sebi_charges + sell_fees.sebi_charges,
            stamp_duty=buy_fees.stamp_duty + sell_fees.stamp_duty,
            total=total,
            total_as_percentage=total_as_percentage,
            buy_side_total=buy_fees.total,
            sell_side_total=sell_fees.total
        )

def default_angel_one_equity_intraday() -> FeeSchedule:
    """Returns the current Angel One fee schedule for NSE equity intraday."""
    return FeeSchedule(
        broker="ANGEL_ONE",
        segment="EQUITY",
        product="INTRADAY",
        effective_from=date(2023, 1, 1),
        brokerage_per_order=Decimal('20.00'),
        brokerage_percentage=Decimal('0.03'),
        brokerage_type="LOWER_OF_BOTH",
        stt_buy_percentage=Decimal('0.00'),
        stt_sell_percentage=Decimal('0.025'),
        exchange_transaction_charge_percentage=Decimal('0.00345'),
        gst_percentage=Decimal('18.00'),
        sebi_turnover_fee_per_crore=Decimal('10.00'),
        stamp_duty_buy_percentage=Decimal('0.003')
    )
