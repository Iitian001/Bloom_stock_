from datetime import datetime, date, timedelta
from typing import Dict, Any
from enum import Enum

class TradingSessionPhase(Enum):
    PRE_MARKET = "PRE_MARKET"
    OPENING_RANGE = "OPENING_RANGE"
    CORE_TRADING = "CORE_TRADING"
    LIQUIDATION = "LIQUIDATION"
    HARD_FLAT = "HARD_FLAT"
    POST_MARKET = "POST_MARKET"

class NSEHolidays2026:
    """
    NSE Holidays for the year 2026.
    """
    HOLIDAYS = frozenset([
        date(2026, 1, 26),  # Republic Day
        date(2026, 3, 3),   # Mahashivratri
        date(2026, 3, 23),  # Holi
        date(2026, 4, 3),   # Good Friday
        date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
        date(2026, 4, 20),  # Id-ul-Fitr (Ramzan Id)
        date(2026, 5, 1),   # Maharashtra Day
        date(2026, 8, 15),  # Independence Day
        date(2026, 9, 15),  # Ganesh Chaturthi
        date(2026, 10, 2),  # Mahatma Gandhi Jayanti
        date(2026, 10, 20), # Dussehra
        date(2026, 11, 8),  # Diwali-Laxmi Pujan
        date(2026, 11, 24), # Gurunanak Jayanti
        date(2026, 12, 25), # Christmas
    ])

class MarketCalendar:
    """
    Market Session Calendar to manage trading phases and dates.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("session", {})
        
        # Parse times from config
        self.market_open = datetime.strptime(self.config.get("market_open", "09:15:00"), "%H:%M:%S").time()
        self.market_close = datetime.strptime(self.config.get("market_close", "15:30:00"), "%H:%M:%S").time()
        self.no_new_entries = datetime.strptime(self.config.get("no_new_entries_after", "14:30:00"), "%H:%M:%S").time()
        self.liquidation = datetime.strptime(self.config.get("begin_liquidation_at", "14:55:00"), "%H:%M:%S").time()
        self.hard_flat = datetime.strptime(self.config.get("hard_flat_cash_at", "15:10:00"), "%H:%M:%S").time()
        
        self.opening_range_mins = self.config.get("opening_range_minutes", 15)

    def is_trading_day(self, dt_date: date) -> bool:
        """Check if the given date is a trading day (weekday + non-holiday)."""
        if dt_date.weekday() >= 5: # 5=Sat, 6=Sun
            return False
        if dt_date in NSEHolidays2026.HOLIDAYS:
            return False
        return True

    def get_session_phase(self, dt: datetime) -> TradingSessionPhase:
        """Returns the current trading phase."""
        t = dt.time()
        
        if t < self.market_open:
            return TradingSessionPhase.PRE_MARKET
            
        open_time = datetime.combine(dt.date(), self.market_open)
        opening_range_end = (open_time + timedelta(minutes=self.opening_range_mins)).time()
        
        if t < opening_range_end:
            return TradingSessionPhase.OPENING_RANGE
            
        if t < self.liquidation:
            return TradingSessionPhase.CORE_TRADING
            
        if t < self.hard_flat:
            return TradingSessionPhase.LIQUIDATION
            
        if t < self.market_close:
            return TradingSessionPhase.HARD_FLAT
            
        return TradingSessionPhase.POST_MARKET

    def time_to_flat(self, dt: datetime) -> timedelta:
        """Time remaining until hard flat."""
        flat_time = datetime.combine(dt.date(), self.hard_flat)
        if dt >= flat_time:
            return timedelta(0)
        return flat_time - dt

    def time_since_open(self, dt: datetime) -> timedelta:
        """Time since market open."""
        open_time = datetime.combine(dt.date(), self.market_open)
        if dt <= open_time:
            return timedelta(0)
        return dt - open_time

    def is_entry_allowed(self, dt: datetime) -> bool:
        """Check if new entries are allowed based on session phase and time."""
        if not self.is_trading_day(dt.date()):
            return False
            
        t = dt.time()
        phase = self.get_session_phase(dt)
        
        if phase not in [TradingSessionPhase.OPENING_RANGE, TradingSessionPhase.CORE_TRADING]:
            return False
            
        if t >= self.no_new_entries:
            return False
            
        return True

    def next_trading_day(self, current_date: date) -> date:
        """Get the next trading day."""
        next_date = current_date + timedelta(days=1)
        while not self.is_trading_day(next_date):
            next_date += timedelta(days=1)
        return next_date

    def trading_minutes_remaining(self, dt: datetime) -> int:
        """Minutes remaining until market close."""
        close_time = datetime.combine(dt.date(), self.market_close)
        if dt >= close_time:
            return 0
        delta = close_time - dt
        return int(delta.total_seconds() / 60)
