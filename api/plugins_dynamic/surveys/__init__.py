"""
YourFinanceWORKS surveys plugin package root.

When installed as a plugin (repo cloned into api/plugins/surveys/),
adding this directory to sys.path makes both `plugin` and `shared`
importable as top-level packages in plugin mode.
"""
import sys
from pathlib import Path

_here = Path(__file__).parent
# Detect if we are being imported as a YFW plugin (inside api/plugins/... or plugins_dynamic/...)
_is_plugin = "plugins" in __name__ or "plugins_dynamic" in __name__

if not _is_plugin and str(_here) not in sys.path:
    # Standalone mode: we need root folders 'plugin' and 'shared' to be top-level
    sys.path.insert(0, str(_here))

from .plugin.api import register_plugin  # noqa: E402

__all__ = ["register_plugin"]
