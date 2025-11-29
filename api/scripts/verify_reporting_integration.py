#!/usr/bin/env python3
"""
Reporting Module Integration Verification Script

This script verifies that the reporting module is properly integrated with the existing system.
"""

import os
import sys
import importlib.util
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.utils.file_validation import validate_file_path

def check_file_exists(file_path, description):
    """Check if a file exists and report the result"""
    if os.path.exists(file_path):
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - NOT FOUND")
        return False

def check_content_in_file(file_path, content, description):
    """Check if content exists in a file"""
    try:
        # Validate file path
        try:
            safe_path = validate_file_path(file_path)
        except ValueError as e:
            print(f"❌ {description} - Invalid path: {e}")
            return False
        with open(safe_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
            if content in file_content:
                print(f"✅ {description}")
                return True
            else:
                print(f"❌ {description} - NOT FOUND")
                return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def verify_rbac_integration():
    """Verify RBAC integration"""
    print("\n🔐 Verifying RBAC Integration...")
    
    try:
        # Import RBAC functions
        sys.path.append('.')
        from core.utils.rbac import (
            can_generate_reports, can_manage_report_templates, 
            can_schedule_reports, require_report_access
        )
        
        # Test with mock user objects
        class MockUser:
            def __init__(self, role):
                self.role = role
        
        admin_user = MockUser("admin")
        user_user = MockUser("user") 
        viewer_user = MockUser("viewer")
        
        # Test admin permissions
        assert can_generate_reports(admin_user) == True
        assert can_manage_report_templates(admin_user) == True
        assert can_schedule_reports(admin_user) == True
        print("✅ Admin user has all reporting permissions")
        
        # Test regular user permissions
        assert can_generate_reports(user_user) == True
        assert can_manage_report_templates(user_user) == True
        assert can_schedule_reports(user_user) == True
        print("✅ Regular user has all reporting permissions")
        
        # Test viewer permissions
        assert can_generate_reports(viewer_user) == False
        assert can_manage_report_templates(viewer_user) == False
        assert can_schedule_reports(viewer_user) == False
        print("✅ Viewer user has no reporting permissions")
        
        return True
        
    except Exception as e:
        print(f"❌ RBAC integration test failed: {e}")
        return False

def verify_main_app_integration():
    """Verify main app integration"""
    print("\n🚀 Verifying Main App Integration...")
    
    success = True
    
    # Check that reports router is included in main.py
    success &= check_content_in_file(
        "main.py", 
        "reports", 
        "Reports router imported in main.py"
    )
    
    success &= check_content_in_file(
        "main.py",
        "reports.router",
        "Reports router included in main.py"
    )
    
    return success

def verify_ui_integration():
    """Verify UI integration"""
    print("\n🎨 Verifying UI Integration...")
    
    success = True
    
    # Check reports page exists
    success &= check_file_exists(
        "ui/src/pages/Reports.tsx",
        "Reports page component"
    )
    
    # Check navigation integration
    success &= check_content_in_file(
        "ui/src/components/layout/AppSidebar.tsx",
        "navigation.reports",
        "Reports navigation item in sidebar"
    )
    
    success &= check_content_in_file(
        "ui/src/components/layout/AppSidebar.tsx", 
        "/reports",
        "Reports route in sidebar"
    )
    
    # Check translation exists
    success &= check_content_in_file(
        "ui/src/i18n/locales/en.json",
        '"reports": "Reports"',
        "Reports translation in English locale"
    )
    
    # Check route configuration
    success &= check_content_in_file(
        "ui/src/App.tsx",
        "/reports",
        "Reports route configured in App.tsx"
    )
    
    return success

def verify_database_integration():
    """Verify database integration"""
    print("\n🗄️ Verifying Database Integration...")
    
    success = True
    
    # Check migration exists
    success &= check_file_exists(
        "alembic/versions/add_reporting_tables.py",
        "Reporting tables migration"
    )
    
    # Check migration has proper revision chain
    success &= check_content_in_file(
        "alembic/versions/add_reporting_tables.py",
        "down_revision = '951a7ee5381c'",
        "Migration has proper revision chain"
    )
    
    # Check deployment script exists
    success &= check_file_exists(
        "scripts/deploy_reporting_migration.sh",
        "Migration deployment script"
    )
    
    return success

def verify_service_files():
    """Verify all service files exist"""
    print("\n⚙️ Verifying Service Files...")
    
    success = True
    
    services = [
        ("routers/reports.py", "Reports router"),
        ("services/report_service.py", "Report service"),
        ("services/report_template_service.py", "Report template service"),
        ("services/scheduled_report_service.py", "Scheduled report service"),
        ("services/report_history_service.py", "Report history service"),
        ("services/report_data_aggregator.py", "Report data aggregator"),
        ("services/report_exporter.py", "Report exporter"),
        ("schemas/report.py", "Report schemas"),
    ]
    
    for file_path, description in services:
        success &= check_file_exists(file_path, description)
    
    return success

def verify_ui_components():
    """Verify UI components exist"""
    print("\n🧩 Verifying UI Components...")
    
    success = True
    
    components = [
        ("ui/src/components/reports/ReportGenerator.tsx", "Report generator component"),
        ("ui/src/components/reports/ReportFilters.tsx", "Report filters component"),
        ("ui/src/components/reports/ReportPreview.tsx", "Report preview component"),
        ("ui/src/components/reports/ExportFormatSelector.tsx", "Export format selector"),
        ("ui/src/components/reports/ReportTypeSelector.tsx", "Report type selector"),
        ("ui/src/components/reports/TemplateManager.tsx", "Template manager component"),
        ("ui/src/components/reports/ScheduledReportsManager.tsx", "Scheduled reports manager"),
    ]
    
    for file_path, description in components:
        success &= check_file_exists(file_path, description)
    
    return success

def main():
    """Main verification function"""
    print("🔍 Reporting Module Integration Verification")
    print("=" * 50)
    
    # Change to API directory if we're not already there
    if os.path.exists("api"):
        os.chdir("api")
    
    all_checks_passed = True
    
    # Run all verification checks
    all_checks_passed &= verify_rbac_integration()
    all_checks_passed &= verify_main_app_integration()
    all_checks_passed &= verify_database_integration()
    all_checks_passed &= verify_service_files()
    
    # Change back to root for UI checks
    if os.path.basename(os.getcwd()) == "api":
        os.chdir("..")
    
    all_checks_passed &= verify_ui_integration()
    all_checks_passed &= verify_ui_components()
    
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("🎉 All integration checks PASSED!")
        print("✅ Reporting module is properly integrated with the existing system.")
        print("\n📋 Integration Summary:")
        print("   ✅ RBAC permissions configured")
        print("   ✅ Main app router integration")
        print("   ✅ Database migration ready")
        print("   ✅ UI navigation integrated")
        print("   ✅ All service files present")
        print("   ✅ All UI components present")
        return 0
    else:
        print("❌ Some integration checks FAILED!")
        print("🔧 Please review the failed checks above and fix any issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())