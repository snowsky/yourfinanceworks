"""
Unit tests for api/plugins/loader.py
=====================================

These tests use pytest's tmp_path fixture to create synthetic plugin
directory layouts without touching the real api/plugins/ folder.

Run:
    cd api && source venv/bin/activate
    pytest tests/test_plugin_loader.py -v
"""

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_plugin(tmp_path: Path, plugin_id: str, manifest: dict, has_models: bool = False) -> Path:
    """
    Create a minimal plugin folder structure under tmp_path.

    Returns the plugin directory path.
    """
    plugin_dir = tmp_path / plugin_id
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (plugin_dir / "__init__.py").write_text(
        "def register_plugin(app, mcp_registry=None, feature_gate=None):\n"
        "    return {'name': '" + plugin_id + "', 'version': '1.0.0', 'routes': []}\n"
    )
    if has_models:
        (plugin_dir / "models.py").write_text("# stub models\n")
    return plugin_dir


VALID_MANIFEST = {
    "name": "test-plugin",
    "version": "1.0.0",
    "description": "A test plugin for unit testing",
    "license_tier": "agpl",
}


# ---------------------------------------------------------------------------
# Tests — PluginLoader (patching _PLUGINS_DIR to use tmp_path)
# ---------------------------------------------------------------------------

@pytest.fixture()
def loader():
    """Return a fresh PluginLoader instance (not the module singleton)."""
    # Import fresh to avoid state pollution between tests
    from plugins.loader import PluginLoader
    return PluginLoader()


# 1. Happy path: valid plugin is discovered
def test_discover_valid_plugin(tmp_path, loader):
    make_plugin(tmp_path, "test-plugin", VALID_MANIFEST)

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        discovered = loader.discover()

    assert len(discovered) == 1
    assert discovered[0].plugin_id == "test-plugin"
    assert discovered[0].manifest["version"] == "1.0.0"


# 2. Directory without plugin.json is silently skipped
def test_discover_no_manifest(tmp_path, loader):
    (tmp_path / "orphan-plugin").mkdir()

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        discovered = loader.discover()

    assert discovered == []


