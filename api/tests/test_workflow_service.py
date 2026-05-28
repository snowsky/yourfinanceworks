import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from core.services.workflow_service import WorkflowService
from core.models.models_per_tenant import (
    WorkflowDefinition,
    WorkflowExecutionLog,
    Invoice,
    Expense,
    ExpenseApproval,
    Payment,
    Reminder,
    User,
    Client,
    ClientNote,
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
        ), patch.object(
            service,
            "process_client_created_workflows",
            return_value={
                "processed_count": 2,
                "created_task_count": 1,
                "notification_count": 1,
                "skipped_count": 0,
                "errors": [],
            },
        ), patch.object(
            service,
            "process_expense_created_workflows",
            return_value={
                "processed_count": 5,
                "created_task_count": 3,
                "notification_count": 3,
                "skipped_count": 1,
                "errors": [],
            },
        ), patch.object(
            service,
            "process_expense_submitted_for_approval_workflows",
            return_value={
                "processed_count": 3,
                "created_task_count": 2,
                "notification_count": 2,
                "skipped_count": 1,
                "errors": [],
            },
        ):
            stats = service.process_all_workflows()

            assert stats["processed_count"] == 19
            assert stats["created_task_count"] == 10
            assert stats["notification_count"] == 10
            assert stats["skipped_count"] == 5
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
        ), patch.object(
            service,
            "process_client_created_workflows",
            return_value=empty_stats,
        ), patch.object(
            service,
            "process_expense_created_workflows",
            return_value=empty_stats,
        ), patch.object(
            service,
            "process_expense_submitted_for_approval_workflows",
            return_value=empty_stats,
        ):
            stats = service.process_all_workflows()

            # Other processors still ran.
            assert stats["processed_count"] == 1
            # Overdue's exception is captured in errors.
            assert any("invoice_became_overdue" in err for err in stats["errors"])

    # ---------- client_created trigger ----------

    @pytest.fixture
    def sample_new_client(self):
        return Client(
            id=505,
            name="Brand New LLC",
            email="contact@brandnew.example",
            owner_user_id=1,
            stage="active_client",
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_client_created_workflow(self):
        return WorkflowDefinition(
            id=5,
            name="Welcome new clients",
            key="client-created-welcome",
            description="When a new client is added, notify the owner and create an onboarding task.",
            trigger_type="client_created",
            conditions={},
            actions={
                "send_internal_notification": True,
                "create_internal_task": True,
                "task_type": "reminder",
                "task_title_template": "Onboard new client {client_name}",
                "task_due_in_days": 3,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(hours=4),
        )

    def test_catalog_includes_client_created_trigger(self, service):
        catalog = service.get_catalog()
        trigger_ids = {trigger["id"] for trigger in catalog["triggers"]}
        assert "client_created" in trigger_ids

    def test_create_workflow_accepts_client_created_trigger(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="Welcome Clients",
                description="",
                trigger_type="client_created",
                action_ids=["send_internal_notification"],
            )
            assert workflow.trigger_type == "client_created"

    def test_process_client_created_workflows_success(
        self,
        service,
        mock_db,
        sample_client_created_workflow,
        sample_new_client,
        sample_user,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_user_for_client", return_value=sample_user), \
             patch("core.services.workflow_service.send_notification") as mock_notification:

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_client_created_workflow])))),
                Client: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_new_client])))),
            }[model]

            mock_reminder = Reminder(id=2020)
            with patch.object(service, "_create_internal_task", return_value=mock_reminder) as mock_task:
                stats = service.process_client_created_workflows()

            assert stats["processed_count"] == 1
            assert stats["created_task_count"] == 1
            assert stats["notification_count"] == 1
            assert stats["errors"] == []

            # Notification uses the client_created event type, resource_type=client.
            kwargs = mock_notification.call_args.kwargs
            assert kwargs["event_type"] == "client_created"
            assert kwargs["resource_type"] == "client"
            assert kwargs["resource_id"] == str(sample_new_client.id)

            # _create_internal_task receives invoice=None and the client metadata.
            task_kwargs = mock_task.call_args.kwargs
            assert task_kwargs["invoice"] is None
            assert task_kwargs["extra_metadata"] == {"client_id": sample_new_client.id}

            # Execution log uses client entity_type + :client_created suffix.
            added = [call[0][0] for call in mock_db.add.call_args_list]
            logs = [obj for obj in added if isinstance(obj, WorkflowExecutionLog)]
            assert len(logs) == 1
            assert logs[0].status == "success"
            assert logs[0].entity_type == "client"
            assert logs[0].event_key.endswith(":client_created")

    def test_process_client_created_workflows_skips_when_log_exists(
        self,
        service,
        mock_db,
        sample_client_created_workflow,
        sample_new_client,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=True):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_client_created_workflow])))),
                Client: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_new_client])))),
            }[model]

            stats = service.process_client_created_workflows()

            assert stats["processed_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["created_task_count"] == 0

    def test_process_client_created_workflows_failure_logged(
        self,
        service,
        mock_db,
        sample_client_created_workflow,
        sample_new_client,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_user_for_client", return_value=None):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_client_created_workflow])))),
                Client: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_new_client])))),
            }[model]

            stats = service.process_client_created_workflows()

            assert stats["processed_count"] == 1
            assert len(stats["errors"]) == 1
            added = [call[0][0] for call in mock_db.add.call_args_list]
            failed = [obj for obj in added if isinstance(obj, WorkflowExecutionLog) and obj.status == "failed"]
            assert len(failed) == 1
            assert failed[0].entity_type == "client"
            assert failed[0].event_key.endswith(":client_created")

    def test_run_workflow_now_dispatches_to_client_created_processor(
        self, service, mock_db, sample_client_created_workflow
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_client_created_workflow
        sentinel = {"processed_count": 3, "created_task_count": 0, "notification_count": 0, "skipped_count": 0, "errors": []}

        with patch.object(service, "process_client_created_workflows", return_value=sentinel) as mock_processor, \
             patch.object(service, "process_due_invoice_workflows") as overdue_processor, \
             patch.object(service, "process_invoice_created_workflows") as created_processor, \
             patch.object(service, "process_payment_received_workflows") as payment_processor:
            result = service.run_workflow_now(sample_client_created_workflow.id)

            mock_processor.assert_called_once()
            overdue_processor.assert_not_called()
            created_processor.assert_not_called()
            payment_processor.assert_not_called()
            assert result is sentinel

    def test_resolve_user_for_client_uses_owner_id(self, service, mock_db, sample_user):
        client = Client(id=99, name="X", owner_user_id=7)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user

        result = service._resolve_user_for_client(client)
        assert result is sample_user

    def test_resolve_user_for_client_falls_back_to_admin(self, service, mock_db, sample_user):
        client = Client(id=99, name="X", owner_user_id=None)
        # First branch returns None (no owner). Fallback queries admin.
        with patch.object(service, "_fallback_admin_user", return_value=sample_user) as fallback:
            result = service._resolve_user_for_client(client)
            fallback.assert_called_once()
            assert result is sample_user

    # ---------- expense_created trigger ----------

    @pytest.fixture
    def sample_new_expense(self):
        return Expense(
            id=606,
            amount=125.50,
            currency="USD",
            expense_date=datetime.now(timezone.utc),
            category="travel",
            vendor="Acme Taxi",
            status="recorded",
            created_by_user_id=1,
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_expense_created_workflow(self):
        return WorkflowDefinition(
            id=6,
            name="On expense recorded",
            key="expense-created-review",
            description="Notify the bookkeeper when a new expense is recorded; create a review task.",
            trigger_type="expense_created",
            conditions={},
            actions={
                "send_internal_notification": True,
                "create_internal_task": True,
                "task_type": "reminder",
                "task_title_template": "Review newly recorded expense from {vendor}",
                "task_due_in_days": 2,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(hours=6),
        )

    def test_catalog_includes_expense_created_trigger(self, service):
        catalog = service.get_catalog()
        trigger_ids = {trigger["id"] for trigger in catalog["triggers"]}
        assert "expense_created" in trigger_ids

    def test_create_workflow_accepts_expense_created_trigger(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="Expense Review",
                description="",
                trigger_type="expense_created",
                action_ids=["send_internal_notification"],
            )
            assert workflow.trigger_type == "expense_created"

    def test_process_expense_created_workflows_success(
        self,
        service,
        mock_db,
        sample_expense_created_workflow,
        sample_new_expense,
        sample_user,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_user_for_expense", return_value=sample_user), \
             patch("core.services.workflow_service.send_notification") as mock_notification:

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_created_workflow])))),
                Expense: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_new_expense])))),
            }[model]

            mock_reminder = Reminder(id=3030)
            with patch.object(service, "_create_internal_task", return_value=mock_reminder) as mock_task:
                stats = service.process_expense_created_workflows()

            assert stats["processed_count"] == 1
            assert stats["created_task_count"] == 1
            assert stats["notification_count"] == 1
            assert stats["errors"] == []

            kwargs = mock_notification.call_args.kwargs
            assert kwargs["event_type"] == "expense_created"
            assert kwargs["resource_type"] == "expense"
            assert kwargs["resource_id"] == str(sample_new_expense.id)
            assert kwargs["resource_name"] == sample_new_expense.vendor

            # _create_internal_task gets invoice=None and expense template vars + extra_metadata.
            task_kwargs = mock_task.call_args.kwargs
            assert task_kwargs["invoice"] is None
            assert task_kwargs["template_vars"]["vendor"] == sample_new_expense.vendor
            assert task_kwargs["template_vars"]["category"] == sample_new_expense.category
            assert task_kwargs["template_vars"]["amount"] == sample_new_expense.amount
            assert task_kwargs["extra_metadata"] == {"expense_id": sample_new_expense.id}

            # Execution log uses expense entity_type + :expense_created suffix.
            added = [call[0][0] for call in mock_db.add.call_args_list]
            logs = [obj for obj in added if isinstance(obj, WorkflowExecutionLog)]
            assert len(logs) == 1
            assert logs[0].status == "success"
            assert logs[0].entity_type == "expense"
            assert logs[0].event_key.endswith(":expense_created")

    def test_process_expense_created_workflows_skips_when_log_exists(
        self,
        service,
        mock_db,
        sample_expense_created_workflow,
        sample_new_expense,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=True):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_created_workflow])))),
                Expense: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_new_expense])))),
            }[model]

            stats = service.process_expense_created_workflows()

            assert stats["processed_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["created_task_count"] == 0

    def test_process_expense_created_workflows_failure_logged(
        self,
        service,
        mock_db,
        sample_expense_created_workflow,
        sample_new_expense,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_user_for_expense", return_value=None):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_created_workflow])))),
                Expense: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_new_expense])))),
            }[model]

            stats = service.process_expense_created_workflows()

            assert stats["processed_count"] == 1
            assert len(stats["errors"]) == 1
            added = [call[0][0] for call in mock_db.add.call_args_list]
            failed = [obj for obj in added if isinstance(obj, WorkflowExecutionLog) and obj.status == "failed"]
            assert len(failed) == 1
            assert failed[0].entity_type == "expense"
            assert failed[0].event_key.endswith(":expense_created")

    def test_run_workflow_now_dispatches_to_expense_created_processor(
        self, service, mock_db, sample_expense_created_workflow
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense_created_workflow
        sentinel = {"processed_count": 4, "created_task_count": 0, "notification_count": 0, "skipped_count": 0, "errors": []}

        with patch.object(service, "process_expense_created_workflows", return_value=sentinel) as mock_processor, \
             patch.object(service, "process_due_invoice_workflows") as overdue_processor, \
             patch.object(service, "process_invoice_created_workflows") as created_processor, \
             patch.object(service, "process_payment_received_workflows") as payment_processor, \
             patch.object(service, "process_client_created_workflows") as client_processor:
            result = service.run_workflow_now(sample_expense_created_workflow.id)

            mock_processor.assert_called_once()
            overdue_processor.assert_not_called()
            created_processor.assert_not_called()
            payment_processor.assert_not_called()
            client_processor.assert_not_called()
            assert result is sentinel

    def test_resolve_user_for_expense_uses_created_by_id(self, service, mock_db, sample_user):
        expense = Expense(id=99, vendor="X", category="food", created_by_user_id=7)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user
        result = service._resolve_user_for_expense(expense)
        assert result is sample_user

    def test_resolve_user_for_expense_falls_back_to_admin(self, service, mock_db, sample_user):
        expense = Expense(id=99, vendor="X", category="food", created_by_user_id=None)
        with patch.object(service, "_fallback_admin_user", return_value=sample_user) as fallback:
            result = service._resolve_user_for_expense(expense)
            fallback.assert_called_once()
            assert result is sample_user

    # ---------- expense_submitted_for_approval trigger ----------

    @pytest.fixture
    def sample_expense_approval(self, sample_new_expense):
        return ExpenseApproval(
            id=707,
            expense_id=sample_new_expense.id,
            approver_id=1,
            status="pending",
            submitted_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=True,
        )

    @pytest.fixture
    def sample_expense_submitted_workflow(self):
        return WorkflowDefinition(
            id=7,
            name="On expense submitted for approval",
            key="expense-submitted-approval-task",
            description="Notify the approver and create an approval task when an expense is submitted.",
            trigger_type="expense_submitted_for_approval",
            conditions={},
            actions={
                "send_internal_notification": True,
                "create_internal_task": True,
                "task_type": "reminder",
                "task_title_template": "Approve expense from {vendor}",
                "task_due_in_days": 1,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(hours=8),
        )

    def test_catalog_includes_expense_submitted_trigger(self, service):
        catalog = service.get_catalog()
        trigger_ids = {trigger["id"] for trigger in catalog["triggers"]}
        assert "expense_submitted_for_approval" in trigger_ids

    def test_create_workflow_accepts_expense_submitted_trigger(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="Approver Notify",
                description="",
                trigger_type="expense_submitted_for_approval",
                action_ids=["send_internal_notification"],
            )
            assert workflow.trigger_type == "expense_submitted_for_approval"

    def test_process_expense_submitted_for_approval_workflows_success(
        self,
        service,
        mock_db,
        sample_expense_submitted_workflow,
        sample_expense_approval,
        sample_new_expense,
        sample_user,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_user_for_expense_approval", return_value=sample_user), \
             patch("core.services.workflow_service.send_notification") as mock_notification:

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_submitted_workflow])))),
                ExpenseApproval: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_approval])))),
                Expense: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_new_expense)))),
            }[model]

            mock_reminder = Reminder(id=4040)
            with patch.object(service, "_create_internal_task", return_value=mock_reminder) as mock_task:
                stats = service.process_expense_submitted_for_approval_workflows()

            assert stats["processed_count"] == 1
            assert stats["created_task_count"] == 1
            assert stats["notification_count"] == 1
            assert stats["errors"] == []

            kwargs = mock_notification.call_args.kwargs
            assert kwargs["event_type"] == "expense_submitted_for_approval"
            assert kwargs["resource_type"] == "expense"
            assert kwargs["resource_id"] == str(sample_new_expense.id)
            assert kwargs["details"]["expense_approval_id"] == sample_expense_approval.id
            assert kwargs["details"]["approval_level"] == sample_expense_approval.approval_level

            # Task helper receives invoice=None and approval metadata threaded through.
            task_kwargs = mock_task.call_args.kwargs
            assert task_kwargs["invoice"] is None
            assert task_kwargs["template_vars"]["vendor"] == sample_new_expense.vendor
            assert task_kwargs["template_vars"]["approval_level"] == sample_expense_approval.approval_level
            assert task_kwargs["extra_metadata"] == {
                "expense_id": sample_new_expense.id,
                "expense_approval_id": sample_expense_approval.id,
                "approval_level": sample_expense_approval.approval_level,
            }

            # Execution log uses expense_approval entity_type + :submitted_for_approval suffix.
            added = [call[0][0] for call in mock_db.add.call_args_list]
            logs = [obj for obj in added if isinstance(obj, WorkflowExecutionLog)]
            assert len(logs) == 1
            assert logs[0].status == "success"
            assert logs[0].entity_type == "expense_approval"
            assert logs[0].entity_id == str(sample_expense_approval.id)
            assert logs[0].event_key.endswith(":submitted_for_approval")

    def test_process_expense_submitted_workflows_skips_when_log_exists(
        self,
        service,
        mock_db,
        sample_expense_submitted_workflow,
        sample_expense_approval,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=True):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_submitted_workflow])))),
                ExpenseApproval: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_approval])))),
            }[model]

            stats = service.process_expense_submitted_for_approval_workflows()

            assert stats["processed_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["created_task_count"] == 0

    def test_process_expense_submitted_workflows_skips_when_underlying_expense_missing(
        self,
        service,
        mock_db,
        sample_expense_submitted_workflow,
        sample_expense_approval,
    ):
        """An approval whose Expense has been deleted has no actionable owner — silent skip."""
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_submitted_workflow])))),
                ExpenseApproval: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_approval])))),
                Expense: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=None)))),
            }[model]

            stats = service.process_expense_submitted_for_approval_workflows()

            assert stats["processed_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["created_task_count"] == 0
            assert stats["notification_count"] == 0
            assert stats["errors"] == []

    def test_process_expense_submitted_workflows_skips_when_expense_is_deleted(
        self,
        service,
        mock_db,
        sample_expense_submitted_workflow,
        sample_expense_approval,
    ):
        """If the expense is soft-deleted between submission and tick, skip silently."""
        deleted_expense = Expense(
            id=sample_expense_approval.expense_id,
            vendor="Was Acme",
            category="travel",
            currency="USD",
            amount=10,
            is_deleted=True,
            created_at=datetime.now(timezone.utc),
        )
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_submitted_workflow])))),
                ExpenseApproval: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_approval])))),
                Expense: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=deleted_expense)))),
            }[model]

            stats = service.process_expense_submitted_for_approval_workflows()

            assert stats["processed_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["created_task_count"] == 0

    def test_process_expense_submitted_workflows_failure_logged(
        self,
        service,
        mock_db,
        sample_expense_submitted_workflow,
        sample_expense_approval,
        sample_new_expense,
    ):
        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_user_for_expense_approval", return_value=None):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_submitted_workflow])))),
                ExpenseApproval: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_approval])))),
                Expense: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_new_expense)))),
            }[model]

            stats = service.process_expense_submitted_for_approval_workflows()

            assert stats["processed_count"] == 1
            assert len(stats["errors"]) == 1
            added = [call[0][0] for call in mock_db.add.call_args_list]
            failed = [obj for obj in added if isinstance(obj, WorkflowExecutionLog) and obj.status == "failed"]
            assert len(failed) == 1
            assert failed[0].entity_type == "expense_approval"
            assert failed[0].event_key.endswith(":submitted_for_approval")

    def test_run_workflow_now_dispatches_to_expense_submitted_processor(
        self, service, mock_db, sample_expense_submitted_workflow
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_expense_submitted_workflow
        sentinel = {"processed_count": 5, "created_task_count": 0, "notification_count": 0, "skipped_count": 0, "errors": []}

        with patch.object(service, "process_expense_submitted_for_approval_workflows", return_value=sentinel) as mock_processor, \
             patch.object(service, "process_due_invoice_workflows") as overdue_processor, \
             patch.object(service, "process_invoice_created_workflows") as created_processor, \
             patch.object(service, "process_payment_received_workflows") as payment_processor, \
             patch.object(service, "process_client_created_workflows") as client_processor, \
             patch.object(service, "process_expense_created_workflows") as expense_created_processor:
            result = service.run_workflow_now(sample_expense_submitted_workflow.id)

            mock_processor.assert_called_once()
            overdue_processor.assert_not_called()
            created_processor.assert_not_called()
            payment_processor.assert_not_called()
            client_processor.assert_not_called()
            expense_created_processor.assert_not_called()
            assert result is sentinel

    def test_resolve_user_for_expense_approval_uses_approver_id(self, service, mock_db, sample_user):
        approval = ExpenseApproval(
            id=99,
            expense_id=1,
            approver_id=7,
            status="pending",
            submitted_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=True,
        )
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user
        result = service._resolve_user_for_expense_approval(approval)
        assert result is sample_user

    def test_resolve_user_for_expense_approval_falls_back_to_admin(self, service, mock_db, sample_user):
        approval = ExpenseApproval(
            id=99,
            expense_id=1,
            approver_id=None,
            status="pending",
            submitted_at=datetime.now(timezone.utc),
            approval_level=1,
            is_current_level=True,
        )
        with patch.object(service, "_fallback_admin_user", return_value=sample_user) as fallback:
            result = service._resolve_user_for_expense_approval(approval)
            fallback.assert_called_once()
            assert result is sample_user

    # ---------- add_client_note action ----------

    def test_catalog_includes_add_client_note_action(self, service):
        catalog = service.get_catalog()
        action_ids = {action["id"] for action in catalog["actions"]}
        assert "add_client_note" in action_ids

    def test_create_workflow_persists_add_client_note_flag(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="With Note",
                description="",
                trigger_type="invoice_became_overdue",
                action_ids=["send_internal_notification", "add_client_note"],
            )
            assert workflow.actions["add_client_note"] is True
            # Unselected actions stay False so older readers see a stable dict shape.
            assert workflow.actions["create_internal_task"] is False

    def test_add_client_note_helper_inserts_attributed_row(self, service, mock_db, sample_client, sample_user):
        workflow = WorkflowDefinition(id=10, key="demo-key")
        note = service._add_client_note(
            client=sample_client,
            workflow=workflow,
            assigned_user=sample_user,
            note_template="[Workflow {workflow_key}] Invoice #{invoice_number} is now overdue.",
            note_vars={"invoice_number": "INV-2026-001"},
        )

        assert isinstance(note, ClientNote)
        assert note.client_id == sample_client.id
        assert note.user_id == sample_user.id
        assert note.note == "[Workflow demo-key] Invoice #INV-2026-001 is now overdue."
        mock_db.add.assert_called()
        mock_db.flush.assert_called()

    def test_add_client_note_helper_no_op_without_client(self, service, mock_db, sample_user):
        workflow = WorkflowDefinition(id=10, key="demo-key")
        result = service._add_client_note(
            client=None,
            workflow=workflow,
            assigned_user=sample_user,
            note_template="anything {workflow_key}",
            note_vars={},
        )
        assert result is None
        # Nothing was inserted.
        added = [call[0][0] for call in mock_db.add.call_args_list]
        assert not any(isinstance(obj, ClientNote) for obj in added)

    def test_process_due_invoice_workflows_adds_client_note_when_enabled(
        self,
        service,
        mock_db,
        sample_invoice,
        sample_user,
        sample_client,
    ):
        workflow = WorkflowDefinition(
            id=99,
            key="overdue-with-note",
            trigger_type="invoice_became_overdue",
            conditions={"invoice_statuses": ["sent"]},
            actions={
                "send_internal_notification": False,
                "create_internal_task": False,
                "add_client_note": True,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "ensure_default_workflows"), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_assigned_user", return_value=sample_user):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[workflow])))),
                Invoice: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice])))),
                Client: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))),
            }[model]

            stats = service.process_due_invoice_workflows()

            assert stats["client_note_count"] == 1
            assert stats["created_task_count"] == 0
            assert stats["notification_count"] == 0

            added = [call[0][0] for call in mock_db.add.call_args_list]
            notes = [obj for obj in added if isinstance(obj, ClientNote)]
            assert len(notes) == 1
            assert notes[0].client_id == sample_client.id
            assert notes[0].user_id == sample_user.id
            assert "Invoice #INV-2026-001 is now overdue" in notes[0].note

            logs = [obj for obj in added if isinstance(obj, WorkflowExecutionLog)]
            assert logs[0].details["client_note_id"] == notes[0].id

    def test_process_expense_created_workflows_skips_note_when_no_client(
        self,
        service,
        mock_db,
        sample_user,
        sample_expense_created_workflow,
    ):
        """Expenses without a client link should silently skip the note (and not bump count)."""
        # Override the action set to include add_client_note.
        sample_expense_created_workflow.actions = {
            **sample_expense_created_workflow.actions,
            "add_client_note": True,
        }
        expense_no_client = Expense(
            id=910,
            amount=25.0,
            currency="USD",
            expense_date=datetime.now(timezone.utc),
            category="meals",
            vendor="Cafe",
            status="recorded",
            created_by_user_id=1,
            client_id=None,
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
        )

        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_user_for_expense", return_value=sample_user):

            mock_db.query.side_effect = lambda model: {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_expense_created_workflow])))),
                Expense: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[expense_no_client])))),
            }[model]

            mock_reminder = Reminder(id=5050)
            with patch.object(service, "_create_internal_task", return_value=mock_reminder):
                stats = service.process_expense_created_workflows()

            assert stats["client_note_count"] == 0
            added = [call[0][0] for call in mock_db.add.call_args_list]
            assert not any(isinstance(obj, ClientNote) for obj in added)

    def test_process_all_workflows_aggregates_client_note_count(self, service):
        empty_stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "client_note_count": 0,
            "skipped_count": 0,
            "errors": [],
        }
        with patch.object(service, "process_due_invoice_workflows", return_value={**empty_stats, "client_note_count": 2}), \
             patch.object(service, "process_invoice_created_workflows", return_value=empty_stats), \
             patch.object(service, "process_payment_received_workflows", return_value={**empty_stats, "client_note_count": 1}), \
             patch.object(service, "process_client_created_workflows", return_value=empty_stats), \
             patch.object(service, "process_expense_created_workflows", return_value=empty_stats), \
             patch.object(service, "process_expense_submitted_for_approval_workflows", return_value=empty_stats):
            stats = service.process_all_workflows()
            assert stats["client_note_count"] == 3

    # ---------- assign_to_specific_user action ----------

    def test_catalog_includes_assign_to_specific_user_action(self, service):
        catalog = service.get_catalog()
        action_ids = {action["id"] for action in catalog["actions"]}
        assert "assign_to_specific_user" in action_ids

    def test_create_workflow_persists_assigned_user_id(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="Pinned Owner",
                description="",
                trigger_type="invoice_became_overdue",
                action_ids=["send_internal_notification", "assign_to_specific_user"],
                assigned_user_id=42,
            )
            assert workflow.actions["assign_to_specific_user"] is True
            assert workflow.actions["assigned_user_id"] == 42

    def test_create_workflow_rejects_assign_action_without_user_id(self, service):
        with patch.object(service, "ensure_default_workflows"):
            with pytest.raises(ValueError, match="assign_to_specific_user requires assigned_user_id"):
                service.create_workflow(
                    name="Missing User",
                    description="",
                    trigger_type="invoice_became_overdue",
                    action_ids=["send_internal_notification", "assign_to_specific_user"],
                )

    def test_update_workflow_rejects_assign_action_without_user_id(
        self, service, mock_db, sample_custom_workflow
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_custom_workflow
        with pytest.raises(ValueError, match="assign_to_specific_user requires assigned_user_id"):
            service.update_workflow(
                workflow_id=sample_custom_workflow.id,
                name="No Override Provided",
                description="",
                action_ids=["send_internal_notification", "assign_to_specific_user"],
            )

    def test_update_workflow_clears_assigned_user_id_when_action_removed(
        self, service, mock_db, sample_custom_workflow
    ):
        sample_custom_workflow.actions = {"assigned_user_id": 99, "assign_to_specific_user": True}
        mock_db.query.return_value.filter.return_value.first.return_value = sample_custom_workflow

        updated = service.update_workflow(
            workflow_id=sample_custom_workflow.id,
            name="Cleared Override",
            description="",
            action_ids=["send_internal_notification"],
            assigned_user_id=None,
        )
        assert updated.actions["assign_to_specific_user"] is False
        assert updated.actions["assigned_user_id"] is None

    def test_apply_assignment_override_returns_default_when_action_disabled(
        self, service, sample_user
    ):
        workflow = WorkflowDefinition(actions={"send_internal_notification": True})
        result = service._apply_assignment_override(workflow, sample_user)
        assert result is sample_user

    def test_apply_assignment_override_returns_default_when_user_id_missing(
        self, service, sample_user
    ):
        workflow = WorkflowDefinition(
            actions={"assign_to_specific_user": True, "assigned_user_id": None}
        )
        result = service._apply_assignment_override(workflow, sample_user)
        assert result is sample_user

    def test_apply_assignment_override_uses_target_user(self, service, mock_db, sample_user):
        target = User(id=42, email="target@example.com", is_active=True, role="admin")
        workflow = WorkflowDefinition(
            actions={"assign_to_specific_user": True, "assigned_user_id": 42}
        )
        mock_db.query.return_value.filter.return_value.first.return_value = target

        result = service._apply_assignment_override(workflow, sample_user)
        assert result is target

    def test_apply_assignment_override_falls_back_when_target_inactive(
        self, service, mock_db, sample_user, caplog
    ):
        """An override user who's been deactivated should silently fall back."""
        workflow = WorkflowDefinition(
            key="demo-workflow",
            actions={"assign_to_specific_user": True, "assigned_user_id": 999},
        )
        # The query that filters by is_active=True returns None.
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with caplog.at_level("WARNING"):
            result = service._apply_assignment_override(workflow, sample_user)

        assert result is sample_user
        assert any("missing or inactive" in record.message for record in caplog.records)

    def test_process_due_invoice_workflows_uses_override_user(
        self, service, mock_db, sample_invoice, sample_user, sample_client
    ):
        """End-to-end: the override user is the one wired into notifications + tasks."""
        target = User(id=42, email="target@example.com", is_active=True, role="admin")
        workflow = WorkflowDefinition(
            id=99,
            key="overdue-pinned",
            trigger_type="invoice_became_overdue",
            conditions={"invoice_statuses": ["sent"]},
            actions={
                "send_internal_notification": True,
                "create_internal_task": False,
                "assign_to_specific_user": True,
                "assigned_user_id": 42,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        # Query side_effect: WorkflowDefinition/Invoice/Client are the model-keyed
        # lookups; the override-user query keys off User and needs the explicit
        # target row.
        def query_side_effect(model):
            return {
                WorkflowDefinition: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[workflow])))),
                Invoice: Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice])))),
                Client: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))),
                User: Mock(filter=Mock(return_value=Mock(first=Mock(return_value=target)))),
            }[model]

        with patch("core.services.workflow_service.FeatureConfigService.is_enabled", return_value=True), \
             patch.object(service, "ensure_default_workflows"), \
             patch.object(service, "_has_execution_log", return_value=False), \
             patch.object(service, "_resolve_assigned_user", return_value=sample_user), \
             patch("core.services.workflow_service.send_notification") as mock_notification:
            mock_db.query.side_effect = query_side_effect

            stats = service.process_due_invoice_workflows()

            assert stats["notification_count"] == 1
            # Notification fires for the override user, not the default-resolved one.
            assert mock_notification.call_args.kwargs["user_id"] == target.id

    # ---------- send_client_email action ----------

    def test_catalog_includes_send_client_email_action(self, service):
        catalog = service.get_catalog()
        action_ids = {action["id"] for action in catalog["actions"]}
        assert "send_client_email" in action_ids

    def test_create_workflow_persists_send_client_email_flag(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="With Client Email",
                description="",
                trigger_type="invoice_became_overdue",
                action_ids=["send_internal_notification", "send_client_email"],
            )
            assert workflow.actions["send_client_email"] is True
            assert workflow.actions["add_client_note"] is False

    def test_send_client_email_helper_no_op_without_client(
        self, service, mock_db, sample_user
    ):
        workflow = WorkflowDefinition(id=10, key="demo-key")
        result = service._send_client_email(
            client=None,
            workflow=workflow,
            subject_template="anything",
            body_template="anything",
            template_vars={},
        )
        assert result is False
        mock_db.query.assert_not_called()

    def test_send_client_email_helper_no_op_without_email_address(
        self, service, mock_db, sample_client, caplog
    ):
        workflow = WorkflowDefinition(id=10, key="demo-key")
        sample_client.email = None

        with caplog.at_level("WARNING"):
            result = service._send_client_email(
                client=sample_client,
                workflow=workflow,
                subject_template="anything",
                body_template="anything",
                template_vars={},
            )

        assert result is False
        mock_db.query.assert_not_called()
        assert any("has no email" in r.message for r in caplog.records)

    def test_send_client_email_helper_no_op_without_provider_config(
        self, service, mock_db, sample_client, caplog
    ):
        workflow = WorkflowDefinition(id=10, key="demo-key")
        sample_client.email = "client@example.com"
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with caplog.at_level("WARNING"):
            result = service._send_client_email(
                client=sample_client,
                workflow=workflow,
                subject_template="anything",
                body_template="anything",
                template_vars={},
            )

        assert result is False
        assert any(
            "email_provider_config not set" in r.message for r in caplog.records
        )

    def test_send_client_email_helper_happy_path(
        self, service, mock_db, sample_client
    ):
        from core.models.models_per_tenant import Settings

        workflow = WorkflowDefinition(id=10, key="demo-key")
        sample_client.email = "client@example.com"

        settings_row = Settings(
            key="email_provider_config",
            value={
                "provider": "aws_ses",
                "from_email": "noreply@yfw.test",
                "from_name": "YFW",
                "aws_access_key_id": "AKIA",
                "aws_secret_access_key": "secret",
                "aws_region": "us-east-1",
            },
        )
        mock_db.query.return_value.filter.return_value.first.return_value = settings_row

        with patch("core.services.email_service.EmailService") as mock_email_service_cls:
            mock_provider = Mock()
            mock_provider.send_email.return_value = True
            mock_email_service_cls.return_value = mock_provider

            result = service._send_client_email(
                client=sample_client,
                workflow=workflow,
                subject_template="Hi {client_name} (workflow {workflow_key})",
                body_template="Invoice #{invoice_number}",
                template_vars={"invoice_number": "INV-2026-001"},
            )

        assert result is True
        mock_email_service_cls.assert_called_once()
        sent_message = mock_provider.send_email.call_args.args[0]
        assert sent_message.to_email == "client@example.com"
        assert "ACME Corp" in sent_message.subject
        assert "demo-key" in sent_message.subject
        assert "INV-2026-001" in sent_message.html_body

    def test_process_due_invoice_workflows_sends_client_email_when_enabled(
        self,
        service,
        mock_db,
        sample_invoice,
        sample_user,
        sample_client,
    ):
        from core.models.models_per_tenant import Settings

        sample_client.email = "client@example.com"
        workflow = WorkflowDefinition(
            id=99,
            key="overdue-with-email",
            trigger_type="invoice_became_overdue",
            conditions={"invoice_statuses": ["sent"]},
            actions={
                "send_internal_notification": False,
                "create_internal_task": False,
                "send_client_email": True,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        settings_row = Settings(
            key="email_provider_config",
            value={
                "provider": "mailgun",
                "from_email": "noreply@yfw.test",
                "from_name": "YFW",
                "mailgun_api_key": "key-x",
                "mailgun_domain": "yfw.test",
            },
        )

        def query_side_effect(model):
            return {
                WorkflowDefinition: Mock(
                    filter=Mock(return_value=Mock(all=Mock(return_value=[workflow])))
                ),
                Invoice: Mock(
                    filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice])))
                ),
                Client: Mock(
                    filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))
                ),
                Settings: Mock(
                    filter=Mock(return_value=Mock(first=Mock(return_value=settings_row)))
                ),
            }[model]

        with patch(
            "core.services.workflow_service.FeatureConfigService.is_enabled",
            return_value=True,
        ), patch.object(service, "ensure_default_workflows"), patch.object(
            service, "_has_execution_log", return_value=False
        ), patch.object(
            service, "_resolve_assigned_user", return_value=sample_user
        ), patch(
            "core.services.email_service.EmailService"
        ) as mock_email_service_cls:
            mock_provider = Mock()
            mock_provider.send_email.return_value = True
            mock_email_service_cls.return_value = mock_provider
            mock_db.query.side_effect = query_side_effect

            stats = service.process_due_invoice_workflows()

        assert stats["client_email_count"] == 1
        assert stats["notification_count"] == 0
        assert stats["created_task_count"] == 0

        sent_message = mock_provider.send_email.call_args.args[0]
        assert sent_message.to_email == "client@example.com"
        assert "INV-2026-001" in sent_message.subject

        added = [call[0][0] for call in mock_db.add.call_args_list]
        logs = [obj for obj in added if isinstance(obj, WorkflowExecutionLog)]
        assert logs[0].details["client_email_sent"] is True

    def test_process_all_workflows_aggregates_client_email_count(self, service):
        empty_stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "client_note_count": 0,
            "client_email_count": 0,
            "skipped_count": 0,
            "errors": [],
        }
        with patch.object(
            service,
            "process_due_invoice_workflows",
            return_value={**empty_stats, "client_email_count": 2},
        ), patch.object(
            service, "process_invoice_created_workflows", return_value=empty_stats
        ), patch.object(
            service,
            "process_payment_received_workflows",
            return_value={**empty_stats, "client_email_count": 1},
        ), patch.object(
            service, "process_client_created_workflows", return_value=empty_stats
        ), patch.object(
            service, "process_expense_created_workflows", return_value=empty_stats
        ), patch.object(
            service,
            "process_expense_submitted_for_approval_workflows",
            return_value=empty_stats,
        ):
            stats = service.process_all_workflows()
            assert stats["client_email_count"] == 3

    # ---------- send_slack_notification action ----------

    def test_catalog_includes_send_slack_notification_action(self, service):
        catalog = service.get_catalog()
        action_ids = {action["id"] for action in catalog["actions"]}
        assert "send_slack_notification" in action_ids

    def test_create_workflow_persists_send_slack_notification_flag(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, "ensure_default_workflows"):
            workflow = service.create_workflow(
                name="With Slack",
                description="",
                trigger_type="invoice_became_overdue",
                action_ids=["send_internal_notification", "send_slack_notification"],
            )
            assert workflow.actions["send_slack_notification"] is True
            assert workflow.actions["send_client_email"] is False

    def test_send_slack_notification_helper_no_op_without_config(
        self, service, mock_db, caplog
    ):
        workflow = WorkflowDefinition(id=10, key="demo-key")
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with caplog.at_level("WARNING"):
            result = service._send_slack_notification(
                workflow=workflow,
                message_template="hello {workflow_key}",
                template_vars={},
            )

        assert result is False
        assert any(
            "slack_webhook_config not set" in r.message for r in caplog.records
        )

    def test_send_slack_notification_helper_no_op_without_url(
        self, service, mock_db, caplog
    ):
        from core.models.models_per_tenant import Settings

        workflow = WorkflowDefinition(id=10, key="demo-key")
        settings_row = Settings(key="slack_webhook_config", value={})
        mock_db.query.return_value.filter.return_value.first.return_value = settings_row

        with caplog.at_level("WARNING"):
            result = service._send_slack_notification(
                workflow=workflow,
                message_template="hello {workflow_key}",
                template_vars={},
            )

        assert result is False
        assert any("webhook_url missing" in r.message for r in caplog.records)

    def test_send_slack_notification_helper_happy_path(self, service, mock_db):
        from core.models.models_per_tenant import Settings

        workflow = WorkflowDefinition(id=10, key="demo-key")
        settings_row = Settings(
            key="slack_webhook_config",
            value={"webhook_url": "https://hooks.slack.com/services/T/B/X"},
        )
        mock_db.query.return_value.filter.return_value.first.return_value = settings_row

        mock_response = Mock()
        mock_response.status_code = 200

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = service._send_slack_notification(
                workflow=workflow,
                message_template="hello {workflow_key} for invoice #{invoice_number}",
                template_vars={"invoice_number": "INV-2026-001"},
            )

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["text"] == "hello demo-key for invoice #INV-2026-001"
        assert call_kwargs["timeout"] == 10
        assert mock_post.call_args.args[0] == "https://hooks.slack.com/services/T/B/X"

    def test_send_slack_notification_helper_non_2xx_is_failure(
        self, service, mock_db, caplog
    ):
        from core.models.models_per_tenant import Settings

        workflow = WorkflowDefinition(id=10, key="demo-key")
        settings_row = Settings(
            key="slack_webhook_config",
            value={"webhook_url": "https://hooks.slack.com/services/T/B/X"},
        )
        mock_db.query.return_value.filter.return_value.first.return_value = settings_row

        mock_response = Mock()
        mock_response.status_code = 503

        with patch("requests.post", return_value=mock_response):
            with caplog.at_level("WARNING"):
                result = service._send_slack_notification(
                    workflow=workflow,
                    message_template="anything",
                    template_vars={},
                )

        assert result is False
        assert any("non-2xx response 503" in r.message for r in caplog.records)

    def test_send_slack_notification_helper_network_error_is_failure(
        self, service, mock_db, caplog
    ):
        from core.models.models_per_tenant import Settings

        workflow = WorkflowDefinition(id=10, key="demo-key")
        settings_row = Settings(
            key="slack_webhook_config",
            value={"webhook_url": "https://hooks.slack.com/services/T/B/X"},
        )
        mock_db.query.return_value.filter.return_value.first.return_value = settings_row

        with patch(
            "requests.post", side_effect=ConnectionError("dns lookup failed")
        ):
            with caplog.at_level("WARNING"):
                result = service._send_slack_notification(
                    workflow=workflow,
                    message_template="anything",
                    template_vars={},
                )

        assert result is False
        assert any("network error" in r.message for r in caplog.records)

    def test_process_due_invoice_workflows_sends_slack_when_enabled(
        self,
        service,
        mock_db,
        sample_invoice,
        sample_user,
        sample_client,
    ):
        from core.models.models_per_tenant import Settings

        workflow = WorkflowDefinition(
            id=99,
            key="overdue-with-slack",
            trigger_type="invoice_became_overdue",
            conditions={"invoice_statuses": ["sent"]},
            actions={
                "send_internal_notification": False,
                "create_internal_task": False,
                "send_slack_notification": True,
            },
            is_enabled=True,
            is_system=False,
            is_default=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        settings_row = Settings(
            key="slack_webhook_config",
            value={"webhook_url": "https://hooks.slack.com/services/T/B/X"},
        )

        def query_side_effect(model):
            return {
                WorkflowDefinition: Mock(
                    filter=Mock(return_value=Mock(all=Mock(return_value=[workflow])))
                ),
                Invoice: Mock(
                    filter=Mock(return_value=Mock(all=Mock(return_value=[sample_invoice])))
                ),
                Client: Mock(
                    filter=Mock(return_value=Mock(first=Mock(return_value=sample_client)))
                ),
                Settings: Mock(
                    filter=Mock(return_value=Mock(first=Mock(return_value=settings_row)))
                ),
            }[model]

        mock_response = Mock()
        mock_response.status_code = 200

        with patch(
            "core.services.workflow_service.FeatureConfigService.is_enabled",
            return_value=True,
        ), patch.object(service, "ensure_default_workflows"), patch.object(
            service, "_has_execution_log", return_value=False
        ), patch.object(
            service, "_resolve_assigned_user", return_value=sample_user
        ), patch(
            "requests.post", return_value=mock_response
        ) as mock_post:
            mock_db.query.side_effect = query_side_effect

            stats = service.process_due_invoice_workflows()

        assert stats["slack_notification_count"] == 1
        assert stats["notification_count"] == 0
        assert stats["created_task_count"] == 0

        slack_text = mock_post.call_args.kwargs["json"]["text"]
        assert "INV-2026-001" in slack_text
        assert "ACME Corp" in slack_text

        added = [call[0][0] for call in mock_db.add.call_args_list]
        logs = [obj for obj in added if isinstance(obj, WorkflowExecutionLog)]
        assert logs[0].details["slack_notification_sent"] is True

    def test_process_all_workflows_aggregates_slack_notification_count(self, service):
        empty_stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "client_note_count": 0,
            "client_email_count": 0,
            "slack_notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }
        with patch.object(
            service,
            "process_due_invoice_workflows",
            return_value={**empty_stats, "slack_notification_count": 2},
        ), patch.object(
            service, "process_invoice_created_workflows", return_value=empty_stats
        ), patch.object(
            service,
            "process_payment_received_workflows",
            return_value={**empty_stats, "slack_notification_count": 1},
        ), patch.object(
            service, "process_client_created_workflows", return_value=empty_stats
        ), patch.object(
            service, "process_expense_created_workflows", return_value=empty_stats
        ), patch.object(
            service,
            "process_expense_submitted_for_approval_workflows",
            return_value=empty_stats,
        ):
            stats = service.process_all_workflows()
            assert stats["slack_notification_count"] == 3

    # ---------- duplicate_workflow ----------

    def test_duplicate_workflow_raises_when_source_missing(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="Workflow not found"):
            service.duplicate_workflow(999)

    def test_duplicate_workflow_copies_payload_and_marks_user_owned(
        self, service, mock_db, sample_system_workflow
    ):
        # Re-use the system fixture as the source so we also assert
        # is_system/is_default are flipped on the clone.
        sample_system_workflow.actions = {
            "send_internal_notification": True,
            "create_internal_task": False,
            "add_client_note": True,
            "assign_to_specific_user": True,
            "assigned_user_id": 42,
            "send_client_email": True,
            "send_slack_notification": True,
            "task_type": "reminder",
            "task_due_in_days": 1,
        }
        sample_system_workflow.conditions = {"invoice_statuses": ["sent", "overdue"]}
        sample_system_workflow.description = "Original description"
        sample_system_workflow.is_enabled = False  # deliberately disabled source

        # First .first() returns the source; subsequent .first()s used by
        # _build_workflow_key to check name uniqueness return None.
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_system_workflow,
            None,
        ]

        clone = service.duplicate_workflow(sample_system_workflow.id)

        assert clone.name == f"{sample_system_workflow.name} (copy)"
        assert clone.trigger_type == sample_system_workflow.trigger_type
        assert clone.description == "Original description"
        assert clone.conditions == {"invoice_statuses": ["sent", "overdue"]}
        # Carries all action flags including assigned_user_id.
        assert clone.actions["add_client_note"] is True
        assert clone.actions["send_client_email"] is True
        assert clone.actions["send_slack_notification"] is True
        assert clone.actions["assigned_user_id"] == 42
        # Clone is always user-owned and enabled regardless of source state.
        assert clone.is_system is False
        assert clone.is_default is False
        assert clone.is_enabled is True
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_duplicate_workflow_handles_name_collision(
        self, service, mock_db, sample_custom_workflow
    ):
        # _build_workflow_key suffixes -2 when the slugified name already
        # exists. The fixture's name is "Custom Escalation", base slug is
        # "custom-escalation-copy" → first lookup returns an existing row,
        # second returns None.
        existing = WorkflowDefinition(id=88, key="custom-escalation-copy")
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_custom_workflow,  # source load
            existing,                 # slug "custom-escalation-copy" exists
            None,                     # slug "custom-escalation-copy-2" free
        ]

        clone = service.duplicate_workflow(sample_custom_workflow.id)
        assert clone.key == "custom-escalation-copy-2"

    def test_duplicate_workflow_decouples_mutable_dicts(
        self, service, mock_db, sample_custom_workflow
    ):
        sample_custom_workflow.actions = {"send_internal_notification": True}
        sample_custom_workflow.conditions = {"invoice_statuses": ["sent"]}
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_custom_workflow,
            None,
        ]

        clone = service.duplicate_workflow(sample_custom_workflow.id)
        # Mutating the clone's dicts must not mutate the source — guards
        # against accidental aliasing if SQLAlchemy returns the same dict.
        clone.actions["new_flag"] = True
        clone.conditions["new_cond"] = ["x"]
        assert "new_flag" not in sample_custom_workflow.actions
        assert "new_cond" not in sample_custom_workflow.conditions


if __name__ == "__main__":
    pytest.main([__file__])
