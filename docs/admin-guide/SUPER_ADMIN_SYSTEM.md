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
- **Access Control**: Enable or disable organization-wide features or manage their commercial license status.

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

## 4. System Statistics

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
