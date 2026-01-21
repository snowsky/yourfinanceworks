# Existing Customer Migration Guide

## Overview

This guide explains how to migrate existing customers to the new licensing system without disrupting their service. The migration process ensures all existing customers retain access to all features with a generous grace period.

## Table of Contents

1. [Migration Strategy](#migration-strategy)
2. [Pre-Migration Checklist](#pre-migration-checklist)
3. [Running the Migration](#running-the-migration)
4. [Post-Migration Tasks](#post-migration-tasks)
5. [Customer Communication](#customer-communication)
6. [Troubleshooting](#troubleshooting)

---

## Migration Strategy

### Goals

- ✅ Zero disruption to existing customers
- ✅ All features remain available
- ✅ Generous grace period (90 days recommended)
- ✅ Automatic license generation and activation
- ✅ Clear communication to customers

### Migration Process

```
1. Backup Database
   ↓
2. Run Migration Script (Dry Run)
   ↓
3. Review Results
   ↓
4. Run Actual Migration
   ↓
5. Verify All Tenants Migrated
   ↓
6. Send Customer Notifications
   ↓
7. Monitor Grace Period
   ↓
8. Follow Up Before Expiration
```

### Timeline

| Phase | Duration | Activities |
|-------|----------|------------|
| **Preparation** | 1 week | Test in staging, prepare communications |
| **Migration** | 1 day | Run migration script, verify results |
| **Grace Period** | 90 days | Monitor, support customers, send reminders |
| **Enforcement** | Ongoing | License system fully active |

---

## Pre-Migration Checklist

### 1. Test in Staging

```bash
# Deploy licensing system to staging
./api/scripts/deploy_licensing_system.sh staging

# Run migration in staging (dry run)
cd api
python scripts/migrate_existing_customers_to_licensing.py --dry-run

# Verify staging results
# Test license activation
# Check UI displays correctly
```

### 2. Backup Production Database

**Critical: Always backup before migration**

```bash
# Backup master database
pg_dump -h localhost -U postgres invoice_master > backup_master_$(date +%Y%m%d).sql

# Backup all tenant databases
for db in $(psql -h localhost -U postgres -t -c "SELECT 'tenant_' || id FROM tenants WHERE is_active = true;"); do
    pg_dump -h localhost -U postgres $db > backup_${db}_$(date +%Y%m%d).sql
done

# Verify backups
ls -lh backup_*.sql
```

### 3. Prepare Customer Communications

Create email templates:
- Migration announcement
- License activation confirmation
- Grace period reminder (30 days before)
- Final reminder (7 days before)

### 4. Configure Migration Parameters

Decide on:
- **Grace Period:** 90 days recommended (can be 30-180 days)
- **License Duration:** 1 year recommended (can be 1-3 years)
- **Email Notifications:** Yes (recommended)

### 5. Notify Team

- Inform support team about migration
- Prepare FAQ for customer questions
- Schedule monitoring during migration
- Have rollback plan ready

---

## Running the Migration

### Step 1: Dry Run

**Always run dry run first to preview changes**

```bash
cd api
python scripts/migrate_existing_customers_to_licensing.py --dry-run
```

**Expected Output:**
```
================================================================================
EXISTING CUSTOMER MIGRATION TO LICENSING SYSTEM
================================================================================
Dry Run: True
Grace Period: 90 days
License Duration: 1 year(s)
Send Emails: False
Skip Inactive: True
================================================================================

⚠️  DRY RUN MODE - No changes will be made

Found 25 tenants to migrate

📦 Migrating Tenant 1: Acme Corporation
  [DRY RUN] Would create installation record for tenant 1
  [DRY RUN] Would generate license for tenant 1
  [DRY RUN] Would activate license for tenant 1

📦 Migrating Tenant 2: Beta Industries
  [DRY RUN] Would create installation record for tenant 2
  [DRY RUN] Would generate license for tenant 2
  [DRY RUN] Would activate license for tenant 2

...

================================================================================
MIGRATION SUMMARY
================================================================================
Total Tenants: 25
Successful: 25
Installations Created: 25
Licenses Generated: 25
Licenses Activated: 25
Emails Sent: 0
================================================================================

⚠️  This was a DRY RUN - no changes were made
Run without --dry-run to apply changes
```

### Step 2: Review Dry Run Results

Check:
- ✓ All active tenants are included
- ✓ No unexpected errors
- ✓ Tenant count matches expectations
- ✓ Email addresses are correct

### Step 3: Run Actual Migration

**Without email notifications (recommended first):**

```bash
python scripts/migrate_existing_customers_to_licensing.py \
  --grace-days 90 \
  --license-years 1
```

**With email notifications:**

```bash
python scripts/migrate_existing_customers_to_licensing.py \
  --grace-days 90 \
  --license-years 1 \
  --send-emails
```

**You will be prompted to confirm:**
```
⚠️  WARNING: This will modify the database and potentially send emails
Grace period: 90 days
License duration: 1 year(s)
Send emails: True

Continue? (yes/no):
```

Type `yes` to proceed.

### Step 4: Monitor Migration Progress

The script will output progress for each tenant:

```
📦 Migrating Tenant 1: Acme Corporation
  ✅ Created installation record for tenant 1
  ✅ Generated license for tenant 1
  ✅ Activated license for tenant 1
  ✅ Sent notification email to admin@acme.com

📦 Migrating Tenant 2: Beta Industries
  ✅ Created installation record for tenant 2
  ✅ Generated license for tenant 2
  ✅ Activated license for tenant 2
  ✅ Sent notification email to admin@beta.com
```

### Step 5: Review Migration Summary

```
================================================================================
MIGRATION SUMMARY
================================================================================
Total Tenants: 25
Successful: 25
Installations Created: 25
Licenses Generated: 25
Licenses Activated: 25
Emails Sent: 25
================================================================================

✅ Migration complete!
Grace period: 90 days
Customers have been notified via email
```

---

## Post-Migration Tasks

### 1. Verify All Tenants Migrated

```bash
# Check installation records
psql -h localhost -U postgres invoice_master -c "
SELECT COUNT(*) FROM installation_info;
"

# Should match number of active tenants

# Check license activation
psql -h localhost -U postgres invoice_master -c "
SELECT tenant_id, is_trial, trial_end_date 
FROM installation_info 
ORDER BY tenant_id;
"
```

### 2. Test License System

```bash
# Test license service
cd api
python -c "
from services.license_service import LicenseService

service = LicenseService()

# Check tenant 1
status = service.get_trial_status(tenant_id=1)
print(f'Tenant 1 Status: {status}')

features = service.get_enabled_features(tenant_id=1)
print(f'Tenant 1 Features: {len(features)} enabled')
"
```

### 3. Verify UI

1. Log in as different tenants
2. Navigate to Settings → License
3. Verify license status shows:
   - License Active
   - All features enabled
   - Expiration date
   - Grace period information

### 4. Check Email Delivery

If emails were sent:
- Verify emails were delivered
- Check spam folders
- Review bounce reports
- Follow up on failed deliveries

### 5. Monitor Logs

```bash
# Check for errors
tail -f /var/log/invoice-api/app.log | grep -i license

# Check for license validation
grep "license" /var/log/invoice-api/app.log | tail -20
```

### 6. Update Documentation

- Mark migration as complete
- Document any issues encountered
- Update customer-facing documentation
- Update internal runbooks

---

## Customer Communication

### Initial Migration Email

**Subject:** Important: New Licensing System - No Action Required

```
Dear [Customer Name],

We're excited to announce that we've upgraded our {APP_NAME} 
with a new licensing system!

As a valued existing customer, we've automatically activated a license for 
you with ALL features enabled.

✅ What This Means for You:
- No action required - your license is already activated
- All features you currently use remain available
- 90-day grace period before enforcement
- 1-year license with all features included

📋 Your License Details:
- Customer: [Customer Name]
- Features: All features enabled
- Expires: [Expiration Date]
- Grace Period: 90 days

🔍 View Your License:
1. Log in to your account
2. Go to Settings → License
3. View your license status and features

📚 Learn More:
- Documentation: https://docs.yourdomain.com/licensing
- FAQ: https://docs.yourdomain.com/licensing-faq
- Support: support@yourdomain.com

Thank you for being a valued customer!

Best regards,
The Invoice Management Team
```

### 30-Day Reminder Email

**Subject:** Reminder: License Renewal in 30 Days

```
Dear [Customer Name],

This is a friendly reminder that your license will expire in 30 days.

License Details:
- Expires: [Expiration Date]
- Features: All features enabled
- Days Remaining: 30

To ensure uninterrupted service, please renew your license before expiration.

Renew Now: [Renewal Link]

Questions? Contact support@yourdomain.com

Best regards,
The Invoice Management Team
```

### 7-Day Final Reminder

**Subject:** Action Required: License Expires in 7 Days

```
Dear [Customer Name],

Your license will expire in 7 days. Please renew to continue using all features.

License Details:
- Expires: [Expiration Date]
- Days Remaining: 7

After expiration, premium features will be disabled. Core features (invoices, 
expenses, clients) will remain available.

Renew Now: [Renewal Link]

Need help? Contact support@yourdomain.com

Best regards,
The Invoice Management Team
```

---

## Troubleshooting

### Issue: Migration Script Fails

**Error:** Script exits with errors

**Solution:**
```bash
# Check Python dependencies
pip install PyJWT cryptography

# Check database connection
psql -h localhost -U postgres invoice_master -c "SELECT 1;"

# Run with verbose output
python scripts/migrate_existing_customers_to_licensing.py --dry-run 2>&1 | tee migration.log

# Review log
cat migration.log
```

### Issue: Some Tenants Not Migrated

**Error:** Not all tenants appear in summary

**Solution:**
```bash
# Check which tenants were skipped
psql -h localhost -U postgres invoice_master -c "
SELECT t.id, t.name, t.is_active, i.installation_id
FROM tenants t
LEFT JOIN installation_info i ON t.id = i.tenant_id
WHERE i.installation_id IS NULL;
"

# Migrate specific tenant manually
python -c "
from scripts.migrate_existing_customers_to_licensing import CustomerMigration
from models.models import Tenant
from models.database import SessionLocal

db = SessionLocal()
tenant = db.query(Tenant).filter(Tenant.id == TENANT_ID).first()

migration = CustomerMigration(dry_run=False)
result = migration.migrate_tenant(tenant)
print(result)
"
```

### Issue: License Generation Fails

**Error:** "License generation not available"

**Solution:**
```bash
# Check license_server is available
ls -la license_server/

# Install license_server dependencies
cd license_server
pip install -r requirements.txt

# Verify private key exists
ls -la api/core/keys/private_key.pem

# Test license generation
cd license_server
python generate_license_cli.py --email test@example.com --name Test --features ai_invoice --duration 365
```

### Issue: Emails Not Sending

**Error:** Emails not delivered

**Solution:**
```bash
# Check email configuration
cat license_server/.env | grep SMTP

# Test email service
cd license_server
python -c "
from email_service import send_license_email

send_license_email(
    to_email='test@example.com',
    customer_name='Test',
    license_key='test_key',
    features=['ai_invoice'],
    expires_at='2026-01-01'
)
"

# Check email logs
tail -f /var/log/mail.log
```

### Issue: Customers Can't See License

**Error:** License page shows "No license found"

**Solution:**
```bash
# Check installation record exists
psql -h localhost -U postgres invoice_master -c "
SELECT * FROM installation_info WHERE tenant_id = TENANT_ID;
"

# Check license is activated
psql -h localhost -U postgres invoice_master -c "
SELECT * FROM installation_info WHERE tenant_id = TENANT_ID AND license_key IS NOT NULL;
"

# Verify in UI
# 1. Clear browser cache
# 2. Hard refresh (Ctrl+F5)
# 3. Log out and log back in
```

---

## Migration Checklist

### Pre-Migration
- [ ] Tested in staging environment
- [ ] Database backup completed
- [ ] Customer communications prepared
- [ ] Team notified
- [ ] Rollback plan documented
- [ ] Dry run completed successfully

### Migration
- [ ] Ran migration script
- [ ] All tenants migrated successfully
- [ ] No errors in migration summary
- [ ] Licenses generated and activated
- [ ] Emails sent (if applicable)

### Post-Migration
- [ ] Verified installation records created
- [ ] Tested license service
- [ ] Checked UI license pages
- [ ] Verified email delivery
- [ ] Monitored logs for errors
- [ ] Updated documentation
- [ ] Notified team of completion

### Grace Period
- [ ] Monitor customer questions
- [ ] Send 30-day reminder emails
- [ ] Send 7-day final reminders
- [ ] Prepare for license enforcement
- [ ] Handle renewal requests

---

## Advanced Options

### Migrate Specific Tenants Only

```python
# Create custom migration script
from scripts.migrate_existing_customers_to_licensing import CustomerMigration
from models.models import Tenant
from models.database import SessionLocal

db = SessionLocal()
migration = CustomerMigration(dry_run=False, grace_days=90, license_years=1)

# Migrate specific tenant IDs
tenant_ids = [1, 5, 10, 15]
for tenant_id in tenant_ids:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant:
        result = migration.migrate_tenant(tenant)
        print(f"Tenant {tenant_id}: {result}")
```

### Custom Grace Period Per Tenant

```python
# Set different grace periods for different tenants
from models.database import SessionLocal
from models.models_per_tenant import InstallationInfo
from datetime import datetime, timedelta

db = SessionLocal()

# VIP customers get 180 days
vip_tenant_ids = [1, 2, 3]
for tenant_id in vip_tenant_ids:
    installation = db.query(InstallationInfo).filter(
        InstallationInfo.tenant_id == tenant_id
    ).first()
    
    if installation:
        installation.trial_end_date = datetime.now() + timedelta(days=180)
        db.commit()
        print(f"Extended grace period for tenant {tenant_id}")
```

### Re-send Notification Emails

```bash
# Re-send emails to specific tenants
python -c "
from license_server.email_service import send_license_email
from models.database import SessionLocal
from models.models_per_tenant import InstallationInfo

db = SessionLocal()
installations = db.query(InstallationInfo).all()

for installation in installations:
    if installation.license_key:
        send_license_email(
            to_email=get_tenant_email(installation.tenant_id),
            customer_name=get_tenant_name(installation.tenant_id),
            license_key=installation.license_key,
            features=['all'],
            expires_at=installation.trial_end_date.strftime('%Y-%m-%d')
        )
        print(f'Sent email to tenant {installation.tenant_id}')
"
```

---

## Support

### Migration Issues

- **Email:** devops@yourdomain.com
- **Slack:** #licensing-migration
- **On-Call:** +1-555-0100

### Customer Questions

- **Email:** support@yourdomain.com
- **Documentation:** https://docs.yourdomain.com/licensing
- **FAQ:** https://docs.yourdomain.com/licensing-faq

---

**Last Updated:** November 2025  
**Version:** 1.0  
**Maintainer:** DevOps Team
