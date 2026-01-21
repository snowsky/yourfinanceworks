# Business Features Implementation Guide

## Overview

This guide provides code to restrict business-only features for personal users.

## Phase 1: API Keys Restriction (Immediate)

### Step 1: Add Feature Gate Decorator

```python
# api/utils/business_feature_gate.py
from functools import wraps
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from models.database import get_db
from routers.auth import get_current_user
from services.license_service import LicenseService

def require_business_license(feature_name: str):
    """
    Decorator to restrict endpoints to business license holders.
    
    Usage:
        @require_business_license("api_access")
        async def create_api_key(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract db and current_user from kwargs
            db = kwargs.get('db')
            current_user = kwargs.get('current_user')
            
            if not db or not current_user:
                raise HTTPException(
                    status_code=500,
                    detail="Missing required dependencies"
                )
            
            # Check license status
            license_service = LicenseService(db)
            status = license_service.get_license_status()
            
            # Allow for business trial and active licenses
            if status["license_status"] in ["trial", "active"]:
                return await func(*args, **kwargs)
            
            # Deny for personal and invalid licenses
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "BUSINESS_FEATURE_REQUIRED",
                    "message": f"{feature_name} is only available with a business license.",
                    "feature": feature_name,
                    "current_license": status["license_status"],
                    "upgrade_url": "/license-management?upgrade=true",
                    "trial_available": status["license_status"] == "personal"
                }
            )
        
        return wrapper
    return decorator


def check_business_feature(feature_id: str, db: Session) -> bool:
    """
    Check if a business feature is available.
    
    Args:
        feature_id: Feature identifier (e.g., "api_access", "batch_processing")
        db: Database session
        
    Returns:
        True if feature is available, False otherwise
    """
    license_service = LicenseService(db)
    status = license_service.get_license_status()
    
    # Business features available for trial and active licenses
    return status["license_status"] in ["trial", "active"]
```

### Step 2: Protect API Key Endpoints

```python
# api/routers/api_keys.py (or wherever your API key routes are)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db
from routers.auth import get_current_user
from utils.business_feature_gate import require_business_license, check_business_feature

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

@router.post("/")
@require_business_license("API Access")
async def create_api_key(
    key_data: APIKeyCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new API key.
    
    **Business Feature**: Requires business license or trial.
    """
    # Your existing API key creation logic
    pass

@router.get("/")
async def list_api_keys(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List API keys.
    
    Returns empty list for personal users with upgrade prompt.
    """
    # Check if business feature is available
    if not check_business_feature("api_access", db):
        return {
            "api_keys": [],
            "business_feature": True,
            "message": "API keys are a business feature. Upgrade to create API keys.",
            "upgrade_url": "/license-management?upgrade=true"
        }
    
    # Your existing list logic
    pass

@router.delete("/{key_id}")
@require_business_license("API Access")
async def delete_api_key(
    key_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an API key."""
    # Your existing delete logic
    pass
```

### Step 3: Protect API Key Authentication

```python
# api/middleware/external_api_auth_middleware.py
# Update your existing API key authentication

from services.license_service import LicenseService

async def verify_api_key(api_key: str, db: Session):
    """Verify API key and check license status"""
    
    # Your existing API key verification logic
    # ...
    
    # After verifying the API key is valid, check license
    license_service = LicenseService(db)
    status = license_service.get_license_status()
    
    if status["license_status"] not in ["trial", "active"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "BUSINESS_LICENSE_REQUIRED",
                "message": "API access requires a business license. Your license status: " + status["license_status"],
                "upgrade_url": "/license-management?upgrade=true"
            }
        )
    
    return api_key_object
```

## Phase 2: Multi-User Access Restriction

### Step 1: Restrict User Creation

```python
# api/routers/users.py (or admin routes)
from utils.business_feature_gate import check_business_feature

@router.post("/users")
async def create_user(
    user_data: UserCreate,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new user."""
    
    # Check current user count
    user_count = db.query(User).count()
    
    # Personal license allows only 1 user
    if not check_business_feature("multi_user", db):
        if user_count >= 1:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "BUSINESS_FEATURE_REQUIRED",
                    "message": "Multi-user access requires a business license.",
                    "feature": "Multi-User Access",
                    "current_users": user_count,
                    "max_users_personal": 1,
                    "upgrade_url": "/license-management?upgrade=true"
                }
            )
    
    # Your existing user creation logic
    pass
```

## Phase 3: Batch Processing Restriction

### Step 1: Protect Batch Endpoints

```python
# api/routers/batch_processing.py
from utils.business_feature_gate import require_business_license

@router.post("/batch")
@require_business_license("Batch Processing")
async def create_batch_job(
    files: List[UploadFile],
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a batch processing job.
    
    **Business Feature**: Requires business license or trial.
    """
    # Your existing batch processing logic
    pass
```

### Step 2: Add File Count Check

