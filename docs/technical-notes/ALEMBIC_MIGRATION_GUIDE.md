# Alembic Migration Guide for Multi-Tenant Invoice Application

This guide explains how to use Alembic for database migrations in the multi-tenant invoice application. The system supports separate migrations for the master database (tenant management) and individual tenant databases.

## Overview

The application uses a **database-per-tenant** architecture:
- **Master Database**: Stores tenant metadata, super users, and cross-tenant information
- **Tenant Databases**: Each tenant has its own isolated database (e.g., `tenant_1`, `tenant_2`)

## Migration Structure

```
api/
├── alembic/
│   ├── versions/           # Migration files
│   ├── env.py             # Alembic environment configuration
│   └── script.py.mako     # Migration template
├── alembic.ini            # Alembic configuration
├── models/
│   ├── models.py          # Master database models
│   └── models_per_tenant.py # Tenant database models
└── scripts/
    ├── manage_migrations.py # Python migration management
    ├── migrate.sh          # Shell script wrapper
    └── docker_migrate.sh   # Docker migration script
```

## Quick Start

### 1. Initialize Migrations

Create initial migration files for both master and tenant databases:

```bash
# Using shell script
./scripts/migrate.sh init

# Using Python script directly
python scripts/manage_migrations.py init

# Using Docker
./scripts/docker_migrate.sh init
```

### 2. Set Up Database Schema

Apply migrations to set up the database schema:

```bash
# Using shell script
./scripts/migrate.sh setup

# Using Python script directly
python scripts/manage_migrations.py setup

# Using Docker
./scripts/docker_migrate.sh setup
```

## Migration Commands

### Creating Migrations

#### Master Database Migration
```bash
# Shell script
./scripts/migrate.sh create "Add new master table" --master

# Python script
python scripts/manage_migrations.py create "Add new master table" --type master

# Docker
./scripts/docker_migrate.sh create "Add new master table" --master
```

#### Tenant Database Migration
```bash
# Shell script
./scripts/migrate.sh create "Add invoice items table" --tenant

# Python script
python scripts/manage_migrations.py create "Add invoice items table" --type tenant

# Docker
./scripts/docker_migrate.sh create "Add invoice items table" --tenant
```

### Upgrading Databases

#### Master Database
```bash
# Shell script
./scripts/migrate.sh upgrade --master

# Python script
python scripts/manage_migrations.py upgrade --type master

# Docker
./scripts/docker_migrate.sh upgrade --master
```

#### Specific Tenant Database
```bash
# Shell script
./scripts/migrate.sh upgrade --tenant 1

# Python script
python scripts/manage_migrations.py upgrade --type tenant --tenant-id 1

# Docker
./scripts/docker_migrate.sh upgrade --tenant 1
```

#### All Tenant Databases
```bash
# Shell script
./scripts/migrate.sh upgrade --all-tenants

# Python script
python scripts/manage_migrations.py upgrade --type all

# Docker
./scripts/docker_migrate.sh upgrade --all-tenants
```

### Checking Migration Status

#### Current Revision
```bash
# Master database
./scripts/migrate.sh current --master

# Specific tenant
./scripts/migrate.sh current --tenant 1
```

#### Migration History
```bash
# Master database
./scripts/migrate.sh history --master

# Specific tenant
./scripts/migrate.sh history --tenant 1
```

### Downgrading Databases

```bash
# Master database (one step back)
./scripts/migrate.sh downgrade --master

# Specific tenant (to specific revision)
./scripts/migrate.sh downgrade --tenant 1 --revision abc123

# Master database (to specific revision)
./scripts/migrate.sh downgrade --master --revision def456
```

## Environment Variables

The migration system uses these environment variables:

- `DATABASE_URL`: Master database connection string
- `ALEMBIC_DB_TYPE`: Set to 'master' or 'tenant' to specify which database to migrate
- `TENANT_ID`: Tenant ID for tenant-specific migrations

## Docker Integration

### Prerequisites

1. Start Docker services:
```bash
docker-compose up -d
```

2. Ensure the API container is running:
```bash
docker-compose ps api
```

### Running Migrations in Docker

Use the `docker_migrate.sh` script to run migrations inside Docker containers:

```bash
# Initialize migrations
./scripts/docker_migrate.sh init

# Set up database schema
./scripts/docker_migrate.sh setup

# Create new migration
./scripts/docker_migrate.sh create "Add new feature" --master

# Upgrade all tenant databases
./scripts/docker_migrate.sh upgrade --all-tenants
```

## Advanced Usage

### Manual Alembic Commands

You can also run Alembic commands directly with environment variables:

