"""
Tools API — assembles all domain sub-routers under /api/v1/tools/.
Designed for agent consumption: read+write, consistent envelopes, OpenAPI-discoverable.
"""
from fastapi import APIRouter

from .bank_statements import router as bank_statements_router
from .clients import router as clients_router
from .email_references import router as email_references_router
from .expenses import router as expenses_router
from .invoices import router as invoices_router
from .payments import router as payments_router

router = APIRouter(tags=["tools-api"])
router.include_router(invoices_router)
router.include_router(expenses_router)
router.include_router(clients_router)
router.include_router(payments_router)
router.include_router(bank_statements_router)
router.include_router(email_references_router)
