# Freemium Licensing Strategy

## Overview

This document outlines the recommended freemium licensing model for the {APP_NAME}, designed to allow individual users to use the application with limitations while providing a clear upgrade path to business licenses.

---

## 🎯 Business Goals

1. **Attract individual users** with a generous free tier
2. **Provide value** that encourages continued use
3. **Create natural upgrade triggers** when users hit limits
4. **Convert power users** to paid business licenses
5. **Maintain sustainable revenue** from business customers

---

## 📊 License Tiers

### Tier 1: Personal Use (Free Forever)

**Target Audience:**
- Individual freelancers
- Sole proprietors
- Hobbyists
- Side hustlers
- Students

**Core Features (Full Access - Unlimited):**
- ✅ Invoice management
- ✅ Expense tracking
- ✅ Inventory management
- ✅ Basic reporting
- ✅ Advanced reporting
- ✅ Advanced search
- ✅ Multi-user support
- ✅ AI Invoice Processing
- ✅ AI Expense Processing
- ✅ AI Bank Statement Processing
- ✅ AI Chat Assistant
- ✅ Local file storage

**Restricted Features (Business Only):**
- ❌ Cloud Storage (AWS S3, Azure, GCP)
- ❌ Tax Service Integration
- ❌ Slack Integration
- ❌ SSO Authentication
- ❌ API Access
- ❌ Approval Workflows
- ❌ Batch Processing

---

### Tier 2: Business Use (Paid License)

**Target Audience:**
- Small businesses
- Growing companies
- Teams
- Agencies
- Enterprises

**Includes:**
- ✅ **Everything in Personal tier** (unlimited)
- ✅ **Cloud storage** (AWS S3, Azure Blob, GCP)
- ✅ **All integrations** (Slack, tax services, SSO)
- ✅ **API access** for external integrations
- ✅ **Approval workflows** for expense management
- ✅ **Batch processing** for bulk operations
- ✅ **Priority support**

**Trial Period:**
- 30-day free trial with all features
- 7-day grace period after expiration
- Automatic downgrade to Personal if not licensed

**No Rate Limits:**
- Unlimited invoices
- Unlimited expenses
- Unlimited bank statement processing
- Unlimited AI processing
- Unlimited file storage (cloud)

---

## 📈 Feature Comparison Matrix

| Feature Category | Feature | Personal (Free) | Business (Paid) |
|-----------------|---------|----------------|-----------------|
| **Core** | Invoices | Unlimited | Unlimited |
| | Expenses | Unlimited | Unlimited |
| | Inventory | Full access | Full access |
| | Basic Reporting | Full access | Full access |
| | Advanced Search | Full access | Full access |
| **AI** | AI Invoice Extract | ✅ Unlimited | ✅ Unlimited |
| | AI Expense Extract | ✅ Unlimited | ✅ Unlimited |
| | AI Bank Statement | ✅ Unlimited | ✅ Unlimited |
| | AI Chat Assistant | ✅ Unlimited | ✅ Unlimited |
| **Storage** | Local Storage | Unlimited | Unlimited |
| | Cloud Storage (S3/Azure/GCP) | ❌ | ✅ Unlimited |
| **Integrations** | Tax Integration | ❌ | ✅ Full |
| | Slack Integration | ❌ | ✅ Full |
| | SSO (Google/Azure AD) | ❌ | ✅ Full |
| | API Access | ❌ | ✅ Full |
| **Advanced** | Approval Workflows | ❌ | ✅ Full |
| | Batch Processing | ❌ | ✅ Full |
| | Advanced Reporting | ✅ Full | ✅ Full |
| **Users** | User Accounts | Unlimited | Unlimited |
| **Support** | Support Level | Community | Priority |

---

## 🔧 Implementation Requirements

### 1. Feature Configuration Updates

**File:** `api/services/feature_config_service.py`

Add new fields to feature definitions:

