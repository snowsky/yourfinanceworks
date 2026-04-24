# Super Admin System Guide

The Super Admin system provides comprehensive management capabilities for multi-tenant environments, ensuring system-wide visibility and control.

## Overview

The Super Admin interface is a protected system available only to users with the `super_user` flag. It allows for the management of all organizations (tenants), system-wide user oversight, and database health monitoring.

## Automatic Super User Creation

The first user to sign up in a fresh system is automatically granted Super User privileges and assigned the `admin` role. This ensures there is always at least one system administrator.

## Creating a Super User

If you prefer to create a Super User explicitly, use the script below after services are running.

```bash
# Run in the API container
docker-compose exec api python scripts/create_super_user.py
```

Or run it manually from your host:

```bash
cd api
python scripts/create_super_user.py
```

## 1. Tenant Management

Manage the lifecycle of organizations in your system.

- **Organization Creation**: Manually onboard new businesses or clients.
- **Tenant Monitoring**: View statistics and health for each individual organization.
- **Storage Visibility**: View each organization's PostgreSQL database size and known attachment payload size from the Organizations table.
- **Access Control**: Enable or disable organization-wide features or manage their commercial license status.

### Organization Size Reporting

The Super Admin Dashboard -> Organizations table includes a storage summary for each organization:

- **DB**: The PostgreSQL database size returned by `pg_database_size`. This includes the tenant schema, system catalog overhead, indexes, TOAST tables, and stored data. Empty tenant databases commonly show a non-zero baseline such as 10-20 MB.
- **files**: The sum of attachment file sizes recorded in tenant metadata tables, including invoice, expense, bank statement, inventory item, and batch-processing attachments.
- **total**: The displayed primary size is `DB + files`.

The list view intentionally does not recursively scan local attachment folders or cloud buckets on every page load. Local and cloud attachments are counted when their database rows have `file_size` populated. Orphaned files without attachment metadata, or older records missing `file_size`, are not included in the list total.

For exact cloud-provider billing usage, use provider-native bucket/container reporting or a background storage usage job that periodically scans cloud storage and stores cached totals. The Super Admin Organizations table is designed for fast operational visibility, not billing-grade storage reconciliation.

## 2. Cross-Tenant User Oversight

A global view of your entire user base.

- **User Inventory**: Search for and manage users across all tenant databases from a single interface.
- **Role Assignments**: Elevate users to Admin or Super User status.
- **Join Requests**: Approve or deny requests from users wanting to join specific organizations.

## 3. Database Health & Management

Ensure the stability of the underlying data infrastructure.

- **Real-Time Monitoring**: View the health status of every tenant database.
- **Auto-Recovery Tools**: Use built-in diagnostics to detect and fix missing or corrupted tenant databases on the fly.
- **Database Operations**: Trigger backups or database migrations across the entire multi-tenant fleet.

## 4. FinanceWorks Insights (AI Forensic Auditor)

System-wide oversight and fraud detection powered by AI.

- **Enterprise-Grade Fraud Detection**: AI-powered "Senior Auditor" that monitors every invoice, expense, and bank transaction for anomalies
- **Risk Scoring System**: Automated risk assessment (Low, Medium, High) with detailed forensic reasoning for each flagged transaction
- **Advanced Detection Rules**: Protection against phantom vendors, duplicate billing, threshold splitting, rounding anomalies, description mismatches, and temporal anomalies
- **Attachment Integrity Analysis**: AI analysis of receipts and invoices for signs of digital tampering or formatting inconsistencies
- **System-Wide Audit Logs**: Permanent, defensible audit trails creating comprehensive paper trails for external auditors
- **Full System Audit**: Trigger reprocessing of historical data when policies change or new detection rules are deployed

**Enterprise License Required**: FinanceWorks Insights requires an Enterprise-tier license and is enabled globally via Settings → AI Configuration.

## 5. System Level Licensing

Manage commercial licensing and feature access across the entire platform.

- **License Tier Management**: Configure and assign license tiers (Free, Professional, Enterprise) to individual organizations
- **Feature Gate Control**: Enable or disable premium features like FinanceWorks Insights, advanced analytics, and plugin management per tenant
- **License Compliance Monitoring**: Track usage and ensure organizations remain within their licensed limits
- **Automated License Enforcement**: System automatically restricts access to features based on current license status
- **License Analytics**: View system-wide license distribution, revenue tracking, and upgrade opportunities
- **Bulk License Operations**: Apply license changes across multiple organizations simultaneously

## 6. System Statistics

Get a "Bird's Eye" view of your platform's usage.

- **Global Metrics**: Total number of tenants, active users, invoices generated, and payments processed system-wide.
- **Resource Usage**: Monitor system performance and database resource consumption.

---

### Accessing the Dashboard

The Super Admin dashboard is available at the `/super-admin` route. You must be logged in as a user with Super User privileges to access this area.

### Database Management Tools

Fix missing or corrupted tenant databases using the built-in scripts:

```bash
# Check for missing databases
docker-compose exec api python scripts/fix_missing_tenant_databases.py check

# List all databases
docker-compose exec api python scripts/fix_missing_tenant_databases.py list

# Recreate missing databases
docker-compose exec api python scripts/fix_missing_tenant_databases.py recreate

# Or use the shell script
./api/scripts/run_fix_missing_databases.sh
```

### Emergency Procedures

For critical database issues, refer to the [Database Troubleshooting Guide](../technical-notes/TROUBLESHOOTING_MISSING_TENANT_DATABASES.md) in the technical archive for specific CLI scripts and recovery protocols.
