"""
Internal plugin isolation mechanism — NOT part of the public plugin API.

This module owns the bypass context var and the ``enter_trusted_service``
context manager.  Only core service code should import from here.  Plugin code
has no legitimate reason to import this module; doing so to bypass isolation is
a policy violation.

Public plugin API lives in ``core.utils.plugin_context``.
"""
import contextvars
import logging
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

# True while a trusted core service is executing on behalf of a plugin.
# The DB isolation interceptor skips checks when this is set.
_bypass_isolation: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_bypass_isolation", default=False
)


def is_isolation_bypassed() -> bool:
    """Return True when the isolation interceptor should be skipped."""
    return _bypass_isolation.get()


@contextmanager
def enter_trusted_service() -> Generator[None, None, None]:
    """
    Suspend DB isolation checks for the duration of a trusted core service call.

    Call this at the **top of core service methods** that may be invoked from
    within a plugin request context (e.g. BatchProcessingService.create_batch_job,
    process_bank_pdf_with_llm).  The service itself is trusted; the suspension is
    scoped to the ``with`` block only.

    Rules:
    - Use inside core service methods, NOT in plugin code.
    - Plugin code should declare table needs in ``permitted_core_tables`` (manifest).
    - This is a no-op when no plugin context is active (normal core requests).

    Example (inside a core service method)::

        from core.utils._plugin_isolation import enter_trusted_service

        async def create_batch_job(self, ...):
            with enter_trusted_service():
                ...  # all DB access here is trusted
    """
    token = _bypass_isolation.set(True)
    try:
        yield
    finally:
        _bypass_isolation.reset(token)
