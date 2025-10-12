# Changelog

## [Latest] - September 2025

### Microsoft Azure AD SSO Implementation

**Summary**: Added enterprise-grade Single Sign-On support with Microsoft Azure AD/Entra ID, enabling seamless authentication for organizations using Microsoft identity services.

#### 🔐 Authentication & Security Enhancements
- **Azure AD OAuth 2.0 Integration**: Full implementation using Microsoft Authentication Library (MSAL)
- **Multi-tenant Support**: Supports both single-tenant and multi-tenant Azure AD configurations
- **Database Schema Extensions**: Added `azure_ad_id` and `azure_tenant_id` fields to user models
- **Automatic User Provisioning**: Creates users and tenants automatically for new Azure AD users
- **Account Linking**: Links existing users with Azure AD accounts seamlessly
- **CSRF Protection**: Secure state management with token expiration

#### 🎨 User Interface Updates
- **Microsoft Login Button**: Added official Microsoft branding to login page
- **Multi-language Support**: Translations for "Sign in with Microsoft" in English, French, Spanish, and German
- **Consistent UX**: Matches existing Google OAuth button styling and behavior
- **OAuth Flow Handling**: Seamless redirect-based authentication flow

#### 🔧 Technical Implementation
- **New Dependencies**: Added MSAL 1.31.0 for Microsoft authentication
- **API Endpoints**: 
  - `/api/v1/auth/azure/login` - Initiates Azure AD authentication
  - `/api/v1/auth/azure/callback` - Handles OAuth callback and user creation
- **Environment Configuration**: Docker Compose support for Azure AD variables
- **Comprehensive Logging**: Detailed logs for debugging and monitoring
- **Error Handling**: Graceful handling of authentication failures and edge cases

#### 📚 Documentation
- **Implementation Guide**: Complete Azure AD SSO setup documentation
- **Testing Guide**: Comprehensive testing scenarios and troubleshooting
- **Security Documentation**: Enterprise compliance and security considerations

#### 🗄️ Database Changes
```sql
-- Added to both MasterUser and TenantUser models
azure_ad_id VARCHAR UNIQUE NULL     -- Azure AD Object ID
azure_tenant_id VARCHAR NULL        -- Azure AD Tenant ID
```

#### 📁 Files Modified
- `api/requirements.txt` - Added MSAL dependency
- `api/models/models.py` - Extended MasterUser and User models
- `api/models/models_per_tenant.py` - Extended TenantUser model
- `api/routers/auth.py` - Added Azure AD OAuth endpoints and client
- `docker-compose.yml` - Added Azure AD environment variables
- `ui/src/pages/Login.tsx` - Added Microsoft login button and handler
- `ui/src/i18n/locales/*.json` - Added Microsoft login translations
- `mobile/src/i18n/locales/*.json` - Added mobile translations

#### 🧪 Testing
- Manual testing scenarios documented
- Error handling verification
- Multi-language UI testing
- Database integration testing
- OAuth flow validation

---

## [Previous] - Bank Statement Processing Improvements

### Summary
Enhanced bank statement extraction service and added CSV export + expense creation features to the transactions interface.

## Changes Made

### 1. Bank Statement Service Refactor
- **File**: `api/services/statement_service.py`
- **Issue**: Bank statement extraction was not finding all 14 transactions from test PDF
- **Solution**: Refactored service using proven patterns from `test-main.py`
- **Key Changes**:
  - Updated date normalization to use exact formats from test-main.py Pydantic validator
  - Simplified regex patterns to match test-main.py `_extract_with_regex` method
  - Streamlined text preprocessing to match test-main.py approach
  - Removed bank-specific (RBC) optimizations for generic compatibility
  - Enhanced LLM response parsing with proper fallback to regex extraction

### 2. CSV Export Feature
- **File**: `ui/src/pages/Statements.tsx`
- **Feature**: Added CSV export functionality for transaction data
- **Implementation**:
  - Export button with FileText icon
  - Proper CSV formatting with quoted descriptions
  - Filename includes original PDF name
  - Handles all transaction fields (Date, Description, Amount, Type, Balance, Category)

### 3. Financial Summary Display
- **File**: `ui/src/pages/Statements.tsx`
- **Feature**: Added income/expense totals above transaction table
- **Implementation**:
  - Three-column grid showing Total Income, Total Expenses, Net Amount
  - Color-coded values (green for positive, red for negative)
  - Real-time calculation as transactions change
  - Only displays when transactions exist

### 4. Expense Creation from Transactions
- **File**: `ui/src/pages/Statements.tsx`
- **Feature**: Create expense records from debit transactions
- **Implementation**:
  - "Expense" button in Actions column for debit transactions only
  - Maps bank transaction categories to valid expense categories
  - Auto-populates expense with transaction data
  - Links back to bank statement via notes field
  - Sets appropriate defaults (Bank Transfer, completed status)

## Technical Details

### Bank Statement Extraction Patterns
```javascript
// Simplified regex patterns from test-main.py
patterns = [
  r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+([^$\d-]+?)\s+([-$]?\d+\.?\d*)',
  r'(\d{4}-\d{2}-\d{2})\s+([^$\d-]+?)\s+([-$]?\d+\.?\d*)',
]
```

### Category Mapping
```javascript
const categoryMap = {
  'Transportation': 'Transportation',
  'Food': 'Meals',
  'Travel': 'Travel',
  'Other': 'General'
};
```

## Files Modified
- `api/services/statement_service.py` - Complete refactor
- `ui/src/pages/Statements.tsx` - Added CSV export, totals, expense creation

## Testing
- Verified with test PDF that all 14 transactions are now extracted
- CSV export generates proper format with all fields
- Expense creation works for debit transactions with proper category mapping
- Financial totals calculate correctly and update in real-time