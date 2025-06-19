"""
Tel-Insights Database Models

SQLAlchemy ORM models for the Tel-Insights database schema.
Implements the database schema as specified in the technical blueprint.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BIGINT,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class Channel(Base):
    """
    Telegram channels being monitored for news aggregation.
    
    Attributes:
        id: Telegram's unique channel ID (BIGINT as per Telegram API)
        name: Channel display name
        username: Channel username (without @)
        ingested_at: Timestamp when channel was added to monitoring
    """
    
    __tablename__ = "channels"

    id = Column(BIGINT, primary_key=True, comment="Telegram's unique channel ID")
    name = Column(String(255), nullable=False, comment="Channel display name")
    username = Column(String(255), unique=True, nullable=True, comment="Channel username")
    ingested_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when channel was added"
    )

    # Relationship to messages
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, name='{self.name}', username='{self.username}')>"


class Media(Base):
    """
    Media files with deduplication based on SHA256 hash.
    
    Attributes:
        id: Auto-increment primary key
        media_hash: SHA256 hash of the media file (unique)
        storage_url: URL to the file in Google Cloud Storage
        media_type: Type of media (image, video, document, etc.)
        file_size_bytes: Size of the file in bytes
        created_at: Timestamp when media was first stored
    """
    
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="SHA256 hash of the media file"
    )
    storage_url = Column(Text, nullable=False, comment="URL to file in GCS")
    media_type = Column(String(50), nullable=False, comment="Type of media")
    file_size_bytes = Column(BIGINT, nullable=True, comment="File size in bytes")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when media was stored"
    )

    # Relationship to messages
    messages = relationship("Message", back_populates="media")

    # Index on media_hash for fast deduplication lookups
    __table_args__ = (
        Index("idx_media_hash", "media_hash"),
    )

    def __repr__(self) -> str:
        return f"<Media(id={self.id}, hash='{self.media_hash[:8]}...', type='{self.media_type}')>"


class Message(Base):
    """
    Telegram messages with AI-generated metadata.
    
    Attributes:
        id: Auto-increment primary key
        telegram_message_id: Original Telegram message ID
        channel_id: Foreign key to channels table
        message_text: Text content of the message
        media_id: Foreign key to media table (nullable)
        message_timestamp: Original timestamp of the Telegram message
        created_at: Timestamp when message was stored in our system
        ai_metadata: JSONB field containing AI analysis results
    """
    
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_message_id = Column(
        BIGINT,
        nullable=False,
        comment="Original Telegram message ID"
    )
    channel_id = Column(
        BIGINT,
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to the channel"
    )
    message_text = Column(Text, nullable=True, comment="Text content of the message")
    media_id = Column(
        Integer,
        ForeignKey("media.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to media file"
    )
    message_timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Original Telegram message timestamp"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when stored in our system"
    )
    ai_metadata = Column(
        JSONB,
        nullable=True,
        comment="AI analysis results in JSON format"
    )

    # Relationships
    channel = relationship("Channel", back_populates="messages")
    media = relationship("Media", back_populates="messages")

    # Indexes for performance
    __table_args__ = (
        Index("idx_messages_channel_id", "channel_id"),
        Index("idx_messages_message_timestamp", "message_timestamp"),
        Index("idx_messages_ai_metadata", "ai_metadata", postgresql_using="gin"),  # GIN index for JSONB
        Index("idx_messages_telegram_id_channel", "telegram_message_id", "channel_id"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, channel_id={self.channel_id}, telegram_id={self.telegram_message_id})>"


class User(Base):
    """
    Users who interact with the alerting bot.
    
    Attributes:
        telegram_user_id: Telegram user ID (primary key)
        first_name: User's first name from Telegram
        username: User's username from Telegram
        created_at: Timestamp when user was first registered
    """
    
    __tablename__ = "users"

    telegram_user_id = Column(
        BIGINT,
        primary_key=True,
        comment="Telegram user ID"
    )
    first_name = Column(String(255), nullable=True, comment="User's first name")
    username = Column(String(255), nullable=True, comment="User's username")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="User registration timestamp"
    )

    # Relationship to alert configurations
    alert_configs = relationship("AlertConfig", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.telegram_user_id}, username='{self.username}', name='{self.first_name}')>"


class AlertConfig(Base):
    """
    User-defined alert configurations.
    
    Attributes:
        id: Auto-increment primary key
        user_id: Foreign key to users table
        config_name: User-friendly name for the alert configuration
        criteria: JSONB field containing alert criteria and parameters
        is_active: Boolean flag to enable/disable the alert
        created_at: Timestamp when alert config was created
    """
    
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        BIGINT,
        ForeignKey("users.telegram_user_id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to the user"
    )
    config_name = Column(
        String(100),
        nullable=False,
        comment="User-friendly name for the alert"
    )
    criteria = Column(
        JSONB,
        nullable=False,
        comment="Alert criteria and parameters in JSON format"
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the alert is active"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Alert configuration creation timestamp"
    )

    # Relationship
    user = relationship("User", back_populates="alert_configs")

    # Index for performance
    __table_args__ = (
        Index("idx_alert_configs_user_id", "user_id"),
        Index("idx_alert_configs_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<AlertConfig(id={self.id}, user_id={self.user_id}, name='{self.config_name}', active={self.is_active})>"


class Prompt(Base):
    """
    Prompt templates for LLM analysis with versioning support.
    
    Attributes:
        id: Auto-increment primary key
        name: Unique name for the prompt template
        version: Version number of the prompt
        template: The actual prompt template text
        parameters: JSONB field for prompt parameters and metadata
        is_active: Whether this version is currently active
        created_at: Timestamp when prompt was created
    """
    
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="Prompt template name")
    version = Column(Integer, nullable=False, default=1, comment="Prompt version number")
    template = Column(Text, nullable=False, comment="Prompt template text")
    parameters = Column(
        JSONB,
        nullable=True,
        comment="Prompt parameters and metadata"
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this version is active"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Prompt creation timestamp"
    )

    # Ensure only one active version per prompt name
    __table_args__ = (
        Index("idx_prompts_name_version", "name", "version"),
        Index("idx_prompts_name_active", "name", "is_active"),
        UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )

    def __repr__(self) -> str:
        return f"<Prompt(id={self.id}, name='{self.name}', version={self.version}, active={self.is_active})>"


# Additional utility functions for common queries

def get_ai_metadata_schema() -> Dict[str, Any]:
    """
    Get the expected schema for the ai_metadata JSONB field.
    
    Returns:
        Dict[str, Any]: Schema definition for AI metadata
    """
    return {
        "summary": str,  # Concise summary of the message
        "topics": List[str],  # Main categories/subjects
        "sentiment": str,  # positive, negative, neutral
        "entities": {  # Named entities
            "people": List[str],
            "organizations": List[str],
            "locations": List[str],
            "dates": List[str],
            "other": List[str]
        },
        "keywords": List[str],  # Relevant keywords
        "source_type": str,  # Type of source (news, tech, politics, etc.)
        "confidence_score": float,  # AI confidence in the analysis
        "language": str,  # Detected language
        "analysis_model": str,  # Which model performed the analysis
        "analysis_timestamp": str,  # ISO timestamp of analysis
    }


def get_alert_criteria_schema() -> Dict[str, Any]:
    """
    Get the expected schema for alert criteria JSONB field.
    
    Returns:
        Dict[str, Any]: Schema definition for alert criteria
    """
    return {
        "type": str,  # "frequency", "sentiment", "keyword", "topic"
        "keywords": List[str],  # Keywords to monitor
        "topics": List[str],  # Topics to monitor
        "sentiment": str,  # Sentiment filter
        "threshold": int,  # Alert threshold
        "window_minutes": int,  # Time window for evaluation
        "sources": List[str],  # Channel filters
        "locations": List[str],  # Location filters
        "logic": str,  # "AND" or "OR" for multiple criteria
    } 