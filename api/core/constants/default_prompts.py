
import json

DEFAULT_PROMPT_TEMPLATES = [
    {
        "name": "pdf_invoice_extraction",
        "category": "invoice_processing",
        "description": "Extract invoice information from PDF text for AI processing",
        "template_content": """Extract invoice information from this text and return ONLY valid JSON:

{
  "date": "YYYY-MM-DD",
  "bills_to": "Client name and email",
  "items": [
    {
      "description": "Item description", 
      "quantity": 1,
      "price": 0.00,
      "amount": 0.00,
      "discount": 0.0
    }
  ],
  "total_amount": 0.00,
  "total_discount": 0.0
}

Invoice text:
{{text}}

Respond with JSON only:""",
        "template_variables": ["text"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {
            "openai": "Extract invoice information from this text and return ONLY valid JSON. Focus on accurate line item extraction and total calculations.",
            "anthropic": "As an expert in invoice analysis, extract structured data from this invoice text with high precision and attention to financial details."
        }
    },
    {
        "name": "ocr_data_conversion",
        "category": "ocr",
        "description": "Convert raw OCR output to structured JSON",
        "template_content": """You are a data extraction expert. The following is OCR output from a receipt or invoice in various formats (markdown, text, etc.). Convert it to a compact JSON object with these keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, notes, receipt_timestamp (YYYY-MM-DD HH:MM:SS if available). For receipt_timestamp, use the exact time from the receipt if visible. If a field is unknown or not present, set it to null. Return ONLY the JSON object, no markdown, no explanations.

OCR Output:
{{raw_content}}""",
        "template_variables": ["raw_content"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {
            "openai": "You are a data extraction expert. Convert this OCR output to clean, compact JSON.",
            "anthropic": "As a data extraction specialist, analyze this OCR text and structure it into the requested JSON format."
        }
    },
    {
        "name": "email_expense_classification",
        "category": "email_processing",
        "description": "Classify if email contains receipts, invoices, or expenses",
        "template_content": """You are an AI assistant specialized in identifying expense-related emails.

Please analyze this email and determine if it contains a receipt, invoice, expense, or purchase confirmation.

Email Details:
- Subject: {{subject}}
- From: {{sender}}
- Has Attachments: {{has_attachments}}

Email Body Preview:
{{body}}

Common expense email patterns:
- Receipt from stores/restaurants (e.g., "Your receipt from...", "Thank you for your purchase")
- Invoice notifications (e.g., "Invoice #...", "Payment confirmation")
- Subscription/service charges (e.g., "Your monthly bill", "Payment processed")
- Delivery/ride receipts (e.g., Uber, DoorDash, Amazon)
- Utility bills, insurance payments, etc.

NOT expense emails:
- Marketing/promotional emails
- Newsletters
- Account notifications (password reset, security alerts)
- Social media notifications
- General correspondence

Respond with ONLY valid JSON in this exact format:
{
  "is_expense": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation (max 100 chars)"
}""",
        "template_variables": ["subject", "body", "sender", "has_attachments"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {
            "openai": "You are an AI assistant specialized in identifying expense-related emails.",
            "anthropic": "As an expert in email analysis, determine if this email contains financial transactions or expense-related content."
        }
    },
    {
        "name": "invoice_data_extraction",
        "category": "invoice_processing",
        "description": "Extract structured invoice data from documents",
        "template_content": """You are an invoice data extraction AI. Extract key invoice fields and respond ONLY with compact JSON.

Required keys: invoice_number, invoice_date (YYYY-MM-DD), due_date (YYYY-MM-DD), 
vendor_name, vendor_address, client_name, client_address, 
subtotal, tax_amount, tax_rate, total_amount, currency, 
line_items (array with description, quantity, unit_price, total), 
payment_terms, notes.

If a field is unknown, set it to null. Do not include any prose.

Document path: {{file_path}}""",
        "template_variables": ["file_path"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {
            "openai": "You are an invoice data extraction AI. Extract key invoice fields and respond ONLY with compact JSON.",
            "anthropic": "As an expert in invoice analysis, extract all relevant invoice data with high precision and attention to financial details."
        }
    },
    {
        "name": "invoice_classification",
        "category": "invoice_processing",
        "description": "Classify invoice documents by type and complexity",
        "template_content": """Analyze this invoice document and classify it. Respond ONLY with JSON.

Required keys: document_type (invoice/receipt/bill/statement), 
invoice_type (service/product/mixed), complexity (simple/standard/complex), 
language, currency_detected, has_line_items (boolean), 
estimated_processing_difficulty (low/medium/high).

Do not include any prose.

Document path: {{file_path}}""",
        "template_variables": ["file_path"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {
            "openai": "Analyze this invoice document and classify it. Respond ONLY with JSON.",
            "anthropic": "As an expert in document analysis, classify this invoice document with high precision."
        }
    },
  {
    "name": "bank_transaction_extraction",
    "category": "bank_processing",
    "description": "Extract bank transactions from statement text",
    "template_content": """You are a financial data extraction expert. Your task is to extract ALL bank transactions from the text below.

RULES:
1. Look for dates, descriptions, and amounts.
2. Identify the transaction type:
   - 'debit': Money leaving the account (Withdrawals, Payments, Transfers Out, etc.).
   - 'credit': Money entering the account (Deposits, Salary, Transfers In, Interest, etc.).
3. Use context such as column headers (Withdrawal/Debit vs Deposit/Credit) or keywords in the description to determine the type.
4. Normalize the 'amount':
   - For 'debit' transactions, the amount MUST BE NEGATIVE (e.g., -45.67).
   - For 'credit' transactions, the amount MUST BE POSITIVE (e.g., 2500.00).
   - Ignore existing signs or parentheses if they contradict the identified transaction type.
5. Convert dates to YYYY-MM-DD format.
6. Extract merchant names or transaction descriptions clearly.
7. Only extract actual transactions, not headers, sub-totals, or account summaries.

STEP-BY-STEP PROCESS:
1. Scan the ENTIRE text to identify all transaction entries.
2. For each transaction, extract: date, description, amount, transaction_type, balance (if available).
3. Validate that you found ALL transactions.
4. Return a complete JSON array with ALL transactions.

TEXT:
{{text}}

Return ONLY a valid JSON array. Each transaction must have these fields:
- date (string, YYYY-MM-DD format, REQUIRED)
- description (string, merchant/vendor name, REQUIRED)
- amount (number, negative for debits, positive for credits, REQUIRED)
- transaction_type (string, "debit" or "credit", REQUIRED)
- balance (number, account balance after transaction, OPTIONAL)

Example format:
[
  {"date": "2024-01-15", "description": "WALMART", "amount": -45.67, "transaction_type": "debit", "balance": 1234.56},
  {"date": "2024-01-16", "description": "ABC CORP SALARY", "amount": 2500.00, "transaction_type": "credit", "balance": 3734.56}
]

JSON:""",
        "template_variables": ["text"],
        "output_format": "json",
        "default_values": {},
        "version": 2,
        "is_active": True,
        "provider_overrides": {
            "openai": "You are a financial data extraction expert. Extract ALL bank transactions from the text. Be thorough and extract every single transaction.",
            "anthropic": "As an expert in financial data analysis, meticulously extract ALL transactions with high precision. Do not skip any transactions."
        }
    },
    {
        "name": "forensic_auditor_phantom_vendor",
        "category": "fraud_detection",
        "description": "Analyze vendor name to identify potential phantom vendors used for fraud",
        "template_content": """You are a Senior Forensic Auditor with 20 years of experience in fraud prevention. 
Your task is to analyze a vendor name and determine if it has characteristics of a "Phantom Vendor" (a shell company or fictitious entity created to embezzle funds).

Vendor Name: "{{vendor_name}}"

Analyze for:
1. Typos of well-known brands (e.g., "Amazn" vs "Amazon")
2. Generic or suspicious names (e.g., "Consulting Services LLC", "Miscellaneous Supply")
3. Fictitious patterns (e.g., "ABC 123 Corp")
4. Names that attempt to sound official but are vague

Respond with ONLY valid JSON in this format:
{
  "is_phantom": boolean,
  "risk_score": 0-100,
  "reasoning": "Detailed forensic explanation",
  "risk_level": "low/medium/high"
}""",
        "template_variables": ["vendor_name"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {}
    },
    {
        "name": "forensic_auditor_description_mismatch",
        "category": "fraud_detection",
        "description": "Analyze transaction details for discrepancies between vendor and description",
        "template_content": """You are a Senior Forensic Auditor specializing in corporate embezzlement. 
Analyze the following transaction for a "Description Mismatch" anomaly, where the description of items purchased doesn't align with the vendor's primary business.

Transaction Details:
- Vendor: {{vendor}}
- Category: {{category}}
- Description/Notes: {{description}}

Identify:
1. Semantic mismatch (e.g., Buying "Luxury Watch" from "Standard Office Supplies")
2. Unusual items for the business type
3. Vague descriptions that might hide unauthorized personal purchases

Respond with ONLY valid JSON in this format:
{
  "is_mismatch": boolean,
  "risk_score": 0-100,
  "reasoning": "Detailed forensic explanation",
  "risk_level": "low/medium/high"
}""",
        "template_variables": ["vendor", "category", "description"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {}
    },
    {
        "name": "forensic_auditor_attachment",
        "category": "fraud_detection",
        "description": "Analyze document attachments for evidence of tampering, suspicious formatting, or digital alterations.",
        "template_content": """You are a Senior Forensic Document Examiner. 
Analyze the provided image(s) of a financial document (receipt, invoice, or statement) for any signs of fraud or manipulation.

Focus on:
1. **Digital Alterations**: Inconsistent fonts, misaligned text, or "photoshopped" elements (e.g., amount or date look different from the rest of the text).
2. **Formatting Anomalies**: Non-standard layouts from supposedly reputable vendors.
3. **Inconsistencies**: Discontinuities in shadows, paper texture, or ink density around critical fields.
4. **Data Verification**: Does the text in the image match the metadata provided?
   - Vendor Context: {{vendor}}
   - Stated Amount: {{amount}}

Respond with ONLY valid JSON in this format:
{
  "is_tampered": boolean,
  "risk_score": 0-100,
  "reasoning": "Detailed forensic explanation of findings",
  "risk_level": "low/medium/high",
  "detected_anomalies": ["list", "of", "specific", "observations"]
}""",
        "template_variables": ["vendor", "amount"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {}
    },
    {
        "name": "invoice_review_extraction",
        "category": "invoice_processing",
        "description": "Premium reviewer prompt for high-precision invoice data extraction",
        "template_content": """You are a Senior Financial Auditor and Invoice Specialist. Your task is to extract data from this invoice with 100% precision for a secondary review check.

Instructions:
1. Scan the document twice to ensure no line items are missed.
2. Meticulously verify that the sum of line items matches the subtotal and total amount.
3. Pay close attention to tax rates and amounts - ensure they are mathematically consistent.
4. Extract vendor and client details exactly as they appear.
5. If any data is ambiguous, mark it as null rather than guessing.

Required JSON format:
{
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "vendor_name": "string",
  "vendor_address": "string",
  "client_name": "string",
  "client_address": "string",
  "subtotal": 0.00,
  "tax_amount": 0.00,
  "tax_rate": 0.00,
  "total_amount": 0.00,
  "currency": "string",
  "line_items": [
    {
      "description": "string",
      "quantity": 0,
      "unit_price": 0.00,
      "total": 0.00
    }
  ],
  "payment_terms": "string",
  "notes": "string"
}

Invoice text:
{{text}}

Return ONLY valid JSON:""",
        "template_variables": ["text"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {
            "openai": "You are a Senior Financial Auditor. Extract invoice data with absolute precision for a forensic review.",
            "anthropic": "As an expert forensic accountant, extract every detail from this invoice text. Double-check all mathematical calculations and line item totals."
        }
    },
    {
        "name": "expense_review_extraction",
        "category": "ocr",
        "description": "Detailed reviewer prompt for expense/receipt re-extraction from OCR data",
        "template_content": """You are a Professional Expense Auditor performing high-scrutiny re-extraction from OCR data.

CRITICAL INSTRUCTIONS:
1. Extract the EXACT vendor name from the data. If unclear or missing, return null. NEVER guess or hallucinate brand names (e.g. 'Starbucks', 'Walmart') if not explicitly present in the OCR output.
2. Extract the exact date and time if present.
3. Strictly separate subtotal, tax amounts, and final total.
4. Identify expense category with high confidence.
5. Note any discrepancies or unusual patterns.

OCR Output:
{{raw_content}}

Return ONLY valid JSON with these exact keys:
{
  "amount": <number or null>,
  "currency": "<3-letter code or null>",
  "expense_date": "<YYYY-MM-DD or null>",
  "category": "<category or null>",
  "vendor": "<exact vendor name or null>",
  "tax_rate": <number or null>,
  "tax_amount": <number or null>,
  "total_amount": <number or null>,
  "payment_method": "<method or null>",
  "reference_number": "<reference or null>",
  "notes": "<notes or null>"
}

If a field is not present in the OCR output, set it to null. Return ONLY the JSON object.""",
        "template_variables": ["raw_content"],
        "output_format": "json",
        "default_values": {},
        "version": 4,
        "is_active": True,
        "provider_overrides": {
            "openai": "You are an Expense Auditor. Re-extract receipt data with meticulous attention to subtotals and taxes. NEVER hallucinate vendor names - only extract what is clearly present in the OCR data.",
            "anthropic": "As a financial compliance specialist, re-extract data from this OCR output with absolute precision. Verify vendor names are exactly as shown - do not guess or infer brand names."
        }
    },
    {
        "name": "bank_statement_review_extraction",
        "category": "bank_processing",
        "description": "High-fidelity prompt for bank statement transaction review",
        "template_content": """You are a Bank Reconciliation Specialist. Your task is to perform an exhaustive extraction of ALL transactions from this bank statement for a verification audit.

RULES:
1. Extract EVERY SINGLE transaction. Compare the count against summary totals if provided.
2. Identify the transaction type:
   - 'debit': Money leaving the account (Withdrawals, Payments, Transfers Out, etc.).
   - 'credit': Money entering the account (Deposits, Salary, Transfers In, Interest, etc.).
3. Use context such as column headers (Withdrawal/Debit vs Deposit/Credit) or keywords in the description to determine the type.
4. Normalize the 'amount':
   - For 'debit' transactions, the amount MUST BE NEGATIVE (e.g., -45.67).
   - For 'credit' transactions, the amount MUST BE POSITIVE (e.g., 2500.00).
   - Ignore existing signs or parentheses if they contradict the identified transaction type.
5. Convert ALL dates to YYYY-MM-DD format.
6. Clean the merchant/vendor names by removing noise from the strings.

Required JSON format:
{
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "description": "Clean Merchant Name",
      "amount": 0.00,
      "transaction_type": "debit/credit",
      "balance": 0.00
    }
  ]
}

Statement Text:
{{text}}

Return ONLY valid JSON:""",
        "template_variables": ["text"],
        "output_format": "json",
        "default_values": {},
        "version": 2,
        "is_active": True,
        "provider_overrides": {
            "openai": "You are a Bank Reconciliation Specialist. Extract every transaction with high fidelity. Ensure all amounts are correctly signed based on context.",
            "anthropic": "As an expert in banking data analysis, meticulously extract all transaction entries. Identify transaction types from context and ensure correct negative/positive signs for amounts."
        }
    },
    {
        "name": "raw_text_extraction",
        "category": "ocr",
        "description": "Extract all text from a document image accurately without structured JSON constraints",
        "template_content": """You are a document extraction expert. Extract all text from this image exactly as it appears.
Include vendor names, dates, amounts, line items, and any handwritten notes.
Preserve the layout as much as possible using text/markdown.
Return ONLY the extracted text, no explanations.""",
        "template_variables": [],
        "output_format": "text",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {
            "openai": "Extract all text from this document image accurately. Preserve layout and details.",
            "anthropic": "As a document specialist, transcribe all text from this image with high fidelity, including fine print and peripheral data."
        }
    },
]
