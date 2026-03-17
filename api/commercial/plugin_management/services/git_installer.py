"""
Git-based plugin installer for YourFinanceWORKS.

Clones a plugin repository into api/plugins/ and optionally copies
its ui/ directory into ui/src/plugins/. A server restart and frontend
rebuild are required after installation for the plugin to become active.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Paths relative to this file:
# api/commercial/plugin_management/services/git_installer.py
#  ^4 parents up = api/
_API_DIR = Path(__file__).parent.parent.parent.parent
_API_PLUGINS_DIR = _API_DIR / "plugins"

# UI plugins dir: prefer the env var (set in Docker to a mounted host path),
# fall back to the relative path for local non-Docker runs.
_UI_PLUGINS_DIR = Path(os.environ.get("UI_PLUGINS_DIR", str(_API_DIR.parent / "ui" / "src" / "plugins")))

_VALID_GIT_URL = re.compile(
    r"^(https?://[^\s]+|git@[^\s:]+:[^\s]+|ssh://[^\s]+|file://[^\s]+)$"
)

# In-memory job store (single-process; sufficient for self-hosted deployments)
_jobs: dict[str, "InstallJob"] = {}


@dataclass
class InstallStep:
    label: str
    status: str = "pending"   # pending | running | done | failed
    detail: Optional[str] = None


@dataclass
class InstallJob:
    job_id: str
    git_url: str
    ref: str
    status: str = "pending"   # pending | running | done | failed
    plugin_id: Optional[str] = None
    error: Optional[str] = None
    restart_required: bool = True
    steps: list = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "git_url": self.git_url,
            "ref": self.ref,
            "status": self.status,
            "plugin_id": self.plugin_id,
            "error": self.error,
            "restart_required": self.restart_required,
            "steps": [
                {"label": s.label, "status": s.status, "detail": s.detail}
                for s in self.steps
            ],
            "created_at": self.created_at.isoformat(),
        }


def _step(job: InstallJob, label: str) -> InstallStep:
    s = InstallStep(label=label, status="running")
    job.steps.append(s)
    return s


def _ok(step: InstallStep, detail: Optional[str] = None) -> None:
    step.status = "done"
    step.detail = detail


def _fail(step: InstallStep, detail: str) -> None:
    step.status = "failed"
    step.detail = detail


def _validate_git_url(url: str) -> None:
    if not _VALID_GIT_URL.match(url):
        raise ValueError(f"Invalid git URL: {url!r}")
    # Reject obviously dangerous patterns
    for bad in (";", "&&", "|", "`", "$", "\n", "\r"):
        if bad in url:
            raise ValueError("Git URL contains disallowed characters")


def run_install(job_id: str) -> None:
    """
    Blocking install routine — intended to be called from a background thread
    via FastAPI BackgroundTasks.
    """
    job = _jobs.get(job_id)
    if not job:
        return

    job.status = "running"
    tmp_dir: Optional[Path] = None

    try:
        # ── 1. Clone ─────────────────────────────────────────────────────────
        step = _step(job, "Cloning repository")
        with tempfile.TemporaryDirectory(prefix="yfworks_plugin_") as td:
            tmp_dir = Path(td) / "repo"
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", job.ref, job.git_url, str(tmp_dir)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                _fail(step, result.stderr.strip())
                raise RuntimeError("git clone failed")
            _ok(step, f"Cloned from {job.git_url}@{job.ref}")

            # ── 2. Validate manifest ─────────────────────────────────────────
            step = _step(job, "Validating plugin manifest")
            manifest_path = tmp_dir / "plugin.json"
            if not manifest_path.exists():
                _fail(step, "plugin.json not found in repository root")
                raise RuntimeError("Missing plugin.json")

            with manifest_path.open() as fh:
                manifest = json.load(fh)

            missing = [f for f in ("name", "version", "description") if not manifest.get(f)]
            if missing:
                _fail(step, f"plugin.json missing required fields: {missing}")
                raise RuntimeError("Invalid manifest")

            raw_name: str = manifest["name"]
            plugin_id = raw_name.lower().replace(" ", "-")
            folder_name = plugin_id.replace("-", "_")
            job.plugin_id = plugin_id
            _ok(step, f"Plugin: {raw_name} v{manifest['version']}")

            dest_api = _API_PLUGINS_DIR / folder_name
            if dest_api.exists():
                _fail(step, f"Plugin folder already exists: {dest_api}")
                raise RuntimeError("Plugin already installed")

            # ── 3. Install Python dependencies ───────────────────────────────
            req_file = tmp_dir / "requirements.txt"
            if req_file.exists():
                step = _step(job, "Installing Python dependencies")
                result = subprocess.run(
                    ["pip", "install", "-r", str(req_file)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    _fail(step, result.stderr.strip()[:500])
                    raise RuntimeError("pip install failed")
                _ok(step, "Dependencies installed")

            # ── 4. Copy backend plugin files ─────────────────────────────────
            step = _step(job, "Installing plugin files")
            # If the repo has an api/plugins/<name>/ subfolder, use that;
            # otherwise treat the repo root as the plugin folder.
            nested = tmp_dir / "api" / "plugins" / folder_name
            source_api = nested if nested.exists() else tmp_dir

            shutil.copytree(str(source_api), str(dest_api), ignore=shutil.ignore_patterns("ui", ".git", "__pycache__", "*.pyc"))
            _ok(step, f"Backend installed to plugins/{folder_name}/")

            # ── 5. Copy frontend plugin files (if present) ───────────────────
            # Look for ui/ in repo root or ui/src/plugins/<name>/
            ui_source = None
            for candidate in (
                tmp_dir / "ui" / "src" / "plugins" / folder_name,
                tmp_dir / "ui",
            ):
                if candidate.exists() and (candidate / "index.ts").exists():
                    ui_source = candidate
                    break

            if ui_source and _UI_PLUGINS_DIR.exists():
                step = _step(job, "Installing frontend plugin files")
                dest_ui = _UI_PLUGINS_DIR / folder_name
                shutil.copytree(str(ui_source), str(dest_ui))
                _ok(step, f"Frontend installed to ui/src/plugins/{folder_name}/")
            else:
                step = _step(job, "Frontend files")
                _ok(step, "No frontend files found (backend-only plugin)")

            # ── 6. Reset plugin loader cache ─────────────────────────────────
            step = _step(job, "Registering plugin")
            try:
                from plugins.loader import plugin_loader
                plugin_loader._discovery_done = False
                plugin_loader._discovered = []
                plugin_loader._table_registry = {}
                _ok(step, "Plugin loader cache reset — restart required to activate")
            except Exception as exc:
                _ok(step, f"Cache reset skipped: {exc}")

        job.status = "done"
        logger.info("Plugin '%s' installed successfully from %s", plugin_id, job.git_url)

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        logger.error("Plugin install failed (job %s): %s", job_id, exc)
        # Mark any still-running steps as failed
        for s in job.steps:
            if s.status == "running":
                s.status = "failed"
        # Clean up partial install
        try:
            if job.plugin_id:
                folder = job.plugin_id.replace("-", "_")
                partial = _API_PLUGINS_DIR / folder
                if partial.exists():
                    shutil.rmtree(partial)
        except Exception:
            pass


def start_install(git_url: str, ref: str = "main") -> InstallJob:
    """Validate inputs, create an InstallJob, and return it (caller runs it in background)."""
    _validate_git_url(git_url)
    job = InstallJob(job_id=str(uuid.uuid4()), git_url=git_url, ref=ref)
    _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[InstallJob]:
    return _jobs.get(job_id)


def uninstall_plugin(plugin_id: str) -> None:
    """
    Remove plugin files from disk and reset the loader cache.
    Raises FileNotFoundError if the plugin folder does not exist.
    """
    folder_name = plugin_id.replace("-", "_")

    api_dir = _API_PLUGINS_DIR / folder_name
    if not api_dir.exists():
        raise FileNotFoundError(f"Plugin folder not found: {api_dir}")

    shutil.rmtree(api_dir)
    logger.info("Removed backend plugin folder: %s", api_dir)

    ui_dir = _UI_PLUGINS_DIR / folder_name
    if ui_dir.exists():
        shutil.rmtree(ui_dir)
        logger.info("Removed frontend plugin folder: %s", ui_dir)

    # Reset loader cache
    try:
        from plugins.loader import plugin_loader
        plugin_loader._discovery_done = False
        plugin_loader._discovered = []
        plugin_loader._table_registry = {}
    except Exception as exc:
        logger.warning("Could not reset plugin loader cache: %s", exc)
