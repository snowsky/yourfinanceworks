# License Feature Comparison

This document provides a comprehensive overview of features available under each license tier for YourFinanceWORKS.

## 📋 Table of Contents

- [License Overview](#license-overview)
- [Quick Comparison Table](#quick-comparison-table)
- [GPLv3 Features (Core)](#gplv3-features-core)
- [Commercial Features](#commercial-features)
- [Code Organization](#code-organization)
- [Important Legal Notes](#important-legal-notes)

---

## License Overview

YourFinanceWORKS is **dual-licensed** under two options:

### 1. GNU General Public License v3 (GPLv3)

- **License File**: [`LICENSE-GPLv3.txt`](LICENSE-GPLv3.txt)
- **Code Location**: `api/core/`
- **Use Case**: Open source projects, community use, learning
- **Requirements**:
  - Derivative works must be licensed under GPLv3
  - Source code must be shared
  - Cannot be integrated into proprietary software
- **Cost**: Free

### 2. Commercial License

- **License File**: [`LICENSE-COMMERCIAL.txt`](LICENSE-COMMERCIAL.txt)
- **Code Location**: `api/commercial/`
- **Use Case**: Proprietary use, SaaS offerings, commercial applications
- **Requirements**:
  - Purchase commercial license
  - Can integrate into closed-source software
  - No obligation to share source code
- **Cost**: Contact for pricing

---

## Quick Comparison Table

| Feature Category                | GPLv3 (Core)              | Commercial                                               |
| ------------------------------- | ------------------------- | -------------------------------------------------------- |
| **Basic Financial Management**  | ✅ Full                   | ✅ Full                                                  |
| **Client & Invoice Management** | ✅ Full                   | ✅ Full                                                  |
| **Payment Tracking**            | ✅ Full                   | ✅ Full                                                  |
| **Expense Management**          | ✅ Full                   | ✅ Full                                                  |
| **Bank Statement Processing**   | ❌ No                     | ✅ Yes (gated: `ai_bank_statement`)                      |
| **Reporting & Analytics**       | ❌ No                     | ✅ Yes (gated: `reporting`)                              |
| **Authentication & Security**   | ✅ Basic (Email/Password) | ✅ Full (incl. gated: `sso`)                             |
| **Enterprise Search**           | ❌ No                     | ✅ Yes (gated: `advanced_search`)                        |
| **AI Processing Suite**         | ❌ No                     | ✅ Yes (`ai_invoice`, `ai_expense`, `ai_bank_statement`) |
| **AI Assistant (Chat)**         | ❌ No                     | ✅ Yes (gated: `ai_chat`)                                |
| **Batch processing**            | ❌ No                     | ✅ Yes (gated: `batch_processing`)                       |
| **Inventory Management**        | ✅ Full (Core)            | ✅ Full                                                  |
| **CRM & Client Notes**          | ✅ Full (Core)            | ✅ Full                                                  |
| **Cloud Storage integration**   | ❌ No                     | ✅ Yes (gated: `cloud_storage`)                          |
| **Advanced Export**             | ❌ No                     | ✅ Yes (gated: `advanced_export`)                        |
| **Third-Party Integrations**    | ❌ No                     | ✅ Yes (`slack_integration`, `tax_integration`)          |
| **Workflow Automation**         | ❌ No                     | ✅ Yes (gated: `approvals`)                              |
| **Prompt Management**           | ❌ No                     | ✅ Yes (gated: `prompt_management`)                      |
| **External API & Sync**         | ❌ No                     | ✅ Yes (`external_api`, `external_transactions`)         |
| **Email Ingestion (Sync)**      | ❌ No                     | ✅ Yes (gated: `email_integration`)                      |
| **Approval Analytics**          | ❌ No                     | ✅ Yes (gated: `approval_analytics`)                     |

---

## GPLv3 Features (Core)

All features in `api/core/` are available under the GPLv3 license.

### 🏦 Financial Management

#### Client Management (`clients.py`)

- Complete CRM system
- Client profiles and contact information
- Client interaction history
- Client categorization and tagging
- Client search and filtering

#### Invoice Management (`invoices.py`)

- Professional invoice creation
- Automatic invoice numbering
- Item management with quantities and prices
- Tax calculations
- Multiple invoice statuses (draft, sent, paid, overdue)
- Invoice templates
- PDF generation
- Invoice preview and printing
- Recurring invoices

#### Payment Tracking (`payments.py`)

- Payment recording and tracking
- Partial payment support
- Payment method tracking
- Payment history
- Outstanding balance calculations

#### Expense Management (`expenses.py`)

- Expense creation and tracking
- Expense categorization
- Receipt attachment support
- Expense approval workflows
- Expense search and filtering
- Expense analytics

### 📊 Banking & Statements

> **Note**: Bank Statement Processing is feature-gated and requires a commercial license.

### 📈 Reporting & Analytics

#### Financial Reports (`reports.py`)

- Profit & Loss statements
- Cash flow analysis
- Revenue reports
- Expense reports
- Tax reports
- Custom report generation
- Report scheduling
- Report templates
- Report history
- Report caching
- Report export (PDF, Excel, CSV)

#### Analytics (`analytics.py`)

- Financial dashboards
- Real-time metrics
- Trend analysis
- KPI tracking

### 🏢 Multi-Tenant & Organization

#### Tenant Management (`tenant.py`)

- Database-per-tenant architecture
- Tenant isolation
- Tenant provisioning
- Tenant database health monitoring

#### Organization Management

- Organization profiles
- Organization settings
- Organization join requests (`organization_join.py`)
- Multi-organization support

#### Super Admin (`super_admin.py`)

- System-wide administration
- Tenant management
- User management across tenants
- Database health monitoring
- System diagnostics

### 🔐 Authentication & Security

#### Authentication (`auth.py`)

- JWT-based authentication
- Role-based access control (RBAC)
- User registration and login
- Password reset
- Email verification
- Session management
- Token refresh

#### Audit Logging (`audit_log.py`)

- Complete activity tracking
- User action logging
- Change history
- Compliance reporting

### 📧 Communication

#### Email Delivery (`email.py`)

- Outbound email sending (AWS SES, Azure, Mailgun)
- Invoice delivery
- Email templates
- Configuration management
- Test email functionality

#### Notifications (`notifications.py`)

- In-app notifications
- Email notifications
- Notification preferences
- Notification history

#### Reminders (`reminders.py`)

- Payment reminders
- Invoice due date reminders
- Custom reminder scheduling
- Reminder templates

### 🎮 Gamification

#### Gamification System (`gamification.py`)

- Points and rewards system
- Achievement tracking
- Leaderboards
- User levels and progression
- Challenges and goals
- Team gamification features
- Habit formation support
- Streak tracking

### 📦 Inventory Management

#### Inventory (`inventory.py`)

- **Core Feature**: Always available.
- Product/item management
- Stock tracking
- Stock movements
- Inventory valuation
- Low stock alerts
- Inventory categories

#### Inventory Attachments (`inventory_attachments.py`)

- Product images
- Product documentation
- Attachment management

### ⚙️ Settings & Configuration

#### Settings Management (`settings.py`)

- Organization settings
- User preferences
- Currency configuration
- Tax rate configuration
- Email configuration
- Notification preferences
- Feature toggles

#### User Preferences (`user_preference_controls.py`)

- Personal preferences
- UI customization
- Notification settings
- Language preferences

#### Preference Hierarchy (`preference_hierarchy.py`)

- System-level preferences
- Organization-level preferences
- User-level preferences
- Preference inheritance

### 🔍 Search

#### Search Service (`search.py`)

- Global search across entities
- Advanced filtering
- Search indexing
- Full-text search

### 📎 File Management

#### Attachments (`attachments.py`)

- File upload and storage
- Multiple file format support
- Attachment preview
- Attachment download
- Attachment search

#### File Storage (`files.py`)

- Local file storage
- File organization
- File metadata management

### 🎨 Additional Features

#### Currency Management (`currency.py`)

- Multi-currency support
- Currency conversion
- Exchange rate management
- Currency formatting

#### Discount Rules (`discount_rules.py`)

- Discount creation and management
- Automatic discount application
- Discount rules engine

#### CRM & Client Notes (`crm.py`)

- **Core Feature**: Always available.
- Customer relationship management
- Contact management
- Interaction tracking
- Client notes and history

#### Social Features (`social_features.py`)

- User collaboration
- Activity feeds
- Sharing capabilities

#### External API (`external_api.py`)

- RESTful API endpoints
- API documentation
- API versioning

#### License Management (`license.py`)

- License key generation
- License validation
- Trial licenses
- License activation

#### Prompts (`prompts.py`)

- Custom prompt management
- Prompt templates
- Prompt versioning

---

## Commercial Features

All features in `api/commercial/` require a commercial license.

### 🤖 AI-Powered Features (`ai/`)

#### AI Assistant (`router.py`)

- Natural language queries about business data
- Intelligent invoice analysis
- Business insights and recommendations
- Automated expense categorization
- Fraud detection
- Predictive analytics
- MCP (Model Context Protocol) integration

#### AI Configuration (`config_router.py`)

- Multiple AI provider support (OpenAI, Ollama, etc.)
- AI provider configuration
- Default provider selection
- AI model selection
- API key management

#### AI PDF Processing (`pdf_processor.py`)

- Advanced OCR with AI enhancement
- Intelligent data extraction
- Document understanding
- Multi-language support

### 📦 Batch Processing (`batch_processing/`)

#### Batch Upload Service (`service.py`)

- Bulk file upload
- Batch processing queue
- Concurrent job management
- Job status tracking
- Job cancellation
- Progress monitoring

#### Batch Processing Router (`router.py`)

- Batch upload endpoints
- Job management API
- Bulk operations
- Job history

### ☁️ Cloud Storage Integration (`cloud_storage/`)

#### Cloud Storage Service (`service.py`)

- Multi-provider cloud storage support
- File synchronization
- Cloud backup
- Storage migration

#### Cloud Storage Configuration (`config.py`)

- Provider configuration
- Storage quotas
- Access control
- Cost optimization

#### Cloud Storage Providers (`providers/`)

- AWS S3
- Azure Blob Storage
- Google Cloud Storage
- Dropbox
- OneDrive
- Custom providers

#### Cloud Storage Router (`router.py`)

- Cloud storage API endpoints
- File upload/download
- Storage management

### 📤 Advanced Export (`export/`)

#### Export Service

- Advanced export formats
- Custom export templates
- Scheduled exports
- Export to cloud storage
- Export to third-party systems

### 🔗 Third-Party Integrations (`integrations/`)

#### Email Ingestion (`email/`)

- Inbound email monitoring (IMAP)
- Expense ingestion from emails
- AI-powered classification
- Automated expense creation

#### Slack Integration (`slack/`)

- Slack notifications
- Slack commands
- Slack bot integration

#### Tax Service Integrations (`tax/`)

- Automated tax calculations
- Tax compliance services
- Tax filing integration

#### Key Vault Integrations

- **AWS KMS** (`aws_kms_provider.py`) - AWS Key Management Service
- **Azure Key Vault** (`azure_keyvault_provider.py`) - Azure Key Vault
- **HashiCorp Vault** (`hashicorp_vault_provider.py`) - HashiCorp Vault
- **Key Vault Factory** (`key_vault_factory.py`) - Unified key management

#### Circuit Breaker (`circuit_breaker.py`)

- Fault tolerance
- Service resilience
- Automatic retry logic

### 🔄 Workflow Automation (`workflows/`)

#### Approval Workflows (`approvals/`)

- Multi-step approval processes
- Approval routing
- Approval notifications
- Approval history
- Custom approval rules
- Role-based approvals
- Conditional approvals
- Approval escalation

### 🔑 API Access Management (`api_access/`)

#### External API Access (`external_api`)

- API key generation and management
- External API access with API key authentication
- Rate limiting and usage tracking

#### External Transactions (`transaction_router.py`)

- Ingest transaction data via external API
- Transaction matching and duplicate detection

### 🔐 Advanced Authentication & Security

#### Single Sign-On (SSO) (`sso/router.py`)

- Google OAuth integration
- Azure AD integration
- Enterprise identity management

### 📈 Advanced Reporting (`reporting/router.py`)

- Comprehensive financial reports
- Custom date ranges
- Export to multiple formats
- Visual data representation

### 🔍 Advanced Search (`advanced_search/router.py`)

- Full-text search across all entities
- Advanced filtering and sorting
- Saved search queries

### 📝 Prompt Management (`prompt_management/router.py`)

- AI prompt templates
- Version control for prompts
- Prompt testing and optimization

---

## Code Organization

### Directory Structure

```text
api/
├── core/                          # GPLv3 Licensed
│   ├── constants/                 # System constants
│   ├── decorators/                # Utility decorators
│   ├── exceptions/                # Custom exceptions
│   ├── interfaces/                # Interface definitions
│   ├── keys/                      # Key management
│   ├── middleware/                # Request middleware
│   ├── models/                    # Database models
│   ├── routers/                   # API endpoints (36 routers)
│   ├── schemas/                   # Pydantic schemas
│   ├── services/                  # Business logic (88 services)
│   ├── settings/                  # Configuration
│   └── utils/                     # Utility functions
│
└── commercial/                    # Commercial Licensed
    ├── ai/                        # AI-powered features
    ├── api_access/                # API access management
    ├── batch_processing/          # Batch operations
    ├── cloud_storage/             # Cloud storage integration
    ├── export/                    # Advanced export
    ├── integrations/              # Third-party integrations
    ├── routers/                   # Commercial API endpoints
    └── workflows/                 # Workflow automation
```

### File Count Summary

| Location          | Routers | Services | Total Files |
| ----------------- | ------- | -------- | ----------- |
| **GPLv3 (core/)** | 30      | 88       | 200+        |
| **Commercial**    | 7       | 10+      | 50+         |

---

## Important Legal Notes

### ⚠️ GPLv3 Copyleft Requirements

If you use the GPLv3 version:

1. **Source Code Sharing**: You must make your source code available to users
2. **License Propagation**: Any derivative work must also be licensed under GPLv3
3. **No Proprietary Integration**: You cannot integrate GPLv3 code into proprietary software
4. **Attribution**: You must maintain copyright notices and license information

### ✅ Commercial License Benefits

If you purchase a commercial license:

1. **Proprietary Use**: Integrate into closed-source software
2. **No Source Sharing**: Keep your modifications private
3. **SaaS Deployment**: Offer as a hosted service
4. **White Labeling**: Rebrand and resell (subject to license terms)
5. **Support**: Professional support and maintenance

### 🚫 What You CANNOT Do

#### Moving Features Between Licenses

- **❌ CANNOT**: Take GPLv3 code and make it commercial-only
- **❌ CANNOT**: Remove features from GPLv3 version after public release
- **❌ CANNOT**: Relicense GPLv3 code as proprietary

#### What You CAN Do

- **✅ CAN**: Dual-license NEW code from the start
- **✅ CAN**: Move commercial features to GPLv3 (as a gift to community)
- **✅ CAN**: Rewrite features independently for commercial version
- **✅ CAN**: Keep minimal features in GPLv3, advanced in commercial

### 📞 Getting a Commercial License

To obtain a commercial license:

1. **Contact**: [YOUR EMAIL ADDRESS]
2. **Visit**: [YOUR WEBSITE]
3. **Discuss**: Your use case and requirements
4. **Pricing**: Custom pricing based on deployment scale

---

## Version History

- **v1.0** (2026-01-06): Initial feature comparison documentation

---

## Questions?

For licensing questions:

- **GPLv3 Questions**: See [LICENSE-GPLv3.txt](LICENSE-GPLv3.txt)
- **Commercial Questions**: See [LICENSE-COMMERCIAL.txt](LICENSE-COMMERCIAL.txt)
- **General Questions**: Contact [YOUR EMAIL ADDRESS]

**Legal Disclaimer**: This document is for informational purposes only. For legal advice regarding licensing, consult with an intellectual property attorney.