```bash
# Master database migration
ALEMBIC_DB_TYPE=master python -m alembic upgrade head

# Tenant database migration
ALEMBIC_DB_TYPE=tenant TENANT_ID=1 python -m alembic upgrade head

# Create master database migration
ALEMBIC_DB_TYPE=master python -m alembic revision --autogenerate -m "Add new table"
```

### Custom Migration Scripts

For complex migrations, you can create custom Python scripts:

```python
#!/usr/bin/env python3
"""Custom migration script example"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.append(str(Path(__file__).parent.parent))

from models.database import SessionLocal
from models.models import Tenant
from scripts.manage_migrations import upgrade_database

def custom_migration():
    """Run custom migration logic"""
    
    # Get all tenants
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        
        for tenant in tenants:
            print(f"Processing tenant {tenant.id}...")
            
            # Run specific migration for this tenant
            upgrade_database('tenant', tenant.id, 'specific_revision')
            
            # Add custom logic here
            # ...
            
    finally:
        db.close()

if __name__ == "__main__":
    custom_migration()
```

## Best Practices

### 1. Always Test Migrations

- Test migrations on a copy of production data
- Use downgrade functionality to test rollback scenarios
- Verify data integrity after migrations

### 2. Migration Naming

Use descriptive names for migrations:
```bash
# Good
./scripts/migrate.sh create "Add user authentication table" --master
./scripts/migrate.sh create "Add invoice soft delete fields" --tenant

# Bad
./scripts/migrate.sh create "Update" --master
```

### 3. Backup Before Major Migrations

```bash
# Backup master database
pg_dump invoice_master > backup_master_$(date +%Y%m%d_%H%M%S).sql

# Backup tenant databases
for i in {1..10}; do
    pg_dump tenant_$i > backup_tenant_${i}_$(date +%Y%m%d_%H%M%S).sql
done
```

### 4. Coordinate Master and Tenant Migrations

When adding features that affect both master and tenant databases:

1. Create master database migration first
2. Create tenant database migration second
3. Apply master migration first
4. Apply tenant migrations to all tenants

### 5. Handle Migration Failures

If a migration fails on some tenants:

```bash
# Check which tenants failed
./scripts/migrate.sh current --tenant 1
./scripts/migrate.sh current --tenant 2
# ... check all tenants

# Fix the issue and retry
./scripts/migrate.sh upgrade --tenant 1
```

## Troubleshooting

### Common Issues

#### 1. "No module named alembic"
```bash
pip install alembic
```

#### 2. "Target database is not up to date"
```bash
# Check current revision
./scripts/migrate.sh current --master

# Upgrade to latest
./scripts/migrate.sh upgrade --master
```

#### 3. "Tenant database not found"
```bash
# Check if tenant exists in master database
python scripts/fix_missing_tenant_databases.py check

# Recreate missing tenant databases
python scripts/fix_missing_tenant_databases.py recreate
```

#### 4. Migration conflicts
```bash
# Check migration history
./scripts/migrate.sh history --master

# Resolve conflicts by creating a merge migration
ALEMBIC_DB_TYPE=master python -m alembic merge -m "Merge conflicting migrations" head1 head2
```

### Debugging

Enable verbose logging:

```bash
# Set log level in alembic.ini
[logger_alembic]
level = DEBUG

# Or use environment variable
ALEMBIC_LOG_LEVEL=DEBUG ./scripts/migrate.sh upgrade --master
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Database Migrations

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  migrate:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
          POSTGRES_DB: invoice_master
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        cd api
        pip install -r requirements.txt
    
    - name: Run migrations
      env:
        DATABASE_URL: postgresql://postgres:password@localhost:5432/invoice_master
      run: |
        cd api
        python scripts/manage_migrations.py init
        python scripts/manage_migrations.py setup
```

## Monitoring and Maintenance

### Regular Tasks

1. **Monitor Migration Status**: Regularly check that all tenant databases are up to date
2. **Clean Up Old Migrations**: Remove old migration files that are no longer needed
3. **Performance Monitoring**: Monitor migration performance, especially for large datasets
4. **Backup Strategy**: Ensure regular backups before running migrations

### Automated Checks

Create a script to check migration status across all tenants:

```python
#!/usr/bin/env python3
"""Check migration status across all tenants"""

from models.database import SessionLocal
from models.models import Tenant
from scripts.manage_migrations import show_current_revision

def check_all_tenants():
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        
        print("Migration Status Report")
        print("=" * 50)
        
        # Check master database
        print("Master Database:")
        show_current_revision('master')
        print()
        
        # Check all tenant databases
        for tenant in tenants:
            print(f"Tenant {tenant.id} ({tenant.name}):")
            show_current_revision('tenant', tenant.id)
            print()
            
    finally:
        db.close()

if __name__ == "__main__":
    check_all_tenants()
```

This comprehensive migration system provides robust database schema management for your multi-tenant invoice application while maintaining data isolation and consistency across all tenant databases.