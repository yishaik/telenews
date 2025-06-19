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
        self.logger.info("TelegramBotHandlers initialized.") # Added period for consistency
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        chat_id = update.effective_chat.id # Useful for group contexts if any

        self.logger.info(
            log_function_call(
                "start_command",
                user_id=user.id,
                username=user.username,
                chat_id=chat_id,
                command_text=update.message.text if update.message else "N/A (no message)"
            )
        )
        
        try:
            # Register or update user in database
            self._register_user(user) # This method will have its own logging
        
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
        self.logger.debug(f"Welcome message sent to user {user.id}.")

        except Exception as e:
            self.logger.error(
                "Error processing /start command",
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            try:
                if update.message:
                    await update.message.reply_text("An error occurred while starting. Please try again later.")
            except Exception as send_error:
                self.logger.error("Failed to send error message to user during /start.", error=str(send_error))
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        user = update.effective_user
        self.logger.info(
            log_function_call(
                "help_command",
                user_id=user.id,
                username=user.username,
                chat_id=update.effective_chat.id
            )
        )
        try:
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
            self.logger.debug(f"Help message sent to user {user.id}.")
        except Exception as e:
            self.logger.error(
                "Error processing /help command",
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            # Optionally send an error message to user if appropriate
    
    async def summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /summary command."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        raw_args = context.args

        self.logger.info(
            log_function_call(
                "summary_command",
                user_id=user.id,
                username=user.username,
                chat_id=chat_id,
                raw_args=raw_args
            )
        )
        try:
            # Parse hours parameter (default to 1)
            hours = 1
            if context.args and len(context.args) > 0:
                try:
                    hours = int(context.args[0])
                    hours = max(1, min(hours, 168))  # Limit between 1 and 168 hours
                    self.logger.debug(f"Parsed hours for summary: {hours}", user_id=user.id)
                except ValueError:
                    self.logger.warning("Invalid hours parameter for summary.", user_id=user.id, provided_arg=context.args[0])
                    await update.message.reply_text("⚠️ Invalid hours parameter. Using 1 hour.")
                    hours = 1
            
            # Request summary from Smart Analysis service
            self.logger.debug(f"Requesting news summary for {hours} hours (mock).", user_id=user.id)
            summary_data = await self._get_news_summary(hours) # This is a mock
            
            if summary_data and summary_data.get('message_count', 0) > 0:
                summary_text = self._format_summary(summary_data) # format_summary has debug log
                self.logger.info("News summary generated.", user_id=user.id, message_count=summary_data.get('message_count'), hours=hours)
            else:
                summary_text = f"📭 No news found in the last {hours} hour(s)."
                self.logger.info("No news found for summary.", user_id=user.id, hours=hours)
            
            await update.message.reply_text(summary_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(
                "Error in /summary command",
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            await update.message.reply_text("❌ Failed to get news summary. Please try again later.")
    
    async def trends_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /trends command."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        raw_args = context.args

        self.logger.info(
            log_function_call(
                "trends_command",
                user_id=user.id,
                username=user.username,
                chat_id=chat_id,
                raw_args=raw_args
            )
        )
        try:
            # Parse hours parameter (default to 24)
            hours = 24
            if context.args and len(context.args) > 0:
                try:
                    hours = int(context.args[0])
                    hours = max(1, min(hours, 168))  # Limit between 1 and 168 hours
                    self.logger.debug(f"Parsed hours for trends: {hours}", user_id=user.id)
                except ValueError:
                    self.logger.warning("Invalid hours parameter for trends.", user_id=user.id, provided_arg=context.args[0])
                    await update.message.reply_text("⚠️ Invalid hours parameter. Using 24 hours.")
                    hours = 24
            
            # Request trends from Smart Analysis service
            self.logger.debug(f"Requesting topic trends for {hours} hours (mock).", user_id=user.id)
            trends_data = await self._get_topic_trends(hours) # This is a mock
            
            if trends_data and trends_data.get('trends'):
                trends_text = self._format_trends(trends_data) # format_trends has debug log
                self.logger.info("Topic trends generated.", user_id=user.id, trends_count=len(trends_data.get('trends')), hours=hours)
            else:
                trends_text = f"📊 No trends found in the last {hours} hour(s)."
                self.logger.info("No topic trends found.", user_id=user.id, hours=hours)
            
            await update.message.reply_text(trends_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(
                "Error in /trends command",
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            await update.message.reply_text("❌ Failed to get topic trends. Please try again later.")
    
    async def create_alert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start alert creation conversation."""
        user = update.effective_user
        self.logger.info(
            log_function_call(
                "create_alert_command (conversation_start)",
                user_id=user.id,
                username=user.username,
                chat_id=update.effective_chat.id if update.effective_chat else "N/A (no chat)",
                message_text=update.message.text if update.message else "N/A (no message text)"
            )
        )
        # Ensure we are using the correct update object that has 'message' if called from button_callback
        reply_target = update.message if hasattr(update, 'message') and update.message else update.callback_query.message

        await reply_target.reply_text(
            "🚨 **Create New Alert**\n\n"
            "Let's set up a custom alert for you!\n\n"
            "First, what would you like to name this alert?\n"
            "Example: 'AI News', 'Breaking Tech', 'Market Updates'"
        )
        self.logger.debug("Requested alert name from user.", user_id=user.id)
        return ALERT_NAME
    
    async def alert_name_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle alert name input."""
        user = update.effective_user
        alert_name = update.message.text.strip()
        self.logger.info(
            log_function_call(
                "alert_name_received (conversation_step)",
                user_id=user.id,
                username=user.username,
                state="ALERT_NAME",
                received_text=alert_name
            )
        )
        
        if len(alert_name) < 3 or len(alert_name) > 50:
            self.logger.debug("Invalid alert name length.", user_id=user.id, alert_name=alert_name)
            await update.message.reply_text(
                "⚠️ Alert name must be between 3 and 50 characters. Please try again:"
            )
            return ALERT_NAME
        
        context.user_data['alert_name'] = alert_name
        self.logger.info(f"Alert name set to '{alert_name}' for user {user.id}.", user_data_preview=context.user_data.get('alert_name'))
        
        await update.message.reply_text(
            f"✅ Alert name: **{alert_name}**\n\n"
            "Now, what keywords should trigger this alert?\n"
            "Enter keywords separated by commas.\n\n"
            "Example: AI, artificial intelligence, machine learning",
            parse_mode='Markdown'
        )
        self.logger.debug("Requested alert keywords from user.", user_id=user.id)
        return ALERT_KEYWORDS
    
    async def alert_keywords_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle alert keywords input."""
        user = update.effective_user
        keywords_text = update.message.text.strip()
        keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
        self.logger.info(
            log_function_call(
                "alert_keywords_received (conversation_step)",
                user_id=user.id,
                username=user.username,
                state="ALERT_KEYWORDS",
                received_text=keywords_text,
                parsed_keywords=keywords
            )
        )
        
        if not (1 <= len(keywords) <= 10): # Check for empty list or too many keywords
            self.logger.debug("Invalid number of keywords.", user_id=user.id, keywords_count=len(keywords), provided_text=keywords_text)
            await update.message.reply_text(
                "⚠️ Please provide 1-10 keywords separated by commas:"
            )
            return ALERT_KEYWORDS
        
        context.user_data['alert_keywords'] = keywords
        self.logger.info(f"Alert keywords set for user {user.id}.", user_data_preview=context.user_data.get('alert_keywords'))

        await update.message.reply_text(
            f"✅ Keywords: {', '.join(keywords)}\n\n"
            "How many messages should trigger the alert?\n"
            "Enter a number between 1 and 100 (recommended: 5-20):"
        )
        self.logger.debug("Requested alert threshold from user.", user_id=user.id)
        return ALERT_THRESHOLD
    
    async def alert_threshold_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle alert threshold input."""
        user = update.effective_user
        threshold_text = update.message.text.strip()
        self.logger.info(
            log_function_call(
                "alert_threshold_received (conversation_step)",
                user_id=user.id,
                username=user.username,
                state="ALERT_THRESHOLD",
                received_text=threshold_text
            )
        )
        try:
            threshold = int(threshold_text)
            if not (1 <= threshold <= 100):
                raise ValueError("Threshold out of range")
        except ValueError as e:
            self.logger.debug(f"Invalid alert threshold: {threshold_text}", user_id=user.id, error=str(e))
            await update.message.reply_text(
                "⚠️ Please enter a valid number between 1 and 100:"
            )
            return ALERT_THRESHOLD
        
        context.user_data['alert_threshold'] = threshold
        self.logger.info(f"Alert threshold set for user {user.id}.", user_data_preview=context.user_data.get('alert_threshold'))
        
        await update.message.reply_text(
            f"✅ Threshold: {threshold} messages\n\n"
            "In what time window should we count messages?\n"
            "Enter minutes (15-1440, recommended: 60-240):"
        )
        self.logger.debug("Requested alert window from user.", user_id=user.id)
        return ALERT_WINDOW
    
    async def alert_window_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle alert window input and create the alert."""
        user = update.effective_user
        window_text = update.message.text.strip()
        self.logger.info(
            log_function_call(
                "alert_window_received (conversation_step_final)",
                user_id=user.id,
                username=user.username,
                state="ALERT_WINDOW",
                received_text=window_text,
                current_user_data_keys=list(context.user_data.keys()) # Log keys to confirm data presence
            )
        )
        try:
            window_minutes = int(window_text)
            if not (15 <= window_minutes <= 1440):  # 15 min to 24 hours
                raise ValueError("Window minutes out of range")
        except ValueError as e:
            self.logger.debug(f"Invalid alert window: {window_text}", user_id=user.id, error=str(e))
            await update.message.reply_text(
                "⚠️ Please enter minutes between 15 and 1440 (24 hours):"
            )
            return ALERT_WINDOW
        
        # Create the alert
        alert_data_to_save = { # Renamed to avoid confusion
            'name': context.user_data.get('alert_name', 'Unnamed Alert'), # Add default if key missing
            'keywords': context.user_data.get('alert_keywords', []),
            'threshold': context.user_data.get('alert_threshold', 5), # Default threshold
            'window_minutes': window_minutes
        }
        
        # _create_user_alert has its own logging including DB operations
        success = self._create_user_alert(user.id, alert_data_to_save)
        
        if success:
            self.logger.info("Alert creation successful.", user_id=user.id, alert_name=alert_data_to_save['name'])
            await update.message.reply_text(
                f"🎉 **Alert Created Successfully!**\n\n"
                f"**Name:** {alert_data_to_save['name']}\n"
                f"**Keywords:** {', '.join(alert_data_to_save['keywords'])}\n"
                f"**Threshold:** {alert_data_to_save['threshold']} messages\n"
                f"**Time Window:** {window_minutes} minutes\n\n"
                "Your alert is now active! 🚨",
                parse_mode='Markdown'
            )
        else:
            # Error already logged by _create_user_alert
            await update.message.reply_text(
                "❌ Failed to create alert. An error occurred. Please try again later."
            )
        
        # Clear user data
        self.logger.debug("Clearing user_data after conversation completion/failure.", user_id=user.id, keys_before_clear=list(context.user_data.keys()))
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel conversation."""
        user = update.effective_user
        self.logger.info(
            log_function_call(
                "cancel_command (conversation_cancel)",
                user_id=user.id,
                username=user.username,
                current_user_data_keys=list(context.user_data.keys())
            )
        )
        await update.message.reply_text(
            "❌ Alert creation cancelled. Use /create_alert to start again."
        )
        self.logger.debug("Clearing user_data due to cancellation.", user_id=user.id)
        context.user_data.clear()
        return ConversationHandler.END
    
    async def list_alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list_alerts command."""
        user = update.effective_user
        self.logger.info(
            log_function_call(
                "list_alerts_command",
                user_id=user.id,
                username=user.username
            )
        )
        # _get_user_alerts has its own logging including DB operations
        alerts = self._get_user_alerts(user.id)
        
        if not alerts:
            self.logger.info("No alerts found for user.", user_id=user.id)
            await update.message.reply_text(
                "📭 You don't have any alerts configured.\n"
                "Use /create_alert to set up your first alert!"
            )
            return
        
        self.logger.info(f"Found {len(alerts)} alerts for user {user.id}.")
        alerts_text = "🚨 **Your Active Alerts:**\n\n"
        for alert_config_item in alerts: # Renamed to avoid confusion
            criteria = alert_config_item.criteria # criteria is already a dict
            alerts_text += (
                f"**{alert_config_item.config_name}** (ID: {alert_config_item.id})\n"
                f"Keywords: {', '.join(criteria.get('keywords', []))}\n"
                f"Threshold: {criteria.get('threshold', 'N/A')} messages\n"
                f"Window: {criteria.get('window_minutes', 'N/A')} minutes\n\n"
            )
        
        alerts_text += "Use `/delete_alert [id]` to remove an alert."
        
        await update.message.reply_text(alerts_text, parse_mode='Markdown')
        self.logger.debug("Alert list sent to user.", user_id=user.id)
    
    async def delete_alert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /delete_alert command."""
        user = update.effective_user
        raw_args = context.args
        self.logger.info(
            log_function_call(
                "delete_alert_command",
                user_id=user.id,
                username=user.username,
                raw_args=raw_args
            )
        )

        if not context.args or len(context.args) != 1:
            self.logger.debug("Invalid arguments for /delete_alert.", user_id=user.id, args=raw_args)
            await update.message.reply_text(
                "⚠️ Usage: `/delete_alert [alert_id]`\n"
                "Use /list_alerts to see your alert IDs.",
                parse_mode='Markdown'
            )
            return
        
        try:
            alert_id_to_delete = int(context.args[0]) # Renamed
            self.logger.debug(f"Attempting to delete alert_id: {alert_id_to_delete}", user_id=user.id)
        except ValueError:
            self.logger.warning("Invalid alert_id format for /delete_alert.", user_id=user.id, provided_alert_id=context.args[0])
            await update.message.reply_text("⚠️ Invalid alert ID. Please provide a number.")
            return
        
        # _delete_user_alert has its own logging including DB operations
        success = self._delete_user_alert(user.id, alert_id_to_delete)
        
        if success:
            # Logged by _delete_user_alert
            await update.message.reply_text(f"✅ Alert {alert_id_to_delete} deleted successfully!")
        else:
            # Logged by _delete_user_alert if alert not found or DB error
            self.logger.warning(f"Failed to delete alert {alert_id_to_delete} for user {user.id} (handler level). It might not exist or not belong to user.", alert_id=alert_id_to_delete)
            await update.message.reply_text(f"❌ Failed to delete alert {alert_id_to_delete}. Make sure it exists and belongs to you.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button callbacks."""
        query = update.callback_query
        user = update.effective_user

        self.logger.info(
            log_function_call(
                "button_callback",
                user_id=user.id,
                username=user.username,
                callback_data=query.data,
                message_id=query.message.message_id if query.message else "N/A"
            )
        )

        await query.answer() # Acknowledge callback
        self.logger.debug("Callback query answered.", user_id=user.id, callback_data=query.data)

        # Ensure effective_message is available for command calls if needed by them
        effective_update_for_commands = update
        if not hasattr(effective_update_for_commands, 'message') or effective_update_for_commands.message is None:
             if query.message: # If original message is available from callback
                effective_update_for_commands.message = query.message
             else: # Fallback if no message context (less likely for these commands)
                self.logger.warning("Button callback has no associated message for reply.", user_id=user.id, callback_data=query.data)
                # Cannot proceed with commands that require a message reply here.
                return


        try:
            if query.data == "help":
                await self.help_command(effective_update_for_commands, context)
            elif query.data.startswith("summary_"):
                hours = int(query.data.split("_")[1].replace("h", ""))
                context.args = [str(hours)] # Set args for the command
                await self.summary_command(effective_update_for_commands, context)
            elif query.data.startswith("trends_"):
                hours = int(query.data.split("_")[1].replace("h", ""))
                context.args = [str(hours)] # Set args for the command
                await self.trends_command(effective_update_for_commands, context)
            elif query.data == "setup_alert":
                if effective_update_for_commands.message: # Check if message context exists for reply
                    await self.create_alert_command(effective_update_for_commands, context)
                else:
                    self.logger.error("Cannot start alert creation from callback: no message context for reply.", user_id=user.id, callback_data=query.data)
                    # Might want to send a new message if possible, or edit if it's an inline keyboard on an ephemeral message
            else:
                self.logger.warning("Unhandled button callback data.", user_id=user.id, callback_data=query.data)
                if effective_update_for_commands.message:
                     await effective_update_for_commands.message.reply_text("Sorry, I didn't understand that action.")

        except Exception as e:
            self.logger.error(
                "Error processing button callback.",
                user_id=user.id,
                callback_data=query.data,
                error=str(e),
                exc_info=True
            )
            try:
                if effective_update_for_commands.message:
                    await effective_update_for_commands.message.reply_text("An error occurred while processing your request. Please try again.")
            except Exception as send_error:
                 self.logger.error("Failed to send error message to user during button_callback.", error=str(send_error), user_id=user.id)

    
    def _register_user(self, user_telegram_data) -> None: # Renamed param for clarity
        """Register or update user in database."""
        db = next(get_sync_db())
        user_id = user_telegram_data.id # Extracted for logging
        self.logger.debug(
            log_database_operation("attempt_register_user", User.__tablename__),
            telegram_user_id=user_id,
            username=user_telegram_data.username
        )
        
        try:
            existing_user = db.query(User).filter(
                User.telegram_user_id == user_id
            ).first()
            
            operation_type = "update"
            if existing_user:
                # Update existing user
                existing_user.first_name = user_telegram_data.first_name
                existing_user.last_name = user_telegram_data.last_name
                existing_user.username = user_telegram_data.username
                self.logger.debug("Updating existing user in DB.", telegram_user_id=user_id)
            else:
                # Create new user
                operation_type = "insert"
                new_user = User(
                    telegram_user_id=user_id,
                    first_name=user_telegram_data.first_name,
                    last_name=user_telegram_data.last_name,
                    username=user_telegram_data.username
                )
                db.add(new_user)
                self.logger.debug("Creating new user in DB.", telegram_user_id=user_id)
            
            db.commit()
            self.logger.info(
                log_database_operation(f"{operation_type}_success", User.__tablename__),
                telegram_user_id=user_id,
                username=user_telegram_data.username
            )
            
        except Exception as e:
            self.logger.error(
                log_database_operation("register_failed", User.__tablename__, error=str(e)),
                telegram_user_id=user_id,
                exc_info=True
            )
            db.rollback()
        finally:
            db.close()
    
    def _create_user_alert(self, user_id: int, alert_data: Dict[str, Any]) -> bool:
        """Create a new alert configuration for user."""
        db = next(get_sync_db())
        self.logger.debug(
            log_database_operation("attempt_create_alert", AlertConfig.__tablename__),
            user_id=user_id,
            alert_name=alert_data.get('name')
        )
        
        try:
            alert_config = AlertConfig(
                user_id=user_id,
                config_name=alert_data['name'],
                criteria={ # Storing criteria as JSON/dict
                    'type': 'frequency', # Defaulting type, could be part of alert_data
                    'keywords': alert_data['keywords'],
                    'threshold': alert_data['threshold'],
                    'window_minutes': alert_data['window_minutes']
                },
                is_active=True
            )
            
            db.add(alert_config)
            db.commit()
            db.refresh(alert_config) # To get the ID of the new alert
            
            self.logger.info(
                log_database_operation("insert_success", AlertConfig.__tablename__),
                user_id=user_id,
                alert_id=alert_config.id,
                alert_name=alert_data['name'],
                criteria=alert_config.criteria # Log the actual criteria stored
            )
            return True
            
        except Exception as e:
            self.logger.error(
                log_database_operation("insert_failed", AlertConfig.__tablename__, error=str(e)),
                user_id=user_id,
                alert_name=alert_data.get('name'),
                exc_info=True
            )
            db.rollback()
            return False
        finally:
            db.close()
    
    def _get_user_alerts(self, user_id: int) -> List[AlertConfig]:
        """Get all active alerts for a user."""
        db = next(get_sync_db())
        self.logger.debug(
            log_database_operation("query_user_alerts", AlertConfig.__tablename__),
            user_id=user_id,
            is_active=True # Explicitly stating filter criteria
        )
        try:
            alerts = db.query(AlertConfig).filter(
                AlertConfig.user_id == user_id,
                AlertConfig.is_active == True # Only fetch active alerts
            ).all()
            self.logger.info(
                log_database_operation("query_success", AlertConfig.__tablename__),
                user_id=user_id,
                alerts_found=len(alerts)
            )
            return alerts
        except Exception as e:
            self.logger.error(
                log_database_operation("query_failed", AlertConfig.__tablename__, error=str(e)),
                user_id=user_id,
                exc_info=True
            )
            return []
        finally:
            db.close()
    
    def _delete_user_alert(self, user_id: int, alert_id: int) -> bool:
        """Delete a user's alert configuration by marking it inactive."""
        db = next(get_sync_db())
        self.logger.debug(
            log_database_operation("attempt_delete_alert (mark_inactive)", AlertConfig.__tablename__),
            user_id=user_id,
            alert_id=alert_id
        )
        try:
            alert_to_delete = db.query(AlertConfig).filter( # Renamed
                AlertConfig.id == alert_id,
                AlertConfig.user_id == user_id
            ).first()
            
            if alert_to_delete:
                if alert_to_delete.is_active: # Check if it's not already inactive
                    alert_to_delete.is_active = False
                    db.commit()
                    self.logger.info(
                        log_database_operation("update_success (marked_inactive)", AlertConfig.__tablename__),
                        user_id=user_id,
                        alert_id=alert_id
                    )
                else: # If already inactive
                    self.logger.info(
                        "Alert was already inactive in DB.",
                        user_id=user_id,
                        alert_id=alert_id
                    )
                return True # Considered success even if already inactive, as desired state is achieved
            else:
                self.logger.warning(
                    log_database_operation("update_failed (not_found_for_user)", AlertConfig.__tablename__),
                    user_id=user_id,
                    alert_id=alert_id
                )
                return False
                
        except Exception as e:
            self.logger.error(
                log_database_operation("update_failed (mark_inactive_error)", AlertConfig.__tablename__, error=str(e)),
                user_id=user_id,
                alert_id=alert_id,
                exc_info=True
            )
            db.rollback()
            return False
        finally:
            db.close()
    
    async def _get_news_summary(self, hours: int) -> Dict[str, Any]:
        """Get news summary from Smart Analysis service."""
        # TODO: Implement HTTP client to Smart Analysis service
        self.logger.info(log_function_call("_get_news_summary (mock_placeholder)", requested_hours=hours))
        # For now, return mock data
        if hours == 1: # Specific mock for testing
            return {
                'message_count': 5,
                'summary': f'Mock summary for the last {hours} hour(s). Topics include AI and Tech.',
                'time_range_hours': hours,
                'top_topics': {"AI": 3, "Tech": 2}
            }
        return {
            'message_count': 0,
            'summary': f'No recent news available in the last {hours} hour(s). (Mock)',
            'time_range_hours': hours,
            'top_topics': {}
        }
    
    async def _get_topic_trends(self, hours: int) -> Dict[str, Any]:
        """Get topic trends from Smart Analysis service."""
        # TODO: Implement HTTP client to Smart Analysis service
        self.logger.info(log_function_call("_get_topic_trends (mock_placeholder)", requested_hours=hours))
        # For now, return mock data
        if hours == 24: # Specific mock for testing
             return {
                'trends': [
                    {'topic': 'AI Ethics', 'message_count': 15, 'dominant_sentiment': 'neutral'},
                    {'topic': 'Quantum Computing', 'message_count': 10, 'dominant_sentiment': 'positive'}
                ],
                'time_range_hours': hours
            }
        return {
            'trends': [],
            'time_range_hours': hours
        }
    
    def _format_summary(self, summary_data: Dict[str, Any]) -> str:
        """Format news summary for display."""
        # This is a helper, logging within calling methods is usually sufficient.
        # Adding a debug log here to trace its usage if needed.
        self.logger.debug(log_function_call("_format_summary", data_keys=list(summary_data.keys())))
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
        
        return text
    
    def _format_trends(self, trends_data: Dict[str, Any]) -> str:
        """Format topic trends for display."""
        self.logger.debug(log_function_call("_format_trends", data_keys=list(trends_data.keys())))
        trends = trends_data.get('trends', [])
        time_range = trends_data.get('time_range_hours', 24)
        
        text = f"📈 **Topic Trends ({time_range}h)**\n\n"
        
        if not trends:
            text += "No significant trends found."
            return text
        
        for i, trend in enumerate(trends[:10], 1): # Show top 10 trends
            topic = trend['topic'].title()
            count = trend['message_count']
            sentiment = trend.get('dominant_sentiment', 'neutral') # Default sentiment if missing
            
            sentiment_emoji = {
                'positive': '😊',
                'negative': '😔',
                'neutral': '😐'
            }.get(sentiment, '😐')
            
            text += f"{i}. **{topic}** {sentiment_emoji}\n"
            text += f"   {count} messages\n\n"
        
        return text 