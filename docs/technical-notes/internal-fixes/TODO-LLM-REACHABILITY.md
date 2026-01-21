# TODO: Make LLM reachability check provider-agnostic

Context
- Current reachability helper `is_bank_llm_reachable` is implemented for Ollama-only (via `GET /api/tags`).
- Location: `api/services/statement_service.py`.
- Goal: Support multiple LLM vendors (OpenAI, Anthropic, Azure OpenAI, Google Vertex AI, AWS Bedrock, Ollama) via a unified interface.

Refactor Plan
- Create a provider-agnostic interface, e.g. `LLMProvider` with:
  - `is_reachable(ai_config: dict) -> bool`
  - Optional: `list_models(ai_config: dict) -> List[str]`
- Implement adapters:
  - OllamaProvider (current logic using `/api/tags`)
  - OpenAIProvider (`GET /v1/models` or minimal chat probe)
  - AnthropicProvider (models listing or minimal message probe)
  - AzureOpenAIProvider (deployments listing endpoint)
  - GoogleVertexProvider (Model Garden or minimal prediction)
  - AWSBedrockProvider (list foundation models or minimal invoke)
- Provider factory:
  - Choose by `ai_config.provider_name` (stored per-tenant), fallback to env.
  - Normalize base URLs and API keys from `ai_config`.
- Timeouts & caching:
  - 2–3s timeout for reachability; avoid long operations
  - Cache reachability per tenant/provider ~60s
- Error handling:
  - Differentiate unreachable (network) vs unauthorized (401/403) vs reachable
  - Never log secrets; redact keys
- Telemetry:
  - Log provider, base URL (redacted), model name, and counters for failures

Acceptance Criteria
- `is_bank_llm_reachable` delegates to provider adapters and returns True/False.
- Worker (`api/workers/ocr_consumer.py`) uses the provider-agnostic helper.
- Unit tests per provider adapter (mock HTTP): reachable, unauthorized, network error.
- Update `docs/BANK_STATEMENT_LLM_VENDOR_SUPPORT.md` with reachability design.

Related Files
- `api/services/statement_service.py`
- `api/workers/ocr_consumer.py`
- `api/models/models_per_tenant.py`
- `docs/BANK_STATEMENT_LLM_VENDOR_SUPPORT.md`
