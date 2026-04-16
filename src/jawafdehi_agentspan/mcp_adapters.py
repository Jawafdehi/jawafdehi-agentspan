from __future__ import annotations

import json
from typing import Any

from jawafdehi_mcp.server import TOOL_MAP
from mcp.types import TextContent


class MCPToolAdapter:
    @staticmethod
    def _text_content(items: list[TextContent]) -> str:
        return "\n".join(
            item.text for item in items if getattr(item, "text", None)
        ).strip()

    @classmethod
    def _json_payload(cls, items: list[TextContent]) -> dict[str, Any]:
        text = cls._text_content(items)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Expected JSON MCP response, got: {text}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Expected object payload, got: {type(payload).__name__}"
            )
        if "error" in payload:
            raise RuntimeError(str(payload["error"]))
        return payload

    async def call_text(self, tool_name: str, arguments: dict[str, Any]) -> str:
        tool = TOOL_MAP.get(tool_name)
        if tool is None:
            raise RuntimeError(f"Unknown MCP tool: {tool_name}")
        return self._text_content(await tool.execute(arguments))

    async def call_json(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        tool = TOOL_MAP.get(tool_name)
        if tool is None:
            raise RuntimeError(f"Unknown MCP tool: {tool_name}")
        return self._json_payload(await tool.execute(arguments))

    async def ngm_extract_case_data(self, arguments: dict[str, Any]) -> str:
        result = await self.call_text("ngm_extract_case_data", arguments)
        try:
            payload = json.loads(result)
            if isinstance(payload, dict) and not payload.get("success", True):
                raise RuntimeError(str(payload.get("error", result)))
        except json.JSONDecodeError:
            pass
        return result

    async def convert_to_markdown(self, arguments: dict[str, Any]) -> str:
        text = await self.call_text("convert_to_markdown", arguments)
        if text.startswith("Error:"):
            raise RuntimeError(text)
        return text

    async def create_jawafdehi_case(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("create_jawafdehi_case", arguments)

    async def patch_jawafdehi_case(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("patch_jawafdehi_case", arguments)

    async def upload_document_source(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("upload_document_source", arguments)

    async def search_jawaf_entities(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("search_jawaf_entities", arguments)

    async def get_jawaf_entity(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("get_jawaf_entity", arguments)

    async def create_jawaf_entity(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("create_jawaf_entity", arguments)

    async def get_jawafdehi_case(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("get_jawafdehi_case", arguments)

    async def search_jawafdehi_cases(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("search_jawafdehi_cases", arguments)

    async def convert_date(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_json("convert_date", arguments)
