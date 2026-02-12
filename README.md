# YourFinanceWORKS

![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)
![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)
![React: 18+](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.0-646CFF.svg?logo=vite&logoColor=white)

A modern, AI-powered multi-tenant financial management system. YourFinanceWORKS empowers businesses with professional invoicing, automated expense tracking through OCR, and deep business intelligence powered by the Model Context Protocol (MCP).

---

## ⚡ Quick Start

Get up and running in minutes using Docker:

```bash
# 1. Clone and enter
git clone git@github.com:snowsky/yourfinanceworks.git
cd yourfinanceworks

# 2. Spin up the entire stack
docker-compose up -d

# The first user to sign up in a fresh system is automatically granted super user (system admin) privileges and assigned the 'admin' role.
# If you have already created a super user, you can skip this step.
# 3. Create your first Super User
docker-compose exec api python scripts/create_super_user.py
```

- **Default Login**: Use the credentials created in step 3.

---

## 🚀 Features

### 💰 Revenue & Billing

- **Client Management** - Comprehensive client profiles with contact details, billing history, and communication tracking ([Guide](docs/features/REVENUE_CYCLE_OPTIMIZATION.md))
- **Professional Invoicing** - AI-powered invoice creation with customizable templates, automatic numbering, and tax compliance
- **Email Delivery** - Multi-provider email delivery (AWS SES, Azure, Mailgun) with professional PDF attachments
- **Payment Tracking** - Real-time payment status monitoring, partial payment support, and automated reminders
- **Revenue Cycle Optimization** - Strategic insights into billing efficiency and collection cycles ([Guide](docs/features/REVENUE_CYCLE_OPTIMIZATION.md))

### 📊 Expense Intelligence & Automation

- **AI-Powered OCR** - Upload receipts and invoices for automatic data extraction with high accuracy ([Guide](docs/features/EXPENSE_INTELLIGENCE.md))
- **Smart Categorization** - Automatic expense categorization based on vendor patterns and historical data
- **Batch Processing** - Process multiple receipts simultaneously with background worker efficiency
- **Spend Analytics** - Visual expense breakdowns, trend detection, and category-based reporting
- **Expense Workflows** - Multi-level approval system with configurable rules and audit trails ([Guide](docs/features/GOVERNANCE_WORKFLOWS.md))

### 🏦 Banking & Financial Health

- **Bank Statement Processing** - Automated transaction extraction from PDF bank statements ([Guide](docs/features/BANKING_RECONCILIATION.md))
- **Smart Transaction Matching** - AI-powered matching between bank transactions and invoices/expenses
- **Multi-Currency Support** - Handle international transactions with automatic currency conversion
- **Financial Health Monitoring** - Real-time cash flow analysis and financial metrics dashboard ([Guide](docs/features/FINANCIAL_HEALTH.md))
- **Tax Management** - Configurable tax rates and tax-compliant financial reporting

### 🕵️ Forensic Auditing & Insights

- **FinanceWorks Insights** - AI-powered "Senior Auditor" that monitors transactions for anomalies and fraud ([Guide](docs/features/FINANCEWORKS_INSIGHTS.md))
- **Risk Scoring** - Automated risk assessment (Low, Medium, High) for every financial document
- **Fraud Detection** - Protection against patterns like phantom vendors and threshold splitting
- **Audit Trails** - Permanent, defensible logs of all audit decisions and reasoning
- **Attachment Integrity** - AI analysis of receipts for signs of digital tampering

### 📈 Growth Analytics & Reporting

- **Strategic Growth Analytics** - Turn financial data into actionable business intelligence ([Guide](docs/features/GROWTH_ANALYTICS.md))
- **Interactive Dashboards** - Real-time visibility into net income, cash on hand, and receivables
- **Trend Visualization** - Dynamic charts showing revenue growth and expense patterns
- **Actionable Recommendations** - Data-driven suggestions for improving cash flow and profitability
- **Custom Reporting** - Generate P&L, Cash Flow, and Tax Summary reports in multiple formats

