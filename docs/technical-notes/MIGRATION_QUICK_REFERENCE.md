# Migration Quick Reference

## Quick Commands

### Initial Setup
```bash
# Create initial migrations and set up schema
./scripts/migrate.sh init
./scripts/migrate.sh setup
```

### Create Migrations
```bash
# Master database
./scripts/migrate.sh create "Description" --master

# Tenant database  
./scripts/migrate.sh create "Description" --tenant
```

### Apply Migrations
```bash
# Master database
./scripts/migrate.sh upgrade --master

# Specific tenant
./scripts/migrate.sh upgrade --tenant 1

# All tenants
./scripts/migrate.sh upgrade --all-tenants
```

### Check Status
```bash
# Master database
./scripts/migrate.sh current --master

# Specific tenant
./scripts/migrate.sh current --tenant 1
```

### Docker Commands
```bash
# Replace ./scripts/migrate.sh with ./scripts/docker_migrate.sh
./scripts/docker_migrate.sh init
./scripts/docker_migrate.sh upgrade --all-tenants
```

## File Structure
```
api/
├── alembic/
│   ├── versions/           # Migration files
│   └── env.py             # Configuration
├── alembic.ini            # Alembic config
└── scripts/
    ├── manage_migrations.py # Python script
    ├── migrate.sh          # Shell wrapper
    └── docker_migrate.sh   # Docker wrapper
```

## Environment Variables
- `ALEMBIC_DB_TYPE`: 'master' or 'tenant'
- `TENANT_ID`: Tenant ID for tenant migrations
- `DATABASE_URL`: Database connection string

## Common Workflows

### Adding New Feature
1. Create master migration (if needed)
2. Create tenant migration
3. Apply master migration
4. Apply tenant migrations to all tenants

### Emergency Rollback
```bash
# One step back
./scripts/migrate.sh downgrade --master

# To specific revision
./scripts/migrate.sh downgrade --master --revision abc123
```

### Check All Tenant Status
```python
python scripts/example_migration_usage.py --demo
```