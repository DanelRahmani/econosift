"""SQLAlchemy ORM models for Axiom Finance persistence layer."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
)

from .database import Base


class DailyPrice(Base):
    """OHLCV price history per symbol/date."""

    __tablename__ = "daily_price"

    symbol = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    adj_close = Column(Float)
    volume = Column(BigInteger)

    __table_args__ = (
        PrimaryKeyConstraint("symbol", "date"),
        Index("ix_daily_price_date", "date"),
    )


class DailyQuote(Base):
    """Latest fundamental snapshot per symbol."""

    __tablename__ = "daily_quote"

    symbol = Column(String, primary_key=True)
    date = Column(Date)
    price = Column(Float)
    market_cap = Column(Float)
    pe = Column(Float)
    forward_pe = Column(Float)
    div_yield = Column(Float)
    beta = Column(Float)
    high52 = Column(Float)
    low52 = Column(Float)
    avg_vol_20d = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DailyMacro(Base):
    """World Bank / FRED macro indicator values per country/date."""

    __tablename__ = "daily_macro"

    indicator_id = Column(String, nullable=False)
    country = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    value = Column(Float)

    __table_args__ = (
        PrimaryKeyConstraint("indicator_id", "country", "date"),
        Index("ix_daily_macro_indicator_date", "indicator_id", "date"),
    )


class DailyFX(Base):
    """FX spot rates per currency pair/date."""

    __tablename__ = "daily_fx"

    base_ccy = Column(String(3), nullable=False)
    quote_ccy = Column(String(3), nullable=False)
    date = Column(Date, nullable=False)
    rate = Column(Float)

    __table_args__ = (
        PrimaryKeyConstraint("base_ccy", "quote_ccy", "date"),
    )


class JobExecution(Base):
    """Audit log for background scheduler jobs."""

    __tablename__ = "job_execution"

    job_id = Column(String, primary_key=True)
    job_name = Column(String)
    status = Column(String)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(String)
    rows_affected = Column(Integer)


class CacheEntry(Base):
    """Persistent key-value cache (JSON strings) keyed by cache_name + key."""

    __tablename__ = "cache_entry"

    cache_name = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value_json = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint("cache_name", "key"),
    )