```python
# api/routers/expenses.py or invoices.py
@router.post("/upload-multiple")
async def upload_multiple_files(
    files: List[UploadFile],
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload multiple files."""
    
    # Personal users can only upload 1 file at a time
    if not check_business_feature("batch_processing", db):
        if len(files) > 1:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "BUSINESS_FEATURE_REQUIRED",
                    "message": "Batch file upload requires a business license. Personal users can upload 1 file at a time.",
                    "feature": "Batch Processing",
                    "files_attempted": len(files),
                    "max_files_personal": 1,
                    "upgrade_url": "/license-management?upgrade=true"
                }
            )
    
    # Your existing upload logic
    pass
```

## Phase 4: Webhook Restriction

### Step 1: Protect Webhook Endpoints

```python
# api/routers/webhooks.py
from utils.business_feature_gate import require_business_license

@router.post("/webhooks")
@require_business_license("Webhooks")
async def create_webhook(
    webhook_data: WebhookCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a webhook endpoint.
    
    **Business Feature**: Requires business license or trial.
    """
    # Your existing webhook creation logic
    pass

@router.get("/webhooks")
async def list_webhooks(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List webhooks with business feature check."""
    
    if not check_business_feature("webhooks", db):
        return {
            "webhooks": [],
            "business_feature": True,
            "message": "Webhooks are a business feature. Upgrade to create webhooks.",
            "upgrade_url": "/license-management?upgrade=true"
        }
    
    # Your existing list logic
    pass
```

## Phase 5: Approval Workflows Restriction

### Step 1: Protect Approval Endpoints

```python
# api/routers/approvals.py
from utils.business_feature_gate import require_business_license

@router.post("/approval-workflows")
@require_business_license("Approval Workflows")
async def create_approval_workflow(
    workflow_data: ApprovalWorkflowCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create an approval workflow.
    
    **Business Feature**: Requires business license or trial.
    """
    # Your existing workflow creation logic
    pass

@router.post("/expenses/{expense_id}/submit-for-approval")
@require_business_license("Approval Workflows")
async def submit_expense_for_approval(
    expense_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit expense for approval."""
    # Your existing approval logic
    pass
```

## Phase 6: Recurring Invoices Restriction

### Step 1: Protect Recurring Invoice Creation

```python
# api/routers/invoices.py
from utils.business_feature_gate import check_business_feature

@router.post("/invoices")
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create an invoice."""
    
    # Check if trying to create recurring invoice
    if invoice_data.is_recurring:
        if not check_business_feature("recurring_invoices", db):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "BUSINESS_FEATURE_REQUIRED",
                    "message": "Recurring invoices require a business license.",
                    "feature": "Recurring Invoices",
                    "upgrade_url": "/license-management?upgrade=true"
                }
            )
    
    # Your existing invoice creation logic
    pass
```

## Phase 7: Cloud Storage Restriction

### Step 1: Check License Before Cloud Upload

```python
# api/services/cloud_storage_service.py
from services.license_service import LicenseService

class CloudStorageService:
    def upload_file(self, file, db: Session):
        """Upload file to cloud storage."""
        
        # Check if cloud storage is available
        license_service = LicenseService(db)
        status = license_service.get_license_status()
        
        if status["license_status"] not in ["trial", "active"]:
            raise Exception(
                "Cloud storage is only available with a business license. "
                "Personal users can use local storage."
            )
        
        # Your existing cloud upload logic
        pass
```

## Frontend Integration

### Step 1: Feature Gate Component

```typescript
// ui/src/components/BusinessFeatureGate.tsx
import { useEffect, useState } from 'react';
import { Lock } from 'lucide-react';
import { api } from '@/lib/api';

interface BusinessFeatureGateProps {
  feature: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function BusinessFeatureGate({ feature, children, fallback }: BusinessFeatureGateProps) {
  const [hasAccess, setHasAccess] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/license/status')
      .then(response => {
        const hasBusinessLicense = ['trial', 'active'].includes(response.license_status);
        setHasAccess(hasBusinessLicense);
      })
      .catch(() => setHasAccess(false))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!hasAccess) {
    return fallback || (
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
        <Lock className="mx-auto text-gray-400 mb-4" size={48} />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Business Feature: {feature}
        </h3>
        <p className="text-gray-600 mb-4">
          This feature requires a business license.
        </p>
        <a
          href="/license-management?upgrade=true"
          className="inline-block px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Upgrade to Business
        </a>
      </div>
    );
  }

  return <>{children}</>;
}
```

### Step 2: Use in Components

```typescript
// ui/src/pages/APIKeys.tsx
import { BusinessFeatureGate } from '@/components/BusinessFeatureGate';

export function APIKeysPage() {
  return (
    <div>
      <h1>API Keys</h1>
      
      <BusinessFeatureGate feature="API Access">
        {/* Your API keys management UI */}
        <APIKeysList />
        <CreateAPIKeyButton />
      </BusinessFeatureGate>
    </div>
  );
}
```

