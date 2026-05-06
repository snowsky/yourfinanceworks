# Agent CLI

The Finance Agent CLI provides command-line access to YourFinanceWORKS workflows, including authenticated AI chat, document ingestion, portfolio monitoring, and investment analysis.

## Overview

The CLI is designed for operators and power users who want to work with YourFinanceWORKS from a terminal while reusing the same backend permissions, tenant isolation, and MCP-powered assistant path used by the web app.

Key capabilities:

- **Authenticated AI chat**: Ask natural-language questions against your business data.
- **Agentic MCP tool planning**: The backend model plans which MCP tools and arguments are needed before tool execution.
- **Formatted terminal output**: Chat responses print as readable text by default, with `--json` available for automation.
- **Document ingestion**: Scan local folders, classify financial documents, and send them to YourFinanceWORKS.
- **Portfolio monitoring**: Run one-shot or continuous investment optimization cycles.
- **Browser/device login**: Authenticate the CLI without storing plaintext passwords in command history.

## Installation

Run CLI commands from the repository root:

```bash
python -m cli.finance_agent_cli --help
```

The CLI reads configuration from `.finance-agent/config.json` by default. You can override the location:

```bash
python -m cli.finance_agent_cli --config path/to/config.json auth status
```

## Configuration

Profiles are loaded from `.finance-agent/config.json`, environment variables, or both.

Example profile:

```json
{
  "active_profile": "local",
  "profiles": {
    "local": {
      "base_url": "http://localhost:8000",
      "auth_type": "none"
    },
    "demo": {
      "base_url": "https://demo.yourfinanceworks.com",
      "auth_type": "bearer"
    }
  }
}
```

Common environment overrides:

```bash
export FINANCE_AGENT_BASE_URL="http://localhost:8000"
export FINANCE_AGENT_PROFILE="local"
export FINANCE_AGENT_TOKEN_PATH=".finance-agent/token.json"
```

Supported authentication inputs include:

- `FINANCE_AGENT_TOKEN`
- `FINANCE_AGENT_EMAIL`
- `FINANCE_AGENT_PASSWORD`
- `FINANCE_AGENT_AUTH_TYPE`
- `FINANCE_AGENT_YFW_API_KEY`

## Authentication

Check current auth state:

```bash
python -m cli.finance_agent_cli auth status
```

Start browser/device login:

```bash
python -m cli.finance_agent_cli auth browser-login
```

Log in with email and password:

```bash
python -m cli.finance_agent_cli auth login --email user@example.com
```

Remove the cached token:

```bash
python -m cli.finance_agent_cli auth logout
```

Cached bearer tokens are stored at `.finance-agent/token.json` unless overridden by `FINANCE_AGENT_TOKEN_PATH`.

## AI Chat

Ask a one-shot question:

```bash
python -m cli.finance_agent_cli agent chat "how much did I get paid?"
```

By default, the CLI prints only the formatted assistant response:

```text
💰 Payment Information Dashboard

• Total Payments: 1
• Total Amount: $12,075.00
```

Use `--json` when scripts need the full API payload:

```bash
python -m cli.finance_agent_cli --json agent chat "how much did I get paid?"
```

Pass page context to mirror the web assistant:

```bash
python -m cli.finance_agent_cli agent chat \
  --page-context '{"route":"/expenses"}' \
  "how much did I spend in the last 4 expenses?"
```

## Agentic MCP Tool Planning

CLI chat sends messages to `/api/v1/ai/chat`. The backend then asks the configured AI model to create a compact MCP tool plan before executing tools.

Example plan:

```json
{
  "tools": [
    {
      "intent": "expenses",
      "limit": 4
    }
  ],
  "reason": "last four expenses"
}
```

The backend executes the planned MCP intents and passes structured arguments like `limit` to the relevant handler. This avoids hard-coded phrase matching in the CLI and lets the model interpret varied user phrasing.

Examples:

- `"how much did I get paid?"` -> `payments`
- `"how much did I spend in the last 4 expenses?"` -> `expenses` with `limit: 4`
- `"what was my net income?"` -> `payments` and `expenses`
- `"what is my cash runway?"` -> `cashflow`

If multiple tools are needed, the backend executes them and synthesizes a single answer from the MCP outputs.

## Document Ingestion

Scan a folder and classify local documents:

```bash
python -m cli.finance_agent_cli documents scan ./incoming
```

Send classified files to YourFinanceWORKS:

```bash
python -m cli.finance_agent_cli documents scan ./incoming --send
```

Useful routing options:

```bash
python -m cli.finance_agent_cli documents scan ./incoming \
  --send \
  --portfolio-id 7 \
  --export-destination-id 3 \
  --client-id 12 \
  --card-type auto
```

## Portfolio Monitoring

List portfolios:

```bash
python -m cli.finance_agent_cli portfolio list
```

Analyze a portfolio:

```bash
python -m cli.finance_agent_cli portfolio analyze 12
```

Run one monitor cycle:

```bash
python -m cli.finance_agent_cli portfolio monitor --once
```

Run continuous monitoring:

```bash
python -m cli.finance_agent_cli portfolio monitor --interval 300
```

Include sentiment research:

```bash
python -m cli.finance_agent_cli portfolio monitor --once --with-sentiment
```

Monitor artifacts are written to `.finance-agent/monitor-history.jsonl` and `.finance-agent/snapshots/` unless overridden.

## Output Modes

Most commands print human-readable output by default. Add global `--json` for machine-readable output:

```bash
python -m cli.finance_agent_cli --json portfolio list
```

For chat specifically:

- Default: prints `data.response` as formatted text.
- `--json`: prints the full response payload, including model, provider, and source.

## Troubleshooting

**The CLI cannot reach the API**

Check `base_url` in `.finance-agent/config.json` or set:

```bash
export FINANCE_AGENT_BASE_URL="http://localhost:8000"
```

**The chat response says it has no business data**

Confirm the backend is running, the token is valid, and the backend response source is `mcp_tools` when business data is needed.

**A command returns escaped Unicode**

Use normal chat mode without `--json` to print formatted text. JSON output intentionally preserves the full structured payload.

**Authentication unexpectedly fails**

Refresh the cached token:

```bash
python -m cli.finance_agent_cli auth logout
python -m cli.finance_agent_cli auth browser-login
```

## Related Guides

- [AI Services & Business Intelligence](AI_SERVICES.md)
- [Batch Processing & External API Access](BATCH_PROCESSING_API_ACCESS.md)
- [External Transactions API](EXTERNAL_TRANSACTIONS.md)
