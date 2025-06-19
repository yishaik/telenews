"""
Tel-Insights Prompt Management System

Manages LLM prompt templates with versioning support and database storage.
Provides structured prompts for different analysis tasks.
"""

import json
from typing import Any, Dict, List, Optional

from shared.database import get_sync_db
from shared.logging import LoggingMixin, get_logger
from shared.models import Prompt

logger = get_logger(__name__)


class PromptManager(LoggingMixin):
    """
    Manages prompt templates for LLM analysis tasks.
    """
    
    def __init__(self):
        """Initialize the prompt manager."""
        self.logger.info("PromptManager initialized")
    
    def get_prompt(self, name: str, version: int = None) -> Optional[str]:
        """
        Get a prompt template by name and version.
        
        Args:
            name: Prompt template name
            version: Specific version (if None, gets the active version)
            
        Returns:
            Optional[str]: Prompt template or None if not found
        """
        db = next(get_sync_db())
        
        try:
            query = db.query(Prompt).filter(Prompt.name == name)
            
            if version is not None:
                query = query.filter(Prompt.version == version)
            else:
                query = query.filter(Prompt.is_active == True)
            
            prompt = query.first()
            
            if prompt:
                self.logger.debug(f"Retrieved prompt: {name} v{prompt.version}")
                return prompt.template
            else:
                self.logger.warning(f"Prompt not found: {name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving prompt {name}: {e}")
            return None
        finally:
            db.close()
    
    def format_prompt(self, template: str, **kwargs) -> str:
        """
        Format a prompt template with provided variables.
        
        Args:
            template: Prompt template string
            **kwargs: Variables to substitute in the template
            
        Returns:
            str: Formatted prompt
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            self.logger.error(f"Missing variable in prompt template: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error formatting prompt: {e}")
            raise
    
    def save_prompt(
        self, 
        name: str, 
        template: str, 
        parameters: Dict[str, Any] = None,
        version: int = None
    ) -> bool:
        """
        Save a prompt template to the database.
        
        Args:
            name: Prompt template name
            template: Prompt template string
            parameters: Additional parameters/metadata
            version: Version number (if None, auto-increments)
            
        Returns:
            bool: True if saved successfully
        """
        db = next(get_sync_db())
        
        try:
            # Determine version number
            if version is None:
                max_version = db.query(Prompt).filter(
                    Prompt.name == name
                ).order_by(Prompt.version.desc()).first()
                version = (max_version.version + 1) if max_version else 1
            
            # Deactivate previous active version
            db.query(Prompt).filter(
                Prompt.name == name,
                Prompt.is_active == True
            ).update({"is_active": False})
            
            # Create new prompt
            prompt = Prompt(
                name=name,
                version=version,
                template=template,
                parameters=parameters or {},
                is_active=True
            )
            
            db.add(prompt)
            db.commit()
            
            self.logger.info(f"Saved prompt: {name} v{version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving prompt {name}: {e}")
            db.rollback()
            return False
        finally:
            db.close()


# Initialize default prompts
def initialize_default_prompts():
    """Initialize default prompt templates in the database."""
    prompt_manager = PromptManager()
    
    # Text Analysis Prompt
    text_analysis_prompt = """
Analyze the following news message and extract structured information. Respond ONLY with valid JSON in the exact format shown below.

Message: "{message_text}"

Required JSON response format:
{{
    "summary": "Brief 1-2 sentence summary of the main news",
    "topics": ["topic1", "topic2", "topic3"],
    "sentiment": "positive|negative|neutral",
    "entities": {{
        "people": ["person1", "person2"],
        "organizations": ["org1", "org2"],
        "locations": ["location1", "location2"],
        "dates": ["date1", "date2"],
        "other": ["entity1", "entity2"]
    }},
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    "source_type": "news|technology|politics|business|sports|entertainment|other",
    "confidence_score": 0.85,
    "language": "en|es|fr|de|ru|ar|other"
}}

Instructions:
- Extract 3-5 main topics from the content
- Identify sentiment as positive, negative, or neutral
- Find all named entities (people, organizations, locations, dates)
- Extract 5-8 relevant keywords
- Classify the source type based on content
- Provide confidence score between 0.0 and 1.0
- Detect the language of the message
- Ensure the response is valid JSON only
"""
    
    prompt_manager.save_prompt(
        name="text_analysis",
        template=text_analysis_prompt,
        parameters={
            "description": "Analyzes text messages and extracts structured metadata",
            "input_variables": ["message_text"],
            "output_format": "json"
        }
    )
    
    # Summarization Prompt
    summarization_prompt = """
Create a concise summary of the following news messages from the last {time_range} hours.

Messages:
{messages}

Instructions:
- Provide a brief overview of the main news themes
- Highlight any breaking news or important developments
- Group related stories together
- Keep the summary under 200 words
- Focus on factual information
- Use clear, professional language

Summary:
"""
    
    prompt_manager.save_prompt(
        name="news_summarization",
        template=summarization_prompt,
        parameters={
            "description": "Summarizes multiple news messages into a concise overview",
            "input_variables": ["messages", "time_range"],
            "output_format": "text"
        }
    )
    
    logger.info("Default prompts initialized")


def get_prompt_manager() -> PromptManager:
    """Get a prompt manager instance."""
    return PromptManager() 