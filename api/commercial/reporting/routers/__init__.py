"""
Reporting router package.

Split from the original monolithic router.py (1,904 lines) into focused modules:
  - generate.py     — GET /types, POST /generate, /preview, /regenerate/{id}
  - templates.py    — CRUD for /templates and /templates/{id}
  - scheduled.py    — CRUD for /scheduled and /scheduled/{id}
  - history.py      — GET /history, GET /download/{id}, DELETE /history/{id},
                       GET /storage/stats, POST /cleanup/expired, /cleanup/orphaned
  - performance.py  — GET/DELETE /performance/cache, /performance/query/stats,
                       /performance/progress/stats, /tasks, /optimization/recommendations
  - _shared.py      — get_report_service, error handlers, shared deps
"""

from fastapi import APIRouter

from . import generate, templates, scheduled, history, performance

router = APIRouter(prefix="/reports", tags=["reports"])

router.include_router(generate.router)
router.include_router(templates.router)
router.include_router(scheduled.router)
router.include_router(history.router)
router.include_router(performance.router)
