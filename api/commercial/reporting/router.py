"""
Reporting router — delegates to the routers/ package.

Split from a 1,904-line monolith into focused modules:
  routers/generate.py     — GET /types, POST /generate, /preview, /regenerate/{id}
  routers/templates.py    — CRUD for /templates and /templates/{id}
  routers/scheduled.py    — CRUD for /scheduled and /scheduled/{id}
  routers/history.py      — history, download, admin cleanup
  routers/performance.py  — cache, query/progress stats, tasks, optimization
"""

from .routers import router

__all__ = ["router"]
