"""
Tel-Insights Telegram Client

Telegram client implementation using Telethon for message aggregation.
Connects as a user to monitor channels and process incoming messages.
"""

import asyncio
import hashlib
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import (
    Channel,
    DocumentAttributeFilename,
    Message,
    MessageMediaDocument,
    MessageMediaPhoto,
    User,
)

from shared.config import get_settings
from shared.database import get_db_session
from shared.logging import LoggingMixin, get_logger
from shared.messaging import MessageProducer, create_new_message_event
from shared.models import Channel as ChannelModel, Media, Message as MessageModel

settings = get_settings()
logger = get_logger(__name__)


class TelegramAggregator(LoggingMixin):
    """
    Telegram message aggregator using Telethon client.
    
    This class handles:
    - Connecting to Telegram as a user
    - Monitoring configured channels
    - Processing incoming messages
    - Media hashing and deduplication
    - Publishing events to message queue
    """
    
    def __init__(self) -> None:
        self.client: Optional[TelegramClient] = None
        self.message_producer: Optional[MessageProducer] = None
        self.monitored_channels: List[str] = []
        self.running = False
        
    async def initialize(self) -> None:
        """
        Initialize the Telegram client and message producer.
        """
        try:
            # Initialize Telegram client
            self.client = TelegramClient(
                settings.telegram.session_file,
                int(settings.telegram.api_id),
                settings.telegram.api_hash
            )
            
            # Initialize message producer
            self.message_producer = MessageProducer()
            
            # Parse monitored channels from settings
            if settings.app.monitored_channels:
                self.monitored_channels = [
                    channel.strip() for channel in settings.app.monitored_channels
                    if channel.strip()
                ]
            
            self.logger.info(
                "TelegramAggregator initialized",
                monitored_channels_count=len(self.monitored_channels)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to initialize TelegramAggregator: {e}")
            raise
    
    async def connect(self) -> None:
        """
        Connect to Telegram and authenticate.
        """
        if not self.client:
            await self.initialize()
        
        try:
            await self.client.start()
            
            # Get user info
            me = await self.client.get_me()
            self.logger.info(
                "Connected to Telegram",
                user_id=me.id,
                username=me.username,
                first_name=me.first_name
            )
            
            # Register monitored channels in database
            await self._register_channels()
            
            # Set up event handlers
            self._setup_event_handlers()
            
        except SessionPasswordNeededError:
            self.logger.error("Two-factor authentication is enabled. Please set up session manually.")
            raise
        except Exception as e:
            self.logger.error(f"Failed to connect to Telegram: {e}")
            raise
    
    def _setup_event_handlers(self) -> None:
        """
        Set up event handlers for incoming messages.
        """
        @self.client.on(events.NewMessage(chats=self.monitored_channels))
        async def handle_new_message(event):
            """Handle new messages from monitored channels."""
            await self._process_message(event)
        
        self.logger.info("Event handlers registered for monitored channels")
    
    async def _register_channels(self) -> None:
        """
        Register monitored channels in the database.
        """
        db = get_db_session()
        
        try:
            for channel_identifier in self.monitored_channels:
                try:
                    # Get channel entity
                    entity = await self.client.get_entity(channel_identifier)
                    
                    if isinstance(entity, Channel):
                        # Check if channel already exists in database
                        existing_channel = db.query(ChannelModel).filter(
                            ChannelModel.id == entity.id
                        ).first()
                        
                        if not existing_channel:
                            # Create new channel record
                            channel = ChannelModel(
                                id=entity.id,
                                name=entity.title or "Unknown",
                                username=entity.username
                            )
                            db.add(channel)
                            db.commit()
                            
                            self.logger.info(
                                "Channel registered",
                                channel_id=entity.id,
                                channel_name=entity.title,
                                username=entity.username
                            )
                        else:
                            self.logger.info(
                                "Channel already registered",
                                channel_id=entity.id,
                                channel_name=existing_channel.name
                            )
                
                except Exception as e:
                    self.logger.error(
                        f"Failed to register channel {channel_identifier}: {e}"
                    )
        
        finally:
            db.close()
    
    async def _process_message(self, event) -> None:
        """
        Process an incoming message event.
        
        Args:
            event: Telethon NewMessage event
        """
        try:
            message: Message = event.message
            
            # Extract basic message information
            message_data = {
                'message_id': str(message.id),
                'channel_id': str(message.peer_id.channel_id),
                'message_text': message.text,
                'message_timestamp': message.date.timestamp(),
            }
            
            # Process media if present
            media_hash = None
            if message.media:
                media_hash = await self._process_media(message)
                message_data['media_hash'] = media_hash
            
            # Store message in database
            await self._store_message(message_data, media_hash)
            
            # Create and publish message event
            event_data = create_new_message_event(**message_data)
            
            success = self.message_producer.publish_new_message_event(event_data)
            
            if success:
                self.logger.info(
                    "Message processed successfully",
                    message_id=message.id,
                    channel_id=message.peer_id.channel_id,
                    has_media=bool(message.media),
                    text_length=len(message.text) if message.text else 0
                )
            else:
                self.logger.error(
                    "Failed to publish message event",
                    message_id=message.id,
                    channel_id=message.peer_id.channel_id
                )
        
        except Exception as e:
            self.logger.error(
                f"Error processing message {message.id}: {e}",
                message_id=message.id,
                channel_id=getattr(message.peer_id, 'channel_id', 'unknown')
            )
    
    async def _process_media(self, message: Message) -> Optional[str]:
        """
        Process media attached to a message.
        
        Args:
            message: Telegram message with media
            
        Returns:
            Optional[str]: SHA256 hash of the media file, or None if processing failed
        """
        try:
            media = message.media
            
            # Download media to calculate hash
            media_bytes = await self.client.download_media(message, file=bytes)
            
            if media_bytes:
                # Calculate SHA256 hash
                media_hash = hashlib.sha256(media_bytes).hexdigest()
                
                # Determine media type and filename
                media_type = "unknown"
                filename = f"{media_hash}"
                file_size = len(media_bytes)
                
                if isinstance(media, MessageMediaPhoto):
                    media_type = "photo"
                    filename += ".jpg"
                elif isinstance(media, MessageMediaDocument):
                    media_type = "document"
                    # Try to get original filename
                    for attr in media.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            # Extract file extension
                            original_name = attr.file_name
                            if '.' in original_name:
                                extension = original_name.split('.')[-1]
                                filename = f"{media_hash}.{extension}"
                            break
                
                # Check if media already exists in database
                db = next(get_sync_db())
                try:
                    existing_media = db.query(Media).filter(
                        Media.media_hash == media_hash
                    ).first()
                    
                    if not existing_media:
                        # TODO: Upload to Google Cloud Storage
                        # For now, we'll just store the metadata
                        storage_url = f"gs://{settings.gcs.bucket_name}/{filename}"
                        
                        # Create media record
                        media_record = Media(
                            media_hash=media_hash,
                            storage_url=storage_url,
                            media_type=media_type,
                            file_size_bytes=file_size
                        )
                        db.add(media_record)
                        db.commit()
                        
                        self.logger.info(
                            "New media processed",
                            media_hash=media_hash[:8],
                            media_type=media_type,
                            file_size=file_size
                        )
                    else:
                        self.logger.info(
                            "Media already exists (deduplicated)",
                            media_hash=media_hash[:8],
                            media_type=media_type
                        )
                
                finally:
                    db.close()
                
                return media_hash
        
        except Exception as e:
            self.logger.error(f"Failed to process media: {e}")
            return None
    
    async def _store_message(self, message_data: Dict, media_hash: Optional[str] = None) -> None:
        """
        Store message in the database.
        
        Args:
            message_data: Message information
            media_hash: SHA256 hash of media if present
        """
        db = get_db_session()
        
        try:
            # Get media ID if media exists
            media_id = None
            if media_hash:
                media_record = db.query(Media).filter(
                    Media.media_hash == media_hash
                ).first()
                if media_record:
                    media_id = media_record.id
            
            # Create message record
            message = MessageModel(
                telegram_message_id=int(message_data['message_id']),
                channel_id=int(message_data['channel_id']),
                message_text=message_data.get('message_text'),
                media_id=media_id,
                message_timestamp=datetime.fromtimestamp(
                    message_data['message_timestamp'],
                    tz=timezone.utc
                )
            )
            
            db.add(message)
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to store message in database: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def start_aggregation(self) -> None:
        """
        Start the message aggregation process.
        This is a blocking operation that runs until stopped.
        """
        if not self.client:
            await self.connect()
        
        try:
            self.running = True
            self.logger.info("Starting message aggregation...")
            
            # Run the client until disconnected
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            self.logger.info("Aggregation stopped by user")
        except Exception as e:
            self.logger.error(f"Error in aggregation loop: {e}")
            raise
        finally:
            self.running = False
    
    async def stop_aggregation(self) -> None:
        """
        Stop the message aggregation process.
        """
        self.running = False
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        
        if self.message_producer:
            self.message_producer.close()
        
        self.logger.info("TelegramAggregator stopped")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_aggregation()


# Datetime imports moved to top of file 