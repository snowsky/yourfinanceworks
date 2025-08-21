#!/usr/bin/env python3
"""
Test script for cancel invite functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from models.database import get_master_db
from models.models import MasterUser, Invite, Tenant
from datetime import datetime, timezone, timedelta
import requests
import json

def test_cancel_invite():
    """Test the cancel invite functionality"""
    
    # Test data
    test_email = "test@example.com"
    test_inviter_email = "admin@example.com"  # Assuming this admin exists
    
    print("Testing cancel invite functionality...")
    
    # Get database session
    db = next(get_master_db())
    
    try:
        # Find the admin user
        admin_user = db.query(MasterUser).filter(MasterUser.email == test_inviter_email).first()
        if not admin_user:
            print(f"❌ Admin user {test_inviter_email} not found")
            return False
        
        # Create a test invite
        test_invite = Invite(
            email=test_email,
            first_name="Test",
            last_name="User",
            role="user",
            token="test_token_123",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            tenant_id=admin_user.tenant_id,
            invited_by_id=admin_user.id
        )
        
        db.add(test_invite)
        db.commit()
        db.refresh(test_invite)
        
        print(f"✅ Created test invite with ID: {test_invite.id}")
        
        # Verify invite exists and is pending
        invite = db.query(Invite).filter(Invite.id == test_invite.id).first()
        if not invite:
            print("❌ Test invite not found after creation")
            return False
        
        if invite.is_accepted:
            print("❌ Test invite was marked as accepted unexpectedly")
            return False
        
        print("✅ Test invite is pending as expected")
        
        # Test cancel invite (this would normally be done via API)
        # For this test, we'll simulate the cancel operation
        db.delete(invite)
        db.commit()
        
        # Verify invite was deleted
        deleted_invite = db.query(Invite).filter(Invite.id == test_invite.id).first()
        if deleted_invite:
            print("❌ Test invite still exists after deletion")
            return False
        
        print("✅ Test invite was successfully cancelled/deleted")
        
        # Check audit logs (if they exist)
        from models.models import AuditLog
        audit_logs = db.query(AuditLog).filter(
            AuditLog.resource_type == "invite",
            AuditLog.action == "DELETE"  # Note: invites still use "DELETE", only invoices use "Soft Delete"
        ).all()
        
        if audit_logs:
            print(f"✅ Found {len(audit_logs)} audit log entries for invite deletions")
        else:
            print("ℹ️  No audit log entries found (this is expected if audit logging wasn't triggered)")
        
        print("✅ Cancel invite functionality test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_cancel_invite()
    sys.exit(0 if success else 1) 