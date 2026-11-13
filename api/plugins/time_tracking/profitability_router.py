"""Cost-bearing endpoints are exclusively tenant administrator routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from .cost_models import ContributorCostRate
from .cost_schemas import CostRateWrite, CostRateResponse, CostBackfillRequest, CostBackfillPreview, CostBackfillResult
from .cost_service import require_cost_admin, set_cost_rate, preview_cost_backfill, apply_cost_backfill

profitability_router = APIRouter()


def cost_admin(db: Session = Depends(get_db), actor: MasterUser = Depends(get_current_user)):
    require_cost_admin(db, actor)
    return actor


@profitability_router.get('/cost-rates', response_model=list[CostRateResponse])
def list_cost_rates(currency: str = Query(..., pattern=r'^[A-Z]{3}$'), user_id: int = Query(..., gt=0),
                    db: Session = Depends(get_db), actor=Depends(cost_admin)):
    from core.models.models_per_tenant import User
    # Include inactive tenant contributors so historical records remain reviewable.
    return db.query(ContributorCostRate).join(User, ContributorCostRate.user_id == User.id).filter(
        ContributorCostRate.currency == currency, ContributorCostRate.user_id == user_id,
    ).order_by(ContributorCostRate.effective_from).all()


@profitability_router.post('/cost-rates', response_model=CostRateResponse)
def write_cost_rate(payload: CostRateWrite, db: Session = Depends(get_db), actor=Depends(cost_admin)):
    try:
        response = set_cost_rate(db, actor, payload)
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@profitability_router.post('/{project_id}/cost-backfill/preview', response_model=CostBackfillPreview)
def preview_backfill(project_id: int, payload: CostBackfillRequest, db: Session = Depends(get_db), actor=Depends(cost_admin)):
    return preview_cost_backfill(db, project_id, payload.entry_ids)


@profitability_router.post('/{project_id}/cost-backfill/apply', response_model=CostBackfillResult)
def apply_backfill(project_id: int, payload: CostBackfillPreview, db: Session = Depends(get_db), actor=Depends(cost_admin)):
    from fastapi import HTTPException
    if project_id != payload.project_id:
        raise HTTPException(422, 'Preview project does not match request')
    try:
        result = apply_cost_backfill(db, actor, payload)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
