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
            
            logger.info("MessageProducer connected to RabbitMQ")
            
        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise MessageQueueError(f"RabbitMQ connection failed: {e}")
    
    def _declare_queues(self) -> None:
        """Declare all required queues."""
        queues = [
            settings.rabbitmq.queue_new_message,
            settings.rabbitmq.queue_dead_letter,
        ]
        
        for queue_name in queues:
            self.channel.queue_declare(
                queue=queue_name,
                durable=True,
                arguments={
                    'x-dead-letter-exchange': settings.rabbitmq.exchange,
                    'x-dead-letter-routing-key': settings.rabbitmq.queue_dead_letter,
                }
            )
            
            # Bind queue to exchange
            self.channel.queue_bind(
                exchange=settings.rabbitmq.exchange,
                queue=queue_name,
                routing_key=queue_name
            )
    
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
                "Message published",
                exchange=exchange_name,
                routing_key=routing_key,
                message_id=message.get('message_id', 'unknown')
            )
            
            return True
            
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Failed to publish message: {e}")
            # Try to reconnect
            self._setup_connection()
            raise MessageQueueError(f"Failed to publish message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error publishing message: {e}")
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
            
            logger.info(f"MessageConsumer connected to queue: {self.queue_name}")
            
        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise MessageQueueError(f"RabbitMQ connection failed: {e}")
    
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
            message = json.loads(body.decode('utf-8'))
            
            logger.info(
                "Message received",
                queue=self.queue_name,
                message_id=message.get('message_id', 'unknown'),
                event_type=message.get('event_type', 'unknown')
            )
            
            # Process message with callback
            success = self.callback(message)
            
            if success:
                # Acknowledge message
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(
                    "Message processed successfully",
                    queue=self.queue_name,
                    message_id=message.get('message_id', 'unknown')
                )
            else:
                # Reject message and send to dead letter queue
                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=False
                )
                logger.warning(
                    "Message processing failed, sent to dead letter queue",
                    queue=self.queue_name,
                    message_id=message.get('message_id', 'unknown')
                )
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
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
            logger.info("Consumer interrupted by user")
            self.stop_consuming()
        
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            raise MessageQueueError(f"Consumer error: {e}")
    
    def stop_consuming(self) -> None:
        """Stop consuming messages."""
        if self.channel:
            self.channel.stop_consuming()
            logger.info("Stopped consuming messages")
    
    def close(self) -> None:
        """Close the connection to RabbitMQ."""
        self.stop_consuming()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("MessageConsumer connection closed")


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