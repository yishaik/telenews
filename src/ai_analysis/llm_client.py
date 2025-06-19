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
            raise LLMError("Google API key is required for Gemini client")
        
        # Configure the API
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name=self.model_name)
        
        self.logger.info(f"Gemini client initialized with model: {self.model_name}")
    
    def generate_content(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate content using Gemini with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=kwargs.get('temperature', 0.1),
                        max_output_tokens=kwargs.get('max_tokens', 2048),
                    )
                )
                
                if not response.text:
                    raise LLMError("Empty response from Gemini")
                
                self.logger.info(
                    "LLM request successful",
                    model=self.model_name,
                    response_time=round(time.time() - start_time, 2),
                    attempt=attempt + 1
                )
                
                return LLMResponse(
                    content=response.text,
                    model=self.model_name
                )
                
            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"LLM request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )
                
                if attempt < self.max_retries:
                    wait_time = (2 ** attempt) + 1
                    time.sleep(wait_time)
        
        raise LLMError(f"Failed after {self.max_retries + 1} attempts: {last_error}")


def get_llm_client() -> GeminiClient:
    """Get configured LLM client."""
    return GeminiClient() 