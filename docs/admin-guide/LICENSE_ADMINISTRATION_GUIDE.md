# License Administration Guide

## Overview

This guide is for system administrators and license managers who need to generate licenses, handle customer support requests, and manage the licensing system for the {APP_NAME}.

## Table of Contents

1. [License Generation](#license-generation)
2. [Customer Support](#customer-support)
3. [License Revocation](#license-revocation)
4. [Troubleshooting](#troubleshooting)
5. [Security Best Practices](#security-best-practices)
6. [Monitoring and Analytics](#monitoring-and-analytics)

---

## License Generation

### Prerequisites

Before generating licenses, ensure you have:
- ✅ Access to the license server
- ✅ Private key file (`private_key.pem`)
- ✅ License generation CLI tool or web interface
- ✅ Customer information (email, name, purchased features)

### Method 1: CLI Tool (Recommended)

The CLI tool is the fastest way to generate licenses for individual customers.

#### Basic Usage

```bash
cd license_server
python generate_license_cli.py \
  --email customer@example.com \
  --name "Acme Corporation" \
  --features ai_invoice,ai_expense,tax_integration \
  --duration 365
```

#### Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `--email` | Yes | Customer email address | `customer@example.com` |
| `--name` | Yes | Customer/company name | `"Acme Corp"` |
| `--features` | Yes | Comma-separated feature IDs | `ai_invoice,tax_integration` |
| `--duration` | No | License duration in days (default: 365) | `730` (2 years) |
| `--output` | No | Save license to file | `license.txt` |

#### Available Feature IDs

**AI Features:**
- `ai_invoice` - AI Invoice Processing
- `ai_expense` - AI Expense Processing
- `ai_bank_statement` - AI Bank Statement Processing
- `ai_chat` - AI Chat Assistant

**Integration Features:**
- `tax_integration` - Tax Service Integration
- `slack_integration` - Slack Integration
- `cloud_storage` - Cloud Storage (S3, Azure, GCP)
- `sso_auth` - SSO Authentication

**Advanced Features:**
- `approvals` - Approval Workflows
- `reporting` - Reporting & Analytics
- `batch_processing` - Batch File Processing
- `inventory` - Inventory Management
- `advanced_search` - Advanced Search
- `crm` - CRM Module

#### Example: Generate Full-Featured License

```bash
python generate_license_cli.py \
  --email premium@customer.com \
  --name "Premium Customer Inc" \
  --features ai_invoice,ai_expense,ai_bank_statement,ai_chat,tax_integration,slack_integration,cloud_storage,sso_auth,approvals,reporting,batch_processing,inventory,advanced_search,crm \
  --duration 365 \
  --output premium_license.txt
```

#### Example: Generate Trial License

```bash
python generate_license_cli.py \
  --email trial@customer.com \
  --name "Trial User" \
  --features ai_invoice,ai_expense \
  --duration 30 \
  --output trial_license.txt
```

#### Output

The CLI tool will output:
```
✅ License generated successfully!

Customer: Acme Corporation
Email: customer@example.com
Features: ai_invoice, ai_expense, tax_integration
Expires: 2026-11-16
Duration: 365 days

License Key:
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImN1c3RvbWVyQGV4YW1wbGUuY29tIiwibmFtZSI6IkFjbWUgQ29ycG9yYXRpb24iLCJmZWF0dXJlcyI6WyJhaV9pbnZvaWNlIiwiYWlfZXhwZW5zZSIsInRheF9pbnRlZ3JhdGlvbiJdLCJleHAiOjE3NjYwMDAwMDB9.signature...

✅ License saved to: premium_license.txt
```

### Method 2: Web Interface

The web interface provides a user-friendly way to generate licenses.

#### Starting the Web Interface

```bash
cd license_server
python web_app.py
```

Access at: `http://localhost:5000`

#### Using the Web Interface

1. **Navigate to License Generator**
   - Open `http://localhost:5000/generate`

2. **Fill in Customer Information**
   - Customer Name
   - Customer Email
   - Select Features (checkboxes)
   - License Duration (days)

3. **Generate License**
   - Click "Generate License" button
   - License key is displayed
   - Copy to clipboard or download

4. **Send to Customer**
   - Copy the license key
   - Send via email or support ticket

### Method 3: Automated via Stripe Webhook

For automated license generation after payment:

1. **Stripe Checkout Completes**
   - Customer completes payment
   - Stripe sends webhook to your server

2. **Webhook Handler Processes Payment**
   ```python
   # Automatically handled by webhook_handler.py
   # No manual intervention required
   ```

3. **License Generated Automatically**
   - License is generated based on purchased features
   - Stored in database
   - Email sent to customer

4. **Verify in Database**
   ```bash
   python -c "from database import get_license_by_email; print(get_license_by_email('customer@example.com'))"
   ```

### License Storage

All generated licenses are stored in the license database:

**Database Location:** `license_server/licenses.db`

**Schema:**
```sql
CREATE TABLE licenses (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    license_key TEXT NOT NULL,
    features TEXT NOT NULL,  -- JSON array
    created_at TIMESTAMP,
    expires_at TIMESTAMP,
    stripe_session_id TEXT,
    revoked BOOLEAN DEFAULT 0
);
```

**Query Licenses:**
```bash
cd license_server
sqlite3 licenses.db "SELECT email, name, expires_at FROM licenses WHERE revoked = 0;"
```

---

## Customer Support

### Common Support Requests

#### 1. License Not Working

**Customer Issue:** "I activated my license but features are still locked."

**Troubleshooting Steps:**

1. **Verify License Key**
   ```bash
   cd license_server
   python -c "
   from license_generator import LicenseGenerator
   lg = LicenseGenerator()
   result = lg.verify_license('PASTE_LICENSE_KEY_HERE')
   print(result)
   "
   ```

2. **Check License Details**
   - Is the license expired?
   - Does it include the features customer expects?
   - Is the email correct?

3. **Common Issues:**
   - License key copied incorrectly (extra spaces, line breaks)
   - License expired
   - Customer using wrong installation
   - Browser cache not cleared

**Resolution:**
- Ask customer to copy license key again
- Verify license in database
- Generate new license if needed
- Ask customer to clear browser cache and re-login

#### 2. License Expired

**Customer Issue:** "My license expired, can you extend it?"

**Resolution:**

1. **Check Purchase History**
   ```bash
   sqlite3 licenses.db "SELECT * FROM licenses WHERE email = 'customer@example.com';"
   ```

2. **Generate Extended License**
   ```bash
   python generate_license_cli.py \
     --email customer@example.com \
     --name "Customer Name" \
     --features ai_invoice,ai_expense,tax_integration \
     --duration 365
   ```

3. **Send New License**
   - Email new license key to customer
   - Include activation instructions
   - Note: Old license is automatically replaced

#### 3. Need to Add Features

**Customer Issue:** "I want to add more features to my existing license."

**Resolution:**

1. **Check Current License**
   ```bash
   sqlite3 licenses.db "SELECT features FROM licenses WHERE email = 'customer@example.com';"
   ```

2. **Generate New License with All Features**
   ```bash
   # Include OLD features + NEW features
   python generate_license_cli.py \
     --email customer@example.com \
     --name "Customer Name" \
     --features ai_invoice,ai_expense,tax_integration,reporting,inventory \
     --duration 365
   ```

3. **Send Updated License**
   - New license replaces old one
   - All features (old + new) are included
   - Same expiration date or extended

#### 4. Lost License Key

**Customer Issue:** "I lost my license key, can you resend it?"

**Resolution:**

1. **Look Up License in Database**
   ```bash
   sqlite3 licenses.db "SELECT license_key FROM licenses WHERE email = 'customer@example.com' AND revoked = 0 ORDER BY created_at DESC LIMIT 1;"
   ```

2. **Verify Customer Identity**
   - Confirm email address
   - Verify purchase details
   - Check account information

3. **Resend License**
   - Copy license key from database
   - Send via email
   - Include activation instructions

#### 5. License for Wrong Email

**Customer Issue:** "License was sent to wrong email address."

**Resolution:**

1. **Generate New License with Correct Email**
   ```bash
   python generate_license_cli.py \
     --email correct@email.com \
     --name "Customer Name" \
     --features ai_invoice,ai_expense \
     --duration 365
   ```

2. **Optionally Revoke Old License**
   ```bash
   sqlite3 licenses.db "UPDATE licenses SET revoked = 1 WHERE email = 'wrong@email.com';"
   ```

3. **Send to Correct Email**

### Support Response Templates

#### Template 1: License Activation Help

```
Subject: License Activation Assistance

Hi [Customer Name],

Thank you for contacting support. I'd be happy to help you activate your license.

Your license key is:
[LICENSE_KEY]

To activate:
1. Log in to your {APP_NAME}
2. Go to Settings → License
3. Paste the license key above
4. Click "Activate License"
5. Refresh your browser (Ctrl+F5)

If you continue to experience issues, please:
- Clear your browser cache
- Log out and log back in
- Send a screenshot of any error messages

Best regards,
Support Team
```

#### Template 2: License Extended

```
Subject: License Extended

Hi [Customer Name],

Your license has been extended. Here is your new license key:

[LICENSE_KEY]

License Details:
- Features: [FEATURE_LIST]
- Expires: [EXPIRATION_DATE]

To activate the new license:
1. Go to Settings → License
2. Paste the new license key
3. Click "Activate License"

The new license will replace your existing one.

Best regards,
Support Team
```

#### Template 3: Features Added

```
Subject: Additional Features Added to Your License

Hi [Customer Name],

Your license has been updated with additional features. Here is your new license key:

[LICENSE_KEY]

New Features Included:
- [FEATURE_1]
- [FEATURE_2]
- [FEATURE_3]

To activate:
1. Go to Settings → License
2. Paste the new license key
3. Click "Activate License"

All your previous features are still included.

Best regards,
Support Team
```

---

## License Revocation

### When to Revoke a License

Revoke licenses in these situations:
- ❌ Chargeback or payment dispute
- ❌ Terms of service violation
- ❌ Customer requests refund
- ❌ Fraudulent purchase
- ❌ License shared/resold without authorization

### How to Revoke a License

#### Method 1: Database Update

```bash
cd license_server
sqlite3 licenses.db "UPDATE licenses SET revoked = 1 WHERE email = 'customer@example.com';"
```

#### Method 2: Python Script

```python
from database import revoke_license

revoke_license('customer@example.com')
print("License revoked successfully")
```

### Important Notes

⚠️ **License revocation is NOT enforced in offline mode**

The current implementation does NOT support online license validation. Revoked licenses will continue to work until they expire because:
- License verification is done locally (offline)
- No "phone home" mechanism exists
- Revocation is only tracked in your database

**To enforce revocation, you would need to:**
1. Implement online license validation (optional feature)
2. Customer installations check revocation status daily
3. Revoked licenses are rejected even if not expired

**Current Workaround:**
- Generate a new license with expiration date in the past
- Send to customer (will fail validation immediately)
- Or wait for current license to expire naturally

### Revocation Process

1. **Document Reason**
   ```bash
   sqlite3 licenses.db "UPDATE licenses SET revoked = 1, revocation_reason = 'Chargeback' WHERE email = 'customer@example.com';"
   ```

2. **Notify Customer (if appropriate)**
   ```
   Subject: License Revocation Notice
   
   Your license has been revoked due to [REASON].
   
   If you believe this is an error, please contact support.
   ```

3. **Log the Revocation**
   - Record in support system
   - Note reason and date
   - Keep for audit trail

---

## Troubleshooting

### Issue: License Generation Fails

**Symptoms:**
- CLI tool crashes
- "Private key not found" error
- "Invalid feature ID" error

**Solutions:**

1. **Check Private Key Exists**
   ```bash
   ls -la api/core/keys/private_key.pem
   ```

2. **Verify Private Key Permissions**
   ```bash
   chmod 600 api/core/keys/private_key.pem
   ```

3. **Test Key Loading**
   ```python
   from license_generator import LicenseGenerator
   lg = LicenseGenerator()
   print("Private key loaded successfully")
   ```

4. **Validate Feature IDs**
   - Check spelling of feature IDs
   - Refer to available feature list above
   - Use comma-separated format (no spaces)

### Issue: Webhook Not Receiving Stripe Events

**Symptoms:**
- Licenses not generated after payment
- No email sent to customer
- Webhook endpoint returns errors

**Solutions:**

1. **Check Webhook URL in Stripe Dashboard**
   - Go to Stripe Dashboard → Developers → Webhooks
   - Verify URL is correct: `https://yourdomain.com/webhook/stripe`
   - Check webhook is enabled

2. **Verify Webhook Secret**
   ```bash
   # In license_server/.env
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

3. **Test Webhook Locally**
   ```bash
   stripe listen --forward-to localhost:5000/webhook/stripe
   stripe trigger checkout.session.completed
   ```

4. **Check Webhook Logs**
   ```bash
   tail -f license_server/webhook.log
   ```

5. **Verify Signature Validation**
   - Ensure webhook secret matches Stripe dashboard
   - Check signature verification in webhook_handler.py

### Issue: Email Not Sending

**Symptoms:**
- License generated but customer doesn't receive email
- SMTP errors in logs

**Solutions:**

1. **Check Email Configuration**
   ```bash
   # In license_server/.env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SMTP_FROM=noreply@yourdomain.com
   ```

2. **Test Email Service**
   ```python
   from email_service import send_license_email
   
   send_license_email(
       to_email="test@example.com",
       customer_name="Test Customer",
       license_key="test_key",
       features=["ai_invoice"],
       expires_at="2026-11-16"
   )
   ```

3. **Check SMTP Credentials**
   - Verify username/password
   - Enable "Less secure app access" (Gmail)
   - Use app-specific password (Gmail)

4. **Check Firewall/Network**
   - Ensure port 587 (or 465) is open
   - Check if SMTP is blocked by firewall

### Issue: Database Corruption

**Symptoms:**
- Cannot query licenses
- Database locked errors
- Missing licenses

**Solutions:**

1. **Backup Database**
   ```bash
   cp license_server/licenses.db license_server/licenses.db.backup
   ```

2. **Check Database Integrity**
   ```bash
   sqlite3 licenses.db "PRAGMA integrity_check;"
   ```

3. **Repair Database**
   ```bash
   sqlite3 licenses.db ".recover" | sqlite3 licenses_recovered.db
   mv licenses_recovered.db licenses.db
   ```

4. **Restore from Backup**
   ```bash
   cp license_server/licenses.db.backup license_server/licenses.db
   ```

---

## Security Best Practices

### Private Key Security

🔒 **CRITICAL: Protect the private key at all costs**

The private key (`private_key.pem`) is used to sign all licenses. If compromised, attackers can generate unlimited valid licenses.

#### Security Measures

1. **File Permissions**
   ```bash
   chmod 600 api/core/keys/private_key.pem
   chown root:root api/core/keys/private_key.pem
   ```

2. **Never Commit to Git**
   ```bash
   # Ensure in .gitignore
   echo "api/core/keys/private_key.pem" >> .gitignore
   ```

3. **Backup Securely**
   ```bash
   # Encrypt backup
   gpg --encrypt --recipient admin@yourdomain.com private_key.pem
   # Store encrypted backup in secure location
   ```

4. **Limit Access**
   - Only license administrators should have access
   - Use separate server for license generation
   - Implement access logging

5. **Rotate Keys (if compromised)**
   ```bash
   # Generate new key pair
   python api/scripts/generate_license_keys.py
   
   # Update all customer licenses with new key
   # (This is a major operation - avoid if possible)
   ```

### Database Security

1. **Regular Backups**
   ```bash
   # Daily backup cron job
   0 2 * * * cp /path/to/licenses.db /backups/licenses-$(date +\%Y\%m\%d).db
   ```

2. **Encrypt Database**
   ```bash
   # Use SQLCipher for encrypted database
   pip install sqlcipher3
   ```

3. **Access Control**
   - Restrict database file permissions
   - Use authentication for database access
   - Log all database queries

### Webhook Security

1. **Verify Signatures**
   - Always verify Stripe webhook signatures
   - Reject unsigned requests
   - Log verification failures

2. **Use HTTPS**
   - Never use HTTP for webhooks
   - Ensure SSL certificate is valid
   - Use strong TLS version (1.2+)

3. **Rate Limiting**
   - Implement rate limiting on webhook endpoint
   - Prevent abuse and DoS attacks

---

## Monitoring and Analytics

### License Usage Statistics

#### Query Active Licenses

```bash
sqlite3 licenses.db "SELECT COUNT(*) FROM licenses WHERE revoked = 0 AND expires_at > datetime('now');"
```

#### Query by Feature

```bash
sqlite3 licenses.db "SELECT COUNT(*) FROM licenses WHERE features LIKE '%ai_invoice%' AND revoked = 0;"
```

#### Query Expiring Soon

```bash
sqlite3 licenses.db "SELECT email, name, expires_at FROM licenses WHERE expires_at BETWEEN datetime('now') AND datetime('now', '+30 days') AND revoked = 0;"
```

#### Revenue by Feature

```bash
# Requires Stripe integration
python -c "
from database import get_all_licenses
licenses = get_all_licenses()
for license in licenses:
    print(f'{license.email}: {len(license.features)} features')
"
```

### Automated Reports

Create a daily report script:

```python
# scripts/daily_license_report.py
from database import get_all_licenses
from datetime import datetime, timedelta

licenses = get_all_licenses()
active = [l for l in licenses if not l.revoked and l.expires_at > datetime.now()]
expiring_soon = [l for l in active if l.expires_at < datetime.now() + timedelta(days=30)]

print(f"Active Licenses: {len(active)}")
print(f"Expiring in 30 days: {len(expiring_soon)}")
print(f"Total Revenue: ${len(active) * 99}")  # Adjust pricing

# Email report to admin
```

### Monitoring Checklist

- [ ] Daily backup of license database
- [ ] Weekly review of expiring licenses
- [ ] Monthly revenue report
- [ ] Monitor webhook failures
- [ ] Check email delivery success rate
- [ ] Review support tickets for license issues
- [ ] Audit private key access logs

---

## Quick Reference

### Common Commands

```bash
# Generate license
python generate_license_cli.py --email customer@example.com --name "Customer" --features ai_invoice --duration 365

# Verify license
python -c "from license_generator import LicenseGenerator; lg = LicenseGenerator(); print(lg.verify_license('LICENSE_KEY'))"

# Look up license
sqlite3 licenses.db "SELECT * FROM licenses WHERE email = 'customer@example.com';"

# Revoke license
sqlite3 licenses.db "UPDATE licenses SET revoked = 1 WHERE email = 'customer@example.com';"

# Count active licenses
sqlite3 licenses.db "SELECT COUNT(*) FROM licenses WHERE revoked = 0 AND expires_at > datetime('now');"

# Backup database
cp licenses.db licenses-$(date +%Y%m%d).db
```

### Support Workflow

1. Customer contacts support
2. Verify customer identity (email, order ID)
3. Look up license in database
4. Diagnose issue (expired, wrong features, etc.)
5. Generate new license if needed
6. Send license key with instructions
7. Follow up to ensure resolution
8. Document in support system

---

## Appendix

### Feature ID Reference

| Feature ID | Feature Name | Category |
|------------|--------------|----------|
| `ai_invoice` | AI Invoice Processing | AI |
| `ai_expense` | AI Expense Processing | AI |
| `ai_bank_statement` | AI Bank Statement Processing | AI |
| `ai_chat` | AI Chat Assistant | AI |
| `tax_integration` | Tax Service Integration | Integration |
| `slack_integration` | Slack Integration | Integration |
| `cloud_storage` | Cloud Storage | Integration |
| `sso_auth` | SSO Authentication | Integration |
| `approvals` | Approval Workflows | Advanced |
| `reporting` | Reporting & Analytics | Advanced |
| `batch_processing` | Batch File Processing | Advanced |
| `inventory` | Inventory Management | Advanced |
| `advanced_search` | Advanced Search | Advanced |
| `crm` | CRM Module | Advanced |

### Contact Information

- **Technical Issues:** devops@yourdomain.com
- **License Questions:** licensing@yourdomain.com
- **Sales:** sales@yourdomain.com
- **Emergency:** +1-555-0100

---

**Last Updated:** November 2025  
**Version:** 1.0  
**Maintainer:** License Administration Team
