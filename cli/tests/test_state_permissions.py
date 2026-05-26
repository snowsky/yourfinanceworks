"""State file permission hardening."""

from __future__ import annotations

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
