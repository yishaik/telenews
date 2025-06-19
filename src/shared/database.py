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
from .logging import get_logger # Import logger

settings = get_settings()
logger = get_logger(__name__) # Initialize module logger

# Database metadata
metadata = MetaData()

# Declarative base for ORM models
Base = declarative_base(metadata=metadata)

# Synchronous database engine and session
logger.info(
    "Creating synchronous database engine.",
    db_url_preview=settings.database.url[:settings.database.url.find('@')] if '@' in settings.database.url else settings.database.url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    echo=settings.app.debug
)
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
logger.debug("Synchronous SessionLocal created.")

# Asynchronous database engine and session (for future use)
async_database_url = settings.database.url.replace("postgresql://", "postgresql+asyncpg://")
logger.info(
    "Creating asynchronous database engine.",
    db_url_preview=async_database_url[:async_database_url.find('@')] if '@' in async_database_url else async_database_url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    echo=settings.app.debug
)
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
logger.debug("Asynchronous AsyncSessionLocal created.")


def get_sync_db() -> Session:
    """
    Dependency function to get a synchronous database session.
    
    Returns:
        Session: SQLAlchemy database session
        
    Yields:
        Session: Database session that will be closed after use
    """
    logger.debug("Requesting synchronous database session.")
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        logger.debug("Closing synchronous database session.")
        db.close()


def get_db_session() -> Session:
    """
    Get a synchronous database session for direct use.
    
    Returns:
        Session: SQLAlchemy database session (must be closed manually)
    """
    return SyncSessionLocal()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager to get an asynchronous database session.
    
    Yields:
        AsyncSession: SQLAlchemy async database session
    """
    logger.debug("Requesting asynchronous database session.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            logger.debug("Closing asynchronous database session.")
            await session.close()


def create_tables() -> None:
    """
    Create all database tables defined in the models.
    This should only be used in development or for initial setup.
    """
    logger.info("Attempting to create database tables (synchronous).")
    try:
        Base.metadata.create_all(bind=sync_engine)
        logger.info("Database tables created successfully (synchronous).")
    except Exception as e:
        logger.error("Failed to create database tables (synchronous).", error=str(e), exc_info=True)
        raise


def drop_tables() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data. Use with caution.
    """
    logger.warning("Attempting to drop all database tables (synchronous). THIS IS A DESTRUCTIVE OPERATION.")
    try:
        Base.metadata.drop_all(bind=sync_engine)
        logger.info("Database tables dropped successfully (synchronous).")
    except Exception as e:
        logger.error("Failed to drop database tables (synchronous).", error=str(e), exc_info=True)
        raise


async def create_tables_async() -> None:
    """
    Asynchronously create all database tables defined in the models.
    """
    logger.info("Attempting to create database tables (asynchronous).")
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully (asynchronous).")
    except Exception as e:
        logger.error("Failed to create database tables (asynchronous).", error=str(e), exc_info=True)
        raise


async def drop_tables_async() -> None:
    """
    Asynchronously drop all database tables.
    WARNING: This will delete all data. Use with caution.
    """
    logger.warning("Attempting to drop all database tables (asynchronous). THIS IS A DESTRUCTIVE OPERATION.")
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped successfully (asynchronous).")
    except Exception as e:
        logger.error("Failed to drop database tables (asynchronous).", error=str(e), exc_info=True)
        raise


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    This is typically called during application startup.
    """
    logger.info("Initializing database (synchronous)...")
    create_tables()
    logger.info("Database initialization complete (synchronous).")


async def init_db_async() -> None:
    """
    Asynchronously initialize the database by creating all tables.
    """
    logger.info("Initializing database (asynchronous)...")
    await create_tables_async()
    logger.info("Database initialization complete (asynchronous).")