"""Database connection and session management for Bloom_Stock."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

# Base class for all SQLAlchemy declarative models
Base = declarative_base()

# Use SQLite for local development, allowing easy swap to Postgres later
# In a production setting, the connection string should be loaded from configuration
DATABASE_URL = "sqlite+aiosqlite:///paper_trading.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    """Initialize the database by creating all defined tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
