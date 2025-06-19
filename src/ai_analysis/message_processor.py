"""
Tel-Insights AI Message Processor

Processes messages from the queue using LLM analysis and stores enriched metadata.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from shared.config import get_settings
from shared.database import get_sync_db
from shared.logging import LoggingMixin, get_logger
from shared.messaging import MessageConsumer, create_consumer
from shared.models import Message

from .llm_client import get_llm_client, LLMError
from .prompt_manager import get_prompt_manager

settings = get_settings()
logger = get_logger(__name__)


class MessageProcessor(LoggingMixin):
    """
    Processes messages using AI analysis and stores metadata.
    """
    
    def __init__(self):
        """Initialize the message processor."""
        self.logger.info("Initializing MessageProcessor...")
        self.llm_client = get_llm_client() # LLMClient has its own init logging
        self.prompt_manager = get_prompt_manager() # PromptManager has its own init logging
        self.logger.info(
            "MessageProcessor initialized successfully with LLM client and Prompt manager."
        )
    
    def process_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Process a single message with AI analysis.
        
        Args:
            message_data: Message data from the queue
            
        Returns:
            bool: True if processed successfully
        """
        message_id = message_data.get('message_id', 'unknown_id')
        channel_id = message_data.get('channel_id', 'unknown_channel') # Assuming channel_id might be in message_data

        # Using shared log_message_processing helper
        self.logger.info(
            log_message_processing(message_id, channel_id, "ai_analysis_started", source_event_type=message_data.get("event_type"))
        )

        try:
            message_text = message_data.get('message_text')
            
            self.logger.debug(
                "Message content details for AI processing",
                message_id=message_id,
                has_text=bool(message_text),
                text_length=len(message_text) if message_text else 0
            )
            
            # Skip if no text to analyze
            if not message_text or not message_text.strip():
                self.logger.info(
                    log_message_processing(message_id, channel_id, "skipped_no_text")
                )
                return True # Considered success as no processing needed
            
            # Get analysis prompt
            self.logger.debug(log_function_call("get_prompt", parent_logger=self.logger.name, prompt_name="text_analysis"))
            prompt_template = self.prompt_manager.get_prompt("text_analysis") # PromptManager logs details
            if not prompt_template:
                self.logger.error(
                    log_message_processing(message_id, channel_id, "ai_analysis_failed", error="Text analysis prompt not found")
                )
                return False
            
            # Format prompt
            self.logger.debug(log_function_call("format_prompt", parent_logger=self.logger.name, prompt_name="text_analysis"))
            formatted_prompt = self.prompt_manager.format_prompt( # PromptManager logs details
                prompt_template,
                message_text=message_text
            )
            
            # Generate AI analysis - LLMClient logs details including log_llm_request
            self.logger.debug("Requesting AI analysis from LLM client.", message_id=message_id)
            response = self.llm_client.generate_content(formatted_prompt) # LLMClient has detailed logging
            
            # Parse JSON response
            ai_metadata = self._parse_ai_response(response.content, message_id) # Pass message_id for context
            if not ai_metadata:
                self.logger.error(
                    log_message_processing(message_id, channel_id, "ai_analysis_failed", error="Failed to parse AI response")
                )
                return False
            
            # Add processing metadata
            ai_metadata.update({
                "analysis_model": response.model, # Model used for this analysis
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "processing_version": "1.0" # Version of this processing logic
            })
            
            # Store metadata in database
            # _store_ai_metadata has its own logging including log_database_operation
            success = self._store_ai_metadata(message_id, channel_id, ai_metadata)
            
            if success:
                self.logger.info(
                    log_message_processing(
                        message_id,
                        channel_id,
                        "ai_analysis_completed",
                        summary_length=len(ai_metadata.get('summary', '')),
                        topics_count=len(ai_metadata.get('topics', [])),
                        sentiment=ai_metadata.get('sentiment'),
                        confidence=ai_metadata.get('confidence_score'),
                        model_used=response.model
                    )
                )
            # If not success, _store_ai_metadata would have logged the error.
            # No need to log "ai_analysis_failed" again here unless for a different reason.
            
            return success
            
        except LLMError as e: # Specific exception from LLM client
            self.logger.error(
                log_message_processing(message_id, channel_id, "ai_analysis_failed", error=f"LLM client error: {e}"),
                exc_info=True
            )
            return False
        except Exception as e:
            self.logger.error(
                log_message_processing(message_id, channel_id, "ai_analysis_failed", error=f"Unexpected error: {e}"),
                error_type=type(e).__name__,
                exc_info=True
            )
            return False
    
    def _parse_ai_response(self, response_text: str, message_id: str = "unknown") -> Optional[Dict[str, Any]]:
        """
        Parse AI response and validate structure.
        
        Args:
            response_text: Raw response from LLM
            message_id: Message ID for logging context
            
        Returns:
            Optional[Dict[str, Any]]: Parsed metadata or None if invalid
        """
        self.logger.debug("Starting to parse AI response.", message_id=message_id, response_length=len(response_text))
        try:
            # Clean response text (remove markdown code blocks if present)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
                self.logger.debug("Removed ```json prefix from response.", message_id=message_id)
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
                self.logger.debug("Removed ``` suffix from response.", message_id=message_id)
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            metadata = json.loads(cleaned_text)
            self.logger.debug("Successfully parsed JSON from AI response.", message_id=message_id)
            
            # Validate required fields
            required_fields = ['summary', 'topics', 'sentiment', 'keywords'] # Consider entities, source_type, language as well
            for field in required_fields:
                if field not in metadata:
                    self.logger.warning(
                        f"Missing required field '{field}' in AI response.",
                        message_id=message_id,
                        ai_response_preview=cleaned_text[:200]
                    )
                    # Depending on strictness, might return None here or fill with default.
                    # For now, just warning. If critical, return None.
            
            # Validate/sanitize data types (example)
            if 'topics' in metadata and not isinstance(metadata.get('topics'), list):
                self.logger.warning("AI response 'topics' field is not a list, attempting to sanitize.", message_id=message_id)
                metadata['topics'] = [] if metadata.get('topics') is None else [str(metadata.get('topics'))]
            if 'keywords' in metadata and not isinstance(metadata.get('keywords'), list):
                self.logger.warning("AI response 'keywords' field is not a list, attempting to sanitize.", message_id=message_id)
                metadata['keywords'] = [] if metadata.get('keywords') is None else [str(metadata.get('keywords'))]
            if 'entities' in metadata and not isinstance(metadata.get('entities'), dict):
                self.logger.warning("AI response 'entities' field is not a dict, attempting to sanitize.", message_id=message_id)
                metadata['entities'] = {}

            # Ensure confidence score is a float between 0 and 1
            confidence = metadata.get('confidence_score') # Allow it to be None initially
            if confidence is not None:
                try:
                    confidence = float(confidence)
                    confidence = max(0.0, min(1.0, confidence))
                except (ValueError, TypeError):
                    self.logger.warning(
                        f"Invalid confidence score '{confidence}', defaulting to 0.5.",
                        message_id=message_id
                    )
                    confidence = 0.5
            else: # If confidence_score was not in metadata or was None
                self.logger.debug("Confidence score not provided or None, defaulting to 0.5.", message_id=message_id)
                confidence = 0.5 # Default if not provided or None
            metadata['confidence_score'] = confidence
            
            self.logger.info("Successfully parsed and validated AI response.", message_id=message_id)
            return metadata
            
        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse JSON from AI response.",
                message_id=message_id,
                json_error=str(e),
                response_preview=response_text[:500] + "..." if len(response_text) > 500 else response_text,
                exc_info=True
            )
            return None
        except Exception as e:
            self.logger.error(
                "Unexpected error parsing AI response.",
                message_id=message_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    def _store_ai_metadata(self, message_id: str, channel_id: str, ai_metadata: Dict[str, Any]) -> bool:
        """
        Store AI metadata in the database.
        
        Args:
            message_id: Telegram message ID
            channel_id: Channel ID for logging context
            ai_metadata: Processed AI metadata
            
        Returns:
            bool: True if stored successfully
        """
        self.logger.debug(
            log_database_operation("attempt_store_ai_metadata", Message.__tablename__),
            message_id=message_id,
            channel_id=channel_id
        )
        db = next(get_sync_db())
        
        try:
            # Find the message in the database
            self.logger.debug(log_database_operation("query_message", Message.__tablename__, telegram_message_id=message_id))
            message_record = db.query(Message).filter( # Renamed to avoid conflict
                Message.telegram_message_id == int(message_id)
            ).first()
            
            if not message_record:
                self.logger.error(
                    log_database_operation("query_message_failed", Message.__tablename__, status="not_found"),
                    message_id=message_id,
                    channel_id=channel_id
                )
                return False
            
            # Update with AI metadata
            message_record.ai_metadata = ai_metadata
            db.commit()
            
            self.logger.info(
                log_database_operation("update_success_ai_metadata", Message.__tablename__),
                message_id=message_id,
                db_message_id=message_record.id, # Internal DB ID
                channel_id=channel_id
            )
            return True
            
        except Exception as e:
            self.logger.error(
                log_database_operation("update_failed_ai_metadata", Message.__tablename__, error=str(e)),
                message_id=message_id,
                channel_id=channel_id,
                exc_info=True
            )
            try:
                db.rollback()
                self.logger.info("Database rollback successful after AI metadata store failure.", message_id=message_id)
            except Exception as re:
                self.logger.error("Failed to rollback database transaction.", original_error=str(e), rollback_error=str(re), message_id=message_id)
            return False
        finally:
            db.close()


class AIAnalysisConsumer(LoggingMixin):
    """
    Message queue consumer for AI analysis.
    """
    
    def __init__(self):
        """Initialize the AI analysis consumer."""
        self.logger.info("Initializing AIAnalysisConsumer...")
        self.processor = MessageProcessor() # MessageProcessor has its own init logging
        self.consumer = None # To be initialized in start_consuming
        self.logger.info("AIAnalysisConsumer initialized successfully.")
    
    def message_callback(self, message_data: Dict[str, Any]) -> bool:
        """
        Callback function for processing queue messages.
        
        Args:
            message_data: Message data from the queue
            
        Returns:
            bool: True if message was processed successfully (for ACK)
        """
        message_id = message_data.get('message_id', 'unknown_id')
        event_type = message_data.get('event_type', 'unknown_event')
        self.logger.info(
            "AI analysis callback received message.",
            message_id=message_id,
            event_type=event_type,
            queue_name=settings.rabbitmq.queue_new_message
        )

        try:
            # Process the message - process_message has detailed logging
            success = self.processor.process_message(message_data)
            self.logger.info(
                "Message processing in callback finished.",
                message_id=message_id,
                event_type=event_type,
                successfully_processed=success
            )
            return success # Return status for ACK/NACK by the underlying consumer
            
        except Exception as e:
            # This is a fallback for unexpected errors directly in the callback logic
            # process_message itself should handle its own errors.
            self.logger.error(
                "Unexpected error in AI analysis message_callback.",
                message_id=message_id,
                event_type=event_type,
                error=str(e),
                exc_info=True
            )
            return False # Indicate failure to process
    
    def start_consuming(self) -> None:
        """
        Start consuming messages from the queue.
        """
        self.logger.info(
            "Attempting to start AI analysis message consumption.",
            queue_name=settings.rabbitmq.queue_new_message
        )
        try:
            self.consumer = create_consumer(
                queue_name=settings.rabbitmq.queue_new_message,
                callback=self.message_callback
            )
            
            self.logger.info(
                "AI analysis message consumer started successfully. Waiting for messages...",
                queue_name=settings.rabbitmq.queue_new_message
            )
            self.consumer.start_consuming() # This is a blocking call
            
        except KeyboardInterrupt:
            self.logger.info("AI analysis consumer stopped by user (KeyboardInterrupt).")
        except Exception as e: # Catch other exceptions like RabbitMQ connection issues
            self.logger.error(
                "Critical error in AI analysis consumer.",
                error=str(e),
                queue_name=settings.rabbitmq.queue_new_message,
                exc_info=True
            )
            # Depending on design, might re-raise or attempt restart after backoff
            raise
        finally:
            self.logger.info("AI Analysis consumer loop exited.")
            if self.consumer: # Ensure cleanup if consumer was initialized
                self.consumer.close()
                self.logger.info("RabbitMQ consumer connection closed.")
    
    def stop_consuming(self) -> None:
        """Stop consuming messages (graceful shutdown)."""
        self.logger.info("Attempting to stop AI analysis consumer...")
        if self.consumer:
            self.consumer.stop_consuming() # Signal the consumer to stop
            # Underlying Pika consumer might take a moment to fully stop.
            # Closing is typically handled in the finally block of start_consuming.
            self.logger.info("AI analysis consumer stop signal sent.")
        else:
            self.logger.info("AI analysis consumer was not running or already stopped.")