from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import logging
import traceback
from datetime import datetime, timezone

from core.models.database import get_db, get_master_db
from core.models.models_per_tenant import Client, Invoice, Settings
from core.models.models import MasterUser, Tenant
from core.routers.payments import Payment
from core.schemas.client import ClientCreate, ClientUpdate, Client as ClientSchema
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer
from core.utils.audit import log_audit_event
from core.constants.error_codes import CLIENT_ALREADY_EXISTS, CLIENT_NOT_FOUND, CLIENT_HAS_INVOICES, FAILED_TO_CREATE_CLIENT, FAILED_TO_UPDATE_CLIENT, FAILED_TO_FETCH_CLIENTS, FAILED_TO_FETCH_CLIENT
from core.services.notification_service import NotificationService
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])

@router.get("/", response_model=List[ClientSchema])
async def read_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    try:
        # Get clients with their total invoice amounts, total paid amounts, and calculate outstanding balance
        # No tenant_id filtering needed since we're in the tenant's database
        clients = db.query(
            Client,
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid'),
            func.coalesce(func.sum(Invoice.amount), 0).label('total_invoiced')
        ).outerjoin(
            Invoice, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Payment.invoice_id == Invoice.id
        ).group_by(
            Client.id
        ).offset(skip).limit(limit).all()

        # Convert to response format
        result = []
        for client, total_paid, total_invoiced in clients:
            # Calculate outstanding balance for pending/unpaid invoices
            pending_invoices = db.query(
                func.coalesce(func.sum(Invoice.amount), 0)
            ).filter(
                Invoice.client_id == client.id,
                Invoice.status.in_(['pending', 'overdue', 'partially_paid'])
            ).scalar()
            
            pending_payments = db.query(
                func.coalesce(func.sum(Payment.amount), 0)
            ).filter(
                Payment.invoice_id.in_(
                    db.query(Invoice.id).filter(
                        Invoice.client_id == client.id,
                        Invoice.status.in_(['pending', 'overdue', 'partially_paid'])
                    )
                )
            ).scalar()
            
            outstanding_balance = float(pending_invoices or 0) - float(pending_payments or 0)
            
            client_dict = {
                "id": client.id,
                "name": client.name,
                "email": client.email,
                "phone": client.phone,
                "address": client.address,
                "company": client.company,
                "balance": client.balance,
                "paid_amount": float(total_paid),
                "outstanding_balance": outstanding_balance,
                "preferred_currency": client.preferred_currency,
                "created_at": client.created_at.isoformat() if client.created_at else None,
                "updated_at": client.updated_at.isoformat() if client.updated_at else None
            }
            result.append(client_dict)

        return result
    except Exception as e:
        logger.error(f"Error in read_clients: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_FETCH_CLIENTS
        )

@router.get("/{client_id}", response_model=ClientSchema)
async def read_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    try:
        # Get client with total paid amount
        # No tenant_id filtering needed since we're in the tenant's database
        client_tuple = db.query(
            Client,
            func.coalesce(func.sum(Payment.amount), 0).label('total_paid')
        ).outerjoin(
            Invoice, Invoice.client_id == Client.id
        ).outerjoin(
            Payment, Payment.invoice_id == Invoice.id
        ).filter(
            Client.id == client_id
        ).group_by(
            Client.id
        ).first()

        if client_tuple is None:
            raise HTTPException(
                status_code=404,
                detail=CLIENT_NOT_FOUND
            )

        client, total_paid = client_tuple
        
        # Calculate outstanding balance for pending/unpaid invoices
        pending_invoices = db.query(
            func.coalesce(func.sum(Invoice.amount), 0)
        ).filter(
            Invoice.client_id == client.id,
            Invoice.status.in_(['pending', 'overdue', 'partially_paid'])
        ).scalar()
        
        pending_payments = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.invoice_id.in_(
                db.query(Invoice.id).filter(
                    Invoice.client_id == client.id,
                    Invoice.status.in_(['pending', 'overdue', 'partially_paid'])
                )
            )
        ).scalar()
        
        outstanding_balance = float(pending_invoices or 0) - float(pending_payments or 0)
        
        client_dict = {
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "phone": client.phone,
            "address": client.address,
            "company": client.company,
            "balance": client.balance,
            "paid_amount": float(total_paid),
            "outstanding_balance": outstanding_balance,
            "preferred_currency": client.preferred_currency,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None
        }
        return client_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in read_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_FETCH_CLIENT
        )

