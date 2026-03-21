# AI-Assisted Prompt Improvement via Chat

Introduced in commit `be71572` on branch `dynamic-prmopt-optimization`.

## Overview

Users can describe an extraction problem in plain language to the AI Assistant, and the system automatically identifies the responsible prompt template, iteratively improves it, tests it against the real document, and saves the winning version — with no manual prompt editing required.

## User Flow

1. Open the AI Assistant (chat bubble, bottom-right)
2. Describe the extraction problem, e.g.:
   - *"invoice number is not being recognized"*
   - *"holdings not being extracted correctly"*
   - *"bank statement amount is misread"*
3. The assistant detects the intent and immediately shows a progress card
4. Watch live iteration progress as the AI retries (up to 5 times)
5. On success: the winning prompt is saved as a new version — visible in **Settings → Prompt Management**
6. On exhaustion: an amber card links directly to `/settings?tab=prompts` for manual editing

Alternatively, click the **Improve Prompt** quick-action button in the chat input area.

## Trigger Keywords

The assistant detects prompt-improvement intent when the message contains any of:

> `not being recognized`, `not extracted`, `parsing problem`, `improve prompt`,
> `fix prompt`, `extraction issue`, `not reading`, `misread`, `incorrect field`,
> `missing field`, `not parsing`, `recognized wrong`, `wrong number`,
> `holdings not`, `portfolio not`, `wrong holding`, `incorrect holding`

## Architecture

### Flow

```
User message
  → Frontend detects intent → POST /prompts/improve
  → Backend: identify prompt (~1s LLM call) → create PromptImprovementJob
  → BackgroundTask: run_improvement_loop (up to 5 iterations)
      For each iteration:
        generate improved prompt → test on document → evaluate → save if passing
      Commits job record after each iteration (enables live polling)
  → Frontend polls GET /prompts/improve/{job_id} every 3s
  → Renders PromptImprovementProgress card inline in chat
```

### Async Strategy

Uses FastAPI `BackgroundTasks` (consistent with existing patterns). The background loop creates its own DB session — same pattern used in `invoices/crud.py`.

### Saving Strategy

Only the passing candidate is saved as a new prompt version. Failed iterations are discarded, avoiding pollution of the 5-version history limit.

---

## Backend

### New Model: `PromptImprovementJob`

File: `api/commercial/prompt_management/models/prompt_improvement_job.py`

| Field | Type | Description |
|---|---|---|
| `id` | int | Primary key |
| `user_id`, `tenant_id` | int | Owner context |
| `user_message` | Text | Original complaint |
| `document_id`, `document_type` | optional | Document the prompt failed on |
| `prompt_name`, `prompt_category` | str | Resolved during identification |
| `status` | str | `pending → running → succeeded \| exhausted \| failed` |
| `current_iteration`, `max_iterations` | int | Progress (default max: 5) |
| `iteration_log` | JSON | `[{iteration, prompt_preview, evaluation, reason}]` |
| `final_prompt_content` | Text | Winning prompt (set on success) |
| `final_prompt_version` | int | Version number saved by PromptService |
| `result_summary` | Text | Human-readable result for chat |
| `error_message` | Text | Set on failure |
| `created_at`, `updated_at`, `completed_at` | DateTime | Timestamps |

Table is auto-created for all tenants via `TenantBase.metadata.create_all()` in `tenant_database_manager.py`.

### New Service: `PromptImprovementService`

File: `api/commercial/prompt_management/services/prompt_improvement_service.py`

| Method | Description |
|---|---|
| `identify_affected_prompt(message, document_type?)` | Single LLM call; maps complaint to one of 16 known prompt names |
| `generate_improved_prompt(name, current_content, user_message, prior_failure?)` | LLM generates candidate; passes failure context on iteration > 1 |
| `test_prompt_on_document(prompt_content, doc_type, doc_id, db)` | Dispatches to existing extractors with `custom_prompt` injected; does NOT write back |
| `evaluate_result(extraction_result, user_message, prompt_name)` | LLM evaluates `{passed: bool, reason: str}` |
| `_resolve_document(doc_type, doc_id?, db)` | Resolves document → file path; falls back to most recent if no doc_id |
| `run_improvement_loop(job_id, tenant_id)` | Standalone async function; creates its own DB session |

### New Endpoints

All require `prompt_management` feature flag.

| Method | Path | Description |
|---|---|---|
| `POST` | `/prompts/improve` | Start a job; synchronously identifies prompt, schedules background loop |
| `GET` | `/prompts/improve/{job_id}` | Poll current job state |
| `GET` | `/prompts/improve?limit=10` | List recent jobs for current user |

### Modified Files

| File | Change |
|---|---|
| `api/commercial/prompt_management/router.py` | 3 new endpoints + Pydantic schemas |
| `api/core/services/tenant_database_manager.py` | Register `PromptImprovementJob.__table__` in schema init |
| `api/plugins/investments/services/llm_extraction_service.py` | `custom_prompt` param on `_extract_with_llm`, `extract_portfolio_data_from_pdf`, `extract_portfolio_data_from_csv` |

---

## Frontend

### New Component: `PromptImprovementProgress`

Inline card rendered in the chat message stream.

| Status | Appearance |
|---|---|
| `pending / running` | Blue header + spinner, "Improving prompt for [name]...", "Iteration N / 5" |
| `succeeded` | Green header + checkmark, result summary, iteration log |
| `exhausted` | Amber header, "Tried 5 iterations", iteration log, link to Prompt Management |
| `failed` | Red header + error message |

### Modified Files

| File | Change |
|---|---|
| `ui/src/components/AIAssistant.tsx` | `PromptImprovementProgress` component, `isPromptImprovementIntent` helper, `handlePromptImprovementChat` polling handler, intent branch in `handleSendMessage`, "Improve Prompt" quick action button |
| `ui/src/lib/api/settings.ts` | `PromptImprovementJob` type, `StartImprovementRequest` type, `promptImprovementApi` export |

---

## Document Type Support

| Document type | Prompt identified | Test via |
|---|---|---|
| `invoice` | `invoice_data_extraction`, `pdf_invoice_extraction`, … | `InvoiceAIService.extract_invoice_data(file_path, custom_prompt=...)` |
| `expense` | `expense_receipt_vision_extraction`, … | `_run_ocr(file_path, custom_prompt=...)` |
| `bank_statement` | `bank_transaction_extraction`, … | `_run_ocr(file_path, custom_prompt=...)` |
| `portfolio` | `portfolio_data_extraction` | `LLMExtractionService.extract_portfolio_data_from_{pdf,csv}(file_path, custom_prompt=...)` |

---

## Feature Gate

The feature is gated behind `prompt_management`. Tenants without this feature receive a `403` from all `/prompts/improve` endpoints.

## Verification Checklist

- [ ] Open AI Assistant on an invoice page → type "invoice number is not being recognized" → progress card appears
- [ ] Card updates every 3s with iteration count
- [ ] On success: version incremented in Settings → Prompt Management
- [ ] On exhaustion: amber card with iteration log + link to Prompt Management
- [ ] Open AI Assistant on a portfolio page → type "holdings not being extracted correctly" → `portfolio_data_extraction` prompt is targeted
- [ ] Feature gate: disable `prompt_management` → endpoint returns 403
- [ ] No document context: job fails gracefully with clear error message
- [ ] "Improve Prompt" quick action button visible in chat
