# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

"""
AI router.
Assembles focused sub-routers into the /ai prefix.
"""

from fastapi import APIRouter, Depends
from core.routers.auth import get_current_user

from commercial.ai.routers.invoice_analysis import router as invoice_analysis_router
from commercial.ai.routers.chat import router as chat_router
from commercial.ai.routers.client_notes import router as client_notes_router
from commercial.ai.routers.chat_history import router as chat_history_router

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

router.include_router(invoice_analysis_router)
router.include_router(chat_router)
router.include_router(client_notes_router)
router.include_router(chat_history_router)