### 🤖 AI Services & Prompt Management

- **AI Assistant (MCP-Powered)** - Natural language queries for business insights using Model Context Protocol ([Guide](docs/features/AI_SERVICES.md))
- **Intelligent Business Queries** - Ask questions like "Who owes me money?" or "Show me overdue invoices"
- **AI Prompt Management** - Centralized control and customization of AI "instructions" ([Guide](docs/features/PROMPT_MANAGEMENT.md))
- **Template Versioning** - Version control and rollbacks for all AI prompt templates
- **Provider-Specific Overrides** - Optimize prompts for specific models (OpenAI, Ollama, etc.)

### 📦 Inventory & Product Management

- **Product Catalog** - Centralized database of items with SKUs, pricing, and cost tracking ([Guide](docs/features/INVENTORY_MANAGEMENT.md))
- **Stock Monitoring** - Real-time inventory tracking with automatic deductions on invoicing
- **Financial Integration** - Seamless inventory-to-invoice workflow with margin analysis
- **Asset Valuation** - Track total value of on-hand stock for balance sheet reporting
- **Bulk Operations** - Import/export functionality for efficient inventory management

### 🏢 Enterprise & Governance

- **Multi-Tenant Architecture** - Secure database-per-tenant isolation for organizations
- **Governance Workflows** - Advanced approval systems for invoices and expenses ([Guide](docs/features/GOVERNANCE_WORKFLOWS.md))
- **Role-Based Access Control** - Granular permissions (Admin, Editor, Viewer) with governance
- **Audit Ready** - Comprehensive logging of all financial activities and approval decisions
- **Data Export & Import** - Enterprise-grade backup and migration capabilities

### 🔒 Security & Compliance

- **Bank-Grade Security** - End-to-end encryption and secure data storage
- **SSO Integration** - Google OAuth and enterprise SSO support ([Guide](docs/features/SSO_AUTHENTICATION.md))
- **Data Privacy** - GDPR-compliant data handling with tenant isolation
- **Regular Backups** - Automated backup system with disaster recovery
- **Compliance Reporting** - Generate reports for tax and regulatory requirements

### 🛠️ Advanced Infrastructure

- **Plugin Management** - Extensible system architecture for custom functionality ([Guide](docs/features/PLUGIN_MANAGEMENT.md))
- **Cloud Storage Integration** - Secure file storage with multiple provider support ([Guide](docs/features/CLOUD_STORAGE.md))
- **Batch Processing & API Access** - RESTful API for system integration ([Guide](docs/features/BATCH_PROCESSING_API_ACCESS.md))
- **External Transactions API** - Programmatically manage third-party financial data ([Guide](docs/features/EXTERNAL_TRANSACTIONS.md))
- **Slack Integration** - Notifications and basic operations via Slack ([Guide](docs/features/SLACK_INTEGRATION.md))
- **Advanced Export** - Comprehensive data export in multiple formats ([Guide](docs/features/ADVANCED_EXPORT.md))

## 🏗️ Architecture

### 📚 Documentation Hub

For detailed guides, architecture diagrams, and administration manuals, visit our **[Documentation Hub](docs/README.md)**.

### Backend (FastAPI)

- **Framework**: FastAPI
- **Database**: Multi-tenant PostgreSQL with database-per-tenant architecture
- **Master Database**: Central PostgreSQL database for tenant metadata and super users
- **Authentication**: JWT with enhanced role-based access control
- **Multi-tenancy**: Automatic tenant database management with middleware
- **Documentation**: Auto-generated OpenAPI/Swagger docs
- **Deployment**: Docker containerized with PostgreSQL, Redis, and API services

### Frontend (React Web)

