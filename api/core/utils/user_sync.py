"""
User synchronization utilities for multi-tenant system.
Ensures users exist in tenant databases when added to organizations.
"""

import logging
from sqlalchemy.orm import Session
from core.models.models import MasterUser
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager

logger = logging.getLogger(__name__)

def sync_user_to_tenant_database(master_user: MasterUser, tenant_id: int, role: str = None) -> bool:
    """
    Sync a master user to a tenant database.
    Creates the user in the tenant database if they don't exist.

    Args:
        master_user: The master user to sync
        tenant_id: The tenant database to sync to
        role: Optional role override for this tenant

    Returns:
        bool: True if sync was successful, False otherwise
    """
    try:
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()

        try:
            # Check if user already exists in tenant database
            existing_tenant_user = tenant_db.query(TenantUser).filter(
                TenantUser.id == master_user.id
            ).first()

            if existing_tenant_user:
                # Update fields that might have changed
                updated = False
                if role and existing_tenant_user.role != role:
                    existing_tenant_user.role = role
                    updated = True
                if existing_tenant_user.is_active != master_user.is_active:
                    existing_tenant_user.is_active = master_user.is_active
                    updated = True
                if existing_tenant_user.is_superuser != master_user.is_superuser:
                    existing_tenant_user.is_superuser = master_user.is_superuser
                    updated = True
                if existing_tenant_user.is_verified != master_user.is_verified:
                    existing_tenant_user.is_verified = master_user.is_verified
                    updated = True
                if existing_tenant_user.theme != master_user.theme:
                    existing_tenant_user.theme = master_user.theme
                    updated = True

                # Always update timestamps to keep in sync
                existing_tenant_user.updated_at = master_user.updated_at

                if updated:
                    tenant_db.commit()
                    logger.info(f"Updated user {master_user.email} in tenant {tenant_id}")
                else:
                    logger.debug(f"User {master_user.email} already exists in tenant {tenant_id}, no changes needed")
                return True

            # Create user in tenant database with explicit ID
            # Use merge() to handle potential conflicts gracefully
            tenant_user = tenant_db.merge(TenantUser(
                id=master_user.id,  # Use same ID as master user
                email=master_user.email,
                hashed_password=master_user.hashed_password,
                first_name=master_user.first_name,
                last_name=master_user.last_name,
                role=role or master_user.role,
                is_active=master_user.is_active,
                is_superuser=master_user.is_superuser,
                is_verified=master_user.is_verified,
                theme=master_user.theme,
                google_id=master_user.google_id,
                created_at=master_user.created_at,
                updated_at=master_user.updated_at
            ))
            tenant_db.commit()

            # Seed currencies if they don't exist
            _seed_currencies_if_needed(tenant_db)

            logger.info(f"Successfully synced user {master_user.email} to tenant {tenant_id}")
            return True

        finally:
            tenant_db.close()

    except Exception as e:
        logger.error(f"Failed to sync user {master_user.email} to tenant {tenant_id}: {e}")
        # Log more details for debugging
        import traceback
        logger.debug(f"User sync error details: {traceback.format_exc()}")
        # Check if it's a duplicate key error and handle gracefully
        if "duplicate key value" in str(e).lower() or "unique constraint" in str(e).lower():
            logger.warning(f"User {master_user.email} already exists in tenant {tenant_id}, treating as successful sync")
            return True
        return False

def remove_user_from_tenant_database(user_id: int, tenant_id: int) -> bool:
    """
    Remove a user from a tenant database when they're removed from the organization.
    
    Args:
        user_id: The user ID to remove
        tenant_id: The tenant database to remove from
    
    Returns:
        bool: True if removal was successful, False otherwise
    """
    try:
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()
        
        try:
            # Find and remove user from tenant database
            tenant_user = tenant_db.query(TenantUser).filter(
                TenantUser.id == user_id
            ).first()
            
            if tenant_user:
                tenant_db.delete(tenant_user)
                tenant_db.commit()
                logger.info(f"Successfully removed user {user_id} from tenant {tenant_id}")
                return True
            else:
                logger.info(f"User {user_id} not found in tenant {tenant_id} database")
                return True  # Consider it successful if user doesn't exist
            
        finally:
            tenant_db.close()
            
    except Exception as e:
        logger.error(f"Failed to remove user {user_id} from tenant {tenant_id}: {e}")
        return False

def _seed_currencies_if_needed(tenant_db: Session):
    """Seed basic currencies if the tenant database doesn't have any"""
    try:
        from core.models.models_per_tenant import SupportedCurrency
        from datetime import datetime, timezone
        from sqlalchemy import func
        
        # Check if currencies already exist using SQLAlchemy func.count()
        existing_count = tenant_db.query(func.count(SupportedCurrency.id)).scalar()
        if existing_count > 0:
            return
        
        # Basic currencies to seed
        currencies = [
            {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2},
            {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2},
            {"code": "GBP", "name": "British Pound", "symbol": "£", "decimal_places": 2},
            {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimal_places": 0},
            {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$", "decimal_places": 2},
            {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "decimal_places": 2},
        ]
        
        for currency_data in currencies:
            currency = SupportedCurrency(
                code=currency_data["code"],
                name=currency_data["name"],
                symbol=currency_data["symbol"],
                decimal_places=currency_data["decimal_places"],
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            tenant_db.add(currency)
        
        tenant_db.commit()
        logger.info("Seeded basic currencies for tenant database")
        
    except Exception as e:
        logger.error(f"Failed to seed currencies: {e}")
        tenant_db.rollback()