```python
FEATURES = {
    'ai_invoice': {
        'name': 'AI Invoice Processing',
        'description': 'AI-powered invoice data extraction and processing',
        'category': 'ai',
        'env_var': 'FEATURE_AI_INVOICE_ENABLED',
        'default': False,
        'personal_allowed': True
    },
    'ai_expense': {
        'name': 'AI Expense Processing',
        'description': 'AI-powered expense OCR and categorization',
        'category': 'ai',
        'env_var': 'FEATURE_AI_EXPENSE_ENABLED',
        'default': False,
        'personal_allowed': True
    },
    'ai_bank_statement': {
        'name': 'AI Bank Statement Processing',
        'description': 'AI-powered bank statement parsing',
        'category': 'ai',
        'env_var': 'FEATURE_AI_BANK_STATEMENT_ENABLED',
        'default': False,
        'personal_allowed': True
    },
    'ai_chat': {
        'name': 'AI Chat Assistant',
        'description': 'Conversational AI assistant',
        'category': 'ai',
        'env_var': 'FEATURE_AI_CHAT_ENABLED',
        'default': False,
        'personal_allowed': True
    },
    'cloud_storage': {
        'name': 'Cloud Storage',
        'description': 'AWS S3, Azure Blob, and GCP Storage providers',
        'category': 'integration',
        'env_var': 'FEATURE_CLOUD_STORAGE_ENABLED',
        'default': False,
        'personal_allowed': False,      # NEW: Business only
    },
    'api_keys': {
        'name': 'API Keys',
        'description': 'External API access with API key authentication',
        'category': 'integration',
        'env_var': 'FEATURE_API_KEYS_ENABLED',
        'default': False,
        'personal_allowed': False,      # NEW: Business only
    },
    # ... etc
}
```

---

### 2. Rate Limiting Service

**Note:** This service is currently for future implementation. The Personal (Free) tier currently offers unlimited usage for core features, making rate limiting unnecessary at this time.

**New File:** `api/services/rate_limit_service.py`

```python
class RateLimitService:
    """
    Manages usage limits for personal tier users.
    Tracks monthly usage and enforces limits.
    """
    
    def check_limit(self, installation_id: str, feature: str) -> Dict[str, Any]:
        """
        Check if user has exceeded their monthly limit for a feature.
        
        Returns:
            {
                'allowed': bool,
                'current_usage': int,
                'limit': int,
                'reset_date': datetime,
                'percentage_used': float
            }
        """
        pass
    
    def increment_usage(self, installation_id: str, feature: str) -> None:
        """Increment usage counter for a feature."""
        pass
    
    def get_usage_stats(self, installation_id: str) -> Dict[str, Any]:
        """Get all usage statistics for an installation."""
        pass
    
    def reset_monthly_limits(self) -> None:
        """Reset all monthly limits (run as cron job)."""
        pass
```

**Database Schema Addition:**

```sql
CREATE TABLE usage_tracking (
    id SERIAL PRIMARY KEY,
    installation_id UUID NOT NULL,
    feature VARCHAR(50) NOT NULL,
    usage_count INTEGER DEFAULT 0,
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(installation_id, feature, period_start)
);
```

---

### 3. License Service Updates

**File:** `api/services/license_service.py`

Update `select_usage_type()` method:

```python
def select_usage_type(self, usage_type: str, installation_id: str) -> Dict[str, Any]:
    """Select usage type and grant appropriate features."""
    
    if usage_type == "personal":
        # Grant all core features for personal use
        installation.licensed_features = [
            'ai_invoice',              # Unlimited
            'ai_expense',              # Unlimited
            'ai_bank_statement',       # Unlimited
            'ai_chat',                 # Unlimited
            'reporting',               # Full access
            'advanced_search',         # Full access
            'inventory',               # Full access
            # Note: Multi-user is enabled by default, no feature flag needed
        ]
        installation.license_status = "personal"
        
    elif usage_type == "business":
        # Start 30-day trial with all features
        installation.licensed_features = ['all']
        installation.license_status = "trial"
        installation.trial_start_date = now
        installation.trial_end_date = now + timedelta(days=30)
    
    # Save and return
    db.commit()
    return self.get_license_status()
```

---

### 4. Feature Gate Decorator Updates

**File:** `api/utils/feature_gate.py`

Update `@require_feature` to check rate limits:

```python
def require_feature(feature_id: str, check_rate_limit: bool = True):
    """
    Decorator to require a feature and optionally check rate limits.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get database session
            db = kwargs.get('db') or next(get_db())
            
            # Check if feature is enabled
            if not FeatureConfigService.is_enabled(feature_id, db):
                raise HTTPException(402, "Feature not licensed")
            
            # Check rate limits for personal users
            if check_rate_limit:
                license_service = LicenseService(db)
                status = license_service.get_license_status()
                
                if status['usage_type'] == 'personal':
                    rate_limit_service = RateLimitService(db)
                    limit_check = rate_limit_service.check_limit(
                        installation_id=status['installation_id'],
                        feature=feature_id
                    )
                    
                    if not limit_check['allowed']:
                        raise HTTPException(
                            429,
                            detail={
                                'error': 'Rate limit exceeded',
                                'feature': feature_id,
                                'current_usage': limit_check['current_usage'],
                                'limit': limit_check['limit'],
                                'reset_date': limit_check['reset_date'],
                                'upgrade_url': '/settings/license'
                            }
                        )
                    
                    # Increment usage counter
                    rate_limit_service.increment_usage(
                        installation_id=status['installation_id'],
                        feature=feature_id
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

---

### 5. UI Components

#### A. Usage Type Selection Screen

**New File:** `ui/src/components/UsageTypeSelector.tsx`

```tsx
interface UsageTypeSelectorProps {
  onSelect: (usageType: 'personal' | 'business') => void;
}