- **Framework**: React with TypeScript
- **Build Tool**: Vite
- **UI Library**: ShadCN UI components with Tailwind CSS
- **State Management**: TanStack Query for server state
- **Routing**: React Router with protected routes
- **Deployment**: Docker containerized

### Infrastructure

- **Orchestration**: Docker Compose with multi-service setup
- **Master Database**: PostgreSQL for tenant metadata and super users
- **Tenant Databases**: Isolated PostgreSQL databases per tenant
- **Caching**: Redis for session management and caching
- **Message Queue**: Kafka for asynchronous processing (OCR, bank statements)
- **Networking**: Internal Docker network for secure service communication
- **Health Checks**: Comprehensive health monitoring for all services
- **Backup System**: Automated backup and restore capabilities

## 🤖 AI Assistant Usage

The AI assistant provides intelligent business insights using your actual data. Here are some example queries you can try:

### Business Analysis Queries

- **"Can you analyze my invoice patterns and trends?"** - Get comprehensive invoice analysis
- **"What actions should I take based on my invoice data?"** - Receive actionable business recommendations
- **"Show me all my clients"** - List all clients with their details
- **"Search for clients named John"** - Find specific clients
- **"Show me all my invoices"** - List all invoices with status and amounts
- **"Find invoices for client ABC"** - Search invoices by client
- **"Show me all payments"** - View payment history
- **"Who owes me money?"** - Check outstanding balances
- **"Show me overdue invoices"** - Identify overdue payments
- **"How many invoices do I have?"** - Get invoice statistics

### General Questions

- **"What is the weather like today?"** - General questions use the LLM
- **"Explain invoice terms"** - Educational content
- **"How do I create a professional invoice?"** - Best practices guidance

### AI Configuration

1. **Navigate to Settings** → **AI Configuration** tab
2. **Configure AI Provider** - Set up OpenAI, Ollama, or other providers
3. **Set as Default** - Mark your preferred provider as default
4. **Test Configuration** - Verify your AI setup works correctly

The AI assistant automatically detects the type of query and uses the appropriate tool (MCP for business data, LLM for general questions).

## Super User System

- The first user to sign up in a fresh system is automatically granted super user (system admin) privileges and assigned the 'admin' role.
- Super users can manage all tenants, users, and databases across the system.
- All subsequent users will follow the normal role and superuser logic.

### How it works

- On first registration, if there are no users in the system, the new user is created as a super user and admin by default.
- This ensures there is always at least one super admin in the system.

## 🏢 Super User System Usage

The super user system provides comprehensive management capabilities for multi-tenant environments.
The first signed up user becomes Super User automatically or you can use the below script to create one.

### Creating a Super User

Use the provided script to create a super user:

```bash
# Run in the API container
docker-compose exec api python scripts/create_super_user.py

# Or manually run the script
cd api
python scripts/create_super_user.py
```

### Super Admin Dashboard

Access the super admin dashboard at `/super-admin` (requires super user login):

#### 📊 Overview Tab

- **System Statistics** - Total tenants, users, invoices, and payments across all tenants
- **Tenant Health** - Real-time health status of all tenant databases
- **Quick Actions** - Common administrative tasks

#### 🏢 Tenants Tab

- **Tenant Management** - Create, edit, and delete tenant organizations
- **Tenant Statistics** - Individual tenant metrics and analytics
- **Database Operations** - Health checks and database management

#### 👥 Users Tab

- **Cross-Tenant User View** - See users from all tenant databases
- **User Management** - Create users for specific tenants
- **Role Management** - Assign roles and permissions

#### 🗄️ Database Tab

- **Database Health Monitoring** - Real-time status of all databases
- **Database Operations** - Create, backup, and restore tenant databases
- **Troubleshooting Tools** - Fix missing or corrupted databases

### Database Management Tools

#### Fix Missing Tenant Databases

