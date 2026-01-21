# Dual-Licensing Open Source Strategy

## Overview

This document outlines the transition from a Freemium model to a **Dual-Licensing Open Source Strategy** for the {APP_NAME} (IMS). This strategy aligns with the goal of open-sourcing the core product under **GPLv3** while sustaining the business through a **Commercial License** for proprietary enterprise modules.

---

## ⚖️ The Licensing Model

### 1. Core Edition (GPLv3)
**License:** GNU General Public License v3 (GPLv3)
**Repository:** Public (e.g., GitHub)
**Cost:** Free

The **Core Edition** contains the fully functional base application. It is "Open Core" and includes all features necessary for individuals and small teams to run the application effectively.

**Included Features:**
- ✅ **Invoice & Expense Management** (Unlimited)
- ✅ **Inventory Management**
- ✅ **Basic & Advanced Reporting**
- ✅ **Multi-user Support**
- ✅ **All AI Processing** (Invoice, Expense, Bank Statement, Chat)
- ✅ **Local File Storage**

### 2. Business Edition (Commercial License)
**License:** Proprietary / Commercial
**Repository:** Private / Closed Source
**Cost:** Paid Subscription (e.g., $29/month)

The **Business Edition** consists of **Commercial Modules** that are installed on top of the Core Edition. These modules provide enterprise-grade capabilities, integrations, and automation.

**Commercial Modules:**
- 🔒 **Cloud Storage Integration** (AWS S3, Azure, GCP)
- 🔒 **Enterprise Integrations** (SSO, Tax Services, Slack)
- 🔒 **API Access** (Programmatic access)
- 🔒 **Advanced Workflows** (Approval Workflows)
- 🔒 **Batch Processing** (Bulk operations)
- 🔒 **Priority Support** (SLA)

---

## 🏗️ Technical Architecture: Core vs. Commercial

To comply with GPLv3 and protect proprietary IP, the codebase will be physically separated.

### Directory Structure
```
invoice_app/
├── api/
│   ├── core/                  # GPLv3 Licensed Code
│   │   ├── routers/           # Core endpoints (invoices, expenses, ai)
│   │   ├── services/          # Core logic
│   │   └── models/            # Database models
│   │
│   └── commercial/            # Proprietary Modules (Not in public repo)
│       ├── cloud_storage/     # Cloud storage providers
│       ├── integrations/      # Slack, Tax, SSO
│       ├── workflows/         # Approval engines
│       └── api_access/        # API key management
```

### Licensing Mechanism
1. **Default State:** Application runs in "Core Mode" (GPLv3).
2. **Activation:** Admin enters a **Commercial License Key**.
3. **Validation:** System verifies the key against the License Server.
4. **Loading:** If valid, the system dynamically loads/enables the **Commercial Modules**.

---

## 🔄 Conversion Strategy

### From Personal (Free) to Core (GPLv3)
- **Existing Free Users** automatically become **Core Edition** users.
- **No loss of functionality:** They retain all core features, including unlimited AI.
- **Messaging:** "You are using the Open Source Core Edition."

### From Business (Paid) to Commercial License
- **Existing Paid Users** are migrated to the **Business Edition**.
- **License Key:** They receive a commercial license key to unlock modules.
- **Messaging:** "Thank you for supporting the project with the Business Edition."

### Upgrade Triggers
We retain the "Upgrade to Business" prompts, but the messaging shifts from "Unlock Feature" to "Install Commercial Module".

| Trigger | Message |
|---------|---------|
| **Cloud Storage** | "Cloud Storage is a Commercial Module for enterprise reliability. Upgrade to Business Edition." |
| **API Access** | "API Access is a Commercial Module for custom integrations. Upgrade to Business Edition." |
| **SSO Login** | "Single Sign-On is a Commercial Module for enterprise security. Upgrade to Business Edition." |

---

## 🚀 Implementation Roadmap

### Phase 1: Infrastructure & Separation
1. **Refactor Codebase:** Separate `core` and `commercial` directories.
2. **Update Feature Config:** Replace `personal_allowed` with `license_tier: 'core' | 'commercial'`.
3. **Implement License Loader:** Logic to load commercial modules only when a valid license is present.
4. **Open Source Release:** Publish `core` to public repository with GPLv3 license.

### Phase 2: User Experience
1. **Update UI:** Rename "Personal" to "Core Edition" and "Business" to "Business Edition".
2. **License Input:** Add UI to enter Commercial License Key.
3. **Upgrade Flows:** Update all upgrade prompts to reflect the new model.

### Phase 3: Commercial Launch
1. **Sales Page:** Launch website for purchasing Commercial Licenses.
2. **Documentation:** Publish docs for Core (Community) and Business (Commercial).
3. **Support Channels:** Establish Community Support (GitHub Issues) vs Priority Support (Email/Portal).

---

## 💰 Long-Term Viability

This model ensures:
1. **Compliance:** Strict separation satisfies GPLv3 requirements.
2. **Community:** Open sourcing the core attracts developers and users.
3. **Revenue:** Enterprise features remain protected and monetized.
4. **Sustainability:** A clear path from free user to paying customer.
