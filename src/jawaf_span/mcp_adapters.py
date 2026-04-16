from __future__ import annotations

import json
from typing import Any

from jawafdehi_mcp.tools.date_converter import DateConverterTool
from jawafdehi_mcp.tools.document_converter import DocumentConverterTool
from jawafdehi_mcp.tools.jawafdehi_cases import (
    CreateJawafdehiCaseTool,
    CreateJawafEntityTool,
    GetJawafdehiCaseTool,
    GetJawafEntityTool,
    PatchJawafdehiCaseTool,
    SearchJawafdehiCasesTool,
    SearchJawafEntitiesTool,
    UploadDocumentSourceTool,
)
from jawafdehi_mcp.tools.ngm_extract import NGMExtractCaseDataTool
from mcp.types import TextContent


class MCPToolAdapter:
    def __init__(self) -> None:
        self.ngm_extract_case_data_tool = NGMExtractCaseDataTool()
        self.convert_to_markdown_tool = DocumentConverterTool()
        self.create_jawafdehi_case_tool = CreateJawafdehiCaseTool()
        self.patch_jawafdehi_case_tool = PatchJawafdehiCaseTool()
        self.upload_document_source_tool = UploadDocumentSourceTool()
        self.search_jawaf_entities_tool = SearchJawafEntitiesTool()
        self.get_jawaf_entity_tool = GetJawafEntityTool()
        self.create_jawaf_entity_tool = CreateJawafEntityTool()
        self.get_jawafdehi_case_tool = GetJawafdehiCaseTool()
        self.search_jawafdehi_cases_tool = SearchJawafdehiCasesTool()
        self.convert_date_tool = DateConverterTool()

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

    async def ngm_extract_case_data(self, arguments: dict[str, Any]) -> str:
        result = self._text_content(
            await self.ngm_extract_case_data_tool.execute(arguments)
        )
        try:
            payload = json.loads(result)
            if isinstance(payload, dict) and not payload.get("success", True):
                raise RuntimeError(str(payload.get("error", result)))
        except json.JSONDecodeError:
            pass
        return result

    async def convert_to_markdown(self, arguments: dict[str, Any]) -> str:
        text = self._text_content(
            await self.convert_to_markdown_tool.execute(arguments)
        )
        if text.startswith("Error:"):
            raise RuntimeError(text)
        return text

    async def create_jawafdehi_case(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(
            await self.create_jawafdehi_case_tool.execute(arguments)
        )

    async def patch_jawafdehi_case(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(
            await self.patch_jawafdehi_case_tool.execute(arguments)
        )

    async def upload_document_source(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(
            await self.upload_document_source_tool.execute(arguments)
        )

    async def search_jawaf_entities(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(
            await self.search_jawaf_entities_tool.execute(arguments)
        )

    async def get_jawaf_entity(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(await self.get_jawaf_entity_tool.execute(arguments))

    async def create_jawaf_entity(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(
            await self.create_jawaf_entity_tool.execute(arguments)
        )

    async def get_jawafdehi_case(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(await self.get_jawafdehi_case_tool.execute(arguments))

    async def search_jawafdehi_cases(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(
            await self.search_jawafdehi_cases_tool.execute(arguments)
        )

    async def convert_date(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._json_payload(await self.convert_date_tool.execute(arguments))