```bash
# Check for missing databases
docker-compose exec api python scripts/fix_missing_tenant_databases.py check

# List all databases
docker-compose exec api python scripts/fix_missing_tenant_databases.py list

# Recreate missing databases
docker-compose exec api python scripts/fix_missing_tenant_databases.py recreate

# Or use the shell script
./api/scripts/run_fix_missing_databases.sh
```

#### Database Health Monitoring

The system includes automatic database health monitoring:

- **Middleware Detection** - Automatically detects missing tenant databases
- **Auto-Recovery** - Creates missing databases on-the-fly
- **Health Endpoints** - API endpoints for database status checks
- **Logging** - Comprehensive logging of database operations

### Troubleshooting

For database-related issues, see the comprehensive troubleshooting guide:

- [Database Troubleshooting Guide](docs/technical-notes/TROUBLESHOOTING_MISSING_TENANT_DATABASES.md)

## 📧 Email Invoice Delivery

The application includes comprehensive email functionality to send invoices directly to clients with professional PDF attachments.

### 🌟 Email Features

- **Multiple Email Providers** - Support for AWS SES, Azure Email Services, and Mailgun
- **Professional Templates** - Beautiful HTML and text email templates
- **PDF Attachments** - Automatically attach invoice PDFs to emails
- **Configuration Management** - Easy setup through the settings interface
- **Test Functionality** - Test email configuration before going live
- **Error Handling** - Comprehensive error handling and logging

### 📊 Supported Email Providers

#### AWS SES (Simple Email Service)

- **Setup**: Configure AWS credentials and region
- **Features**: High deliverability, detailed analytics, cost-effective
- **Requirements**: AWS Access Key ID, Secret Access Key, and region

#### Azure Email Services

- **Setup**: Configure Azure Communication Services connection string
- **Features**: Enterprise-grade reliability, global scale
- **Requirements**: Azure Communication Services connection string

#### Mailgun

- **Setup**: Configure API key and domain
- **Features**: Developer-friendly API, detailed tracking
- **Requirements**: Mailgun API key and verified domain

### 🔧 Email Configuration

1. **Navigate to Settings** → **Email Settings** tab
2. **Enable Email Service** - Toggle the email functionality
3. **Select Provider** - Choose from AWS SES, Azure, or Mailgun
4. **Configure Credentials** - Enter your provider-specific settings
5. **Test Configuration** - Send a test email to verify setup
6. **Save Settings** - Store your configuration securely

### 📤 Sending Invoices

#### From Invoice Form

- Open any saved invoice
- Click the **Send Email** button in the preview section
- Email will be sent to the client's email address automatically

#### Via API

```bash
POST /api/v1/email/send-invoice
{
  "invoice_id": 123,
  "include_pdf": true,
  "to_email": "client@example.com"  // Optional override
}
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional, but recommended)
- **Ollama** (optional - for local LLM inference)

  If you want to run AI features locally without cloud API costs:

  ```bash
  # Start Ollama server with optimized settings
  OLLAMA_CONTEXT_LENGTH=64000 OLLAMA_HOST=0.0.0.0 OLLAMA_NUM_PARALLEL=2 ollama serve &

  # Pull required models
  ollama pull llama3.2-vision:11b  # For OCR and expense processing
  ollama pull gpt-oss:latest       # For invoice and bank statement processing
  ```

  > **Note**: When using Docker Compose, Ollama should be running on your **host machine** (not in a container). The application will connect to it via `host.docker.internal:11434`.

### Installation

1. **Clone the repository**:

   ```bash
   git clone <GIT_URL_FOR_THIS_PROJECT>
   cd finance-works
   ```

2. **Start the backend**:

   ```bash
   cd api
   pip install -r requirements.txt
   python main.py
   ```

3. **Start the web frontend**:

   ```bash
   cd ui
   npm install
   npm run dev
   ```

4. **Access the application**:
   - Web: [http://localhost:8080](http://localhost:8080)
   - API: [http://localhost:8000](http://localhost:8000)
   - API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Docker Deployment

```bash
# Copy the full env file and update with your values
cp api/.env.example.full api/.env

