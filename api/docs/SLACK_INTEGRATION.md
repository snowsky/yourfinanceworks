# Slack Integration for Invoice App

This document describes the minimal Slack integration that allows users to manage invoices and clients directly from Slack using slash commands and bot mentions.

## 🚀 Features

### Supported Commands

#### Client Management
- `create client John Doe, email: john@example.com, phone: 555-1234`
- `add client Jane Smith`
- `list clients`
- `find client John`
- `search client Doe`

#### Invoice Management
- `create invoice for John Doe, amount: 500.00, due: 2024-02-15`
- `invoice Jane Smith 750 due 2024-03-01`
- `list invoices`
- `find invoice 123`
- `search invoice John`

#### Reports & Analytics
- `overdue invoices`
- `outstanding balance`
- `who owes money`
- `invoice stats`
- `dashboard`

#### Help
- `help` - Show available commands

## 🏗️ Architecture

The Slack integration is built with minimal code and uses direct database access:

```
Slack → FastAPI Router → Command Parser → Service Layer → Database
```

### Components

1. **SlackCommandParser** - Parses natural language commands into structured operations
2. **SlackInvoiceBot** - Main bot logic that processes commands and formats responses
3. **Service Layer Integration** - Uses existing services for all invoice/client operations
4. **FastAPI Router** - Handles Slack webhooks and events

## 📦 Installation & Setup

### 1. Run Setup Script

#### Using Docker (Recommended)
```bash
# From the project root
docker-compose exec api python scripts/setup_slack_integration.py
```

#### Local Development
```bash
cd api
python scripts/setup_slack_integration.py
```

This creates:
- `.env.slack` - Environment template
- `slack_app_manifest.json` - Slack app configuration

### 2. Create Slack App

#### Option A: Using App Manifest (Recommended)
1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From an app manifest"
3. Upload the generated `slack_app_manifest.json`
4. Update the URLs to match your domain

#### Option B: Manual Setup
1. Go to https://api.slack.com/apps
2. Create new app
3. Add Bot User
4. Add Slash Command: `/invoice`
5. Configure Event Subscriptions
6. Set OAuth scopes (see below)

### 3. Configure OAuth Scopes

Add these Bot Token Scopes:
- `commands` - For slash commands
- `chat:write` - To send messages
- `app_mentions:read` - To respond to mentions
- `channels:read` - To read channel info
- `groups:read` - To read private channel info
- `im:read` - To read direct messages
- `mpim:read` - To read group messages

### 4. Set Webhook URLs

- **Slash Commands**: `https://your-domain.com/api/v1/slack/commands`
- **Event Subscriptions**: `https://your-domain.com/api/v1/slack/events`

### 5. Configure Environment Variables

Add to your `.env` file:

```bash
# Slack Integration
SLACK_VERIFICATION_TOKEN=your_verification_token
SLACK_BOT_TOKEN=xoxb-your-bot-token

# Optional
SLACK_SIGNING_SECRET=your_signing_secret
```

### 6. Deploy & Test

#### Using Docker
```bash
# Add Slack variables to your .env file:
echo "SLACK_VERIFICATION_TOKEN=your_token" >> .env
echo "SLACK_BOT_TOKEN=xoxb-your-bot-token" >> .env

# Restart to load new environment variables
docker-compose restart api

# Test the integration
docker-compose exec api python scripts/test_slack_integration.py
```

#### Manual Testing
1. Install the Slack app to your workspace
2. Test with: `/invoice help`
3. Check health: `curl http://localhost:8000/api/v1/slack/health`

## 🧪 Testing

### Run Tests in Docker

```bash
# Basic tests
docker-compose exec api python scripts/test_slack_integration.py

# Test with API integration
docker-compose exec -e TEST_EMAIL=your-test-email@example.com -e TEST_PASSWORD=your-test-password api python scripts/test_slack_integration.py
```

### Run Tests Locally

