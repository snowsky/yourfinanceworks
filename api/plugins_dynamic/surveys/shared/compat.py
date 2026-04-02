"""
Compatibility shim — detects whether we are running as a YFW plugin or standalone.

Usage:
    from shared.compat import get_current_user, STANDALONE
"""

try:
    # ── Plugin mode ───────────────────────────────────────────────────────────
    from core.routers.auth import get_current_user  # noqa: F401
    STANDALONE = False

except ImportError:
    # ── Standalone mode ───────────────────────────────────────────────────────
    from standalone.auth import get_current_user    # noqa: F401
    STANDALONE = True

__all__ = ["get_current_user", "STANDALONE"]