@router.post("/", response_model=ClientSchema, status_code=status.HTTP_201_CREATED)
async def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    # Check if user has permission to create clients
    require_non_viewer(current_user, "create clients")
    
    try:
        logger.info(f"DEBUG: Attempting to create client: name='{client.name}', email='{client.email}'")

        # Check for existing client with same name and email to prevent duplicates
        # Since name and email are encrypted, we need to check all existing clients
        # and compare decrypted values
        # TODO: For better performance with large datasets, consider:
        # 1. Using database triggers for duplicate prevention
        # 2. Maintaining a separate unencrypted index table for lookups
        # 3. Using hash-based lookups with pre-computed hashes
        existing_clients = db.query(Client).all()
        for existing_client in existing_clients:
            if existing_client.name == client.name and existing_client.email == client.email:
                logger.warning(f"Attempted to create duplicate client: name='{client.name}', email='{client.email}'")
                raise HTTPException(
                    status_code=400,
                    detail=CLIENT_ALREADY_EXISTS
                )

        logger.info("DEBUG: No duplicate client found, proceeding with creation")
        
        # Prepare client data
        client_data = client.model_dump()
        
        # If no preferred_currency is provided, use tenant's default currency
        if not client_data.get('preferred_currency') or client_data.get('preferred_currency').strip() == "":
            try:
                # Get tenant's default currency from master database
                master_db = next(get_master_db())
                try:
                    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
                    if tenant and tenant.default_currency:
                        client_data['preferred_currency'] = tenant.default_currency
                    else:
                        client_data['preferred_currency'] = 'USD'  # Fallback
                finally:
                    master_db.close()
            except Exception as e:
                logger.warning(f"Failed to get tenant default currency: {e}")
                client_data['preferred_currency'] = 'USD'  # Fallback
        
        # No tenant_id needed since each tenant has its own database
        db_client = Client(
            **client_data,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(db_client)
        db.commit()
        db.refresh(db_client)
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="client",
            resource_id=str(db_client.id),
            resource_name=db_client.name,
            details=client.model_dump(),
            status="success"
        )
        
        # Send notification if email service is configured
        try:
            email_settings = db.query(Settings).filter(Settings.key == "email_config").first()
            if email_settings and email_settings.value and email_settings.value.get('enabled'):
                email_config_data = email_settings.value
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
                email_service = EmailService(config)
                notification_service = NotificationService(db, email_service)

                # Get tenant name for notification
                master_db = next(get_master_db())
                try:
                    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
                    company_name = tenant.name if tenant else "Invoice Management System"
                finally:
                    master_db.close()

                notification_service.send_operation_notification(
                    event_type="client_created",
                    user_id=current_user.id,
                    resource_type="client",
                    resource_id=str(db_client.id),
                    resource_name=db_client.name,
                    details={
                        "email": db_client.email,
                        "phone": db_client.phone or "N/A",
                        "preferred_currency": db_client.preferred_currency
                    },
                    company_name=company_name
                )
        except Exception as e:
            logger.warning(f"Failed to send client creation notification: {str(e)}")
            # Don't fail the request if notification fails
        
        # Return client data as dict to avoid DetachedInstanceError
        client_dict = {
            "id": db_client.id,
            "name": db_client.name,
            "email": db_client.email,
            "phone": db_client.phone,
            "address": db_client.address,
            "balance": db_client.balance,
            "paid_amount": 0,
            "outstanding_balance": 0,
            "preferred_currency": db_client.preferred_currency,
            "created_at": db_client.created_at.isoformat() if db_client.created_at else None,
            "updated_at": db_client.updated_at.isoformat() if db_client.updated_at else None
        }
        return client_dict
    except HTTPException as e:
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="client",
            resource_id=None,
            resource_name=client.name,
            details=client.model_dump(),
            status="error",
            error_message=str(e.detail) if hasattr(e, 'detail') else str(e)
        )
        raise
    except Exception as e:
        db.rollback()
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="client",
            resource_id=None,
            resource_name=client.name,
            details=client.model_dump(),
            status="error",
            error_message=str(e)
        )
        logger.error(f"Error in create_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_CREATE_CLIENT
        )

