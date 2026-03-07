import contextvars
from typing import Optional

# Context variable to track the current plugin ID during the request lifecycle
_current_plugin_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("_current_plugin_id", default=None)

def set_current_plugin_id(plugin_id: Optional[str]) -> contextvars.Token:
    """Sets the current plugin ID in the context."""
    return _current_plugin_id.set(plugin_id)

def get_current_plugin_id() -> Optional[str]:
    """Retrieves the current plugin ID from the context."""
    return _current_plugin_id.get()

def reset_current_plugin_id(token: contextvars.Token) -> None:
    """Resets the current plugin ID context using the provided token."""
    _current_plugin_id.reset(token)
