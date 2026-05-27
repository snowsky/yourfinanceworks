"""State file persistence: permissions + payload integrity."""

from __future__ import annotations

import json
import os
import stat

import pytest

from cli.finance_agent_cli.state import AgentState


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only permission semantics")
def test_agent_state_save_restricts_permissions(tmp_path):
    state = AgentState(recommendations={"abc": "1.00"})
    state_path = tmp_path / "state.json"

    state.save(state_path)

    mode = stat.S_IMODE(os.stat(state_path).st_mode)
    assert mode == 0o600


def test_save_does_not_backfill_missing_last_run_at(tmp_path):
    """An untouched state must round-trip with last_run_at=None, not 'now'."""
    state_path = tmp_path / "state.json"

    AgentState().save(state_path)
    payload = json.loads(state_path.read_text())

    assert payload["last_run_at"] is None
    assert AgentState.load(state_path).last_run_at is None


def test_save_persists_set_last_run_at(tmp_path):
    state_path = tmp_path / "state.json"
    state = AgentState(last_run_at="2026-05-26T12:00:00Z")

    state.save(state_path)
    payload = json.loads(state_path.read_text())

    assert payload["last_run_at"] == "2026-05-26T12:00:00Z"
