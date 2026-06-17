import pytest
from MCP.tools.settings import SettingsToolsMixin


class _FakeClient:
    def __init__(self):
        self.sent = None

    async def update_settings(self, settings_data):
        self.sent = settings_data
        return {"invoice_branding": settings_data["invoice_branding"]}


class _Tools(SettingsToolsMixin):
    def __init__(self, client):
        self.api_client = client


@pytest.mark.asyncio
async def test_set_branding_sends_only_provided_colors():
    client = _FakeClient()
    tools = _Tools(client)
    result = await tools.set_branding(accent_color="#3b82f6")
    assert result["success"] is True
    assert client.sent == {"invoice_branding": {"accent_color": "#3b82f6"}}


@pytest.mark.asyncio
async def test_set_branding_includes_both_colors_when_given():
    client = _FakeClient()
    tools = _Tools(client)
    await tools.set_branding(brand_color="#1e3a8a", accent_color="#3b82f6")
    assert client.sent["invoice_branding"] == {"brand_color": "#1e3a8a", "accent_color": "#3b82f6"}


@pytest.mark.asyncio
async def test_set_branding_rejects_empty():
    client = _FakeClient()
    tools = _Tools(client)
    result = await tools.set_branding()
    assert result["success"] is False
    assert client.sent is None
