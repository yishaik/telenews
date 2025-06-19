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
        self.logger.info("Initializing SmartAnalysisMCP...")
        self.alert_analyzer = AlertAnalyzer() # AlertAnalyzer has its own init logging
        self.app = FastAPI(title="Tel-Insights Smart Analysis MCP")
        self._setup_routes()
        self.logger.info("SmartAnalysisMCP initialized successfully.")
    
    def _setup_routes(self) -> None:
        """Set up FastAPI routes for MCP tools."""
        self.logger.info("Setting up MCP server FastAPI routes...")
        
        @self.app.get("/")
        async def root():
            """Root endpoint with service information."""
            self.logger.info(log_function_call("mcp_root_get", endpoint="/"))
            response_data = {
                "service": "Tel-Insights Smart Analysis MCP",
                "version": "1.0.0",
                "tools": [
                    "summarize_news",
                    "topic_trends",
                    "check_alerts"
                ]
            }
            self.logger.debug("Root endpoint response generated.", response_data=response_data)
            return response_data
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            self.logger.info(log_function_call("mcp_health_check_get", endpoint="/health"))
            response_data = {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
            self.logger.debug("Health check response generated.", response_data=response_data)
            return response_data
        
        @self.app.post("/tools/summarize_news")
        async def summarize_news(request: SummarizeNewsRequest):
            """
            MCP tool: Summarize news messages from the specified time range.
            """
            self.logger.info(
                log_function_call("mcp_summarize_news_post", endpoint="/tools/summarize_news", request_data=request.model_dump())
            )
            try:
                # _summarize_news_impl will have its own detailed logging
                result = await self._summarize_news_impl(request)
                self.logger.info("Summarize news tool executed successfully.", endpoint="/tools/summarize_news")
                return result
            except Exception as e:
                self.logger.error(
                    "Error processing summarize_news request.",
                    endpoint="/tools/summarize_news",
                    error=str(e),
                    request_data=request.model_dump(),
                    exc_info=True
                )
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tools/topic_trends")
        async def topic_trends(request: TopicTrendsRequest):
            """
            MCP tool: Analyze topic trends over the specified time period.
            """
            self.logger.info(
                log_function_call("mcp_topic_trends_post", endpoint="/tools/topic_trends", request_data=request.model_dump())
            )
            try:
                # _topic_trends_impl will have its own detailed logging
                result = await self._topic_trends_impl(request)
                self.logger.info("Topic trends tool executed successfully.", endpoint="/tools/topic_trends")
                return result
            except Exception as e:
                self.logger.error(
                    "Error processing topic_trends request.",
                    endpoint="/tools/topic_trends",
                    error=str(e),
                    request_data=request.model_dump(),
                    exc_info=True
                )
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tools/check_alerts")
        async def check_alerts(request: AlertCheckRequest):
            """
            MCP tool: Check for triggered alerts based on current data.
            """
            self.logger.info(
                log_function_call("mcp_check_alerts_post", endpoint="/tools/check_alerts", request_data=request.model_dump())
            )
            try:
                # _check_alerts_impl will have its own detailed logging
                result = await self._check_alerts_impl(request)
                self.logger.info("Check alerts tool executed successfully.", endpoint="/tools/check_alerts")
                return result
            except Exception as e:
                self.logger.error(
                    "Error processing check_alerts request.",
                    endpoint="/tools/check_alerts",
                    error=str(e),
                    request_data=request.model_dump(),
                    exc_info=True
                )
                raise HTTPException(status_code=500, detail=str(e))
        self.logger.info("MCP server FastAPI routes configured.")
    
    async def _summarize_news_impl(self, request: SummarizeNewsRequest) -> Dict[str, Any]:
        """
        Implementation of news summarization tool.
        
        Args:
            request: Summarization request parameters
            
        Returns:
            Dict[str, Any]: Summarization results
        """
        self.logger.info(log_function_call("_summarize_news_impl", request_params=request.model_dump()))
        db = next(get_sync_db())
        
        try:
            # Calculate time window
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=request.time_range_hours)
            self.logger.debug(
                f"Time window for news summary: {window_start.isoformat()} to {now.isoformat()}",
                hours=request.time_range_hours
            )
            
            # Build query
            query_filters = [
                Message.message_timestamp >= window_start,
                Message.message_timestamp <= now, # Ensure we don't get future messages if any clock skew
                Message.ai_metadata.isnot(None)
            ]
            
            # Apply topic filter
            if request.topics:
                self.logger.debug(f"Applying topic filter: {request.topics}")
                topic_conditions = []
                for topic_filter_item in request.topics: # Renamed
                    topic_conditions.append(
                        Message.ai_metadata['topics'].astext.contains(f'"{topic_filter_item.lower()}"')
                    )
                from sqlalchemy import or_ # Import locally
                if topic_conditions: query_filters.append(or_(*topic_conditions))
            
            # Apply sentiment filter
            if request.sentiment:
                self.logger.debug(f"Applying sentiment filter: {request.sentiment}")
                query_filters.append(Message.ai_metadata['sentiment'].astext == request.sentiment)
            
            self.logger.debug(
                log_database_operation("query_messages_for_summary", Message.__tablename__),
                filters_applied_count=len(query_filters) - 3, # Baseline filters for time and metadata
                limit=request.max_messages
            )
            # Get messages ordered by timestamp
            messages = db.query(Message).filter(and_(*query_filters)).order_by(Message.message_timestamp.desc()).limit(request.max_messages).all()
            self.logger.info(f"Retrieved {len(messages)} messages for summarization.", request_hours=request.time_range_hours)
            
            # Analyze and summarize
            if not messages:
                self.logger.info("No messages found for summarization matching criteria.")
                return { # Return structured empty response
                    "summary": "No messages found for the specified criteria.",
                    "message_count": 0,
                    "time_range_hours": request.time_range_hours,
                    "topics_filter": request.topics, # Explicitly show filters used
                    "sentiment_filter": request.sentiment,
                    "generated_at": now.isoformat()
                }
            
            # Extract key information
            self.logger.debug("Analyzing retrieved messages for summary content.", message_count=len(messages))
            topic_counts_summary = {} # Renamed
            sentiment_counts_summary = {'positive': 0, 'negative': 0, 'neutral': 0} # Renamed
            key_summaries_list = [] # Renamed
            
            for msg_item in messages: # Renamed
                ai_metadata = msg_item.ai_metadata # Already checked for not None
                
                for topic_name in ai_metadata.get('topics', []): # Renamed
                    topic_name = topic_name.lower().strip()
                    if topic_name: topic_counts_summary[topic_name] = topic_counts_summary.get(topic_name, 0) + 1
                
                sentiment_val = ai_metadata.get('sentiment', 'neutral') # Renamed
                sentiment_counts_summary[sentiment_val] = sentiment_counts_summary.get(sentiment_val, 0) + 1
                
                msg_summary_text = ai_metadata.get('summary', '') # Renamed
                if msg_summary_text and len(key_summaries_list) < 10:  # Top 10 summaries
                    key_summaries_list.append({
                        'summary': msg_summary_text,
                        'timestamp': msg_item.message_timestamp.isoformat(),
                        'topics': ai_metadata.get('topics', []),
                        'sentiment': sentiment_val
                    })
            
            # Sort topics by frequency
            top_topics_summary = dict(sorted(topic_counts_summary.items(), key=lambda x: x[1], reverse=True)[:10]) # Renamed
            
            # Generate overall summary text
            total_messages_analyzed = len(messages) # Renamed
            dominant_sentiment_overall = max(sentiment_counts_summary.items(), key=lambda x: x[1])[0] if total_messages_analyzed > 0 else "neutral" # Renamed
            
            generated_summary_text = f"Analysis of {total_messages_analyzed} messages from the last {request.time_range_hours} hours. " # Renamed
            
            if top_topics_summary:
                first_top_topic = list(top_topics_summary.keys())[0] # Renamed
                generated_summary_text += f"Most discussed topic: '{first_top_topic}' ({top_topics_summary[first_top_topic]} mentions). "
            
            generated_summary_text += f"Overall sentiment: {dominant_sentiment_overall} ({sentiment_counts_summary[dominant_sentiment_overall]} messages). "
            
            if request.topics:
                generated_summary_text += f"Filtered by topics: {', '.join(request.topics)}. "
            
            if request.sentiment:
                generated_summary_text += f"Filtered by sentiment: {request.sentiment}. "
            
            self.logger.debug("Summary analysis complete.", top_topics_count=len(top_topics_summary), dominant_sentiment=dominant_sentiment_overall)
            result = {
                "summary": generated_summary_text,
                "message_count": total_messages_analyzed,
                "time_range_hours": request.time_range_hours,
                "sentiment_breakdown": sentiment_counts_summary,
                "top_topics": top_topics_summary,
                "key_summaries": key_summaries_list,
                "filters": {
                    "topics": request.topics,
                    "sentiment": request.sentiment
                },
                "generated_at": now.isoformat()
            }
            
            # This log message was already present and seems good.
            self.logger.info(
                "News summary generated",
                message_count=total_messages_analyzed,
                time_range_hours=request.time_range_hours,
                top_topics_count=len(top_topics_summary)
            )
            
            return result
        except Exception as e: # Catch exceptions within this impl to log before re-raising
            self.logger.error(
                "Error during _summarize_news_impl execution.",
                request_params=request.model_dump(),
                error=str(e),
                exc_info=True
            )
            raise # Re-raise for the main endpoint handler to catch and return HTTP 500
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
        self.logger.info(log_function_call("_topic_trends_impl", request_params=request.model_dump()))
        try:
            # AlertAnalyzer.check_topic_trends already has good logging
            trends = self.alert_analyzer.check_topic_trends(hours=request.time_range_hours)

            self.logger.debug(f"Retrieved {len(trends)} raw trends before min_count filter.", min_count_filter=request.min_count)
            # Filter by minimum count
            filtered_trends = [
                trend_item for trend_item in trends
                if trend_item['message_count'] >= request.min_count
            ]
            self.logger.debug(f"{len(filtered_trends)} trends remaining after applying min_count filter.")

            result = {
                "trends": filtered_trends,
                "total_topics_after_filter": len(filtered_trends), # Clarified name
                "time_range_hours": request.time_range_hours,
                "min_count_filter": request.min_count,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

            # This log message was already present and seems good.
            self.logger.info(
                "Topic trends analyzed",
                total_topics_returned=len(filtered_trends), # Clarified name
                time_range_hours=request.time_range_hours
            )

            return result
        except Exception as e:
            self.logger.error(
                "Error during _topic_trends_impl execution.",
                request_params=request.model_dump(),
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _check_alerts_impl(self, request: AlertCheckRequest) -> Dict[str, Any]:
        """
        Implementation of alert checking tool.
        
        Args:
            request: Alert check request parameters
            
        Returns:
            Dict[str, Any]: Alert check results
        """
        self.logger.info(log_function_call("_check_alerts_impl", request_params=request.model_dump()))
        try:
            if request.force_check:
                self.logger.info("Forcing alert check: Clearing alert cooldown timers.", user_request=request.force_check)
                # Clear cooldown timers for forced check
                self.alert_analyzer.last_check_time.clear()

            # AlertAnalyzer.check_frequency_alerts already has good logging
            triggered_alerts = self.alert_analyzer.check_frequency_alerts()

            result = {
                "alerts_triggered_count": len(triggered_alerts), # Clarified name
                "alerts_details": triggered_alerts, # Clarified name
                "force_check_applied": request.force_check, # Clarified name
                "checked_at": datetime.now(timezone.utc).isoformat()
            }

            # This log message was already present and seems good.
            self.logger.info(
                "Alert check completed",
                alerts_triggered_count=len(triggered_alerts), # Clarified name
                force_check_applied=request.force_check # Clarified name
            )

            return result
        except Exception as e:
            self.logger.error(
                "Error during _check_alerts_impl execution.",
                request_params=request.model_dump(),
                error=str(e),
                exc_info=True
            )
            raise
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app


# Global MCP server instance
mcp_server = SmartAnalysisMCP()


def get_mcp_server() -> SmartAnalysisMCP:
    """Get the global MCP server instance."""
    return mcp_server 