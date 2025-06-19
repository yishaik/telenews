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
        self.logger.info("AlertDelivery initialized")
    
    async def deliver_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Deliver an alert to a user.
        
        Args:
            alert_data: Alert data with user_id and alert details
            
        Returns:
            bool: True if delivered successfully
        """
        try:
            user_id = alert_data.get('user_id')
            if not user_id:
                self.logger.error("No user_id in alert data")
                return False
            
            # Format alert message
            message = self._format_alert_message(alert_data)
            
            # Send message to user
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            
            self.logger.info(
                "Alert delivered successfully",
                user_id=user_id,
                alert_id=alert_data.get('alert_id')
            )
            return True
            
        except TelegramError as e:
            self.logger.error(f"Telegram error delivering alert: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error delivering alert: {e}")
            return False
    
    async def deliver_alerts_batch(self, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Deliver multiple alerts in batch.
        
        Args:
            alerts: List of alert data
            
        Returns:
            Dict with success/failure counts
        """
        results = {'success': 0, 'failed': 0}
        
        for alert in alerts:
            success = await self.deliver_alert(alert)
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        
        self.logger.info(
            "Batch alert delivery completed",
            total_alerts=len(alerts),
            successful=results['success'],
            failed=results['failed']
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
        config_name = alert_data.get('config_name', 'Alert')
        message_count = alert_data.get('message_count', 0)
        threshold = alert_data.get('threshold', 0)
        time_window = alert_data.get('time_window_minutes', 0)
        
        # Base alert message
        message = (
            f"🚨 **{config_name} Alert Triggered!**\n\n"
            f"📊 **{message_count}** messages detected\n"
            f"⏰ In the last **{time_window}** minutes\n"
            f"🎯 Threshold: **{threshold}** messages\n\n"
        )
        
        # Add criteria information
        criteria = alert_data.get('criteria', {})
        keywords = criteria.get('keywords', [])
        if keywords:
            message += f"🔍 **Keywords:** {', '.join(keywords)}\n\n"
        
        # Add sample messages if available
        sample_messages = alert_data.get('sample_messages', [])
        if sample_messages:
            message += "📰 **Recent Messages:**\n"
            for i, msg in enumerate(sample_messages[:3], 1):  # Show max 3 samples
                summary = msg.get('summary', msg.get('text', ''))[:100]
                if len(summary) == 100:
                    summary += "..."
                message += f"{i}. {summary}\n"
            
            if len(sample_messages) > 3:
                message += f"... and {len(sample_messages) - 3} more\n"
        
        message += f"\n⏰ {datetime.now().strftime('%H:%M %d/%m/%Y')}"
        
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
        try:
            message = self._format_summary_message(summary_data)
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending summary to user {user_id}: {e}")
            return False
    
    def _format_summary_message(self, summary_data: Dict[str, Any]) -> str:
        """Format summary data into a message."""
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
            for topic, count in list(top_topics.items())[:5]:
                text += f"• {topic.title()}: {count} mentions\n"
        
        return text 