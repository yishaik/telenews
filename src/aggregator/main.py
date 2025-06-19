"""
Tel-Insights Aggregator Service Main Entry Point

This module provides the main entry point for the Aggregator microservice.
It handles service initialization, configuration, and graceful shutdown.
"""

import asyncio
import signal
import sys
from typing import Optional

from shared.config import get_settings
from shared.database import init_db
from shared.logging import configure_logging, get_logger

from .telegram_client import TelegramAggregator

# Configure logging for this service
configure_logging("aggregator")
logger = get_logger(__name__)

class AggregatorService:
    """
    Main aggregator service that orchestrates the Telegram message aggregation.
    """
    
    def __init__(self) -> None:
        self.aggregator: Optional[TelegramAggregator] = None
        self.running = False
        self.settings = get_settings()
    
    async def initialize(self) -> None:
        """
        Initialize the aggregator service.
        """
        try:
            logger.info("Initializing Aggregator Service...")
            
            # Initialize database
            logger.info("Initializing database connection...")
            init_db()
            
            # Initialize Telegram aggregator
            logger.info("Initializing Telegram aggregator...")
            self.aggregator = TelegramAggregator()
            await self.aggregator.initialize()
            
            logger.info("Aggregator Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Aggregator Service: {e}")
            raise
    
    async def start(self) -> None:
        """
        Start the aggregator service.
        """
        if not self.aggregator:
            await self.initialize()
        
        try:
            logger.info("Starting Aggregator Service...")
            self.running = True
            
            # Connect to Telegram
            await self.aggregator.connect()
            
            # Start message aggregation
            await self.aggregator.start_aggregation()
            
        except Exception as e:
            logger.error(f"Error in Aggregator Service: {e}")
            raise
        finally:
            self.running = False
    
    async def stop(self) -> None:
        """
        Stop the aggregator service gracefully.
        """
        logger.info("Stopping Aggregator Service...")
        
        self.running = False
        
        if self.aggregator:
            await self.aggregator.stop_aggregation()
        
        logger.info("Aggregator Service stopped")
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the aggregator service.
        
        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            if not self.running:
                return False
            
            if not self.aggregator:
                return False
            
            if not self.aggregator.client or not self.aggregator.client.is_connected():
                return False
            
            return True
        
        except Exception:
            return False


# Global service instance
service = AggregatorService()


async def main() -> None:
    """
    Main function to run the Aggregator service.
    """
    
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(service.stop())
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the service
        await service.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error in Aggregator service: {e}")
        sys.exit(1)
    finally:
        # Ensure cleanup
        await service.stop()


def run_aggregator() -> None:
    """
    Run the aggregator service using asyncio.
    This is the function that should be called from CLI or Docker.
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Failed to run aggregator service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Load environment variables if .env file exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    run_aggregator() 