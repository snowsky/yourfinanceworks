#!/usr/bin/env python3
"""
Script to seed default prompt templates for all tenant databases.
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import get_master_db
from core.models.models import Tenant
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default prompt templates
DEFAULT_PROMPT_TEMPLATES = [
    {
        "name": "pdf_invoice_extraction",
        "category": "invoice_processing",
        "description": "Extract invoice information from PDF text for AI processing",
        "template_content": """Extract invoice information from this text and return ONLY valid JSON:

{{
  "date": "YYYY-MM-DD",
  "bills_to": "Client name and email",
  "items": [
    {{
      "description": "Item description", 
      "quantity": 1,
      "price": 0.00,
      "amount": 0.00,
      "discount": 0.0
    }}
  ],
  "total_amount": 0.00,
  "total_discount": 0.0
}}

Invoice text:
{text}

Respond with JSON only:""",
        "template_variables": ["text"],
        "output_format": "json",
        "default_values": {},
        "provider_overrides": {
            "openai": "Extract invoice information from this text and return ONLY valid JSON. Focus on accurate line item extraction and total calculations.",
            "anthropic": "As an expert in invoice analysis, extract structured data from this invoice text with high precision and attention to financial details."
        }
    },
    {
        "name": "invoice_processing",
        "category": "invoice_processing",
        "description": "Extract structured data from invoice documents",
        "template_content": """You are an AI assistant specialized in extracting structured data from invoice documents. 

Please analyze the following invoice text and extract the following information in JSON format:

Required fields:
- invoice_number: The invoice identification number
- invoice_date: Date of the invoice (YYYY-MM-DD format)
- due_date: Payment due date (YYYY-MM-DD format) 
- vendor_name: Name of the vendor/company issuing the invoice
- vendor_address: Full address of the vendor
- vendor_tax_id: Tax ID or VAT number of vendor (if available)
- client_name: Name of the client/customer being billed
- client_address: Address of the client/customer
- line_items: Array of line items with:
  - description: Item description
  - quantity: Quantity ordered
  - unit_price: Price per unit
  - total_price: Total price for this line item
- subtotal: Subtotal before taxes
- tax_amount: Total tax amount
- tax_rate: Tax rate percentage (if specified)
- total_amount: Total amount due
- currency: Currency code (USD, EUR, etc.)
- payment_terms: Payment terms (e.g., "Net 30", "Due on receipt")
- notes: Any additional notes or terms

Invoice text:
{{invoice_text}}

Respond with valid JSON only. If any field cannot be found, use null or empty string.""",
        "template_variables": ["invoice_text"],
        "output_format": "json",
        "default_values": {},
        "provider_overrides": {
            "openai": "You are an AI assistant specialized in extracting structured data from invoice documents. Analyze the invoice and provide detailed, accurate extraction with special attention to line items and tax calculations.",
            "anthropic": "As an expert in invoice data extraction, carefully analyze this document and extract all financial and business information with high precision."
        }
    },
    {
        "name": "receipt_processing",
        "category": "expense_processing", 
        "description": "Extract structured data from receipt documents",
        "template_content": """You are an AI assistant specialized in extracting structured data from receipt documents.

Please analyze the following receipt text and extract the following information in JSON format:

Required fields:
- receipt_number: Receipt identification number (if available)
- transaction_date: Date of transaction (YYYY-MM-DD format)
- transaction_time: Time of transaction (HH:MM format, if available)
- merchant_name: Name of the store/merchant
- merchant_address: Address of the merchant
- merchant_category: Business category (e.g., "Restaurant", "Gas Station", "Grocery")
- line_items: Array of purchased items with:
  - description: Item description
  - quantity: Quantity purchased
  - unit_price: Price per unit
  - total_price: Total price for this item
- subtotal: Subtotal before taxes
- tax_amount: Total tax amount
- tax_rate: Tax rate percentage (if specified)
- tip_amount: Tip amount (if any)
- total_amount: Total amount paid
- currency: Currency code (USD, EUR, etc.)
- payment_method: Payment method (cash, credit card, etc.)
- notes: Any additional information

Receipt text:
{{receipt_text}}

Respond with valid JSON only. If any field cannot be found, use null or empty string.""",
        "template_variables": ["receipt_text"],
        "output_format": "json",
        "default_values": {},
        "provider_overrides": {
            "openai": "You are an AI assistant specialized in extracting structured data from receipt documents. Focus on accurate merchant information and itemized purchases.",
            "anthropic": "As an expert in receipt data extraction, carefully analyze this document and extract all transaction details with special attention to merchant categorization."
        }
    },
    {
        "name": "bank_statement_processing",
        "category": "statement_processing",
        "description": "Extract transaction data from bank statements",
        "template_content": """You are an AI assistant specialized in extracting transaction data from bank statements.

Please analyze the following bank statement text and extract transaction information in JSON format:

Required fields:
- statement_period: Statement period (e.g., "January 2024")
- account_number: Bank account number (masked)
- account_type: Account type (checking, savings, etc.)
- opening_balance: Opening balance
- closing_balance: Closing balance
- transactions: Array of transactions with:
  - transaction_date: Date of transaction (YYYY-MM-DD)
  - description: Transaction description
  - amount: Transaction amount (positive for deposits, negative for withdrawals)
  - balance: Balance after transaction
  - transaction_type: Type (deposit, withdrawal, transfer, fee, etc.)
  - reference_number: Reference number (if available)

Bank statement text:
{{statement_text}}

