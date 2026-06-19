"""Clients-domain methods for the in-process AI client.

Mirrors core/routers/clients.py behavior but runs against the request's tenant
session, reusing the same shared helpers (RBAC, audit, validation, serialization,
notification). Spyable helpers are imported at module top for testability.
"""

from typing import Any, Dict

from core.utils.rbac import require_component_permission
from core.utils.audit import log_audit_event
from core.services.operation_notifications import maybe_send_operation_notification
from core.constants.error_codes import CLIENT_ALREADY_EXISTS


def _tenant_default_currency(tenant_id: int) -> str:
    from core.models.database import get_master_db
    from core.models.models import Tenant

    master_db = next(get_master_db())
    try:
        tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.default_currency:
            return tenant.default_currency
        return "USD"
    except Exception:
        return "USD"
    finally:
        master_db.close()


class ClientsInProcessMixin:
    async def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        from core.models.models_per_tenant import Client
        from core.schemas.client import ClientCreate
        from core.utils.timezone import get_tenant_timezone_aware_datetime
        from core.routers.clients import _client_to_dict

        db = self._db
        user = self._current_user

        require_component_permission(db, user, "customers", "user", "create clients")

        # Validate + normalize via the same schema the route uses.
        payload = ClientCreate(**client_data)
        data = payload.model_dump()
        if data.get("email") is not None and data["email"].strip() == "":
            data["email"] = None

        # Duplicate guard (mirror the route: compare decrypted name+email).
        if data.get("email") is not None:
            for existing in db.query(Client).all():
                if existing.name == data.get("name") and existing.email == data["email"]:
                    raise ValueError(CLIENT_ALREADY_EXISTS)

        if not data.get("preferred_currency") or not str(data.get("preferred_currency")).strip():
            data["preferred_currency"] = _tenant_default_currency(user.tenant_id)

        with db.begin_nested():
            db_client = Client(
                **data,
                created_at=get_tenant_timezone_aware_datetime(db),
                updated_at=get_tenant_timezone_aware_datetime(db),
            )
            db.add(db_client)
        db.commit()
        db.refresh(db_client)

        log_audit_event(
            db=db,
            user_id=user.id,
            user_email=user.email,
            action="CREATE",
            resource_type="client",
            resource_id=str(db_client.id),
            resource_name=db_client.name,
            details=data,
            status="success",
        )
        maybe_send_operation_notification(
            db,
            event_type="client_created",
            user_id=user.id,
            tenant_id=user.tenant_id,
            resource_type="client",
            resource_id=str(db_client.id),
            resource_name=db_client.name,
            details={
                "email": db_client.email,
                "phone": db_client.phone or "N/A",
                "preferred_currency": db_client.preferred_currency,
            },
        )
        return _client_to_dict(db_client)
