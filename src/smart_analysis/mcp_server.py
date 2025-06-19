"""
Tel-Insights MCP Server

Model Context Protocol server implementation for Smart Analysis tools.
Provides tools for news summarization and trend analysis.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.config import get_settings
from shared.database import get_sync_db
from shared.logging import LoggingMixin, get_logger
from shared.models import Message

from .alert_analyzer import AlertAnalyzer

settings = get_settings()
logger = get_logger(__name__)


# Pydantic models for MCP tools
class SummarizeNewsRequest(BaseModel):
    """Request model for news summarization."""
    time_range_hours: int = Field(default=1, ge=1, le=168, description="Time range in hours (1-168)")
    topics: Optional[List[str]] = Field(default=None, description="Filter by specific topics")
    sentiment: Optional[str] = Field(default=None, description="Filter by sentiment (positive/negative/neutral)")
    max_messages: int = Field(default=50, ge=1, le=200, description="Maximum messages to include")


class TopicTrendsRequest(BaseModel):
    """Request model for topic trends analysis."""
    time_range_hours: int = Field(default=24, ge=1, le=168, description="Time range in hours")
    min_count: int = Field(default=2, ge=1, description="Minimum topic count to include")


class AlertCheckRequest(BaseModel):
    """Request model for alert checking."""
    force_check: bool = Field(default=False, description="Force check ignoring cooldown")


class SmartAnalysisMCP(LoggingMixin):
    """
    MCP server for Smart Analysis tools.
    """
    
    def __init__(self):
        """Initialize the MCP server."""
        self.alert_analyzer = AlertAnalyzer()
        self.app = FastAPI(title="Tel-Insights Smart Analysis MCP")
        self._setup_routes()
        self.logger.info("SmartAnalysisMCP initialized")
    
    def _setup_routes(self) -> None:
        """Set up FastAPI routes for MCP tools."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint with service information."""
            return {
                "service": "Tel-Insights Smart Analysis MCP",
                "version": "1.0.0",
                "tools": [
                    "summarize_news",
                    "topic_trends",
                    "check_alerts"
                ]
            }
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
        
        @self.app.post("/tools/summarize_news")
        async def summarize_news(request: SummarizeNewsRequest):
            """
            MCP tool: Summarize news messages from the specified time range.
            """
            try:
                return await self._summarize_news_impl(request)
            except Exception as e:
                self.logger.error(f"Error in summarize_news: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tools/topic_trends")
        async def topic_trends(request: TopicTrendsRequest):
            """
            MCP tool: Analyze topic trends over the specified time period.
            """
            try:
                return await self._topic_trends_impl(request)
            except Exception as e:
                self.logger.error(f"Error in topic_trends: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tools/check_alerts")
        async def check_alerts(request: AlertCheckRequest):
            """
            MCP tool: Check for triggered alerts based on current data.
            """
            try:
                return await self._check_alerts_impl(request)
            except Exception as e:
                self.logger.error(f"Error in check_alerts: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _summarize_news_impl(self, request: SummarizeNewsRequest) -> Dict[str, Any]:
        """
        Implementation of news summarization tool.
        
        Args:
            request: Summarization request parameters
            
        Returns:
            Dict[str, Any]: Summarization results
        """
        db = next(get_sync_db())
        
        try:
            # Calculate time window
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=request.time_range_hours)
            
            # Build query
            query = db.query(Message).filter(
                Message.message_timestamp >= window_start,
                Message.message_timestamp <= now,
                Message.ai_metadata.isnot(None)
            )
            
            # Apply topic filter
            if request.topics:
                topic_conditions = []
                for topic in request.topics:
                    topic_conditions.append(
                        Message.ai_metadata['topics'].astext.contains(f'"{topic.lower()}"')
                    )
                
                from sqlalchemy import or_
                query = query.filter(or_(*topic_conditions))
            
            # Apply sentiment filter
            if request.sentiment:
                query = query.filter(
                    Message.ai_metadata['sentiment'].astext == request.sentiment
                )
            
            # Get messages ordered by timestamp
            messages = query.order_by(Message.message_timestamp.desc()).limit(request.max_messages).all()
            
            # Analyze and summarize
            if not messages:
                return {
                    "summary": "No messages found for the specified criteria.",
                    "message_count": 0,
                    "time_range_hours": request.time_range_hours,
                    "topics": request.topics,
                    "sentiment_filter": request.sentiment,
                    "generated_at": now.isoformat()
                }
            
            # Extract key information
            topic_counts = {}
            sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
            key_summaries = []
            
            for message in messages:
                ai_metadata = message.ai_metadata
                if not ai_metadata:
                    continue
                
                # Count topics
                for topic in ai_metadata.get('topics', []):
                    topic = topic.lower().strip()
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
                
                # Count sentiment
                sentiment = ai_metadata.get('sentiment', 'neutral')
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
                
                # Collect summaries
                summary = ai_metadata.get('summary', '')
                if summary and len(key_summaries) < 10:  # Top 10 summaries
                    key_summaries.append({
                        'summary': summary,
                        'timestamp': message.message_timestamp.isoformat(),
                        'topics': ai_metadata.get('topics', []),
                        'sentiment': sentiment
                    })
            
            # Sort topics by frequency
            top_topics = dict(sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10])
            
            # Generate overall summary text
            total_messages = len(messages)
            dominant_sentiment = max(sentiment_counts.items(), key=lambda x: x[1])[0]
            
            summary_text = f"Analysis of {total_messages} messages from the last {request.time_range_hours} hours. "
            
            if top_topics:
                top_topic = list(top_topics.keys())[0]
                summary_text += f"Most discussed topic: '{top_topic}' ({top_topics[top_topic]} mentions). "
            
            summary_text += f"Overall sentiment: {dominant_sentiment} ({sentiment_counts[dominant_sentiment]} messages). "
            
            if request.topics:
                summary_text += f"Filtered by topics: {', '.join(request.topics)}. "
            
            if request.sentiment:
                summary_text += f"Filtered by sentiment: {request.sentiment}. "
            
            result = {
                "summary": summary_text,
                "message_count": total_messages,
                "time_range_hours": request.time_range_hours,
                "sentiment_breakdown": sentiment_counts,
                "top_topics": top_topics,
                "key_summaries": key_summaries,
                "filters": {
                    "topics": request.topics,
                    "sentiment": request.sentiment
                },
                "generated_at": now.isoformat()
            }
            
            self.logger.info(
                "News summary generated",
                message_count=total_messages,
                time_range_hours=request.time_range_hours,
                top_topics_count=len(top_topics)
            )
            
            return result
            
        finally:
            db.close()
    
    async def _topic_trends_impl(self, request: TopicTrendsRequest) -> Dict[str, Any]:
        """
        Implementation of topic trends analysis tool.
        
        Args:
            request: Topic trends request parameters
            
        Returns:
            Dict[str, Any]: Topic trends analysis results
        """
        trends = self.alert_analyzer.check_topic_trends(hours=request.time_range_hours)
        
        # Filter by minimum count
        filtered_trends = [
            trend for trend in trends 
            if trend['message_count'] >= request.min_count
        ]
        
        result = {
            "trends": filtered_trends,
            "total_topics": len(filtered_trends),
            "time_range_hours": request.time_range_hours,
            "min_count_filter": request.min_count,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        self.logger.info(
            "Topic trends analyzed",
            total_topics=len(filtered_trends),
            time_range_hours=request.time_range_hours
        )
        
        return result
    
    async def _check_alerts_impl(self, request: AlertCheckRequest) -> Dict[str, Any]:
        """
        Implementation of alert checking tool.
        
        Args:
            request: Alert check request parameters
            
        Returns:
            Dict[str, Any]: Alert check results
        """
        if request.force_check:
            # Clear cooldown timers for forced check
            self.alert_analyzer.last_check_time.clear()
        
        triggered_alerts = self.alert_analyzer.check_frequency_alerts()
        
        result = {
            "alerts_triggered": len(triggered_alerts),
            "alerts": triggered_alerts,
            "force_check": request.force_check,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
        self.logger.info(
            "Alert check completed",
            alerts_triggered=len(triggered_alerts),
            force_check=request.force_check
        )
        
        return result
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app


# Global MCP server instance
mcp_server = SmartAnalysisMCP()


def get_mcp_server() -> SmartAnalysisMCP:
    """Get the global MCP server instance."""
    return mcp_server 