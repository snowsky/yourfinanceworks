from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

from core.models.database import set_tenant_context
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.services.tenant_database_manager import tenant_db_manager
from core.services.timeline_service import get_client_timeline
from core.schemas.timeline import TimelineResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["client-timeline"])


@router.get("/{client_id}/timeline", response_model=TimelineResponse)
async def client_timeline(
    client_id: int,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Events per page"),
    event_types: Optional[str] = Query(
        None,
        description="Comma-separated event type filter: invoice,payment,expense,bank_transaction,note",
    ),
    source: Optional[str] = Query(
        None,
        description="Comma-separated source filter: invoice,expense,bank_statement,note",
    ),
    current_user: MasterUser = Depends(get_current_user),
) -> TimelineResponse:
    """
    Return a unified, paginated activity timeline for a client.

    Aggregates invoices, payments, expenses (matched by vendor name),
    bank statement transactions (linked via invoice or matched expense),
    and client notes — sorted by date descending.
    """
    # Tenant-aware: set context and get tenant DB session
    set_tenant_context(current_user.tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    db = SessionLocal()

    try:
        result = get_client_timeline(
            db=db,
            client_id=client_id,
            page=page,
            page_size=page_size,
            event_types=event_types,
            source_filter=source,
        )

        if result is None:
            raise HTTPException(status_code=404, detail="Client not found")

        return TimelineResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching timeline for client {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch client timeline")
    finally:
        db.close()
