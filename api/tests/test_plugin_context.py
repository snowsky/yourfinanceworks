"""Tests for the plugin-context ContextVar pair.

The original implementation returned only the plugin_id token from
``set_current_plugin_id(lock=True)``, so a request finally-block that
called ``reset_current_plugin_id(token)`` left ``_is_locked=True``
stuck in the surrounding asyncio task. Any code reusing that task
(BackgroundTasks, run_in_executor inheritance, sub-tasks) would then
trip the spurious ``SECURITY ALERT`` log on the next legitimate
``set_current_plugin_id`` call.

These tests pin the fix: ``set_current_plugin_id`` now returns a
``PluginContextTokens`` dataclass holding both tokens, and
``reset_current_plugin_id`` resets the pair atomically.
"""

import contextvars
import pytest

from core.utils.plugin_context import (
    PluginContextTokens,
    get_current_plugin_id,
    is_lockdown_mode,
    reset_current_plugin_id,
    set_current_plugin_id,
)


def _run_in_clean_context(fn):
    """Run ``fn`` inside a fresh ``contextvars.copy_context()`` so each test
    gets isolated ContextVar state regardless of run order."""
    ctx = contextvars.copy_context()
    return ctx.run(fn)


def test_set_with_lock_returns_both_tokens():
    def go():
        tokens = set_current_plugin_id("alpha", lock=True)
        assert isinstance(tokens, PluginContextTokens)
        assert tokens.plugin_id_token is not None
        assert tokens.lock_token is not None

    _run_in_clean_context(go)


def test_set_without_lock_returns_only_plugin_id_token():
    def go():
        tokens = set_current_plugin_id("alpha", lock=False)
        assert tokens is not None
        assert tokens.plugin_id_token is not None
        assert tokens.lock_token is None

    _run_in_clean_context(go)


def test_reset_clears_lock_state_too():
    """Regression: the original bug left _is_locked stuck at True after reset."""

    def go():
        assert is_lockdown_mode() is False
        tokens = set_current_plugin_id("alpha", lock=True)
        assert is_lockdown_mode() is True
        assert get_current_plugin_id() == "alpha"

        reset_current_plugin_id(tokens)

        # Both ContextVars are restored to their pre-set values.
        assert is_lockdown_mode() is False, (
            "_is_locked leaked past reset_current_plugin_id — this used to "
            "trigger the spurious SECURITY ALERT log on the next "
            "set_current_plugin_id call."
        )
        assert get_current_plugin_id() is None

    _run_in_clean_context(go)


def test_reset_is_noop_on_none_tokens():
    """A lockdown-rejected ``set_current_plugin_id`` returns ``None``; the
    middleware calls ``reset_current_plugin_id`` unconditionally in its
    finally-block, so the reset must tolerate ``None``."""

    def go():
        reset_current_plugin_id(None)  # must not raise
        assert is_lockdown_mode() is False
        assert get_current_plugin_id() is None

    _run_in_clean_context(go)


def test_subsequent_set_after_reset_does_not_log_security_alert(caplog):
    """End-to-end of the bug the lock-reset fix closes: after a clean
    request scope, the next ``set_current_plugin_id`` for a different
    plugin must succeed without firing the lockdown SECURITY ALERT."""

    def go():
        tokens = set_current_plugin_id("alpha", lock=True)
        reset_current_plugin_id(tokens)

        with caplog.at_level("WARNING"):
            new_tokens = set_current_plugin_id("beta", lock=True)

        assert new_tokens is not None
        assert get_current_plugin_id() == "beta"
        assert not any(
            "SECURITY ALERT" in r.message for r in caplog.records
        ), (
            "Setting a fresh plugin_id after a clean reset must not log "
            "SECURITY ALERT — that's the bug the lock-token-reset fixes."
        )

    _run_in_clean_context(go)


def test_lockdown_still_blocks_changes_within_a_request():
    """The lock semantics for a single request scope are unchanged: once
    lock=True, the plugin_id cannot be changed mid-flight."""

    def go():
        tokens = set_current_plugin_id("alpha", lock=True)
        assert tokens is not None

        attempted = set_current_plugin_id("evil")
        # Returns None to signal the change was rejected.
        assert attempted is None
        # The current plugin_id did not change.
        assert get_current_plugin_id() == "alpha"
        assert is_lockdown_mode() is True

    _run_in_clean_context(go)
