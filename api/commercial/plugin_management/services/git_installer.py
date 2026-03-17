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

# Job store — persisted to disk so jobs survive uvicorn --reload restarts
# triggered by the file watcher when new plugin files are written.
_JOBS_DIR = Path(tempfile.gettempdir()) / "yfworks_plugin_jobs"
_JOBS_DIR.mkdir(exist_ok=True)

# Tokens are kept in-memory ONLY — never written to disk.
# They are only needed during the clone step (step 1), which completes
# before uvicorn --reload is triggered by new plugin files in step 4/5.
_job_tokens: dict[str, str] = {}


def _job_path(job_id: str) -> Path:
    return _JOBS_DIR / f"{job_id}.json"


def _save_job(job: "InstallJob") -> None:
    try:
        _job_path(job.job_id).write_text(json.dumps(job.to_dict()), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not persist install job %s: %s", job.job_id, exc)


def _load_job(job_id: str) -> Optional["InstallJob"]:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        job = InstallJob(
            job_id=data["job_id"],
            git_url=data["git_url"],
            ref=data["ref"],
            status=data["status"],
            plugin_id=data.get("plugin_id"),
            error=data.get("error"),
            restart_required=data.get("restart_required", True),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
        for s in data.get("steps", []):
            step = InstallStep(label=s["label"], status=s["status"], detail=s.get("detail"))
            job.steps.append(step)
        return job
    except Exception as exc:
        logger.warning("Could not load install job %s: %s", job_id, exc)
        return None


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
    _save_job(job)
    return s


def _ok(step: InstallStep, job: InstallJob, detail: Optional[str] = None) -> None:
    step.status = "done"
    step.detail = detail
    _save_job(job)


def _fail(step: InstallStep, job: InstallJob, detail: str) -> None:
    step.status = "failed"
    step.detail = detail
    _save_job(job)


def _validate_git_url(url: str) -> None:
    if not _VALID_GIT_URL.match(url):
        raise ValueError(f"Invalid git URL: {url!r}")
    # Reject obviously dangerous patterns
    for bad in (";", "&&", "|", "`", "$", "\n", "\r"):
        if bad in url:
            raise ValueError("Git URL contains disallowed characters")


def _authenticated_url(git_url: str, token: str) -> str:
    """Embed a token into an HTTPS git URL for authenticated cloning."""
    # Works for GitHub, GitHub Enterprise, Gitea, GitLab, etc.
    # https://github.com/org/repo  →  https://<token>@github.com/org/repo
    if git_url.startswith("https://"):
        return git_url.replace("https://", f"https://{token}@", 1)
    # For http:// (uncommon but valid)
    if git_url.startswith("http://"):
        return git_url.replace("http://", f"http://{token}@", 1)
    return git_url  # SSH / file:// — token has no effect


def run_install(job_id: str) -> None:
    """
    Blocking install routine — intended to be called from a background thread
    via FastAPI BackgroundTasks.
    Job state is written to disk after every step so it survives a uvicorn
    --reload triggered by new files appearing in api/plugins/.
    """
    job = _load_job(job_id)
    if not job:
        return

    # Retrieve token from in-memory store (not persisted to disk)
    token = _job_tokens.pop(job_id, None)

    job.status = "running"
    _save_job(job)

    try:
        # ── 1. Clone ─────────────────────────────────────────────────────────
        step = _step(job, "Cloning repository")
        with tempfile.TemporaryDirectory(prefix="yfworks_plugin_") as td:
            tmp_dir = Path(td) / "repo"
            clone_url = _authenticated_url(job.git_url, token) if token else job.git_url
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", job.ref, clone_url, str(tmp_dir)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                _fail(step, job, result.stderr.strip())
                raise RuntimeError("git clone failed")
            _ok(step, job, f"Cloned from {job.git_url}@{job.ref}")

            # ── 2. Validate manifest ─────────────────────────────────────────
            step = _step(job, "Validating plugin manifest")
            manifest_path = tmp_dir / "plugin.json"
            if not manifest_path.exists():
                _fail(step, job, "plugin.json not found in repository root")
                raise RuntimeError("Missing plugin.json")

            with manifest_path.open() as fh:
                manifest = json.load(fh)

            missing = [f for f in ("name", "version", "description") if not manifest.get(f)]
            if missing:
                _fail(step, job, f"plugin.json missing required fields: {missing}")
                raise RuntimeError("Invalid manifest")

            raw_name: str = manifest["name"]
            plugin_id = raw_name.lower().replace(" ", "-")
            folder_name = plugin_id.replace("-", "_")
            job.plugin_id = plugin_id
            _ok(step, job, f"Plugin: {raw_name} v{manifest['version']}")

            dest_api = _API_PLUGINS_DIR / folder_name
            if dest_api.exists():
                _fail(step, job, f"Plugin folder already exists: {dest_api}")
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
                    _fail(step, job, result.stderr.strip()[:500])
                    raise RuntimeError("pip install failed")
                _ok(step, job, "Dependencies installed")

            # ── 4. Copy backend plugin files ─────────────────────────────────
            step = _step(job, "Installing plugin files")
            nested = tmp_dir / "api" / "plugins" / folder_name
            source_api = nested if nested.exists() else tmp_dir
            shutil.copytree(str(source_api), str(dest_api), ignore=shutil.ignore_patterns("ui", ".git", "__pycache__", "*.pyc"))
            _ok(step, job, f"Backend installed to plugins/{folder_name}/")

            # ── 5. Copy frontend plugin files (if present) ───────────────────
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
                _ok(step, job, f"Frontend installed to ui/src/plugins/{folder_name}/")
            else:
                step = _step(job, "Frontend files")
                _ok(step, job, "No frontend files found (backend-only plugin)")

            # ── 6. Reset plugin loader cache ─────────────────────────────────
            step = _step(job, "Registering plugin")
            try:
                from plugins.loader import plugin_loader
                plugin_loader._discovery_done = False
                plugin_loader._discovered = []
                plugin_loader._table_registry = {}
                _ok(step, job, "Plugin loader cache reset — restart required to activate")
            except Exception as exc:
                _ok(step, job, f"Cache reset skipped: {exc}")

        job.status = "done"
        _save_job(job)
        logger.info("Plugin '%s' installed successfully from %s", plugin_id, job.git_url)

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        logger.error("Plugin install failed (job %s): %s", job_id, exc)
        for s in job.steps:
            if s.status == "running":
                s.status = "failed"
        _save_job(job)
        # Clean up partial install
        try:
            if job.plugin_id:
                partial = _API_PLUGINS_DIR / job.plugin_id.replace("-", "_")
                if partial.exists():
                    shutil.rmtree(partial)
        except Exception:
            pass


def start_install(git_url: str, ref: str = "main", github_token: Optional[str] = None) -> InstallJob:
    """Validate inputs, create an InstallJob, persist it to disk, and return it.

    If *github_token* is provided it is stored in-memory only and used during
    the clone step. It is never written to disk.
    """
    _validate_git_url(git_url)
    job = InstallJob(job_id=str(uuid.uuid4()), git_url=git_url, ref=ref)
    _save_job(job)
    if github_token:
        _job_tokens[job.job_id] = github_token
    return job


def get_job(job_id: str) -> Optional[InstallJob]:
    """Load job state from disk — survives process restarts."""
    return _load_job(job_id)


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