```bash
cd api
python scripts/test_slack_integration.py
```

### Manual Testing

Test the health endpoint:
```bash
curl http://localhost:8000/api/v1/slack/health
```

## 📝 Usage Examples

### Creating a Client
```
/invoice create client Acme Corp, email: billing@acme.com, phone: 555-0123
```

Response:
```
✅ Client created: Acme Corp
ID: 123
Email: billing@acme.com
Phone: 555-0123
```

### Creating an Invoice
```
/invoice create invoice for Acme Corp, amount: 1500.00, due: 2024-03-15
```

Response:
```
✅ Invoice created: #INV-001
Client: Acme Corp
Amount: $1500.00
Due: 2024-03-15
Status: draft
```

### Checking Overdue Invoices
```
/invoice overdue invoices
```

Response:
```
⚠️ 3 Overdue Invoices:
• #INV-001 - Acme Corp - $1500.00
• #INV-005 - XYZ Ltd - $750.00
• #INV-008 - ABC Inc - $2200.00

💰 Total overdue: $4450.00
```

## 🔧 Troubleshooting

### Common Issues

1. **Bot not responding**
   - Verify SLACK_VERIFICATION_TOKEN is set correctly
   - Check application logs
   - Ensure webhook URLs are accessible

2. **Database connection errors**
   - Check if database is accessible
   - Verify tenant configuration
   - Check service layer functionality

3. **Command parsing issues**
   - Commands are case-insensitive
   - Use commas to separate parameters
   - Check supported command patterns in the code

4. **Webhook verification failed**
   - Verify SLACK_VERIFICATION_TOKEN matches your app
   - Check if webhook URLs are accessible from Slack
   - Ensure HTTPS is used for production

### Debug Commands

Check bot health:
```bash
curl http://localhost:8000/api/v1/slack/health
```

Test MCP integration:
```bash
cd api/MCP
python -m MCP --email slack-bot@yourcompany.com --password bot_password
```

### Logs

Check application logs for Slack-related errors:
```bash
# Look for these log entries
grep "slack" /path/to/your/logs
grep "SlackInvoiceBot" /path/to/your/logs
```

## 🔒 Security Considerations

1. **Token Verification**: Always verify Slack tokens in production
2. **Bot Permissions**: Give bot user minimal required permissions
3. **HTTPS**: Use HTTPS for all webhook endpoints
4. **Rate Limiting**: Consider implementing rate limiting for Slack commands
5. **Input Validation**: All user inputs are validated through existing API validation

## 🚀 Extending the Integration

### Adding New Commands

1. Add pattern to `SlackCommandParser.patterns`
2. Add handler method to `SlackInvoiceBot`
3. Update help text

Example:
```python
# In SlackCommandParser
'delete_invoice': [r'delete invoice (?P<invoice_id>\d+)']

# In SlackInvoiceBot
async def _delete_invoice(self, params: Dict[str, Any]) -> Dict[str, Any]:
    invoice_id = params.get('invoice_id')
    # Implementation using MCP tools
```

### Adding Interactive Elements

The current implementation supports basic slash commands. To add interactive elements:

1. Implement interactive endpoint handler
2. Add buttons and menus to responses
3. Handle interactive payloads

### Multi-Tenant Support

The integration automatically supports multi-tenancy through the bot user's tenant context. Each Slack workspace should have its own bot user account in the appropriate tenant.

## 📊 Monitoring

### Health Check

The integration provides a health check endpoint:
```
GET /api/v1/slack/health
```

Response:
```json
{
  "status": "healthy",
  "bot_initialized": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Metrics to Monitor

- Command success/failure rates
- Response times
- Bot initialization status
- API client connection health

## 🤝 Contributing

To contribute to the Slack integration:

1. Follow the existing code patterns
2. Add tests for new functionality
3. Update documentation
4. Ensure minimal dependencies

The integration is designed to be lightweight and leverage existing MCP tools rather than duplicating functionality.