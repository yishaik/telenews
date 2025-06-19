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
        self.logger.info("AlertAnalyzer initialized")
    
    def check_frequency_alerts(self) -> List[Dict[str, Any]]:
        """
        Check all active frequency-based alert configurations.
        
        Returns:
            List[Dict[str, Any]]: List of triggered alerts
        """
        triggered_alerts = []
        db = next(get_sync_db())
        
        try:
            # Get all active alert configurations
            alert_configs = db.query(AlertConfig).filter(
                AlertConfig.is_active == True,
                AlertConfig.criteria['type'].astext == 'frequency'
            ).all()
            
            self.logger.info(f"Checking {len(alert_configs)} frequency alert configurations")
            
            for config in alert_configs:
                try:
                    alerts = self._check_single_frequency_alert(db, config)
                    triggered_alerts.extend(alerts)
                except Exception as e:
                    self.logger.error(
                        f"Error checking alert config {config.id}: {e}",
                        config_id=config.id,
                        user_id=config.user_id
                    )
            
            return triggered_alerts
            
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
        criteria = config.criteria
        threshold = criteria.get('threshold', settings.alerts.default_threshold)
        window_minutes = criteria.get('window_minutes', settings.alerts.default_window_minutes)
        keywords = criteria.get('keywords', [])
        topics = criteria.get('topics', [])
        sentiment = criteria.get('sentiment')
        
        # Calculate time window
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=window_minutes)
        
        # Check cooldown period
        config_key = f"freq_{config.id}"
        last_check = self.last_check_time.get(config_key)
        cooldown_minutes = settings.alerts.cooldown_minutes
        
        if last_check and (now - last_check).total_seconds() < (cooldown_minutes * 60):
            self.logger.debug(f"Alert config {config.id} in cooldown period")
            return []
        
        # Build query for messages in time window
        query = db.query(Message).filter(
            Message.message_timestamp >= window_start,
            Message.message_timestamp <= now,
            Message.ai_metadata.isnot(None)
        )
        
        # Apply keyword filters
        if keywords:
            keyword_conditions = []
            for keyword in keywords:
                # Search in AI metadata keywords and message text
                keyword_conditions.append(
                    Message.ai_metadata['keywords'].astext.contains(f'"{keyword.lower()}"')
                )
                keyword_conditions.append(
                    func.lower(Message.message_text).contains(keyword.lower())
                )
            
            # Use OR for keyword matching
            from sqlalchemy import or_
            query = query.filter(or_(*keyword_conditions))
        
        # Apply topic filters
        if topics:
            topic_conditions = []
            for topic in topics:
                topic_conditions.append(
                    Message.ai_metadata['topics'].astext.contains(f'"{topic.lower()}"')
                )
            
            from sqlalchemy import or_
            query = query.filter(or_(*topic_conditions))
        
        # Apply sentiment filter
        if sentiment:
            query = query.filter(
                Message.ai_metadata['sentiment'].astext == sentiment
            )
        
        # Count matching messages
        message_count = query.count()
        
        self.logger.debug(
            f"Alert check for config {config.id}",
            config_id=config.id,
            message_count=message_count,
            threshold=threshold,
            window_minutes=window_minutes
        )
        
        # Check if threshold is exceeded
        if message_count >= threshold:
            # Update last check time
            self.last_check_time[config_key] = now
            
            # Get sample messages for context
            sample_messages = query.limit(5).all()
            
            alert = {
                'alert_id': f"freq_{config.id}_{int(time.time())}",
                'config_id': config.id,
                'user_id': config.user_id,
                'config_name': config.config_name,
                'alert_type': 'frequency',
                'criteria': criteria,
                'triggered_at': now.isoformat(),
                'message_count': message_count,
                'threshold': threshold,
                'time_window_minutes': window_minutes,
                'sample_messages': [
                    {
                        'id': msg.id,
                        'text': msg.message_text[:200] + "..." if len(msg.message_text) > 200 else msg.message_text,
                        'timestamp': msg.message_timestamp.isoformat(),
                        'summary': msg.ai_metadata.get('summary', '') if msg.ai_metadata else '',
                        'topics': msg.ai_metadata.get('topics', []) if msg.ai_metadata else [],
                        'sentiment': msg.ai_metadata.get('sentiment', '') if msg.ai_metadata else ''
                    }
                    for msg in sample_messages
                ]
            }
            
            self.logger.info(
                "Frequency alert triggered",
                alert_id=alert['alert_id'],
                config_id=config.id,
                user_id=config.user_id,
                message_count=message_count,
                threshold=threshold
            )
            
            return [alert]
        
        return []
    
    def check_topic_trends(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Analyze topic trends over the specified time period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            List[Dict[str, Any]]: Topic trend analysis
        """
        db = next(get_sync_db())
        
        try:
            # Calculate time window
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=hours)
            
            # Query messages with AI metadata
            messages = db.query(Message).filter(
                Message.message_timestamp >= window_start,
                Message.ai_metadata.isnot(None)
            ).all()
            
            # Count topics
            topic_counts = {}
            sentiment_by_topic = {}
            
            for message in messages:
                ai_metadata = message.ai_metadata
                if not ai_metadata:
                    continue
                
                topics = ai_metadata.get('topics', [])
                sentiment = ai_metadata.get('sentiment', 'neutral')
                
                for topic in topics:
                    topic = topic.lower().strip()
                    if not topic:
                        continue
                    
                    # Count topic occurrences
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
                    
                    # Track sentiment for this topic
                    if topic not in sentiment_by_topic:
                        sentiment_by_topic[topic] = {'positive': 0, 'negative': 0, 'neutral': 0}
                    
                    sentiment_by_topic[topic][sentiment] = sentiment_by_topic[topic].get(sentiment, 0) + 1
            
            # Sort topics by frequency
            sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
            
            trends = []
            for topic, count in sorted_topics[:20]:  # Top 20 topics
                sentiment_data = sentiment_by_topic.get(topic, {})
                total_sentiment = sum(sentiment_data.values())
                
                trend = {
                    'topic': topic,
                    'message_count': count,
                    'sentiment_breakdown': sentiment_data,
                    'dominant_sentiment': max(sentiment_data.items(), key=lambda x: x[1])[0] if sentiment_data else 'neutral',
                    'sentiment_score': sentiment_data.get('positive', 0) - sentiment_data.get('negative', 0)
                }
                trends.append(trend)
            
            self.logger.info(f"Analyzed {len(trends)} topic trends over {hours} hours")
            return trends
            
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
        db = next(get_sync_db())
        
        try:
            # Calculate time window
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=hours)
            
            # Build base query
            query = db.query(Message).filter(
                Message.message_timestamp >= window_start,
                Message.ai_metadata.isnot(None)
            )
            
            # Apply topic filter if specified
            if topics:
                topic_conditions = []
                for topic in topics:
                    topic_conditions.append(
                        Message.ai_metadata['topics'].astext.contains(f'"{topic.lower()}"')
                    )
                
                from sqlalchemy import or_
                query = query.filter(or_(*topic_conditions))
            
            messages = query.all()
            
            # Analyze messages
            total_messages = len(messages)
            sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
            top_topics = {}
            
            for message in messages:
                ai_metadata = message.ai_metadata
                if not ai_metadata:
                    continue
                
                # Count sentiment
                sentiment = ai_metadata.get('sentiment', 'neutral')
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
                
                # Count topics
                for topic in ai_metadata.get('topics', []):
                    topic = topic.lower().strip()
                    top_topics[topic] = top_topics.get(topic, 0) + 1
            
            # Sort topics
            sorted_topics = sorted(top_topics.items(), key=lambda x: x[1], reverse=True)[:10]
            
            summary = {
                'time_window_hours': hours,
                'total_messages': total_messages,
                'sentiment_breakdown': sentiment_counts,
                'top_topics': dict(sorted_topics),
                'generated_at': now.isoformat(),
                'filter_topics': topics
            }
            
            self.logger.info(f"Generated summary for {hours}h window: {total_messages} messages")
            return summary
            
        finally:
            db.close() 