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
- monitor settings via `FINANCE_AGENT_INTERVAL`, `FINANCE_AGENT_DRIFT_THRESHOLD`, `FINANCE_AGENT_REFRESH_PRICES`

Base URLs are normalized to the backend API path automatically:

- `https://host/` -> `https://host/api/v1`
- `https://host/api` -> `https://host/api/v1`
- `https://host/api/v1` -> unchanged

## CLI Commands

Examples:

```bash
finance-agent portfolio list
finance-agent portfolio analyze 12
finance-agent portfolio rebalance 12
finance-agent portfolio transactions 12
finance-agent portfolio cross-summary
finance-agent prices status
finance-agent prices refresh
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
