# CLAUDE.md

Do not make any changes until you have 95% confidence in what you need to build. Ask me follow-up questions until you reach that confidence level.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YourFinanceWORKS is an AI-powered financial management SaaS platform. It uses a **FastAPI backend** (`api/`) and a **React/TypeScript frontend** (`ui/`), containerized with Docker Compose. The platform features multi-tenant architecture (database-per-tenant isolation), an extensible plugin system, and optional commercial modules.

## Commands

### Running the Full Stack
```bash
docker-compose up                        # Start all services (PostgreSQL, Redis, Kafka, OpenSearch, API, UI)
```

### Backend (FastAPI)
```bash
# Tests (via Docker)
docker compose exec api pytest -v                               # All tests
docker compose exec api pytest -v --cov=. --cov-report=html    # With coverage
docker compose exec api pytest tests/test_invoices.py          # Single test file
docker compose exec api pytest -k "test_create_invoice"        # Single test by name
```

### Frontend (React/TypeScript/Vite)
```bash
# Tests (via Docker)
docker compose exec ui npx vitest run                                          # Single run
docker compose exec ui npx vitest run --coverage                               # With coverage
docker compose exec ui npx vitest run src/components/InvoiceForm.test.tsx      # Single test file
```

### Run All Tests
```bash
./run-tests.sh
```

## Architecture

### Multi-Tenant Model
Each tenant gets an isolated PostgreSQL database. The master DB (`invoice_master`) stores tenant registry. `db_init.py` handles DB creation/migration per tenant. All API requests resolve the tenant from the JWT or subdomain, then connect to that tenant's DB.

### Backend Structure (`api/`)
- **`core/`** — Open-source (AGPL) modules:
  - `routers/` — FastAPI route handlers (35+)
  - `models/` — SQLAlchemy ORM models
  - `schemas/` — Pydantic request/response models
  - `services/` — Business logic layer (88 modules)
  - `utils/` — Shared utilities
  - `middleware/` — Request middleware (auth, tenant resolution)
- **`commercial/`** — Licensed commercial features (AI, SSO, advanced search, fraud detection, plugins, workflows, cloud storage, etc.). Each submodule is conditionally imported — missing modules degrade gracefully.
- **`plugins/`** — Auto-discovered extensions (currency_rates, investments, time_tracking). Plugins register their own routes and models at startup.
- **`main.py`** — App entrypoint; assembles routers and middleware
- **`config.py`** — All environment-based configuration
- **`auth.py`** — JWT + FastAPI-Users authentication

### Frontend Structure (`ui/src/`)
- **`pages/`** — 52 page-level components (one per feature area)
- **`components/`** — 33 shared UI components (ShadCN/Radix-based)
- **`hooks/`** — 21 custom hooks (data fetching, auth, forms)
- **`contexts/`** — 8 providers (AuthContext, ThemeContext, LocaleContext, PluginContext, etc.)
- **`services/`** — Typed API client modules (one per domain)
- **`plugins/`** — Frontend plugin integration (mirrors `api/plugins/`)
- **`i18n/`** — i18next translations

### Key Patterns
- **API calls**: Frontend uses TanStack Query v5 (`useQuery`/`useMutation`) with typed service functions
- **Forms**: React Hook Form + Zod schemas
- **Routing**: React Router v6 with protected routes via AuthContext
- **Styling**: Tailwind CSS with ShadCN UI components in `components/ui/`
- **AI features**: LiteLLM as the unified LLM interface; FastMCP for the AI assistant (Model Context Protocol)

### Commercial Module Imports
Commercial features use try/except import guards:
```python
try:
    from commercial.ai import router as ai_router
    app.include_router(ai_router)
except ImportError:
    pass
```

### Plugin System
Plugins live in `api/plugins/<name>/` and `ui/src/plugins/<name>/`. The backend auto-discovers them at startup, registers their SQLAlchemy models, and mounts their routers. The frontend `PluginContext` dynamically loads plugin UI components.

## Environment Configuration

Copy `api/.env.example.full` to `api/.env`. Key variables:
- `DATABASE_URL` — PostgreSQL master DB connection
- `AI_PROVIDER` / `AI_MODEL` / `LLM_API_KEY` — LLM configuration (supports ollama, openai, anthropic)
- `REDIS_URL`, `KAFKA_BOOTSTRAP_SERVERS`, `OPENSEARCH_HOST` — Infrastructure
- `SECRET_KEY` — JWT signing key
- `LICENSE_KEY` / `INSTALLATION_ID` — Commercial features activation
- Email: choose AWS SES, Azure Communication Services, or Mailgun env vars
- Cloud storage: choose Azure, GCS, or S3 env vars