Respond with valid JSON only. If any field cannot be found, use null or empty string.""",
        "template_variables": ["statement_text"],
        "output_format": "json",
        "default_values": {},
        "provider_overrides": {
            "openai": "You are an AI assistant specialized in bank statement analysis. Focus on accurate transaction categorization and balance calculations.",
            "anthropic": "As an expert in financial document analysis, carefully extract all transaction data with attention to detail and accuracy."
        }
    },
    {
        "name": "expense_categorization",
        "category": "expense_processing",
        "description": "Categorize expenses based on description and merchant",
        "template_content": """You are an AI assistant specialized in expense categorization for business accounting.

Please analyze the following expense information and provide detailed categorization in JSON format:

Required fields:
- primary_category: Main expense category (e.g., "Meals & Entertainment", "Office Supplies", "Travel", "Utilities")
- subcategory: Specific subcategory (e.g., "Client Lunch", "Software", "Airfare", "Electricity")
- is_business_expense: Boolean indicating if this is a legitimate business expense
- is_tax_deductible: Boolean indicating if this expense is tax deductible
- receipt_required: Boolean indicating if a receipt is required for this expense type
- approval_required: Boolean indicating if manager approval is needed
- suggested_notes: Any notes for bookkeeping or compliance

Expense information:
- Description: {{description}}
- Merchant: {{merchant}}
- Amount: {{amount}}
- Date: {{date}}

Respond with valid JSON only.""",
        "template_variables": ["description", "merchant", "amount", "date"],
        "output_format": "json",
        "default_values": {},
        "provider_overrides": {
            "openai": "You are an AI assistant specialized in business expense categorization. Provide accurate tax and compliance guidance.",
            "anthropic": "As an expert in business accounting and expense management, categorize this expense with attention to tax implications and compliance requirements."
        }
    },
    {
        "name": "invoice_line_item_extraction",
        "category": "invoice_processing",
        "description": "Extract detailed line items from invoices with complex formatting",
        "template_content": """You are an AI assistant specialized in extracting detailed line items from complex invoice documents.

Please analyze the following invoice section and extract detailed line item information in JSON format:

Required fields:
- line_items: Array of line items with:
  - item_code: Product/SKU code (if available)
  - description: Detailed item description
  - quantity: Quantity ordered
  - unit_of_measure: Unit of measure (each, hours, kg, etc.)
  - unit_price: Price per unit
  - discount_amount: Discount amount per unit (if any)
  - tax_rate: Tax rate for this item (if specified)
  - total_price: Total price for this line item (quantity × unit_price - discount)
  - notes: Any additional notes for this item

Invoice line items section:
{{line_items_text}}

Respond with valid JSON only. If any field cannot be found, use null or empty string.""",
        "template_variables": ["line_items_text"],
        "output_format": "json",
        "default_values": {},
        "provider_overrides": {
            "openai": "You are an AI assistant specialized in extracting complex line item data from invoices. Pay special attention to quantities, units, and pricing calculations.",
            "anthropic": "As an expert in invoice analysis, extract detailed line item information with high accuracy, including discounts and tax implications."
        }
    }
]

def seed_prompt_templates():
    """Seed default prompt templates for all tenant databases"""
    try:
        # Get master database session
        master_db = next(get_master_db())
        
        # Get all active tenants
        tenants = master_db.query(Tenant).filter(Tenant.is_active == True).all()
        
        logger.info(f"Found {len(tenants)} active tenants")

        for tenant in tenants:
            try:
                # Construct tenant database URL
                tenant_db_url = f"postgresql://postgres:password@postgres-master:5432/tenant_{tenant.id}"
                tenant_engine = create_engine(tenant_db_url)
                
                with tenant_engine.connect() as connection:
                    # Check if prompt_templates table exists
                    result = connection.execute(text("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'prompt_templates'
                    """))
                    
                    if not result.fetchone():
                        logger.warning(f"prompt_templates table does not exist for tenant_{tenant.id}, skipping")
                        continue
                    
                    # Check if templates already exist
                    existing_templates = connection.execute(text("""
                        SELECT name FROM prompt_templates WHERE version = 1
                    """)).fetchall()
                    existing_names = {row[0] for row in existing_templates}
                    
                    templates_to_add = [t for t in DEFAULT_PROMPT_TEMPLATES if t["name"] not in existing_names]
                    
                    if not templates_to_add:
                        logger.info(f"All default templates already exist for tenant_{tenant.id}")
                        continue
                    
                    logger.info(f"Adding {len(templates_to_add)} default templates to tenant_{tenant.id}")
                    
                    # Insert default templates
                    for template in templates_to_add:
                        connection.execute(text("""
                            INSERT INTO prompt_templates (
                                name, category, description, template_content, 
                                template_variables, output_format, default_values, 
                                version, is_active, provider_overrides
                            ) VALUES (
                                :name, :category, :description, :template_content,
                                :template_variables, :output_format, :default_values,
                                1, true, :provider_overrides
                            )
                        """), {
                            'name': template['name'],
                            'category': template['category'],
                            'description': template['description'],
                            'template_content': template['template_content'],
                            'template_variables': template['template_variables'],
                            'output_format': template['output_format'],
                            'default_values': template['default_values'],
                            'provider_overrides': template['provider_overrides']
                        })
                    
                    connection.commit()
                    logger.info(f"Successfully seeded default templates for tenant_{tenant.id}")

                    # Seed review_worker_enabled setting
                    connection.execute(text("""
                        INSERT INTO settings (key, value, category, description, is_public)
                        VALUES ('review_worker_enabled', 'true', 'system', 'Enable background AI review processing', false)
                        ON CONFLICT (key) DO NOTHING
                    """))
                    connection.commit()
                    logger.info(f"Seeded review_worker_enabled setting for tenant_{tenant.id}")
                    
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.id}: {e}")
                continue
        
        logger.info("Prompt templates seeding completed for all tenant databases")
        
    except Exception as e:
        logger.error(f"Error seeding prompt templates: {e}")
        raise

if __name__ == "__main__":
    seed_prompt_templates()