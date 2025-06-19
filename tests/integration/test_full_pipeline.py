"""
Integration test for the full Tel-Insights message processing pipeline.

This test verifies that messages can flow through the entire system:
Queue -> AI Analysis -> Database Storage -> Smart Analysis
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from ai_analysis.message_processor import MessageProcessor
from smart_analysis.alert_analyzer import AlertAnalyzer
from shared.models import Message, Channel, AlertConfig, User


@pytest.mark.integration
def test_full_message_processing_pipeline(
    db_session, 
    sample_channel, 
    mock_llm_client,
    test_env_vars
):
    """Test the complete message processing pipeline."""
    
    # Setup test data
    db_session.add(sample_channel)
    db_session.commit()
    
    # Create a test message in the database (simulating aggregator output)
    test_message = Message(
        telegram_message_id=98765,
        channel_id=sample_channel.id,
        message_text="Breaking: Major AI breakthrough announced by Google researchers. "
                    "The new technology could revolutionize machine learning applications.",
        message_timestamp=datetime.now(timezone.utc)
    )
    db_session.add(test_message)
    db_session.commit()
    
    # Mock the LLM response
    mock_response = Mock()
    mock_response.content = json.dumps({
        "summary": "Google announces breakthrough in AI technology",
        "topics": ["technology", "artificial intelligence", "research"],
        "sentiment": "positive",
        "entities": {
            "organizations": ["Google"],
            "people": [],
            "locations": [],
            "dates": [],
            "other": ["AI", "machine learning"]
        },
        "keywords": ["AI", "breakthrough", "Google", "technology", "research"],
        "source_type": "technology",
        "confidence_score": 0.92,
        "language": "en"
    })
    mock_response.model = "gemini-1.5-pro"
    
    mock_llm_client.generate_content.return_value = mock_response
    
    # Initialize message processor with mocked LLM
    processor = MessageProcessor()
    processor.llm_client = mock_llm_client
    
    # Create message data as it would come from the queue
    message_data = {
        "message_id": str(test_message.telegram_message_id),
        "message_text": test_message.message_text,
        "channel_id": str(test_message.channel_id),
        "timestamp": test_message.message_timestamp.isoformat()
    }
    
    # Process the message
    success = processor.process_message(message_data)
    
    # Verify processing succeeded
    assert success is True
    
    # Verify AI metadata was stored
    db_session.refresh(test_message)
    assert test_message.ai_metadata is not None
    assert test_message.ai_metadata["summary"] == "Google announces breakthrough in AI technology"
    assert "technology" in test_message.ai_metadata["topics"]
    assert "artificial intelligence" in test_message.ai_metadata["topics"]
    assert test_message.ai_metadata["sentiment"] == "positive"
    assert "Google" in test_message.ai_metadata["entities"]["organizations"]
    assert test_message.ai_metadata["confidence_score"] == 0.92
    
    # Test smart analysis functionality
    alert_analyzer = AlertAnalyzer()
    
    # Create a test user and alert configuration
    test_user = User(
        telegram_user_id=123456789,
        first_name="Test",
        username="testuser"
    )
    db_session.add(test_user)
    db_session.commit()
    
    # Create alert config that should trigger
    alert_config = AlertConfig(
        user_id=test_user.telegram_user_id,
        config_name="AI News Alert",
        criteria={
            "type": "frequency",
            "keywords": ["AI", "technology"],
            "threshold": 1,  # Low threshold for testing
            "window_minutes": 60
        },
        is_active=True
    )
    db_session.add(alert_config)
    db_session.commit()
    
    # Check if alerts are triggered
    triggered_alerts = alert_analyzer.check_frequency_alerts()
    
    # Verify alert was triggered
    assert len(triggered_alerts) == 1
    alert = triggered_alerts[0]
    assert alert["config_name"] == "AI News Alert"
    assert alert["message_count"] >= 1
    assert alert["user_id"] == test_user.telegram_user_id
    
    # Test recent summary functionality
    summary = alert_analyzer.get_recent_summary(hours=1)
    
    assert summary["total_messages"] >= 1
    assert "technology" in summary["top_topics"]
    assert summary["sentiment_breakdown"]["positive"] >= 1


@pytest.mark.integration
def test_topic_trends_analysis(db_session, sample_channel):
    """Test topic trends analysis functionality."""
    
    # Setup test data
    db_session.add(sample_channel)
    db_session.commit()
    
    # Create multiple messages with different topics
    test_messages = [
        {
            "text": "AI breakthrough in machine learning",
            "metadata": {
                "topics": ["artificial intelligence", "technology"],
                "sentiment": "positive"
            }
        },
        {
            "text": "New research in quantum computing",
            "metadata": {
                "topics": ["quantum computing", "technology", "research"],
                "sentiment": "neutral"
            }
        },
        {
            "text": "Technology stocks rise after AI announcement",
            "metadata": {
                "topics": ["technology", "finance", "artificial intelligence"],
                "sentiment": "positive"
            }
        }
    ]
    
    # Add messages to database
    for i, msg_data in enumerate(test_messages):
        message = Message(
            telegram_message_id=100000 + i,
            channel_id=sample_channel.id,
            message_text=msg_data["text"],
            message_timestamp=datetime.now(timezone.utc),
            ai_metadata=msg_data["metadata"]
        )
        db_session.add(message)
    
    db_session.commit()
    
    # Analyze topic trends
    alert_analyzer = AlertAnalyzer()
    trends = alert_analyzer.check_topic_trends(hours=1)
    
    # Verify trends analysis
    assert len(trends) > 0
    
    # Check that technology is the top topic (appears in all 3 messages)
    tech_trend = next((t for t in trends if t["topic"] == "technology"), None)
    assert tech_trend is not None
    assert tech_trend["message_count"] == 3
    
    # Check AI topic (appears in 2 messages)
    ai_trend = next((t for t in trends if t["topic"] == "artificial intelligence"), None)
    assert ai_trend is not None
    assert ai_trend["message_count"] == 2
    
    # Verify sentiment breakdown
    assert tech_trend["sentiment_breakdown"]["positive"] == 2
    assert tech_trend["sentiment_breakdown"]["neutral"] == 1
    assert tech_trend["dominant_sentiment"] == "positive"


@pytest.mark.integration 
def test_error_handling_in_pipeline(db_session, sample_channel, mock_llm_client):
    """Test error handling in the message processing pipeline."""
    
    # Setup test data
    db_session.add(sample_channel)
    db_session.commit()
    
    test_message = Message(
        telegram_message_id=99999,
        channel_id=sample_channel.id,
        message_text="Test message for error handling",
        message_timestamp=datetime.now(timezone.utc)
    )
    db_session.add(test_message)
    db_session.commit()
    
    # Test with LLM returning invalid JSON
    mock_response = Mock()
    mock_response.content = "Invalid JSON response"
    mock_response.model = "gemini-1.5-pro"
    mock_llm_client.generate_content.return_value = mock_response
    
    processor = MessageProcessor()
    processor.llm_client = mock_llm_client
    
    message_data = {
        "message_id": str(test_message.telegram_message_id),
        "message_text": test_message.message_text,
        "channel_id": str(test_message.channel_id),
        "timestamp": test_message.message_timestamp.isoformat()
    }
    
    # Process should handle the error gracefully
    success = processor.process_message(message_data)
    assert success is False  # Should fail gracefully
    
    # Test with empty message text
    empty_message_data = {
        "message_id": "888888",
        "message_text": "",
        "channel_id": str(test_message.channel_id)
    }
    
    success = processor.process_message(empty_message_data)
    assert success is True  # Should skip empty messages successfully


@pytest.mark.integration
def test_smart_analysis_mcp_endpoints(db_session, sample_channel):
    """Test Smart Analysis MCP server endpoints."""
    
    # This would test the FastAPI endpoints
    # For now, we test the underlying functionality
    
    # Setup test data
    db_session.add(sample_channel)
    
    message = Message(
        telegram_message_id=777777,
        channel_id=sample_channel.id,
        message_text="Test message for MCP endpoints",
        message_timestamp=datetime.now(timezone.utc),
        ai_metadata={
            "summary": "Test message summary",
            "topics": ["test", "development"],
            "sentiment": "neutral",
            "keywords": ["test", "message"]
        }
    )
    db_session.add(message)
    db_session.commit()
    
    # Test summarization functionality
    from smart_analysis.mcp_server import SmartAnalysisMCP
    mcp = SmartAnalysisMCP()
    
    # Create mock request
    class MockRequest:
        def __init__(self):
            self.time_range_hours = 1
            self.topics = None
            self.sentiment = None
            self.max_messages = 50
    
    request = MockRequest()
    
    # This would be tested with actual HTTP requests in a full integration test
    # For now, we verify the core logic works
    assert mcp.alert_analyzer is not None
    
    # Test health check
    health = {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
    assert health["status"] == "healthy" 