#!/usr/bin/env python3
"""
Script to seed default prompt templates for all tenant databases.
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import get_master_db
from core.models.models import Tenant
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from core.constants.default_prompts import DEFAULT_PROMPT_TEMPLATES

def seed_prompt_templates():
    """Seed default prompt templates for all tenant databases"""
    try:
        # Get master database session
        master_db = next(get_master_db())
        
        # Get all active tenants
        tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        
        logger.info(f"Found {len(tenants)} active tenants")

        for tenant in tenants:
            try:
                # Construct tenant database URL
                tenant_db_url = f"postgresql://postgres:password@postgres-master:5432/tenant_{tenant.id}"
                tenant_engine = create_engine(tenant_db_url)
                
                with tenant_engine.connect() as connection:
                    # Check if prompt_templates table exists
                    result = connection.execute(text("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'prompt_templates'
                    """))
                    
                    if not result.fetchone():
                        logger.warning(f"prompt_templates table does not exist for tenant_{tenant.id}, skipping")
                        continue
                    
                    # Check if templates already exist
                    existing_templates = connection.execute(text("""
                        SELECT name FROM prompt_templates WHERE version = 1
                    """)).fetchall()
                    existing_names = {row[0] for row in existing_templates}
                    
                    templates_to_add = [t for t in DEFAULT_PROMPT_TEMPLATES if t["name"] not in existing_names]
                    
                    if not templates_to_add:
                        logger.info(f"All default templates already exist for tenant_{tenant.id}")
                        continue
                    
                    logger.info(f"Adding {len(templates_to_add)} default templates to tenant_{tenant.id}")
                    
                    # Insert default templates
                    for template in templates_to_add:
                        connection.execute(text("""
                            INSERT INTO prompt_templates (
                                name, category, description, template_content, 
                                template_variables, output_format, default_values, 
                                version, is_active, provider_overrides
                            ) VALUES (
                                :name, :category, :description, :template_content,
                                :template_variables, :output_format, :default_values,
                                1, true, :provider_overrides
                            )
                        """), {
                            'name': template['name'],
                            'category': template['category'],
                            'description': template['description'],
                            'template_content': template['template_content'],
                            'template_variables': template['template_variables'],
                            'output_format': template['output_format'],
                            'default_values': template['default_values'],
                            'provider_overrides': template['provider_overrides']
                        })
                    
                    connection.commit()
                    logger.info(f"Successfully seeded default templates for tenant_{tenant.id}")

                    # Seed review_worker_enabled setting
                    connection.execute(text("""
                        INSERT INTO settings (key, value, category, description, is_public)
                        VALUES ('review_worker_enabled', 'true', 'system', 'Enable background AI review processing', false)
                        ON CONFLICT (key) DO NOTHING
                    """))
                    connection.commit()
                    logger.info(f"Seeded review_worker_enabled setting for tenant_{tenant.id}")
                    
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.id}: {e}")
                continue
        
        logger.info("Prompt templates seeding completed for all tenant databases")
        
    except Exception as e:
        logger.error(f"Error seeding prompt templates: {e}")
        raise

if __name__ == "__main__":
    seed_prompt_templates()