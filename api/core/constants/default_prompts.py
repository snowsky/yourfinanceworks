
import json

BANK_TRANSACTION_EXTRACTION_PROMPT = """You are a financial data extraction expert. Your task is to extract ALL bank transactions from the text below.

CONTEXT:
This is a statement for a **{{card_type}}** card/account.
- If 'auto', you must first determine if this is a Credit Card or a Debit/Checking account statement based on the text.
- If it is a Credit Card, follow 'credit' rules below.
- Otherwise, follow 'debit' rules.

RULES:
1. Look for dates, descriptions, and amounts.
2. Identify the transaction type:
   - 'debit': Money leaving the account (Withdrawals, Payments, Transfers Out, etc.).
   - 'credit': Money entering the account (Deposits, Salary, Transfers In, Interest, etc.).
3. Use context such as column headers (Withdrawal/Debit vs Deposit/Credit) or keywords in the description to determine the type.
4. Normalize the 'amount' based on the CARD TYPE:
   - **For DEBIT cards**:
     - 'debit' transactions (money out) MUST BE NEGATIVE (e.g., -45.67).
     - 'credit' transactions (money in) MUST BE POSITIVE (e.g., 2500.00).
   - **For CREDIT cards**:
     - 'debit' transactions (spending/interest) MUST BE POSITIVE (e.g., 45.67).
     - 'credit' transactions (payments to the card/refunds) MUST BE NEGATIVE (e.g., -2500.00).
5. Convert dates to YYYY-MM-DD format.
6. Extract merchant names or transaction descriptions clearly.
7. Only extract actual transactions. DO NOT extract account summaries, opening balances, closing balances, previous balances, or statement balances.

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
- amount (number, according to sign rules above, REQUIRED)
- transaction_type (string, "debit" or "credit", REQUIRED)
- balance (number, account balance after transaction, OPTIONAL)

JSON:"""

