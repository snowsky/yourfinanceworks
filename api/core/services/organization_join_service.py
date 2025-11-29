import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models.models import OrganizationJoinRequest, Tenant, MasterUser
from core.schemas.organization_join import (
    OrganizationJoinRequestCreate, 
    OrganizationJoinRequestRead,
    OrganizationJoinRequestUpdate,
    OrganizationLookupResult,
    OrganizationJoinResponse
)
from core.utils.auth import get_password_hash, verify_password
from core.utils.notifications import send_notification

logger = logging.getLogger(__name__)

class OrganizationJoinService:
    """
    Service for managing organization join requests.
    Handles submission, approval, rejection, and cleanup of join requests.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.default_expiry_days = 30  # Requests expire after 30 days
    
    def lookup_organization(self, organization_name: str) -> OrganizationLookupResult:
        """
        Look up an organization by name to see if it exists.
        """
        try:
            # Search for tenant by name (case-insensitive)
            tenant = self.db.query(Tenant).filter(
                Tenant.name.ilike(f"%{organization_name.strip()}%"),
                Tenant.is_active == True
            ).first()
            
            if tenant:
                return OrganizationLookupResult(
                    exists=True,
                    tenant_id=tenant.id,
                    organization_name=tenant.name,
                    message=f"Organization '{tenant.name}' found. You can request to join."
                )
            else:
                return OrganizationLookupResult(
                    exists=False,
                    message=f"Organization '{organization_name}' not found. You can create a new organization instead."
                )
        except Exception as e:
            logger.error(f"Error looking up organization '{organization_name}': {str(e)}")
            return OrganizationLookupResult(
                exists=False,
                message="Error looking up organization. Please try again."
            )
    
    def create_join_request(self, request_data: OrganizationJoinRequestCreate) -> OrganizationJoinResponse:
        """
        Create a new organization join request.
        """
        try:
            # First, verify the organization exists
            tenant = self.db.query(Tenant).filter(
                Tenant.name.ilike(f"%{request_data.organization_name.strip()}%"),
                Tenant.is_active == True
            ).first()
            
            if not tenant:
                return OrganizationJoinResponse(
                    success=False,
                    message="Organization not found. Please check the organization name."
                )
            
            # Check if user already exists in the system
            existing_user = self.db.query(MasterUser).filter(
                MasterUser.email == request_data.email
            ).first()
            
            if existing_user:
                return OrganizationJoinResponse(
                    success=False,
                    message="An account with this email already exists. Please login instead."
                )
            
            # Check if there's already a pending request for this email/tenant
            existing_request = self.db.query(OrganizationJoinRequest).filter(
                and_(
                    OrganizationJoinRequest.email == request_data.email,
                    OrganizationJoinRequest.tenant_id == tenant.id,
                    OrganizationJoinRequest.status == "pending"
                )
            ).first()
            
            if existing_request:
                return OrganizationJoinResponse(
                    success=False,
                    message="You already have a pending request to join this organization."
                )
            
            # Create the join request
            hashed_password = get_password_hash(request_data.password)
            expires_at = datetime.now(timezone.utc) + timedelta(days=self.default_expiry_days)
            
            join_request = OrganizationJoinRequest(
                email=request_data.email,
                first_name=request_data.first_name,
                last_name=request_data.last_name,
                hashed_password=hashed_password,
                tenant_id=tenant.id,
                requested_role=request_data.requested_role,
                message=request_data.message,
                expires_at=expires_at
            )
            
            self.db.add(join_request)
            self.db.commit()
            self.db.refresh(join_request)
            
            logger.info(f"Created join request {join_request.id} for {request_data.email} to join {tenant.name}")
            
            # Send notification to all admins of the organization
            try:
                self._notify_admins_of_new_request(tenant.id, join_request)
            except Exception as e:
                logger.warning(f"Failed to send notification to admins for join request {join_request.id}: {str(e)}")
            
            return OrganizationJoinResponse(
                success=True,
                message=f"Request to join '{tenant.name}' submitted successfully. An admin will review your request.",
                request_id=join_request.id
            )
            
        except Exception as e:
            logger.error(f"Error creating join request: {str(e)}")
            self.db.rollback()
            return OrganizationJoinResponse(
                success=False,
                message="Error creating join request. Please try again."
            )
    
    def get_pending_requests(self, tenant_id: Optional[int] = None) -> List[OrganizationJoinRequestRead]:
        """
        Get pending join requests for a specific tenant or all tenants.
        """
        try:
            query = self.db.query(OrganizationJoinRequest).filter(
                OrganizationJoinRequest.status == "pending"
            )
            
            if tenant_id:
                query = query.filter(OrganizationJoinRequest.tenant_id == tenant_id)
            
            requests = query.order_by(OrganizationJoinRequest.created_at.desc()).all()
            
            result = []
            for request in requests:
                # Populate additional data
                request_data = OrganizationJoinRequestRead(
                    id=request.id,
                    email=request.email,
                    first_name=request.first_name,
                    last_name=request.last_name,
                    organization_name=request.tenant.name if request.tenant else None,
                    tenant_id=request.tenant_id,
                    requested_role=request.requested_role,
                    message=request.message,
                    status=request.status,
                    created_at=request.created_at,
                    expires_at=request.expires_at
                )
                result.append(request_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting pending requests: {str(e)}")
            return []
    
    def approve_join_request(
        self, 
        request_id: int, 
        admin_user_id: int, 
        approval_data: OrganizationJoinRequestUpdate
    ) -> OrganizationJoinResponse:
        """
        Approve a join request and create the user account.
        """
        try:
            # Get the join request
            join_request = self.db.query(OrganizationJoinRequest).filter(
                OrganizationJoinRequest.id == request_id,
                OrganizationJoinRequest.status == "pending"
            ).first()
            
            if not join_request:
                return OrganizationJoinResponse(
                    success=False,
                    message="Join request not found or already processed."
                )
            
            # Check if request has expired
            if join_request.expires_at and join_request.expires_at < datetime.now(timezone.utc):
                join_request.status = "expired"
                self.db.commit()
                return OrganizationJoinResponse(
                    success=False,
                    message="Join request has expired."
                )
            
            if approval_data.status == "approved":
                # Create the user account
                approved_role = approval_data.approved_role or join_request.requested_role
                
                # Create master user
                new_user = MasterUser(
                    email=join_request.email,
                    hashed_password=join_request.hashed_password,
                    first_name=join_request.first_name,
                    last_name=join_request.last_name,
                    role=approved_role,
                    tenant_id=join_request.tenant_id,
                    is_active=True,
                    is_verified=True
                )
                
                self.db.add(new_user)
                self.db.flush()  # Get the user ID
                
                # Update join request status
                join_request.status = "approved"
                join_request.reviewed_by_id = admin_user_id
                join_request.reviewed_at = datetime.now(timezone.utc)
                join_request.notes = approval_data.notes
                
                self.db.commit()
                
                # Create tenant user record in per-tenant database
                try:
                    from core.services.tenant_database_manager import tenant_db_manager
                    from core.models.models_per_tenant import User as TenantUser
                    
                    SessionLocal_tenant = tenant_db_manager.get_tenant_session(join_request.tenant_id)
                    tenant_db = SessionLocal_tenant()
                    
                    try:
                        tenant_user = TenantUser(
                            id=new_user.id,
                            email=new_user.email,
                            hashed_password=new_user.hashed_password,
                            first_name=new_user.first_name,
                            last_name=new_user.last_name,
                            role=new_user.role,
                            is_active=True,
                            is_verified=True
                        )
                        tenant_db.add(tenant_user)
                        tenant_db.commit()
                        logger.info(f"Created tenant user record for user {new_user.id} in tenant {join_request.tenant_id}")
                    finally:
                        tenant_db.close()
                except Exception as e:
                    logger.error(f"Failed to create tenant user record: {str(e)}")
                    # Don't fail the entire operation if tenant user creation fails
                
                logger.info(f"Approved join request {request_id}, created user {new_user.id}")
                
                # Send notification about approval
                try:
                    admin_user = self.db.query(MasterUser).filter(MasterUser.id == admin_user_id).first()
                    admin_name = f"{admin_user.first_name} {admin_user.last_name}".strip() if admin_user and admin_user.first_name else "Admin"
                    self._notify_requester_of_decision(join_request, "approved", admin_name)
                except Exception as e:
                    logger.warning(f"Failed to send approval notification: {str(e)}")
                
                return OrganizationJoinResponse(
                    success=True,
                    message="Join request approved successfully. User account created."
                )
            
            elif approval_data.status == "rejected":
                # Reject the request
                join_request.status = "rejected"
                join_request.reviewed_by_id = admin_user_id
                join_request.reviewed_at = datetime.now(timezone.utc)
                join_request.rejection_reason = approval_data.rejection_reason
                join_request.notes = approval_data.notes
                
                self.db.commit()
                
                logger.info(f"Rejected join request {request_id}")
                
                # Send notification about rejection
                try:
                    admin_user = self.db.query(MasterUser).filter(MasterUser.id == admin_user_id).first()
                    admin_name = f"{admin_user.first_name} {admin_user.last_name}".strip() if admin_user and admin_user.first_name else "Admin"
                    self._notify_requester_of_decision(join_request, "rejected", admin_name)
                except Exception as e:
                    logger.warning(f"Failed to send rejection notification: {str(e)}")
                
                return OrganizationJoinResponse(
                    success=True,
                    message="Join request rejected successfully."
                )
            
        except Exception as e:
            logger.error(f"Error processing join request {request_id}: {str(e)}")
            self.db.rollback()
            return OrganizationJoinResponse(
                success=False,
                message="Error processing join request. Please try again."
            )
    
    def cleanup_expired_requests(self) -> int:
        """
        Clean up expired join requests.
        Returns the number of expired requests cleaned up.
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Find expired pending requests
            expired_requests = self.db.query(OrganizationJoinRequest).filter(
                and_(
                    OrganizationJoinRequest.status == "pending",
                    OrganizationJoinRequest.expires_at < current_time
                )
            ).all()
            
            count = len(expired_requests)
            
            if count > 0:
                # Mark as expired
                for request in expired_requests:
                    request.status = "expired"
                
                self.db.commit()
                logger.info(f"Marked {count} join requests as expired")
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired requests: {str(e)}")
            self.db.rollback()
            return 0
    
    def get_request_by_id(self, request_id: int) -> Optional[OrganizationJoinRequestRead]:
        """
        Get a specific join request by ID.
        """
        try:
            request = self.db.query(OrganizationJoinRequest).filter(
                OrganizationJoinRequest.id == request_id
            ).first()
            
            if not request:
                return None
            
            return OrganizationJoinRequestRead(
                id=request.id,
                email=request.email,
                first_name=request.first_name,
                last_name=request.last_name,
                organization_name=request.tenant.name if request.tenant else None,
                tenant_id=request.tenant_id,
                requested_role=request.requested_role,
                message=request.message,
                status=request.status,
                rejection_reason=request.rejection_reason,
                reviewed_by_id=request.reviewed_by_id,
                reviewed_by_name=f"{request.reviewed_by.first_name} {request.reviewed_by.last_name}".strip() if request.reviewed_by else None,
                notes=request.notes,
                created_at=request.created_at,
                reviewed_at=request.reviewed_at,
                expires_at=request.expires_at
            )
            
        except Exception as e:
            logger.error(f"Error getting request {request_id}: {str(e)}")
            return None
    
    def _notify_admins_of_new_request(self, tenant_id: int, join_request: OrganizationJoinRequest):
        """Send notification to all admins of the organization about a new join request."""
        try:
            # Get all admin users for this tenant from master database
            admin_users = self.db.query(MasterUser).filter(
                and_(
                    MasterUser.tenant_id == tenant_id,
                    MasterUser.role == "admin",
                    MasterUser.is_active == True
                )
            ).all()
            
            # Create reminder notifications for each admin in their tenant database
            from core.services.tenant_database_manager import tenant_db_manager
            from core.models.models_per_tenant import ReminderNotification
            
            requester_name = f"{join_request.first_name} {join_request.last_name}".strip() if join_request.first_name else join_request.email
            
            # Get tenant database session
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            tenant_db = SessionLocal_tenant()
            
            try:
                for admin_user in admin_users:
                    # Create in-app notification for the admin
                    notification = ReminderNotification(
                        reminder_id=None,  # Not linked to a specific reminder
                        user_id=admin_user.id,
                        notification_type="join_request",
                        channel="in_app",
                        scheduled_for=datetime.now(timezone.utc),
                        subject="New Join Request",
                        message=f"{requester_name} has requested to join your organization",
                        is_sent=True,
                        sent_at=datetime.now(timezone.utc),
                        is_read=False
                    )
                    tenant_db.add(notification)
                
                tenant_db.commit()
                logger.info(f"Created reminder notifications for {len(admin_users)} admin(s) about new join request {join_request.id}")
            finally:
                tenant_db.close()
            
        except Exception as e:
            logger.error(f"Error notifying admins of new join request {join_request.id}: {str(e)}")
            raise e
    
    def _notify_requester_of_decision(self, join_request: OrganizationJoinRequest, decision: str, admin_name: str):
        """Send notification to the requester about the decision on their join request."""
        try:
            # Note: Since the requester is not yet a user in the system, 
            # we would typically send an email directly rather than through the notification system.
            # For now, we'll log this - in a full implementation, you'd send an email.
            logger.info(f"Would notify {join_request.email} that their join request was {decision} by {admin_name}")
            
        except Exception as e:
            logger.error(f"Error notifying requester about join request decision: {str(e)}")
