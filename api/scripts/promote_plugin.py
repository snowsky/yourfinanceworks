#!/usr/bin/env python3
"""Promote a standalone yfw-* plugin into this repository.

The standalone plugin layout is expected to look like:

    yfw-example/
      plugin.json
      __init__.py
      router.py
      models.py
      schemas.py
      plugin/ui/index.ts

This script copies backend files into api/plugins/<plugin_folder>/ and UI
files into ui/src/plugins/<plugin_folder>/plugin/ui/. It also adds the
needed .gitignore exception for the promoted backend plugin path.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
IGNORED_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}


def _plugin_slug(source: Path, explicit: str | None) -> str:
    if explicit:
        return explicit.strip().lower().replace("_", "-")

    manifest = source / "plugin.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        name = str(data.get("name") or "").strip()
        if name:
            return name.lower().replace("_", "-")

    name = source.name
    if name.startswith("yfw-"):
        name = name[4:]
    return name.lower().replace("_", "-")


def _plugin_folder(slug: str) -> str:
    return slug.replace("-", "_")


def _is_backend_path(relative_path: Path) -> bool:
    parts = relative_path.parts
    if not parts:
        return False
    if any(part in IGNORED_NAMES for part in parts):
        return False
    if parts[:2] == ("plugin", "ui"):
        return False
    if parts[0] == "ui":
        return False
    return True


def _copy_tree_contents(source: Path, destination: Path, *, force: bool, dry_run: bool) -> list[str]:
    copied: list[str] = []
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if item.is_dir() or not _is_backend_path(relative):
            continue

        target = destination / relative
        if target.exists() and not force:
            raise FileExistsError(f"{target} already exists. Re-run with --force to overwrite.")

        copied.append(str(target.relative_to(REPO_ROOT)))
        if dry_run:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
    return copied


def _copy_ui(source: Path, destination: Path, *, force: bool, dry_run: bool) -> list[str]:
    ui_source = source / "plugin" / "ui"
    if not ui_source.exists():
        return []

    copied: list[str] = []
    for item in sorted(ui_source.rglob("*")):
        relative = item.relative_to(ui_source)
        if item.is_dir() or any(part in IGNORED_NAMES for part in relative.parts):
            continue

        target = destination / relative
        if target.exists() and not force:
            raise FileExistsError(f"{target} already exists. Re-run with --force to overwrite.")

        copied.append(str(target.relative_to(REPO_ROOT)))
        if dry_run:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
    return copied


def _ensure_gitignore_exception(plugin_folder: str, *, dry_run: bool) -> bool:
    gitignore = REPO_ROOT / ".gitignore"
    line = f"!api/plugins/{plugin_folder}/"
    text = gitignore.read_text(encoding="utf-8")
    if line in text.splitlines():
        return False

    if not dry_run:
        suffix = "" if text.endswith("\n") else "\n"
        gitignore.write_text(f"{text}{suffix}{line}\n", encoding="utf-8")
    return True


def promote(source: Path, *, plugin_id: str | None, force: bool, dry_run: bool) -> int:
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(f"Plugin source not found: {source}")
    if not (source / "plugin.json").exists():
        raise FileNotFoundError(f"plugin.json not found in {source}")

    slug = _plugin_slug(source, plugin_id)
    folder = _plugin_folder(slug)
    backend_dest = REPO_ROOT / "api" / "plugins" / folder
    ui_dest = REPO_ROOT / "ui" / "src" / "plugins" / folder / "plugin" / "ui"

    backend_files = _copy_tree_contents(source, backend_dest, force=force, dry_run=dry_run)
    ui_files = _copy_ui(source, ui_dest, force=force, dry_run=dry_run)
    gitignore_updated = _ensure_gitignore_exception(folder, dry_run=dry_run)

    print(f"Promoted plugin: {slug}")
    print(f"Source: {source}")
    print(f"Backend destination: {backend_dest.relative_to(REPO_ROOT)}")
    print(f"UI destination: {ui_dest.relative_to(REPO_ROOT)}")
    print(f"Backend files: {len(backend_files)}")
    print(f"UI files: {len(ui_files)}")
    if gitignore_updated:
        print(f"Updated .gitignore with !api/plugins/{folder}/")
    if dry_run:
        print("Dry run only; no files were written.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Path to standalone plugin folder or yfw-* symlink")
    parser.add_argument("--plugin-id", help="Override plugin id from plugin.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing promoted files")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be copied without writing")
    args = parser.parse_args(argv)

    try:
        return promote(
            Path(args.source),
            plugin_id=args.plugin_id,
            force=args.force,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
