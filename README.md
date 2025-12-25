# YourFinanceWORKS

A modern, multi-tenant financial management system built with FastAPI and React, with ugly mobile app support for iOS and Android. This application allows businesses to manage clients, create invoices, track payments, and generate professional PDF invoices with comprehensive CRM capabilities and data management features.

## 🚀 Features

### Core Functionality
- **Multi-tenant Architecture** - Isolated data per tenant/organization with database-per-tenant design
- **Super User System** - Complete super user management for cross-tenant operations
- **Client Management** - Add, edit, and manage customer information with CRM capabilities
- **Smart Invoice Creation** - Generate professional invoices with automatic numbering and intelligent status management
- **Advanced Invoice Editing** - Individual item updates with immutable paid invoice protection
- **Payment Tracking** - Record and track payments against invoices with automatic status updates
- **Dashboard Analytics** - Overview of financial metrics and statistics
- **PDF Generation** - Export invoices as professional PDF documents
- **Email Delivery** - Send invoices directly to clients via email with PDF attachments
- **Responsive Design** - Modern UI that works on desktop and mobile

### 📱 Mobile App Support (Under Development)
- **iOS & Android Apps** - Native mobile applications with full feature parity
- **Cross-Platform** - Single codebase for both iOS and Android
- **Offline Support** - Basic offline functionality with data caching
- **Touch-Optimized** - Designed specifically for mobile interactions
- **Push Notifications** - Real-time updates and alerts
- **Native Performance** - Optimized for mobile devices

### 🆕 CRM & Client Management
- **Client Notes System** - Add, edit, update, and delete client notes with timestamps
- **Note Management** - Inline editing with save/cancel functionality
- **User Attribution** - Track which user created each note
- **Complete CRM History** - Comprehensive client interaction tracking
- **Enhanced Client Profiles** - Rich client information with note history

### 💰 Currency & International Support
- **Multi-Currency Support** - Support for multiple currencies with proper formatting
- **Currency Selection** - Choose preferred currency per client and invoice
- **Dynamic Currency API** - Real-time currency support with fallback handling
- **Localized Display** - Proper currency formatting and display

### 📊 Data Management & Backup
- **Complete Data Export** - Export all business data to SQLite format
- **Data Import/Restore** - Import data from previous backups with conflict resolution
- **Smart Import Logic** - Automatic invoice number generation to avoid conflicts
- **Data Integrity** - Comprehensive validation and error handling during import/export
- **Backup Recommendations** - Built-in guidance for data safety best practices

### 🤖 AI Assistant with MCP Integration
- **Intelligent Business Queries** - AI assistant automatically detects business-related questions and uses real data
- **Comprehensive Tool Integration** - 9 different MCP tools for invoice analysis, client management, and business insights
- **Dynamic Authentication** - Uses current user's session for secure data access
- **Smart Pattern Detection** - Routes business queries to MCP tools, general questions to LLM
- **Real-time Data Analysis** - Provides insights based on actual invoice, client, and payment data
- **Actionable Recommendations** - Suggests business actions based on data analysis
- **Multi-Provider Support** - Configurable AI providers (OpenAI, Ollama, Anthropic, Google, Custom)
- **Fallback Intelligence** - Seamlessly switches between MCP tools and LLM based on query type

### Invoice Management Enhancements ✨
- **Intelligent Item Management** - Individual invoice item updates without losing data
- **Immutable Paid Invoices** - Paid invoices are protected from accidental changes (except status)
- **Smart Status Controls** - Enhanced status filtering and management
- **Enhanced Data Persistence** - Invoice descriptions and details are properly saved and loaded
- **Consistent API Responses** - All endpoints return complete invoice data including items

### Authentication & Security
- **User Authentication** - Secure login/signup with JWT tokens
- **Role-based Access** - Admin, user, and viewer roles
- **Google SSO** - Optional Google OAuth integration
- **Tenant Isolation** - Complete data separation between organizations

### 🏢 Super User System
- **Cross-Tenant Management** - Super users can manage all tenants from a single interface
- **Tenant CRUD Operations** - Create, read, update, and delete tenant organizations
- **User Management Across Tenants** - View and manage users from all tenant databases
- **Database Operations** - Health checks, backup, restore, and database recreation
- **Tenant Statistics** - Real-time analytics for each tenant (users, clients, invoices, payments)
- **Master Database Architecture** - Central database for tenant metadata and super user information
- **Database Per Tenant Model** - Each tenant gets its own isolated database for maximum security
- **Super Admin Dashboard** - Comprehensive web interface with tabs for different management functions
- **Automatic Database Recovery** - Middleware automatically creates missing tenant databases
- **Database Troubleshooting Tools** - Scripts and tools for diagnosing and fixing database issues

