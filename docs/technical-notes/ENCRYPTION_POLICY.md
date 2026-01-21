# Database Encryption Policy and Implementation

## Overview

This document outlines the encryption policy for the {APP_NAME}, detailing which data fields are encrypted and why certain fields remain unencrypted for operational requirements.

## Encryption Architecture

The system uses tenant-specific encryption with AES-256-GCM encryption through SQLAlchemy's `EncryptedColumn` and `EncryptedJSON` types. Each tenant has their own encryption key, ensuring data isolation.

### Key Components
- **Encryption Service**: `api/services/encryption_service.py`
- **Column Types**: `api/utils/column_encryptor.py`
- **Validation**: `api/utils/encryption_validation.py`
- **Migration Support**: `api/utils/data_migration_encryption.py`

## Encryption Policy by Table

### Users Table
**Encrypted Fields:**
- `email` - Primary contact information
- `first_name` - Personal information
- `last_name` - Personal information
- `google_id` - OAuth identifier
- `azure_ad_id` - OAuth identifier

**Unencrypted Fields:**
- `hashed_password` - Already cryptographically hashed
- `role` - Required for authorization logic
- `is_active`, `is_superuser`, `is_verified` - Status flags
- `azure_tenant_id` - System identifier
- `theme` - UI preference
- `business_type` - UI customization
- `created_at`, `updated_at` - Timestamps

### Clients Table
**Encrypted Fields:**
- `name` - Business/client name
- `email` - Contact information
- `phone` - Contact information
- `address` - Location information
- `company` - Business information

**Unencrypted Fields:**
- `balance` - Financial calculations (explicitly kept unencrypted)
- `paid_amount` - Financial calculations (explicitly kept unencrypted)
- `preferred_currency` - Currency preference
- `created_at`, `updated_at` - Timestamps

### Client Notes Table
**Encrypted Fields:**
- `note` - Sensitive client communication

**Unencrypted Fields:**
- `client_id`, `user_id` - Foreign keys
- `created_at`, `updated_at` - Timestamps

### Invoices Table
**Encrypted Fields:**
- `notes` - Invoice notes and terms
- `custom_fields` - JSON custom data
- `attachment_filename` - File attachment names

**Unencrypted Fields:**
- `amount` - Total invoice amount (kept unencrypted for calculations)
- `subtotal` - Pre-discount amount (kept unencrypted for calculations)
- `discount_value` - Discount amount (kept unencrypted for calculations)
- `currency` - Currency code
- `status` - Invoice status
- `number` - Invoice number (unique identifier)
- `due_date` - Payment deadline
- `is_recurring` - Recurrence flag
- `recurring_frequency` - Recurrence pattern
- `discount_type` - Discount type (percentage/fixed)
- `show_discount_in_pdf` - Display preference
- `attachment_path` - File system path
- `is_deleted` - Soft delete flag
- `deleted_at`, `deleted_by` - Soft delete metadata
- `created_at`, `updated_at` - Timestamps

### Payments Table
**Encrypted Fields:**
- `reference_number` - Payment reference
- `notes` - Payment notes

**Unencrypted Fields:**
- `amount` - Payment amount (kept unencrypted for calculations)
- `currency` - Currency code
- `payment_date` - Transaction date
- `payment_method` - Payment method
- `created_at`, `updated_at` - Timestamps

### Expenses Table
**Encrypted Fields:**
- `vendor` - Vendor/supplier information
- `notes` - Expense notes
- `receipt_filename` - Receipt file names
- `inventory_items` - Inventory purchase details (JSON)
- `consumption_items` - Inventory consumption details (JSON)
- `analysis_result` - AI analysis results (JSON)

**Unencrypted Fields:**
- `amount` - Expense amount (kept unencrypted for calculations)
- `tax_amount` - Tax amount (kept unencrypted for calculations)
- `total_amount` - Total amount (kept unencrypted for calculations)
- `currency` - Currency code
- `expense_date` - Transaction date
- `category` - Expense category
- `label`, `labels` - Categorization tags
- `tax_rate` - Tax rate percentage
- `payment_method` - Payment method
- `reference_number` - Expense reference
- `status` - Expense status
- `receipt_path` - File system path
- `is_inventory_purchase` - Inventory flag
- `is_inventory_consumption` - Consumption flag
- `imported_from_attachment` - Import flag
- `analysis_status` - Processing status
- `analysis_error` - Error messages
- `manual_override` - Override flag
- `analysis_updated_at` - Processing timestamp
- `created_at`, `updated_at` - Timestamps

