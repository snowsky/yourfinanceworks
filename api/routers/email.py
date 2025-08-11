from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import Dict, Any, List
import logging

from models.database import get_db
from models.models import Tenant, MasterUser
from models.models_per_tenant import Invoice, Client, User, Settings
from services.tenant_database_manager import tenant_db_manager
from models.database import set_tenant_context
from schemas.email import (
    SendInvoiceEmailRequest, EmailResponse, EmailTestRequest,
    EmailConfig, EmailConfigValidationResponse, EmailDeliveryStatus
)
from routers.auth import get_current_user
from services.email_service import EmailService, EmailProviderConfig, EmailProvider
from utils.pdf_generator import generate_invoice_pdf
from constants.error_codes import FAILED_TO_SEND_EMAIL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])

def get_email_service(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
) -> EmailService:
    """Get configured email service for the current tenant"""
    
    try:
        # Get email configuration from settings
        email_settings = db.query(Settings).filter(
            Settings.key == "email_config"
        ).first()
        
        if not email_settings or not email_settings.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email service not configured. Please configure email settings first."
            )
    
        email_config_data = email_settings.value
        
        # Create email provider config
        config = EmailProviderConfig(
            provider=EmailProvider(email_config_data['provider']),
            aws_access_key_id=email_config_data.get('aws_access_key_id'),
            aws_secret_access_key=email_config_data.get('aws_secret_access_key'),
            aws_region=email_config_data.get('aws_region'),
            azure_connection_string=email_config_data.get('azure_connection_string'),
            mailgun_api_key=email_config_data.get('mailgun_api_key'),
            mailgun_domain=email_config_data.get('mailgun_domain')
        )
        
        return EmailService(config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize email service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize email service: {str(e)}"
        )

@router.post("/send-invoice", response_model=EmailResponse)
async def send_invoice_email(
    request: SendInvoiceEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    email_service: EmailService = Depends(get_email_service)
):
    """Send an invoice via email"""
    try:
        # Get invoice
        invoice = db.query(Invoice).options(joinedload(Invoice.items)).filter(
            Invoice.id == request.invoice_id,
            Invoice.tenant_id == current_user.tenant_id
        ).first()
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found"
            )
        
        # Get client
        client = db.query(Client).filter(
            Client.id == invoice.client_id,
            Client.tenant_id == current_user.tenant_id
        ).first()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get company/tenant info
        tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
        
        # Prepare invoice data
        invoice_data = {
            'id': invoice.id,
            'number': invoice.number,
            'date': invoice.created_at.strftime('%Y-%m-%d') if invoice.created_at else '',
            'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else '',
            'amount': float(invoice.amount),
            'subtotal': float(invoice.subtotal) if invoice.subtotal else float(invoice.amount),
            'discount_type': invoice.discount_type,
            'discount_value': float(invoice.discount_value) if invoice.discount_value else 0,
            'paid_amount': 0,  # Calculate from payments if needed
            'status': invoice.status,
            'notes': invoice.notes or '',
            'items': [item.dict() for item in invoice.items] if invoice.items else [] # Ensure items are included
        }
        
        # Prepare client data
        client_data = {
            'id': client.id,
            'name': request.to_name or client.name,
            'email': request.to_email or client.email,
            'phone': client.phone or '',
            'address': client.address or ''
        }
        
        if not client_data['email']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client email not available. Please provide recipient email."
            )
        
        # Prepare company data
        company_data = {
            'name': tenant.name if tenant else 'Your Company',
            'email': tenant.email if tenant else 'noreply@company.com',
            'phone': tenant.phone if tenant else '',
            'address': tenant.address if tenant else '',
            'tax_id': tenant.tax_id if tenant else ''
        }
        
        # Generate PDF if requested
        pdf_content = None
        if request.include_pdf:
            try:
                # Use the request value if provided, otherwise use the invoice's field
                show_discount = request.show_discount_in_pdf if request.show_discount_in_pdf is not None else getattr(invoice, 'show_discount_in_pdf', True)
                pdf_content = generate_invoice_pdf(
                    invoice_data=invoice_data,
                    client_data=client_data,
                    company_data=company_data,
                    items=invoice.items, # Pass items to PDF generator
                    db=db,
                    show_discount=show_discount
                )
            except Exception as e:
                logger.error(f"Failed to generate PDF: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate PDF: {str(e)}"
                )
        
        # Send email
        success = email_service.send_invoice_email(
            invoice_data=invoice_data,
            client_data=client_data,
            company_data=company_data,
            pdf_content=pdf_content
        )
        
        if success:
            logger.info(f"Invoice {invoice.number} sent successfully to {client_data['email']}")
            return EmailResponse(
                success=True,
                message=f"Invoice {invoice.number} sent successfully to {client_data['email']}"
            )
        else:
            return EmailResponse(
                success=False,
                message="Failed to send invoice email. Please check email configuration and try again."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending invoice email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_SEND_EMAIL
        )

