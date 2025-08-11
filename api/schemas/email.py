from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from enum import Enum

class EmailProvider(str, Enum):
    AWS_SES = "aws_ses"
    AZURE_EMAIL = "azure_email"
    MAILGUN = "mailgun"

class EmailConfigBase(BaseModel):
    """Base email configuration"""
    provider: EmailProvider
    from_name: str = Field(..., description="Default sender name")
    from_email: EmailStr = Field(..., description="Default sender email")
    enabled: bool = Field(default=False, description="Whether email service is enabled")

class AWSEmailConfig(EmailConfigBase):
    """AWS SES email configuration"""
    provider: EmailProvider = EmailProvider.AWS_SES
    aws_access_key_id: str = Field(..., description="AWS Access Key ID")
    aws_secret_access_key: str = Field(..., description="AWS Secret Access Key")
    aws_region: str = Field(default="us-east-1", description="AWS Region")

class AzureEmailConfig(EmailConfigBase):
    """Azure Email Services configuration"""
    provider: EmailProvider = EmailProvider.AZURE_EMAIL
    azure_connection_string: str = Field(..., description="Azure Communication Services connection string")

class MailgunEmailConfig(EmailConfigBase):
    """Mailgun email configuration"""
    provider: EmailProvider = EmailProvider.MAILGUN
    mailgun_api_key: str = Field(..., description="Mailgun API Key")
    mailgun_domain: str = Field(..., description="Mailgun Domain")

class EmailConfig(BaseModel):
    """Email configuration container"""
    provider: EmailProvider
    from_name: str
    from_email: EmailStr
    enabled: bool = False
    aws_session_token: Optional[str] = None
    
    # Provider-specific settings
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "us-east-1"
    azure_connection_string: Optional[str] = None
    mailgun_api_key: Optional[str] = None
    mailgun_domain: Optional[str] = None

class EmailTemplateConfig(BaseModel):
    """Email template configuration"""
    invoice_subject_template: str = Field(
        default="Invoice {{ invoice.number }} from {{ company.name }}",
        description="Subject template for invoice emails"
    )
    auto_send_enabled: bool = Field(
        default=False,
        description="Whether to automatically send emails when invoices are created"
    )
    send_copy_to_sender: bool = Field(
        default=False,
        description="Whether to send a copy to the sender"
    )
    include_payment_link: bool = Field(
        default=False,
        description="Whether to include payment links in emails"
    )

class SendInvoiceEmailRequest(BaseModel):
    """Request to send an invoice email"""
    invoice_id: int = Field(..., description="Invoice ID to send")
    to_email: Optional[EmailStr] = Field(None, description="Override recipient email")
    to_name: Optional[str] = Field(None, description="Override recipient name")
    subject: Optional[str] = Field(None, description="Override email subject")
    include_pdf: bool = Field(default=True, description="Whether to include PDF attachment")
    show_discount_in_pdf: bool = Field(default=False, description="Whether to show discount details in the PDF preview")
    cc_emails: Optional[List[EmailStr]] = Field(None, description="CC recipients")
    bcc_emails: Optional[List[EmailStr]] = Field(None, description="BCC recipients")
    custom_message: Optional[str] = Field(None, description="Custom message to include in email")

class EmailTestRequest(BaseModel):
    """Request to test email configuration"""
    test_email: EmailStr = Field(..., description="Email address to send test email to")

class EmailResponse(BaseModel):
    """Email sending response"""
    success: bool = Field(..., description="Whether email was sent successfully")
    message: str = Field(..., description="Response message")
    message_id: Optional[str] = Field(None, description="Email provider message ID")

class EmailConfigValidationResponse(BaseModel):
    """Email configuration validation response"""
    valid: bool = Field(..., description="Whether configuration is valid")
    message: str = Field(..., description="Validation message")
    provider: EmailProvider = Field(..., description="Email provider")

class EmailDeliveryStatus(BaseModel):
    """Email delivery status"""
    invoice_id: int
    recipient_email: str
    status: str  # sent, failed, pending
    sent_at: Optional[str] = None
    error_message: Optional[str] = None
    message_id: Optional[str] = None 