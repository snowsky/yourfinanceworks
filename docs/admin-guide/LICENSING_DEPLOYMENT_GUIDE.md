# Licensing System Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the licensing system to production, staging, or development environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Deployment Methods](#deployment-methods)
4. [Post-Deployment Verification](#post-deployment-verification)
5. [Rollback Procedures](#rollback-procedures)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Components

- ✅ PostgreSQL database (master + tenant databases)
- ✅ Python 3.9+ with pip
- ✅ Alembic for database migrations
- ✅ Public key file (`api/core/keys/public_key.pem`)
- ✅ Access to production servers
- ✅ Backup of current database

### Required Packages

```bash
pip install PyJWT cryptography alembic
```

### Environment Access

- SSH access to production servers
- Database admin credentials
- Docker access (if using containers)
- Sudo/root privileges for system changes

---

## Pre-Deployment Checklist

### 1. Generate RSA Key Pair

If not already generated:

```bash
cd api
python scripts/generate_license_keys.py
```

**Verify keys exist:**
```bash
ls -la api/core/keys/
# Should show:
# private_key.pem (600 permissions)
# public_key.pem (644 permissions)
```

### 2. Backup Database

**Critical: Always backup before deployment**

```bash
# Backup master database
pg_dump -h localhost -U postgres invoice_master > backup_master_$(date +%Y%m%d).sql

# Backup all tenant databases
for db in $(psql -h localhost -U postgres -t -c "SELECT 'tenant_' || id FROM tenants;"); do
    pg_dump -h localhost -U postgres $db > backup_${db}_$(date +%Y%m%d).sql
done
```

### 3. Test in Staging

**Always test in staging first:**

```bash
# Deploy to staging
./api/scripts/deploy_licensing_system.sh staging

# Verify staging works
curl http://staging.yourdomain.com/api/v1/license/features
```

### 4. Review Migration Scripts

```bash
# Check migration exists
cd api
alembic history | grep "add_license_tables"

# Review migration SQL
alembic upgrade --sql add_license_tables:head > migration_preview.sql
cat migration_preview.sql
```

### 5. Prepare Rollback Plan

Document rollback steps:
- Database backup locations
- Previous version tag/commit
- Rollback commands
- Contact information for support

---

## Deployment Methods

### Method 1: Standard Deployment (Recommended)

For traditional server deployments:

```bash
# 1. Navigate to project directory
cd /path/to/invoice_app

# 2. Pull latest code
git pull origin main

# 3. Activate virtual environment
source api/venv/bin/activate

# 4. Install dependencies
pip install -r api/requirements.txt

# 5. Run deployment script
./api/scripts/deploy_licensing_system.sh production

# 6. Restart services
sudo systemctl restart invoice-api
sudo systemctl restart invoice-ui
```

**Expected Output:**
```
=== Deploying Licensing System ===
Environment: production
[STEP] 1/7 Validating prerequisites...
✓ Public key found
✓ Required packages installed
[STEP] 2/7 Running database migrations...
✓ Master database migration completed
✓ Tenant databases migrated
[STEP] 3/7 Verifying public key embedding...
✓ Public key embedded and loadable
[STEP] 4/7 Configuring feature flags...
✓ Feature flags loaded
[STEP] 5/7 Initializing license system...
✓ License system initialized
[STEP] 6/7 Testing license verification...
✓ License verification tests passed
[STEP] 7/7 Verifying API endpoints...
✓ API endpoints verified
=== Deployment Complete ===
```

### Method 2: Docker Deployment

For containerized deployments:

```bash
# 1. Navigate to project directory
cd /path/to/invoice_app

# 2. Pull latest code
git pull origin main

# 3. Run Docker deployment script
./api/scripts/docker_deploy_licensing.sh

# 4. Verify containers are running
docker-compose ps
```

**Expected Output:**
```
=== Docker Licensing System Deployment ===
Building Docker containers...
✓ Containers built
Running database migrations...
✓ Migrations completed
Initializing license system...
✓ Installation record created
Restarting API service...
✓ API is healthy
=== Deployment Complete ===
```

### Method 3: Manual Deployment

For custom deployments or troubleshooting:

#### Step 1: Run Database Migrations

```bash
cd api
alembic upgrade head
```

#### Step 2: Verify Public Key

```bash
python -c "
from services.license_service import LicenseService
service = LicenseService()
print('Public key loaded successfully')
"
```

#### Step 3: Configure Environment Variables

Add to `.env` or environment:

```bash
# Feature Flags
export FEATURE_AI_INVOICE_ENABLED=true
export FEATURE_AI_EXPENSE_ENABLED=true
export FEATURE_AI_BANK_STATEMENT_ENABLED=true
export FEATURE_AI_CHAT_ENABLED=true
export FEATURE_TAX_INTEGRATION_ENABLED=true
export FEATURE_SLACK_INTEGRATION_ENABLED=true
export FEATURE_CLOUD_STORAGE_ENABLED=true
export FEATURE_SSO_AUTH_ENABLED=true
export FEATURE_APPROVALS_ENABLED=true
export FEATURE_REPORTING_ENABLED=true
export FEATURE_BATCH_PROCESSING_ENABLED=true
export FEATURE_INVENTORY_ENABLED=true
export FEATURE_ADVANCED_SEARCH_ENABLED=true
export FEATURE_CRM_ENABLED=true

# License Settings
export LICENSE_TRIAL_DAYS=30
export LICENSE_GRACE_PERIOD_DAYS=7
export LICENSE_VALIDATION_CACHE_TTL=3600
```

#### Step 4: Initialize License System

```bash
python << 'EOF'
from models.database import SessionLocal
from models.models_per_tenant import InstallationInfo
from datetime import datetime, timedelta

db = SessionLocal()
try:
    installation = InstallationInfo(
        tenant_id=1,
        installation_id=f"inst_{datetime.now().strftime('%Y%m%d')}",
        trial_start_date=datetime.now(),
        trial_end_date=datetime.now() + timedelta(days=30),
        is_trial=True
    )
    db.add(installation)
    db.commit()
    print("Installation record created")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
EOF
```

#### Step 5: Restart Services

```bash
sudo systemctl restart invoice-api
sudo systemctl restart invoice-ui
```

### Method 4: Zero-Downtime Deployment

For production systems requiring zero downtime:

#### Step 1: Deploy to Secondary Server

```bash
# On secondary server
./api/scripts/deploy_licensing_system.sh production
```

#### Step 2: Verify Secondary Server

```bash
curl http://secondary.yourdomain.com/api/v1/license/features
```

#### Step 3: Switch Load Balancer

```bash
# Update load balancer to point to secondary
# (Specific commands depend on your load balancer)
```

#### Step 4: Deploy to Primary Server

```bash
# On primary server
./api/scripts/deploy_licensing_system.sh production
```

#### Step 5: Add Primary Back to Load Balancer

```bash
# Add primary server back to load balancer
```

---

## Post-Deployment Verification

### 1. Check API Health

```bash
curl http://yourdomain.com/health
# Expected: {"status": "healthy"}
```

### 2. Verify License Endpoints

```bash
# Test features endpoint (requires authentication)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://yourdomain.com/api/v1/license/features

# Expected response:
# {
#   "features": {
#     "ai_invoice": true,
#     "ai_expense": true,
#     ...
#   }
# }
```

### 3. Test License Service

```bash
cd api
python -c "
from services.license_service import LicenseService

service = LicenseService()

# Test trial status
trial_status = service.get_trial_status(tenant_id=1)
print(f'Trial Status: {trial_status}')

# Test feature availability
features = service.get_enabled_features(tenant_id=1)
print(f'Enabled Features: {len(features)}')
"
```

### 4. Verify Database Tables

```bash
psql -h localhost -U postgres invoice_master -c "\dt *installation*"
psql -h localhost -U postgres invoice_master -c "\dt *license*"

# Should show:
# installation_info
# license_validation_log
```

### 5. Check UI License Page

1. Navigate to: `http://yourdomain.com/settings/license`
2. Verify trial status is displayed
3. Check feature list is shown
4. Ensure "Activate License" form is present

### 6. Test License Activation

```bash
# Generate test license
cd license_server
python generate_license_cli.py \
  --email test@example.com \
  --name "Test User" \
  --features ai_invoice,ai_expense \
  --duration 365

# Copy license key and activate in UI
# Verify features are enabled
```

### 7. Monitor Logs

```bash
# Check API logs for errors
tail -f /var/log/invoice-api/app.log

# Check for license-related errors
grep -i "license" /var/log/invoice-api/app.log

# Docker logs
docker-compose logs -f api | grep -i license
```

### 8. Performance Check

```bash
# Test response times
time curl http://yourdomain.com/api/v1/license/features

# Should be < 100ms
```

---

## Rollback Procedures

### When to Rollback

Rollback if:
- ❌ Database migration fails
- ❌ API health checks fail
- ❌ License verification errors
- ❌ Critical features broken
- ❌ Performance degradation

### Rollback Steps

#### 1. Stop Services

```bash
sudo systemctl stop invoice-api
sudo systemctl stop invoice-ui

# Or for Docker:
docker-compose down
```

#### 2. Restore Database

```bash
# Restore master database
psql -h localhost -U postgres invoice_master < backup_master_YYYYMMDD.sql

# Restore tenant databases
for backup in backup_tenant_*.sql; do
    db_name=$(echo $backup | sed 's/backup_\(.*\)_[0-9]*.sql/\1/')
    psql -h localhost -U postgres $db_name < $backup
done
```

#### 3. Revert Code

```bash
# Checkout previous version
git checkout <previous-commit-hash>

# Or revert specific commit
git revert <commit-hash>
```

#### 4. Restart Services

```bash
sudo systemctl start invoice-api
sudo systemctl start invoice-ui

# Or for Docker:
docker-compose up -d
```

#### 5. Verify Rollback

```bash
curl http://yourdomain.com/health
# Verify application is working
```

### Partial Rollback

If only database needs rollback:

```bash
# Downgrade database migration
cd api
alembic downgrade -1

# Verify
alembic current
```

---

## Troubleshooting

### Issue: Migration Fails

**Error:** `alembic upgrade head` fails

**Solution:**
```bash
# Check current version
alembic current

# Check migration history
alembic history

# Try upgrading one step at a time
alembic upgrade +1

# Check database connection
psql -h localhost -U postgres invoice_master -c "SELECT 1;"
```

### Issue: Public Key Not Found

**Error:** `Public key not found at api/core/keys/public_key.pem`

**Solution:**
```bash
# Generate keys
cd api
python scripts/generate_license_keys.py

# Verify
ls -la keys/
```

### Issue: License Service Fails to Initialize

**Error:** `License service initialization failed`

**Solution:**
```bash
# Check Python imports
python -c "import jwt; import cryptography; print('OK')"

# Check service directly
python -c "
from services.license_service import LicenseService
service = LicenseService()
print('Service initialized')
"

# Check logs
tail -f /var/log/invoice-api/app.log
```

### Issue: Features Not Showing in UI

**Error:** UI doesn't show licensed features

**Solution:**
```bash
# Check API endpoint
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/license/features

# Clear browser cache
# Hard refresh: Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)

# Check frontend build
cd ui
npm run build

# Restart UI service
sudo systemctl restart invoice-ui
```

### Issue: Docker Container Won't Start

**Error:** API container exits immediately

**Solution:**
```bash
# Check logs
docker-compose logs api

# Check environment variables
docker-compose exec api env | grep FEATURE

# Rebuild container
docker-compose build --no-cache api
docker-compose up -d api
```

### Issue: Database Connection Errors

**Error:** `Could not connect to database`

**Solution:**
```bash
# Check database is running
docker-compose ps postgres-master

# Check connection
psql -h localhost -U postgres invoice_master -c "SELECT 1;"

# Check environment variables
echo $DATABASE_URL

# Restart database
docker-compose restart postgres-master
```

---

## Deployment Checklist

Use this checklist for each deployment:

### Pre-Deployment
- [ ] Code reviewed and approved
- [ ] Tested in staging environment
- [ ] Database backup completed
- [ ] Rollback plan documented
- [ ] Team notified of deployment
- [ ] Maintenance window scheduled (if needed)

### Deployment
- [ ] Pull latest code
- [ ] Run deployment script
- [ ] Monitor deployment logs
- [ ] Verify no errors

### Post-Deployment
- [ ] API health check passes
- [ ] License endpoints accessible
- [ ] UI license page loads
- [ ] Test license activation
- [ ] Monitor logs for errors
- [ ] Performance check passes
- [ ] Team notified of completion

### Rollback (if needed)
- [ ] Stop services
- [ ] Restore database
- [ ] Revert code
- [ ] Restart services
- [ ] Verify rollback successful
- [ ] Document issues
- [ ] Schedule fix deployment

---

## Environment-Specific Notes

### Development

```bash
./api/scripts/deploy_licensing_system.sh development
```

- All features enabled by default
- Trial period: 30 days
- No email notifications
- Local key vault

### Staging

```bash
./api/scripts/deploy_licensing_system.sh staging
```

- Mirror production configuration
- Test with real license keys
- Enable monitoring
- Use staging database

### Production

```bash
./api/scripts/deploy_licensing_system.sh production
```

- Backup before deployment
- Zero-downtime deployment preferred
- Enable all monitoring
- Use production key vault (AWS KMS, Azure KV, etc.)
- Schedule during low-traffic window

---

## Support

### Deployment Issues

- **Email:** devops@yourdomain.com
- **Slack:** #deployments
- **On-Call:** +1-555-0100

### Emergency Rollback

If critical issues occur:
1. Execute rollback immediately
2. Notify team in #incidents
3. Document issue
4. Schedule post-mortem

---

**Last Updated:** November 2025  
**Version:** 1.0  
**Maintainer:** DevOps Team
