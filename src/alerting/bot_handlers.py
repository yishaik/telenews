"""
Tel-Insights Telegram Bot Handlers

Implements bot commands and user interaction handlers for the alerting system.
"""

import json
from typing import Dict, Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from shared.config import get_settings
from shared.database import get_sync_db
from shared.logging import LoggingMixin, get_logger
from shared.models import User, AlertConfig

settings = get_settings()
logger = get_logger(__name__)

# Conversation states
ALERT_NAME, ALERT_KEYWORDS, ALERT_THRESHOLD, ALERT_WINDOW = range(4)


class TelegramBotHandlers(LoggingMixin):
    """
    Telegram bot command and callback handlers.
    """
    
    def __init__(self):
        """Initialize the bot handlers."""
        self.logger.info("TelegramBotHandlers initialized")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        self.logger.info(f"Start command from user {user.id} ({user.username})")
        
        # Register or update user in database
        self._register_user(user)
        
        welcome_message = (
            f"🎉 Welcome to Tel-Insights, {user.first_name}!\n\n"
            "I'm your intelligent news alert bot.\n\n"
            "Commands:\n"
            "/help - Show help\n"
            "/summary [hours] - Get news summary\n"
            "/trends [hours] - Show topic trends\n"
            "/create_alert - Create new alert\n"
            "/list_alerts - Show your alerts"
        )
        
        keyboard = [
            [InlineKeyboardButton("📊 Latest Summary", callback_data="summary_1h")],
            [InlineKeyboardButton("🚨 Setup Alert", callback_data="setup_alert")],
            [InlineKeyboardButton("📈 Topic Trends", callback_data="trends_24h")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        help_text = (
            "🤖 **Tel-Insights Bot Commands**\n\n"
            "/start - Welcome message\n"
            "/help - Show this help\n"
            "/summary [hours] - Get news summary\n"
            "/trends [hours] - Show topic trends\n"
            "/create_alert - Create alert\n"
            "/list_alerts - Show your alerts\n"
            "/delete_alert [id] - Delete an alert"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /summary command."""
        try:
            # Parse hours parameter (default to 1)
            hours = 1
            if context.args and len(context.args) > 0:
                try:
                    hours = int(context.args[0])
                    hours = max(1, min(hours, 168))  # Limit between 1 and 168 hours
                except ValueError:
                    await update.message.reply_text("⚠️ Invalid hours parameter. Using 1 hour.")
                    hours = 1
            
            # Request summary from Smart Analysis service
            summary_data = await self._get_news_summary(hours)
            
            if summary_data and summary_data.get('message_count', 0) > 0:
                summary_text = self._format_summary(summary_data)
            else:
                summary_text = f"📭 No news found in the last {hours} hour(s)."
            
            await update.message.reply_text(summary_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"Error in summary command: {e}")
            await update.message.reply_text("❌ Failed to get news summary. Please try again later.")
    
    async def trends_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /trends command."""
        try:
            # Parse hours parameter (default to 24)
            hours = 24
            if context.args and len(context.args) > 0:
                try:
                    hours = int(context.args[0])
                    hours = max(1, min(hours, 168))  # Limit between 1 and 168 hours
                except ValueError:
                    await update.message.reply_text("⚠️ Invalid hours parameter. Using 24 hours.")
                    hours = 24
            
            # Request trends from Smart Analysis service
            trends_data = await self._get_topic_trends(hours)
            
            if trends_data and trends_data.get('trends'):
                trends_text = self._format_trends(trends_data)
            else:
                trends_text = f"📊 No trends found in the last {hours} hour(s)."
            
            await update.message.reply_text(trends_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"Error in trends command: {e}")
            await update.message.reply_text("❌ Failed to get topic trends. Please try again later.")
    
    async def create_alert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start alert creation conversation."""
        await update.message.reply_text(
            "🚨 **Create New Alert**\n\n"
            "Let's set up a custom alert for you!\n\n"
            "First, what would you like to name this alert?\n"
            "Example: 'AI News', 'Breaking Tech', 'Market Updates'"
        )
        return ALERT_NAME
    
    async def alert_name_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle alert name input."""
        alert_name = update.message.text.strip()
        
        if len(alert_name) < 3 or len(alert_name) > 50:
            await update.message.reply_text(
                "⚠️ Alert name must be between 3 and 50 characters. Please try again:"
            )
            return ALERT_NAME
        
        context.user_data['alert_name'] = alert_name
        
        await update.message.reply_text(
            f"✅ Alert name: **{alert_name}**\n\n"
            "Now, what keywords should trigger this alert?\n"
            "Enter keywords separated by commas.\n\n"
            "Example: AI, artificial intelligence, machine learning",
            parse_mode='Markdown'
        )
        return ALERT_KEYWORDS
    
    async def alert_keywords_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle alert keywords input."""
        keywords_text = update.message.text.strip()
        keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
        
        if len(keywords) < 1 or len(keywords) > 10:
            await update.message.reply_text(
                "⚠️ Please provide 1-10 keywords separated by commas:"
            )
            return ALERT_KEYWORDS
        
        context.user_data['alert_keywords'] = keywords
        
        await update.message.reply_text(
            f"✅ Keywords: {', '.join(keywords)}\n\n"
            "How many messages should trigger the alert?\n"
            "Enter a number between 1 and 100 (recommended: 5-20):"
        )
        return ALERT_THRESHOLD
    
    async def alert_threshold_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle alert threshold input."""
        try:
            threshold = int(update.message.text.strip())
            if threshold < 1 or threshold > 100:
                raise ValueError()
        except ValueError:
            await update.message.reply_text(
                "⚠️ Please enter a valid number between 1 and 100:"
            )
            return ALERT_THRESHOLD
        
        context.user_data['alert_threshold'] = threshold
        
        await update.message.reply_text(
            f"✅ Threshold: {threshold} messages\n\n"
            "In what time window should we count messages?\n"
            "Enter minutes (15-1440, recommended: 60-240):"
        )
        return ALERT_WINDOW
    
    async def alert_window_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle alert window input and create the alert."""
        try:
            window_minutes = int(update.message.text.strip())
            if window_minutes < 15 or window_minutes > 1440:  # 15 min to 24 hours
                raise ValueError()
        except ValueError:
            await update.message.reply_text(
                "⚠️ Please enter minutes between 15 and 1440 (24 hours):"
            )
            return ALERT_WINDOW
        
        # Create the alert
        user = update.effective_user
        alert_data = {
            'name': context.user_data['alert_name'],
            'keywords': context.user_data['alert_keywords'],
            'threshold': context.user_data['alert_threshold'],
            'window_minutes': window_minutes
        }
        
        success = self._create_user_alert(user.id, alert_data)
        
        if success:
            await update.message.reply_text(
                f"🎉 **Alert Created Successfully!**\n\n"
                f"**Name:** {alert_data['name']}\n"
                f"**Keywords:** {', '.join(alert_data['keywords'])}\n"
                f"**Threshold:** {alert_data['threshold']} messages\n"
                f"**Time Window:** {window_minutes} minutes\n\n"
                "Your alert is now active! 🚨",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ Failed to create alert. Please try again later."
            )
        
        # Clear user data
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel conversation."""
        await update.message.reply_text(
            "❌ Alert creation cancelled. Use /create_alert to start again."
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    async def list_alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list_alerts command."""
        user = update.effective_user
        alerts = self._get_user_alerts(user.id)
        
        if not alerts:
            await update.message.reply_text(
                "📭 You don't have any alerts configured.\n"
                "Use /create_alert to set up your first alert!"
            )
            return
        
        alerts_text = "🚨 **Your Active Alerts:**\n\n"
        for alert in alerts:
            criteria = alert.criteria
            alerts_text += (
                f"**{alert.config_name}** (ID: {alert.id})\n"
                f"Keywords: {', '.join(criteria.get('keywords', []))}\n"
                f"Threshold: {criteria.get('threshold', 'N/A')} messages\n"
                f"Window: {criteria.get('window_minutes', 'N/A')} minutes\n\n"
            )
        
        alerts_text += "Use `/delete_alert [id]` to remove an alert."
        
        await update.message.reply_text(alerts_text, parse_mode='Markdown')
    
    async def delete_alert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /delete_alert command."""
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "⚠️ Usage: `/delete_alert [alert_id]`\n"
                "Use /list_alerts to see your alert IDs.",
                parse_mode='Markdown'
            )
            return
        
        try:
            alert_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("⚠️ Invalid alert ID. Please provide a number.")
            return
        
        user = update.effective_user
        success = self._delete_user_alert(user.id, alert_id)
        
        if success:
            await update.message.reply_text(f"✅ Alert {alert_id} deleted successfully!")
        else:
            await update.message.reply_text(f"❌ Failed to delete alert {alert_id}. Make sure it exists and belongs to you.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            await self.help_command(update, context)
        elif query.data.startswith("summary_"):
            hours = int(query.data.split("_")[1].replace("h", ""))
            context.args = [str(hours)]
            await self.summary_command(update, context)
        elif query.data.startswith("trends_"):
            hours = int(query.data.split("_")[1].replace("h", ""))
            context.args = [str(hours)]
            await self.trends_command(update, context)
        elif query.data == "setup_alert":
            await self.create_alert_command(update, context)
    
    def _register_user(self, user) -> None:
        """Register or update user in database."""
        db = next(get_sync_db())
        
        try:
            existing_user = db.query(User).filter(
                User.telegram_user_id == user.id
            ).first()
            
            if existing_user:
                # Update existing user
                existing_user.first_name = user.first_name
                existing_user.last_name = user.last_name
                existing_user.username = user.username
            else:
                # Create new user
                new_user = User(
                    telegram_user_id=user.id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username
                )
                db.add(new_user)
            
            db.commit()
            self.logger.info(f"User {user.id} registered/updated")
            
        except Exception as e:
            self.logger.error(f"Error registering user {user.id}: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _create_user_alert(self, user_id: int, alert_data: Dict[str, Any]) -> bool:
        """Create a new alert configuration for user."""
        db = next(get_sync_db())
        
        try:
            alert_config = AlertConfig(
                user_id=user_id,
                config_name=alert_data['name'],
                criteria={
                    'type': 'frequency',
                    'keywords': alert_data['keywords'],
                    'threshold': alert_data['threshold'],
                    'window_minutes': alert_data['window_minutes']
                },
                is_active=True
            )
            
            db.add(alert_config)
            db.commit()
            
            self.logger.info(f"Alert created for user {user_id}: {alert_data['name']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating alert for user {user_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def _get_user_alerts(self, user_id: int) -> List[AlertConfig]:
        """Get all alerts for a user."""
        db = next(get_sync_db())
        
        try:
            alerts = db.query(AlertConfig).filter(
                AlertConfig.user_id == user_id,
                AlertConfig.is_active == True
            ).all()
            return alerts
        except Exception as e:
            self.logger.error(f"Error getting alerts for user {user_id}: {e}")
            return []
        finally:
            db.close()
    
    def _delete_user_alert(self, user_id: int, alert_id: int) -> bool:
        """Delete a user's alert configuration."""
        db = next(get_sync_db())
        
        try:
            alert = db.query(AlertConfig).filter(
                AlertConfig.id == alert_id,
                AlertConfig.user_id == user_id
            ).first()
            
            if alert:
                alert.is_active = False
                db.commit()
                self.logger.info(f"Alert {alert_id} deleted for user {user_id}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting alert {alert_id} for user {user_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    async def _get_news_summary(self, hours: int) -> Dict[str, Any]:
        """Get news summary from Smart Analysis service."""
        # TODO: Implement HTTP client to Smart Analysis service
        # For now, return mock data
        return {
            'message_count': 0,
            'summary': 'No recent news available.'
        }
    
    async def _get_topic_trends(self, hours: int) -> Dict[str, Any]:
        """Get topic trends from Smart Analysis service."""
        # TODO: Implement HTTP client to Smart Analysis service
        # For now, return mock data
        return {
            'trends': []
        }
    
    def _format_summary(self, summary_data: Dict[str, Any]) -> str:
        """Format news summary for display."""
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
    
    def _format_trends(self, trends_data: Dict[str, Any]) -> str:
        """Format topic trends for display."""
        trends = trends_data.get('trends', [])
        time_range = trends_data.get('time_range_hours', 24)
        
        text = f"📈 **Topic Trends ({time_range}h)**\n\n"
        
        if not trends:
            text += "No significant trends found."
            return text
        
        for i, trend in enumerate(trends[:10], 1):
            topic = trend['topic'].title()
            count = trend['message_count']
            sentiment = trend['dominant_sentiment']
            
            sentiment_emoji = {
                'positive': '😊',
                'negative': '😔',
                'neutral': '😐'
            }.get(sentiment, '😐')
            
            text += f"{i}. **{topic}** {sentiment_emoji}\n"
            text += f"   {count} messages\n\n"
        
        return text 