@router.put("/{client_id}", response_model=ClientSchema)
async def update_client(
    client_id: int,
    client: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    # Check if user has permission to update clients
    require_non_viewer(current_user, "update clients")

    try:
        # No tenant_id filtering needed since we're in the tenant's database
        db_client = db.query(Client).filter(
            Client.id == client_id
        ).first()
        if db_client is None:
            raise HTTPException(
                status_code=404,
                detail=CLIENT_NOT_FOUND
            )

        update_data = client.model_dump(exclude_unset=True)

        # Check for duplicate client with same name and email (excluding current client)
        if 'name' in update_data and 'email' in update_data:
            # Since name and email are encrypted, we need to check all existing clients
            # and compare decrypted values
            existing_clients = db.query(Client).filter(Client.id != client_id).all()
            for existing_client in existing_clients:
                if existing_client.name == update_data['name'] and existing_client.email == update_data['email']:
                    raise HTTPException(
                        status_code=400,
                        detail=CLIENT_ALREADY_EXISTS
                    )

        # # Update client fields, excluding email
        # if 'email' in update_data:
        #     del update_data['email']  # Remove email from update data

        for field, value in update_data.items():
            setattr(db_client, field, value)
        db_client.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_client)
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="client",
            resource_id=str(db_client.id),
            resource_name=db_client.name,
            details=update_data,
            status="success"
        )
        # Return client data as dict to avoid DetachedInstanceError
        client_dict = {
            "id": db_client.id,
            "name": db_client.name,
            "email": db_client.email,
            "phone": db_client.phone,
            "address": db_client.address,
            "balance": db_client.balance,
            "paid_amount": 0,  # Will be calculated by frontend if needed
            "outstanding_balance": 0,  # Will be calculated by frontend if needed
            "preferred_currency": db_client.preferred_currency,
            "created_at": db_client.created_at.isoformat() if db_client.created_at else None,
            "updated_at": db_client.updated_at.isoformat() if db_client.updated_at else None
        }
        return client_dict
    except HTTPException as e:
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="client",
            resource_id=str(client_id),
            resource_name=None,
            details=client.model_dump(),
            status="error",
            error_message=str(e.detail) if hasattr(e, 'detail') else str(e)
        )
        raise
    except Exception as e:
        db.rollback()
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="client",
            resource_id=str(client_id),
            resource_name=None,
            details=client.dict(),
            status="error",
            error_message=str(e)
        )
        logger.error(f"Error in update_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_UPDATE_CLIENT
        )

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    try:
        # Check if client exists
        # No tenant_id filtering needed since we're in the tenant's database
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if db_client is None:
            raise HTTPException(
                status_code=404,
                detail=CLIENT_NOT_FOUND
            )
        
        # Check if client has associated invoices
        # No tenant_id filtering needed since we're in the tenant's database
        has_invoices = db.query(Invoice).filter(
            Invoice.client_id == client_id,
            Invoice.is_deleted == False
        ).first() is not None
        
        if has_invoices:
            raise HTTPException(
                status_code=400,
                detail=CLIENT_HAS_INVOICES
            )
        
        # Delete the client
        db.delete(db_client)
        db.commit()
        # Audit log for client delete
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE",
            resource_type="client",
            resource_id=str(client_id),
            resource_name=db_client.name,
            details={"message": "Client deleted"},
            status="success"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in delete_client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=FAILED_TO_FETCH_CLIENTS
        ) 