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
        self.llm_client = get_llm_client()
        self.prompt_manager = get_prompt_manager()
        self.logger.info("MessageProcessor initialized")
    
    def process_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Process a single message with AI analysis.
        
        Args:
            message_data: Message data from the queue
            
        Returns:
            bool: True if processed successfully
        """
        try:
            message_id = message_data.get('message_id')
            message_text = message_data.get('message_text')
            
            self.logger.info(
                "Processing message",
                message_id=message_id,
                has_text=bool(message_text),
                text_length=len(message_text) if message_text else 0
            )
            
            # Skip if no text to analyze
            if not message_text or not message_text.strip():
                self.logger.info(f"Skipping message {message_id} - no text content")
                return True
            
            # Get analysis prompt
            prompt_template = self.prompt_manager.get_prompt("text_analysis")
            if not prompt_template:
                self.logger.error("Text analysis prompt not found")
                return False
            
            # Format prompt
            formatted_prompt = self.prompt_manager.format_prompt(
                prompt_template,
                message_text=message_text
            )
            
            # Generate AI analysis
            response = self.llm_client.generate_content(formatted_prompt)
            
            # Parse JSON response
            ai_metadata = self._parse_ai_response(response.content)
            if not ai_metadata:
                self.logger.error(f"Failed to parse AI response for message {message_id}")
                return False
            
            # Add processing metadata
            ai_metadata.update({
                "analysis_model": response.model,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "processing_version": "1.0"
            })
            
            # Store metadata in database
            success = self._store_ai_metadata(message_id, ai_metadata)
            
            if success:
                self.logger.info(
                    "Message processed successfully",
                    message_id=message_id,
                    summary_length=len(ai_metadata.get('summary', '')),
                    topics_count=len(ai_metadata.get('topics', [])),
                    sentiment=ai_metadata.get('sentiment'),
                    confidence=ai_metadata.get('confidence_score')
                )
            
            return success
            
        except Exception as e:
            self.logger.error(
                f"Error processing message {message_data.get('message_id', 'unknown')}: {e}",
                error_type=type(e).__name__
            )
            return False
    
    def _parse_ai_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse AI response and validate structure.
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Optional[Dict[str, Any]]: Parsed metadata or None if invalid
        """
        try:
            # Clean response text (remove markdown code blocks if present)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            metadata = json.loads(cleaned_text)
            
            # Validate required fields
            required_fields = ['summary', 'topics', 'sentiment', 'keywords']
            for field in required_fields:
                if field not in metadata:
                    self.logger.warning(f"Missing required field in AI response: {field}")
                    return None
            
            # Validate data types
            if not isinstance(metadata.get('topics'), list):
                metadata['topics'] = []
            if not isinstance(metadata.get('keywords'), list):
                metadata['keywords'] = []
            if not isinstance(metadata.get('entities'), dict):
                metadata['entities'] = {}
            
            # Ensure confidence score is a float between 0 and 1
            confidence = metadata.get('confidence_score', 0.5)
            try:
                confidence = float(confidence)
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                confidence = 0.5
            metadata['confidence_score'] = confidence
            
            return metadata
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            self.logger.debug(f"Raw response: {response_text[:500]}...")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing AI response: {e}")
            return None
    
    def _store_ai_metadata(self, message_id: str, ai_metadata: Dict[str, Any]) -> bool:
        """
        Store AI metadata in the database.
        
        Args:
            message_id: Telegram message ID
            ai_metadata: Processed AI metadata
            
        Returns:
            bool: True if stored successfully
        """
        db = next(get_sync_db())
        
        try:
            # Find the message in the database
            message = db.query(Message).filter(
                Message.telegram_message_id == int(message_id)
            ).first()
            
            if not message:
                self.logger.error(f"Message {message_id} not found in database")
                return False
            
            # Update with AI metadata
            message.ai_metadata = ai_metadata
            db.commit()
            
            self.logger.debug(f"AI metadata stored for message {message_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing AI metadata for message {message_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()


class AIAnalysisConsumer(LoggingMixin):
    """
    Message queue consumer for AI analysis.
    """
    
    def __init__(self):
        """Initialize the AI analysis consumer."""
        self.processor = MessageProcessor()
        self.consumer = None
        self.logger.info("AIAnalysisConsumer initialized")
    
    def message_callback(self, message_data: Dict[str, Any]) -> bool:
        """
        Callback function for processing queue messages.
        
        Args:
            message_data: Message data from the queue
            
        Returns:
            bool: True if message was processed successfully
        """
        try:
            # Process the message
            return self.processor.process_message(message_data)
            
        except Exception as e:
            self.logger.error(f"Error in message callback: {e}")
            return False
    
    def start_consuming(self) -> None:
        """
        Start consuming messages from the queue.
        """
        try:
            self.consumer = create_consumer(
                queue_name=settings.rabbitmq.queue_new_message,
                callback=self.message_callback
            )
            
            self.logger.info("Starting AI analysis message consumption...")
            self.consumer.start_consuming()
            
        except KeyboardInterrupt:
            self.logger.info("AI analysis consumer stopped by user")
        except Exception as e:
            self.logger.error(f"Error in AI analysis consumer: {e}")
            raise
        finally:
            if self.consumer:
                self.consumer.close()
    
    def stop_consuming(self) -> None:
        """Stop consuming messages."""
        if self.consumer:
            self.consumer.stop_consuming()
            self.logger.info("AI analysis consumer stopped") 