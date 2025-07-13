# Database-Per-Tenant Migration Guide

This guide walks you through migrating from a single shared database to a database-per-tenant architecture.

## Overview

**Before**: Single PostgreSQL database with tenant isolation via `tenant_id` columns
**After**: Separate PostgreSQL database for each tenant

## Benefits

- **Complete Data Isolation**: Physical separation prevents cross-tenant data access
- **Performance**: Each tenant gets dedicated resources
- **Scalability**: Individual tenant databases can be scaled independently
- **Backup/Recovery**: Tenant-specific backup strategies
- **Compliance**: Easier data residency and privacy requirements
- **Security**: Reduced blast radius of security incidents

## Migration Steps

### 1. Pre-Migration Preparation

#### 1.1 Backup Current Database
```bash
# Create full backup of current database
pg_dump -h localhost -U postgres invoice_app > backup_pre_migration.sql

# Create compressed backup
pg_dump -h localhost -U postgres invoice_app | gzip > backup_pre_migration.sql.gz
```

#### 1.2 Verify Current Setup
```bash
# Check tenant count
psql -h localhost -U postgres -d invoice_app -c "SELECT COUNT(*) as tenant_count FROM tenants;"

# Check data distribution
psql -h localhost -U postgres -d invoice_app -c "
SELECT 
    t.name,
    COUNT(DISTINCT u.id) as users,
    COUNT(DISTINCT c.id) as clients,
    COUNT(DISTINCT i.id) as invoices
FROM tenants t
LEFT JOIN users u ON t.id = u.tenant_id
LEFT JOIN clients c ON t.id = c.tenant_id
LEFT JOIN invoices i ON t.id = i.tenant_id
GROUP BY t.name;
"
```

### 2. Deploy New Architecture

#### 2.1 Update Application Code

1. **Add the new services and middleware**:
   - `api/services/tenant_database_manager.py` ✅
   - `api/middleware/tenant_context_middleware.py` ✅
   - `api/models/database.py` (updated) ✅

2. **Update main.py to use the middleware**:
```python
# Add to your main.py
from middleware.tenant_context_middleware import TenantContextMiddleware

# Add middleware
app.add_middleware(TenantContextMiddleware)
```

#### 2.2 Update Docker Configuration

1. **Use the new docker-compose file**:
```bash
# Copy the new configuration
cp docker-compose-multitenant.yml docker-compose.yml

# Update environment variables
cp api/env.postgresql.example .env
```

2. **Start the new infrastructure**:
```bash
# Stop current services
docker-compose down

# Start new services
docker-compose up -d postgres-master redis

# Wait for health checks
docker-compose ps
```

### 3. Run Migration

#### 3.1 Test Migration (Dry Run)
```bash
# Run migration in dry-run mode first
docker-compose --profile migration run --rm migration python scripts/migrate_to_db_per_tenant.py --dry-run

# Or run directly
cd api
python scripts/migrate_to_db_per_tenant.py --dry-run --verbose
```

#### 3.2 Execute Migration
```bash
# Run actual migration
docker-compose --profile migration run --rm migration python scripts/migrate_to_db_per_tenant.py

# Or run directly
cd api
python scripts/migrate_to_db_per_tenant.py --verbose
```

#### 3.3 Verify Migration
```bash
# Check created databases
docker-compose exec postgres-master psql -U postgres -c "SELECT datname FROM pg_database WHERE datname LIKE 'tenant_%';"

# Check data in tenant databases
docker-compose exec postgres-master psql -U postgres -d tenant_1 -c "SELECT COUNT(*) FROM users;"
docker-compose exec postgres-master psql -U postgres -d tenant_1 -c "SELECT COUNT(*) FROM clients;"
docker-compose exec postgres-master psql -U postgres -d tenant_1 -c "SELECT COUNT(*) FROM invoices;"
```

### 4. Start Application

#### 4.1 Deploy Application
```bash
# Start all services
docker-compose up -d

# Check health
docker-compose ps
curl http://localhost:8000/health
```

#### 4.2 Test Application
```bash
# Test authentication
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password"}'

# Test tenant-specific data access
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/clients
```

### 5. Post-Migration Tasks

#### 5.1 Update Authentication
The middleware automatically handles tenant context, but you may need to update:
- JWT secret key configuration
- Token expiration settings
- User registration flow

