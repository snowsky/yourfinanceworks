import logging
import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add api directory to path for imports
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

from core.models.database import get_master_db
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager
from core.constants.default_prompts import DEFAULT_PROMPT_TEMPLATES
from commercial.prompt_management.services.prompt_service import PromptService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_prompt_in_db(tenant: Tenant, prompt_template: dict):
    """Update a specific prompt template in a tenant's database."""
    name = prompt_template["name"]
    version = prompt_template["version"]
    
    try:
        # Get tenant database session
        SessionMaker = tenant_db_manager.get_tenant_session(tenant.id)
        db = SessionMaker()
        
        from commercial.prompt_management.models.prompt_templates import PromptTemplate
        
        prompt_service = PromptService(db)
        
        # Check if prompt exists using direct query since PromptService might not have the helper
        existing = db.query(PromptTemplate).filter(
            PromptTemplate.name == name,
            PromptTemplate.is_active == True
        ).order_by(PromptTemplate.version.desc()).first()
        
        if existing:
            logger.info(f"  Found existing prompt '{name}' (Version {existing.version})")
            # If version is lower or content is different, update it
            if existing.version < version or existing.template_content != prompt_template["template_content"]:
                logger.info(f"  Updating prompt content...")
                prompt_service.update_prompt(
                    name=name,
                    updates={
                        "template_content": prompt_template["template_content"],
                        "description": prompt_template.get("description"),
                        "template_variables": prompt_template.get("template_variables"),
                        "output_format": prompt_template.get("output_format"),
                        "provider_overrides": prompt_template.get("provider_overrides")
                    }
                )
                logger.info(f"  ✅ Updated to version {version}")
            else:
                logger.info(f"  Already at version {version} with same content. Skipping.")
        else:
            logger.info(f"  Prompt '{name}' not found. Creating...")
            prompt_service.create_prompt(
                name=name,
                category=prompt_template["category"],
                description=prompt_template.get("description", ""),
                template_content=prompt_template["template_content"],
                template_variables=prompt_template.get("template_variables", []),
                output_format=prompt_template.get("output_format", "text"),
                default_values=prompt_template.get("default_values", {}),
                provider_overrides=prompt_template.get("provider_overrides", {})
            )
            logger.info(f"  ✅ Created new prompt '{name}'")
            
        db.close()
    except Exception as e:
        logger.error(f"❌ Error processing tenant {tenant.name}: {e}")
        import traceback
        logger.error(traceback.format_exc())

def main():
    logger.info("Updating prompts in database...")
    
    master_db = next(get_master_db())
    tenants = master_db.query(Tenant).all()
    logger.info(f"Found {len(tenants)} tenants.")
    
    for tenant in tenants:
        logger.info(f"Processing tenant {tenant.name} (ID: {tenant.id})...")
        for prompt_template in DEFAULT_PROMPT_TEMPLATES:
            update_prompt_in_db(tenant, prompt_template)
            
    logger.info("✅ Prompt update completed!")

if __name__ == "__main__":
    main()
