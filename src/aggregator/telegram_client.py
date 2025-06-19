"""
Tel-Insights Telegram Client

Telegram client implementation using Telethon for message aggregation.
Connects as a user to monitor channels and process incoming messages.
"""

import asyncio
import hashlib
import time
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
from shared.database import get_sync_db
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
        # LoggingMixin provides self.logger, so we can use it directly.
        self.logger.debug("TelegramAggregator instance created.")
        
    async def initialize(self) -> None:
        """
        Initialize the Telegram client and message producer.
        """
        self.logger.info("Initializing TelegramAggregator...")
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
                "TelegramAggregator initialized successfully.",
                monitored_channels_count=len(self.monitored_channels),
                session_file=settings.telegram.session_file
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize TelegramAggregator", error=str(e))
            raise
    
    async def connect(self) -> None:
        """
        Connect to Telegram and authenticate.
        """
        self.logger.info("Attempting to connect to Telegram...")
        if not self.client:
            # Initialize implicitly calls logger.info, so no need to repeat here for that part.
            await self.initialize()
        
        try:
            await self.client.start()
            
            # Get user info
            me = await self.client.get_me()
            self.logger.info(
                "Successfully connected to Telegram",
                user_id=me.id,
                username=me.username,
                first_name=me.first_name,
                phone=me.phone # Added phone for more context
            )
            
            # Register monitored channels in database
            # _register_channels has its own logging
            await self._register_channels()
            
            # Set up event handlers
            # _setup_event_handlers has its own logging
            self._setup_event_handlers()
            
        except SessionPasswordNeededError:
            self.logger.error(
                "Two-factor authentication (2FA) is enabled for this account. "
                "Please generate a session file manually or provide the password. "
                "Refer to Telethon documentation for session handling with 2FA."
            )
            # Potentially guide user for manual session string or password input if interactive
            raise
        except Exception as e:
            self.logger.error("Failed to connect to Telegram", error=str(e))
            raise
    
    def _setup_event_handlers(self) -> None:
        """
        Set up event handlers for incoming messages.
        """
        @self.client.on(events.NewMessage(chats=self.monitored_channels))
        async def handle_new_message(event):
            """Handle new messages from monitored channels."""
            # _process_message has its own detailed logging
            await self._process_message(event)
        
        self.logger.info(
            "Event handlers for NewMessage registered.",
            monitored_channels=self.monitored_channels
        )
    
    async def _register_channels(self) -> None:
        """
        Register monitored channels in the database.
        """
        self.logger.info("Starting channel registration process.")
        db = next(get_sync_db())
        
        try:
            for channel_identifier in self.monitored_channels:
                self.logger.debug(f"Processing channel identifier: {channel_identifier}")
                try:
                    # Get channel entity
                    entity = await self.client.get_entity(channel_identifier)
                    
                    if isinstance(entity, Channel):
                        # Check if channel already exists in database
                        self.logger.debug(
                            log_database_operation(
                                "query",
                                ChannelModel.__tablename__,
                                channel_id=entity.id
                            )
                        )
                        existing_channel = db.query(ChannelModel).filter(
                            ChannelModel.id == entity.id
                        ).first()
                        
                        if not existing_channel:
                            # Create new channel record
                            channel = ChannelModel(
                                id=entity.id,
                                name=entity.title or "Unknown", # Ensure name is not None
                                username=entity.username
                            )
                            db.add(channel)
                            db.commit()
                            self.logger.info(
                                log_database_operation(
                                    "insert",
                                    ChannelModel.__tablename__,
                                    channel_id=entity.id,
                                    channel_name=channel.name,
                                    username=channel.username
                                )
                            )
                        else:
                            self.logger.info(
                                "Channel already registered in database",
                                channel_id=entity.id,
                                channel_name=existing_channel.name,
                                username=existing_channel.username
                            )
                    else:
                        self.logger.warning(
                            "Entity found for identifier is not a Channel.",
                            identifier=channel_identifier,
                            entity_type=type(entity).__name__
                        )
                
                except Exception as e:
                    self.logger.error(
                        "Failed to register channel",
                        channel_identifier=channel_identifier,
                        error=str(e)
                    )
        
        finally:
            db.close()
        self.logger.info("Channel registration process completed.")
    
    async def _process_message(self, event) -> None:
        """
        Process an incoming message event.
        
        Args:
            event: Telethon NewMessage event
        """
        message: Message = event.message
        message_id_str = str(message.id)
        channel_id_str = str(message.peer_id.channel_id) if hasattr(message.peer_id, 'channel_id') else "unknown"

        self.logger.info(log_message_processing(message_id_str, channel_id_str, "started"))

        try:
            # Extract basic message information
            message_data = {
                'message_id': message_id_str,
                'channel_id': channel_id_str,
                'message_text': message.text,
                'message_timestamp': message.date.timestamp(),
            }
            
            # Process media if present
            media_hash = None
            if message.media:
                self.logger.debug("Message contains media, processing.", message_id=message_id_str, channel_id=channel_id_str)
                media_hash = await self._process_media(message) # _process_media has its own logging
                message_data['media_hash'] = media_hash
            
            # Store message in database
            await self._store_message(message_data, media_hash) # _store_message has its own logging
            
            # Create and publish message event
            event_data = create_new_message_event(**message_data)
            
            self.logger.debug(
                "Publishing new message event to queue.",
                message_id=message_id_str,
                channel_id=channel_id_str,
                event_type=event_data["event_type"]
            )
            success = self.message_producer.publish_new_message_event(event_data)
            
            if success:
                self.logger.info(
                    log_message_processing(
                        message_id_str,
                        channel_id_str,
                        "completed_and_published",
                        has_media=bool(message.media),
                        text_length=len(message.text) if message.text else 0,
                        media_hash=media_hash
                    )
                )
            else:
                # This state indicates message was processed and stored, but not published.
                self.logger.error(
                    log_message_processing(
                        message_id_str,
                        channel_id_str,
                        "failed_to_publish",
                        error="MessageProducer.publish_new_message_event returned False"
                    )
                )
        
        except Exception as e:
            self.logger.error(
                log_message_processing(
                    message_id_str,
                    channel_id_str,
                    "failed",
                    error=str(e),
                    exc_info=True # Captures stack trace
                )
            )
    
    async def _process_media(self, message: Message) -> Optional[str]:
        """
        Process media attached to a message.
        
        Args:
            message: Telegram message with media
            
        Returns:
            Optional[str]: SHA256 hash of the media file, or None if processing failed
        """
        message_id = str(message.id)
        channel_id = str(message.peer_id.channel_id) if hasattr(message.peer_id, 'channel_id') else "unknown"
        self.logger.debug(
            "Starting media processing for message.",
            message_id=message_id,
            channel_id=channel_id
        )

        try:
            media = message.media
            
            self.logger.debug("Downloading media.", message_id=message_id, media_type=type(media).__name__)
            # Download media to calculate hash
            media_bytes = await self.client.download_media(message, file=bytes)
            
            if media_bytes:
                # Calculate SHA256 hash
                media_hash = hashlib.sha256(media_bytes).hexdigest()
                self.logger.debug("Media downloaded and hash calculated.", media_hash_prefix=media_hash[:8], message_id=message_id)
                
                # Determine media type and filename
                media_type = "unknown"
                filename = f"{media_hash}" # Default filename
                file_size = len(media_bytes)
                
                if isinstance(media, MessageMediaPhoto):
                    media_type = "photo"
                    filename += ".jpg" # Common extension for photos
                elif isinstance(media, MessageMediaDocument):
                    media_type = "document"
                    # Try to get original filename and extension
                    original_name = "unknown_filename"
                    for attr in media.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            original_name = attr.file_name
                            if '.' in original_name:
                                extension = original_name.split('.')[-1]
                                filename = f"{media_hash}.{extension}"
                            else: # No extension, use a generic one or none
                                filename = f"{media_hash}"
                            break
                    self.logger.debug(
                        "Document media details.",
                        original_filename=original_name,
                        derived_filename=filename,
                        message_id=message_id
                    )
                
                # Check if media already exists in database
                db = next(get_sync_db())
                try:
                    self.logger.debug(
                        log_database_operation(
                            "query",
                            Media.__tablename__,
                            media_hash=media_hash
                        )
                    )
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
                            log_database_operation(
                                "insert",
                                Media.__tablename__,
                                media_hash=media_hash[:8], # Log prefix for brevity
                                media_type=media_type,
                                file_size=file_size,
                                storage_url=storage_url
                            )
                        )
                    else:
                        self.logger.info(
                            "Media already exists in database (deduplicated).",
                            media_hash=media_hash[:8],
                            media_type=existing_media.media_type, # Use existing type
                            existing_media_id=existing_media.id
                        )
                
                finally:
                    db.close()
                
                return media_hash
            else:
                self.logger.warning("Media download returned empty bytes.", message_id=message_id)
                return None
        
        except Exception as e:
            self.logger.error(
                "Failed to process media for message.",
                message_id=message_id,
                channel_id=channel_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    async def _store_message(self, message_data: Dict, media_hash: Optional[str] = None) -> None:
        """
        Store message in the database.
        
        Args:
            message_data: Message information
            media_hash: SHA256 hash of media if present
        """
        message_id = message_data.get('message_id', 'unknown_id')
        channel_id = message_data.get('channel_id', 'unknown_channel')
        self.logger.debug(
            log_database_operation("attempt_store", MessageModel.__tablename__),
            message_id=message_id,
            channel_id=channel_id,
            has_media=bool(media_hash)
        )
        db = next(get_sync_db())
        
        try:
            # Get media ID if media exists
            media_id_fk = None # Renamed to avoid confusion with message_id variable
            if media_hash:
                self.logger.debug(
                    log_database_operation("query", Media.__tablename__, media_hash=media_hash),
                    message_id=message_id
                )
                media_record = db.query(Media).filter(
                    Media.media_hash == media_hash
                ).first()
                if media_record:
                    media_id_fk = media_record.id
                    self.logger.debug("Found media in DB for message.", media_id_fk=media_id_fk, message_id=message_id)
                else:
                    # This case should ideally not happen if _process_media ran correctly and media was present
                    self.logger.warning(
                        "Media hash provided, but media record not found in DB.",
                        media_hash=media_hash,
                        message_id=message_id
                    )
            
            # Create message record
            message_to_store = MessageModel(
                telegram_message_id=int(message_data['message_id']),
                channel_id=int(message_data['channel_id']),
                message_text=message_data.get('message_text'),
                media_id=media_id_fk,
                message_timestamp=datetime.fromtimestamp(
                    float(message_data['message_timestamp']), # Ensure it's float
                    tz=timezone.utc
                )
            )
            
            db.add(message_to_store)
            db.commit()
            db.refresh(message_to_store) # To get the auto-generated primary key if needed elsewhere

            self.logger.info(
                log_database_operation(
                    "insert",
                    MessageModel.__tablename__,
                    message_id=message_to_store.telegram_message_id,
                    channel_id=message_to_store.channel_id,
                    db_message_id=message_to_store.id # internal DB id
                )
            )
            
        except Exception as e:
            self.logger.error(
                log_database_operation(
                    "insert_failed",
                    MessageModel.__tablename__,
                    message_id=message_id,
                    error=str(e)
                ),
                exc_info=True
            )
            try:
                db.rollback()
                self.logger.info("Database rollback successful after error.", message_id=message_id)
            except Exception as re:
                self.logger.error("Failed to rollback database transaction.", original_error=str(e), rollback_error=str(re))
        finally:
            db.close()
    
    async def start_aggregation(self) -> None:
        """
        Start the message aggregation process.
        This is a blocking operation that runs until stopped.
        """
        self.logger.info("Attempting to start message aggregation...")
        if not self.client or not self.client.is_connected():
            # Connect implicitly calls initialize and logs its own stages
            await self.connect()
        
        if not self.client.is_connected():
            self.logger.error("Cannot start aggregation: Telegram client is not connected.")
            return

        try:
            self.running = True
            self.logger.info(
                "Message aggregation started. Client is listening for new messages.",
                monitored_channels=self.monitored_channels
            )
            
            # Run the client until disconnected
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            self.logger.info("Aggregation process interrupted by user (KeyboardInterrupt).")
            # stop_aggregation will be called in finally
        except Exception as e:
            self.logger.error("Unhandled error in aggregation loop.", error=str(e), exc_info=True)
            # Potentially re-raise depending on desired behavior for critical errors
            raise
        finally:
            self.running = False
            self.logger.info("Message aggregation loop ended.")
            # Ensure stop_aggregation is called to clean up
            await self.stop_aggregation() # Call the full stop method
    
    async def stop_aggregation(self) -> None:
        """
        Stop the message aggregation process.
        """
        self.logger.info("Stopping TelegramAggregator...")
        self.running = False # Signal any loops to stop
        
        if self.client and self.client.is_connected():
            self.logger.info("Disconnecting Telegram client...")
            try:
                await self.client.disconnect()
                self.logger.info("Telegram client disconnected successfully.")
            except Exception as e:
                self.logger.error("Error during Telegram client disconnection.", error=str(e))
        else:
            self.logger.info("Telegram client was not connected or already disconnected.")

        if self.message_producer:
            self.logger.info("Closing message producer...")
            try:
                self.message_producer.close()
                self.logger.info("Message producer closed successfully.")
            except Exception as e: # Catch potential errors during producer close
                self.logger.error("Error closing message producer.", error=str(e))
        
        self.logger.info("TelegramAggregator stopped successfully.")
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.logger.debug("TelegramAggregator context manager entered (__aenter__).")
        await self.initialize()
        # connect() is not called here, typically called before start_aggregation
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.logger.debug(
            "TelegramAggregator context manager exiting (__aexit__).",
            exc_type=str(exc_type) if exc_type else None,
            # exc_val=str(exc_val) if exc_val else None # Can be verbose
        )
        await self.stop_aggregation()


# Import datetime here to avoid circular imports
from datetime import datetime, timezone 