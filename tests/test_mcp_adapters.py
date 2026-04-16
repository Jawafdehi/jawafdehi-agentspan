from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter


def _text_items(payload) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload))]


@pytest.mark.asyncio
async def test_call_json_dispatches_via_tool_map():
    adapter = MCPToolAdapter()
    fake_tool = AsyncMock(return_value=_text_items({"id": 7}))
    with patch(
        "jawafdehi_agentspan.mcp_adapters.TOOL_MAP",
        {"create_jawafdehi_case": type("T", (), {"execute": fake_tool})()},
    ):
        result = await adapter.call_json(
            "create_jawafdehi_case", {"title": "Test", "case_type": "CORRUPTION"}
        )
    assert result["id"] == 7


@pytest.mark.asyncio
async def test_call_json_raises_on_error_field():
    adapter = MCPToolAdapter()
    fake_tool = AsyncMock(return_value=_text_items({"error": "boom"}))
    with patch(
        "jawafdehi_agentspan.mcp_adapters.TOOL_MAP",
        {"patch_jawafdehi_case": type("T", (), {"execute": fake_tool})()},
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await adapter.call_json(
                "patch_jawafdehi_case", {"case_id": 1, "operations": []}
            )


@pytest.mark.asyncio
async def test_call_json_raises_on_unknown_tool():
    adapter = MCPToolAdapter()
    with patch("jawafdehi_agentspan.mcp_adapters.TOOL_MAP", {}):
        with pytest.raises(RuntimeError, match="Unknown MCP tool"):
            await adapter.call_json("nonexistent_tool", {})
