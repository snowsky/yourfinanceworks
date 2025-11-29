#!/usr/bin/env python3
"""
Fix email worker encryption issues by clearing corrupted encrypted data.

This script identifies and clears encrypted fields that cannot be decrypted
with the current encryption key. This is safer than trying to re-encrypt
data we can't decrypt.

IMPORTANT: This will CLEAR encrypted data that cannot be decrypted.
Make sure you have a backup before running this script!
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import text
from core.models.database import get_master_db, set_tenant_context
from core.models.models import Tenant
from core.models.models_per_tenant import User, Client, ClientNote, Invoice, Payment, Expense
from core.services.tenant_database_manager import tenant_db_manager
from core.services.encryption_service import get_encryption_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clear_corrupted_user_data(tenant_id: int, dry_run: bool = True):
    """Clear corrupted encrypted data from User table."""
    logger.info(f"\nProcessing User table for tenant {tenant_id}...")
    
    set_tenant_context(tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(tenant_id)
    
    if not SessionLocal:
        logger.error(f"Could not get tenant database session")
        return 0
    
    db = SessionLocal()
    encryption_service = get_encryption_service()
    cleared_count = 0
    
    try:
        users = db.query(User).all()
        logger.info(f"Found {len(users)} users to check")
        
        for user in users:
            user_updated = False
            
            # Check email
            if user.email and user.email.startswith("[Encrypted data"):
                logger.info(f"  User {user.id}: Clearing corrupted email")
                if not dry_run:
                    # Set to a placeholder that can be updated later
                    user.email = f"user{user.id}@placeholder.local"
                user_updated = True
            
            # Check first_name
            if user.first_name and user.first_name.startswith("[Encrypted data"):
                logger.info(f"  User {user.id}: Clearing corrupted first_name")
                if not dry_run:
                    user.first_name = None
                user_updated = True
            
            # Check last_name
            if user.last_name and user.last_name.startswith("[Encrypted data"):
                logger.info(f"  User {user.id}: Clearing corrupted last_name")
                if not dry_run:
                    user.last_name = None
                user_updated = True
            
            # Check google_id
            if user.google_id and user.google_id.startswith("[Encrypted data"):
                logger.info(f"  User {user.id}: Clearing corrupted google_id")
                if not dry_run:
                    user.google_id = None
                user_updated = True
            
            # Check azure_ad_id
            if user.azure_ad_id and user.azure_ad_id.startswith("[Encrypted data"):
                logger.info(f"  User {user.id}: Clearing corrupted azure_ad_id")
                if not dry_run:
                    user.azure_ad_id = None
                user_updated = True
            
            if user_updated:
                cleared_count += 1
        
        if not dry_run:
            db.commit()
            logger.info(f"✓ Cleared corrupted data for {cleared_count} users")
        else:
            logger.info(f"[DRY RUN] Would clear corrupted data for {cleared_count} users")
        
        return cleared_count
    
    except Exception as e:
        logger.error(f"Error processing users: {e}")
        db.rollback()
        import traceback
        logger.error(traceback.format_exc())
        return 0
    finally:
        db.close()


def clear_corrupted_client_data(tenant_id: int, dry_run: bool = True):
    """Clear corrupted encrypted data from Client table."""
    logger.info(f"\nProcessing Client table for tenant {tenant_id}...")
    
    set_tenant_context(tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(tenant_id)
    
    if not SessionLocal:
        logger.error(f"Could not get tenant database session")
        return 0
    
    db = SessionLocal()
    cleared_count = 0
    
    try:
        clients = db.query(Client).all()
        logger.info(f"Found {len(clients)} clients to check")
        
        for client in clients:
            client_updated = False
            
            # Check encrypted fields
            if client.name and client.name.startswith("[Encrypted data"):
                logger.info(f"  Client {client.id}: Clearing corrupted name")
                if not dry_run:
                    client.name = f"Client {client.id}"
                client_updated = True
            
            if client.email and client.email.startswith("[Encrypted data"):
                logger.info(f"  Client {client.id}: Clearing corrupted email")
                if not dry_run:
                    client.email = f"client{client.id}@placeholder.local"
                client_updated = True
            
            if client.phone and client.phone.startswith("[Encrypted data"):
                logger.info(f"  Client {client.id}: Clearing corrupted phone")
                if not dry_run:
                    client.phone = None
                client_updated = True
            
            if client.address and client.address.startswith("[Encrypted data"):
                logger.info(f"  Client {client.id}: Clearing corrupted address")
                if not dry_run:
                    client.address = None
                client_updated = True
            
            if client.company and client.company.startswith("[Encrypted data"):
                logger.info(f"  Client {client.id}: Clearing corrupted company")
                if not dry_run:
                    client.company = None
                client_updated = True
            
            if client_updated:
                cleared_count += 1
        
        if not dry_run:
            db.commit()
            logger.info(f"✓ Cleared corrupted data for {cleared_count} clients")
        else:
            logger.info(f"[DRY RUN] Would clear corrupted data for {cleared_count} clients")
        
        return cleared_count
    
    except Exception as e:
        logger.error(f"Error processing clients: {e}")
        db.rollback()
        import traceback
        logger.error(traceback.format_exc())
        return 0
    finally:
        db.close()


def fix_tenant_encryption(tenant_id: int, dry_run: bool = True):
    """Fix encryption issues for a specific tenant."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Fixing encryption for tenant {tenant_id}")
    if dry_run:
        logger.info("(DRY RUN MODE - no changes will be made)")
    logger.info(f"{'='*60}\n")
    
    total_cleared = 0
    
    # Clear corrupted user data
    total_cleared += clear_corrupted_user_data(tenant_id, dry_run)
    
    # Clear corrupted client data
    total_cleared += clear_corrupted_client_data(tenant_id, dry_run)
    
    # Add more tables as needed...
    
    logger.info(f"\n{'='*60}")
    if dry_run:
        logger.info(f"[DRY RUN] Would clear corrupted data for {total_cleared} records")
    else:
        logger.info(f"✓ Cleared corrupted data for {total_cleared} records")
    logger.info(f"{'='*60}\n")
    
    return total_cleared


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix email worker encryption issues")
    parser.add_argument("--tenant-id", type=int, help="Specific tenant ID to fix (default: all)")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry-run)")
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    logger.info("Email Worker Encryption Fix Tool")
    logger.info("=" * 60)
    
    if dry_run:
        logger.info("Running in DRY RUN mode - no changes will be made")
        logger.info("Use --apply flag to actually apply changes")
    else:
        logger.warning("⚠️  APPLYING CHANGES - corrupted encrypted data will be cleared!")
        logger.warning("Make sure you have a backup before proceeding!")
        response = input("\nAre you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Aborted by user")
            return 0
    
    logger.info("=" * 60)
    
    # Get tenants to process
    master_db = next(get_master_db())
    try:
        if args.tenant_id:
            tenants = master_db.query(Tenant).filter(
                Tenant.id == args.tenant_id,
                Tenant.is_active == True
            ).all()
        else:
            tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        
        logger.info(f"\nFound {len(tenants)} tenant(s) to process\n")
        
        total_cleared = 0
        for tenant in tenants:
            cleared = fix_tenant_encryption(tenant.id, dry_run)
            total_cleared += cleared
        
        logger.info(f"\n{'='*60}")
        if dry_run:
            logger.info(f"[DRY RUN] Would clear corrupted data for {total_cleared} total records")
            logger.info("\nTo apply these changes, run with --apply flag")
        else:
            logger.info(f"✓ Successfully cleared corrupted data for {total_cleared} total records")
        logger.info(f"{'='*60}\n")
        
        return 0
    
    finally:
        master_db.close()


if __name__ == "__main__":
    sys.exit(main())
