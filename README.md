# Invoice Management Application

A modern, multi-tenant invoice management system built with FastAPI and React, with full mobile app support for iOS and Android. This application allows businesses to manage clients, create invoices, track payments, and generate professional PDF invoices with comprehensive CRM capabilities and data management features.

## 🚀 Features

### Core Functionality
- **Multi-tenant Architecture** - Isolated data per tenant/organization
- **Client Management** - Add, edit, and manage customer information with CRM capabilities
- **Smart Invoice Creation** - Generate professional invoices with automatic numbering and intelligent status management
- **Advanced Invoice Editing** - Individual item updates with immutable paid invoice protection
- **Payment Tracking** - Record and track payments against invoices with automatic status updates
- **Dashboard Analytics** - Overview of financial metrics and statistics
- **PDF Generation** - Export invoices as professional PDF documents
- **Email Delivery** - Send invoices directly to clients via email with PDF attachments
- **Responsive Design** - Modern UI that works on desktop and mobile

### 📱 Mobile App Support
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

### Technical Features
- **RESTful API** - Clean, documented API endpoints with consistent data structures
- **AI Integration (MCP)** - Model Context Protocol server for AI assistant integration
- **Email Service Integration** - Support for AWS SES, Azure Email Services, and Mailgun with proper API routing
- **Real-time Updates** - Instant UI updates with optimistic rendering
- **Search & Filtering** - Advanced filtering and search capabilities
- **Docker Support** - Containerized deployment ready
- **Database Migrations** - Automated schema management

## 🆕 Recent Major Updates & Improvements

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
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: JWT with fastapi-users
- **Documentation**: Auto-generated OpenAPI/Swagger docs
- **Deployment**: Docker containerized

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
- **Orchestration**: Docker Compose
- **Database**: Persistent SQLite with volume mounting
- **Networking**: Internal Docker network for service communication

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
POST /api/email/send-invoice
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
   git clone <repository-url>
   cd hao_invoice_app
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
   - Web: http://localhost:5173
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📚 Documentation

- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [Mobile App Guide](mobile/README.md) - Mobile app setup and usage
- [Backend API](api/README.md) - Backend development guide
- [Frontend Guide](ui/README.md) - Frontend development guide

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

1. Check the documentation
2. Review the troubleshooting guides
3. Open an issue on GitHub
4. Contact the development team

---

**Note**: The mobile app requires the backend API to be running. Ensure your FastAPI backend is accessible before testing the mobile app.
