"""
Tel-Insights LLM Client

LLM client implementation for Google Gemini with retry logic and error handling.
"""

import json
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass

import google.generativeai as genai

from shared.config import get_settings
from shared.logging import LoggingMixin, get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Structured response from LLM API calls."""
    
    content: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    finish_reason: Optional[str] = None


class LLMError(Exception):
    """Custom exception for LLM-related errors."""
    pass


class GeminiClient(LoggingMixin):
    """Google Gemini LLM client implementation."""
    
    def __init__(self, api_key: str = None, model_name: str = "gemini-1.5-pro"):
        """Initialize Gemini client."""
        self.api_key = api_key or settings.llm.google_api_key
        self.model_name = model_name
        self.max_retries = settings.llm.max_retries
        
        if not self.api_key:
            # This error is raised, but logging it provides context if error isn't caught upstream.
            self.logger.error("Google API key is missing. Cannot initialize GeminiClient.")
            raise LLMError("Google API key is required for Gemini client")
        
        # Configure the API
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name=self.model_name)
        
        self.logger.info(
            "Gemini client initialized",
            model_name=self.model_name,
            max_retries=self.max_retries
        )
    
    def generate_content(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate content using Gemini with retry logic."""
        last_error = None
        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        
        self.logger.debug(
            "Attempting to generate content with LLM",
            model=self.model_name,
            prompt_preview=prompt_preview,
            generation_kwargs=kwargs
        )

        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                
                # Note: The google.generativeai library might have its own ways to get token counts
                # via response.usage_metadata but it's not directly available on response.text
                # For now, we log what is readily available.
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=kwargs.get('temperature', 0.1),
                        max_output_tokens=kwargs.get('max_tokens', 2048),
                    )
                )
                
                response_time_ms = round((time.time() - start_time) * 1000)

                if not response.text:
                    # This is an LLMError, but log_llm_request is good for consistency
                    self.logger.error(
                        log_llm_request(
                            model=self.model_name,
                            error="Empty response from Gemini",
                            attempt=attempt + 1,
                            response_time_ms=response_time_ms,
                            prompt_length=len(prompt)
                        )
                    )
                    raise LLMError("Empty response from Gemini")
                
                # Assuming prompt_tokens and completion_tokens are not directly available
                # in this simplified setup. If they were, they'd be passed to log_llm_request.
                self.logger.info(
                    log_llm_request(
                        model=self.model_name,
                        # prompt_tokens= N/A,
                        # completion_tokens= N/A,
                        response_time_ms=response_time_ms,
                        attempt=attempt + 1,
                        prompt_length=len(prompt),
                        response_length=len(response.text),
                        finish_reason=str(response.candidates[0].finish_reason) if response.candidates else "unknown"
                    )
                )
                
                return LLMResponse(
                    content=response.text,
                    model=self.model_name,
                    # finish_reason=str(response.candidates[0].finish_reason) if response.candidates else None
                    # Token counts would be set here if available
                )
                
            except Exception as e:
                last_error = e
                response_time_ms = round((time.time() - start_time) * 1000) if 'start_time' in locals() else -1

                self.logger.warning(
                    log_llm_request(
                        model=self.model_name,
                        error=str(e),
                        attempt=attempt + 1,
                        max_attempts=self.max_retries + 1,
                        response_time_ms=response_time_ms,
                        prompt_length=len(prompt)
                    ),
                    exc_info=True # Add stack trace for warnings too, can be helpful
                )
                
                if attempt < self.max_retries:
                    wait_time = (2 ** attempt) + 1 # Exponential backoff with jitter could be better
                    self.logger.info(f"Retrying LLM request in {wait_time} seconds...")
                    time.sleep(wait_time)
        
        self.logger.error(
            log_llm_request(
                model=self.model_name,
                error=f"Failed after {self.max_retries + 1} attempts: {last_error}",
                final_attempt_failed=True,
                total_attempts=self.max_retries + 1
            ),
            exc_info=True # Include stack trace for the final error
        )
        raise LLMError(f"Failed after {self.max_retries + 1} attempts: {last_error}")


def get_llm_client() -> GeminiClient:
    """Get configured LLM client."""
    return GeminiClient() 