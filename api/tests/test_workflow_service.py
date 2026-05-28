import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from core.services.workflow_service import WorkflowService
from core.models.models_per_tenant import (
    WorkflowDefinition,
    WorkflowExecutionLog,
    Invoice,
    Payment,
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


    # ---------- invoice_created trigger ----------

    @pytest.fixture
    def sample_created_invoice(self):
        """Invoice created recently, eligible for the invoice_created trigger."""
        return Invoice(
            id=202,
            number="INV-2026-NEW",
            client_id=201,
            amount=750.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=14),
            status="sent",
            is_deleted=False,
            created_by_user_id=1,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_invoice_created_workflow(self):
        return WorkflowDefinition(
            id=3,
            name="Welcome new invoices",
            key="invoice-created-welcome",
            description="When a new invoice is created, notify the owner and create a review task.",
            trigger_type="invoice_created",
            conditions={},
            actions={
                "send_internal_notification": True,
                "create_internal_task": True,
                "task_type": "reminder",
                "task_title_template": "Review newly created invoice #{invoice_number}",
                "task_due_in_days": 1,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

    def test_catalog_includes_invoice_created_trigger(self, service):
        catalog = service.get_catalog()
        trigger_ids = {trigger["id"] for trigger in catalog["triggers"]}
        assert "invoice_became_overdue" in trigger_ids
        assert "invoice_created" in trigger_ids

    def test_create_workflow_accepts_invoice_created_trigger(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="On New Invoice",
                description="",
                trigger_type="invoice_created",
                action_ids=["send_internal_notification"],
            )
            assert workflow.trigger_type == "invoice_created"

    def test_process_invoice_created_workflows_success(
        self,
        service,
        mock_db,
        sample_invoice_created_workflow,
        sample_created_invoice,
        sample_user,
        sample_client,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_assigned_user", return_value=sample_user), \
             patch("core.services.workflow_service.send_notification") as mock_notification:

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice_created_workflow])))),
                Invoice: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_created_invoice])))),
                Client: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))),
            }[model]

            mock_reminder = Reminder(id=999)
            with patch.object(service, "_create_internal_task", return_value=mock_reminder):
                stats = service.process_invoice_created_workflows()

            assert stats["processed_count"] == 1
            assert stats["created_task_count"] == 1
            assert stats["notification_count"] == 1
            assert stats["errors"] == []

            # Notification uses the invoice_created event_type, not invoice_overdue.
            assert mock_notification.call_args.kwargs["event_type"] == "invoice_created"

            # Execution log uses the :created suffix.
            added = [call[0][0] for call in mock_db.add.call_args_list]
            logs = [obj for obj in added if isinstance(obj, WorkflowExecutionLog)]
            assert len(logs) == 1
            assert logs[0].status == "success"
            assert logs[0].event_key.endswith(":created")

    def test_process_invoice_created_workflows_skips_when_log_exists(
        self,
        service,
        mock_db,
        sample_invoice_created_workflow,
        sample_created_invoice,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=True):  # already processed

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice_created_workflow])))),
                Invoice: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_created_invoice])))),
            }[model]

            stats = service.process_invoice_created_workflows()

            assert stats["processed_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["created_task_count"] == 0
            assert stats["notification_count"] == 0

    def test_process_invoice_created_workflows_failure_logged(
        self,
        service,
        mock_db,
        sample_invoice_created_workflow,
        sample_created_invoice,
        sample_client,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_assigned_user", return_value=None):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice_created_workflow])))),
                Invoice: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_created_invoice])))),
                Client: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))),
            }[model]

            stats = service.process_invoice_created_workflows()

            assert stats["processed_count"] == 1
            assert len(stats["errors"]) == 1
            added = [call[0][0] for call in mock_db.add.call_args_list]
            failed = [obj for obj in added if isinstance(obj, WorkflowExecutionLog) and obj.status == "failed"]
            assert len(failed) == 1
            assert failed[0].event_key.endswith(":created")

    # ---------- dispatch + combined runner ----------

    def test_run_workflow_now_dispatches_to_invoice_created_processor(
        self, service, mock_db, sample_invoice_created_workflow
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_invoice_created_workflow
        sentinel = {"processed_count": 0, "created_task_count": 0, "notification_count": 0, "skipped_count": 0, "errors": []}

        with patch.object(service, "process_invoice_created_workflows", return_value=sentinel) as mock_processor, \
             patch.object(service, "process_due_invoice_workflows") as overdue_processor:
            result = service.run_workflow_now(sample_invoice_created_workflow.id)

            mock_processor.assert_called_once()
            overdue_processor.assert_not_called()
            assert result is sentinel

    def test_run_workflow_now_rejects_unknown_trigger(self, service, mock_db):
        workflow = WorkflowDefinition(id=99, trigger_type="some_future_trigger")
        mock_db.query.return_value.filter.return_value.first.return_value = workflow

        with pytest.raises(ValueError, match="some_future_trigger"):
            service.run_workflow_now(99)

    def test_process_all_workflows_combines_stats_from_each_trigger(self, service):
        with patch.object(
            service,
            "process_due_invoice_workflows",
            return_value={
                "processed_count": 2,
                "created_task_count": 1,
                "notification_count": 1,
                "skipped_count": 1,
                "errors": ["overdue err"],
            },
        ), patch.object(
            service,
            "process_invoice_created_workflows",
            return_value={
                "processed_count": 3,
                "created_task_count": 2,
                "notification_count": 2,
                "skipped_count": 0,
                "errors": [],
            },
        ), patch.object(
            service,
            "process_payment_received_workflows",
            return_value={
                "processed_count": 4,
                "created_task_count": 1,
                "notification_count": 1,
                "skipped_count": 2,
                "errors": [],
            },
        ):
            stats = service.process_all_workflows()

            assert stats["processed_count"] == 9
            assert stats["created_task_count"] == 4
            assert stats["notification_count"] == 4
            assert stats["skipped_count"] == 3
            assert stats["errors"] == ["overdue err"]

    # ---------- payment_received trigger ----------

    @pytest.fixture
    def sample_payment(self, sample_invoice):
        """Payment created recently, linked to sample_invoice."""
        return Payment(
            id=303,
            invoice_id=sample_invoice.id,
            amount=500.0,
            currency="USD",
            payment_method="ach",
            payment_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_payment_received_workflow(self):
        return WorkflowDefinition(
            id=4,
            name="On payment received",
            key="payment-received-ack",
            description="Acknowledge each payment with a thank-you and a reconcile task.",
            trigger_type="payment_received",
            conditions={},
            actions={
                "send_internal_notification": True,
                "create_internal_task": True,
                "task_type": "reminder",
                "task_title_template": "Acknowledge payment on invoice #{invoice_number}",
                "task_due_in_days": 2,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )

    def test_catalog_includes_payment_received_trigger(self, service):
        catalog = service.get_catalog()
        trigger_ids = {trigger["id"] for trigger in catalog["triggers"]}
        assert "payment_received" in trigger_ids

    def test_create_workflow_accepts_payment_received_trigger(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="Payment Ack",
                description="",
                trigger_type="payment_received",
                action_ids=["send_internal_notification"],
            )
            assert workflow.trigger_type == "payment_received"

    def test_process_payment_received_workflows_success(
        self,
        service,
        mock_db,
        sample_payment_received_workflow,
        sample_payment,
        sample_invoice,
        sample_user,
        sample_client,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_assigned_user", return_value=sample_user), \
             patch("core.services.workflow_service.send_notification") as mock_notification:

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_payment_received_workflow])))),
                Payment: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_payment])))),
                Invoice: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_invoice)))),
                Client: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))),
            }[model]

            mock_reminder = Reminder(id=1010)
            with patch.object(service, "_create_internal_task", return_value=mock_reminder) as mock_task:
                stats = service.process_payment_received_workflows()

            assert stats["processed_count"] == 1
            assert stats["created_task_count"] == 1
            assert stats["notification_count"] == 1
            assert stats["errors"] == []

            # Notification fires with payment_created event type and resource_type=payment.
            kwargs = mock_notification.call_args.kwargs
            assert kwargs["event_type"] == "payment_created"
            assert kwargs["resource_type"] == "payment"
            assert kwargs["resource_id"] == str(sample_payment.id)
            assert kwargs["details"]["payment_amount"] == sample_payment.amount

            # Task helper receives payment-aware template vars + extra_metadata.
            task_kwargs = mock_task.call_args.kwargs
            assert task_kwargs["template_vars"]["payment_amount"] == sample_payment.amount
            assert task_kwargs["extra_metadata"] == {"payment_id": sample_payment.id}

            # Execution log uses the :payment_received event-key suffix and payment entity_type.
            added = [call[0][0] for call in mock_db.add.call_args_list]
            logs = [obj for obj in added if isinstance(obj, WorkflowExecutionLog)]
            assert len(logs) == 1
            assert logs[0].status == "success"
            assert logs[0].entity_type == "payment"
            assert logs[0].event_key.endswith(":payment_received")

    def test_process_payment_received_workflows_skips_when_log_exists(
        self,
        service,
        mock_db,
        sample_payment_received_workflow,
        sample_payment,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=True):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_payment_received_workflow])))),
                Payment: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_payment])))),
            }[model]

            stats = service.process_payment_received_workflows()

            assert stats["processed_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["created_task_count"] == 0

    def test_process_payment_received_workflows_skips_payment_without_invoice(
        self,
        service,
        mock_db,
        sample_payment_received_workflow,
    ):
        """A payment with no invoice has no actionable owner; skip silently."""
        orphan_payment = Payment(
            id=404,
            invoice_id=None,
            amount=99.0,
            currency="USD",
            payment_method="cash",
            payment_date=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )

        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_payment_received_workflow])))),
                Payment: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[orphan_payment])))),
            }[model]

            stats = service.process_payment_received_workflows()

            assert stats["processed_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["created_task_count"] == 0
            assert stats["notification_count"] == 0
            assert stats["errors"] == []

    def test_process_payment_received_workflows_failure_logged(
        self,
        service,
        mock_db,
        sample_payment_received_workflow,
        sample_payment,
        sample_invoice,
        sample_client,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_assigned_user", return_value=None):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_payment_received_workflow])))),
                Payment: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_payment])))),
                Invoice: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_invoice)))),
                Client: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))),
            }[model]

            stats = service.process_payment_received_workflows()

            assert stats["processed_count"] == 1
            assert len(stats["errors"]) == 1
            added = [call[0][0] for call in mock_db.add.call_args_list]
            failed = [obj for obj in added if isinstance(obj, WorkflowExecutionLog) and obj.status == "failed"]
            assert len(failed) == 1
            assert failed[0].entity_type == "payment"
            assert failed[0].event_key.endswith(":payment_received")

    def test_run_workflow_now_dispatches_to_payment_received_processor(
        self, service, mock_db, sample_payment_received_workflow
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_payment_received_workflow
        sentinel = {"processed_count": 7, "created_task_count": 0, "notification_count": 0, "skipped_count": 0, "errors": []}

        with patch.object(service, "process_payment_received_workflows", return_value=sentinel) as mock_processor, \
             patch.object(service, "process_due_invoice_workflows") as overdue_processor, \
             patch.object(service, "process_invoice_created_workflows") as created_processor:
            result = service.run_workflow_now(sample_payment_received_workflow.id)

            mock_processor.assert_called_once()
            overdue_processor.assert_not_called()
            created_processor.assert_not_called()
            assert result is sentinel

    def test_process_all_workflows_continues_when_one_processor_raises(self, service):
        empty_stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }
        with patch.object(
            service,
            "process_due_invoice_workflows",
            side_effect=RuntimeError("db blew up"),
        ), patch.object(
            service,
            "process_invoice_created_workflows",
            return_value={
                "processed_count": 1,
                "created_task_count": 1,
                "notification_count": 1,
                "skipped_count": 0,
                "errors": [],
            },
        ), patch.object(
            service,
            "process_payment_received_workflows",
            return_value=empty_stats,
        ):
            stats = service.process_all_workflows()

            # Other processors still ran.
            assert stats["processed_count"] == 1
            # Overdue's exception is captured in errors.
            assert any("invoice_became_overdue" in err for err in stats["errors"])


if __name__ == "__main__":
    pytest.main([__file__])
