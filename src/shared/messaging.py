"""
Tel-Insights Message Queue Management

RabbitMQ messaging utilities for asynchronous communication between microservices.
Provides producer and consumer classes with error handling and retry logic.
"""

import json
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from .config import get_settings
from .logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class MessageQueueError(Exception):
    """Custom exception for message queue operations."""
    pass


class MessageProducer:
    """
    RabbitMQ message producer for publishing events to queues.
    """
    
    def __init__(self) -> None:
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self._setup_connection()
    
    def _setup_connection(self) -> None:
        """Set up RabbitMQ connection and channel."""
        try:
            # Parse connection parameters
            connection_params = pika.URLParameters(settings.rabbitmq.url)
            
            # Create connection with retry logic
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            # Declare exchange
            self.channel.exchange_declare(
                exchange=settings.rabbitmq.exchange,
                exchange_type='topic',
                durable=True
            )
            
            # Declare queues
            self._declare_queues()
            
            logger.info(
                "MessageProducer connected to RabbitMQ and setup complete.",
                target_url=settings.rabbitmq.url[:settings.rabbitmq.url.find('@')] if '@' in settings.rabbitmq.url else settings.rabbitmq.url,
                exchange=settings.rabbitmq.exchange
            )
            
        except AMQPConnectionError as e:
            logger.error("Failed to connect to RabbitMQ for MessageProducer.", error=str(e), exc_info=True)
            raise MessageQueueError(f"RabbitMQ connection failed: {e}")
        except Exception as e: # Catch any other unexpected errors during setup
            logger.error("Unexpected error during MessageProducer setup.", error=str(e), exc_info=True)
            raise MessageQueueError(f"Unexpected error during MessageProducer setup: {e}")

    
    def _declare_queues(self) -> None:
        """Declare all required queues."""
        queues_to_declare = { # Using a dict for more context in logging
            "new_message": settings.rabbitmq.queue_new_message,
            "dead_letter": settings.rabbitmq.queue_dead_letter,
        }
        
        logger.debug("Declaring RabbitMQ queues...")
        for queue_key, queue_name in queues_to_declare.items():
            logger.debug(f"Declaring queue '{queue_name}' (for {queue_key}).")
            self.channel.queue_declare(
                queue=queue_name,
                durable=True,
                arguments={
                    'x-dead-letter-exchange': settings.rabbitmq.exchange, # DLX for all queues
                    'x-dead-letter-routing-key': settings.rabbitmq.queue_dead_letter, # Default DLQ routing key
                }
            )
            
            # Bind queue to exchange - routing key is typically the queue name itself for this setup
            routing_key_for_bind = queue_name
            logger.debug(f"Binding queue '{queue_name}' to exchange '{settings.rabbitmq.exchange}' with routing key '{routing_key_for_bind}'.")
            self.channel.queue_bind(
                exchange=settings.rabbitmq.exchange,
                queue=queue_name,
                routing_key=routing_key_for_bind # Often same as queue name for direct-to-queue via topic
            )
        logger.info("MessageProducer queues declared and bound.")
    
    def publish_message(
        self,
        routing_key: str,
        message: Dict[str, Any],
        exchange: str = None,
        persistent: bool = True
    ) -> bool:
        """
        Publish a message to the specified queue.
        
        Args:
            routing_key: Queue routing key
            message: Message payload as dictionary
            exchange: Exchange name (defaults to configured exchange)
            persistent: Whether to make message persistent
            
        Returns:
            bool: True if message was published successfully
            
        Raises:
            MessageQueueError: If publishing fails
        """
        if not self.channel:
            self._setup_connection()
        
        try:
            exchange_name = exchange or settings.rabbitmq.exchange
            
            # Serialize message to JSON
            message_body = json.dumps(message, default=str)
            
            # Publish message
            self.channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2 if persistent else 1,  # Make message persistent
                    content_type='application/json',
                    timestamp=int(time.time()),
                )
            )
            
            logger.info(
                "Message published successfully.",
                exchange=exchange_name,
                routing_key=routing_key,
                message_id=message.get('message_id', 'unknown'), # Assuming message has an ID
                message_event_type=message.get('event_type', 'N/A'),
                message_size=len(message_body)
            )
            
            return True
            
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(
                "RabbitMQ connection/channel error while publishing message. Attempting to reconnect.",
                error=str(e),
                exchange=exchange_name,
                routing_key=routing_key,
                exc_info=True
            )
            # Try to reconnect - this might be risky if in a loop
            try:
                self._setup_connection()
                logger.info("Reconnected to RabbitMQ successfully after publish error.")
            except Exception as conn_err:
                logger.error("Failed to reconnect to RabbitMQ after publish error.", reconn_error=str(conn_err))
                raise MessageQueueError(f"Failed to publish message due to AMQP error and failed to reconnect: {e}") from conn_err
            # It might be better to raise and let the caller handle retry logic for publishing
            raise MessageQueueError(f"Failed to publish message: {e}")
        except Exception as e:
            logger.error(
                "Unexpected error publishing message.",
                error=str(e),
                exchange=exchange_name,
                routing_key=routing_key,
                exc_info=True
            )
            raise MessageQueueError(f"Unexpected error: {e}")
    
    def publish_new_message_event(self, message_data: Dict[str, Any]) -> bool:
        """
        Publish a new message received event.
        
        Args:
            message_data: Message data containing all necessary information
            
        Returns:
            bool: True if published successfully
        """
        return self.publish_message(
            routing_key=settings.rabbitmq.queue_new_message,
            message={
                'event_type': 'new_message_received',
                'timestamp': time.time(),
                **message_data
            }
        )
    
    def close(self) -> None:
        """Close the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("MessageProducer connection closed")


class MessageConsumer:
    """
    RabbitMQ message consumer for processing events from queues.
    """
    
    def __init__(self, queue_name: str, callback: Callable[[Dict[str, Any]], bool]) -> None:
        """
        Initialize the message consumer.
        
        Args:
            queue_name: Name of the queue to consume from
            callback: Function to call when a message is received.
                     Should return True if message was processed successfully.
        """
        self.queue_name = queue_name
        self.callback = callback
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self._setup_connection()
    
    def _setup_connection(self) -> None:
        """Set up RabbitMQ connection and channel."""
        try:
            connection_params = pika.URLParameters(settings.rabbitmq.url)
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            # Declare exchange and queue (in case they don't exist)
            self.channel.exchange_declare(
                exchange=settings.rabbitmq.exchange,
                exchange_type='topic',
                durable=True
            )
            
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True,
                arguments={
                    'x-dead-letter-exchange': settings.rabbitmq.exchange,
                    'x-dead-letter-routing-key': settings.rabbitmq.queue_dead_letter,
                }
            )
            
            # Set QoS to process one message at a time
            self.channel.basic_qos(prefetch_count=1)
            logger.debug(f"QoS prefetch_count=1 set for consumer on queue '{self.queue_name}'.")
            
            logger.info(
                f"MessageConsumer connected to RabbitMQ and setup complete for queue: {self.queue_name}",
                target_url=settings.rabbitmq.url[:settings.rabbitmq.url.find('@')] if '@' in settings.rabbitmq.url else settings.rabbitmq.url,
                exchange=settings.rabbitmq.exchange
            )
            
        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ for MessageConsumer on queue '{self.queue_name}'.", error=str(e), exc_info=True)
            raise MessageQueueError(f"RabbitMQ connection failed: {e}")
        except Exception as e: # Catch any other unexpected errors during setup
            logger.error(f"Unexpected error during MessageConsumer setup for queue '{self.queue_name}'.", error=str(e), exc_info=True)
            raise MessageQueueError(f"Unexpected error during MessageConsumer setup: {e}")

    
    def _message_handler(self, channel: BlockingChannel, method, properties, body: bytes) -> None:
        """
        Handle incoming messages.
        
        Args:
            channel: RabbitMQ channel
            method: Delivery method
            properties: Message properties
            body: Message body
        """
        try:
            # Parse JSON message
            message_body_str = body.decode('utf-8') # For logging preview
            message = json.loads(message_body_str)
            
            self.logger.debug( # Changed to debug as it can be very verbose
                "Message received by consumer.",
                queue=self.queue_name,
                message_id=message.get('message_id', 'unknown'),
                event_type=message.get('event_type', 'unknown'),
                message_size=len(body),
                delivery_tag=method.delivery_tag,
                # message_preview=message_body_str[:100] # Optional: log preview, be careful with sensitive data
            )
            
            # Process message with callback
            success = self.callback(message)
            
            if success:
                # Acknowledge message
                logger.debug(f"Acknowledging message (basic_ack) with delivery_tag: {method.delivery_tag}", queue=self.queue_name)
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.info( # Keep info for successful processing confirmation
                    "Message processed successfully and acknowledged.",
                    queue=self.queue_name,
                    message_id=message.get('message_id', 'unknown'),
                    event_type=message.get('event_type', 'unknown')
                )
            else:
                # Reject message and send to dead letter queue (if configured)
                logger.warning(
                    "Message processing failed by callback. Rejecting message (basic_nack).",
                    queue=self.queue_name,
                    message_id=message.get('message_id', 'unknown'),
                    event_type=message.get('event_type', 'unknown'),
                    delivery_tag=method.delivery_tag
                )
                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=False # False means send to DLQ if DLX is configured
                )
        
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse message JSON in consumer.",
                queue=self.queue_name,
                error=str(e),
                raw_body_preview=body.decode('utf-8', errors='ignore')[:200], # Log preview of unparseable body
                delivery_tag=method.delivery_tag if method else None,
                exc_info=True
            )
            if method: channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        except Exception as e:
            logger.error(
                "Unexpected error processing message in consumer.",
                queue=self.queue_name,
                error=str(e),
                delivery_tag=method.delivery_tag if method else None,
                exc_info=True
            )
            if method: channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False) # Ensure nack on unexpected error
    
    def start_consuming(self) -> None:
        """
        Start consuming messages from the queue.
        This is a blocking operation that will run until interrupted.
        """
        if not self.channel:
            self._setup_connection()
        
        try:
            # Set up consumer
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self._message_handler
            )
            
            logger.info(f"Starting to consume messages from queue: {self.queue_name}")
            
            # Start consuming (blocking)
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info(f"Consumer for queue '{self.queue_name}' interrupted by user (KeyboardInterrupt).")
            self.stop_consuming() # Attempt graceful stop
        
        except Exception as e:
            logger.error(f"Critical error in consumer for queue '{self.queue_name}'.", error=str(e), exc_info=True)
            # Depending on the design, may want to attempt reconnection here or let a supervisor handle it.
            raise MessageQueueError(f"Consumer error: {e}")
        finally:
            logger.info(f"Consumer loop for queue '{self.queue_name}' exited.")
            # Close is typically called by the code that created the consumer instance
            # self.close() might be too aggressive here if start_consuming is meant to be restartable
    
    def stop_consuming(self) -> None:
        """Stop consuming messages."""
        if self.channel and self.channel.is_consuming: # Check if it's actually consuming
            logger.info(f"Stopping message consumption for queue '{self.queue_name}'...")
            try:
                self.channel.stop_consuming()
                logger.info(f"Message consumption stopped for queue '{self.queue_name}'.")
            except Exception as e: # stop_consuming can sometimes raise errors if connection is already closing
                logger.warning(f"Error while trying to stop consuming on queue '{self.queue_name}'.", error=str(e), exc_info=True)
        else:
            logger.info(f"Consumer for queue '{self.queue_name}' was not actively consuming or channel closed.")
    
    def close(self) -> None:
        """Close the connection to RabbitMQ."""
        logger.info(f"Attempting to close MessageConsumer connection for queue '{self.queue_name}'.")
        try:
            self.stop_consuming() # Ensure consuming is stopped first
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info(f"MessageConsumer connection for queue '{self.queue_name}' closed successfully.")
            else:
                logger.info(f"MessageConsumer connection for queue '{self.queue_name}' was already closed or not established.")
        except Exception as e:
            logger.error(f"Error during MessageConsumer close for queue '{self.queue_name}'.", error=str(e), exc_info=True)


@contextmanager
def get_message_producer() -> Generator[MessageProducer, None, None]:
    """
    Context manager to get a message producer with automatic cleanup.
    
    Yields:
        MessageProducer: Configured message producer
    """
    producer = MessageProducer()
    try:
        yield producer
    finally:
        producer.close()


def create_consumer(queue_name: str, callback: Callable[[Dict[str, Any]], bool]) -> MessageConsumer:
    """
    Create a message consumer for the specified queue.
    
    Args:
        queue_name: Name of the queue to consume from
        callback: Function to call when a message is received
        
    Returns:
        MessageConsumer: Configured message consumer
    """
    return MessageConsumer(queue_name, callback)


# Message event schemas for type safety
def create_new_message_event(
    message_id: str,
    channel_id: str,
    message_text: str = None,
    media_hash: str = None,
    message_timestamp: float = None
) -> Dict[str, Any]:
    """
    Create a standardized new message event.
    
    Args:
        message_id: Telegram message ID
        channel_id: Channel ID
        message_text: Text content of the message
        media_hash: SHA256 hash of any media
        message_timestamp: Original message timestamp
        
    Returns:
        Dict[str, Any]: Standardized message event
    """
    return {
        'event_type': 'new_message_received',
        'message_id': message_id,
        'channel_id': channel_id,
        'message_text': message_text,
        'media_hash': media_hash,
        'message_timestamp': message_timestamp or time.time(),
        'processing_timestamp': time.time(),
    } 