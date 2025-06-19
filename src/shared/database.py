"""
Tel-Insights Database Module

Database connection management and session handling using SQLAlchemy.
This module provides the database engine, session factory, and base model class.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings

settings = get_settings()

# Database metadata
metadata = MetaData()

# Declarative base for ORM models
Base = declarative_base(metadata=metadata)

# Synchronous database engine and session
sync_engine = create_engine(
    settings.database.url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    echo=settings.app.debug,
)

SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)

# Asynchronous database engine and session (for future use)
async_database_url = settings.database.url.replace("postgresql://", "postgresql+asyncpg://")
async_engine = create_async_engine(
    async_database_url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    echo=settings.app.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
)


def get_sync_db() -> Session:
    """
    Dependency function to get a synchronous database session.
    
    Returns:
        Session: SQLAlchemy database session
        
    Yields:
        Session: Database session that will be closed after use
    """
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager to get an asynchronous database session.
    
    Yields:
        AsyncSession: SQLAlchemy async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def create_tables() -> None:
    """
    Create all database tables defined in the models.
    This should only be used in development or for initial setup.
    """
    Base.metadata.create_all(bind=sync_engine)


def drop_tables() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data. Use with caution.
    """
    Base.metadata.drop_all(bind=sync_engine)


async def create_tables_async() -> None:
    """
    Asynchronously create all database tables defined in the models.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables_async() -> None:
    """
    Asynchronously drop all database tables.
    WARNING: This will delete all data. Use with caution.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    This is typically called during application startup.
    """
    create_tables()


async def init_db_async() -> None:
    """
    Asynchronously initialize the database by creating all tables.
    """
    await create_tables_async() 