### Technical Features
- **RESTful API** - Clean, documented API endpoints with consistent data structures
- **AI Integration (MCP)** - Enhanced Model Context Protocol server with dynamic authentication and comprehensive tool integration
- **Email Service Integration** - Support for AWS SES, Azure Email Services, and Mailgun with proper API routing
- **Real-time Updates** - Instant UI updates with optimistic rendering
- **Search & Filtering** - Advanced filtering and search capabilities
- **Docker Support** - Containerized deployment ready
- **Database Migrations** - Automated schema management

## 🆕 Recent Major Updates & Improvements

### 🏢 Super User System & Multi-Tenant Architecture
- **✅ Complete Super User Implementation** - Full super user system for managing multiple tenants
- **✅ Database Per Tenant Architecture** - Each tenant gets its own isolated database (e.g., `tenant_1`, `tenant_2`)
- **✅ Master Database for Tenant Management** - Central database for tenant metadata and super user information
- **✅ Super Admin Dashboard** - Comprehensive web interface for super users to manage all tenants
- **✅ Cross-Tenant User Management** - CRUD operations for users across all tenants
- **✅ Tenant Statistics & Analytics** - Real-time statistics for each tenant (users, clients, invoices, payments)
- **✅ Database Operations** - Health checks, backup, restore, and database recreation tools
- **✅ Enhanced RBAC** - Role-based access control with super user permissions
- **✅ Super User Authentication** - Authentication that doesn't require tenant context
- **✅ Tenant CRUD Operations** - Create, read, update, and delete tenant organizations

### 🛠️ Database Management & Troubleshooting
- **✅ Automatic Database Recovery** - Middleware automatically detects and creates missing tenant databases
- **✅ Database Fix Scripts** - Comprehensive scripts for checking and fixing database issues
- **✅ Docker Integration** - Shell scripts for running database fixes in containerized environments
- **✅ Database Health Monitoring** - Real-time health checks for all tenant databases
- **✅ Missing Database Detection** - Automatic detection of missing tenant databases with recovery options
- **✅ Troubleshooting Documentation** - Complete guide for database-related issues
- **✅ Database Recreation Tools** - Safe recreation of tenant databases with data preservation options

### 🔧 Technical Improvements & Bug Fixes
- **✅ React Hooks Violations Fixed** - Resolved "hooks order changed" errors in SuperAdmin and AIAssistant components
- **✅ Proxy Configuration Fix** - Fixed Docker service naming issue between UI and API services
- **✅ Component Architecture Enhancement** - Improved component structure to prevent conditional hook calls
- **✅ Enhanced Error Handling** - Better error messages and recovery mechanisms
- **✅ Service Discovery** - Fixed service communication issues in Docker environment
- **✅ Authentication Flow Improvements** - Better handling of authentication states and redirects

### 🤖 Enhanced AI Assistant with MCP Integration
- **✅ Dynamic Authentication** - AI assistant uses current user's JWT token instead of hardcoded credentials
- **✅ Comprehensive MCP Tools** - 9 different business query patterns with real data access:
  * Invoice pattern analysis and trend detection
  * Actionable business recommendations
  * Client management (list, search, details)
  * Invoice management (list, search, status)
  * Payment tracking and history
  * Overdue invoice detection
  * Invoice statistics and metrics
  * Currency management
  * Outstanding balance tracking
- **✅ Smart Pattern Detection** - Automatically routes business queries to MCP tools, general questions to LLM
- **✅ Real Data Integration** - All MCP tools access actual database data through authenticated API calls
- **✅ Intelligent Fallback** - Seamlessly falls back to LLM for non-business queries
- **✅ SQLAlchemy Serialization Fix** - Resolved Row object serialization issues in AI endpoints
- **✅ User Role Management** - Fixed admin role requirements for settings and AI configuration
- **✅ Test Coverage** - Comprehensive test scripts for MCP integration validation
- **✅ PDF Upload AI Priority System** - Smart configuration priority: AI Config → Environment Variables → Manual fallback

### 🎯 Help Center & Onboarding System
- **✅ Interactive Help Center** - Comprehensive help system with guided tours, documentation, and support
- **✅ Multi-Language Support** - Help Center translated to English, Spanish, and French
- **✅ Guided Tours System** - Interactive onboarding tours for dashboard and navigation
- **✅ Enhanced Tour Coverage** - Added tours for Payments, Expenses, and Bank Statements sections
- **✅ Modal Management** - Fixed tour overlay interactions and modal closing behavior
- **✅ Responsive Layout** - Improved sidebar layout with proper spacing for help and language controls

