#!/usr/bin/env python3
"""
Compare encryption keys between API and OCR worker containers.
"""

import os
import sys
import logging
import base64

# Add the API directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Compare encryption keys and context."""
    logger.info("Comparing encryption keys and context...")
    
    try:
        from core.models.database import set_tenant_context
        from core.services.key_management_service import get_key_management_service
        
        # Set tenant context
        set_tenant_context(1)
        
        # Get key management service
        key_service = get_key_management_service()
        
        # Get tenant key
        tenant_key = key_service.retrieve_tenant_key(1)
        logger.info(f"Tenant key (base64): {tenant_key[:20]}...")
        
        # Check master key
        master_key_path = "/app/keys/master.key"
        if os.path.exists(master_key_path):
            with open(master_key_path, 'rb') as f:
                master_key_b64 = f.read().decode('utf-8').strip()
                logger.info(f"Master key (base64): {master_key_b64[:20]}...")
        else:
            logger.error("Master key file not found")
            
        # Check database connection
        from core.models.database import SessionLocal as get_db_session
        db = get_db_session()
        try:
            from core.models.models import TenantKey
            tenant_key_record = db.query(TenantKey).filter(TenantKey.tenant_id == 1).first()
            if tenant_key_record:
                logger.info(f"Database tenant key ID: {tenant_key_record.key_id}")
                logger.info(f"Database tenant key version: {tenant_key_record.version}")
                logger.info(f"Database tenant key active: {tenant_key_record.is_active}")
            else:
                logger.error("No tenant key found in database")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error comparing keys: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)