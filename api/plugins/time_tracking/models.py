"""
Time Tracking Plugin — SQLAlchemy Models

Tables: projects, project_tasks, time_entries
Follows existing codebase patterns:
  - Integer PKs
  - Float monetary columns
  - DateTime(timezone=True) timestamps
  - String status fields (not Enum) for flexibility
  - Imports Base from models_per_tenant for test integration
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text,
    DateTime, ForeignKey
)
from sqlalchemy.orm import relationship

# Use the shared Base so tables are created in the tenant schema
from core.models.models_per_tenant import Base


class Project(Base):
    """
    A billable project linked to a client.
    billing_method: 'hourly' | 'fixed_cost'
    status: 'active' | 'completed' | 'archived' | 'cancelled'
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    billing_method = Column(String, nullable=False, default="hourly")  # 'hourly' | 'fixed_cost'
    fixed_amount = Column(Float, nullable=True)
    budget_hours = Column(Float, nullable=True)
    budget_amount = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="active")
    currency = Column(String(3), nullable=False, default="USD")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"


class ProjectTask(Base):
    """
    A task within a project. Can have its own hourly_rate (overrides project rate).
    status: 'active' | 'completed' | 'cancelled'
    """
    __tablename__ = "project_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    estimated_hours = Column(Float, nullable=True)
    hourly_rate = Column(Float, nullable=True)  # overrides project-level rate if set
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("Project", back_populates="tasks")
    time_entries = relationship("TimeEntry", back_populates="task")

    def __repr__(self):
        return f"<ProjectTask(id={self.id}, name='{self.name}')>"


class TimeEntry(Base):
    """
    A logged unit of time against a project/task.
    status: 'in_progress' | 'logged' | 'approved' | 'invoiced'

    Timer workflow:
      - POST /timer/start  → creates entry with status='in_progress', ended_at=None
      - POST /timer/stop   → sets ended_at, computes duration_minutes and amount
      - GET  /timer/active → returns latest in_progress entry for current user

    duration_minutes is always stored (computed on stop, or provided for manual entries).
    amount = (duration_minutes / 60) * hourly_rate (stored for fast export queries).
    invoice_number is denormalized for fast Excel export without a join.
    """
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("project_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)

    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    hourly_rate = Column(Float, nullable=False)
    billable = Column(Boolean, nullable=False, default=True)
    amount = Column(Float, nullable=True)  # computed: (duration_minutes/60) * hourly_rate

    status = Column(String, nullable=False, default="in_progress")
    invoiced = Column(Boolean, nullable=False, default=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    invoice_number = Column(String, nullable=True)  # denormalized for fast export

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("Project", back_populates="time_entries")
    task = relationship("ProjectTask", back_populates="time_entries")

    @property
    def hours(self) -> float:
        """Computed hours from duration_minutes"""
        if self.duration_minutes is not None:
            return round(self.duration_minutes / 60.0, 4)
        return 0.0

    def compute_amount(self):
        """Compute and store the billable amount"""
        if self.duration_minutes and self.hourly_rate:
            self.amount = round((self.duration_minutes / 60.0) * self.hourly_rate, 2)
        else:
            self.amount = None

    def __repr__(self):
        return f"<TimeEntry(id={self.id}, project_id={self.project_id}, status='{self.status}')>"
