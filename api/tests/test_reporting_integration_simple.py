"""
Simple integration tests for the Reporting Module

These tests verify basic integration without complex imports.
"""

import pytest
from unittest.mock import Mock
import os


class TestReportingRBACIntegration:
    """Test reporting module integration with RBAC system"""
    
    def test_admin_user_has_all_reporting_permissions(self):
        """Test that admin users have all reporting permissions"""
        from core.utils.rbac import (
            can_generate_reports, can_manage_report_templates, 
            can_schedule_reports
        )
        
        admin_user = Mock()
        admin_user.role = "admin"
        
        assert can_generate_reports(admin_user) is True
        assert can_manage_report_templates(admin_user) is True
        assert can_schedule_reports(admin_user) is True
    
    def test_regular_user_has_reporting_permissions(self):
        """Test that regular users have reporting permissions"""
        from core.utils.rbac import (
            can_generate_reports, can_manage_report_templates, 
            can_schedule_reports
        )
        
        regular_user = Mock()
        regular_user.role = "user"
        
        assert can_generate_reports(regular_user) is True
        assert can_manage_report_templates(regular_user) is True
        assert can_schedule_reports(regular_user) is True
    
    def test_viewer_user_has_no_reporting_permissions(self):
        """Test that viewer users have no reporting permissions"""
        from core.utils.rbac import (
            can_generate_reports, can_manage_report_templates, 
            can_schedule_reports
        )
        
        viewer_user = Mock()
        viewer_user.role = "viewer"
        
        assert can_generate_reports(viewer_user) is False
        assert can_manage_report_templates(viewer_user) is False
        assert can_schedule_reports(viewer_user) is False


class TestReportingFileIntegration:
    """Test reporting module file integration"""
    
    def test_reports_router_exists(self):
        """Test that reports router file exists"""
        assert os.path.exists("api/routers/reports.py")
    
    def test_report_services_exist(self):
        """Test that report service files exist"""
        services = [
            "api/services/report_service.py",
            "api/services/report_template_service.py", 
            "api/services/scheduled_report_service.py",
            "api/services/report_history_service.py",
            "api/services/report_data_aggregator.py",
            "api/services/report_exporter.py"
        ]
        
        for service_file in services:
            assert os.path.exists(service_file), f"Service file {service_file} does not exist"
    
    def test_report_models_exist(self):
        """Test that report model definitions exist"""
        # Check that models file contains report models
        with open("api/models/models_per_tenant.py", "r") as f:
            content = f.read()
            
        assert "class ReportTemplate" in content
        assert "class ScheduledReport" in content  
        assert "class ReportHistory" in content
    
    def test_report_schemas_exist(self):
        """Test that report schema definitions exist"""
        assert os.path.exists("api/schemas/report.py")
        
        # Check that schemas file contains report schemas
        with open("api/schemas/report.py", "r") as f:
            content = f.read()
            
        assert "ReportTemplateCreate" in content
        assert "ReportType" in content
        assert "ExportFormat" in content


class TestReportingMigrationIntegration:
    """Test reporting module database migration integration"""
    
    def test_migration_script_exists(self):
        """Test that the reporting migration script exists"""
        assert os.path.exists("api/alembic/versions/add_reporting_tables.py")
    
    def test_deployment_script_exists(self):
        """Test that the deployment script exists"""
        assert os.path.exists("api/scripts/deploy_reporting_migration.sh")
    
    def test_migration_has_proper_revision_chain(self):
        """Test that the migration has proper revision chain"""
        with open("api/alembic/versions/add_reporting_tables.py", "r") as f:
            content = f.read()
            
        # Should have a down_revision that's not None
        assert "down_revision = '951a7ee5381c'" in content
        assert "revision = 'add_reporting_tables'" in content
    
    def test_deployment_script_is_executable(self):
        """Test that the deployment script is executable"""
        import stat
        script_path = "api/scripts/deploy_reporting_migration.sh"
        file_stat = os.stat(script_path)
        
        # Check if the file has execute permissions
        assert file_stat.st_mode & stat.S_IEXEC


class TestReportingUIIntegration:
    """Test reporting module UI integration"""
    
    def test_reports_page_exists(self):
        """Test that reports page component exists"""
        assert os.path.exists("ui/src/pages/Reports.tsx")
    
    def test_report_components_exist(self):
        """Test that report UI components exist"""
        components = [
            "ui/src/components/reports/ReportGenerator.tsx",
            "ui/src/components/reports/ReportFilters.tsx",
            "ui/src/components/reports/ReportPreview.tsx",
            "ui/src/components/reports/ExportFormatSelector.tsx",
            "ui/src/components/reports/ReportTypeSelector.tsx"
        ]
        
        for component_file in components:
            assert os.path.exists(component_file), f"Component file {component_file} does not exist"
    
    def test_navigation_translation_exists(self):
        """Test that navigation translation for reports exists"""
        with open("ui/src/i18n/locales/en.json", "r") as f:
            content = f.read()
            
        assert '"reports": "Reports"' in content
    
    def test_sidebar_includes_reports(self):
        """Test that sidebar includes reports navigation"""
        with open("ui/src/components/layout/AppSidebar.tsx", "r") as f:
            content = f.read()
            
        assert "navigation.reports" in content
        assert "/reports" in content


class TestReportingMainAppIntegration:
    """Test reporting module integration with main application"""
    
    def test_reports_router_imported_in_main(self):
        """Test that reports router is imported in main.py"""
        with open("api/main.py", "r") as f:
            content = f.read()
            
        assert "reports" in content
        assert "reports.router" in content
    
    def test_reports_route_configured_in_ui(self):
        """Test that reports route is configured in UI router"""
        with open("ui/src/App.tsx", "r") as f:
            content = f.read()
            
        assert "/reports" in content
        assert "Reports" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])