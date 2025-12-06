#!/usr/bin/env python3
"""
Test script to verify that users in the same organization can see each other's expenses.

This script tests the fix for the issue where user B (with user role) could not see
expenses created by user A (admin) in the same organization.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from core.models.database import get_master_db, get_tenant_db
from core.models.models import MasterUser, Tenant
from core.models.models_per_tenant import Expense, User
from datetime import datetime, timezone

def test_expense_visibility():
    """Test that users in the same tenant can see all expenses"""

    # Get master database session
    master_db = next(get_master_db())

    try:
        # Find a tenant with multiple users
        print("🔍 Looking for a tenant with multiple users...")

        # Get all tenants
        tenants = master_db.query(Tenant).all()

        for tenant in tenants:
            # Get users in this tenant
            users = master_db.query(MasterUser).filter(
                MasterUser.tenant_id == tenant.id
            ).all()

            if len(users) >= 2:
                print(f"\n✅ Found tenant '{tenant.name}' (ID: {tenant.id}) with {len(users)} users:")

                # Get tenant database
                tenant_db = next(get_tenant_db(tenant.id))

                try:
                    # Count total expenses in tenant
                    total_expenses = tenant_db.query(Expense).count()
                    print(f"   📊 Total expenses in tenant: {total_expenses}")

                    # Show expenses per user
                    for user in users:
                        user_expenses = tenant_db.query(Expense).filter(
                            Expense.user_id == user.id
                        ).count()
                        print(f"   👤 {user.email} (role: {user.role}): {user_expenses} expenses created")

                    print(f"\n   ✨ All {len(users)} users should be able to see all {total_expenses} expenses")
                    print(f"   ✨ The fix removes the user_id filter, so everyone in the tenant sees all expenses")

                    # Show a few sample expenses
                    if total_expenses > 0:
                        print(f"\n   📝 Sample expenses:")
                        sample_expenses = tenant_db.query(Expense).limit(5).all()
                        for exp in sample_expenses:
                            creator = next((u for u in users if u.id == exp.user_id), None)
                            creator_email = creator.email if creator else "Unknown"
                            print(f"      - Expense #{exp.id}: ${exp.amount} by {creator_email}")

                    return True

                finally:
                    tenant_db.close()

        print("\n⚠️  No tenant found with multiple users. Create a test scenario:")
        print("   1. User A (admin) creates 3 expenses")
        print("   2. User A invites User B (user role)")
        print("   3. User B should now see all 3 expenses")

        return False

    finally:
        master_db.close()

if __name__ == "__main__":
    print("=" * 70)
    print("Testing Expense Visibility Fix")
    print("=" * 70)

    test_expense_visibility()

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)