### 🎯 CRM System Implementation
- **✅ Complete Client Notes System** - Full CRUD operations for client notes with user attribution
- **✅ Inline Note Editing** - Edit notes directly in the interface with save/cancel functionality
- **✅ Note Deletion with Confirmation** - Safe note deletion with preview confirmation dialogs
- **✅ Timestamp Tracking** - Automatic creation and update timestamps for all notes
- **✅ User Attribution** - Track which user created each note for accountability
- **✅ Enhanced Client Profiles** - Rich client detail pages with integrated note management

### 💾 Data Management & Backup System
- **✅ Complete Data Export** - Export all tenant data (clients, invoices, payments, notes, settings) to SQLite
- **✅ Data Import/Restore** - Import data from SQLite backups with intelligent conflict resolution
- **✅ Smart Invoice Number Generation** - Automatic generation of unique invoice numbers during import
- **✅ Data Integrity Protection** - Comprehensive validation and rollback on import errors
- **✅ User-Friendly Interface** - Intuitive data management UI with clear warnings and guidance
- **✅ Best Practices Integration** - Built-in recommendations for backup and restore procedures

### 💰 Currency System Enhancement
- **✅ Multi-Currency Support** - Full support for multiple currencies with proper API integration
- **✅ Client Currency Preferences** - Set and save preferred currency per client
- **✅ Dynamic Currency Loading** - Real-time currency options with fallback handling
- **✅ Currency Display Components** - Consistent currency formatting throughout the application
- **✅ API Integration Fix** - Resolved currency selector API connectivity issues

### 🔧 Bug Fixes & System Improvements
- **✅ Invoice Status Filtering** - Fixed invoice status dropdown and backend filtering
- **✅ Client Currency Updates** - Resolved issues with saving client preferred currency
- **✅ API Response Consistency** - Fixed missing fields in client and invoice API responses
- **✅ Currency Selector Integration** - Fixed "API not available" errors in currency selection
- **✅ Import Conflict Resolution** - Resolved unique constraint errors during data import
- **✅ Error Handling Enhancement** - Improved error messages and user feedback throughout

### 🎨 UI/UX Improvements
- **✅ Refactored Data Management Tab** - Complete redesign of export/import interface
- **✅ Visual Status Indicators** - Color-coded status indicators and progress feedback
- **✅ Enhanced File Selection** - Improved file upload interface with visual feedback
- **✅ Responsive Design Updates** - Better mobile and tablet experience
- **✅ Professional Layout** - Clean, modern interface with improved information hierarchy
- **✅ Interactive Elements** - Better button states, loading indicators, and user feedback
- **✅ Dashboard Layout Enhancement** - Improved invoice overview chart width for better data visualization
- **✅ Sidebar Layout Optimization** - Fixed overflow issues with help center and language picker positioning

### 📈 Performance & Reliability
- **✅ Database Optimization** - Improved query performance and data handling
- **✅ Error Recovery** - Enhanced error handling with proper rollback mechanisms
- **✅ API Reliability** - More robust API responses with consistent data structures
- **✅ Session Management** - Better handling of database sessions and transactions
- **✅ Memory Management** - Improved cleanup of temporary files and resources

### Invoice Management Enhancements
- **✅ Fixed Invoice Item Persistence** - Invoice item descriptions now save correctly without reverting to default values
- **✅ Enhanced Item Update Logic** - Individual items can be updated, added, or removed without affecting other items
- **✅ Immutable Paid Invoice Protection** - Paid invoices are now read-only except for status changes to prevent accidental modifications
- **✅ Smart Status Management** - Enhanced status filtering and management capabilities

### API & Data Consistency
- **✅ Complete API Responses** - All invoice endpoints now return consistent data structures including invoice items
- **✅ Proper Item ID Handling** - Invoice items include proper IDs for reliable updates and tracking
- **✅ Enhanced Error Handling** - Eliminated "Invoice items could not be loaded properly" errors
- **✅ Centralized API Client** - All frontend requests use the centralized API client for better reliability

### User Experience Improvements
- **✅ Visual Feedback for Paid Invoices** - Clear indication when invoices are locked due to paid status
- **✅ Improved Form Validation** - Better error messages and validation for invoice creation and editing
- **✅ Enhanced Data Loading** - More reliable data loading with proper fallback handling
- **✅ Professional UI Components** - Consistent design language with ShadCN UI components

## 🏗️ Architecture

