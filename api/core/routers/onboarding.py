"""Onboarding endpoints: sample-data seeding for a new tenant."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer
from core.services.sample_data import SampleDataError, SampleDataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/sample-data")
async def get_sample_data_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return SampleDataService(db).sample_data_status()


@router.post("/sample-data")
async def seed_sample_data(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_non_viewer(current_user, "load sample data")
    try:
        return SampleDataService(db).seed(user_id=current_user.id)
    except SampleDataError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/sample-data")
async def clear_sample_data(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_non_viewer(current_user, "remove sample data")
    return SampleDataService(db).clear()
