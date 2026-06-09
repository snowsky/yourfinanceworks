"""Payment-date forecast endpoint for outstanding invoices."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.services.payment_predictor import PaymentDatePredictor

router = APIRouter()


@router.get("/payment-forecast")
async def payment_forecast(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Predicted payment date + confidence for each outstanding invoice."""
    return PaymentDatePredictor(db).predict_outstanding()