### Backend (FastAPI)
- **Framework**: FastAPI with Python 3.11
- **Database**: Multi-tenant PostgreSQL with database-per-tenant architecture
- **Master Database**: Central PostgreSQL database for tenant metadata and super users
- **Authentication**: JWT with enhanced role-based access control
- **Multi-tenancy**: Automatic tenant database management with middleware
- **Documentation**: Auto-generated OpenAPI/Swagger docs
- **Deployment**: Docker containerized with PostgreSQL, Redis, and API services

### Frontend (React Web)
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **UI Library**: ShadCN UI components with Tailwind CSS
- **State Management**: TanStack Query for server state
- **Routing**: React Router with protected routes
- **Deployment**: Docker containerized

### Mobile App (React Native)
- **Framework**: React Native with Expo
- **Language**: TypeScript
- **Navigation**: React Navigation v6
- **State Management**: React Query (TanStack Query)
- **UI Components**: React Native Paper
- **Build Tool**: EAS Build
- **Platforms**: iOS, Android, Web

### Infrastructure
- **Orchestration**: Docker Compose with multi-service setup
- **Master Database**: PostgreSQL for tenant metadata and super users
- **Tenant Databases**: Isolated PostgreSQL databases per tenant
- **Caching**: Redis for session management and caching
- **Networking**: Internal Docker network for secure service communication
- **Health Checks**: Comprehensive health monitoring for all services
- **Backup System**: Automated backup and restore capabilities

## 📱 Mobile App Setup

### Quick Start

1. **Navigate to mobile directory**:
   ```bash
   cd mobile
   ```

2. **Run the setup script**:
   ```bash
   ./setup.sh
   ```

3. **Start development**:
   ```bash
   npm start
   ```

4. **Run on device/simulator**:
   ```bash
   # iOS (macOS only)
   npm run ios
   
   # Android
   npm run android
   ```

### Building for Production

```bash
# Build for iOS
eas build --platform ios --profile production

# Build for Android
eas build --platform android --profile production

# Submit to app stores
eas submit --platform ios
eas submit --platform android
```

For detailed mobile app documentation, see [mobile/README.md](mobile/README.md).

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
- [Database Troubleshooting Guide](api/docs/TROUBLESHOOTING_MISSING_TENANT_DATABASES.md)

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
- Docker (optional)
- iOS Simulator (for mobile development on macOS)
- Android Studio (for mobile development)

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

4. **Start the mobile app** (optional):
   ```bash
   cd mobile
   ./setup.sh
   npm start
   ```

5. **Access the application**:
   - Web: http://localhost:8080
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Docker Deployment

```bash
# Start all services (PostgreSQL, Redis, API, UI)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Create a super user (after services are running)
docker-compose exec api python scripts/create_super_user.py

# Access the application
# - Web UI: http://localhost:8080
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Super Admin: http://localhost:8080/super-admin
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

- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [Testing Guide](TESTING.md) - Comprehensive testing documentation
- [Mobile App Guide](mobile/README.md) - Mobile app setup and usage
- [Backend API](api/README.md) - Backend development guide
- [Frontend Guide](ui/README.md) - Frontend development guide
- [Database Troubleshooting](api/docs/TROUBLESHOOTING_MISSING_TENANT_DATABASES.md) - Database troubleshooting guide
- [Super User System](api/docs/SUPER_USER_SYSTEM.md) - Super user system documentation
- [Data Export & Import Guide](docs/DATA_EXPORT_IMPORT_GUIDE.md) - Complete backup and restore documentation
- [PDF Upload AI Priority System](docs/PDF_UPLOAD_AI_PRIORITY.md) - AI configuration priority system for PDF processing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Licensing

This project is dual-licensed under two options:

1. **GNU General Public License v3 (GPLv3)**:
   - Free to use, modify, and distribute under the terms of the GPLv3.
   - Requires that derivative works be licensed under GPLv3 and source code be shared.
   - Ideal for open source projects and community use.
   - See [LICENSE-GPLv3.txt](LICENSE-GPLv3.txt) for the full license text.

2. **Commercial License**:
   - Available for proprietary use, allowing integration into closed-source software without GPLv3 obligations.
   - Suitable for businesses or commercial applications.
   - To obtain a commercial license, contact us at [YOUR EMAIL ADDRESS] or visit [YOUR WEBSITE].
   - See [LICENSE-COMMERCIAL.txt](LICENSE-COMMERCIAL.txt) for more information.

## 🆘 Support

For support and questions:

1. Check the documentation
2. Review the troubleshooting guides
3. Open an issue on GitHub
4. Contact the development team

---

**Note**: The mobile app requires the backend API to be running. Ensure your FastAPI backend is accessible before testing the mobile app.