@router.post("/test", response_model=EmailResponse)
async def test_email_configuration(
    request: EmailTestRequest,
    email_service: EmailService = Depends(get_email_service)
):
    """Test email configuration by sending a test email"""
    try:
        success = email_service.test_email_connection(request.test_email)
        
        if success:
            return EmailResponse(
                success=True,
                message=f"Test email sent successfully to {request.test_email}"
            )
        else:
            return EmailResponse(
                success=False,
                message="Failed to send test email. Please check your email configuration."
            )
            
    except Exception as e:
        logger.error(f"Email test failed: {str(e)}")
        return EmailResponse(
            success=False,
            message=f"Email test failed: {str(e)}"
        )

@router.post("/config/validate", response_model=EmailConfigValidationResponse)
async def validate_email_configuration(
    config: EmailConfig,
    current_user: User = Depends(get_current_user)
):
    """Validate email configuration without saving it"""
    try:
        # Create email provider config
        provider_config = EmailProviderConfig(
            provider=config.provider,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            aws_region=config.aws_region,
            azure_connection_string=config.azure_connection_string,
            mailgun_api_key=config.mailgun_api_key,
            mailgun_domain=config.mailgun_domain
        )
        
        # Create email service and validate
        email_service = EmailService(provider_config)
        is_valid = email_service.validate_configuration()
        
        return EmailConfigValidationResponse(
            valid=is_valid,
            message="Configuration is valid" if is_valid else "Configuration validation failed",
            provider=config.provider
        )
        
    except Exception as e:
        logger.error(f"Email configuration validation failed: {str(e)}")
        return EmailConfigValidationResponse(
            valid=False,
            message=f"Configuration validation failed: {str(e)}",
            provider=config.provider
        )

@router.get("/config", response_model=EmailConfig)
async def get_email_configuration(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get current email configuration"""
    
    try:
        # Get email configuration from settings
        email_settings = db.query(Settings).filter(
            Settings.key == "email_config"
        ).first()
        
        if not email_settings or not email_settings.value:
            # Return default configuration
            return EmailConfig(
                provider="aws_ses",
                enabled=False,
                from_name="Your Company",
                from_email="noreply@example.com"
            )

        config_data = email_settings.value or {}

        # Ensure all required fields are included with sensible defaults
        return EmailConfig(
            provider=config_data.get('provider', 'aws_ses'),
            from_name=config_data.get('from_name', 'Your Company'),
            from_email=config_data.get('from_email', 'noreply@example.com'),
            enabled=bool(config_data.get('enabled', False)),
            aws_access_key_id=config_data.get('aws_access_key_id'),
            aws_secret_access_key=config_data.get('aws_secret_access_key'),
            aws_region=config_data.get('aws_region'),
            azure_connection_string=config_data.get('azure_connection_string'),
            mailgun_api_key=config_data.get('mailgun_api_key'),
            mailgun_domain=config_data.get('mailgun_domain')
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get email configuration: {str(e)}"
        )

@router.put("/config", response_model=EmailConfig)
async def update_email_configuration(
    config: EmailConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update email configuration"""
    try:
        # Validate configuration first
        provider_config = EmailProviderConfig(
            provider=config.provider,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            aws_region=config.aws_region,
            azure_connection_string=config.azure_connection_string,
            mailgun_api_key=config.mailgun_api_key,
            mailgun_domain=config.mailgun_domain
        )
        
        if config.enabled:
            email_service = EmailService(provider_config)
            if not email_service.validate_configuration():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email configuration validation failed"
                )
        
        # Save or update configuration
        email_settings = db.query(Settings).filter(
            Settings.key == "email_config"
        ).first()
        
        config_data = config.dict()
        
        if email_settings:
            email_settings.value = config_data
        else:
            email_settings = Settings(
                key="email_config",
                value=config_data
            )
            db.add(email_settings)
        
        db.commit()
        db.refresh(email_settings)
        
        logger.info(f"Email configuration updated for tenant {current_user.tenant_id}")
        return EmailConfig(**email_settings.value)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update email configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update email configuration: {str(e)}"
        )

@router.delete("/config")
async def delete_email_configuration(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete email configuration"""
    try:
        email_settings = db.query(Settings).filter(
            Settings.key == "email_config"
        ).first()
        
        if email_settings:
            db.delete(email_settings)
            db.commit()
            logger.info(f"Email configuration deleted for tenant {current_user.tenant_id}")
        
        return {"message": "Email configuration deleted successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete email configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete email configuration: {str(e)}"
        ) 