```typescript
// ui/src/pages/Settings.tsx
export function SettingsPage() {
  return (
    <div>
      <Tabs>
        <Tab label="General">
          <GeneralSettings />
        </Tab>
        
        <Tab label="API Keys">
          <BusinessFeatureGate feature="API Access">
            <APIKeysSettings />
          </BusinessFeatureGate>
        </Tab>
        
        <Tab label="Webhooks">
          <BusinessFeatureGate feature="Webhooks">
            <WebhookSettings />
          </BusinessFeatureGate>
        </Tab>
        
        <Tab label="Team">
          <BusinessFeatureGate feature="Multi-User Access">
            <TeamSettings />
          </BusinessFeatureGate>
        </Tab>
      </Tabs>
    </div>
  );
}
```

### Step 3: Inline Feature Checks

```typescript
// ui/src/components/InvoiceForm.tsx
import { useLicenseStatus } from '@/hooks/useLicenseStatus';

export function InvoiceForm() {
  const { hasBusinessLicense } = useLicenseStatus();

  return (
    <form>
      {/* Regular fields */}
      
      <div className="form-group">
        <label>
          <input
            type="checkbox"
            name="is_recurring"
            disabled={!hasBusinessLicense}
          />
          Recurring Invoice
          {!hasBusinessLicense && (
            <span className="text-sm text-gray-500 ml-2">
              (Business feature)
            </span>
          )}
        </label>
        
        {!hasBusinessLicense && (
          <p className="text-xs text-gray-500 mt-1">
            Upgrade to business to enable recurring invoices.
            <a href="/license-management?upgrade=true" className="text-blue-600 ml-1">
              Learn more
            </a>
          </p>
        )}
      </div>
    </form>
  );
}
```

### Step 4: License Status Hook

```typescript
// ui/src/hooks/useLicenseStatus.ts
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export function useLicenseStatus() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/license/status')
      .then(setStatus)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return {
    status,
    loading,
    isPersonal: status?.license_status === 'personal',
    isTrial: status?.license_status === 'trial',
    isActive: status?.license_status === 'active',
    hasBusinessLicense: ['trial', 'active'].includes(status?.license_status),
    canUseBusinessFeatures: ['trial', 'active'].includes(status?.license_status)
  };
}
```

## Testing

### Test Business Feature Restrictions

```python
# api/tests/test_business_features.py
import pytest
from fastapi.testclient import TestClient

def test_api_key_creation_requires_business_license(client: TestClient, personal_user_token):
    """Test that personal users cannot create API keys"""
    response = client.post(
        "/api-keys",
        headers={"Authorization": f"Bearer {personal_user_token}"},
        json={"name": "Test Key"}
    )
    
    assert response.status_code == 403
    assert response.json()["error"] == "BUSINESS_FEATURE_REQUIRED"
    assert "API Access" in response.json()["message"]

def test_api_key_creation_allowed_for_business(client: TestClient, business_user_token):
    """Test that business users can create API keys"""
    response = client.post(
        "/api-keys",
        headers={"Authorization": f"Bearer {business_user_token}"},
        json={"name": "Test Key"}
    )
    
    assert response.status_code == 200

def test_batch_upload_restricted_for_personal(client: TestClient, personal_user_token):
    """Test that personal users cannot upload multiple files"""
    files = [
        ("files", ("file1.pdf", b"content1", "application/pdf")),
        ("files", ("file2.pdf", b"content2", "application/pdf"))
    ]
    
    response = client.post(
        "/expenses/upload-multiple",
        headers={"Authorization": f"Bearer {personal_user_token}"},
        files=files
    )
    
    assert response.status_code == 403
    assert "Batch" in response.json()["message"]

def test_recurring_invoice_restricted_for_personal(client: TestClient, personal_user_token):
    """Test that personal users cannot create recurring invoices"""
    response = client.post(
        "/invoices",
        headers={"Authorization": f"Bearer {personal_user_token}"},
        json={
            "client_id": 1,
            "amount": 100,
            "is_recurring": True,
            "recurring_frequency": "monthly"
        }
    )
    
    assert response.status_code == 403
    assert "Recurring" in response.json()["message"]
```

## Summary

### Implementation Checklist

**Phase 1 (Week 1):**
- [ ] Create `business_feature_gate.py` utility
- [ ] Restrict API key creation/management
- [ ] Restrict API key authentication
- [ ] Add frontend BusinessFeatureGate component
- [ ] Update API keys UI

**Phase 2 (Week 2):**
- [ ] Restrict multi-user access
- [ ] Restrict batch file processing
- [ ] Restrict webhooks
- [ ] Update relevant UIs

**Phase 3 (Week 3):**
- [ ] Restrict approval workflows
- [ ] Restrict recurring invoices
- [ ] Restrict cloud storage
- [ ] Add inline feature checks in forms

**Phase 4 (Week 4):**
- [ ] Add comprehensive tests
- [ ] Update documentation
- [ ] Add upgrade prompts
- [ ] Monitor conversion metrics

### Expected Impact

- **API Keys**: 80% of users who need APIs will upgrade
- **Multi-User**: 95% conversion (clear business need)
- **Batch Processing**: 70% conversion (efficiency need)
- **Webhooks**: 75% conversion (integration need)
- **Recurring Invoices**: 85% conversion (subscription businesses)

### User Experience

- Clear messaging about business features
- Smooth upgrade path
- No frustration for personal users
- Obvious value for business users
