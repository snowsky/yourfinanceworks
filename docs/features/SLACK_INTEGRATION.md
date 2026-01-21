# Slack Integration

Manage your invoices, clients, and financial reports directly from your favorite workspace using the YourFinanceWORKS Slack bot.

## 🚀 Features

Our Slack integration allows you to perform common tasks using simple slash commands:

### Client Management

- **Create Client**: `/invoice create client Acme Corp, email: billing@acme.com`
- **List/Search**: `/invoice list clients` or `/invoice search client John`

### Invoice Management

- **Create Invoice**: `/invoice create invoice for Acme Corp, amount: 1500, due: 2024-12-31`
- **List/Search**: `/invoice list invoices` or `/invoice find invoice #INV-001`

### Reports & Insights

- **Overdue Invoices**: `/invoice overdue invoices`
- **Outstanding Balance**: `/invoice who owes money`
- **Dashboard Summary**: `/invoice dashboard`

---

## 🛠️ Setup & Configuration

Integrating Slack with your organization is a straightforward process:

### 1. Run the Setup Script

From your terminal, run the setup script to generate your app manifest and environment template:

```bash
python api/scripts/setup_slack_integration.py
```

### 2. Create the Slack App

- Go to the [Slack API Dashboard](https://api.slack.com/apps).
- Create a new app "From a manifest" using the generated `slack_app_manifest.json`.
- Update the Verification and Event URLs to point to your deployed API.

### 3. Configure Environment

Add your Slack tokens to your system configuration or `.env` file:

```bash
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your-secret
```

---

## 🔒 Security

- **Verification**: All requests from Slack are verified using a signing secret to ensure authenticity.
- **Tenant Context**: The bot automatically operates within the context of the organization it was installed for.
- **Permission Scopes**: The bot requires minimal scopes (`commands`, `chat:write`, `app_mentions:read`) to function.

---

### Pro Tips

- **Natural Language**: The bot uses a smart command parser, so you can often omit keywords or simplify phrases.
- **Help Command**: Type `/invoice help` at any time to see the full list of supported commands and syntax.
