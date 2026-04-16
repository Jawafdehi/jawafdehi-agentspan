from __future__ import annotations

import json

import pytest
from mcp.types import TextContent

from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter


class FakeTool:
    def __init__(self, payload):
        self.payload = payload

    async def execute(self, arguments):
        return [TextContent(type="text", text=self.payload)]


@pytest.mark.asyncio
async def test_json_payload_is_parsed():
    adapter = MCPToolAdapter()
    adapter.create_jawafdehi_case_tool = FakeTool(json.dumps({"id": 7}))

    payload = await adapter.create_jawafdehi_case(
        {"title": "Test", "case_type": "CORRUPTION"}
    )
    assert payload["id"] == 7


@pytest.mark.asyncio
async def test_json_payload_error_raises():
    adapter = MCPToolAdapter()
    adapter.patch_jawafdehi_case_tool = FakeTool(json.dumps({"error": "boom"}))

    with pytest.raises(RuntimeError, match="boom"):
        await adapter.patch_jawafdehi_case({"case_id": 1, "operations": []})