#### 5.2 Monitor Performance
```bash
# Check database connections
docker-compose exec postgres-master psql -U postgres -c "SELECT datname, numbackends FROM pg_stat_database WHERE datname LIKE 'tenant_%';"

# Monitor logs
docker-compose logs -f api
```

#### 5.3 Set Up Backup Strategy
```bash
# Create backup script for all tenant databases
docker-compose --profile backup run --rm backup

# Schedule regular backups
crontab -e
# Add: 0 2 * * * docker-compose --profile backup run --rm backup
```

## Configuration Files

### Environment Variables
```bash
# Master database
DATABASE_URL=postgresql://postgres:password@postgres-master:5432/invoice_master

# Multi-tenant settings
MULTITENANT_MODE=database_per_tenant
TENANT_DATABASE_PREFIX=tenant_
MASTER_DATABASE_HOST=postgres-master
MASTER_DATABASE_PORT=5432
MASTER_DATABASE_USER=postgres
MASTER_DATABASE_PASSWORD=password

# JWT settings
SECRET_KEY=your-super-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Updated Models
The new models in `api/models/models_per_tenant.py` remove all `tenant_id` columns since each tenant has its own database.

## Troubleshooting

### Common Issues

1. **Migration fails with "tenant database already exists"**:
   ```bash
   # Drop existing tenant databases
   docker-compose exec postgres-master psql -U postgres -c "DROP DATABASE IF EXISTS tenant_1;"
   ```

2. **Application can't connect to tenant database**:
   ```bash
   # Check if tenant database exists
   docker-compose exec postgres-master psql -U postgres -c "SELECT datname FROM pg_database WHERE datname LIKE 'tenant_%';"
   
   # Check middleware logs
   docker-compose logs api | grep -i tenant
   ```

3. **Authentication fails**:
   ```bash
   # Check if master database has user records
   docker-compose exec postgres-master psql -U postgres -d invoice_master -c "SELECT email, tenant_id FROM master_users;"
   ```

4. **Performance issues**:
   ```bash
   # Check connection pool usage
   docker-compose exec postgres-master psql -U postgres -c "SELECT datname, numbackends FROM pg_stat_database;"
   
   # Monitor slow queries
   docker-compose exec postgres-master psql -U postgres -c "SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
   ```

## Rollback Plan

If you need to rollback:

1. **Stop new services**:
   ```bash
   docker-compose down
   ```

2. **Restore original database**:
   ```bash
   # Restore from backup
   psql -h localhost -U postgres -d invoice_app < backup_pre_migration.sql
   ```

3. **Revert code changes**:
   ```bash
   git checkout HEAD~1 -- api/models/database.py
   git checkout HEAD~1 -- api/main.py
   ```

4. **Use original docker-compose**:
   ```bash
   git checkout HEAD~1 -- docker-compose.yml
   docker-compose up -d
   ```

## Performance Considerations

### Database Connections
- Each tenant database maintains its own connection pool
- Monitor total connection usage across all databases
- Adjust pool sizes based on usage patterns

### Memory Usage
- More databases = more memory usage
- Monitor PostgreSQL memory usage
- Consider using connection pooling (PgBouncer)

### Backup Strategy
- Create individual backup schedules for each tenant
- Consider compressed backups for large tenants
- Test restore procedures regularly

## Security Considerations

1. **Database Access**: Each tenant database should have restricted access
2. **Connection Security**: Use SSL connections in production
3. **Backup Security**: Encrypt backup files
4. **Monitoring**: Set up alerts for unusual database activity

## Monitoring and Maintenance

### Key Metrics to Monitor
- Database connection counts per tenant
- Query performance across tenant databases
- Disk usage per tenant database
- Memory usage patterns

### Regular Maintenance
- Update statistics on tenant databases
- Monitor and optimize slow queries
- Clean up unused connections
- Regular backup verification

## Next Steps

After successful migration:
1. Update documentation for new architecture
2. Train team on new deployment procedures
3. Set up monitoring and alerting
4. Plan for new tenant onboarding process
5. Consider implementing database sharding if needed

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review application logs: `docker-compose logs -f api`
3. Check database logs: `docker-compose logs -f postgres-master`
4. Verify network connectivity between services 