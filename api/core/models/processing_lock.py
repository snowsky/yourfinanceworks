"""
Processing lock model to prevent duplicate reprocess requests
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from core.models.models_per_tenant import Base
from datetime import datetime, timezone, timedelta
import json
import uuid


class ProcessingLock(Base):
    """
    Model to track active processing locks for expenses, bank statements, and invoices.
    Prevents duplicate reprocess requests that would send multiple Kafka messages.
    Enhanced with crash recovery capabilities.
    """
    __tablename__ = "processing_locks"

    id = Column(Integer, primary_key=True, index=True)

    # Resource identification (matches the table schema)
    resource_type = Column  (String(50), nullable=False, index=True)  # 'expense', 'bank_statement', 'invoice'
    resource_id = Column(String(255), nullable=False, index=True)  # Changed to String for flexibility

    # Timestamps
    acquired_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Additional metadata (JSONB in PostgreSQL)
    lock_metadata = Column(Text)  # JSON string for additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<ProcessingLock(resource_type='{self.resource_type}', resource_id='{self.resource_id}', expires_at='{self.expires_at}')>"

    @classmethod
    def create_lock_key(cls, resource_type: str, resource_id) -> str:
        """Create a unique lock key for a resource"""
        return f"{resource_type}:{resource_id}"

    @classmethod
    def is_locked(cls, db_session, resource_type: str, resource_id) -> bool:
        """Check if a resource currently has an active processing lock"""
        lock_key = cls.create_lock_key(resource_type, resource_id)
        now = datetime.now(timezone.utc)
        
        active_lock = db_session.query(cls).filter(
            cls.resource_type == resource_type,
            cls.resource_id == str(resource_id),
            cls.is_active == True,
            cls.expires_at > now
        ).first()
        
        return active_lock is not None

    @classmethod
    def acquire_lock(cls, db_session, resource_type: str, resource_id, user_id: int = None,
                    lock_duration_minutes: int = 30, metadata: dict = None) -> bool:
        """
        Acquire a processing lock for a resource.
        Returns True if lock was acquired, False if already locked.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=lock_duration_minutes)
        
        # Clean up expired locks first
        db_session.query(cls).filter(
            cls.resource_type == resource_type,
            cls.resource_id == str(resource_id),
            cls.expires_at <= now
        ).update({"is_active": False})
        
        # Check if there's already an active lock
        if cls.is_locked(db_session, resource_type, resource_id):
            return False
        
        # Create new lock
        new_lock = cls(
            resource_type=resource_type,
            resource_id=str(resource_id),
            expires_at=expires_at,
            metadata=json.dumps(metadata or {})
        )
        
        db_session.add(new_lock)
        return True

    @classmethod
    def release_lock(cls, db_session, resource_type: str, resource_id) -> bool:
        """Release a processing lock for a resource"""
        updated_count = db_session.query(cls).filter(
            cls.resource_type == resource_type,
            cls.resource_id == str(resource_id),
            cls.is_active == True
        ).update({"is_active": False})
        
        return updated_count > 0

    @classmethod
    def cleanup_expired_locks(cls, db_session) -> int:
        """Clean up expired locks. Returns number of locks cleaned up."""
        now = datetime.now(timezone.utc)
        
        updated_count = db_session.query(cls).filter(
            cls.expires_at <= now,
            cls.is_active == True
        ).update({"is_active": False})
        
        return updated_count

    @classmethod
    def force_release_stuck_locks(cls, db_session, resource_type: str = None,
                                  older_than_minutes: int = 60) -> int:
        """
        Force release locks that may be stuck due to service crashes.
        This should be used carefully and typically only via admin endpoints.
        
        Args:
            db_session: Database session
            resource_type: If specified, only release locks for this resource type
            older_than_minutes: Only release locks older than this many minutes
        """
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(minutes=older_than_minutes)
        
        query = db_session.query(cls).filter(
            cls.is_active == True,
            cls.expires_at <= cutoff_time
        )
        
        if resource_type:
            query = query.filter(cls.resource_type == resource_type)
        
        updated_count = query.update({
            "is_active": False,
            "metadata": json.dumps({
                "recovery_note": f"Force released by cleanup at {now.isoformat()} due to suspected service crash",
                "original_metadata": cls.get_metadata_safe()
            })
        })
        
        return updated_count

    @classmethod
    def startup_lock_recovery(cls, db_session, older_than_minutes: int = 30) -> dict:
        """
        Run on application startup to recover from any locks left by crashed services.
        This is the key enhancement to handle service failures gracefully.
        
        Returns a summary of what was cleaned up.
        """
        now = datetime.now(timezone.utc)
        recovery_time = now - timedelta(minutes=older_than_minutes)
        
        # First, clean up any completely expired locks
        expired_count = cls.cleanup_expired_locks(db_session)
        
        # Then, look for potentially stuck locks
        stuck_locks = db_session.query(cls).filter(
            cls.is_active == True,
            cls.expires_at <= recovery_time
        ).all()
        
        stuck_count = len(stuck_locks)
        
        if stuck_count > 0:
            # Mark stuck locks as inactive with crash recovery note
            for lock in stuck_locks:
                lock.is_active = False
                try:
                    current_metadata = lock.get_metadata() if hasattr(lock, 'get_metadata') else {}
                    current_metadata['recovery_note'] = f"Recovered from potential service crash at {now.isoformat()}"
                    lock.lock_metadata = json.dumps(current_metadata)
                except:
                    lock.lock_metadata = json.dumps({"recovery_note": f"Recovered from potential service crash at {now.isoformat()}"})
            
            db_session.commit()
        
        # Get statistics for reporting
        total_active = db_session.query(cls).filter(cls.is_active == True).count()
        
        return {
            "recovery_timestamp": now.isoformat(),
            "expired_locks_cleaned": expired_count,
            "stuck_locks_recovered": stuck_count,
            "remaining_active_locks": total_active,
            "recovery_summary": f"Cleaned up {expired_count} expired, recovered {stuck_count} stuck locks"
        }

    @classmethod
    def is_processing_active(cls, db_session, resource_type: str, resource_id) -> dict:
        """
        Check if a resource is currently being processed and get details.
        This helps distinguish between "locked" and "actually being processed".
        """
        now = datetime.now(timezone.utc)
        
        active_lock = db_session.query(cls).filter(
            cls.resource_type == resource_type,
            cls.resource_id == str(resource_id),
            cls.is_active == True,
            cls.expires_at > now
        ).first()
        
        if active_lock:
            time_remaining = (active_lock.expires_at - now).total_seconds() / 60  # minutes
            lock_age = (now - active_lock.acquired_at).total_seconds() / 60  # minutes
            
            return {
                "locked": True,
                "actively_processing": True,
                "acquired_at": active_lock.acquired_at.isoformat(),
                "expires_at": active_lock.expires_at.isoformat(),
                "time_remaining_minutes": round(time_remaining, 2),
                "lock_age_minutes": round(lock_age, 2),
                "metadata": active_lock.get_metadata_safe()
            }
        else:
            return {"locked": False, "actively_processing": False}

    def get_metadata_safe(self) -> dict:
        """Safely get metadata as dict, returns empty dict if None or invalid JSON"""
        if not self.lock_metadata:
            return {}
        try:
            return json.loads(self.lock_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    def is_expired(self) -> bool:
        """Check if this lock has expired"""
        return datetime.now(timezone.utc) > self.expires_at

    def extend_lock(self, additional_minutes: int = 30) -> None:
        """Extend the lock expiration time"""
        self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=additional_minutes)

    @classmethod
    def get_active_lock_info(cls, db_session, resource_type: str, resource_id: int) -> dict:
        """Get information about active lock for a resource"""
        now = datetime.now(timezone.utc)
        
        active_lock = db_session.query(cls).filter(
            cls.resource_type == resource_type,
            cls.resource_id == str(resource_id),
            cls.is_active == True,
            cls.expires_at > now
        ).first()
        
        if active_lock:
            metadata = active_lock.get_metadata_safe()
            return {
                "locked": True,
                "acquired_at": active_lock.acquired_at.isoformat() if active_lock.acquired_at else None,
                "created_at": active_lock.created_at.isoformat() if active_lock.created_at else None,
                "expires_at": active_lock.expires_at.isoformat() if active_lock.expires_at else None,
                "metadata": metadata
            }
        else:
            return {"locked": False}