# Email Notifications Feature

## Overview

The email notifications feature allows users to configure which operations trigger email notifications. Users can customize their notification preferences for various system operations including user management, client operations, invoice activities, and payment tracking.

## Features

### ✅ Implemented Components

#### 1. Database Model
- **EmailNotificationSettings** table in each tenant database
- Per-user notification preferences
- Support for custom notification email addresses
- Daily and weekly summary options

#### 2. Notification Categories
- **User Operations**: Created, updated, deleted, login
- **Client Operations**: Created, updated, deleted
- **Invoice Operations**: Created, updated, deleted, sent, paid, overdue
- **Payment Operations**: Created, updated, deleted
- **Settings Operations**: Updated
- **Summary Notifications**: Daily and weekly summaries

#### 3. Backend API
- **GET /api/v1/notifications/settings** - Get user's notification settings
- **PUT /api/v1/notifications/settings** - Update notification settings
- **POST /api/v1/notifications/test** - Send test notification

#### 4. Notification Service
- **NotificationService** class for handling email notifications
- Professional HTML and text email templates
- Integration with existing email service (AWS SES, Azure, Mailgun)
- Automatic fallback to user's account email if custom email not set

#### 5. UI Components
- New "Notifications" tab in Settings page
- Organized by operation categories
- Toggle switches for each notification type
- Custom email address field
- Test notification functionality
- Save settings with loading states

#### 6. Integration Points
- Notification triggers added to key operations (e.g., invoice creation)
- Utility functions for easy integration throughout the app
- Audit logging for notification settings changes

## File Structure

```
api/
├── models/
│   └── models_per_tenant.py          # EmailNotificationSettings model
├── schemas/
│   └── email_notifications.py        # Pydantic schemas
├── services/
│   └── notification_service.py       # Core notification service
├── routers/
│   └── notifications.py              # API endpoints
├── utils/
│   └── notifications.py              # Helper functions for triggering notifications
└── scripts/
    ├── add_notification_settings_table.py    # Database migration
    ├── run_notification_migration.sh         # Migration runner
    └── test_notifications.py                 # Test script

ui/src/pages/
└── Settings.tsx                      # Updated with notifications tab
```

## Usage

### 1. Database Setup
Run the migration to create the notification settings table:
```bash
./api/scripts/run_notification_migration.sh
```

### 2. User Configuration
Users can configure their notification preferences in Settings → Notifications tab:
- Toggle individual notification types on/off
- Set custom notification email (optional)
- Test notifications to verify email configuration
- Save settings

### 3. Triggering Notifications
Notifications are automatically triggered when operations occur:
```python
from utils.notifications import notify_invoice_created

# In your operation handler
notify_invoice_created(db, invoice, current_user.id)
```

### 4. Email Templates
Professional email templates include:
- Company branding
- Operation details
- Timestamp information
- Unsubscribe information
- Responsive HTML design

## Configuration Requirements

### Email Service Setup
Notifications require email service to be configured in Settings → Email tab:
- Choose provider (AWS SES, Azure Email Services, or Mailgun)
- Configure credentials
- Enable email service
- Test email configuration

### Default Settings
New users get these default notification settings:
- ✅ Client created/deleted
- ✅ Invoice created/deleted/sent/paid/overdue
- ✅ Payment created/deleted
- ❌ User operations (except for admins)
- ❌ Settings updates
- ❌ Daily/weekly summaries

## Security & Privacy

- Notifications only sent to authenticated users
- Custom email addresses are validated
- No sensitive data (passwords, API keys) included in notifications
- Users can disable all notifications
- Audit logging for settings changes

## Testing

### Manual Testing
1. Configure email service in Settings → Email
2. Go to Settings → Notifications
3. Enable desired notifications
4. Click "Send Test Notification"
5. Perform operations (create invoice, add client, etc.)
6. Check email for notifications

### Automated Testing
```bash
# Run notification system tests
docker-compose exec api python scripts/test_notifications.py
```

## Known limitations / TODO

- Email settings validation currently returns success for some providers:
  - AWS SES: validation stub returns `True` without a live API call.
  - Azure Email: validation stub returns `True` without a live API call.
  - Mailgun: performs a lightweight API request.

- Impact: the “Test configuration” action may report success even if credentials/region are incorrect for SES/Azure. Prefer sending a real test email to verify.

- TODO:
  - Implement real SES checks (e.g., STS GetCallerIdentity + SES GetSendQuota) and surface provider errors.
  - Implement Azure Email connectivity/credential validation.

## Future Enhancements

### Planned Features
- **Daily/Weekly Summaries** - Automated summary emails
- **Notification Templates** - Customizable email templates
- **Notification History** - Log of sent notifications
- **Bulk Notification Settings** - Admin can set defaults for all users
- **SMS Notifications** - Text message notifications
- **In-App Notifications** - Browser notifications
- **Notification Scheduling** - Delayed or scheduled notifications

### Integration Opportunities
- **Slack Integration** - Send notifications to Slack channels
- **Webhook Support** - HTTP callbacks for notifications
- **Mobile Push Notifications** - For mobile app users
- **Calendar Integration** - Add events to calendar

## Troubleshooting

### Common Issues

1. **Notifications not sending**
   - Check email service configuration
   - Verify notification settings are enabled
   - Check server logs for errors

2. **Test notification fails**
   - Ensure email service is properly configured
   - Check email provider credentials
   - Verify recipient email address

3. **Database migration fails**
   - Ensure PostgreSQL is running
   - Check database permissions
   - Verify tenant databases exist

### Debug Commands
```bash
# Check notification settings table exists
docker-compose exec api python -c "
from models.database import get_tenant_db_url
from sqlalchemy import create_engine, inspect
engine = create_engine(get_tenant_db_url(1))
inspector = inspect(engine)
print('email_notification_settings' in inspector.get_table_names())
"

# Test notification service
docker-compose exec api python scripts/test_notifications.py
```

## API Documentation

### Get Notification Settings
```http
GET /api/v1/notifications/settings
Authorization: Bearer <token>
```

### Update Notification Settings
```http
PUT /api/v1/notifications/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "invoice_created": true,
  "client_created": true,
  "payment_created": true,
  "notification_email": "custom@example.com",
  "daily_summary": false,
  "weekly_summary": false
}
```

### Send Test Notification
```http
POST /api/v1/notifications/test
Authorization: Bearer <token>
```

## Implementation Notes

- Notifications are sent asynchronously to avoid blocking operations
- Failed notifications are logged but don't fail the main operation
- Email templates are responsive and work across email clients
- Notification settings are per-user and per-tenant
- The system gracefully handles missing email configuration

This feature provides a comprehensive notification system that keeps users informed about important activities in their invoice management system while maintaining flexibility and user control.