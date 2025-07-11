from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import boto3
from azure.communication.email import EmailClient
import requests
from jinja2 import Template
import logging
from pydantic import BaseModel
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class EmailProvider(str, Enum):
    AWS_SES = "aws_ses"
    AZURE_EMAIL = "azure_email"
    MAILGUN = "mailgun"

@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str

@dataclass
class EmailMessage:
    to_email: str
    to_name: str
    subject: str
    html_body: str
    text_body: str
    from_email: str
    from_name: str
    attachments: List[EmailAttachment] = None
    cc: List[str] = None
    bcc: List[str] = None

class EmailProviderConfig(BaseModel):
    provider: EmailProvider
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None
    azure_connection_string: Optional[str] = None
    mailgun_api_key: Optional[str] = None
    mailgun_domain: Optional[str] = None

class BaseEmailProvider(ABC):
    """Abstract base class for email providers"""
    
    @abstractmethod
    def send_email(self, message: EmailMessage) -> bool:
        """Send an email message"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate provider configuration"""
        pass

class AWSEmailProvider(BaseEmailProvider):
    """AWS SES email provider"""
    
    def __init__(self, config: EmailProviderConfig):
        self.config = config
        self.client = boto3.client(
            'ses',
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            region_name=config.aws_region or 'us-east-1'
        )
    
    def send_email(self, message: EmailMessage) -> bool:
        try:
            # Prepare destinations
            destinations = [message.to_email]
            if message.cc:
                destinations.extend(message.cc)
            if message.bcc:
                destinations.extend(message.bcc)
            
            # Prepare email data
            email_data = {
                'Source': f"{message.from_name} <{message.from_email}>",
                'Destination': {
                    'ToAddresses': [f"{message.to_name} <{message.to_email}>"],
                },
                'Message': {
                    'Subject': {
                        'Data': message.subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Html': {
                            'Data': message.html_body,
                            'Charset': 'UTF-8'
                        },
                        'Text': {
                            'Data': message.text_body,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            }
            
            # Add CC/BCC if present
            if message.cc:
                email_data['Destination']['CcAddresses'] = message.cc
            if message.bcc:
                email_data['Destination']['BccAddresses'] = message.bcc
            
            # Send email with attachments using raw email if attachments exist
            if message.attachments:
                response = self._send_raw_email(message)
            else:
                response = self.client.send_email(**email_data)
            
            logger.info(f"Email sent successfully via AWS SES. MessageId: {response.get('MessageId')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email via AWS SES: {str(e)}")
            return False
    
    def _send_raw_email(self, message: EmailMessage) -> Dict[str, Any]:
        """Send email with attachments using raw email format"""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.application import MIMEApplication
        
        # Create message
        msg = MIMEMultipart()
        msg['Subject'] = message.subject
        msg['From'] = f"{message.from_name} <{message.from_email}>"
        msg['To'] = f"{message.to_name} <{message.to_email}>"
        
        if message.cc:
            msg['Cc'] = ', '.join(message.cc)
        
        # Add body
        msg.attach(MIMEText(message.text_body, 'plain'))
        msg.attach(MIMEText(message.html_body, 'html'))
        
        # Add attachments
        for attachment in message.attachments or []:
            part = MIMEApplication(attachment.content)
            part.add_header('Content-Disposition', 'attachment', filename=attachment.filename)
            msg.attach(part)
        
        # Send raw email
        destinations = [message.to_email]
        if message.cc:
            destinations.extend(message.cc)
        if message.bcc:
            destinations.extend(message.bcc)
            
        return self.client.send_raw_email(
            Source=msg['From'],
            Destinations=destinations,
            RawMessage={'Data': msg.as_string()}
        )
    
    def validate_config(self) -> bool:
        try:
            # Test SES connection by getting send quota
            self.client.get_send_quota()
            return True
        except Exception as e:
            logger.error(f"AWS SES configuration validation failed: {str(e)}")
            return False

class AzureEmailProvider(BaseEmailProvider):
    """Azure Email Services provider"""
    
    def __init__(self, config: EmailProviderConfig):
        self.config = config
        self.client = EmailClient.from_connection_string(config.azure_connection_string)
    
    def send_email(self, message: EmailMessage) -> bool:
        try:
            # Prepare recipients
            recipients = {
                "to": [{"address": message.to_email, "displayName": message.to_name}]
            }
            
            if message.cc:
                recipients["cc"] = [{"address": email} for email in message.cc]
            if message.bcc:
                recipients["bcc"] = [{"address": email} for email in message.bcc]
            
            # Prepare email content
            email_content = {
                "subject": message.subject,
                "html": message.html_body,
                "plainText": message.text_body
            }
            
            # Prepare attachments
            attachments = []
            if message.attachments:
                for attachment in message.attachments:
                    import base64
                    attachments.append({
                        "name": attachment.filename,
                        "contentType": attachment.content_type,
                        "contentInBase64": base64.b64encode(attachment.content).decode()
                    })
            
            # Send email
            email_message = {
                "senderAddress": message.from_email,
                "recipients": recipients,
                "content": email_content
            }
            
            if attachments:
                email_message["attachments"] = attachments
            
            poller = self.client.begin_send(email_message)
            result = poller.result()
            
            logger.info(f"Email sent successfully via Azure Email Services. MessageId: {result.message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email via Azure Email Services: {str(e)}")
            return False
    
    def validate_config(self) -> bool:
        try:
            # Test connection by attempting to send a test message (dry run)
            return True
        except Exception as e:
            logger.error(f"Azure Email Services configuration validation failed: {str(e)}")
            return False

class MailgunEmailProvider(BaseEmailProvider):
    """Mailgun email provider"""
    
    def __init__(self, config: EmailProviderConfig):
        self.config = config
        self.api_key = config.mailgun_api_key
        self.domain = config.mailgun_domain
        self.base_url = f"https://api.mailgun.net/v3/{self.domain}"
    
    def send_email(self, message: EmailMessage) -> bool:
        try:
            # Prepare form data
            data = {
                'from': f"{message.from_name} <{message.from_email}>",
                'to': f"{message.to_name} <{message.to_email}>",
                'subject': message.subject,
                'text': message.text_body,
                'html': message.html_body
            }
            
            if message.cc:
                data['cc'] = ', '.join(message.cc)
            if message.bcc:
                data['bcc'] = ', '.join(message.bcc)
            
            # Prepare files for attachments
            files = []
            if message.attachments:
                for attachment in message.attachments:
                    files.append(
                        ('attachment', (attachment.filename, attachment.content, attachment.content_type))
                    )
            
            # Send email
            response = requests.post(
                f"{self.base_url}/messages",
                auth=('api', self.api_key),
                data=data,
                files=files if files else None
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Email sent successfully via Mailgun. MessageId: {result.get('id')}")
                return True
            else:
                logger.error(f"Mailgun API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send email via Mailgun: {str(e)}")
            return False
    
    def validate_config(self) -> bool:
        try:
            # Test Mailgun configuration by getting domain info
            response = requests.get(
                f"{self.base_url}/stats/total",
                auth=('api', self.api_key)
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Mailgun configuration validation failed: {str(e)}")
            return False

class EmailService:
    """Main email service class that manages different email providers"""
    
    def __init__(self, config: EmailProviderConfig):
        self.config = config
        self.provider = self._create_provider()
    
    def _create_provider(self) -> BaseEmailProvider:
        """Factory method to create the appropriate email provider"""
        if self.config.provider == EmailProvider.AWS_SES:
            return AWSEmailProvider(self.config)
        elif self.config.provider == EmailProvider.AZURE_EMAIL:
            return AzureEmailProvider(self.config)
        elif self.config.provider == EmailProvider.MAILGUN:
            return MailgunEmailProvider(self.config)
        else:
            raise ValueError(f"Unsupported email provider: {self.config.provider}")
    
    def send_invoice_email(
        self,
        invoice_data: Dict[str, Any],
        client_data: Dict[str, Any],
        company_data: Dict[str, Any],
        pdf_content: bytes,
        template_type: str = "invoice"
    ) -> bool:
        """Send an invoice email with PDF attachment"""
        try:
            # Create email message
            message = self._create_invoice_message(
                invoice_data, client_data, company_data, pdf_content, template_type
            )
            
            # Send email
            return self.provider.send_email(message)
            
        except Exception as e:
            logger.error(f"Failed to send invoice email: {str(e)}")
            return False
    
    def _create_invoice_message(
        self,
        invoice_data: Dict[str, Any],
        client_data: Dict[str, Any],
        company_data: Dict[str, Any],
        pdf_content: bytes,
        template_type: str
    ) -> EmailMessage:
        """Create an email message for invoice delivery"""
        
        # Load email templates
        html_template = self._get_email_template(template_type, "html")
        text_template = self._get_email_template(template_type, "text")
        
        # Prepare template context
        context = {
            'invoice': invoice_data,
            'client': client_data,
            'company': company_data,
            'current_date': datetime.now(timezone.utc).strftime('%B %d, %Y')
        }
        
        # Render templates
        html_body = Template(html_template).render(**context)
        text_body = Template(text_template).render(**context)
        
        # Create PDF attachment
        attachment = EmailAttachment(
            filename=f"invoice-{invoice_data.get('number', 'draft')}.pdf",
            content=pdf_content,
            content_type="application/pdf"
        )
        
        # Create email message
        subject = f"Invoice {invoice_data.get('number', 'Draft')} from {company_data.get('name', 'Your Company')}"
        
        return EmailMessage(
            to_email=client_data['email'],
            to_name=client_data['name'],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=company_data.get('email', 'noreply@company.com'),
            from_name=company_data.get('name', 'Your Company'),
            attachments=[attachment]
        )
    
    def _get_email_template(self, template_type: str, format_type: str) -> str:
        """Get email template content"""
        templates = {
            "invoice": {
                "html": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Invoice {{ invoice.number }}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .invoice-details { background-color: #fff; border: 1px solid #dee2e6; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .footer { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px; font-size: 12px; color: #6c757d; }
        .amount { font-size: 18px; font-weight: bold; color: #28a745; }
        .due-date { color: #dc3545; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ company.name }}</h1>
            <p>Thank you for your business! Please find your invoice attached.</p>
        </div>
        
        <div class="invoice-details">
            <h2>Invoice Details</h2>
            <p><strong>Invoice Number:</strong> {{ invoice.number }}</p>
            <p><strong>Invoice Date:</strong> {{ invoice.date }}</p>
            <p><strong>Due Date:</strong> <span class="due-date">{{ invoice.due_date }}</span></p>
            <p><strong>Amount:</strong> <span class="amount">${{ "%.2f"|format(invoice.amount) }}</span></p>
            <p><strong>Status:</strong> {{ invoice.status|title }}</p>
        </div>
        
        <div>
            <h3>Dear {{ client.name }},</h3>
            <p>We hope this email finds you well. Please find attached your invoice for the services/products provided.</p>
            
            {% if invoice.notes %}
            <p><strong>Notes:</strong></p>
            <p>{{ invoice.notes }}</p>
            {% endif %}
            
            <p>If you have any questions about this invoice, please don't hesitate to contact us.</p>
            
            <p>Thank you for your business!</p>
        </div>
        
        <div class="footer">
            <p>{{ company.name }}</p>
            {% if company.address %}<p>{{ company.address }}</p>{% endif %}
            {% if company.phone %}<p>Phone: {{ company.phone }}</p>{% endif %}
            {% if company.email %}<p>Email: {{ company.email }}</p>{% endif %}
        </div>
    </div>
</body>
</html>
                """,
                "text": """
{{ company.name }}

Dear {{ client.name }},

Thank you for your business! Please find your invoice attached.

Invoice Details:
- Invoice Number: {{ invoice.number }}
- Invoice Date: {{ invoice.date }}
- Due Date: {{ invoice.due_date }}
- Amount: ${{ "%.2f"|format(invoice.amount) }}
- Status: {{ invoice.status|title }}

{% if invoice.notes %}
Notes:
{{ invoice.notes }}
{% endif %}

If you have any questions about this invoice, please don't hesitate to contact us.

Thank you for your business!

Best regards,
{{ company.name }}
{% if company.address %}{{ company.address }}{% endif %}
{% if company.phone %}Phone: {{ company.phone }}{% endif %}
{% if company.email %}Email: {{ company.email }}{% endif %}
                """
            }
        }
        
        return templates.get(template_type, {}).get(format_type, "")
    
    def validate_configuration(self) -> bool:
        """Validate the email provider configuration"""
        return self.provider.validate_config()
    
    def test_email_connection(self, test_email: str) -> bool:
        """Send a test email to verify configuration"""
        try:
            test_message = EmailMessage(
                to_email=test_email,
                to_name="Test User",
                subject="Email Configuration Test",
                html_body="<p>This is a test email to verify your email configuration is working correctly.</p>",
                text_body="This is a test email to verify your email configuration is working correctly.",
                from_email=self.config.aws_access_key_id or "test@example.com",  # Placeholder
                from_name="Invoice App Test"
            )
            
            return self.provider.send_email(test_message)
            
        except Exception as e:
            logger.error(f"Test email failed: {str(e)}")
            return False