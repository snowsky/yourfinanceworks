"""
Prompt Management Service

Centralized service for managing AI prompts with template support,
variable substitution, and provider-specific customization.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from jinja2 import Template, TemplateError

from core.models.prompt_templates import PromptTemplate, PromptUsageLog
from core.models.database import get_tenant_context
from core.utils.data_helpers import ensure_dict

logger = logging.getLogger(__name__)


class PromptService:
    """
    Service for managing AI prompts with template support and customization.

    Provides:
    - Template-based prompt management
    - Variable substitution
    - Provider-specific overrides
    - Usage tracking
    - Version control
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self._template_cache = {}
        logger.info("PromptService initialized")

    def get_prompt(
        self,
        name: str,
        variables: Optional[Dict[str, Any]] = None,
        provider_name: Optional[str] = None,
        fallback_prompt: Optional[str] = None,
    ) -> str:
        """
        Get a formatted prompt by name with variable substitution.

        Args:
            name: Prompt template name
            variables: Variables to substitute in template
            provider_name: AI provider name for provider-specific overrides
            fallback_prompt: Fallback prompt if template not found

        Returns:
            Formatted prompt string
        """
        try:
            # Get template from cache or database
            template = self._get_template(name, provider_name)

            if not template:
                if fallback_prompt:
                    logger.warning(
                        f"Prompt template '{name}' not found, using fallback string"
                    )
                    return self._format_simple_prompt(fallback_prompt, variables or {})
                else:
                    raise ValueError(
                        f"Prompt template '{name}' not found and no fallback provided"
                    )

            # Merge with default values
            merged_variables = self._merge_variables(template, variables or {})

            # Render template
            formatted_prompt = self._render_template(template, merged_variables)

            logger.info(
                f"Successfully rendered prompt '{name}' with {len(merged_variables)} variables"
            )
            return formatted_prompt

        except Exception as e:
            logger.error(f"Failed to get prompt '{name}': {e}")
            if fallback_prompt:
                return self._format_simple_prompt(fallback_prompt, variables or {})
            raise

    def _get_template(
        self, name: str, provider_name: Optional[str] = None
    ) -> Optional[PromptTemplate]:
        """Get prompt template from cache or database."""
        cache_key = f"{name}_{provider_name or 'default'}"

        # Check cache first
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]

        # Query database
        template = (
            self.db_session.query(PromptTemplate)
            .filter(PromptTemplate.name == name, PromptTemplate.is_active == True)
            .order_by(PromptTemplate.version.desc())
            .first()
        )

        if template:
            # Check for provider-specific override
            if provider_name and template.provider_overrides:
                overrides = ensure_dict(
                    template.provider_overrides, "provider_overrides"
                )

                if provider_name in overrides:
                    # Create a copy with provider-specific content
                    template_copy = PromptTemplate()
                    template_copy.name = template.name
                    template_copy.category = template.category
                    template_copy.description = template.description
                    template_copy.template_content = overrides[provider_name]
                    template_copy.template_variables = template.template_variables
                    template_copy.output_format = template.output_format
                    template_copy.default_values = template.default_values
                    template_copy.version = template.version
                    template_copy.is_active = template.is_active
                    template_copy.provider_overrides = template.provider_overrides
                    template = template_copy

            # Cache the template
            self._template_cache[cache_key] = template

        # If not found in DB, try defaults
        if not template:
            from core.constants.default_prompts import DEFAULT_PROMPT_TEMPLATES

            default_data = next(
                (t for t in DEFAULT_PROMPT_TEMPLATES if t["name"] == name), None
            )

            if default_data:
                # Ensure provider_overrides and default_values are dicts
                provider_overrides = ensure_dict(
                    default_data.get("provider_overrides"), "provider_overrides"
                )
                default_values = ensure_dict(
                    default_data.get("default_values"), "default_values"
                )

                template = PromptTemplate(
                    id=-(
                        DEFAULT_PROMPT_TEMPLATES.index(default_data) + 1
                    ),  # Negative ID for virtual records
                    name=default_data["name"],
                    category=default_data["category"],
                    description=default_data["description"],
                    template_content=default_data["template_content"],
                    template_variables=default_data["template_variables"],
                    output_format=default_data["output_format"],
                    default_values=default_values,
                    provider_overrides=provider_overrides,
                    version=default_data.get(
                        "version", 1
                    ),  # Default to 1 if not specified
                    is_active=default_data.get(
                        "is_active", True
                    ),  # Default to True if not specified
                    created_at=datetime.utcnow(),  # Fake timestamp
                    updated_at=datetime.utcnow(),
                )
                # Cache the default template
                self._template_cache[cache_key] = template

        return template

    def _merge_variables(
        self, template: PromptTemplate, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge provided variables with template defaults."""
        merged = {}

        # Add default values first
        if template.default_values:
            default_vals = ensure_dict(template.default_values, "default_values")
            merged.update(default_vals)

        # Override with provided variables
        merged.update(variables)

        # Validate required variables
        if template.template_variables:
            required_vars = template.template_variables
            missing_vars = [var for var in required_vars if var not in merged]
            if missing_vars:
                logger.warning(
                    f"Missing required variables for '{template.name}': {missing_vars}"
                )

        return merged

    def _render_template(
        self, template: PromptTemplate, variables: Dict[str, Any]
    ) -> str:
        """Render template using Jinja2."""
        try:
            jinja_template = Template(template.template_content)
            rendered = jinja_template.render(**variables)
            return rendered.strip()
        except TemplateError as e:
            logger.error(f"Template rendering failed for '{template.name}': {e}")
            # Fallback to simple string formatting
            return self._format_simple_prompt(template.template_content, variables)

    def _format_simple_prompt(self, prompt: str, variables: Dict[str, Any]) -> str:
        """Simple string formatting fallback."""
        try:
            return prompt.format(**variables)
        except KeyError as e:
            logger.warning(f"Missing variable in simple formatting: {e}")
            return prompt

    def log_usage(
        self,
        template_name: str,
        provider_name: str,
        model_name: str,
        success: bool,
        processing_time_ms: Optional[int] = None,
        token_count: Optional[int] = None,
        error_message: Optional[str] = None,
        input_preview: Optional[str] = None,
        output_preview: Optional[str] = None,
    ) -> None:
        """
        Log prompt usage for analytics and debugging.

        Args:
            template_name: Name of the prompt template used
            provider_name: AI provider name
            model_name: AI model name
            success: Whether the operation was successful
            processing_time_ms: Processing time in milliseconds
            token_count: Number of tokens used
            error_message: Error message if failed
            input_preview: Preview of input (first 500 chars)
            output_preview: Preview of output (first 500 chars)
        """
        try:
            # Get template ID
            template = self._get_template(template_name)
            if not template:
                logger.warning(
                    f"Cannot log usage for unknown template: {template_name}"
                )
                return

            # Get tenant context
            tenant_id = get_tenant_context()

            # Create usage log
            usage_log = PromptUsageLog(
                template_id=template.id,
                tenant_id=tenant_id,
                provider_name=provider_name,
                model_name=model_name,
                processing_time_ms=processing_time_ms,
                token_count=token_count,
                success=success,
                error_message=error_message,
                input_preview=input_preview[:500] if input_preview else None,
                output_preview=output_preview[:500] if output_preview else None,
            )

            self.db_session.add(usage_log)
            self.db_session.commit()

            logger.debug(
                f"Logged usage for template '{template_name}': success={success}"
            )

        except Exception as e:
            logger.error(f"Failed to log prompt usage: {e}")

    def create_prompt(
        self,
        name: str,
        category: str,
        template_content: str,
        description: Optional[str] = None,
        template_variables: Optional[List[str]] = None,
        output_format: str = "json",
        default_values: Optional[Dict[str, Any]] = None,
        provider_overrides: Optional[Dict[str, str]] = None,
        created_by: Optional[int] = None,
    ) -> PromptTemplate:
        """
        Create a new prompt template.

        Args:
            name: Unique template name
            category: Template category
            template_content: Template content with variable placeholders
            description: Optional description
            template_variables: List of variable names used in template
            output_format: Expected output format
            default_values: Default values for variables
            provider_overrides: Provider-specific template overrides
            created_by: User ID who created the template

        Returns:
            Created PromptTemplate instance
        """
        try:
            # Check if template already exists (any version)
            existing = (
                self.db_session.query(PromptTemplate)
                .filter(PromptTemplate.name == name)
                .first()
            )

            if existing:
                # If name exists, we should probably check if it's active or not,
                # but for creation of a "new" prompt with same name, we might want to fail
                # or treat it as a new version.
                # However, the UI typically uses create for new names and update for existing.
                # Let's check if there is an active version.
                active_existing = (
                    self.db_session.query(PromptTemplate)
                    .filter(
                        PromptTemplate.name == name, PromptTemplate.is_active == True
                    )
                    .first()
                )

                if active_existing:
                    raise ValueError(
                        f"Prompt with name '{name}' already exists. Use update to create new version."
                    )

            # Create new template (Version 1)
            template = PromptTemplate(
                name=name,
                category=category,
                description=description,
                template_content=template_content,
                template_variables=template_variables,
                output_format=output_format,
                default_values=default_values,
                provider_overrides=provider_overrides,
                version=1,
                created_by=created_by,
                is_active=True,
            )

            self.db_session.add(template)
            self.db_session.commit()

            # Clear cache
            self._clear_template_cache(name)

            logger.info(f"Created prompt template '{name}' version {template.version}")
            return template

        except Exception as e:
            logger.error(f"Failed to create prompt template '{name}': {e}")
            self.db_session.rollback()
            raise

    def _check_version_limit(self, name: str, max_versions: int = 5) -> bool:
        """Check if prompt has reached maximum version limit."""
        try:
            version_count = (
                self.db_session.query(PromptTemplate)
                .filter(PromptTemplate.name == name, PromptTemplate.is_active == True)
                .count()
            )

            return version_count >= max_versions
        except Exception as e:
            logger.error(f"Failed to check version limit for '{name}': {e}")
            return False

    def _enforce_version_limit(self, name: str, max_versions: int = 5):
        """Enforce maximum version limit by deactivating oldest versions."""
        try:
            version_count = (
                self.db_session.query(PromptTemplate)
                .filter(PromptTemplate.name == name, PromptTemplate.is_active == True)
                .count()
            )

            if version_count >= max_versions:
                # Get oldest versions to deactivate (keep only max_versions-1 active)
                versions_to_deactivate = (
                    self.db_session.query(PromptTemplate)
                    .filter(
                        PromptTemplate.name == name, PromptTemplate.is_active == True
                    )
                    .order_by(PromptTemplate.version.asc())
                    .limit(version_count - max_versions + 1)
                    .all()
                )

                for old_version in versions_to_deactivate:
                    old_version.is_active = False
                    logger.info(
                        f"Deactivated old version {old_version.version} of prompt '{name}'"
                    )
        except Exception as e:
            logger.error(f"Failed to enforce version limit for '{name}': {e}")

    def update_prompt(
        self, name: str, updates: Dict[str, Any], updated_by: Optional[int] = None
    ) -> Optional[PromptTemplate]:
        """
        Update an existing prompt template by creating a new version.

        Args:
            name: Template name to update
            updates: Dictionary of fields to update
            updated_by: User ID who updated the template

        Returns:
            Updated PromptTemplate instance or None
        """
        try:
            # Get latest existing template
            existing = (
                self.db_session.query(PromptTemplate)
                .filter(PromptTemplate.name == name)
                .order_by(PromptTemplate.version.desc())
                .first()
            )

            if not existing:
                logger.warning(f"Template '{name}' not found for update")
                return None

            # Enforce version limit
            self._enforce_version_limit(name)

            # Create NEW version
            new_version = existing.version + 1

            new_template = PromptTemplate(
                name=name,
                category=updates.get("category", existing.category),
                description=updates.get("description", existing.description),
                template_content=updates.get(
                    "template_content", existing.template_content
                ),
                template_variables=updates.get(
                    "template_variables", existing.template_variables
                ),
                output_format=updates.get("output_format", existing.output_format),
                default_values=updates.get("default_values", existing.default_values),
                provider_overrides=updates.get(
                    "provider_overrides", existing.provider_overrides
                ),
                version=new_version,
                is_active=updates.get("is_active", existing.is_active),
                created_by=existing.created_by,  # Preserve original creator
                updated_by=updated_by,
                created_at=datetime.utcnow(),
            )

            self.db_session.add(new_template)
            self.db_session.commit()

            # Clear cache
            self._clear_template_cache(name)

            logger.info(f"Updated prompt '{name}' to version {new_template.version}")
            return new_template

        except Exception as e:
            logger.error(f"Failed to update prompt template '{name}': {e}")
            self.db_session.rollback()
            return None

    def list_prompts(
        self, category: Optional[str] = None, active_only: bool = True
    ) -> List[PromptTemplate]:
        """
        List prompt templates.

        Args:
            category: Filter by category
            active_only: Only return active templates

        Returns:
            List of PromptTemplate instances
        """
        try:
            query = self.db_session.query(PromptTemplate)

            if category:
                query = query.filter(PromptTemplate.category == category)

            if active_only:
                query = query.filter(PromptTemplate.is_active == True)

            templates = query.order_by(
                PromptTemplate.name, PromptTemplate.version.desc()
            ).all()

            # Group by name and return latest version
            latest_templates = {}
            for template in templates:
                if template.name not in latest_templates:
                    latest_templates[template.name] = template

            return list(latest_templates.values())

        except Exception as e:
            logger.error(f"Failed to list prompts: {e}")
            return []

    def list_default_prompts(self) -> List[PromptTemplate]:
        """List all default prompt templates from the centralized constant."""
        from core.constants.default_prompts import DEFAULT_PROMPT_TEMPLATES
        from datetime import datetime

        templates = []
        for i, data in enumerate(DEFAULT_PROMPT_TEMPLATES):
            # Ensure provider_overrides and default_values are dicts
            provider_overrides = ensure_dict(
                data.get("provider_overrides"), "provider_overrides"
            )
            default_values = ensure_dict(data.get("default_values"), "default_values")

            templates.append(
                PromptTemplate(
                    id=-(i + 1),  # Negative ID for virtual records
                    name=data["name"],
                    category=data["category"],
                    description=data["description"],
                    template_content=data["template_content"],
                    template_variables=data["template_variables"],
                    output_format=data["output_format"],
                    default_values=default_values,
                    provider_overrides=provider_overrides,
                    version=data.get("version", 1),  # Default to 1 if not specified
                    is_active=data.get(
                        "is_active", True
                    ),  # Default to True if not specified
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    created_by=None,
                    updated_by=None,
                )
            )

        logger.info(
            f"Returning {len(templates)} default prompt templates form constants"
        )
        return templates

    def reset_prompt_to_default(
        self, name: str, updated_by: Optional[int] = None
    ) -> Optional[PromptTemplate]:
        """Reset a prompt template to its default version."""
        try:
            # Find the default version (version 1)
            default_template = (
                self.db_session.query(PromptTemplate)
                .filter(
                    PromptTemplate.name == name,
                    PromptTemplate.version == 1,
                    PromptTemplate.is_active == True,
                )
                .first()
            )

            if not default_template:
                logger.warning(f"Default template '{name}' not found")
                return None

            # Enforce version limit
            self._enforce_version_limit(name)

            # Get the latest version to determine new version number
            latest_template = (
                self.db_session.query(PromptTemplate)
                .filter(PromptTemplate.name == name)
                .order_by(PromptTemplate.version.desc())
                .first()
            )

            new_version = (latest_template.version + 1) if latest_template else 2

            # Create new version with default content
            reset_template = PromptTemplate(
                name=default_template.name,
                category=default_template.category,
                description=default_template.description,
                template_content=default_template.template_content,
                template_variables=default_template.template_variables,
                output_format=default_template.output_format,
                default_values=default_template.default_values,
                provider_overrides=default_template.provider_overrides,
                version=new_version,
                is_active=True,
                created_by=updated_by,
                updated_by=updated_by,
            )

            self.db_session.add(reset_template)
            self.db_session.commit()

            # Clear cache
            self._clear_template_cache(name)

            logger.info(
                f"Reset prompt '{name}' to default, created version {new_version}"
            )
            return reset_template

        except Exception as e:
            logger.error(f"Failed to reset prompt '{name}': {e}")
            self.db_session.rollback()
            return None

    def restore_prompt_version(
        self, name: str, version: int, updated_by: Optional[int] = None
    ) -> Optional[PromptTemplate]:
        """Restore a specific version of a prompt template."""
        try:
            # Find the version to restore
            source_template = (
                self.db_session.query(PromptTemplate)
                .filter(
                    PromptTemplate.name == name,
                    PromptTemplate.version == version,
                    PromptTemplate.is_active == True,
                )
                .first()
            )

            if not source_template:
                logger.warning(f"Prompt template '{name}' version {version} not found")
                return None

            # Enforce version limit
            self._enforce_version_limit(name)

            # Get the latest version to determine new version number
            latest_template = (
                self.db_session.query(PromptTemplate)
                .filter(PromptTemplate.name == name)
                .order_by(PromptTemplate.version.desc())
                .first()
            )

            new_version = (latest_template.version + 1) if latest_template else 1

            # Create new version with restored content
            restored_template = PromptTemplate(
                name=source_template.name,
                category=source_template.category,
                description=source_template.description,
                template_content=source_template.template_content,
                template_variables=source_template.template_variables,
                output_format=source_template.output_format,
                default_values=source_template.default_values,
                provider_overrides=source_template.provider_overrides,
                version=new_version,
                is_active=True,
                created_by=updated_by,
                updated_by=updated_by,
            )

            self.db_session.add(restored_template)
            self.db_session.commit()

            # Clear cache
            self._clear_template_cache(name)

            logger.info(
                f"Restored prompt '{name}' version {version} as new version {new_version}"
            )
            return restored_template

        except Exception as e:
            logger.error(f"Failed to restore prompt '{name}' version {version}: {e}")
            self.db_session.rollback()
            return None

    def list_prompt_versions(self, name: str) -> List[PromptTemplate]:
        """List all versions of a specific prompt template."""
        try:
            templates = (
                self.db_session.query(PromptTemplate)
                .filter(PromptTemplate.name == name, PromptTemplate.is_active == True)
                .order_by(PromptTemplate.version.desc())
                .all()
            )

            logger.info(f"Found {len(templates)} versions for prompt '{name}'")
            return templates

        except Exception as e:
            logger.error(f"Failed to list prompt versions for '{name}': {e}")
            return []

    def delete_prompt(self, name: str, updated_by: Optional[int] = None) -> bool:
        """
        Delete a prompt template by deactivating all versions.

        Args:
            name: Template name to delete
            updated_by: User ID who deleted the template

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get all versions of the template
            templates = (
                self.db_session.query(PromptTemplate)
                .filter(PromptTemplate.name == name, PromptTemplate.is_active == True)
                .all()
            )

            if not templates:
                logger.warning(f"No active templates found for '{name}'")
                return False

            # Deactivate all versions instead of deleting
            for template in templates:
                template.is_active = False
                template.updated_by = updated_by

            self.db_session.commit()
            self._clear_template_cache(name)

            logger.info(f"Deleted prompt template '{name}' ({len(templates)} versions)")
            return True

        except Exception as e:
            logger.error(f"Failed to delete prompt template '{name}': {e}")
            self.db_session.rollback()
            return False

    def _clear_template_cache(self, name: str):
        """Clear template cache for a specific prompt name."""
        keys_to_remove = [
            key for key in self._template_cache.keys() if key.startswith(f"{name}_")
        ]
        for key in keys_to_remove:
            del self._template_cache[key]

    def get_usage_stats(
        self, template_name: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage statistics for prompts.

        Args:
            template_name: Filter by specific template name
            days: Number of days to look back

        Returns:
            Dictionary with usage statistics
        """
        try:
            from datetime import timedelta

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            query = self.db_session.query(PromptUsageLog).filter(
                PromptUsageLog.created_at >= cutoff_date
            )

            if template_name:
                query = query.join(PromptTemplate).filter(
                    PromptTemplate.name == template_name
                )

            logs = query.all()

            # Calculate statistics
            total_usage = len(logs)
            successful_usage = sum(1 for log in logs if log.success)
            avg_processing_time = (
                sum(log.processing_time_ms or 0 for log in logs) / total_usage
                if total_usage > 0
                else 0
            )
            total_tokens = sum(log.token_count or 0 for log in logs)

            # Group by provider
            provider_stats = {}
            for log in logs:
                provider = log.provider_name
                if provider not in provider_stats:
                    provider_stats[provider] = {"count": 0, "success": 0, "tokens": 0}
                provider_stats[provider]["count"] += 1
                if log.success:
                    provider_stats[provider]["success"] += 1
                provider_stats[provider]["tokens"] += log.token_count or 0

            return {
                "total_usage": total_usage,
                "successful_usage": successful_usage,
                "success_rate": (
                    successful_usage / total_usage if total_usage > 0 else 0
                ),
                "avg_processing_time_ms": avg_processing_time,
                "total_tokens": total_tokens,
                "provider_stats": provider_stats,
                "days_analyzed": days,
            }

        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {
                "total_usage": 0,
                "successful_usage": 0,
                "success_rate": 0.0,
                "avg_processing_time_ms": 0.0,
                "total_tokens": 0,
                "provider_stats": {},
                "days_analyzed": days,
            }

    def _clear_cache(self):
        """Clear the template cache."""
        self._template_cache.clear()
        logger.info("Template cache cleared")


# Global service instance
def get_prompt_service(db_session: Session) -> PromptService:
    """Get prompt service instance."""
    return PromptService(db_session)
