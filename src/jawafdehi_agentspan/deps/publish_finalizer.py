from __future__ import annotations

import re
from typing import Any

from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter
from jawafdehi_agentspan.models import (
    PublishedCaseResult,
    PublishInput,
)


class MCPPublishFinalizer:
    def __init__(self, adapter: MCPToolAdapter) -> None:
        self.adapter = adapter

    @staticmethod
    def _extract_markdown_section(document: str, heading: str) -> str:
        match = re.search(
            rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", document
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_bullets(section_body: str) -> list[str]:
        return [
            line[2:].strip()
            for line in section_body.splitlines()
            if line.strip().startswith("- ") and line[2:].strip()
        ]

    @staticmethod
    def _extract_entities(case_details: str) -> list[dict[str, str | None]]:
        entities: list[dict[str, str | None]] = []
        pattern = re.compile(r"^- \*\*(?P<name>.+?)\*\*(?P<tail>.*)$", re.MULTILINE)
        for match in pattern.finditer(case_details):
            name = match.group("name").strip()
            tail = match.group("tail")
            nes_match = re.search(r"NES ID:\s*([^)]+)", tail)
            entities.append(
                {
                    "display_name": name,
                    "nes_id": nes_match.group(1).strip() if nes_match else None,
                }
            )
        return entities

    async def _find_existing_case_id(self, case_number: str) -> int | None:
        payload = await self.adapter.search_jawafdehi_cases(
            {"search": case_number, "case_type": "CORRUPTION"}
        )
        results = (
            payload.get("results") or payload.get("data") or payload.get("items") or []
        )
        target = f"special:{case_number}"
        for result in results:
            if target in (result.get("court_cases") or []):
                return int(result["id"])
        return None

    async def _get_or_create_entity_id(self, entity: dict[str, str | None]) -> int:
        display_name = entity["display_name"] or ""
        search_payload = await self.adapter.search_jawaf_entities(
            {"search": display_name}
        )
        for result in search_payload.get("results", []):
            if (
                result.get("display_name") or ""
            ).strip().lower() == display_name.lower():
                return int(result["id"])
        create_args = {"display_name": display_name}
        if entity.get("nes_id"):
            create_args["nes_id"] = entity["nes_id"]
        created = await self.adapter.create_jawaf_entity(create_args)
        return int(created["id"])

    async def _upload_sources(
        self, publish_input: PublishInput
    ) -> list[dict[str, str]]:
        uploaded: list[dict[str, str]] = []
        for source in publish_input.source_bundle.source_artifacts:
            source_type = "OFFICIAL_GOVERNMENT"
            file_path = source.raw_path
            if source.source_type == "charge_sheet":
                source_type = "LEGAL_PROCEDURAL"
            elif source.source_type == "news":
                source_type = "MEDIA_NEWS"
                file_path = source.markdown_path
            arguments = {
                "title": source.title,
                "description": f"{publish_input.case_number} source document",
                "file_path": str(file_path),
                "source_type": source_type,
            }
            if source.external_url:
                arguments["url"] = [source.external_url]
            if source.publication_date:
                arguments["publication_date"] = source.publication_date
            payload = await self.adapter.upload_document_source(arguments)
            uploaded.append(
                {
                    "source_id": str(
                        payload["source_id"]
                        if "source_id" in payload
                        else payload["id"]
                    )
                }
            )
        return uploaded

    async def publish_and_finalize(
        self, publish_input: PublishInput
    ) -> PublishedCaseResult:
        draft_text = publish_input.draft_path.read_text(encoding="utf-8")
        case_details = publish_input.source_bundle.case_details_path.read_text(
            encoding="utf-8"
        )
        title = self._extract_markdown_section(draft_text, "Title") or (
            f"Special Court corruption case {publish_input.case_number}"
        )
        payload = {
            "title": title,
            "case_type": "CORRUPTION",
            "short_description": self._extract_markdown_section(
                draft_text, "Short Description"
            ),
            "description": self._extract_markdown_section(draft_text, "Description"),
        }
        case_id = await self._find_existing_case_id(publish_input.case_number)
        updated_fields = sorted(payload.keys())
        if case_id is None:
            created = await self.adapter.create_jawafdehi_case(payload)
            case_id = int(created["id"])
        else:
            operations = [
                {"op": "replace", "path": f"/{field}", "value": value}
                for field, value in payload.items()
                if field != "case_type"
            ]
            await self.adapter.patch_jawafdehi_case(
                {"case_id": case_id, "operations": operations}
            )
            updated_fields = [
                operation["path"].removeprefix("/") for operation in operations
            ]

        entity_ids: list[int] = []
        entities = self._extract_entities(case_details)
        if entities:
            patch_ops: list[dict[str, Any]] = []
            for entity in entities:
                entity_id = await self._get_or_create_entity_id(entity)
                entity_ids.append(entity_id)
                patch_ops.append(
                    {
                        "op": "add",
                        "path": "/entities/-",
                        "value": {
                            "entity": entity_id,
                            "relationship_type": "accused",
                            "notes": "Auto-linked by jawafdehi-agentspan",
                        },
                    }
                )
            if patch_ops:
                await self.adapter.patch_jawafdehi_case(
                    {"case_id": case_id, "operations": patch_ops}
                )

        uploaded = await self._upload_sources(publish_input)
        if uploaded:
            evidence_ops = [
                {
                    "op": "add",
                    "path": "/evidence/-",
                    "value": {
                        "source_id": item["source_id"],
                        "description": (
                            f"{publish_input.case_number} supporting source"
                        ),
                    },
                }
                for item in uploaded
            ]
            await self.adapter.patch_jawafdehi_case(
                {"case_id": case_id, "patches": evidence_ops}
            )

        draft_patch_ops: list[dict[str, Any]] = []
        key_allegations = self._extract_bullets(
            self._extract_markdown_section(draft_text, "Key Allegations")
        )
        timeline_lines = self._extract_bullets(
            self._extract_markdown_section(draft_text, "Timeline")
        )
        draft_patch_ops.extend(
            [
                {
                    "op": "replace",
                    "path": "/key_allegations",
                    "value": key_allegations,
                },
                {
                    "op": "replace",
                    "path": "/timeline",
                    "value": [
                        {"date": "", "title": line, "description": line}
                        for line in timeline_lines
                    ],
                },
                {
                    "op": "replace",
                    "path": "/court_cases",
                    "value": [f"special:{publish_input.case_number}"],
                },
                {
                    "op": "replace",
                    "path": "/missing_details",
                    "value": self._extract_markdown_section(
                        draft_text, "Missing Details"
                    ),
                },
            ]
        )
        await self.adapter.patch_jawafdehi_case(
            {"case_id": case_id, "patches": draft_patch_ops}
        )
        return PublishedCaseResult(
            case_id=case_id,
            entity_ids=entity_ids,
            source_ids=[item["source_id"] for item in uploaded],
            updated_fields=updated_fields
            + ["key_allegations", "timeline", "court_cases", "missing_details"],
        )
