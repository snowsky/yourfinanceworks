# Feature Gate Decorator Audit Report

## Summary

This document audits the current usage of `@require_feature` and `@require_business_license` decorators across the codebase and provides recommendations for consistency.

---

## Current Implementation Status

### ✅ Correctly Protected Features

| Feature | Router | Decorator Used | Status |
|---------|--------|----------------|--------|
| `ai_invoice` | `ai.py` | `@require_feature("ai_invoice")` | ✅ Correct |
| `ai_expense` | `ai.py` | `@require_feature("ai_expense")` | ✅ Correct (implied) |
| `ai_chat` | `ai.py` | `@require_feature("ai_chat")` | ✅ Correct |
| `ai_bank_statement` | `statements.py` | `@require_feature("ai_bank_statement")` | ✅ Correct |
| `tax_integration` | `tax_integration.py` | `@require_feature("tax_integration")` | ✅ Correct (8 endpoints) |
| `slack_integration` | `slack_simplified.py` | `@require_feature("slack_integration")` | ✅ Correct (2 endpoints) |
| `batch_processing` | `batch_processing.py` | `@require_feature("batch_processing")` | ✅ Correct (3 endpoints) |
| API Keys | `external_api_auth.py` | `@require_business_license` | ✅ Correct (6 endpoints) |

### ⚠️ Missing Protection

| Feature | Default | Router | Current Protection | Recommendation |
|---------|---------|--------|-------------------|----------------|
| `approvals` | `False` | `approvals.py` | ❌ None | Add `@require_feature("approvals")` |
| `reporting` | `True` | `reports.py` | ❌ None | Optional (see below) |
| `cloud_storage` | `False` | `azure_blob_provider.py` | ❌ None | Add `@require_feature("cloud_storage")` |
| `sso` | `False` | N/A | ❌ None | Add when SSO endpoints exist |
| `advanced_search` | `True` | N/A | ❌ None | Optional (core feature) |

---

## Detailed Analysis

### 1. Approvals Feature (`default: False`)

**Current State:**
- `approvals.py` has **NO** feature gate protection
- All endpoints use only RBAC (`require_non_viewer`, `require_approval_permission`)
- Feature is defined with `default: False` → should require licensing

**Recommendation:** ✅ **ADD PROTECTION**

```python
# In api/routers/approvals.py
router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
    dependencies=[Depends(lambda db=Depends(get_db): require_feature("approvals")(lambda: None)())]
)
```

**Rationale:**
- Approval workflows are an advanced feature
- Should require explicit licensing
- Consistent with other `default: False` features

---

### 2. Reporting Feature (`default: True`)

**Current State:**
- `reports.py` has **NO** feature gate protection
- All endpoints use only RBAC (`require_non_viewer`)
- Feature is defined with `default: True` → available without license

**Options:**

#### Option A: Keep as Core Feature (`default: True`)
- ✅ Basic reporting is essential for any business
- ✅ Competitive with other tools
- ❌ Less revenue from premium features

#### Option B: Make Premium Feature (`default: False`)
- ✅ Clear value proposition for paid licenses
- ✅ Consistent with other advanced features
- ❌ May frustrate users who expect basic reporting

**Recommendation:** 🤔 **BUSINESS DECISION REQUIRED**

If you choose Option B, add:
```python
# In api/routers/reports.py
router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(lambda db=Depends(get_db): require_feature("reporting")(lambda: None)())]
)
```

---

### 3. Cloud Storage Feature (`default: False`)

**Current State:**
- `azure_blob_provider.py` has **NO** feature gate protection
- Service is used internally by other modules
- Feature is defined with `default: False` → should require licensing

**Recommendation:** ⚠️ **CONDITIONAL PROTECTION**

Cloud storage is a **service**, not a router. Protection should be added at the **usage points**:

```python
# In routers that use cloud storage (e.g., expenses.py, invoices.py)
@require_feature("cloud_storage")
async def upload_to_cloud():
    # Upload logic
    pass
```

**Alternative:** Add a check in the service itself:
```python
# In azure_blob_provider.py
def upload_file(self, ...):
    if not FeatureConfigService.is_enabled('cloud_storage', self.db):
        raise HTTPException(402, "Cloud storage feature not licensed")
    # Upload logic
```

---

### 4. SSO Feature (`default: False`)

**Current State:**
- No dedicated SSO router yet
- OAuth endpoints exist in `auth.py` but not gated
- Feature is defined with `default: False`

**Recommendation:** 🔮 **FUTURE IMPLEMENTATION**

When SSO endpoints are added, protect them:
```python
@require_feature("sso_authentication")
async def google_oauth_login():
    pass

@require_feature("sso_authentication")
async def azure_ad_oauth_login():
    pass
```

---

### 5. Advanced Search Feature (`default: True`)

**Current State:**
- No dedicated advanced search router
- Search functionality may be embedded in other endpoints
- Feature is defined with `default: True` → core feature

**Recommendation:** ℹ️ **NO ACTION NEEDED**

If advanced search is a core feature, keep `default: True` and no gate needed.

---

## Implementation Priority

### High Priority (Immediate Action)

1. **✅ Add `@require_feature("approvals")` to `approvals.py`**
   - Feature has `default: False`
   - Currently unprotected
   - Clear premium feature

### Medium Priority (Business Decision Required)

2. **🤔 Decide on `reporting` feature**
   - Should it be `default: True` (core) or `default: False` (premium)?
   - Add protection if making it premium

3. **⚠️ Add cloud storage protection**
   - Protect at usage points or in service layer
   - Ensure consistent enforcement

### Low Priority (Future)

4. **🔮 SSO protection**
   - Implement when SSO endpoints are added

---

## Recommended Changes

### Change 1: Protect Approvals Router

```python
# File: api/routers/approvals.py
# Add at the top with other imports
from utils.feature_gate import require_feature

# Modify router definition
router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
    dependencies=[Depends(lambda db=Depends(get_db): require_feature("approvals")(lambda: None)())]
)
```

### Change 2: (Optional) Protect Reports Router

```python
# File: api/routers/reports.py
# Already has the import

# Modify router definition (line 99)
router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(lambda db=Depends(get_db): require_feature("reporting")(lambda: None)())]
)
```

### Change 3: (Optional) Change Reporting Default

```python
# File: api/services/feature_config_service.py
# Line 104-109
'reporting': {
    'name': 'Advanced Reporting',
    'description': 'Custom reports and analytics dashboards',
    'category': 'advanced',
    'env_var': 'FEATURE_REPORTING_ENABLED',
    'default': False  # Changed from True
},
```

---

## Decision Matrix

| Feature | Current Default | Should Gate? | Reason |
|---------|----------------|--------------|--------|
| `approvals` | `False` | ✅ YES | Premium feature, consistent with other `False` defaults |
| `reporting` | `True` | 🤔 DECIDE | Business decision: core vs premium |
| `advanced_search` | `True` | ❌ NO | Core functionality |
| `cloud_storage` | `False` | ✅ YES | Premium integration, protect at usage points |
| `sso` | `False` | ✅ YES | Premium auth method, implement when endpoints exist |

---

## Summary of Recommendations

1. **Immediate:** Add `@require_feature("approvals")` to `approvals.py` router
2. **Decide:** Should `reporting` be premium (`default: False`) or core (`default: True`)?
3. **Consider:** Add cloud storage protection at usage points
4. **Future:** Protect SSO endpoints when implemented

**Key Principle:** All features with `default: False` should have `@require_feature` protection to ensure consistent licensing enforcement.

