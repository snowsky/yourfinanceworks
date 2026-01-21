# User to MasterUser Migration: Database-Per-Tenant Architecture

## Overview

This document explains the architectural migration from a shared database model to a **database-per-tenant architecture** and the critical change from a single `User` model to separate `User` and `MasterUser` models.

## Architecture Comparison

### Before: Single Shared Database

- All tenants shared one database with `tenant_id` columns for isolation
- Single `User` model with `tenant_id` foreign key
- Tenant isolation was enforced at the application level
- Risk of cross-tenant data access through application bugs or SQL injection

### After: Database-Per-Tenant

- Each tenant gets their own separate PostgreSQL database
- **Two User models**:
  - `MasterUser`: Stored in master database, handles authentication and cross-tenant operations
  - `User` (in `models_per_tenant.py`): Stored in individual tenant databases, no `tenant_id` needed
- Physical database separation ensures complete tenant isolation

## Why This Change Was Necessary

The User → MasterUser change is **absolutely necessary** for several critical reasons:

### 1. Complete Data Isolation

**Before (Shared Database):**

```python
# Single database with tenant_id filtering - risky
users = db.query(User).filter(User.tenant_id == current_tenant_id).all()
```

**After (Database-Per-Tenant):**

```python
# Physical database separation - secure
# MasterUser for auth, then switch to tenant database
set_tenant_context(current_user.tenant_id)
tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
users = tenant_db.query(User).all()  # No tenant_id needed
```

### 2. Security Benefits

- **Blast Radius Reduction**: A security breach in one tenant cannot access another tenant's data
- **Physical Separation**: No possibility of accidental cross-tenant data access through SQL injection or application bugs
- **Compliance**: Easier to meet data residency and privacy requirements (GDPR, HIPAA, etc.)
- **Zero Trust**: Physical separation eliminates trust in application-level filtering

### 3. Performance and Scalability

- Each tenant gets dedicated database resources
- Independent scaling per tenant
- Reduced query complexity (no tenant_id filtering needed)
- Better index performance within tenant databases

### 4. Operational Benefits

- Tenant-specific backup and recovery strategies
- Individual database maintenance windows
- Easier debugging and troubleshooting
- Independent database schema evolution if needed

## Authentication Flow

1. **Login**: User authenticates against `master_users` table in master database
2. **Token**: JWT contains user email, resolved to `MasterUser` with `tenant_id`
3. **Request**: Middleware or endpoint extracts `tenant_id` from `MasterUser`
4. **Context Switch**: Application switches to appropriate tenant database
5. **Operations**: Use tenant-specific `User` model for operations within tenant

## Model Definitions

### MasterUser (Master Database)

```python
# api/models/models.py
class MasterUser(Base):
    __tablename__ = "master_users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    role = Column(String, default="user")  # admin, user, viewer
    # ... other fields
```

### User (Tenant Database)

```python
# api/models/models_per_tenant.py
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")  # admin, user, viewer
    # No tenant_id needed - physical separation
```

## Implementation Details

### Middleware Changes

The tenant context middleware now skips most endpoints, allowing manual tenant context management:

```python
# api/middleware/tenant_context_middleware.py
# Skip tenant context for endpoints that handle it manually
if (request.url.path.startswith("/api/v1/clients") or
    request.url.path.startswith("/api/v1/invoices") or
    request.url.path.startswith("/api/v1/payments")):
    return await call_next(request)
```

### Endpoint Pattern

Each endpoint manually handles tenant context for precise control:

```python
@router.get("/")
async def read_clients(
    current_user: MasterUser = Depends(get_current_user)
):
    # Manually set tenant context and get tenant database
    set_tenant_context(current_user.tenant_id)
    tenant_session = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    db = tenant_session()
    
    try:
        # Operations use tenant-specific User model
        clients = db.query(Client).all()  # No tenant_id filtering needed
        return clients
    finally:
        db.close()
```

### Authentication Changes

The `get_current_user` function now returns `MasterUser`:

```python
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_master_db)  # Uses master database
):
    # Decode JWT and get user from master database
    user = db.query(MasterUser).filter(MasterUser.email == email).first()
    return user
```

## Benefits of This Architecture

### Security

- ✅ **True Multi-tenancy**: Physical data separation
- ✅ **Zero Cross-tenant Risk**: Impossible to access other tenant's data
- ✅ **Compliance Ready**: Easier regulatory compliance
- ✅ **Audit Trail**: Clear separation of tenant operations

### Performance

- ✅ **Dedicated Resources**: Each tenant gets its own database resources
- ✅ **Optimized Queries**: No tenant_id filtering overhead
- ✅ **Better Indexing**: Indexes don't span multiple tenants
- ✅ **Independent Scaling**: Scale individual tenant databases

### Operations

- ✅ **Tenant-specific Backups**: Independent backup strategies
- ✅ **Maintenance Windows**: Per-tenant maintenance schedules
- ✅ **Debugging**: Easier to isolate tenant-specific issues
- ✅ **Schema Evolution**: Independent schema changes if needed

### Scalability

- ✅ **Horizontal Scaling**: Add new tenant databases easily
- ✅ **Resource Allocation**: Allocate resources based on tenant needs
- ✅ **Geographic Distribution**: Place tenant databases closer to users
- ✅ **Independent Growth**: Tenants don't affect each other's performance

## Super Admin Features

The master database enables powerful super admin capabilities:

```python
# Cross-tenant user management
@router.get("/users")
async def list_all_users(
    current_user: MasterUser = Depends(require_super_admin)
):
    # Can access all tenants from master database
    users = master_db.query(MasterUser).all()
    return users
```

## Migration Considerations

### User Synchronization

Users exist in both databases with synchronized data:

- Master database: Authentication, tenant association, cross-tenant operations
- Tenant database: Tenant-specific operations, relationships, audit trails

### Data Consistency

The system maintains consistency by:

- Creating users in both databases during registration
- Updating both databases when user data changes
- Using the same user ID across both databases

## Conclusion

The User to MasterUser migration is not just a refactoring—it's a fundamental architectural improvement that provides:

1. **True Security**: Physical data separation eliminates cross-tenant risks
2. **Better Performance**: Dedicated resources and optimized queries
3. **Operational Excellence**: Independent backup, scaling, and maintenance
4. **Compliance**: Easier to meet regulatory requirements
5. **Future-Proof**: Scalable architecture for growth

This architecture follows multi-tenant best practices and provides a solid foundation for enterprise-grade applications. The additional complexity is justified by the significant security, performance, and operational benefits it provides.

## Related Documentation

- [Database Migration Guide](DATABASE_MIGRATION_GUIDE_Multitenants.md)
- [Tenant Context Error Handling](TENANT_CONTEXT_ERROR_HANDLING.md)
- [Troubleshooting Missing Tenant Databases](TROUBLESHOOTING_MISSING_TENANT_DATABASES.md)
