# Super Admin System Guide

The Super Admin system provides comprehensive management capabilities for multi-tenant environments, ensuring system-wide visibility and control.

## Overview

The Super Admin interface is a protected system available only to users with the `super_user` flag. It allows for the management of all organizations (tenants), system-wide user oversight, and database health monitoring.

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

### Emergency Procedures

For critical database issues, refer to the [Database Troubleshooting Guide](../technical-notes/TROUBLESHOOTING_MISSING_TENANT_DATABASES.md) in the technical archive for specific CLI scripts and recovery protocols.
