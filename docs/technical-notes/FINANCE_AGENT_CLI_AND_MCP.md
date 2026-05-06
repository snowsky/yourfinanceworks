# Finance Agent CLI and MCP Usage

## CLI Install

The finance agent CLI lives under `cli/finance_agent_cli`.

To install an editable local console script:

```bash
cd cli
pip install -e .
```

This exposes:

```bash
finance-agent --help
```

If you do not want to install it, you can still run:

```bash
python -m cli.finance_agent_cli --help
```

## CLI Configuration

Default config file:

```text
.finance-agent/config.json
```

Supported runtime inputs:

- profile selection via `--profile`
- env overrides such as `FINANCE_AGENT_BASE_URL`, `FINANCE_AGENT_EMAIL`, `FINANCE_AGENT_PASSWORD`, `FINANCE_AGENT_TOKEN`
- optional legacy YFW batch API key via `FINANCE_AGENT_YFW_API_KEY`, `YFW_API_KEY`, or `INVOICE_API_KEY`
- optional classifier/chat LLM settings via `FINANCE_AGENT_LLM_PROVIDER`, `FINANCE_AGENT_LLM_MODEL`, `FINANCE_AGENT_LLM_API_KEY`, `FINANCE_AGENT_LLM_BASE_URL`
- monitor settings via `FINANCE_AGENT_INTERVAL`, `FINANCE_AGENT_DRIFT_THRESHOLD`, `FINANCE_AGENT_REFRESH_PRICES`

Base URLs are normalized to the backend API path automatically:

- `https://host/` -> `https://host/api/v1`
- `https://host/api` -> `https://host/api/v1`
- `https://host/api/v1` -> unchanged

## CLI Commands

Examples:

```bash
finance-agent auth login --email user@example.com
finance-agent auth browser-login
finance-agent auth status
finance-agent portfolio list
finance-agent portfolio analyze 12
finance-agent portfolio rebalance 12
finance-agent portfolio transactions 12
finance-agent portfolio cross-summary
finance-agent prices status
finance-agent prices refresh
```

Scan a local folder and classify PDF/image/CSV files as `expense`, `invoice`, `statement`, or `portfolio`:

```bash
finance-agent documents scan ./incoming
```

Send classified files to YourFinanceWORKS:

```bash
finance-agent documents scan ./incoming --send --portfolio-id 12
```

Expenses, invoices, and statements are sent to the authenticated batch-processing API using the same CLI login/token as other first-party operations. Portfolio files are sent to the investments holdings-file upload endpoint and require a portfolio ID plus normal CLI auth.

Talk to the CLI agent in one-shot or interactive mode:

```bash
finance-agent agent chat "list expenses"
finance-agent agent chat
```

The chat bridge calls the same `/api/v1/ai/chat` endpoint as the web AI Assistant. Intent classification and MCP dispatch happen in the backend through the existing `MCP.tools.InvoiceTools` integration, so CLI behavior stays aligned with the in-app assistant. You can pass the same optional context payload used by the web UI:

```bash
finance-agent agent chat --page-context '{"route":"/statements","entity":{"type":"bank_statement","id":12}}' "reprocess this statement"
```

## CLI Auth

Use explicit login when you want to cache a bearer token before running the agent:

```bash
finance-agent auth login --email user@example.com
```

The command prompts for a password if `--password` is omitted. The token is cached at `.finance-agent/token.json` by default. You can inspect or clear it with:

```bash
finance-agent auth status
finance-agent auth logout
```

The older env/profile flow still works: commands authenticate on demand when `FINANCE_AGENT_AUTH_TYPE=password`, `FINANCE_AGENT_EMAIL`, and `FINANCE_AGENT_PASSWORD` are configured.

For SSO or passwordless browser approval, use the device/browser flow:

```bash
finance-agent auth browser-login
```

This opens a browser verification URL, asks the browser session to approve the CLI device code, then caches the returned bearer token. On a headless machine:

```bash
finance-agent auth device-login --no-open
```

Single monitor cycle:

```bash
finance-agent portfolio monitor --once
```

Continuous monitor:

```bash
finance-agent portfolio monitor --interval 300 --drift-threshold 1.5 --refresh-prices
```

Limit monitoring to specific portfolios:

```bash
finance-agent portfolio monitor --portfolio-id 12 --portfolio-id 14 --once
```

## Monitor Artifacts

The monitor now persists three artifact types by default:

- state: `.finance-agent/state.json`
- append-only history log: `.finance-agent/monitor-history.jsonl`
- per-cycle snapshots: `.finance-agent/snapshots/monitor-<timestamp>.json`

You can override monitor artifact paths:

```bash
finance-agent portfolio monitor --once \
  --history-path tmp/history.jsonl \
  --snapshot-dir tmp/snapshots
```

Artifact intent:

- `state.json` deduplicates repeated recommendations between runs
- `monitor-history.jsonl` gives a compact operational timeline
- snapshot files preserve the full recommendation payload for audit/debugging

## MCP Investment Tools

The MCP investment surface now includes:

- `list_portfolios`
- `get_portfolio_summary`
- `get_portfolio_rebalance`
- `get_portfolio_diversification`
- `get_portfolio_transactions`
- `get_cross_portfolio_summary`
- `get_cross_portfolio_overlap`
- `get_cross_portfolio_exposure`
- `get_investment_price_status`
- `refresh_investment_prices`
- `get_portfolio_optimization_recommendations`

## One-Call Optimization Tool

Use this MCP tool when an external agent wants a current recommendation set in one call:

```text
get_portfolio_optimization_recommendations(drift_threshold=1.0)
```

Returned payload includes:

- drift threshold used
- active portfolio count
- recommendation count
- price status
- overlap summary
- exposure summary
- ranked recommendations with:
  - portfolio id/name/type
  - severity
  - summary
  - reasons
  - suggested actions
  - fingerprint

This tool is read-only. It does not execute trades or modify holdings.
