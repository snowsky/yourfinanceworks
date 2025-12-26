"""
Centralized User Role Service - Single Source of Truth for User Roles
"""
from typing import Optional
from sqlalchemy.orm import Session
from core.models.models import MasterUser
from core.models.models_per_tenant import User as TenantUser


class UserRoleService:
    """Centralized service for managing and checking user roles"""
    
    # Define all valid roles in one place
    VALID_ROLES = ["admin", "super_admin", "administrator", "manager", "user", "viewer"]
    
    # Define admin roles in one place
    ADMIN_ROLES = ["admin", "super_admin", "administrator", "manager"]
    
    # Define roles that can access reports
    REPORT_ROLES = ["admin", "super_admin", "administrator", "manager", "user"]
    
    @staticmethod
    def get_user_role(db_master: Session, user_id: int) -> str:
        """
        Get user's role from master database (single source of truth)
        
        Args:
            db_master: Master database session
            user_id: User ID to look up
            
        Returns:
            User's role as string
        """
        try:
            user = db_master.query(MasterUser).filter(MasterUser.id == user_id).first()
            return user.role if user else "user"
        except Exception:
            return "user"
    
    @staticmethod
    def update_user_role(db_master: Session, user_id: int, new_role: str) -> bool:
        """
        Update user's role in master database (single source of truth)
        
        Args:
            db_master: Master database session
            user_id: User ID to update
            new_role: New role to assign
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if new_role not in UserRoleService.VALID_ROLES:
                return False
                
            user = db_master.query(MasterUser).filter(MasterUser.id == user_id).first()
            if not user:
                return False
                
            user.role = new_role
            db_master.commit()
            
            # Also update tenant database if user exists there
            UserRoleService._sync_to_tenant_db(db_master, user_id, new_role)
            
            return True
        except Exception:
            db_master.rollback()
            return False
    
    @staticmethod
    def _sync_to_tenant_db(db_master: Session, user_id: int, role: str) -> None:
        """
        Sync role to tenant database (for consistency, but master is source of truth)
        
        Args:
            db_master: Master database session
            user_id: User ID to sync
            role: Role to sync
        """
        try:
            # Get tenant info from master user
            master_user = db_master.query(MasterUser).filter(MasterUser.id == user_id).first()
            if not master_user or not master_user.tenant_id:
                return
                
            # Import here to avoid circular imports
            from db_init import get_tenant_db
            
            # Get tenant database session
            tenant_db = next(get_tenant_db(master_user.tenant_id))
            
            try:
                # Update tenant user if exists
                tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user_id).first()
                if tenant_user:
                    tenant_user.role = role
                    tenant_db.commit()
            finally:
                tenant_db.close()
                
        except Exception:
            # Don't fail the main operation if tenant sync fails
            pass
    
    @staticmethod
    def is_admin_user(db_master: Session, user_id: int) -> bool:
        """
        Check if user is admin based on master database role
        
        Args:
            db_master: Master database session
            user_id: User ID to check
            
        Returns:
            True if user is admin, False otherwise
        """
        role = UserRoleService.get_user_role(db_master, user_id)
        return role in UserRoleService.ADMIN_ROLES
    
    @staticmethod
    def can_access_reports(db_master: Session, user_id: int) -> bool:
        """
        Check if user can access reports
        
        Args:
            db_master: Master database session
            user_id: User ID to check
            
        Returns:
            True if user can access reports, False otherwise
        """
        role = UserRoleService.get_user_role(db_master, user_id)
        return role in UserRoleService.REPORT_ROLES
    
    @staticmethod
    def get_all_users_with_roles(db_master: Session) -> list:
        """
        Get all users with their roles for debugging
        
        Args:
            db_master: Master database session
            
        Returns:
            List of users with their roles
        """
        try:
            users = db_master.query(MasterUser).all()
            return [
                {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "is_superuser": user.is_superuser,
                    "tenant_id": user.tenant_id,
                    "is_admin": user.role in UserRoleService.ADMIN_ROLES
                }
                for user in users
            ]
        except Exception:
            return []


# Convenience functions for backward compatibility
def get_user_role(db_master: Session, user_id: int) -> str:
    """Get user role from master database"""
    return UserRoleService.get_user_role(db_master, user_id)


def is_admin_user(db_master: Session, user_id: int) -> bool:
    """Check if user is admin"""
    return UserRoleService.is_admin_user(db_master, user_id)


def update_user_role(db_master: Session, user_id: int, new_role: str) -> bool:
    """Update user role in master database"""
    return UserRoleService.update_user_role(db_master, user_id, new_role)
