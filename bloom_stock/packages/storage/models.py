"""SQLAlchemy ORM models for Bloom_Stock data storage."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from bloom_stock.packages.storage.db import Base


class OrderModel(Base):
    """
    Represents a trading order in the database.
    """

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(String, index=True, nullable=False)
    side = Column(String, nullable=False)  # "BUY", "SELL"
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    state = Column(String, nullable=False)  # "NEW", "OPEN", "FILLED", "REJECTED", "CANCELLED"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)


class PositionModel(Base):
    """
    Represents a trading position for a specific instrument.
    """

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(String, unique=True, index=True, nullable=False)
    average_price = Column(Float, nullable=False, default=0.0)
    net_quantity = Column(Integer, nullable=False, default=0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)


class LedgerEntryModel(Base):
    """
    Represents a ledger entry for accounting and PnL tracking.
    """

    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(String, index=True, nullable=False)  # "FEE", "REALIZED_GAIN", "MARGIN_LOCK"
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes = Column(String, nullable=True)
