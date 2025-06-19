"""
Tel-Insights Alert Delivery System

Handles the delivery of alerts to users via Telegram.
"""

import asyncio
from typing import Dict, Any, List
from datetime import datetime

from telegram import Bot
from telegram.error import TelegramError

from shared.config import get_settings
from shared.database import get_sync_db
from shared.logging import LoggingMixin, get_logger
from shared.models import User

settings = get_settings()
logger = get_logger(__name__)


class AlertDelivery(LoggingMixin):
    """
    Handles delivery of alerts to users via Telegram.
    """
    
    def __init__(self, bot_token: str):
        """Initialize alert delivery system."""
        self.bot = Bot(token=bot_token)
        self.logger.info("AlertDelivery initialized.") # Added period
    
    async def deliver_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Deliver an alert to a user.
        
        Args:
            alert_data: Alert data with user_id and alert details
            
        Returns:
            bool: True if delivered successfully
        """
        user_id = alert_data.get('user_id')
        alert_id_val = alert_data.get('alert_id', 'N/A') # Use a placeholder if not present
        config_name = alert_data.get('config_name', 'N/A')

        self.logger.info(
            log_function_call(
                "deliver_alert",
                user_id=user_id,
                alert_id=alert_id_val,
                config_name=config_name
            )
        )

        try:
            if not user_id:
                self.logger.error("Cannot deliver alert: No user_id provided in alert_data.", alert_data_keys=list(alert_data.keys()))
                return False
            
            # Format alert message - _format_alert_message has its own logging
            message = self._format_alert_message(alert_data)
            
            self.logger.debug(f"Attempting to send alert message to user {user_id} for alert {alert_id_val}. Message length: {len(message)}")
            # Send message to user
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown' # Assuming Markdown is used
            )
            
            self.logger.info(
                "Alert delivered successfully via Telegram.",
                user_id=user_id,
                alert_id=alert_id_val,
                config_name=config_name,
                message_length=len(message)
            )
            return True
            
        except TelegramError as e:
            self.logger.error(
                "Telegram API error while delivering alert.",
                user_id=user_id,
                alert_id=alert_id_val,
                error_message=str(e),
                telegram_error_code=e.message, # Specific field from TelegramError
                exc_info=True
            )
            return False
        except Exception as e:
            self.logger.error(
                "Generic error while delivering alert.",
                user_id=user_id,
                alert_id=alert_id_val,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def deliver_alerts_batch(self, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Deliver multiple alerts in batch.
        
        Args:
            alerts: List of alert data
            
        Returns:
            Dict with success/failure counts
        """
        self.logger.info(f"Starting batch alert delivery for {len(alerts)} alerts.")
        results = {'success': 0, 'failed': 0}
        
        for i, alert in enumerate(alerts):
            # deliver_alert has its own detailed logging
            self.logger.debug(f"Processing alert {i+1}/{len(alerts)} in batch: alert_id {alert.get('alert_id', 'N/A')}")
            success = await self.deliver_alert(alert)
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
            
            # Small delay to avoid rate limiting, especially for larger batches
            if len(alerts) > 5 and i < len(alerts) -1 : # Add delay if many alerts, but not after the last one
                 await asyncio.sleep(0.2) # Slightly increased delay
        
        self.logger.info(
            "Batch alert delivery process completed.",
            total_alerts_in_batch=len(alerts),
            successfully_delivered=results['success'],
            failed_to_deliver=results['failed']
        )
        
        return results
    
    def _format_alert_message(self, alert_data: Dict[str, Any]) -> str:
        """
        Format alert data into a user-friendly message.
        
        Args:
            alert_data: Alert data
            
        Returns:
            str: Formatted message
        """
        self.logger.debug(log_function_call("_format_alert_message", alert_data_keys=list(alert_data.keys())))

        config_name = alert_data.get('config_name', 'Alert')
        message_count = alert_data.get('message_count', 0)
        # Assuming threshold and window_minutes are part of alert_data.criteria
        criteria = alert_data.get('criteria', {})
        threshold = criteria.get('threshold', alert_data.get('threshold', 0)) # Fallback if not in criteria
        time_window = criteria.get('window_minutes', alert_data.get('time_window_minutes', 0))
        
        # Base alert message
        message = (
            f"🚨 **{config_name} Alert Triggered!**\n\n"
            f"📊 **{message_count}** messages detected\n"
            f"⏰ In the last **{time_window}** minutes\n"
            f"🎯 Threshold: **{threshold}** messages\n\n"
        )
        
        # Add criteria information
        keywords = criteria.get('keywords', [])
        if keywords:
            message += f"🔍 **Keywords:** {', '.join(keywords)}\n\n"
        
        # Add sample messages if available
        sample_messages = alert_data.get('sample_messages', [])
        if sample_messages:
            message += "📰 **Recent Messages:**\n"
            for i, msg_sample in enumerate(sample_messages[:3], 1):  # Show max 3 samples
                # Assuming msg_sample could be a dict or string
                summary = str(msg_sample.get('summary', msg_sample.get('text', msg_sample)) if isinstance(msg_sample, dict) else msg_sample)[:100]
                if len(summary) == 100: # Ensure ellipsis if truncated
                    summary += "..."
                message += f"{i}. {summary}\n"
            
            if len(sample_messages) > 3:
                message += f"... and {len(sample_messages) - 3} more\n"
        
        message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}" # ISO-like format
        
        self.logger.debug(f"Formatted alert message. Length: {len(message)}", alert_id=alert_data.get('alert_id'))
        return message
    
    async def send_summary_to_user(self, user_id: int, summary_data: Dict[str, Any]) -> bool:
        """
        Send a news summary to a user.
        
        Args:
            user_id: Telegram user ID
            summary_data: Summary data from Smart Analysis
            
        Returns:
            bool: True if sent successfully
        """
        self.logger.info(
            log_function_call("send_summary_to_user", user_id=user_id, summary_data_keys=list(summary_data.keys()))
        )
        try:
            # _format_summary_message has its own logging
            message = self._format_summary_message(summary_data)
            
            self.logger.debug(f"Attempting to send summary message to user {user_id}. Message length: {len(message)}")
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown' # Assuming Markdown
            )
            self.logger.info("Summary sent successfully to user.", user_id=user_id, message_length=len(message))
            return True
            
        except TelegramError as e:
            self.logger.error(
                "Telegram API error while sending summary.",
                user_id=user_id,
                error_message=str(e),
                telegram_error_code=e.message,
                exc_info=True
            )
            return False
        except Exception as e:
            self.logger.error(
                "Generic error sending summary to user.",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    def _format_summary_message(self, summary_data: Dict[str, Any]) -> str:
        """Format summary data into a message."""
        self.logger.debug(log_function_call("_format_summary_message", summary_data_keys=list(summary_data.keys())))
        summary = summary_data.get('summary', 'No summary available.')
        message_count = summary_data.get('message_count', 0)
        time_range = summary_data.get('time_range_hours', 1)
        
        text = f"📊 **News Summary ({time_range}h)**\n\n"
        text += f"📈 {message_count} messages analyzed\n\n"
        text += f"📝 {summary}\n\n"
        
        # Add top topics if available
        top_topics = summary_data.get('top_topics', {})
        if top_topics:
            text += "🔥 **Trending Topics:**\n"
            for topic, count in list(top_topics.items())[:5]: # Show top 5
                text += f"• {topic.title()}: {count} mentions\n"
        
        self.logger.debug(f"Formatted summary message. Length: {len(text)}")
        return text 