# Finance Agent CLI

This folder contains a lightweight scaffold for a finance-operations CLI that follows a Codex/Claude-style interaction model while delegating all agent execution to the backend.

## Design Intent

- Prompt-first UX for operators and developers
- Local mode to start the full repo stack with Docker Compose
- Remote mode to connect to an existing deployment
- API-key or login-based authentication
- No local agent runtime duplication

## Current Status

This is a scaffold, not a fully integrated product surface yet.

Implemented now:

- CLI entrypoint
- Interactive shell mode
- One-shot prompt mode
- Command tree placeholders for `up`, `down`, `connect`, `auth`, `run`, `runs`, `approvals`, `doctor`
- Local config file support
- Password-based bearer login
- Browser-based loopback login scaffold

Not implemented yet:

- Docker Compose orchestration
- Approval actions against the backend
- Streaming run traces
- Deployment support for the CLI callback flow on the target environment

## Usage

From the repo root:

```bash
python -m cli.finance_agent_cli --help
python -m cli.finance_agent_cli
python -m cli.finance_agent_cli "review overdue invoices for tenant acme"
python -m cli.finance_agent_cli connect --base-url http://localhost:8000 --profile local
python -m cli.finance_agent_cli auth browser-login --base-url https://demo.example.com
```

## Planned Command Shape

```text
finance-agent
  up
  down
  connect
  auth login
  auth browser-login
  auth api-key set
  auth whoami
  run
  runs list|get|tail|replay
  approvals list|approve|reject
  doctor
```

## Config

The CLI stores config at:

```text
~/.finance-agent/config.json
```

Example structure:

```json
{
  "active_profile": "local",
  "profiles": {
    "local": {
      "mode": "local",
      "base_url": "http://localhost:8000",
      "auth_type": "api_key"
    }
  }
}
```

## Browser Login Flow

The CLI now supports a browser-based login pattern using a local loopback callback:

```bash
python -m cli.finance_agent_cli auth browser-login --base-url https://demo.example.com
```

The CLI will:

1. Start a temporary local callback server on `127.0.0.1`
2. Open the browser to a login URL
3. Wait for the browser to redirect back with `access_token`, `token`, or `api_key`
4. Save the returned bearer token into the active profile

Backend expectation:

- The server must expose `GET/POST /api/v1/auth/cli/login`
- That endpoint must redirect back to the CLI callback URL with a token in the query string

Example redirect:

```text
http://127.0.0.1:47123/callback?access_token=eyJ...
```

This repo now includes that backend route. The browser flow will work once the target deployment is running code that includes `/api/v1/auth/cli/login`.
