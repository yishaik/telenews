"""
Tel-Insights AI Analysis Service Main Entry Point
"""

import signal
import sys
from typing import Optional

from shared.config import get_settings
from shared.database import init_db
from shared.logging import configure_logging, get_logger

from .message_processor import AIAnalysisConsumer
from .prompt_manager import initialize_default_prompts

# Configure logging
configure_logging("ai_analysis")
logger = get_logger(__name__)


class AIAnalysisService:
    """Main AI Analysis service."""
    
    def __init__(self) -> None:
        self.consumer: Optional[AIAnalysisConsumer] = None
        self.running = False
        self.settings = get_settings()
    
    def initialize(self) -> None:
        """Initialize the service."""
        try:
            logger.info("Initializing AI Analysis Service...")
            
            init_db()
            initialize_default_prompts()
            
            self.consumer = AIAnalysisConsumer()
            
            logger.info("AI Analysis Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI Analysis Service: {e}")
            raise
    
    def start(self) -> None:
        """Start the service."""
        if not self.consumer:
            self.initialize()
        
        try:
            logger.info("Starting AI Analysis Service...")
            self.running = True
            
            self.consumer.start_consuming()
            
        except Exception as e:
            logger.error(f"Error in AI Analysis Service: {e}")
            raise
        finally:
            self.running = False
    
    def stop(self) -> None:
        """Stop the service gracefully."""
        logger.info("Stopping AI Analysis Service...")
        
        self.running = False
        
        if self.consumer:
            self.consumer.stop_consuming()
        
        logger.info("AI Analysis Service stopped")


# Global service instance
service = AIAnalysisService()


def main() -> None:
    """Main function."""
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        service.stop()


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    main() 