### AI Configs Table
**Encrypted Fields:**
- `provider_url` - API endpoints
- `api_key` - API credentials

**Unencrypted Fields:**
- `provider_name` - Provider identifier
- `model_name` - Model identifier
- `is_active`, `is_default` - Status flags
- `tested` - Test status
- `ocr_enabled` - Feature flag
- `max_tokens`, `temperature` - Model parameters
- `usage_count`, `last_used_at` - Usage tracking
- `created_at`, `updated_at` - Timestamps

### Audit Logs Table
**Encrypted Fields:**
- `user_email` - User email in audit trail
- `details` - Audit details (JSON)
- `ip_address` - User IP address
- `user_agent` - Browser/client information

**Unencrypted Fields:**
- `user_id` - User identifier
- `action` - Audit action type
- `resource_type`, `resource_id`, `resource_name` - Resource identifiers
- `status` - Success/failure status
- `error_message` - Error details
- `created_at` - Timestamp

## Why Amount Fields Are Not Encrypted

Financial amount fields (`amount`, `balance`, `paid_amount`, `subtotal`, `discount_value`, `tax_amount`, `total_amount`) are deliberately kept unencrypted for the following reasons:

### Performance Requirements
- **Calculations**: Tax calculations, discounts, totals require numeric operations
- **Aggregations**: SUM(), AVG(), MIN(), MAX() operations on amounts
- **Sorting**: ORDER BY amount operations
- **Filtering**: WHERE amount > X operations

### Business Logic Requirements
- **Reporting**: Financial reports need to aggregate amounts
- **Analytics**: Dashboard calculations and charts
- **Currency Conversion**: Mathematical operations for exchange rates
- **Discount Rules**: Dynamic discount calculations based on amounts

### Database Operations
- **Indexing**: Amount fields are frequently indexed for performance
- **Constraints**: Check constraints on amount ranges
- **Triggers**: Automated calculations based on amount changes

## Security Considerations

### Data Classification
- **Public**: Unencrypted operational data (amounts, dates, status)
- **Internal**: Encrypted sensitive business data (notes, custom fields)
- **Confidential**: Encrypted PII (emails, names, addresses)
- **Restricted**: Encrypted credentials (API keys, OAuth tokens)

### Encryption Implementation
- **Algorithm**: AES-256-GCM with authentication
- **Key Management**: Tenant-specific keys
- **Key Rotation**: Supported through re-encryption utilities
- **Backup Security**: Encrypted data remains encrypted in backups

## Validation and Monitoring

### Encryption Validation
The system includes comprehensive validation tools:
- `EncryptionValidator` class for integrity checking
- Automated tests for encryption/decryption
- Migration validation scripts
- Corruption detection and repair tools

### Monitoring
- Encryption status validation on startup
- Failed decryption logging
- Key rotation tracking
- Data integrity checks

## Migration and Maintenance

### Adding New Encrypted Fields
1. Update model definitions to use `EncryptedColumn` or `EncryptedJSON`
2. Create database migration
3. Update validation configuration
4. Test encryption/decryption
5. Update documentation

### Key Rotation
1. Use `data_reencryption.py` for key rotation
2. Validate data integrity after rotation
3. Update key references
4. Test all encrypted operations

### Backup and Recovery
- Encrypted data remains encrypted in backups
- Recovery procedures maintain encryption
- Key backup separate from data backup
- Disaster recovery includes key restoration

## Compliance and Best Practices

### GDPR/CCPA Compliance
- PII fields are encrypted
- Data minimization principles followed
- Right to erasure supported
- Audit trails maintained

### Security Best Practices
- Defense in depth with multiple security layers
- Principle of least privilege
- Regular security assessments
- Incident response procedures

## Future Considerations

### Potential Enhancements
- Homomorphic encryption for calculations on encrypted data
- Field-level encryption for specific compliance requirements
- Enhanced key management systems
- Real-time encryption monitoring

### Deprecation Notes
- Legacy unencrypted fields should be migrated to encrypted versions
- Old encryption methods should be phased out
- Regular security audits recommended

---

**Last Updated**: 2025-10-28
**Version**: 1.0
**Author**: System Documentation