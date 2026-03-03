"""
Plugin Auto-Discovery Loader for YourFinanceWORKS
===================================================

Scans the ``api/plugins/`` directory at startup, validates every
``plugin.json`` manifest it finds, imports each plugin's models so
SQLAlchemy registers their tables, and then registers each plugin's
FastAPI router with the application.

Usage (in main.py)
------------------
::

    from plugins.loader import plugin_loader

    # 1. Import models BEFORE init_db() so tables are created
    plugin_loader.import_models()
    init_db()

    # 2. Register routers AFTER the FastAPI app and middleware exist
    plugin_loader.register_all(app)

Public helpers
--------------
- ``plugin_loader.get_valid_plugin_ids()``  → set of discovered plugin IDs
- ``plugin_loader.get_registry()``          → list of manifest dicts for the API
"""

import importlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Absolute path to the directory that contains plugin sub-folders
_PLUGINS_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredPlugin:
    """Holds the parsed plugin.json manifest plus the resolved Python package path."""

    plugin_id: str          # e.g. "investments"
    package: str            # e.g. "plugins.investments"
    manifest: dict          # full plugin.json content
    plugin_dir: Path        # absolute path to the plugin folder


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class PluginLoader:
    """
    Discovers, imports, and registers plugins found under ``api/plugins/``.

    The instance is intentionally a module-level singleton so that both
    ``main.py`` (which calls ``register_all``) and the plugin management
    router (which needs ``get_valid_plugin_ids`` / ``get_registry``) share
    the same discovery results without running the filesystem scan twice.
    """

    def __init__(self) -> None:
        self._discovered: list[DiscoveredPlugin] = []
        self._discovery_done = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(self) -> list[DiscoveredPlugin]:
        """
        Walk ``api/plugins/*/plugin.json`` and return validated plugin objects.

        Safe to call multiple times — runs the filesystem scan only once.
        """
        if self._discovery_done:
            return self._discovered

        self._discovered = []

        for manifest_path in sorted(_PLUGINS_DIR.glob("*/plugin.json")):
            plugin_dir = manifest_path.parent
            plugin_id = plugin_dir.name  # folder name == plugin id

            # Skip private / helper directories
            if plugin_id.startswith("_"):
                continue

            try:
                manifest = self._load_manifest(manifest_path)
            except Exception as exc:
                logger.error(
                    "Plugin '%s': failed to load plugin.json — %s", plugin_id, exc
                )
                continue

            if not self._validate_manifest(plugin_id, manifest):
                continue

            package = f"plugins.{plugin_id.replace('-', '_')}"

            self._discovered.append(
                DiscoveredPlugin(
                    plugin_id=plugin_id,
                    package=package,
                    manifest=manifest,
                    plugin_dir=plugin_dir,
                )
            )
            logger.info("Plugin discovered: %s v%s", plugin_id, manifest.get("version", "?"))

        self._discovery_done = True
        logger.info(
            "Plugin discovery complete — found %d plugin(s): %s",
            len(self._discovered),
            [p.plugin_id for p in self._discovered],
        )
        return self._discovered

    def import_models(self) -> None:
        """
        Import models from each discovered plugin so SQLAlchemy registers
        them with ``TenantBase.metadata`` **before** ``init_db()`` is called.

        Plugins that have no ``models.py`` are silently skipped.
        """
        for plugin in self.discover():
            models_module = f"{plugin.package}.models"
            try:
                importlib.import_module(models_module)
                logger.info("Plugin '%s': models imported.", plugin.plugin_id)
            except ModuleNotFoundError:
                logger.debug(
                    "Plugin '%s': no models.py found, skipping model import.",
                    plugin.plugin_id,
                )
            except Exception as exc:
                logger.warning(
                    "Plugin '%s': error importing models — %s", plugin.plugin_id, exc
                )

    def register_all(self, app: Any, mcp_registry: Any = None) -> None:
        """
        Dynamically import each plugin's ``__init__.py`` and call its
        registration function with the FastAPI *app*.

        Discovery convention (tried in order):
        1. ``register_plugin(app)``                — preferred standardised name
        2. ``register_<folder_name>_plugin(app)``  — legacy name used by the
           existing ``investments`` and ``time_tracking`` plugins
        """
        for plugin in self.discover():
            try:
                mod = importlib.import_module(plugin.package)
            except ImportError as exc:
                logger.warning(
                    "Plugin '%s': cannot import package '%s' — %s",
                    plugin.plugin_id,
                    plugin.package,
                    exc,
                )
                continue

            register_fn = self._resolve_register_fn(mod, plugin)
            if register_fn is None:
                logger.warning(
                    "Plugin '%s': no register function found, skipping.",
                    plugin.plugin_id,
                )
                continue

            try:
                plugin_info = register_fn(app=app, mcp_registry=mcp_registry or None, feature_gate=None)
                logger.info(
                    "Plugin '%s' registered — routes: %s",
                    plugin.plugin_id,
                    (plugin_info or {}).get("routes", []),
                )
            except Exception as exc:
                logger.error(
                    "Plugin '%s': registration failed — %s", plugin.plugin_id, exc
                )

    def get_valid_plugin_ids(self) -> set[str]:
        """Return the set of IDs of all discovered plugins (for API validation)."""
        return {p.plugin_id for p in self.discover()}

    def get_registry(self) -> list[dict]:
        """Return a list of manifest dicts suitable for the /plugins/registry endpoint."""
        return [p.manifest for p in self.discover()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _load_manifest(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("plugin.json must be a JSON object")
        return data

    @staticmethod
    def _validate_manifest(plugin_id: str, manifest: dict) -> bool:
        """Log and return False if required fields are missing."""
        required = ("name", "version", "description")
        missing = [f for f in required if not manifest.get(f)]
        if missing:
            logger.error(
                "Plugin '%s': plugin.json is missing required fields: %s",
                plugin_id,
                missing,
            )
            return False
        return True

    @staticmethod
    def _resolve_register_fn(mod: Any, plugin: DiscoveredPlugin):
        """
        Try to find a callable registration function on *mod*.

        Checks:
        - ``register_plugin``
        - ``register_<underscore_id>_plugin``  (e.g. ``register_investments_plugin``)
        """
        # Preferred standardised name
        if callable(getattr(mod, "register_plugin", None)):
            return mod.register_plugin

        # Legacy convention: register_<folder_name>_plugin
        legacy_name = f"register_{plugin.plugin_id.replace('-', '_')}_plugin"
        if callable(getattr(mod, legacy_name, None)):
            return getattr(mod, legacy_name)

        return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

plugin_loader = PluginLoader()
