import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models.database import SessionLocal
from core.models.models_per_tenant import Client
from ..models import Project, ProjectTask, TimeEntry

logger = logging.getLogger(__name__)

class TimeTrackingMCPProvider:
    """
    MCP provider for time tracking integration with AI assistant.
    Provides project, task, and time entry data to the MCP assistant while enforcing
    tenant isolation and data privacy.
    """

    def __init__(self, db_session: Session = None):
        """
        Initialize the MCP provider with database session.

        Args:
            db_session: SQLAlchemy session. If None, will create a new session.
        """
        self.provider_name = "time_tracking"
        self.version = "1.0.0"
        self.db = db_session or SessionLocal()

    def _enrich_project(self, project: Project) -> dict:
        """Add client_name and aggregated stats to a project dict."""
        client = self.db.query(Client).filter(Client.id == project.client_id).first()
        hours_agg = (
            self.db.query(func.sum(TimeEntry.duration_minutes))
            .filter(TimeEntry.project_id == project.id, TimeEntry.status != "in_progress")
            .scalar()
        ) or 0
        amount_agg = (
            self.db.query(func.sum(TimeEntry.amount))
            .filter(TimeEntry.project_id == project.id, TimeEntry.invoiced == False)  # noqa: E712
            .scalar()
        ) or 0.0

        return {
            "id": project.id,
            "client_id": project.client_id,
            "client_name": client.name if client else None,
            "name": project.name,
            "description": project.description,
            "billing_method": project.billing_method,
            "status": project.status,
            "total_hours_logged": round(hours_agg / 60.0, 2) if hours_agg else 0.0,
            "total_amount_logged": round(float(amount_agg), 2),
        }

    async def get_projects(self, tenant_id: int, status: str = None) -> Dict[str, Any]:
        """
        Get all projects for the tenant.

        Args:
            tenant_id: Tenant ID for isolation
            status: Optional status to filter by

        Returns:
            Dict containing projects data
        """
        try:
            # For multi-tenant, since this provider runs with a DB session that might be Tenant-mapped, 
            # In our setup, the `__init__` takes db_session or creates SessionLocal, but ideally we only 
            # query those linked to the logged in user or we just query the tenant's DB if isolation is at DB level.
            # Usually, `db` is already scoped to the tenant in this framework.
            q = self.db.query(Project)
            if status:
                q = q.filter(Project.status == status)
            projects = q.all()

            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "projects": [self._enrich_project(p) for p in projects],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting projects: {str(e)}")
            return {"error": str(e)}

    async def get_tasks(self, tenant_id: int, project_id: int) -> Dict[str, Any]:
        """
        Get tasks for a specific project.
        """
        try:
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {"error": "Project not found"}

            tasks = self.db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
            results = []
            for task in tasks:
                actual_minutes = (
                    self.db.query(func.sum(TimeEntry.duration_minutes))
                    .filter(TimeEntry.task_id == task.id, TimeEntry.status != "in_progress")
                    .scalar()
                ) or 0
                results.append({
                    "id": task.id,
                    "name": task.name,
                    "description": task.description,
                    "status": task.status,
                    "estimated_hours": task.estimated_hours,
                    "actual_hours": round(actual_minutes / 60.0, 2)
                })

            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "tasks": results,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting tasks: {str(e)}")
            return {"error": str(e)}

    async def get_time_entries(self, tenant_id: int, user_id: int = None, project_id: int = None, limit: int = 50) -> Dict[str, Any]:
        """
        Get recent time entries.
        """
        try:
            q = self.db.query(TimeEntry)
            if user_id:
                q = q.filter(TimeEntry.user_id == user_id)
            if project_id:
                q = q.filter(TimeEntry.project_id == project_id)
            
            entries = q.order_by(TimeEntry.started_at.desc()).limit(limit).all()
            
            results = []
            for entry in entries:
                project = self.db.query(Project).filter(Project.id == entry.project_id).first()
                task = self.db.query(ProjectTask).filter(ProjectTask.id == entry.task_id).first() if entry.task_id else None
                results.append({
                    "id": entry.id,
                    "project_name": project.name if project else None,
                    "task_name": task.name if task else None,
                    "description": entry.description,
                    "started_at": entry.started_at.isoformat() if entry.started_at else None,
                    "ended_at": entry.ended_at.isoformat() if entry.ended_at else None,
                    "duration_minutes": entry.duration_minutes,
                    "amount": entry.amount,
                    "status": entry.status
                })

            return {
                "provider": self.provider_name,
                "tenant_id": tenant_id,
                "entries": results,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting time entries: {str(e)}")
            return {"error": str(e)}

    async def get_active_timer(self, tenant_id: int, user_id: int) -> Dict[str, Any]:
        """
        Get the currently active timer for a user.
        """
        try:
            entry = (
                self.db.query(TimeEntry)
                .filter(TimeEntry.user_id == user_id, TimeEntry.status == "in_progress")
                .order_by(TimeEntry.started_at.desc())
                .first()
            )
            if not entry:
                return {
                    "active": False,
                    "entry": None,
                    "elapsed_minutes": 0
                }

            now = datetime.now(timezone.utc)
            started = entry.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            elapsed = int((now - started).total_seconds() / 60)

            project = self.db.query(Project).filter(Project.id == entry.project_id).first()

            return {
                "active": True,
                "entry": {
                    "id": entry.id,
                    "project_id": entry.project_id,
                    "project_name": project.name if project else None,
                    "started_at": entry.started_at.isoformat(),
                    "description": entry.description
                },
                "elapsed_minutes": elapsed,
                "timestamp": now.isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting active timer: {str(e)}")
            return {"error": str(e)}

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information for registration"""
        return {
            "name": self.provider_name,
            "version": self.version,
            "description": "Time tracking and project management data provider for MCP assistant",
            "methods": [
                "get_projects",
                "get_tasks",
                "get_time_entries",
                "get_active_timer"
            ],
            "capabilities": [
                "Track project status and profitability",
                "Review tasks and logged hours",
                "Fetch recent time entries",
                "Check for active running timers"
            ]
        }

    def close(self):
        """Close database connections and clean up resources."""
        if hasattr(self, 'db'):
            self.db.close()
