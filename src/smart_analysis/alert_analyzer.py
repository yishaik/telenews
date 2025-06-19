"""
Tel-Insights Alert Analyzer

Implements frequency-based alerting system using AI-generated metadata.
Analyzes patterns in real-time and triggers alerts based on configurable criteria.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session

from shared.config import get_settings
from shared.database import get_sync_db
from shared.logging import LoggingMixin, get_logger
from shared.models import AlertConfig, Message, User

settings = get_settings()
logger = get_logger(__name__)


class AlertAnalyzer(LoggingMixin):
    """
    Analyzes messages and triggers alerts based on frequency and criteria.
    """
    
    def __init__(self):
        """Initialize the alert analyzer."""
        self.last_check_time = {}  # Track last check per alert config
        self.logger.info("AlertAnalyzer initialized.") # Added period
    
    def check_frequency_alerts(self) -> List[Dict[str, Any]]:
        """
        Check all active frequency-based alert configurations.
        
        Returns:
            List[Dict[str, Any]]: List of triggered alerts
        """
        self.logger.info("Starting check for all frequency alerts.")
        triggered_alerts_summary = [] # To store brief info about triggered alerts for summary log
        db = next(get_sync_db())
        
        try:
            # Get all active alert configurations
            self.logger.debug(
                log_database_operation(
                    "query",
                    AlertConfig.__tablename__,
                    filters={"is_active": True, "criteria_type": "frequency"}
                )
            )
            alert_configs = db.query(AlertConfig).filter(
                AlertConfig.is_active == True,
                AlertConfig.criteria['type'].astext == 'frequency' # Ensure criteria is treated as JSON
            ).all()
            
            self.logger.info(
                log_database_operation(
                    "query_result",
                    AlertConfig.__tablename__,
                    count=len(alert_configs),
                    status="success" if alert_configs is not None else "failed"
                )
            )
            
            if not alert_configs:
                self.logger.info("No active frequency alert configurations found.")
                return []

            for config in alert_configs:
                try:
                    # _check_single_frequency_alert will log its own details, including log_alert_triggered
                    triggered_for_config = self._check_single_frequency_alert(db, config)
                    if triggered_for_config:
                        for alert_detail in triggered_for_config: # Can be multiple if logic changes
                            triggered_alerts_summary.append({
                                "config_id": config.id,
                                "config_name": config.config_name,
                                "user_id": config.user_id,
                                "alert_id": alert_detail.get('alert_id')
                            })
                        # triggered_alerts.extend(triggered_for_config) # This was the original var name
                except Exception as e: # Catch errors from _check_single_frequency_alert
                    self.logger.error(
                        "Error processing single alert configuration during batch check.",
                        config_id=config.id,
                        config_name=config.config_name,
                        user_id=config.user_id,
                        error=str(e),
                        exc_info=True
                    )
            
            self.logger.info(
                f"Frequency alert check cycle completed. Triggered alerts: {len(triggered_alerts_summary)}",
                triggered_alerts_details=triggered_alerts_summary # Log summary of what was triggered
            )
            # The method is expected to return the full alert details, not just summary
            # Need to collect the actual alert data if _check_single_frequency_alert returns it
            # For now, this part is a bit disconnected from the return type if triggered_alerts_summary is used.
            # Assuming _check_single_frequency_alert actually appends to a list passed in or returns and is extended.
            # The original code used `triggered_alerts.extend(alerts)`, let's ensure that logic is preserved.
            # Re-evaluating the collection of triggered_alerts.
            # The original `triggered_alerts` variable was not being populated.

            # Corrected logic to collect full triggered alert data
            all_triggered_alerts_details = []
            for config in alert_configs: # Iterate again or store results from first loop
                try:
                    alerts = self._check_single_frequency_alert(db, config)
                    all_triggered_alerts_details.extend(alerts)
                except Exception: # Already logged above
                    pass
            return all_triggered_alerts_details # Return the full details
            
        except Exception as e:
            self.logger.error("Failed to query or process alert configurations.", error=str(e), exc_info=True)
            return [] # Return empty list on major failure
        finally:
            db.close()
    
    def _check_single_frequency_alert(self, db: Session, config: AlertConfig) -> List[Dict[str, Any]]:
        """
        Check a single frequency alert configuration.
        
        Args:
            db: Database session
            config: Alert configuration
            
        Returns:
            List[Dict[str, Any]]: Triggered alerts for this configuration
        """
        self.logger.info(
            log_function_call(
                "_check_single_frequency_alert",
                config_id=config.id,
                config_name=config.config_name,
                user_id=config.user_id
            )
        )
        criteria = config.criteria # This is already a dict
        threshold = criteria.get('threshold', settings.alerts.default_threshold)
        window_minutes = criteria.get('window_minutes', settings.alerts.default_window_minutes)
        keywords = criteria.get('keywords', [])
        topics = criteria.get('topics', []) # Assuming topics are part of criteria
        sentiment_filter = criteria.get('sentiment') # Renamed to avoid conflict

        # Calculate time window
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=window_minutes)
        self.logger.debug(
            "Time window calculated for alert check.",
            config_id=config.id,
            window_start=window_start.isoformat(),
            window_end=now.isoformat(),
            window_minutes=window_minutes
        )
        
        # Check cooldown period
        config_key = f"freq_{config.id}" # Used for last_check_time
        last_triggered_time = self.last_check_time.get(config_key) # Renamed for clarity
        cooldown_minutes = settings.alerts.cooldown_minutes
        
        if last_triggered_time and (now - last_triggered_time).total_seconds() < (cooldown_minutes * 60):
            self.logger.info(
                "Alert config in cooldown period, skipping check.",
                config_id=config.id,
                config_name=config.config_name,
                last_triggered_at=last_triggered_time.isoformat(),
                cooldown_minutes=cooldown_minutes
            )
            return []
        
        # Build query for messages in time window
        query_filters = [
            Message.message_timestamp >= window_start,
            Message.message_timestamp <= now,
            Message.ai_metadata.isnot(None) # Ensure AI metadata exists for filtering
        ]
        
        # Apply keyword filters
        if keywords:
            keyword_conditions = []
            for keyword in keywords:
                # Search in AI metadata keywords and message text
                keyword_conditions.append(Message.ai_metadata['keywords'].astext.contains(f'"{keyword.lower()}"'))
                keyword_conditions.append(func.lower(Message.message_text).contains(keyword.lower()))
            
            from sqlalchemy import or_ # Import locally if not already at top
            if keyword_conditions: query_filters.append(or_(*keyword_conditions))
        
        # Apply topic filters
        if topics:
            topic_conditions = []
            for topic in topics:
                topic_conditions.append(Message.ai_metadata['topics'].astext.contains(f'"{topic.lower()}"'))
            
            from sqlalchemy import or_ # Import locally
            if topic_conditions: query_filters.append(or_(*topic_conditions))
        
        # Apply sentiment filter
        if sentiment_filter: # Use the renamed variable
            query_filters.append(Message.ai_metadata['sentiment'].astext == sentiment_filter)

        self.logger.debug(
            log_database_operation("count_messages", Message.__tablename__),
            config_id=config.id,
            filters_applied_count=len(query_filters) - 3, # -3 for baseline time/metadata filters
            keywords_filter=keywords,
            topics_filter=topics,
            sentiment_filter=sentiment_filter
        )
        
        # Count matching messages
        message_count = db.query(Message).filter(and_(*query_filters)).count()
        
        self.logger.info(
            "Message count for alert config retrieved.",
            config_id=config.id,
            config_name=config.config_name,
            message_count=message_count,
            threshold=threshold,
            window_minutes=window_minutes
        )
        
        # Check if threshold is exceeded
        if message_count >= threshold:
            self.logger.info(
                f"Threshold exceeded for alert config {config.id} ({config.config_name}). Triggering alert.",
                message_count=message_count, threshold=threshold
            )
            # Update last check time to manage cooldown
            self.last_check_time[config_key] = now
            self.logger.debug(f"Updated last_check_time for config {config.id} to {now.isoformat()}", config_key=config_key)
            
            # Get sample messages for context - use the same filters
            self.logger.debug(log_database_operation("query_sample_messages", Message.__tablename__), config_id=config.id)
            sample_messages_query = db.query(Message).filter(and_(*query_filters)).order_by(Message.message_timestamp.desc()).limit(5)
            sample_messages = sample_messages_query.all()
            self.logger.debug(f"Retrieved {len(sample_messages)} sample messages for alert.", config_id=config.id)
            
            alert_payload = { # Renamed for clarity
                'alert_id': f"freq_{config.id}_{int(time.time())}",
                'config_id': config.id,
                'user_id': config.user_id,
                'config_name': config.config_name,
                'alert_type': 'frequency',
                'criteria': criteria, # Original criteria from config
                'triggered_at': now.isoformat(),
                'actual_message_count': message_count, # Explicitly name actual count
                'threshold': threshold, # Include threshold that was met
                'time_window_minutes': window_minutes, # Include window
                'sample_messages': [
                    {
                        'id': msg.id, # Use msg.id not msg.id()
                        'text': msg.message_text[:200] + "..." if msg.message_text and len(msg.message_text) > 200 else msg.message_text,
                        'timestamp': msg.message_timestamp.isoformat() if msg.message_timestamp else None,
                        'summary': msg.ai_metadata.get('summary', '') if msg.ai_metadata else '',
                        'topics': msg.ai_metadata.get('topics', []) if msg.ai_metadata else [],
                        'sentiment': msg.ai_metadata.get('sentiment', '') if msg.ai_metadata else ''
                    }
                    for msg in sample_messages # Ensure msg has these attributes
                ]
            }
            
            # Use the specific log_alert_triggered helper
            self.logger.info(
                log_alert_triggered(
                    alert_type='frequency',
                    criteria={ # Log the criteria that caused trigger
                        "config_id": config.id,
                        "configured_keywords": keywords,
                        "configured_topics": topics,
                        "configured_sentiment": sentiment_filter,
                        "configured_threshold": threshold,
                        "configured_window_minutes": window_minutes
                    },
                    alert_id=alert_payload['alert_id'], # from generated payload
                    config_name=config.config_name,
                    user_id=config.user_id,
                    actual_message_count=message_count, # actual value
                    sample_messages_count=len(sample_messages)
                )
            )
            
            return [alert_payload]
        
        self.logger.debug(f"Alert not triggered for config {config.id} ({config.config_name}). Count: {message_count}, Threshold: {threshold}")
        self.logger.debug(f"Alert not triggered for config {config.id} ({config.config_name}). Count: {message_count}, Threshold: {threshold}")
        return []
    
    def check_topic_trends(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Analyze topic trends over the specified time period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            List[Dict[str, Any]]: Topic trend analysis
        """
        self.logger.info(log_function_call("check_topic_trends", requested_hours=hours))
        db = next(get_sync_db())
        
        try:
            # Calculate time window
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=hours)
            self.logger.debug(f"Time window for topic trends: {window_start.isoformat()} to {now.isoformat()}")
            
            # Query messages with AI metadata
            self.logger.debug(
                log_database_operation("query_messages_for_trends", Message.__tablename__),
                time_window_start=window_start.isoformat()
            )
            messages = db.query(Message).filter(
                Message.message_timestamp >= window_start,
                Message.ai_metadata.isnot(None) # Ensure messages have AI metadata
            ).all()
            self.logger.info(f"Retrieved {len(messages)} messages for topic trend analysis.")
            
            if not messages:
                self.logger.info("No messages with AI metadata found for trend analysis in the time window.")
                return []

            # Count topics
            topic_counts = {}
            sentiment_by_topic = {}
            
            for message in messages:
                ai_metadata = message.ai_metadata # Already checked for isnot(None)
                
                current_topics = ai_metadata.get('topics', [])
                sentiment = ai_metadata.get('sentiment', 'neutral')
                
                for topic_item in current_topics: # Renamed to avoid conflict
                    topic_item = topic_item.lower().strip()
                    if not topic_item:
                        continue
                    
                    topic_counts[topic_item] = topic_counts.get(topic_item, 0) + 1
                    
                    if topic_item not in sentiment_by_topic:
                        sentiment_by_topic[topic_item] = {'positive': 0, 'negative': 0, 'neutral': 0}
                    
                    sentiment_by_topic[topic_item][sentiment] = sentiment_by_topic[topic_item].get(sentiment, 0) + 1
            
            self.logger.debug(f"Identified {len(topic_counts)} unique topics before sorting/filtering.")
            # Sort topics by frequency
            sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
            
            trends_result = [] # Renamed
            for topic_name, count_val in sorted_topics[:20]:  # Top 20 topics
                sentiment_data = sentiment_by_topic.get(topic_name, {})
                
                trend_item = { # Renamed
                    'topic': topic_name,
                    'message_count': count_val,
                    'sentiment_breakdown': sentiment_data,
                    'dominant_sentiment': max(sentiment_data.items(), key=lambda x: x[1])[0] if sentiment_data else 'neutral',
                    'sentiment_score': sentiment_data.get('positive', 0) - sentiment_data.get('negative', 0)
                }
                trends_result.append(trend_item)
            
            self.logger.info(
                f"Topic trend analysis completed. Returning {len(trends_result)} trends.",
                requested_hours=hours,
                total_messages_analyzed=len(messages)
            )
            return trends_result

        except Exception as e:
            self.logger.error("Error during topic trend analysis.", error=str(e), exc_info=True)
            return [] # Return empty list on error
        finally:
            db.close()
    
    def get_recent_summary(self, hours: int = 1, topics: List[str] = None) -> Dict[str, Any]:
        """
        Get a summary of recent news activity.
        
        Args:
            hours: Number of hours to summarize
            topics: Specific topics to filter by (optional)
            
        Returns:
            Dict[str, Any]: Summary data
        """
        self.logger.info(log_function_call("get_recent_summary", requested_hours=hours, filter_topics=topics))
        db = next(get_sync_db())
        
        try:
            # Calculate time window
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=hours)
            self.logger.debug(f"Time window for summary: {window_start.isoformat()} to {now.isoformat()}")
            
            # Build base query
            query_filters_summary = [ # Renamed
                Message.message_timestamp >= window_start,
                Message.ai_metadata.isnot(None)
            ]
            
            # Apply topic filter if specified
            if topics:
                self.logger.debug(f"Applying topic filter for summary: {topics}")
                topic_conditions_summary = [] # Renamed
                for topic_filter_item in topics: # Renamed
                    topic_conditions_summary.append(
                        Message.ai_metadata['topics'].astext.contains(f'"{topic_filter_item.lower()}"')
                    )
                
                from sqlalchemy import or_ # Import locally
                if topic_conditions_summary: query_filters_summary.append(or_(*topic_conditions_summary))
            
            self.logger.debug(
                log_database_operation("query_messages_for_summary", Message.__tablename__),
                filters_applied_count=len(query_filters_summary) - 2 # -2 for baseline time/metadata filters
            )
            messages_for_summary = db.query(Message).filter(and_(*query_filters_summary)).all() # Renamed
            self.logger.info(f"Retrieved {len(messages_for_summary)} messages for summary generation.")
            
            if not messages_for_summary:
                 self.logger.info("No messages found for summary in the time window with specified filters.")
                 return { # Return a structured empty-like response
                    'time_window_hours': hours,
                    'total_messages': 0,
                    'sentiment_breakdown': {'positive': 0, 'negative': 0, 'neutral': 0},
                    'top_topics': {},
                    'summary_text': "No relevant messages found to generate a summary.",
                    'generated_at': now.isoformat(),
                    'filter_topics': topics
                }

            # Analyze messages
            total_messages_analyzed = len(messages_for_summary) # Renamed
            sentiment_counts_summary = {'positive': 0, 'negative': 0, 'neutral': 0} # Renamed
            top_topics_summary = {} # Renamed
            
            for message_item in messages_for_summary: # Renamed
                ai_metadata = message_item.ai_metadata # Already checked for isnot(None)
                
                sentiment = ai_metadata.get('sentiment', 'neutral')
                sentiment_counts_summary[sentiment] = sentiment_counts_summary.get(sentiment, 0) + 1
                
                for topic_name in ai_metadata.get('topics', []): # Renamed
                    topic_name = topic_name.lower().strip()
                    if topic_name: top_topics_summary[topic_name] = top_topics_summary.get(topic_name, 0) + 1
            
            # Sort topics
            sorted_top_topics = dict(sorted(top_topics_summary.items(), key=lambda x: x[1], reverse=True)[:10]) # Renamed
            
            # Basic summary text (can be improved with LLM later if needed)
            summary_text_gen = f"Summary of {total_messages_analyzed} messages in the last {hours} hours. "
            if sorted_top_topics:
                summary_text_gen += f"Key topics include: {', '.join(list(sorted_top_topics.keys())[:3])}. "
            dominant_sentiment_gen = max(sentiment_counts_summary, key=sentiment_counts_summary.get)
            summary_text_gen += f"Overall sentiment appears {dominant_sentiment_gen}."


            summary_result = { # Renamed
                'time_window_hours': hours,
                'total_messages': total_messages_analyzed,
                'sentiment_breakdown': sentiment_counts_summary,
                'top_topics': sorted_top_topics, # Store the dict
                'summary_text': summary_text_gen, # Added a generated summary text
                'generated_at': now.isoformat(),
                'filter_topics': topics
            }
            
            self.logger.info(
                "Recent news summary generated successfully.",
                requested_hours=hours,
                messages_analyzed=total_messages_analyzed,
                topics_found=len(sorted_top_topics),
                filter_topics=topics
            )
            return summary_result

        except Exception as e:
            self.logger.error("Error during recent summary generation.", error=str(e), exc_info=True)
            return {'error': str(e)} # Return error info
        finally:
            db.close() 