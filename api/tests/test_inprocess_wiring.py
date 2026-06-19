# api/tests/test_inprocess_wiring.py
import pytest
from types import SimpleNamespace

import commercial.ai.routers.action_handlers as ah
from commercial.ai.inprocess.base import InProcessAPIClient


@pytest.mark.asyncio
async def test_init_tools_builds_inprocess_client():
    user = SimpleNamespace(id=1, email="u@x.com", tenant_id=1, role="admin", is_superuser=False)
    tools = await ah._init_tools(db="DB", current_user=user)
    assert isinstance(tools.api_client, InProcessAPIClient)
    assert tools.api_client._db == "DB"
    assert tools.api_client._current_user is user
