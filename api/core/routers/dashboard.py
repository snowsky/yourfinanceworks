"""Dashboard router — server-side aggregated stats.

`GET /api/v1/dashboard/stats` returns the same `DashboardStats` shape the
frontend used to compute client-side from up to 2000 fetched rows, so the
dashboard pulls one small summary instead. Auth-only (dashboard is core);
tenant is resolved by the tenant-context middleware before the handler runs.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.services.dashboard_service import get_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def read_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Aggregated dashboard statistics for the current tenant."""
    return get_dashboard_stats(db)
