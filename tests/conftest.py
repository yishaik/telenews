"""
Pytest configuration and shared fixtures for Tel-Insights tests.
"""

import os
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from shared.database import Base
from shared.models import Channel, Message, Media, User, AlertConfig, Prompt


@pytest.fixture(scope="function")
def test_database():
    """Create a test database for the session."""
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    yield TestSessionLocal
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_database):
    """Create a database session for a test."""
    session = test_database()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_channel():
    """Create a sample channel for testing."""
    return Channel(
        id=1001234567890,
        name="Test News Channel",
        username="test_news"
    )


@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    return Message(
        telegram_message_id=12345,
        channel_id=1001234567890,
        message_text="This is a test news message about technology.",
        message_timestamp=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        ai_metadata={
            "summary": "Test news about technology",
            "topics": ["technology", "news"],
            "sentiment": "neutral",
            "entities": {
                "organizations": ["TestCorp"],
                "locations": ["TestCity"]
            },
            "keywords": ["technology", "test", "news"],
            "confidence_score": 0.85
        }
    )


@pytest.fixture
def sample_media():
    """Create a sample media record for testing."""
    return Media(
        media_hash="abcd1234567890abcd1234567890abcd1234567890abcd1234567890abcd1234",
        storage_url="gs://test-bucket/test-file.jpg",
        media_type="photo",
        file_size_bytes=1024000
    )


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User(
        telegram_user_id=987654321,
        first_name="Test",
        username="testuser"
    )


@pytest.fixture
def sample_alert_config():
    """Create a sample alert configuration for testing."""
    return AlertConfig(
        user_id=987654321,
        config_name="Tech News Alert",
        criteria={
            "type": "frequency",
            "keywords": ["AI", "technology"],
            "threshold": 5,
            "window_minutes": 60
        },
        is_active=True
    )


@pytest.fixture
def mock_telegram_client():
    """Create a mock Telegram client for testing."""
    client = Mock()
    client.is_connected.return_value = True
    client.get_me.return_value = Mock(
        id=123456789,
        username="test_bot",
        first_name="Test Bot"
    )
    return client


@pytest.fixture
def mock_message_producer():
    """Create a mock message producer for testing."""
    producer = Mock()
    producer.publish_message.return_value = True
    producer.publish_new_message_event.return_value = True
    return producer


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing."""
    client = Mock()
    client.generate_content.return_value = Mock(
        text='{"summary": "Test summary", "topics": ["test"], "sentiment": "neutral"}'
    )
    return client


@pytest.fixture
def test_env_vars():
    """Set test environment variables."""
    test_vars = {
        "DATABASE_URL": "sqlite:///:memory:",
        "RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
        "TELEGRAM_API_ID": "123456",
        "TELEGRAM_API_HASH": "test_hash",
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234567890",
        "GOOGLE_API_KEY": "test_google_api_key",
        "LOG_LEVEL": "DEBUG",
        "ENVIRONMENT": "test"
    }
    
    # Set environment variables
    for key, value in test_vars.items():
        os.environ[key] = value
    
    yield test_vars
    
    # Cleanup
    for key in test_vars.keys():
        os.environ.pop(key, None)


@pytest.fixture
def sample_telegram_event():
    """Create a sample Telegram event for testing."""
    event = Mock()
    event.message = Mock()
    event.message.id = 12345
    event.message.text = "This is a test message"
    event.message.date = Mock()
    event.message.date.timestamp.return_value = 1640995200.0  # 2022-01-01 10:00:00
    event.message.peer_id = Mock()
    event.message.peer_id.channel_id = 1001234567890
    event.message.media = None
    return event


# Test markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    ) 