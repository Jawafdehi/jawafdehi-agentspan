"""MCP tool server for Jawafdehi case management.

Exposes ``TOOL_MAP``, a dict mapping tool names to callable tool objects.
Each tool object has an async ``execute(arguments: dict) -> list[TextContent]``
method that the ``MCPToolAdapter`` in jawafdehi-agentspan calls at runtime.

Tools:
  - ngm_extract_case_data   – fetch structured case data from the NGM registry
  - convert_to_markdown     – convert a local file to Markdown via markitdown
  - create_jawafdehi_case   – create a new corruption case record via the API
  - patch_jawafdehi_case    – update an existing case via JSON Patch operations
  - upload_document_source  – upload a supporting document to the evidence store
  - search_jawaf_entities   – search accused/entity records
  - get_jawaf_entity        – fetch a single entity record by id
  - create_jawaf_entity     – create a new entity record
  - get_jawafdehi_case      – fetch a single case record by id
  - search_jawafdehi_cases  – search case records by keyword and type
  - convert_date            – convert between AD/BS calendar dates
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from mcp.types import TextContent

from jawafdehi_mcp._config import (
    jawafdehi_api_base_url,
    jawafdehi_api_token,
    nes_api_base_url,
)

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_TIMEOUT = 60.0


def _auth_headers() -> dict[str, str]:
    token = jawafdehi_api_token()
    return {"Authorization": f"Token {token}"} if token else {}


def _json_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload))]


def _plain_text(value: str) -> list[TextContent]:
    return [TextContent(type="text", text=value)]


async def _get_json(url: str, *, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        response = await client.get(url, params=params, headers=_auth_headers())
    response.raise_for_status()
    return response.json()


async def _post_json(url: str, *, data: dict) -> dict:
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        response = await client.post(url, json=data, headers=_auth_headers())
    response.raise_for_status()
    return response.json()


async def _patch_json(url: str, *, operations: list[dict]) -> dict:
    headers = {**_auth_headers(), "Content-Type": "application/json-patch+json"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        response = await client.patch(url, json=operations, headers=headers)
    response.raise_for_status()
    return response.json()


async def _post_multipart(url: str, *, fields: dict, file_path: str) -> dict:
    path = Path(file_path)
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        with path.open("rb") as file_handle:
            response = await client.post(
                url,
                data=fields,
                files={"file": (path.name, file_handle)},
                headers=_auth_headers(),
            )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Tool base class
# ---------------------------------------------------------------------------


class _Tool:
    """Base class for MCP tools."""

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# NGM / case data extraction
# ---------------------------------------------------------------------------


class _NgmExtractCaseData(_Tool):
    """Fetch structured case data from the NGM Special Court registry.

    Arguments:
        court_identifier (str): court slug, e.g. ``"special"``
        case_number (str): normalized case number, e.g. ``"081-CR-0046"``
        file_path (str): absolute path where the extracted Markdown will be saved
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        court = arguments["court_identifier"]
        case_number = arguments["case_number"]
        file_path = arguments["file_path"]

        base = nes_api_base_url().rstrip("/")
        url = f"{base}/api/cases/{court}/{case_number}/"
        payload = await _get_json(url)

        lines: list[str] = [f"# Case Data: {case_number}\n"]
        for key, value in payload.items():
            if isinstance(value, list):
                lines.append(f"\n## {key.replace('_', ' ').title()}\n")
                for item in value:
                    if isinstance(item, dict):
                        name = (
                            item.get("display_name")
                            or item.get("name")
                            or str(item)
                        )
                        nes_id = item.get("nes_id") or item.get("id")
                        if nes_id:
                            lines.append(f"- **{name}** (NES ID: {nes_id})")
                        else:
                            lines.append(f"- **{name}**")
                    else:
                        lines.append(f"- {item}")
            elif isinstance(value, dict):
                lines.append(f"\n## {key.replace('_', ' ').title()}\n")
                for k, v in value.items():
                    lines.append(f"- **{k}**: {v}")
            elif value is not None and str(value).strip():
                lines.append(f"\n## {key.replace('_', ' ').title()}\n\n{value}")

        markdown = "\n".join(lines)
        output = Path(file_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
        return _plain_text(markdown)


# ---------------------------------------------------------------------------
# Markdown conversion
# ---------------------------------------------------------------------------


class _ConvertToMarkdown(_Tool):
    """Convert a local file (PDF, DOCX, HTML, etc.) to Markdown.

    Arguments:
        file_path (str): source file path
        output_path (str): destination Markdown file path
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        from markitdown import MarkItDown  # type: ignore[import]

        file_path = Path(arguments["file_path"])
        output_path = Path(arguments["output_path"])

        converter = MarkItDown()
        result = converter.convert(str(file_path))
        markdown = result.text_content or ""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        return _plain_text(markdown)


# ---------------------------------------------------------------------------
# Jawafdehi case CRUD
# ---------------------------------------------------------------------------


class _CreateJawafdehibiCase(_Tool):
    """Create a new corruption case record in the Jawafdehi portal.

    Arguments:
        title (str): case title
        case_type (str): e.g. ``"CORRUPTION"``
        short_description (str): brief summary
        description (str): full description
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        base = jawafdehi_api_base_url().rstrip("/")
        payload = await _post_json(f"{base}/api/cases/", data=arguments)
        return _json_text(payload)


class _PatchJawafdehibiCase(_Tool):
    """Update an existing case via RFC 6902 JSON Patch operations.

    Arguments:
        case_id (int): the numeric case ID
        operations (list[dict]): JSON Patch operations array
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        case_id = arguments["case_id"]
        operations = arguments.get("operations") or arguments.get("patches") or []
        base = jawafdehi_api_base_url().rstrip("/")
        payload = await _patch_json(
            f"{base}/api/cases/{case_id}/",
            operations=operations,
        )
        return _json_text(payload)


class _GetJawafdehibiCase(_Tool):
    """Fetch a single case record by its numeric ID.

    Arguments:
        case_id (int): the numeric case ID
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        case_id = arguments["case_id"]
        base = jawafdehi_api_base_url().rstrip("/")
        payload = await _get_json(f"{base}/api/cases/{case_id}/")
        return _json_text(payload)


class _SearchJawafdehibiCases(_Tool):
    """Search case records by keyword and/or case type.

    Arguments:
        search (str): search keyword (e.g. case number or defendant name)
        case_type (str, optional): filter by case type, e.g. ``"CORRUPTION"``
        page (int, optional): page number for pagination
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        base = jawafdehi_api_base_url().rstrip("/")
        params: dict[str, Any] = {}
        if arguments.get("search"):
            params["search"] = arguments["search"]
        if arguments.get("case_type"):
            params["case_type"] = arguments["case_type"]
        if arguments.get("page"):
            params["page"] = arguments["page"]
        payload = await _get_json(f"{base}/api/cases/", params=params or None)
        return _json_text(payload)


# ---------------------------------------------------------------------------
# Document source upload
# ---------------------------------------------------------------------------


class _UploadDocumentSource(_Tool):
    """Upload a supporting document to the evidence store.

    Arguments:
        title (str): document title
        description (str): document description
        file_path (str): local path of the file to upload
        source_type (str): e.g. ``"OFFICIAL_GOVERNMENT"``
        url (list[str], optional): external URLs
        publication_date (str, optional): ISO date
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        base = jawafdehi_api_base_url().rstrip("/")
        fields = {
            "title": arguments.get("title", ""),
            "description": arguments.get("description", ""),
            "source_type": arguments.get("source_type", "OTHER"),
        }
        if arguments.get("publication_date"):
            fields["publication_date"] = arguments["publication_date"]
        urls = arguments.get("url") or []
        for idx, u in enumerate(urls):
            fields[f"url[{idx}]"] = u

        payload = await _post_multipart(
            f"{base}/api/sources/",
            fields=fields,
            file_path=arguments["file_path"],
        )
        return _json_text(payload)


# ---------------------------------------------------------------------------
# Entity CRUD
# ---------------------------------------------------------------------------


class _SearchJawafEntities(_Tool):
    """Search accused/entity records by display name or keyword.

    Arguments:
        search (str): search keyword
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        base = jawafdehi_api_base_url().rstrip("/")
        params = {"search": arguments.get("search", "")}
        payload = await _get_json(f"{base}/api/entities/", params=params)
        return _json_text(payload)


class _GetJawafEntity(_Tool):
    """Fetch a single entity record by its numeric ID.

    Arguments:
        entity_id (int): the entity ID
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        entity_id = arguments["entity_id"]
        base = jawafdehi_api_base_url().rstrip("/")
        payload = await _get_json(f"{base}/api/entities/{entity_id}/")
        return _json_text(payload)


class _CreateJawafEntity(_Tool):
    """Create a new entity record (accused person or organisation).

    Arguments:
        display_name (str): human-readable name
        nes_id (str, optional): NES system identifier
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        base = jawafdehi_api_base_url().rstrip("/")
        payload = await _post_json(f"{base}/api/entities/", data=arguments)
        return _json_text(payload)


# ---------------------------------------------------------------------------
# Date conversion
# ---------------------------------------------------------------------------


class _ConvertDate(_Tool):
    """Convert a date between Nepali BS and Gregorian AD calendars.

    Arguments:
        date (str): the date string to convert
        from_calendar (str): ``"BS"`` or ``"AD"``
        to_calendar (str): ``"AD"`` or ``"BS"``
    """

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        base = jawafdehi_api_base_url().rstrip("/")
        payload = await _post_json(f"{base}/api/utils/convert-date/", data=arguments)
        return _json_text(payload)


# ---------------------------------------------------------------------------
# TOOL_MAP – the public interface consumed by MCPToolAdapter
# ---------------------------------------------------------------------------

TOOL_MAP: dict[str, _Tool] = {
    "ngm_extract_case_data": _NgmExtractCaseData(),
    "convert_to_markdown": _ConvertToMarkdown(),
    "create_jawafdehi_case": _CreateJawafdehibiCase(),
    "patch_jawafdehi_case": _PatchJawafdehibiCase(),
    "get_jawafdehi_case": _GetJawafdehibiCase(),
    "search_jawafdehi_cases": _SearchJawafdehibiCases(),
    "upload_document_source": _UploadDocumentSource(),
    "search_jawaf_entities": _SearchJawafEntities(),
    "get_jawaf_entity": _GetJawafEntity(),
    "create_jawaf_entity": _CreateJawafEntity(),
    "convert_date": _ConvertDate(),
}
