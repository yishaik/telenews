"""
Tel-Insights Smart Analysis Service Main Entry Point

This module provides the main entry point for the Smart Analysis microservice.
It runs the MCP server and periodic alert checking.
"""

import asyncio
import signal
import sys
from typing import Optional

import uvicorn

from shared.config import get_settings
from shared.database import init_db
from shared.logging import configure_logging, get_logger

from .mcp_server import get_mcp_server

# Configure logging
configure_logging("smart_analysis")
logger = get_logger(__name__)


class SmartAnalysisService:
    """Main Smart Analysis service."""
    
    def __init__(self) -> None:
        self.mcp_server = get_mcp_server()
        self.running = False
        self.settings = get_settings()
        self.alert_check_task: Optional[asyncio.Task] = None
    
    def initialize(self) -> None:
        """Initialize the service."""
        try:
            logger.info("Initializing Smart Analysis Service...")
            
            # Initialize database
            init_db()
            
            logger.info("Smart Analysis Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Smart Analysis Service: {e}")
            raise
    
    async def start_alert_checker(self) -> None:
        """Start periodic alert checking task."""
        
        async def alert_check_loop():
            """Periodic alert checking loop."""
            while self.running:
                try:
                    logger.debug("Running periodic alert check...")
                    
                    # Check for alerts
                    triggered_alerts = self.mcp_server.alert_analyzer.check_frequency_alerts()
                    
                    if triggered_alerts:
                        logger.info(f"Found {len(triggered_alerts)} triggered alerts")
                        # TODO: Send alerts to alerting service
                        # For now, just log them
                        for alert in triggered_alerts:
                            logger.info(
                                "Alert triggered",
                                alert_id=alert['alert_id'],
                                config_name=alert['config_name'],
                                message_count=alert['message_count']
                            )
                    
                    # Wait 5 minutes before next check
                    await asyncio.sleep(300)
                    
                except Exception as e:
                    logger.error(f"Error in alert check loop: {e}")
                    await asyncio.sleep(60)  # Wait 1 minute on error
        
        if self.running:
            self.alert_check_task = asyncio.create_task(alert_check_loop())
    
    async def start(self) -> None:
        """Start the service."""
        if not self.mcp_server:
            self.initialize()
        
        try:
            logger.info("Starting Smart Analysis Service...")
            self.running = True
            
            # Start periodic alert checking
            await self.start_alert_checker()
            
            # Start the FastAPI server
            config = uvicorn.Config(
                app=self.mcp_server.get_app(),
                host="0.0.0.0",
                port=int(self.settings.service_urls.smart_analysis_url.split(':')[-1]) if ':' in self.settings.service_urls.smart_analysis_url else 8003,
                log_config=None  # Use our logging configuration
            )
            
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            logger.error(f"Error in Smart Analysis Service: {e}")
            raise
        finally:
            self.running = False
    
    async def stop(self) -> None:
        """Stop the service gracefully."""
        logger.info("Stopping Smart Analysis Service...")
        
        self.running = False
        
        if self.alert_check_task:
            self.alert_check_task.cancel()
            try:
                await self.alert_check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Smart Analysis Service stopped")


# Global service instance
service = SmartAnalysisService()


async def main() -> None:
    """Main function."""
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        # Create a new event loop for cleanup if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(service.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await service.stop()


def run_smart_analysis() -> None:
    """Run the Smart Analysis service."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Failed to run Smart Analysis service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    run_smart_analysis() 