"""Local state persistence for monitor dedupe."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AgentState:
    """Persisted monitor state."""

    last_run_at: str | None = None
    recommendations: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "AgentState":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(
            last_run_at=data.get("last_run_at"),
            recommendations=dict(data.get("recommendations") or {}),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_run_at": self.last_run_at or datetime.now(timezone.utc).isoformat(),
            "recommendations": self.recommendations,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def append_history(path: Path, payload: dict[str, Any]) -> None:
    """Append one monitor cycle event as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str))
        handle.write("\n")


def write_snapshot(snapshot_dir: Path, payload: dict[str, Any]) -> Path:
    """Write a per-cycle snapshot for audit/history purposes."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = snapshot_dir / f"monitor-{timestamp}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return path
