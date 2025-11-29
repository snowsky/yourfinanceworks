"""
Verification script for AI Assistant license check.

This script tests that the AI Assistant cannot be enabled without a valid license.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import HTTPException
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

def test_ai_assistant_license_check():
    """Test that enabling AI Assistant requires a valid license"""
    
    print("Testing AI Assistant License Check...")
    print("=" * 60)
    
    # Import the update_settings function
    from core.routers.settings import update_settings
    
    # Test Case 1: License Missing/Invalid - Should Fail
    print("\n[Test 1] Attempting to enable AI Assistant WITHOUT license...")
    
    with patch('routers.settings.get_master_db') as mock_master_db, \
         patch('routers.settings.get_db') as mock_db, \
         patch('routers.settings.feature_enabled') as mock_feature_enabled, \
         patch('routers.settings.require_admin'):
        
        # Setup mocks
        mock_tenant = Mock()
        mock_tenant.id = 1
        mock_tenant.enable_ai_assistant = False
        
        mock_master_session = MagicMock()
        mock_master_session.query.return_value.filter.return_value.first.return_value = mock_tenant
        mock_master_db.return_value = mock_master_session
        
        mock_tenant_session = MagicMock()
        mock_db.return_value = mock_tenant_session
        
        # Mock feature_enabled to return False (no license)
        mock_feature_enabled.return_value = False
        
        mock_user = Mock()
        mock_user.tenant_id = 1
        mock_user.id = 1
        mock_user.email = "test@example.com"
        
        settings_data = {
            "enable_ai_assistant": True
        }
        
        try:
            import asyncio
            asyncio.run(update_settings(
                settings=settings_data,
                master_db=mock_master_session,
                db=mock_tenant_session,
                current_user=mock_user
            ))
            print("❌ FAILED: Should have raised HTTPException")
            return False
        except HTTPException as e:
            if e.status_code == 402:
                print(f"✅ PASSED: Correctly blocked with 402 Payment Required")
                print(f"   Error message: {e.detail}")
            else:
                print(f"❌ FAILED: Wrong status code {e.status_code}, expected 402")
                return False
    
    # Test Case 2: License Valid - Should Succeed
    print("\n[Test 2] Attempting to enable AI Assistant WITH license...")
    
    with patch('routers.settings.get_master_db') as mock_master_db, \
         patch('routers.settings.get_db') as mock_db, \
         patch('routers.settings.feature_enabled') as mock_feature_enabled, \
         patch('routers.settings.require_admin'), \
         patch('routers.settings.log_audit_event'), \
         patch('routers.settings.tenant_db_manager'):
        
        # Setup mocks
        mock_tenant = Mock()
        mock_tenant.id = 1
        mock_tenant.enable_ai_assistant = False
        
        mock_master_session = MagicMock()
        mock_master_session.query.return_value.filter.return_value.first.return_value = mock_tenant
        mock_master_db.return_value = mock_master_session
        
        mock_tenant_session = MagicMock()
        mock_db.return_value = mock_tenant_session
        
        # Mock feature_enabled to return True (has license)
        mock_feature_enabled.return_value = True
        
        mock_user = Mock()
        mock_user.tenant_id = 1
        mock_user.id = 1
        mock_user.email = "test@example.com"
        
        settings_data = {
            "enable_ai_assistant": True
        }
        
        try:
            import asyncio
            result = asyncio.run(update_settings(
                settings=settings_data,
                master_db=mock_master_session,
                db=mock_tenant_session,
                current_user=mock_user
            ))
            print(f"✅ PASSED: Successfully enabled AI Assistant with license")
            print(f"   Result: {result}")
        except HTTPException as e:
            print(f"❌ FAILED: Should not have raised HTTPException")
            print(f"   Error: {e.detail}")
            return False
    
    # Test Case 3: Disabling AI Assistant - Should Always Work
    print("\n[Test 3] Attempting to disable AI Assistant (should work without license)...")
    
    with patch('routers.settings.get_master_db') as mock_master_db, \
         patch('routers.settings.get_db') as mock_db, \
         patch('routers.settings.feature_enabled') as mock_feature_enabled, \
         patch('routers.settings.require_admin'), \
         patch('routers.settings.log_audit_event'), \
         patch('routers.settings.tenant_db_manager'):
        
        # Setup mocks
        mock_tenant = Mock()
        mock_tenant.id = 1
        mock_tenant.enable_ai_assistant = True  # Currently enabled
        
        mock_master_session = MagicMock()
        mock_master_session.query.return_value.filter.return_value.first.return_value = mock_tenant
        mock_master_db.return_value = mock_master_session
        
        mock_tenant_session = MagicMock()
        mock_db.return_value = mock_tenant_session
        
        # Mock feature_enabled to return False (no license)
        mock_feature_enabled.return_value = False
        
        mock_user = Mock()
        mock_user.tenant_id = 1
        mock_user.id = 1
        mock_user.email = "test@example.com"
        
        settings_data = {
            "enable_ai_assistant": False
        }
        
        try:
            import asyncio
            result = asyncio.run(update_settings(
                settings=settings_data,
                master_db=mock_master_session,
                db=mock_tenant_session,
                current_user=mock_user
            ))
            print(f"✅ PASSED: Successfully disabled AI Assistant without license")
            print(f"   Result: {result}")
        except HTTPException as e:
            print(f"❌ FAILED: Should not have raised HTTPException when disabling")
            print(f"   Error: {e.detail}")
            return False
    
    # Test Case 4: Keeping AI Assistant Enabled WITHOUT license - Should Fail
    print("\n[Test 4] Attempting to keep AI Assistant enabled WITHOUT license...")
    
    with patch('routers.settings.get_master_db') as mock_master_db, \
         patch('routers.settings.get_db') as mock_db, \
         patch('routers.settings.feature_enabled') as mock_feature_enabled, \
         patch('routers.settings.require_admin'):
        
        # Setup mocks
        mock_tenant = Mock()
        mock_tenant.id = 1
        mock_tenant.enable_ai_assistant = True  # Already enabled
        
        mock_master_session = MagicMock()
        mock_master_session.query.return_value.filter.return_value.first.return_value = mock_tenant
        mock_master_db.return_value = mock_master_session
        
        mock_tenant_session = MagicMock()
        mock_db.return_value = mock_tenant_session
        
        # Mock feature_enabled to return False (no license)
        mock_feature_enabled.return_value = False
        
        mock_user = Mock()
        mock_user.tenant_id = 1
        mock_user.id = 1
        mock_user.email = "test@example.com"
        
        settings_data = {
            "enable_ai_assistant": True  # Keeping it enabled
        }
        
        try:
            import asyncio
            asyncio.run(update_settings(
                settings=settings_data,
                master_db=mock_master_session,
                db=mock_tenant_session,
                current_user=mock_user
            ))
            print("❌ FAILED: Should have raised HTTPException")
            return False
        except HTTPException as e:
            if e.status_code == 402:
                print(f"✅ PASSED: Correctly blocked with 402 Payment Required")
            else:
                print(f"❌ FAILED: Wrong status code {e.status_code}, expected 402")
                return False

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    return True

if __name__ == "__main__":
    try:
        success = test_ai_assistant_license_check()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