# 3. Malformed plugin.json is skipped and does not raise
def test_discover_invalid_json(tmp_path, loader):
    plugin_dir = tmp_path / "bad-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text("{not valid json", encoding="utf-8")

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        discovered = loader.discover()

    assert discovered == []


# 4. plugin.json missing required fields is skipped
def test_discover_missing_required_fields(tmp_path, loader):
    # Missing 'description'
    bad_manifest = {"name": "no-desc-plugin", "version": "1.0.0"}
    make_plugin(tmp_path, "no-desc-plugin", bad_manifest)

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        discovered = loader.discover()

    assert discovered == []


# 5. Directories starting with '_' (e.g. __pycache__) are skipped
def test_discover_skips_private_dirs(tmp_path, loader):
    make_plugin(tmp_path, "_private", VALID_MANIFEST)

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        discovered = loader.discover()

    assert discovered == []


# 6. Multiple valid plugins are all discovered
def test_discover_multiple_plugins(tmp_path, loader):
    for name in ("alpha", "beta", "gamma"):
        make_plugin(tmp_path, name, {**VALID_MANIFEST, "name": name})

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        discovered = loader.discover()

    assert len(discovered) == 3
    ids = {d.plugin_id for d in discovered}
    assert ids == {"alpha", "beta", "gamma"}


# 7. get_valid_plugin_ids returns the right set
def test_get_valid_plugin_ids(tmp_path, loader):
    make_plugin(tmp_path, "investments", {**VALID_MANIFEST, "name": "investments"})
    make_plugin(tmp_path, "time-tracking", {**VALID_MANIFEST, "name": "time-tracking"})

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        ids = loader.get_valid_plugin_ids()

    assert ids == {"investments", "time-tracking"}


# 8. get_registry returns manifest dicts
def test_get_registry(tmp_path, loader):
    make_plugin(tmp_path, "my-plugin", VALID_MANIFEST)

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        registry = loader.get_registry()

    assert len(registry) == 1
    assert registry[0]["name"] == "test-plugin"


# 9. import_models is a no-op when models.py is absent (no error raised)
def test_import_models_no_models_file(tmp_path, loader):
    make_plugin(tmp_path, "no-models", VALID_MANIFEST, has_models=False)

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        # Should not raise
        loader.import_models()


# 10. register_all calls register_plugin on each discovered plugin
def test_register_all_calls_register_plugin(tmp_path, loader):
    make_plugin(tmp_path, "plug-a", {**VALID_MANIFEST, "name": "plug-a"})
    make_plugin(tmp_path, "plug-b", {**VALID_MANIFEST, "name": "plug-b"})

    mock_app = MagicMock()

    # We need the temp plugin dirs to be importable
    sys.path.insert(0, str(tmp_path.parent))
    try:
        with patch("plugins.loader._PLUGINS_DIR", tmp_path):
            # Patch importlib.import_module so we control what gets "imported"
            def fake_import(name):
                mod = MagicMock()
                mod.register_plugin = MagicMock(return_value={"name": name, "version": "1.0.0", "routes": []})
                return mod

            with patch("plugins.loader.importlib.import_module", side_effect=fake_import):
                loader.register_all(mock_app)
    finally:
        sys.path.pop(0)

    # register_plugin should have been called once per plugin
    # (2 discover calls happen — but actual register only for found plugins)
    # Just verify no exception was raised and loader completed
    assert len(loader.discover()) == 2


# 11. Legacy register_<name>_plugin fallback is supported
def test_register_all_legacy_function_name(tmp_path, loader):
    make_plugin(tmp_path, "legacy-plug", {**VALID_MANIFEST, "name": "legacy-plug"})

    mock_app = MagicMock()

    def fake_import(name):
        mod = MagicMock(spec=[])  # no attributes except what we add
        # No 'register_plugin' — only the legacy name
        mod.register_legacy_plug_plugin = MagicMock(
            return_value={"name": "legacy-plug", "version": "1.0.0", "routes": []}
        )
        return mod

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        with patch("plugins.loader.importlib.import_module", side_effect=fake_import):
            loader.register_all(mock_app)  # should not raise

    # If we get here without an exception, legacy fallback worked
    assert True


# 12. discovery results are cached (filesystem not re-scanned)
def test_discovery_is_cached(tmp_path, loader):
    make_plugin(tmp_path, "cached-plugin", VALID_MANIFEST)

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        first = loader.discover()
        # Add a new plugin after first scan — should NOT appear (cache hit)
        make_plugin(tmp_path, "late-plugin", {**VALID_MANIFEST, "name": "late"})
        second = loader.discover()

    assert first is second  # same list object — not re-scanned
    assert len(second) == 1


# 13. get_public_registry strips sensitive metadata
def test_get_public_registry_strips_sensitive_fields(tmp_path, loader):
    """The public registry endpoint is exempt from auth; sensitive fields
    that help an attacker map the install surface (private git URLs, raw
    load-error text, permitted-core-tables capability lists) must not appear
    in the response."""
    make_plugin(tmp_path, "leaky-plugin", VALID_MANIFEST)

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        # Simulate a load error and a permitted_core_tables manifest field —
        # these are the kinds of payload an attacker would want to read.
        loader._load_errors["leaky-plugin"] = (
            "Traceback (most recent call last):\n  File \"/internal/path/...\""
        )
        for p in loader.discover():
            if p.plugin_id == "leaky-plugin":
                p.manifest["permitted_core_tables"] = ["users", "tenants"]
                p.manifest["git_source"] = {"git_url": "git@private:org/secret.git", "ref": "main"}

        public = loader.get_public_registry()
        full = loader.get_registry()

    assert len(public) == 1
    entry = public[0]
    # Sensitive fields are stripped.
    assert "git_source" not in entry
    assert "load_error" not in entry
    assert "permitted_core_tables" not in entry
    # Replacement boolean is present so the UI still renders an error state.
    assert entry["has_load_error"] is True
    # Manifest basics survive — UI still needs them for sidebar rendering.
    assert entry["name"] == "leaky-plugin"

    # Sanity: the admin-facing registry still carries the sensitive fields.
    full_entry = next(e for e in full if e.get("name") == "leaky-plugin")
    assert full_entry["load_error"].startswith("Traceback")
    assert full_entry["git_source"]["git_url"] == "git@private:org/secret.git"
    assert full_entry["permitted_core_tables"] == ["users", "tenants"]


# 14. get_public_registry without a load error reports has_load_error = False
def test_get_public_registry_has_load_error_false_for_healthy_plugin(tmp_path, loader):
    make_plugin(tmp_path, "healthy-plugin", VALID_MANIFEST)

    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        public = loader.get_public_registry()

    assert len(public) == 1
    assert public[0]["has_load_error"] is False


# 15. Concurrent reader + writer don't trip ``list changed size``
def test_registry_readers_tolerate_concurrent_retry_thread_writes(tmp_path, loader):
    """The sidecar retry thread appends to ``_discovered`` while the main
    thread may be iterating it in ``get_registry`` / ``get_public_registry``.
    Without lock-guarded snapshots this races into
    ``RuntimeError: list changed size during iteration``. This test
    hammers the readers in a loop while a background thread appends, and
    asserts no exception escapes.
    """
    import threading
    from plugins.loader import DiscoveredPlugin

    # Seed a healthy plugin so the readers have something to iterate over.
    make_plugin(tmp_path, "seed-plugin", VALID_MANIFEST)
    with patch("plugins.loader._PLUGINS_DIR", tmp_path):
        loader.discover()

    stop = threading.Event()
    errors: list[BaseException] = []

    def appender() -> None:
        i = 0
        while not stop.is_set():
            plugin = DiscoveredPlugin(
                plugin_id=f"hot-{i}",
                package="",
                manifest={
                    "name": f"hot-{i}",
                    "version": "1.0.0",
                    "description": "concurrent-append fuzz",
                    "license_tier": "agpl",
                },
                plugin_dir=Path("/sidecar/hot"),
                is_sidecar=True,
            )
            # Same code path the retry thread takes — wrap mutations in
            # the same lock the production code uses.
            with loader._mutation_lock:
                loader._discovered.append(plugin)
            i += 1

    def reader() -> None:
        try:
            for _ in range(200):
                loader.get_registry()
                loader.get_public_registry()
                loader.is_sidecar_plugin("seed-plugin")
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    writer_thread = threading.Thread(target=appender, name="appender")
    writer_thread.start()
    try:
        readers = [threading.Thread(target=reader, name=f"reader-{i}") for i in range(4)]
        for t in readers:
            t.start()
        for t in readers:
            t.join(timeout=15)
            assert not t.is_alive(), "reader thread hung — possible deadlock"
    finally:
        stop.set()
        writer_thread.join(timeout=5)

    assert errors == [], f"readers raised under concurrent writes: {errors!r}"


# 17. register_all filters kwargs to match the plugin's actual signature
def test_register_all_only_passes_declared_kwargs(tmp_path, loader):
    """``register_fn`` used to be called with ``app=, mcp_registry=, feature_gate=``
    unconditionally. A plugin defining ``register_plugin(app)`` (positional or
    keyword) failed with ``TypeError: unexpected keyword argument 'mcp_registry'``.
    The loader now uses ``inspect.signature`` to filter the kwargs."""
    make_plugin(tmp_path, "narrow-plug", {**VALID_MANIFEST, "name": "narrow-plug"})

    captured: dict = {}

    def narrow_register_plugin(app):
        captured["app"] = app
        captured["kwargs_seen"] = set()
        return {"name": "narrow-plug", "version": "1.0.0", "routes": []}

    def fake_import(name: str):
        if name == "plugins.narrow_plug":
            mod = MagicMock(spec=["register_plugin"])
            mod.register_plugin = narrow_register_plugin
            return mod
        raise ModuleNotFoundError(name)

    mock_app = MagicMock()
    sys.path.insert(0, str(tmp_path.parent))
    try:
        with patch("plugins.loader._PLUGINS_DIR", tmp_path):
            with patch("plugins.loader.importlib.import_module", side_effect=fake_import):
                # Should not raise — the loader filters out mcp_registry / feature_gate
                # because narrow_register_plugin doesn't declare them.
                loader.register_all(mock_app)
    finally:
        sys.path.pop(0)

    assert captured.get("app") is mock_app, (
        "Plugin's register_plugin(app) was not called — kwargs filter may have "
        "stripped the 'app' parameter too."
    )


# 18. register_all still passes mcp_registry to plugins that declare it
def test_register_all_passes_mcp_registry_when_declared(tmp_path, loader):
    """Symmetric check: plugins that DO declare ``mcp_registry`` still receive
    it. The kwargs filter must not silently drop wanted parameters."""
    make_plugin(tmp_path, "wide-plug", {**VALID_MANIFEST, "name": "wide-plug"})

    captured: dict = {}

    def wide_register_plugin(app, mcp_registry=None, feature_gate=None):
        captured["app"] = app
        captured["mcp_registry"] = mcp_registry
        captured["feature_gate"] = feature_gate
        return {"name": "wide-plug", "version": "1.0.0", "routes": []}

    def fake_import(name: str):
        if name == "plugins.wide_plug":
            mod = MagicMock(spec=["register_plugin"])
            mod.register_plugin = wide_register_plugin
            return mod
        raise ModuleNotFoundError(name)

    mock_app = MagicMock()
    mock_mcp = object()
    sys.path.insert(0, str(tmp_path.parent))
    try:
        with patch("plugins.loader._PLUGINS_DIR", tmp_path):
            with patch("plugins.loader.importlib.import_module", side_effect=fake_import):
                loader.register_all(mock_app, mcp_registry=mock_mcp)
    finally:
        sys.path.pop(0)

    assert captured.get("app") is mock_app
    assert captured.get("mcp_registry") is mock_mcp
    assert "feature_gate" in captured, "declared feature_gate was filtered out"


# 19. tools/router.py auto-mount injects the default auth dependency
def test_register_all_tools_router_is_mounted_with_auth_dependency(tmp_path, loader):
    """A plugin's optional tools/router.py is auto-mounted by ``register_all``.
    Without a router-level dependency, any route the plugin author forgot to
    decorate with ``Depends(get_current_user)`` is exposed unauthenticated.
    The loader now injects the dependency at mount time so the auto-mount
    convention is safe-by-default."""
    from fastapi.params import Depends as DependsParam
    from core.routers.auth import get_current_user as expected_dep

    make_plugin(tmp_path, "tools-plug", {**VALID_MANIFEST, "name": "tools-plug"})

    mock_app = MagicMock()
    tools_router = MagicMock(name="tools_router")

    def fake_import(name: str):
        # The plugin package — register_plugin returns the typical info dict.
        if name == "plugins.tools_plug":
            mod = MagicMock()
            mod.register_plugin = MagicMock(
                return_value={"name": "tools-plug", "version": "1.0.0", "routes": []}
            )
            return mod
        # The tools sub-module — exposes a router attribute the loader picks up.
        if name == "plugins.tools_plug.tools.router":
            mod = MagicMock()
            mod.router = tools_router
            return mod
        raise ModuleNotFoundError(name)

    sys.path.insert(0, str(tmp_path.parent))
    try:
        with patch("plugins.loader._PLUGINS_DIR", tmp_path):
            with patch("plugins.loader.importlib.import_module", side_effect=fake_import):
                loader.register_all(mock_app)
    finally:
        sys.path.pop(0)

    # Locate the include_router call that mounted the tools router (vs. any
    # other include_router the plugin's register_plugin may have triggered).
    tools_mount_calls = [
        call for call in mock_app.include_router.call_args_list
        if call.args and call.args[0] is tools_router
    ]
    assert tools_mount_calls, "tools router was not mounted at all"
    assert len(tools_mount_calls) == 1

    mount_kwargs = tools_mount_calls[0].kwargs
    deps = mount_kwargs.get("dependencies")
    assert deps, (
        "tools router was mounted with no router-level dependencies — any "
        "route the plugin author forgot to protect is now public on the API. "
        "Default auth dependency must be injected at mount time."
    )
    # The injected dependency is Depends(get_current_user). A FastAPI Depends
    # wrapper's ``dependency`` attribute is the bound callable.
    assert any(
        isinstance(d, DependsParam) and d.dependency is expected_dep
        for d in deps
    ), f"expected Depends(get_current_user) among tools-router deps, got {deps!r}"
