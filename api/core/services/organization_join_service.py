import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models.models import OrganizationJoinRequest, Tenant, MasterUser
from core.models.models_per_tenant import Settings
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider, EmailMessage
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

            # Allow existing users to request to join additional organizations
            # But check if they're already a member of this organization
            if existing_user:
                # Check if user is already a member of this tenant
                if existing_user.tenant_id == tenant.id:
                    return OrganizationJoinResponse(
                        success=False,
                        message="You are already a member of this organization."
                    )
                
                # Check if user has an existing association with this tenant
                from core.models.models import user_tenant_association
                existing_association = self.db.query(user_tenant_association).filter(
                    user_tenant_association.c.user_id == existing_user.id,
                    user_tenant_association.c.tenant_id == tenant.id,
                    user_tenant_association.c.is_active == True
                ).first()
                
                if existing_association:
                    return OrganizationJoinResponse(
                        success=False,
                        message="You are already a member of this organization."
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
                # Create the user account or add existing user to organization
                approved_role = approval_data.approved_role or join_request.requested_role

                # Check if user already exists
                existing_user = self.db.query(MasterUser).filter(
                    MasterUser.email == join_request.email
                ).first()

                if existing_user:
                    # Add existing user to this organization
                    user_to_add = existing_user

                    # Add user to the user_tenant_association table
                    from core.models.models import user_tenant_association
                    self.db.execute(
                        user_tenant_association.insert().values(
                            user_id=existing_user.id,
                            tenant_id=join_request.tenant_id,
                            role=approved_role
                        )
                    )

                    logger.info(f"Added existing user {existing_user.id} to organization {join_request.tenant_id}")
                else:
                    # Create new master user
                    user_to_add = MasterUser(
                        email=join_request.email,
                        hashed_password=join_request.hashed_password,
                        first_name=join_request.first_name,
                        last_name=join_request.last_name,
                        role=approved_role,
                        tenant_id=join_request.tenant_id,
                        is_active=True,
                        is_verified=True
                    )

                    self.db.add(user_to_add)
                    self.db.flush()  # Get the user ID

                    # Add user to the user_tenant_association table so they can access this organization
                    from core.models.models import user_tenant_association
                    self.db.execute(
                        user_tenant_association.insert().values(
                            user_id=user_to_add.id,
                            tenant_id=join_request.tenant_id,
                        )
                    )

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
                        # Check if tenant user already exists
                        existing_tenant_user = tenant_db.query(TenantUser).filter(
                            TenantUser.id == user_to_add.id
                        ).first()

                        if existing_tenant_user:
                            # Update existing tenant user with new role for this organization
                            existing_tenant_user.role = approved_role
                            existing_tenant_user.is_active = True
                            tenant_db.commit()
                            logger.info(f"Updated existing tenant user {user_to_add.id} with role {approved_role}")
                        else:
                            # Create new tenant user
                            tenant_user = TenantUser(
                                id=user_to_add.id,
                                email=user_to_add.email,
                                hashed_password=user_to_add.hashed_password,
                                first_name=user_to_add.first_name,
                                last_name=user_to_add.last_name,
                                role=approved_role,
                                is_active=True,
                                is_verified=True
                            )
                            tenant_db.add(tenant_user)
                            tenant_db.commit()
                            logger.info(f"Created tenant user record for user {user_to_add.id} in tenant {join_request.tenant_id}")
                    finally:
                        tenant_db.close()
                except Exception as e:
                    logger.error(f"Failed to create tenant user record: {str(e)}")
                    # Don't fail the entire operation if tenant user creation fails
                
                logger.info(f"Approved join request {request_id}, processed user {user_to_add.id}")
                
                # Send notification about approval
                self._send_decision_notification(join_request, "approved", admin_user_id)
                
                # Clean up notifications and reminders
                self._cleanup_notifications_and_reminders(join_request, admin_user_id, request_id, "approved")
                
                return OrganizationJoinResponse(
                    success=True,
                    message="Join request approved successfully. User added to organization."
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
                self._send_decision_notification(join_request, "rejected", admin_user_id)
                
                # Clean up notifications and reminders
                self._cleanup_notifications_and_reminders(join_request, admin_user_id, request_id, "rejected")

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
            from core.models.models_per_tenant import ReminderNotification, Reminder, ReminderStatus, ReminderPriority, RecurrencePattern
            from core.constants.reminders import JOIN_REQUEST_REMINDER_TITLE_PREFIX

            requester_name = f"{join_request.first_name} {join_request.last_name}".strip() if join_request.first_name else join_request.email

            # Get tenant database session
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            tenant_db = SessionLocal_tenant()

            try:
                for admin_user in admin_users:
                    # Create a reminder task for the admin
                    reminder = Reminder(
                        title=f"{JOIN_REQUEST_REMINDER_TITLE_PREFIX}: {requester_name}",
                        description=f"User {requester_name} ({join_request.email}) has requested to join as {join_request.requested_role}.\n\nMessage: {join_request.message or 'No message provided'}",
                        due_date=datetime.now(timezone.utc) + timedelta(days=3),
                        priority=ReminderPriority.HIGH,
                        status=ReminderStatus.PENDING,
                        recurrence_pattern=RecurrencePattern.NONE,
                        assigned_to_id=admin_user.id,
                        created_by_id=admin_user.id,  # System created, attribute to admin to satisfy non-null constraint
                        tags=["admin", "join_request"],
                        extra_metadata={"join_request_id": join_request.id}
                    )
                    tenant_db.add(reminder)
                    tenant_db.flush()  # Get ID

                    # Create in-app notification for the admin
                    notification = ReminderNotification(
                        reminder_id=reminder.id,
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

    def _get_admin_name(self, admin_user_id: int) -> str:
        """Get admin user's full name or fallback to 'Admin'."""
        try:
            admin_user = self.db.query(MasterUser).filter(MasterUser.id == admin_user_id).first()
            return f"{admin_user.first_name} {admin_user.last_name}".strip() if admin_user and admin_user.first_name else "Admin"
        except Exception as e:
            logger.warning(f"Failed to get admin name for user {admin_user_id}: {str(e)}")
            return "Admin"

    def _send_decision_notification(self, join_request: OrganizationJoinRequest, decision: str, admin_user_id: int):
        """Send notification to requester about join request decision."""
        try:
            admin_name = self._get_admin_name(admin_user_id)
            self._notify_requester_of_decision(join_request, decision, admin_name)
        except Exception as e:
            logger.warning(f"Failed to send {decision} notification: {str(e)}")

    def _cleanup_notifications_and_reminders(self, join_request: OrganizationJoinRequest, admin_user_id: int, request_id: int, decision: str):
        """Clean up notifications and reminders for a processed join request."""
        try:
            from core.services.tenant_database_manager import tenant_db_manager
            from core.models.models_per_tenant import ReminderNotification, Reminder, ReminderStatus
            from sqlalchemy import text

            SessionLocal_tenant = tenant_db_manager.get_tenant_session(join_request.tenant_id)
            tenant_db_notif = SessionLocal_tenant()
            try:
                requester_name = f"{join_request.first_name} {join_request.last_name}".strip() if join_request.first_name else join_request.email

                # Find unread notifications about this request
                notifications = tenant_db_notif.query(ReminderNotification).filter(
                    ReminderNotification.notification_type == "join_request",
                    ReminderNotification.is_read == False,
                    ReminderNotification.message.contains(requester_name)
                ).all()

                for n in notifications:
                    n.is_read = True

                # Find and update reminders about this request
                reminders = tenant_db_notif.query(Reminder).filter(
                    Reminder.status == ReminderStatus.PENDING,
                    text("extra_metadata::jsonb @> :metadata")
                ).params(metadata=f'{{"join_request_id": {request_id}}}').all()

                for r in reminders:
                    if decision == "approved":
                        r.status = ReminderStatus.COMPLETED
                        r.completed_at = datetime.now(timezone.utc)
                        r.completed_by_id = admin_user_id
                    else:  # rejected
                        r.status = ReminderStatus.CANCELLED

                if notifications or reminders:
                    tenant_db_notif.commit()
                    action = "completed" if decision == "approved" else "cancelled"
                    logger.info(f"Marked {len(notifications)} notifications read and {len(reminders)} reminders {action} for join request {request_id}")
            finally:
                tenant_db_notif.close()
        except Exception as e:
            logger.warning(f"Failed to cleanup notifications for join request {request_id}: {e}")

    def _get_email_service(self, tenant_id: int) -> Optional[EmailService]:
        """Get configured email service for a tenant."""
        try:
            from core.services.tenant_database_manager import tenant_db_manager
            
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            tenant_db = SessionLocal_tenant()
            
            try:
                email_settings = tenant_db.query(Settings).filter(
                    Settings.key == "email_config"
                ).first()
                
                if not email_settings or not email_settings.value:
                    logger.warning(f"No email configuration found for tenant {tenant_id}")
                    return None
                
                email_config_data = email_settings.value
                
                # Create email provider config
                config = EmailProviderConfig(
                    provider=EmailProvider(email_config_data['provider']),
                    from_email=email_config_data.get('from_email'),
                    from_name=email_config_data.get('from_name'),
                    aws_access_key_id=email_config_data.get('aws_access_key_id'),
                    aws_secret_access_key=email_config_data.get('aws_secret_access_key'),
                    aws_region=email_config_data.get('aws_region'),
                    azure_connection_string=email_config_data.get('azure_connection_string'),
                    mailgun_api_key=email_config_data.get('mailgun_api_key'),
                    mailgun_domain=email_config_data.get('mailgun_domain')
                )
                
                return EmailService(config)
            finally:
                tenant_db.close()
                
        except Exception as e:
            logger.error(f"Failed to initialize email service for tenant {tenant_id}: {str(e)}")
            return None

    def _notify_requester_of_decision(self, join_request: OrganizationJoinRequest, decision: str, admin_name: str):
        """Send email notification to the requester about the decision on their join request."""
        try:
            email_service = self._get_email_service(join_request.tenant_id)
            
            if not email_service:
                logger.warning(f"Email service not configured for tenant {join_request.tenant_id}, skipping email notification")
                return
            
            # Get tenant info for email
            tenant = self.db.query(Tenant).filter(Tenant.id == join_request.tenant_id).first()
            tenant_name = tenant.name if tenant else "the organization"
            
            # Prepare email content based on decision
            requester_name = f"{join_request.first_name} {join_request.last_name}".strip() if join_request.first_name else join_request.email
            
            if decision == "approved":
                subject = f"Your request to join {tenant_name} has been approved"
                html_body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #16a34a;">Request Approved!</h2>
                        <p>Hello {requester_name},</p>
                        <p>Great news! Your request to join <strong>{tenant_name}</strong> has been approved by {admin_name}.</p>
                        <p>You can now log in to your account and start using the system.</p>
                        <p>If you have any questions, please contact your organization administrator.</p>
                        <p>Best regards,<br>{tenant_name}</p>
                    </div>
                </body>
                </html>
                """
                text_body = f"""Hello {requester_name},

Great news! Your request to join {tenant_name} has been approved by {admin_name}.

You can now log in to your account and start using the system.

If you have any questions, please contact your organization administrator.

Best regards,
{tenant_name}
"""
            else:  # rejected
                subject = f"Your request to join {tenant_name}"
                rejection_reason = join_request.rejection_reason or "No specific reason provided."
                html_body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #dc2626;">Request Update</h2>
                        <p>Hello {requester_name},</p>
                        <p>We regret to inform you that your request to join <strong>{tenant_name}</strong> has been declined by {admin_name}.</p>
                        <p><strong>Reason:</strong> {rejection_reason}</p>
                        <p>If you have any questions or would like to discuss this decision, please contact the organization administrator.</p>
                        <p>Best regards,<br>{tenant_name}</p>
                    </div>
                </body>
                </html>
                """
                text_body = f"""Hello {requester_name},

We regret to inform you that your request to join {tenant_name} has been declined by {admin_name}.

Reason: {rejection_reason}

If you have any questions or would like to discuss this decision, please contact the organization administrator.

Best regards,
{tenant_name}
"""
            
            # Get email config for from address
            from_email = email_service.config.from_email or "noreply@invoiceapp.com"
            from_name = email_service.config.from_name or tenant_name
            
            # Create and send email message
            message = EmailMessage(
                to_email=join_request.email,
                to_name=requester_name,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                from_email=from_email,
                from_name=from_name
            )
            
            success = email_service.send_email(message)
            
            if success:
                logger.info(f"Email notification sent to {join_request.email} about {decision} decision")
            else:
                logger.warning(f"Failed to send email notification to {join_request.email}")
                
        except Exception as e:
            logger.error(f"Error sending email notification to requester: {str(e)}")
