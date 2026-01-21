### Bank Statements: End-to-End Summary

This document summarizes the implementation of the bank statements feature (one entry per uploaded PDF, editable transactions), the async processing flow, LLM integration, UI/UX changes, and key fixes.

### Feature Overview

- **Goal**: Each bank statement corresponds to one uploaded PDF. Users can view the list, open details to edit transactions, preview/download the original PDF, and cannot edit while extraction is processing.
- **Processing**: Asynchronous via Kafka. OCR/LLM parsing is handled by a worker; UI polls/shows status.

### Backend: Data Models (per-tenant)

- `api/models/models_per_tenant.py`
  - `BankStatement`:
    - `id`, `tenant_id` (no FK to master tenants), `original_filename`, `stored_filename`, `file_path`, `status` (`processing|processed|failed`), `extracted_count`, timestamps
    - Relationship: `transactions` → `BankStatementTransaction`
  - `BankStatementTransaction`:
    - `id`, `statement_id` (FK → `bank_statements.id`, cascade delete), `date`, `description`, `amount`, `transaction_type` (`debit|credit`), optional `balance`, `category`, timestamps

### Backend: API Endpoints

- `api/routers/statements.py`
  - `POST /bank-statements/upload`: Creates a statement in `processing`, stores the PDF, enqueues Kafka task (async-only; no sync fallback)
  - `GET /bank-statements` and alias without trailing slash: List statements
  - `GET /bank-statements/{id}`: Detail with transactions
  - `PUT /bank-statements/{id}/transactions`: Replace all transactions
  - `GET /bank-statements/{id}/file`: Authenticated file serving (for preview/download)
  - `DELETE /bank-statements/{id}`: Delete statement + file + transactions

### Kafka & Workers

- Topics: `expenses_ocr`, `bank_statements_ocr`, `invoices_ocr`, `invoices_ocr_result`
- `api/services/ocr_service.py`
  - Caches Kafka producers (`_PRODUCER_CACHE`) to avoid termination warnings
  - `flush_all_producers()` called on FastAPI shutdown (`api/main.py`)
  - `publish_bank_statement_task()`, `publish_invoice_task()`, `publish_invoice_result()` with hardened error handling
- `api/workers/ocr_consumer.py`
  - Subscribes to all topics
  - Bank statements: receives message, loads AI config (or env fallback), calls extraction, replaces transactions, updates status (`processed`/`failed`), logs details
  - Invoices: async LLM extraction with result publishing
  - Expense: left TODO for future parity

### PDF Extraction & LLM

- `api/services/statement_service.py`
  - Loader: `SimplePDFLoader` tries `pdfplumber`, `pymupdf`, `pypdf`, then falls back to `pypdf`
  - Preprocessing: remove page headers/noise and collapse whitespace
  - Prompt: clear rules and JSON-only output with examples (aligned for local models)
  - Two paths:
    - Worker LiteLLM path (`process_bank_pdf_with_llm`): chunk text (3000/150), call LLM per chunk, parse JSON or fallback regex per chunk, aggregate/dedupe/sort
    - Direct Ollama chat fallback path in `extract_from_pdf` if available
  - Regex fallback: generic patterns + documented BMO-specific fallback; doc at `docs/bank_statement_bmo_regex.md`
  - LLM config:
    - Uses DB `AIConfig` when available, else environment fallback
    - Provider/model handling for LiteLLM (e.g., `ollama/<model>`) and sanitizing `api_base`
    - Environment variables considered in order: `OLLAMA_API_BASE` → `LLM_API_BASE` → `OLLAMA_API_URL`; models from `LLM_MODEL_BANK_STATEMENTS` or `OLLAMA_MODEL`

### Frontend

- `ui/src/lib/api.ts`
  - Types: `BankStatementSummary`, `BankStatementDetail`
  - Methods: `list`, `get`, `replaceTransactions`, `delete`, `uploadAndExtract` (returns created statements), `fetchFileBlob` (auth fetch for preview/download)
  - Base URL strictly from `VITE_API_URL` (no implicit ports)
- `ui/src/pages/Statements.tsx`
  - List view with actions: Open, Preview (modal), Download, Delete
  - Detail view: transactions table editor; disabled when status is `processing`
  - Shared `handlePreview`/`handleDownload` using `fetchFileBlob` to include auth headers, `blob:` URL for modal and download
  - Fixed in-app preview blank space by ensuring content-type and using `<embed type="application/pdf">` with fallback link

### Invoices (related refactor)

- `api/routers/pdf_processor.py`
  - Removed bank function (moved to service)
  - For invoices: fallback to env vars for AI config when DB has none
- `ui/src/components/invoices/InvoiceCreationChoice.tsx`
  - Always attempt PDF processing (even if no DB AI config), relying on API env fallback
  - Normalize API response (whether nested under `invoice_data` or not) to keep UI stable and avoid `undefined` fields
  - Populate and format items and totals

### Environment Variables

- API/UI: `VITE_API_URL`
- Kafka: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_OCR_TOPIC`, `KAFKA_BANK_TOPIC`, `KAFKA_INVOICE_TOPIC`, `KAFKA_INVOICE_RESULT_TOPIC`, `BANK_KAFKA_ENABLED`
- LLM:
  - `LLM_MODEL`, `LLM_MODEL_INVOICES`, `LLM_MODEL_BANK_STATEMENTS`
  - `OLLAMA_MODEL`
  - `OLLAMA_API_BASE` (preferred), `LLM_API_BASE`, `OLLAMA_API_URL`
  - `LLM_API_KEY`
- Others: `SECRET_KEY`

### Deployment Notes

- When using Ollama from containers, do not use `localhost:11434` inside containers. Either:
  - Run Ollama as a service (e.g., `ollama:11434`) and set `OLLAMA_API_BASE=http://ollama:11434`, or
  - Use host gateway mapping and set `OLLAMA_API_BASE=http://host.docker.internal:11434`
- Ensure the selected model exists on the Ollama server (e.g., `ollama pull gpt-oss:latest`) or change the model consistently across env/config

### Key Fixes

- Removed invalid relationship to master `Tenant` from `BankStatement`
- Added non-trailing-slash alias to avoid FastAPI 307 redirects
- Auth preview/download via `fetchFileBlob` (fix 401 in modal)
- Kafka producer reuse + explicit flush on shutdown to eliminate pending message warnings
- Worker subscribed to `bank_statements_ocr`; forced async-only path
- AI config fallback to env vars for both bank statements and invoices
- Normalized invoice processing responses to avoid UI crashes
- Added idempotent DB init for missing columns in fresh DBs (`api/db_init.py`)

### Troubleshooting Highlights

- Connection refused to Ollama inside worker: set `OLLAMA_API_BASE` to container-reachable host, not `localhost`
- 0 transactions: improved preprocessing, chunking, prompt, and regex fallback; added BMO-specific extraction logic
- Blank preview: ensure correct content type and use `<embed>` with fallback

### Files of Interest

- `api/models/models_per_tenant.py`
- `api/routers/statements.py`
- `api/services/statement_service.py`
- `api/services/ocr_service.py`
- `api/workers/ocr_consumer.py`
- `api/routers/pdf_processor.py`
- `api/db_init.py`
- `ui/src/lib/api.ts`
- `ui/src/pages/Statements.tsx`
- `ui/src/components/invoices/InvoiceCreationChoice.tsx`
- `docs/bank_statement_bmo_regex.md`


