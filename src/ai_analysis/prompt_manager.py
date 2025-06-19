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
        self.logger.info("PromptManager initialized.") # Added a period for consistency.
    
    def get_prompt(self, name: str, version: int = None) -> Optional[str]:
        """
        Get a prompt template by name and version.
        
        Args:
            name: Prompt template name
            version: Specific version (if None, gets the active version)
            
        Returns:
            Optional[str]: Prompt template or None if not found
        """
        self.logger.debug(
            log_function_call("get_prompt", prompt_name=name, requested_version=version)
        )
        db = next(get_sync_db())
        
        try:
            self.logger.debug(
                log_database_operation(
                    "query",
                    Prompt.__tablename__,
                    name=name,
                    version=version,
                    is_active=version is None
                )
            )
            query = db.query(Prompt).filter(Prompt.name == name)
            
            if version is not None:
                query = query.filter(Prompt.version == version)
            else:
                query = query.filter(Prompt.is_active == True)
            
            prompt_obj = query.first() # Renamed to avoid conflict with model name
            
            if prompt_obj:
                self.logger.info(
                    "Prompt retrieved successfully",
                    prompt_name=name,
                    prompt_version=prompt_obj.version,
                    is_active=prompt_obj.is_active
                )
                return prompt_obj.template
            else:
                self.logger.warning(
                    "Prompt not found in database",
                    prompt_name=name,
                    requested_version=version
                )
                return None
                
        except Exception as e:
            self.logger.error(
                log_database_operation(
                    "query_failed",
                    Prompt.__tablename__,
                    prompt_name=name,
                    error=str(e)
                ),
                exc_info=True
            )
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
        template_preview = template[:75] + "..." if len(template) > 75 else template
        self.logger.debug(
            log_function_call(
                "format_prompt",
                template_preview=template_preview,
                available_vars=list(kwargs.keys())
            )
        )
        try:
            formatted_prompt = template.format(**kwargs)
            self.logger.debug("Prompt formatted successfully.")
            return formatted_prompt
        except KeyError as e:
            self.logger.error(
                "Missing variable in prompt template during formatting.",
                missing_key=str(e),
                template_preview=template_preview,
                available_vars=list(kwargs.keys()),
                exc_info=True
            )
            raise # Re-raise as this is a critical configuration/data issue
        except Exception as e:
            self.logger.error(
                "Error formatting prompt.",
                template_preview=template_preview,
                error=str(e),
                exc_info=True
            )
            raise # Re-raise
    
    def save_prompt(
        self, 
        name: str, 
        template: str, 
        parameters: Dict[str, Any] = None,
        version: int = None # Explicitly allow setting a version
    ) -> bool:
        """
        Save a prompt template to the database.
        
        Args:
            name: Prompt template name
            template: Prompt template string
            parameters: Additional parameters/metadata for the prompt
            version: Version number (if None, auto-increments from max existing)
            
        Returns:
            bool: True if saved successfully
        """
        self.logger.debug(
            log_function_call(
                "save_prompt",
                prompt_name=name,
                version_provided=version,
                has_parameters=bool(parameters)
            )
        )
        db = next(get_sync_db())
        
        try:
            target_version = version
            if target_version is None:
                self.logger.debug(log_database_operation("query_max_version", Prompt.__tablename__, name=name))
                max_version_obj = db.query(Prompt.version).filter(
                    Prompt.name == name
                ).order_by(Prompt.version.desc()).first()
                target_version = (max_version_obj[0] + 1) if max_version_obj else 1
                self.logger.info(f"Auto-incrementing version for prompt '{name}' to {target_version}.")

            # Deactivate previous active version(s) of this prompt if this new one is active
            # For simplicity, assuming new prompts are always set active.
            # A more robust system might have explicit activation.
            self.logger.debug(
                log_database_operation(
                    "update_deactivate_old", Prompt.__tablename__, name=name
                )
            )
            db.query(Prompt).filter(
                Prompt.name == name,
                Prompt.is_active == True
            ).update({"is_active": False}, synchronize_session=False)
            
            # Create new prompt
            new_prompt = Prompt(
                name=name,
                version=target_version,
                template=template,
                parameters=parameters or {}, # Ensure parameters is a dict
                is_active=True # New prompts are active by default
            )
            
            db.add(new_prompt)
            db.commit()
            
            self.logger.info(
                log_database_operation(
                    "insert",
                    Prompt.__tablename__,
                    prompt_name=name,
                    version=target_version,
                    is_active=True
                )
            )
            return True
            
        except Exception as e:
            self.logger.error(
                log_database_operation(
                    "save_failed",
                    Prompt.__tablename__,
                    prompt_name=name,
                    error=str(e)
                ),
                exc_info=True
            )
            try:
                db.rollback()
                self.logger.info("Database rollback successful after error saving prompt.", prompt_name=name)
            except Exception as re:
                self.logger.error("Failed to rollback database transaction for prompt save.", original_error=str(e), rollback_error=str(re))
            return False
        finally:
            db.close()


# Initialize default prompts
def initialize_default_prompts():
    """Initialize default prompt templates in the database."""
    logger.info("Starting initialization of default prompts...") # Use module logger here
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
    
    # save_prompt method now includes logging
    prompt_manager.save_prompt(
        name="text_analysis",
        template=text_analysis_prompt,
        parameters={
            "description": "Analyzes text messages and extracts structured metadata",
            "input_variables": ["message_text"],
            "output_format": "json"
        }
        # version=1 # Optionally set initial version
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
        # version=1 # Optionally set initial version
    )
    
    logger.info("Default prompts initialization process completed.")


def get_prompt_manager() -> PromptManager:
    """Get a prompt manager instance."""
    return PromptManager() 