# Plugin Isolation — TODO

## Background

`enter_trusted_service()` in `api/core/utils/_plugin_isolation.py` is the pattern for
platform services (core or commercial) that are called from plugin code and access
tables beyond what the plugin's `permitted_core_tables` manifest declares.

Two mechanisms work together:

| Situation | Mechanism |
|---|---|
| Plugin directly queries a known, bounded set of tables | Declare in `permitted_core_tables` (plugin.json) |
| Plugin calls a service whose internal table access is predictable and bounded | Declare those tables in `permitted_core_tables` |
| Plugin calls a service that accesses many/unpredictable tables (tracking, audit, AI usage) | Service uses `enter_trusted_service()` internally |

**Rule:** plugin code never imports `_plugin_isolation`. If a bypass is needed, the answer
is always "add to manifest" or "the service should own the bypass".

---

## TODO: Add `enter_trusted_service()` to services with tracking/audit side effects

The following service types access tables that plugins cannot predict or enumerate in
their manifests. If any of these are exposed to plugin callers in the future, they need
an internal `enter_trusted_service()` shim (same pattern as `process_bank_pdf_with_llm`).

### Audit & Event Logging
- [ ] `core.utils.audit.log_audit_event` — inserts into audit log tables
- [ ] `core.services.FinancialEventProcessor` — financial event tables
- [ ] `core.services.ReviewEventService` — review workflow event tables

### AI / OCR Usage Tracking
- [ ] `commercial.ai.services.ocr_service.track_ai_usage` — already covered indirectly
      via `process_bank_pdf_with_llm`'s shim, but if called standalone from a plugin it
      would need its own shim
- [ ] `commercial.ai.services.ocr_service.track_ocr_usage` — same as above

### Notifications & Webhooks
- [ ] Any service that dispatches email notifications, in-app notifications, or webhook
      deliveries as side effects — these write to notification/webhook tables not in any
      plugin manifest

### Expense Processing (if exposed to plugins)
- [ ] `core.services.InventoryIntegrationService` — touches inventory + stock movement tables
- [ ] `core.services.AttributionService` — financial attribution tables
- [ ] `core.services.CurrencyService` — if it writes conversion logs

---

## TODO: Audit new plugins for `_plugin_isolation` imports

Add a CI check (or code review checklist item) that flags any import of
`core.utils._plugin_isolation` from within a plugin directory:

```bash
# Should return no results for plugin directories
grep -r "from core.utils._plugin_isolation" api/plugins/ plugins/
```

---

## Pattern Reference

When adding `enter_trusted_service()` to a new service, use the shim pattern to avoid
re-indenting large method bodies:

```python
# Public entry point — owns the trusted context
def my_service_function(arg1, arg2, db=None):
    """Public docstring..."""
    from core.utils._plugin_isolation import enter_trusted_service
    with enter_trusted_service():
        return _my_service_function_impl(arg1, arg2, db)


def _my_service_function_impl(arg1, arg2, db=None):
    """Implementation — call my_service_function() instead."""
    # existing implementation unchanged
    ...
```

For class methods where re-indenting is acceptable:

```python
async def create_something(self, ...):
    with enter_trusted_service():
        try:
            ...
        except Exception as e:
            ...
            raise
```

---

## Services already handled

- [x] `core.services.statement_service.process_bank_pdf_with_llm` — shim added
- [x] `commercial.batch_processing` (create_batch_job, enqueue_files_to_kafka, get_job_status)
      — covered via `permitted_core_tables` in manifest (no shim needed)