# Start all services (PostgreSQL, Redis, API, UI)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Create a super user (after services are running)
docker-compose exec api python scripts/create_super_user.py

# Access the application
# - Web UI: [http://localhost:8080](http://localhost:8080)
# - API: [http://localhost:8000](http://localhost:8000)
# - API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
# - Super Admin: [http://localhost:8080/super-admin](http://localhost:8080/super-admin)
```

## 🧪 Testing

Comprehensive unit testing is available for both API and UI components.

### Quick Test Commands

```bash
# Run all tests (API + UI)
./run-tests.sh

# API tests only
cd api && ./run-tests.sh

# UI tests only
cd ui && ./run-tests.sh
```

### Test Coverage

- **API Tests**: pytest with FastAPI TestClient
- **UI Tests**: Vitest with React Testing Library
- **Coverage Reports**: Generated in `api/htmlcov/` and `ui/coverage/`

### Test Structure

- **API**: `api/tests/` - Authentication, clients, invoices, payments
- **UI**: `ui/src/components/__tests__/` - Component and utility tests

For detailed testing information, see [TESTING.md](TESTING.md).

## 📚 Documentation

We have organized our documentation to help you get the most out of YourFinanceWORKS:

### 📖 User & Feature Guides

- **[Getting Started Guide](docs/user-guide/GETTING_STARTED_GUIDE.md)** - Your first 10 minutes with the app.
- **[UI Directory](docs/user-guide/PAGES_DIRECTORY.md)** - A map of every page in the system.
- **[Revenue & Invoicing](docs/features/REVENUE_CYCLE_OPTIMIZATION.md)** - Master your billing workflow.
- **[Expense Intelligence](docs/features/EXPENSE_INTELLIGENCE.md)** - Automated tracking and OCR.
- **[Banking & Reconciliation](docs/features/BANKING_RECONCILIATION.md)** - Sync with your bank.
- **[AI Services](docs/features/AI_SERVICES.md)** - How to use the AI Assistant and MCP.
- **[Governance & RBAC](docs/features/GOVERNANCE_WORKFLOWS.md)** - Multi-user approvals and roles.

### 🛠️ Administration & Development

- **[Super Admin Guide](docs/admin-guide/SUPER_ADMIN_SYSTEM.md)** - Platform oversight and tenant management.
- **[Contributing Guide](CONTRIBUTING.md)** - How to help us build a better financial tool.
- **[Support Guide](SUPPORT.md)** - Where to get help.
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Our community standards.
- **[API Reference](docs/developer/API_REFERENCE.md)** - For developers integrating with our API.

### 🗄️ Technical Archive

For historical context and deeply technical implementation details, visit the **[Technical Notes Archive](docs/technical-notes/)**.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Licensing

This project utilizes a **Split-Licensing Model** to provide maximum transparency while protecting specialized features:

1. **GNU Affero General Public License v3.0 (AGPL-3.0)**:
   - **Applies to**: `api/core/`, `ui/`, and shared project infrastructure.
   - Free to use, modify, and distribute under AGPL-3.0 terms.
   - Requires sharing source code for any network-distributed versions.
   - See [LICENSE-AGPLv3.txt](LICENSE-AGPLv3.txt) for details.

2. **Commercial License (Source Available)**:
   - **Applies to**: `api/commercial/` directory.
   - While the source code is visible, usage is restricted to licensed customers.
   - Ideal for businesses requiring enterprise features or proprietary integration.
   - Contact licensing@yourfinanceworks.com for license acquisition or visit [LICENSE-COMMERCIAL.txt](LICENSE-COMMERCIAL.txt).

## 🆘 Support

For support and questions:

1. Check the documentation
2. Review the troubleshooting guides
3. Open an issue on GitHub
4. Contact the development team
