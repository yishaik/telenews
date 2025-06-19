"""
Tel-Insights Logging Configuration

Centralized logging setup using structlog for structured logging.
This module provides consistent logging configuration across all microservices.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from rich.console import Console
from rich.logging import RichHandler

from .config import get_settings

settings = get_settings()


def configure_logging(service_name: str) -> None:
    """
    Configure structured logging for a microservice.
    
    Args:
        service_name: Name of the microservice for log identification
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.monitoring.log_level.upper()),
        handlers=[
            RichHandler(
                console=Console(stderr=True),
                show_time=True,
                show_path=True,
                markup=True,
                rich_tracebacks=True,
            )
        ]
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            add_service_context(service_name),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.app.environment == "production"
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def add_service_context(service_name: str):
    """
    Add service context to all log entries.
    
    Args:
        service_name: Name of the microservice
        
    Returns:
        Processor function for structlog
    """
    def processor(logger, method_name, event_dict):
        event_dict["service"] = service_name
        event_dict["environment"] = settings.app.environment
        return event_dict
    
    return processor


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        structlog.BoundLogger: Configured logger instance
    """
    return structlog.get_logger(name)


class LoggingMixin:
    """
    Mixin class to add logging capabilities to any class.
    """
    
    @property
    def logger(self) -> structlog.BoundLogger:
        """Get a logger bound to this class."""
        return get_logger(self.__class__.__name__)


def log_function_call(func_name: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a structured log entry for function calls.
    
    Args:
        func_name: Name of the function being called
        **kwargs: Additional context to include in the log
        
    Returns:
        Dict[str, Any]: Structured log data
    """
    return {
        "event": "function_call",
        "function": func_name,
        **kwargs
    }


def log_api_request(method: str, url: str, status_code: int = None, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a structured log entry for API requests.
    
    Args:
        method: HTTP method
        url: Request URL
        status_code: Response status code
        **kwargs: Additional context
        
    Returns:
        Dict[str, Any]: Structured log data
    """
    return {
        "event": "api_request",
        "method": method,
        "url": url,
        "status_code": status_code,
        **kwargs
    }


def log_database_operation(operation: str, table: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a structured log entry for database operations.
    
    Args:
        operation: Type of operation (SELECT, INSERT, UPDATE, DELETE)
        table: Database table name
        **kwargs: Additional context
        
    Returns:
        Dict[str, Any]: Structured log data
    """
    return {
        "event": "database_operation",
        "operation": operation,
        "table": table,
        **kwargs
    }


def log_message_processing(message_id: str, channel_id: str, status: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a structured log entry for message processing.
    
    Args:
        message_id: Telegram message ID
        channel_id: Channel ID
        status: Processing status
        **kwargs: Additional context
        
    Returns:
        Dict[str, Any]: Structured log data
    """
    return {
        "event": "message_processing",
        "message_id": message_id,
        "channel_id": channel_id,
        "status": status,
        **kwargs
    }


def log_llm_request(model: str, prompt_tokens: int = None, completion_tokens: int = None, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a structured log entry for LLM API requests.
    
    Args:
        model: LLM model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        **kwargs: Additional context
        
    Returns:
        Dict[str, Any]: Structured log data
    """
    return {
        "event": "llm_request",
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        **kwargs
    }


def log_alert_triggered(alert_type: str, criteria: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    """
    Create a structured log entry for triggered alerts.
    
    Args:
        alert_type: Type of alert
        criteria: Alert criteria that was met
        **kwargs: Additional context
        
    Returns:
        Dict[str, Any]: Structured log data
    """
    return {
        "event": "alert_triggered",
        "alert_type": alert_type,
        "criteria": criteria,
        **kwargs
    } 