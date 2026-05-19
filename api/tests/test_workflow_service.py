import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from core.services.workflow_service import WorkflowService
from core.models.models_per_tenant import (
    WorkflowDefinition,
    WorkflowExecutionLog,
    Invoice,
    Reminder,
    User,
    Client
)


class TestWorkflowService:
    """Test suite for WorkflowService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        """Create WorkflowService instance"""
        # Patch FeatureConfigService to always return True for workflow_automation
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True):
            return WorkflowService(mock_db)

    @pytest.fixture
    def sample_system_workflow(self):
        """Create a sample system workflow"""
        return WorkflowDefinition(
            id=1,
            name="Overdue invoice follow-up",
            key="invoice-overdue-reminder-task",
            description="System workflow for overdue invoices",
            trigger_type="invoice_became_overdue",
            conditions={"invoice_statuses": ["sent"]},
            actions={"send_internal_notification": True, "create_internal_task": True},
            is_enabled=True,
            is_system=True,
            is_default=True,
        )

    @pytest.fixture
    def sample_custom_workflow(self):
        """Create a sample user custom workflow"""
        return WorkflowDefinition(
            id=2,
            name="Custom Escalation",
            key="custom-escalation",
            description="My custom overdue logic",
            trigger_type="invoice_became_overdue",
            conditions={"invoice_statuses": ["sent"]},
            actions={"send_internal_notification": True, "create_internal_task": False},
            is_enabled=True,
            is_system=False,
            is_default=False,
        )

    @pytest.fixture
    def sample_invoice(self):
        """Create a sample invoice"""
        return Invoice(
            id=101,
            number="INV-2026-001",
            client_id=201,
            amount=1500.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) - timedelta(days=5),
            status="sent",
            is_deleted=False,
            created_by_user_id=1,
        )

    @pytest.fixture
    def sample_user(self):
        """Create a sample user"""
        return User(
            id=1,
            email="testowner@financeworks.com",
            first_name="Teammate",
            last_name="One",
            is_active=True,
            role="admin"
        )

    @pytest.fixture
    def sample_client(self):
        """Create a sample client"""
        return Client(
            id=201,
            name="ACME Corp"
        )

    def test_ensure_default_workflows_creation(self, service, mock_db):
        """Test default workflows are created if missing"""
        mock_db.query.return_value.filter.return_value.first.return_value = None  # None exists

        service.ensure_default_workflows()

        assert mock_db.add.called
        assert mock_db.commit.called

    def test_ensure_default_workflows_noop(self, service, mock_db, sample_system_workflow):
        """Test default workflows are not recreated if they exist"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_system_workflow

        service.ensure_default_workflows()

        assert not mock_db.add.called
        assert not mock_db.commit.called

    def test_list_workflows(self, service, mock_db, sample_system_workflow, sample_custom_workflow):
        """Test listing workflows returns ordered results"""
        workflows = [sample_system_workflow, sample_custom_workflow]
        mock_db.query.return_value.order_by.return_value.all.return_value = workflows

        # Mock ensure_default_workflows to avoid DB calls
        with patch.object(service, "ensure_default_workflows"):
            result = service.list_workflows()
            assert result == workflows

    def test_get_catalog(self, service):
        """Test catalog content returns triggers and actions"""
        catalog = service.get_catalog()
        assert "triggers" in catalog
        assert "actions" in catalog
        assert len(catalog["triggers"]) > 0
        assert len(catalog["actions"]) > 0

    def test_create_workflow_success(self, service, mock_db, sample_custom_workflow):
        """Test creating a custom workflow successfully"""
        mock_db.query.return_value.filter.return_value.first.return_value = None  # Key is unique

        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="Custom Escalation",
                description="My custom overdue logic",
                trigger_type="invoice_became_overdue",
                action_ids=["send_internal_notification"],
            )

            assert workflow.name == "Custom Escalation"
            assert workflow.trigger_type == "invoice_became_overdue"
            assert workflow.actions["send_internal_notification"] is True
            assert workflow.actions["create_internal_task"] is False
            assert workflow.is_system is False
            assert mock_db.add.called
            assert mock_db.commit.called

    def test_create_workflow_unsupported_trigger(self, service):
        """Test creating custom workflow raises ValueError for invalid trigger"""
        with patch.object(service, "ensure_default_workflows"):
            with pytest.raises(ValueError, match="Unsupported workflow trigger"):
                service.create_workflow(
                    name="Bad Trigger",
                    description="",
                    trigger_type="invalid_trigger_name",
                    action_ids=["send_internal_notification"],
                )

    def test_create_workflow_empty_actions(self, service):
        """Test creating custom workflow raises ValueError for empty actions list"""
        with patch.object(service, "ensure_default_workflows"):
            with pytest.raises(ValueError, match="Select at least one workflow action"):
                service.create_workflow(
                    name="No Actions",
                    description="",
                    trigger_type="invoice_became_overdue",
                    action_ids=[],
                )

    def test_update_workflow_success(self, service, mock_db, sample_custom_workflow):
        """Test successfully editing a custom workflow"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_custom_workflow

        updated = service.update_workflow(
            workflow_id=sample_custom_workflow.id,
            name="New Name",
            description="New description",
            action_ids=["send_internal_notification", "create_internal_task"],
        )

        assert updated.name == "New Name"
        assert updated.description == "New description"
        assert updated.actions["send_internal_notification"] is True
        assert updated.actions["create_internal_task"] is True
        assert mock_db.commit.called

    def test_update_workflow_system_fails(self, service, mock_db, sample_system_workflow):
        """Test that editing a system workflow raises ValueError"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_system_workflow

        with pytest.raises(ValueError, match="System workflows cannot be edited"):
            service.update_workflow(
                workflow_id=sample_system_workflow.id,
                name="System Modified",
                description="Changing descriptions",
                action_ids=["send_internal_notification"],
            )

    def test_delete_workflow_success(self, service, mock_db, sample_custom_workflow):
        """Test successfully deleting a custom workflow"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_custom_workflow

        service.delete_workflow(sample_custom_workflow.id)

        mock_db.delete.assert_called_once_with(sample_custom_workflow)
        assert mock_db.commit.called

    def test_delete_workflow_system_fails(self, service, mock_db, sample_system_workflow):
        """Test that deleting a system workflow raises ValueError"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_system_workflow

        with pytest.raises(ValueError, match="System workflows cannot be deleted"):
            service.delete_workflow(sample_system_workflow.id)

        assert not mock_db.delete.called

    def test_list_execution_logs(self, service, mock_db, sample_system_workflow):
        """Test execution logs retrieval with paging and resolving workflow names"""
        log = WorkflowExecutionLog(
            id=10,
            workflow_id=1,
            event_key="invoice:101:overdue",
            entity_type="invoice",
            entity_id="101",
            status="success",
            created_at=datetime.now(timezone.utc)
        )
        log.workflow = sample_system_workflow

        # Mock the chained sqlalchemy queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [log]
        mock_db.query.return_value = mock_query

        res = service.list_execution_logs(workflow_id=1, status="success", limit=10, offset=0)

        assert res["total"] == 1
        assert len(res["logs"]) == 1
        assert res["logs"][0].workflow_name == "Overdue invoice follow-up"
        assert res["logs"][0].workflow_key == "invoice-overdue-reminder-task"

    def test_process_due_invoice_workflows_success(
        self, service, mock_db, sample_system_workflow, sample_invoice, sample_user, sample_client
    ):
        """Test success path for invoice overdue workflows, generating notifications, tasks and success logs"""
        # Patch FeatureConfigService
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "ensure_default_workflows"), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_assigned_user", return_value=sample_user), \
             patch("core.services.workflow_service.send_notification") as mock_notification:

            # Mock DB queries
            # 1. query(WorkflowDefinition)
            # 2. query(Invoice)
            # 3. query(Client)
            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_system_workflow])))),
                Invoice: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice])))),
                Client: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))),
            }[model]

            # We need mock_db.flush() and mock_db.add() and mock_db.commit() to work
            mock_reminder = Reminder(id=888)
            with patch.object(service, "_create_internal_task", return_value=mock_reminder):
                stats = service.process_due_invoice_workflows()

                assert stats["processed_count"] == 1
                assert stats["created_task_count"] == 1
                assert stats["notification_count"] == 1
                assert len(stats["errors"]) == 0
                assert mock_notification.called
                assert mock_db.commit.called

                # Assert execution log added
                added_objs = [call[0][0] for call in mock_db.add.call_args_list]
                execution_logs = [obj for obj in added_objs if isinstance(obj, WorkflowExecutionLog)]
                assert len(execution_logs) == 1
                assert execution_logs[0].status == "success"
                assert execution_logs[0].entity_id == "101"

    def test_process_due_invoice_workflows_failure_logged(
        self, service, mock_db, sample_system_workflow, sample_invoice, sample_client
    ):
        """Test overdue workflow failure rolls back business changes and writes a failed execution log in DB"""
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "ensure_default_workflows"), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_assigned_user", return_value=None):  # Will raise ValueError

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_system_workflow])))),
                Invoice: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice])))),
                Client: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))),
            }[model]

            stats = service.process_due_invoice_workflows()

            assert stats["processed_count"] == 1
            assert len(stats["errors"]) == 1
            assert "No eligible user found to own invoice" in stats["errors"][0]

            # Verify transaction rollbacks occurred
            assert mock_db.rollback.called
            # Verify final commit occurred (saving the error execution log)
            assert mock_db.commit.called

            # Check that a failed execution log was added to DB
            added_objs = [call[0][0] for call in mock_db.add.call_args_list]
            failed_logs = [obj for obj in added_objs if isinstance(obj, WorkflowExecutionLog)]
            assert len(failed_logs) == 1
            assert failed_logs[0].status == "failed"
            assert "No eligible user found" in failed_logs[0].details["error"]


if __name__ == "__main__":
    pytest.main([__file__])
