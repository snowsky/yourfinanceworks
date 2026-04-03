from fastapi import APIRouter

from core.routers.super_admin import tenants, users, system

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

router.include_router(tenants.router)
router.include_router(users.router)
router.include_router(system.router)

# Re-export the auth dependency consumed by other modules
from core.routers.super_admin._shared import require_super_admin  # noqa: F401
