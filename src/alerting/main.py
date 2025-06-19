"""
Tel-Insights Alerting Service Main Entry Point

This module provides the main entry point for the Alerting microservice.
It runs the Telegram bot and handles alert delivery.
"""

import asyncio
import signal
import sys
from typing import Optional

from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler

from shared.config import get_settings
from shared.database import init_db
from shared.logging import configure_logging, get_logger

from .bot_handlers import TelegramBotHandlers, ALERT_NAME, ALERT_KEYWORDS, ALERT_THRESHOLD, ALERT_WINDOW
from .alert_delivery import AlertDelivery

# Configure logging
configure_logging("alerting")
logger = get_logger(__name__)


class AlertingService:
    """Main Alerting service that runs the Telegram bot."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.application: Optional[Application] = None
        self.bot_handlers = TelegramBotHandlers()
        self.alert_delivery: Optional[AlertDelivery] = None
        self.running = False
    
    def initialize(self) -> None:
        """Initialize the service."""
        try:
            logger.info("Initializing Alerting Service...")
            
            # Initialize database
            init_db()
            
            # Check bot token
            if not self.settings.telegram.bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN is required")
            
            # Initialize Telegram application
            self.application = Application.builder().token(
                self.settings.telegram.bot_token
            ).build()
            
            # Initialize alert delivery
            self.alert_delivery = AlertDelivery(self.settings.telegram.bot_token)
            
            # Setup handlers
            self._setup_handlers()
            
            logger.info("Alerting Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Alerting Service: {e}")
            raise
    
    def _setup_handlers(self) -> None:
        """Setup Telegram bot handlers."""
        if not self.application:
            raise ValueError("Application not initialized")
        
        # Basic command handlers
        self.application.add_handler(CommandHandler("start", self.bot_handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.bot_handlers.help_command))
        
        # Alert management conversation handler
        alert_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("create_alert", self.bot_handlers.create_alert_command)],
            states={
                ALERT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_handlers.alert_name_received)],
                ALERT_KEYWORDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_handlers.alert_keywords_received)],
                ALERT_THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_handlers.alert_threshold_received)],
                ALERT_WINDOW: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_handlers.alert_window_received)],
            },
            fallbacks=[CommandHandler("cancel", self.bot_handlers.cancel_command)],
        )
        self.application.add_handler(alert_conv_handler)
        
        # Other command handlers
        self.application.add_handler(CommandHandler("list_alerts", self.bot_handlers.list_alerts_command))
        self.application.add_handler(CommandHandler("delete_alert", self.bot_handlers.delete_alert_command))
        
        # Callback query handler for inline buttons
        self.application.add_handler(CallbackQueryHandler(self.bot_handlers.button_callback))
        
        logger.info("Bot handlers configured")
    
    async def start(self) -> None:
        """Start the service."""
        if not self.application:
            self.initialize()
        
        try:
            logger.info("Starting Alerting Service...")
            self.running = True
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Telegram bot is running...")
            
            # Keep the service running
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in Alerting Service: {e}")
            raise
        finally:
            self.running = False
    
    async def stop(self) -> None:
        """Stop the service gracefully."""
        logger.info("Stopping Alerting Service...")
        
        self.running = False
        
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        logger.info("Alerting Service stopped")
    
    async def deliver_alert(self, alert_data: dict) -> bool:
        """Deliver an alert to a user."""
        if not self.alert_delivery:
            logger.error("Alert delivery not initialized")
            return False
        
        return await self.alert_delivery.deliver_alert(alert_data)


# Global service instance
service = AlertingService()


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


def run_alerting() -> None:
    """Run the Alerting service."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Failed to run Alerting service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    run_alerting() 