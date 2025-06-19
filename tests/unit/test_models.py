"""
Unit tests for Tel-Insights database models.
"""

import pytest
from datetime import datetime, timezone
from shared.models import Channel, Message, Media, User, AlertConfig, Prompt


@pytest.mark.unit
def test_channel_creation(db_session, sample_channel):
    """Test channel model creation and attributes."""
    db_session.add(sample_channel)
    db_session.commit()
    
    # Query the channel back
    channel = db_session.query(Channel).filter(Channel.id == sample_channel.id).first()
    
    assert channel is not None
    assert channel.name == "Test News Channel"
    assert channel.username == "test_news"
    assert channel.ingested_at is not None


@pytest.mark.unit
def test_message_creation(db_session, sample_channel, sample_message):
    """Test message model creation with AI metadata."""
    # First add the channel
    db_session.add(sample_channel)
    db_session.commit()
    
    # Add the message
    db_session.add(sample_message)
    db_session.commit()
    
    # Query the message back
    message = db_session.query(Message).filter(
        Message.telegram_message_id == sample_message.telegram_message_id
    ).first()
    
    assert message is not None
    assert message.message_text == "This is a test news message about technology."
    assert message.ai_metadata["summary"] == "Test news about technology"
    assert "technology" in message.ai_metadata["topics"]
    assert message.ai_metadata["sentiment"] == "neutral"


@pytest.mark.unit
def test_media_creation(db_session, sample_media):
    """Test media model creation and deduplication."""
    db_session.add(sample_media)
    db_session.commit()
    
    # Query the media back
    media = db_session.query(Media).filter(
        Media.media_hash == sample_media.media_hash
    ).first()
    
    assert media is not None
    assert media.media_type == "photo"
    assert media.file_size_bytes == 1024000
    assert "test-bucket" in media.storage_url


@pytest.mark.unit
def test_user_creation(db_session, sample_user):
    """Test user model creation."""
    db_session.add(sample_user)
    db_session.commit()
    
    # Query the user back
    user = db_session.query(User).filter(
        User.telegram_user_id == sample_user.telegram_user_id
    ).first()
    
    assert user is not None
    assert user.first_name == "Test"
    assert user.username == "testuser"


@pytest.mark.unit
def test_alert_config_creation(db_session, sample_user, sample_alert_config):
    """Test alert configuration model creation."""
    # First add the user
    db_session.add(sample_user)
    db_session.commit()
    
    # Add the alert config
    db_session.add(sample_alert_config)
    db_session.commit()
    
    # Query the alert config back
    alert_config = db_session.query(AlertConfig).filter(
        AlertConfig.config_name == sample_alert_config.config_name
    ).first()
    
    assert alert_config is not None
    assert alert_config.criteria["type"] == "frequency"
    assert "AI" in alert_config.criteria["keywords"]
    assert alert_config.is_active is True


@pytest.mark.unit
def test_message_channel_relationship(db_session, sample_channel, sample_message):
    """Test the relationship between messages and channels."""
    # Add channel and message
    db_session.add(sample_channel)
    db_session.add(sample_message)
    db_session.commit()
    
    # Test relationship
    channel = db_session.query(Channel).filter(Channel.id == sample_channel.id).first()
    message = db_session.query(Message).filter(
        Message.telegram_message_id == sample_message.telegram_message_id
    ).first()
    
    assert len(channel.messages) == 1
    assert channel.messages[0].id == message.id
    assert message.channel.name == "Test News Channel"


@pytest.mark.unit
def test_message_media_relationship(db_session, sample_channel, sample_media):
    """Test the relationship between messages and media."""
    # Add channel and media
    db_session.add(sample_channel)
    db_session.add(sample_media)
    db_session.commit()
    
    # Create a message with media
    message = Message(
        telegram_message_id=54321,
        channel_id=sample_channel.id,
        message_text="Message with photo",
        media_id=sample_media.id,
        message_timestamp=datetime.now(timezone.utc)
    )
    db_session.add(message)
    db_session.commit()
    
    # Test relationship
    queried_message = db_session.query(Message).filter(
        Message.telegram_message_id == 54321
    ).first()
    
    assert queried_message.media is not None
    assert queried_message.media.media_type == "photo"
    assert queried_message.media.media_hash == sample_media.media_hash 