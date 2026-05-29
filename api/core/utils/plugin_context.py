import contextvars
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Context variables to track the current plugin ID and lockdown status
_current_plugin_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("_current_plugin_id", default=None)
_is_locked: contextvars.ContextVar[bool] = contextvars.ContextVar("_is_locked", default=False)


@dataclass(frozen=True)
class PluginContextTokens:
    """Reset tokens for the plugin-context ContextVars.

    ``set_current_plugin_id(lock=True)`` mutates two ContextVars; resetting
    only one of them — as the original implementation did by returning just
    the plugin_id token — leaves ``_is_locked`` stuck at ``True`` after the
    request finally block runs. Any code that reuses the same asyncio Task
    (BackgroundTasks, connection re-use, run_in_executor inheritance) then
    sees a stale ``_is_locked=True`` with an already-reset plugin_id, which
    triggers the spurious SECURITY ALERT log on the next legitimate
    ``set_current_plugin_id`` call. Bundling both tokens lets the caller
    reset the pair atomically.
    """

    plugin_id_token: contextvars.Token
    lock_token: Optional[contextvars.Token] = None


def set_current_plugin_id(plugin_id: Optional[str], lock: bool = False) -> Optional[PluginContextTokens]:
    """
    Sets the current plugin ID in the context.
    If 'lock' is True, the context enters Lockdown Mode for this request/task.
    """
    if _is_locked.get() and plugin_id != _current_plugin_id.get():
        logger.warning(
            "SECURITY ALERT: Attempted to change plugin_id from '%s' to '%s' while in Lockdown Mode.",
            _current_plugin_id.get(), plugin_id
        )
        return None  # Silently ignore the change attempt

    lock_token: Optional[contextvars.Token] = None
    if lock:
        lock_token = _is_locked.set(True)

    plugin_id_token = _current_plugin_id.set(plugin_id)
    return PluginContextTokens(plugin_id_token=plugin_id_token, lock_token=lock_token)


def get_current_plugin_id() -> Optional[str]:
    """Retrieves the current plugin ID from the context."""
    return _current_plugin_id.get()


def is_lockdown_mode() -> bool:
    """Returns True if the current context is in Lockdown Mode."""
    return _is_locked.get()


def reset_current_plugin_id(tokens: Optional[PluginContextTokens]) -> None:
    """Reset the plugin-context ContextVars using the tokens returned by
    :func:`set_current_plugin_id`. Idempotent against ``None`` so a caller
    that received a lockdown-rejection from ``set_current_plugin_id`` (and
    thus got ``None`` back) can still call this unconditionally inside a
    ``finally``.
    """
    if not tokens:
        return
    _current_plugin_id.reset(tokens.plugin_id_token)
    if tokens.lock_token is not None:
        _is_locked.reset(tokens.lock_token)
