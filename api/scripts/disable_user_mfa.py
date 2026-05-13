#!/usr/bin/env python3
"""
Script to disable MFA for a user.

Clears MFA settings in the master database and, when available, the user's
primary tenant database.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

# Add the parent directory to the path so we can import from the core module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db, set_tenant_context, clear_tenant_context
from core.models.models import MasterUser, Tenant
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager


def disable_mfa_fields(user):
    """Clear MFA fields on a master or tenant user model."""
    user.mfa_chain_enabled = False
    user.mfa_chain_mode = "fixed"
    user.mfa_chain_factors = []
    user.mfa_factor_secrets = {}
    user.updated_at = datetime.now(timezone.utc)


def find_user(db, email=None, user_id=None):
    """Find a master user by email or ID."""
    if user_id is not None:
        return db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if email:
        return db.query(MasterUser).filter(MasterUser.email == email).first()
    return None


def sync_tenant_user_mfa(user):
    """Disable MFA for the matching user in their primary tenant database."""
    if not tenant_db_manager.tenant_database_exists(user.tenant_id):
        return False, f"Tenant database for tenant {user.tenant_id} does not exist"

    tenant_db = None
    try:
        set_tenant_context(user.tenant_id)
        SessionLocalTenant = tenant_db_manager.get_tenant_session(user.tenant_id)
        tenant_db = SessionLocalTenant()

        tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user.id).first()
        if not tenant_user:
            return False, "User was not found in the primary tenant database"

        disable_mfa_fields(tenant_user)
        tenant_db.commit()
        return True, "Tenant user MFA disabled"
    except Exception as exc:
        if tenant_db:
            tenant_db.rollback()
        return False, str(exc)
    finally:
        if tenant_db:
            tenant_db.close()
        clear_tenant_context()


def clear_active_mfa_sessions(user_id):
    """Clear active in-process MFA sessions when the commercial MFA module is available."""
    try:
        from commercial.mfa_chain.utils import clear_mfa_sessions_for_user

        clear_mfa_sessions_for_user(user_id)
        return True, "Active MFA sessions cleared"
    except Exception as exc:
        return False, str(exc)


def disable_user_mfa(email=None, user_id=None, assume_yes=False):
    """Disable MFA for a user."""
    db = next(get_master_db())

    try:
        if not email and user_id is None:
            print("🔐 Disable MFA for User")
            print("=" * 50)
            identifier = input("Enter user email or ID: ").strip()
            if not identifier:
                print("❌ Email or ID is required")
                return
            if identifier.isdigit():
                user_id = int(identifier)
            else:
                email = identifier

        user = find_user(db, email=email, user_id=user_id)
        if not user:
            identifier = email if email else user_id
            print(f"❌ User not found: {identifier}")
            return

        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_name = tenant.name if tenant else "Unknown"

        print("\n📋 User found:")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Name: {user.first_name or ''} {user.last_name or ''}".rstrip())
        print(f"   Tenant: {tenant_name} (tenant_id={user.tenant_id})")
        print(f"   MFA enabled: {user.mfa_chain_enabled}")
        print(f"   MFA mode: {user.mfa_chain_mode}")
        print(f"   MFA factors: {user.mfa_chain_factors or []}")

        if not assume_yes:
            confirm = input("\nDisable MFA for this user? (y/n): ").strip().lower()
            if confirm != "y":
                print("Cancelled")
                return

        disable_mfa_fields(user)
        db.commit()
        print(f"✅ Master user MFA disabled for {user.email}")

        tenant_synced, tenant_message = sync_tenant_user_mfa(user)
        if tenant_synced:
            print("✅ Tenant database MFA disabled")
        else:
            print(f"⚠️ Could not update tenant database: {tenant_message}")

        sessions_cleared, sessions_message = clear_active_mfa_sessions(user.id)
        if sessions_cleared:
            print("✅ Active MFA sessions cleared")
        else:
            print(f"⚠️ Could not clear active MFA sessions: {sessions_message}")

        print("\n✅ MFA disabled successfully")
        print(f"   Email: {user.email}")
        print("   MFA enabled: False")
        print("   MFA factors: []")

    except Exception as exc:
        print(f"❌ Error disabling MFA: {exc}")
        db.rollback()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Disable MFA for a user")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--email", help="User email address")
    group.add_argument("--user-id", type=int, help="Master user ID")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    disable_user_mfa(email=args.email, user_id=args.user_id, assume_yes=args.yes)


if __name__ == "__main__":
    main()
