import contextvars
import logging
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# Context variables to track the current plugin ID and lockdown status
_current_plugin_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_current_plugin_id", default=None
)
_is_locked: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_is_locked", default=False
)
# When True, the DB isolation interceptor is bypassed for the duration.
# Used by plugin internal clients when delegating to trusted core services.
_bypass_isolation: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_bypass_isolation", default=False
)


def set_current_plugin_id(
    plugin_id: Optional[str], lock: bool = False
) -> Optional[contextvars.Token]:
    """
    Sets the current plugin ID in the context.
    If 'lock' is True, the context enters Lockdown Mode for this request/task.
    """
    if _is_locked.get() and plugin_id != _current_plugin_id.get():
        logger.warning(
            "SECURITY ALERT: Attempted to change plugin_id from '%s' to '%s' while in Lockdown Mode.",
            _current_plugin_id.get(),
            plugin_id,
        )
        return None  # Silently ignore the change attempt

    if lock:
        _is_locked.set(True)

    return _current_plugin_id.set(plugin_id)


def get_current_plugin_id() -> Optional[str]:
    """Retrieves the current plugin ID from the context."""
    return _current_plugin_id.get()


def is_lockdown_mode() -> bool:
    """Returns True if the current context is in Lockdown Mode."""
    return _is_locked.get()


def is_isolation_bypassed() -> bool:
    """Returns True when a trusted core service has temporarily lifted isolation."""
    return _bypass_isolation.get()


@contextmanager
def bypass_plugin_isolation() -> Generator[None, None, None]:
    """
    Context manager that temporarily suspends DB isolation checks.

    Use this ONLY inside plugin internal clients when calling trusted core
    services (e.g. BatchProcessingService, user_sync) that must access core
    tables on behalf of the plugin but are not plugin-owned code.

    Example::

        from core.utils.plugin_context import bypass_plugin_isolation

        async def upload_batch(self, ...):
            with bypass_plugin_isolation():
                result = await core_service.do_work(...)
    """
    token = _bypass_isolation.set(True)
    try:
        yield
    finally:
        _bypass_isolation.reset(token)


def reset_current_plugin_id(token: contextvars.Token) -> None:
    """Resets the current plugin ID context using the provided token."""
    if token:
        _current_plugin_id.reset(token)