export const UsageTypeSelector: React.FC<UsageTypeSelectorProps> = ({ onSelect }) => {
  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold text-center mb-8">
        Choose Your Plan
      </h1>
      
      <div className="grid md:grid-cols-2 gap-6">
        {/* Personal Plan Card */}
        <Card className="border-2 hover:border-primary">
          <CardHeader>
            <CardTitle>Personal Use</CardTitle>
            <CardDescription>Free Forever</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold mb-4">$0</div>
            <ul className="space-y-2 mb-6">
              <li>✅ Unlimited invoices & expenses</li>
              <li>✅ Unlimited AI features</li>
              <li>✅ Full inventory management</li>
              <li>✅ Advanced reporting</li>
              <li>✅ Multi-user support</li>
              <li>✅ Local storage</li>
            </ul>
            <Button onClick={() => onSelect('personal')} className="w-full">
              Start Free
            </Button>
          </CardContent>
        </Card>
        
        {/* Business Plan Card */}
        <Card className="border-2 border-primary">
          <CardHeader>
            <Badge className="mb-2">30-Day Free Trial</Badge>
            <CardTitle>Business Use</CardTitle>
            <CardDescription>For teams & companies</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold mb-4">
              $29<span className="text-lg">/month</span>
            </div>
            <ul className="space-y-2 mb-6">
              <li>✅ Everything in Personal</li>
              <li>✅ Cloud storage</li>
              <li>✅ Integrations (Slack, Tax, SSO)</li>
              <li>✅ API access</li>
              <li>✅ Approval workflows</li>
              <li>✅ Advanced reporting</li>
              <li>✅ Multi-user support</li>
            </ul>
            <Button onClick={() => onSelect('business')} className="w-full">
              Start Free Trial
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
```

#### B. Feature Comparison Component

**New File:** `ui/src/components/FeatureComparison.tsx`

```tsx
export const FeatureComparison: React.FC = () => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Upgrade to Business</CardTitle>
        <CardDescription>Unlock advanced features for your team</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <h3 className="font-semibold">Business-Only Features:</h3>
          <ul className="space-y-2">
            <li>✅ Cloud Storage (AWS S3, Azure, GCP)</li>
            <li>✅ Tax Service Integration</li>
            <li>✅ Slack Integration</li>
            <li>✅ SSO Authentication</li>
            <li>✅ API Access</li>
            <li>✅ Approval Workflows</li>
            <li>✅ Batch Processing</li>
            <li>✅ Priority Support</li>
          </ul>
          
          <div className="pt-4 border-t">
            <Button className="w-full">
              Start 30-Day Free Trial
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
```

---

## 🚀 User Journey

### New User Flow

1. **First Launch**
   - Show usage type selection screen
   - User chooses "Personal" or "Business"

2. **Personal User Path**
   - Immediate access to app with full core features
   - Unlimited invoices, expenses, and AI processing
   - See upgrade prompts for business-only features (cloud storage, integrations, etc.)
   - Smooth upgrade path when needing advanced features

3. **Business User Path**
   - Start 30-day trial with all features
   - See trial countdown in UI
   - Get reminders at 7 days, 3 days, 1 day remaining
   - After trial: activate license or downgrade to Personal

### Existing User Migration

1. **Current Installations**
   - Default to "Business" usage type
   - Grant 30-day trial automatically
   - Send email notification about new licensing

2. **After Trial Expires**
   - Show license activation screen
   - Options: "Activate License" or "Switch to Personal"
   - If switching to Personal, business-only features become unavailable

---

## 💰 Pricing Recommendations

### Business License Pricing

**Monthly:**
- $29/month - Single user
- $49/month - Up to 5 users
- $99/month - Up to 20 users
- Custom - Enterprise (20+ users)

**Annual (Save 20%):**
- $279/year - Single user ($23.25/month)
- $470/year - Up to 5 users ($39.17/month)
- $950/year - Up to 20 users ($79.17/month)

### Add-ons (Optional)
- Priority Support: +$10/month
- Custom Integrations: +$20/month
- White-label: +$50/month

---

## 📊 Success Metrics

### Key Performance Indicators (KPIs)

1. **Conversion Rate**
   - Target: 5-10% of Personal users upgrade to Business
   - Track: Monthly conversion rate

2. **Trial Conversion**
   - Target: 30-40% of trials convert to paid
   - Track: Trial-to-paid conversion rate

3. **Feature Request Rate**
   - Track: % of Personal users attempting to use business-only features
   - Optimize: Identify most-requested features for potential tier adjustments

4. **Churn Rate**
   - Target: <5% monthly churn for Business users
   - Track: Monthly subscription cancellations

5. **Average Revenue Per User (ARPU)**
   - Track: Monthly revenue / active Business users
   - Optimize: Upsell to higher tiers

---

## 🎯 Upgrade Triggers

### When to Show Upgrade Prompts

1. **Feature Access Attempt (Primary Trigger)**
   - User tries to use business-only feature (cloud storage, API, integrations)
   - "This feature requires a Business license"
   - CTA: "Start 30-day free trial"

2. **Value Moments**
   - After successful AI extraction
   - After generating a report
   - After creating 10th invoice
   - Message: "Loving the app? Upgrade for more!"

---

## 🔄 Downgrade Handling

### Business → Personal Downgrade

**What happens:**
1. User keeps all existing data
2. Core features remain fully functional (invoices, expenses, AI processing)
3. Business-only features become unavailable for new usage:
   - Cloud storage: Existing files accessible (read-only), no new uploads
   - Integrations: Disconnected (Slack, tax services, SSO)
   - API: Keys deactivated
   - Workflows: Approval workflows disabled
   - Batch processing: Disabled
4. All users and data remain intact

**Grace Period:**
- 7 days to reactivate before restrictions apply
- Export data option provided
- One-click reactivation available

---

## 🛠️ Implementation Checklist

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Add `personal_allowed` field to feature config
- [ ] Update `LicenseService.select_usage_type()` method
- [ ] Update feature gating to check `personal_allowed` flag
- [ ] Write unit tests for personal vs business feature access
- [ ] Document which features are personal vs business-only

### Phase 2: UI Components (Week 2-3)
- [ ] Create `UsageTypeSelector` component
- [ ] Update `LicenseManagement` page
- [ ] Add upgrade prompts for business-only features
- [ ] Add feature comparison page
- [ ] Design smooth upgrade flow
- [ ] Add "Upgrade to Business" CTAs in appropriate places

### Phase 3: Integration & Testing (Week 3-4)
- [ ] Integrate usage type selection on first launch
- [ ] Test personal vs business feature access
- [ ] Test upgrade/downgrade flows
- [ ] Test trial expiration handling
- [ ] Test business-only feature blocking
- [ ] End-to-end testing

### Phase 4: Documentation & Launch (Week 4)
- [ ] Update user documentation
- [ ] Create pricing page
- [ ] Set up payment processing (Stripe)
- [ ] Create email templates (trial reminders, etc.)
- [ ] Prepare marketing materials
- [ ] Soft launch with beta users
- [ ] Monitor metrics and iterate

---

## 📝 Notes & Considerations

### Technical Considerations

1. **Feature Access Control**
   - Use `personal_allowed` flag in feature config
   - Check usage type before allowing business-only features
   - Provide clear upgrade prompts when blocked

2. **Cloud Data After Downgrade**
   - Existing cloud-stored files remain accessible (read-only)
   - Users can download files to local storage
   - New uploads to cloud storage are blocked
   - Provide export/migration tools for bulk downloads
   - Maintain data integrity during transitions

3. **Performance**
   - Feature checks should add <5ms latency
   - Cache feature configs in memory
   - Use database indexes on installation_id

### Business Considerations

1. **Competitive Analysis**
   - Research competitor pricing
   - Ensure Personal tier is competitive
   - Ensure Business tier provides clear value

2. **Customer Support**
   - Prepare support team for upgrade questions
   - Create self-service upgrade documentation
   - Monitor upgrade friction points

3. **Legal**
   - Update Terms of Service
   - Update Privacy Policy
   - Ensure GDPR compliance for usage tracking

---

## 🎉 Expected Outcomes

### Short-term (3 months)
- 1,000+ Personal tier users
- 50-100 Business trial starts
- 15-30 paid Business customers
- $500-1,500 MRR

### Medium-term (6 months)
- 5,000+ Personal tier users
- 200-300 Business trial starts
- 60-100 paid Business customers
- $2,000-4,000 MRR

### Long-term (12 months)
- 20,000+ Personal tier users
- 500+ Business trial starts
- 150-250 paid Business customers
- $5,000-10,000 MRR

---

## 📞 Next Steps

1. **Review and approve** this strategy
2. **Finalize pricing** and limits
3. **Create implementation plan** with timeline
4. **Assign development resources**
5. **Begin Phase 1 implementation**

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-20  
**Status:** Proposal - Pending Approval