BANK_STATEMENT_CLASSIFICATION_PROMPT = """You are a bank statement classifier. 
Based on the text below, determine if this is a **Credit Card** statement or a **Debit/Checking Account** statement.

Look for:
- Keywords like "Credit Card", "Visa", "Mastercard", "Amex", "Available Credit", "Minimum Payment" -> 'credit'.
- Keywords like "Checking", "Current Account", "Savings", "Debit Card", "Available Balance", "Overdraft" -> 'debit'.

Return ONLY a JSON object with a single key 'card_type' whose value is either 'credit' or 'debit'.

TEXT:
{{text}}

JSON:"""

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
            # "openai": "Extract invoice information from this text and return ONLY valid JSON. Focus on accurate line item extraction and total calculations.",
            # "anthropic": "As an expert in invoice analysis, extract structured data from this invoice text with high precision and attention to financial details."
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
            # "openai": "You are a data extraction expert. Convert this OCR output to clean, compact JSON.",
            # "anthropic": "As a data extraction specialist, analyze this OCR text and structure it into the requested JSON format."
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
            # "openai": "You are an AI assistant specialized in identifying expense-related emails.",
            # "anthropic": "As an expert in email analysis, determine if this email contains financial transactions or expense-related content."
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
            # "openai": "You are an invoice data extraction AI. Extract key invoice fields and respond ONLY with compact JSON.",
            # "anthropic": "As an expert in invoice analysis, extract all relevant invoice data with high precision and attention to financial details."
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
            # "openai": "Analyze this invoice document and classify it. Respond ONLY with JSON.",
            # "anthropic": "As an expert in document analysis, classify this invoice document with high precision."
        }
    },
  {
    "name": "bank_transaction_extraction",
    "category": "bank_processing",
    "description": "Extract bank transactions from statement text",
    "template_content": BANK_TRANSACTION_EXTRACTION_PROMPT,
    "template_variables": ["text"],
    "output_format": "json",
    "default_values": {},
    "version": 2,
    "is_active": True,
    "provider_overrides": {
        # "openai": "You are a financial data extraction expert. Extract ALL bank transactions from the text. Be thorough and extract every single transaction.",
        # "anthropic": "As an expert in financial data analysis, meticulously extract ALL transactions with high precision. Do not skip any transactions."
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
            # "openai": "You are a Senior Financial Auditor. Extract invoice data with absolute precision for a forensic review.",
            # "anthropic": "As an expert forensic accountant, extract every detail from this invoice text. Double-check all mathematical calculations and line item totals."
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
            # "openai": "You are an Expense Auditor. Re-extract receipt data with meticulous attention to subtotals and taxes. NEVER hallucinate vendor names - only extract what is clearly present in the OCR data.",
            # "anthropic": "As a financial compliance specialist, re-extract data from this OCR output with absolute precision. Verify vendor names are exactly as shown - do not guess or infer brand names."
        }
    },
    {
        "name": "bank_statement_review_extraction",
        "category": "bank_processing",
        "description": "High-fidelity prompt for bank statement transaction review",
        "template_content": """You are a Bank Reconciliation Specialist reviewing transactions for a **{{card_type}}** card/account. 
- If 'auto', first determine if this is a Credit Card or a Debit/Checking account statement.
- Apply consistent rules for signs: Credit Cards (Negative=Credit, Positive=Debit), Debit Cards (Negative=Debit, Positive=Credit).

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
7. DO NOT extract account summaries, opening balances, closing balances, previous balances, or statement balances.

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
            # "openai": "You are a Bank Reconciliation Specialist. Extract every transaction with high fidelity. Ensure all amounts are correctly signed based on context.",
            # "anthropic": "As an expert in banking data analysis, meticulously extract all transaction entries. Identify transaction types from context and ensure correct negative/positive signs for amounts."
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
            # "openai": "Extract all text from this document image accurately. Preserve layout and details.",
            # "anthropic": "As a document specialist, transcribe all text from this image with high fidelity, including fine print and peripheral data."
        }
    },
    {
        "name": "expense_receipt_vision_extraction",
        "category": "ocr",
        "description": "Extract structured expense data from receipt images using vision models",
        "template_content": """You are an OCR parser. Extract key expense fields and respond ONLY with compact JSON.
Required keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, notes, receipt_timestamp (YYYY-MM-DD HH:MM:SS if available).
For receipt_timestamp, extract the exact time from the receipt if visible (not just the date). Look for timestamps like '14:32', '2:45 PM', etc.
If a field is unknown, set it to null.
IMPORTANT: Return ONLY the JSON object, no markdown formatting, no explanations, no headers like '**Receipt Data Extraction**'.""",
        "template_variables": [],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {
            # "openai": "You are an OCR parser. Extract key expense fields from this receipt image into compact JSON.",
            # "anthropic": "As a receipt processing specialist, extract all expense details from this image into the required JSON format."
        }
    },
    {

        "name": "portfolio_data_extraction",
        "category": "investments",
        "description": "Extract both investment holdings and transaction history from portfolio statements",
        "template_content": """You are a financial data extraction specialist. Extract investment holdings and transaction history from the provided document.

IMPORTANT: Your response MUST be ONLY a valid raw JSON object.
DO NOT include any markdown formatting (like ```json).
DO NOT include any explanations, introduction, or concluding prose.
ONLY return the JSON.

=== FIELD DEFINITIONS (read carefully before extracting) ===

For each holding, extract these fields:

1. security_symbol: The ticker symbol (e.g., AAPL, MSFT, AMD, COIN)

2. security_name: Full name of the security

3. security_type: stock, bond, etf, mutual_fund, option, crypto, or other

4. asset_class: stocks, bonds, cash, real_estate, commodities, alternatives, or other

5. quantity: Number of shares or units held
   - Column names: "Quantity", "Shares", "Units", "Position", "Qty"

6. cost_basis: The TOTAL book cost for ALL shares combined (not per-share price)
   - Column names: "Book Cost", "Total Cost", "Cost Basis", "Adjusted Cost Base", "ACB", "Book Value", "Orig Cost"
   - This equals quantity x average purchase price per share
   - Example: 40 shares with book cost of $128.84 total -> cost_basis = 128.84
   - WARNING: Do NOT put the market price or current price here

7. market_price: The CURRENT market price PER SHARE as of the statement date
   - Column names: "Market Price", "Current Price", "Last Price", "Price", "Mkt Price", "Unit Price"
   - This is a single per-share value (e.g., AMD at $214.16/share)
   - Sanity check: market_price x quantity should approximately equal the "Market Value" total column
   - WARNING: Do NOT put the book cost or total cost here

8. purchase_date: Date of purchase (YYYY-MM-DD, or null if not shown)

9. currency: Currency of the holding (e.g., USD, CAD, EUR)
   - Use the primary currency shown (e.g., USD), not a converted foreign-currency column

=== COLUMN DISAMBIGUATION TABLE ===

| PDF Column Label                              | Maps to JSON field |
|-----------------------------------------------|--------------------|
| Book Cost / Book Value / ACB / Adjusted Cost  | cost_basis         |
| Market Price / Current Price / Last Price     | market_price       |
| Market Value / Current Value / Mkt Value      | (do not store)     |
| Quantity / Shares / Position / Units          | quantity           |

For each transaction found, extract:
- transaction_date: Date of the transaction (YYYY-MM-DD format)
- transaction_type: Type of transaction (BUY, SELL, DIVIDEND, INTEREST, FEE, DEPOSIT, WITHDRAWAL, TRANSFER_IN, TRANSFER_OUT)
- security_symbol: Ticker symbol (if applicable)
- quantity: Number of shares/units (if applicable)
- price: Price per share/unit (if applicable)
- amount: Total transaction amount
- fees: Transaction fees (if any)

The JSON structure must be:
{
  "holdings": [
    {
      "security_symbol": "AMD",
      "security_name": "Advanced Micro Devices Inc.",
      "security_type": "stock",
      "asset_class": "stocks",
      "quantity": 40,
      "cost_basis": 128.84,
      "market_price": 214.16,
      "purchase_date": null,
      "currency": "USD"
    }
  ],
  "transactions": [
    {
      "transaction_date": "2023-01-15",
      "transaction_type": "BUY",
      "security_symbol": "AAPL",
      "quantity": 100,
      "price": 150.00,
      "amount": 15000.00,
      "fees": 9.99
    }
  ]
}

Important:
- Return ONLY valid JSON, no markdown formatting or code blocks
- Use null for missing values
- Ensure all numeric values are numbers, not strings
- Use YYYY-MM-DD format for dates
- If no transactions are found, return an empty transactions array
- Be precise with security symbols and names

Document content:
{{ document_content }}

Document type: {{ document_type }}

JSON ONLY:""",
        "template_variables": ["document_content", "document_type"],
        "output_format": "json",
        "default_values": {},
        "version": 1,
        "is_active": True,
        "provider_overrides": {}
    }
]
