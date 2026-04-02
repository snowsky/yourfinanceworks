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
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Absolute path to the directory that contains plugin sub-folders
_PLUGINS_DIR = Path(__file__).parent
_DYNAMIC_PLUGINS_DIR = Path("/app/plugins_dynamic")


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
        self._table_registry: dict[str, str] = {}
        self._permissions_registry: dict[str, set[str]] = {}
        self._load_errors: dict[str, str] = {}  # plugin_id → human-readable error
        self._plugin_route_map: dict[str, str] = {}  # route_prefix → plugin_id
        self._plugin_dir_cache: dict[str, Path] = {}  # plugin_id → plugin_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(self) -> list[DiscoveredPlugin]:
        """
        Walk all plugin directories and return validated plugin objects.

        Safe to call multiple times — runs the filesystem scan only once.
        """
        if self._discovery_done:
            return self._discovered

        self._discovered = []

        # Scan both root plugin directories
        scan_configs = [
            {"dir": _PLUGINS_DIR, "prefix": "plugins"},
            {"dir": _DYNAMIC_PLUGINS_DIR, "prefix": None}  # Direct import
        ]

        import sys
        for config in scan_configs:
            scan_dir = config["dir"]
            if not scan_dir.exists():
                continue

            # Add dynamic directory to sys.path if not present
            if config["prefix"] is None and str(scan_dir) not in sys.path:
                sys.path.append(str(scan_dir))

            for manifest_path in sorted(scan_dir.glob("*/plugin.json")):
                plugin_dir = manifest_path.parent
                plugin_id = plugin_dir.name.replace("_", "-")

                if plugin_id.startswith("_"):
                    continue

                try:
                    manifest = self._load_manifest(manifest_path)
                except Exception as exc:
                    logger.error("Plugin '%s': failed to load plugin.json — %s", plugin_id, exc)
                    continue

                if not self._validate_manifest(plugin_id, manifest):
                    continue

                # Resolve Python package path
                pkg_name = plugin_dir.name.replace("-", "_")
                package = f"{config['prefix']}.{pkg_name}" if config["prefix"] else pkg_name

                self._discovered.append(
                    DiscoveredPlugin(
                        plugin_id=plugin_id,
                        package=package,
                        manifest=manifest,
                        plugin_dir=plugin_dir,
                    )
                )
                logger.info("Plugin discovered: %s v%s (from %s)", plugin_id, manifest.get("version", "?"), scan_dir)

        self._discovery_done = True
        self._plugin_dir_cache = {p.plugin_id: p.plugin_dir for p in self._discovered}
        self._permissions_registry = {}
        for p in self._discovered:
            permitted = set(p.manifest.get("permitted_core_tables", []))
            self._permissions_registry[p.plugin_id] = permitted

            # Also allow access by the 'name' field in manifest for backward compatibility
            # and to handle folder prefixes like 'yfw-' correctly.
            manifest_name = p.manifest.get("name")
            if manifest_name and manifest_name != p.plugin_id:
                # Normalize manifest name just in case
                manifest_name_normalized = manifest_name.lower().replace("_", "-")
                self._permissions_registry[manifest_name_normalized] = permitted
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
                self._load_errors[plugin.plugin_id] = f"Model import failed: {exc}"

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
            except Exception as exc:
                logger.warning(
                    "Plugin '%s': cannot import package '%s' — %s",
                    plugin.plugin_id,
                    plugin.package,
                    exc,
                )
                self._load_errors[plugin.plugin_id] = f"Import failed: {exc}"
                continue

            register_fn = self._resolve_register_fn(mod, plugin)
            if register_fn is None:
                logger.warning(
                    "Plugin '%s': no register function found, skipping.",
                    plugin.plugin_id,
                )
                self._load_errors[plugin.plugin_id] = "No register function found in plugin package"
                continue

            try:
                plugin_info = register_fn(app=app, mcp_registry=mcp_registry or None, feature_gate=None)
                if plugin_info and "routes" in plugin_info:
                    for route in plugin_info["routes"]:
                        self._plugin_route_map[route] = plugin.plugin_id
                
                logger.info(
                    "Plugin '%s' registered — routes: %s",
                    plugin.plugin_id,
                    (plugin_info or {}).get("routes", []),
                )
            except Exception as exc:
                logger.error(
                    "Plugin '%s': registration failed — %s", plugin.plugin_id, exc
                )
                self._load_errors[plugin.plugin_id] = f"Registration failed: {exc}"

            # Auto-mount plugin Tools API router if present (api/plugins/<name>/tools/router.py)
            try:
                tools_mod = importlib.import_module(f"{plugin.package}.tools.router")
                if hasattr(tools_mod, "router"):
                    app.include_router(tools_mod.router)
                    logger.info("Plugin '%s': tools router registered.", plugin.plugin_id)
            except ModuleNotFoundError:
                pass  # No tools/router.py — optional, not an error
            except Exception as exc:
                logger.warning(
                    "Plugin '%s': tools router failed to register — %s", plugin.plugin_id, exc
                )

    def get_valid_plugin_ids(self) -> set[str]:
        """Return the set of IDs of all discovered plugins (for API validation)."""
        return {p.plugin_id for p in self.discover()}

    def get_plugin_dir(self, plugin_id: str) -> Optional[Path]:
        """Return the physical directory of a discovered plugin."""
        self.discover()  # ensure cache is populated
        return self._plugin_dir_cache.get(plugin_id)

    def get_permitted_core_tables(self, plugin_id: str) -> set[str]:
        """Return the set of core tables a plugin is explicitly permitted to access."""
        self.discover()  # ensure registry is populated
        return self._permissions_registry.get(plugin_id, set())

    def is_dynamic_plugin(self, plugin_id: str) -> bool:
        """Return True if the plugin was loaded from the dynamic plugins directory."""
        p_dir = self.get_plugin_dir(plugin_id)
        return p_dir is not None and p_dir.is_relative_to(_DYNAMIC_PLUGINS_DIR)

    def get_plugin_route_map(self) -> dict[str, str]:
        """Return the mapping of URL prefixes to plugin IDs."""
        return self._plugin_route_map

    def get_registry(self) -> list[dict]:
        """Return a list of manifest dicts suitable for the /plugins/registry endpoint.

        Plugins that failed to load are included with a ``load_error`` field so the
        frontend can show an error state on the plugin card instead of hiding them.
        Dynamic (externally installed) plugins also expose ``is_external`` and
        ``git_source`` fields so the frontend can show a reinstall button.
        """
        result = []
        for p in self.discover():
            entry = dict(p.manifest)
            if p.plugin_id in self._load_errors:
                entry["load_error"] = self._load_errors[p.plugin_id]
            if self.is_dynamic_plugin(p.plugin_id):
                entry["is_external"] = True
                meta_file = p.plugin_dir / ".install_meta.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        entry["git_source"] = {"git_url": meta.get("git_url"), "ref": meta.get("ref")}
                    except Exception:
                        pass
            result.append(entry)
        return result

    def get_table_ownership_registry(self) -> dict[str, str]:
        """
        Returns a mapping of table names to their owners ('core' or plugin_id).
        Used by the database isolation interceptor.
        """
        if self._table_registry:
            return self._table_registry

        # Ensure models are imported first
        self.import_models()

        # Import TenantBase to inspect registered tables
        from core.models.models_per_tenant import Base as TenantBase

        registry = {}
        for table_name, table in TenantBase.metadata.tables.items():
            # Determine ownership based on the model's module path
            model_class = table.info.get("model")
            module_name = model_class.__module__ if model_class and hasattr(model_class, "__module__") else ""

            owner = "core"
            for plugin in self.discover():
                # 1. Check explicit table list in manifest
                explicit_tables = plugin.manifest.get("database_tables", [])
                if table_name in explicit_tables:
                    owner = plugin.plugin_id
                    break

                # Normalize IDs for comparison
                pid = plugin.plugin_id.lower()
                pid_underscore = pid.replace("-", "_")
                pid_hyphen = pid.replace("_", "-")

                # 2. Check if the table name starts with the plugin ID (various formats)
                if table_name.startswith(f"{pid_underscore}_") or \
                   table_name.startswith(f"{pid_hyphen}_") or \
                   table_name == pid_underscore or \
                   table_name == pid_hyphen:
                    owner = plugin.plugin_id
                    break

                # 3. Check if the module name contains the plugin package
                if module_name and (module_name.startswith(plugin.package) or \
                                    f".plugins.{pid_underscore}." in module_name or \
                                    f".plugins.{pid_hyphen}." in module_name):
                    owner = plugin.plugin_id
                    break

            registry[table_name] = owner
            if owner != "core":
                logger.info("Table '%s' correctly mapped to plugin '%s'", table_name, owner)
            else:
                logger.debug("Table '%s' owned by 'core' (module: %s)", table_name, module_name)

        self._table_registry = registry
        return registry

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
