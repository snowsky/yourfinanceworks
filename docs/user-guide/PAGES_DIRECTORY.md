# Directory of Pages (UI Reference)

This directory provides a brief overview of all major pages and components within the YourFinanceWORKS interface to help you navigate the system efficiently.

## Core Workspace

### [Dashboard](../../ui/src/pages/Index.tsx)

The "Heart" of the application. Provides a real-time financial summary, recent activity, and quick actions like "New Invoice" or "Upload Receipt".

### [Invoices](../../ui/src/pages/Invoices.tsx)

Management hub for all your accounts receivable. View status, filter by client, and create new professional PDF invoices.

### [Expenses](../../ui/src/pages/Expenses.tsx)

Track all outbound spending. Includes views for pending approvals, OCR processing status, and categorized spend history.

### [Clients](../../ui/src/pages/Clients.tsx)

A mini-CRM to manage your customer relationships. Store billing details, contact info, and view client-specific financial history.

### [Statements](../../ui/src/pages/Statements.tsx)

The place for bank reconciliation. Upload your bank statement PDFs and match them to your internal invoices and expenses.

---

### [Analytics](../../ui/src/pages/Analytics.tsx)

Provides deeper visual insights into your business trends, revenue growth, and expense breakdowns using charts and graphs.

### [Inventory](../../ui/src/pages/Inventory.tsx)

Manage your product and service catalog. Track stock levels, set unit costs, and sync data with your invoicing workflow.

### [Reports](../../ui/src/pages/Reports.tsx)

Generate static financial reports for tax filing or stakeholder review, including Profit & Loss and Cash Flow statements.

## Management & Support

### [Settings](../../ui/src/pages/Settings.tsx)

Configure your organization’s profile, AI providers, email settings, tax rates, and team member roles.

### [Super Admin](../../ui/src/pages/SuperAdmin.tsx)

_(Visible only to Super Users)_ Centralized management for multi-tenant environments, database health monitoring, and system-wide configurations.

### [Activity](../../ui/src/pages/ActivityPage.tsx)

A full audit trail of all actions taken within your organization, from document creation to approval status changes.

## Authentication & Security

### [Login](../../ui/src/pages/Login.tsx) & [Signup](../../ui/src/pages/Signup.tsx)

Secure entry points for users and new organizations. Includes support for MFA and SSO.

### [Profile](../../ui/src/pages/Settings.tsx)

Manage your personal credentials, timezone preferences, and security settings.

---

### Tips for Navigation

- **Global Search**: Use the search bar at the top of any page to quickly find clients, invoices, or even text inside receipt attachments.
- **AI Assistant**: Click the AI Assistant icon in the bottom right to ask questions about the page you are currently viewing.
