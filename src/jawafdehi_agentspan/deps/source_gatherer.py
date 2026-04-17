from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from jawafdehi_agentspan.assets import (
    ciaa_ag_index_path,
    ciaa_press_releases_path,
)
from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter
from jawafdehi_agentspan.models import (
    CaseInitialization,
    SourceArtifact,
    SourceBundle,
)
from jawafdehi_agentspan.workspace import (
    ensure_case_store_dirs,
    global_markdown_sources_dir,
    global_raw_sources_dir,
)


class WorkspaceSourceGatherer:
    def __init__(
        self,
        *,
        adapter: MCPToolAdapter,
    ) -> None:
        self.adapter = adapter

    def _base_bundle(self, initialization: CaseInitialization) -> SourceBundle:
        ensure_case_store_dirs(initialization.case_number)
        artifact = SourceArtifact(
            source_type="case_details",
            title="Special Court case details",
            raw_path=initialization.case_details_path,
            markdown_path=initialization.case_details_path,
        )
        return SourceBundle(
            case_number=initialization.case_number,
            workspace=initialization.workspace,
            asset_root=initialization.asset_root,
            case_details_path=initialization.case_details_path,
            source_artifacts=[artifact],
            case_details_artifact=artifact,
        )

    @classmethod
    def _append_artifact(
        cls, bundle: SourceBundle, artifact: SourceArtifact
    ) -> SourceBundle:
        artifacts = list(bundle.source_artifacts)
        if all(
            existing.raw_path != artifact.raw_path
            or existing.markdown_path != artifact.markdown_path
            for existing in artifacts
        ):
            artifacts.append(artifact)
        updates: dict[str, Any] = {"source_artifacts": artifacts}
        if artifact.source_type == "press_release":
            updates["press_release_artifact"] = artifact
        if artifact.source_type == "charge_sheet":
            updates["charge_sheet_artifact"] = artifact
        return bundle.model_copy(update=updates)

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    @staticmethod
    def _extract_primary_defendant(case_details: str) -> str | None:
        match = re.search(r"(?m)^- \*\*(.+?)\*\*", case_details)
        if match:
            return match.group(1).strip()
        return None

    def _find_charge_sheet_row(
        self, initialization: CaseInitialization
    ) -> dict[str, str] | None:
        rows = self._read_csv(ciaa_ag_index_path())
        for row in rows:
            if (
                row.get("case_number") or ""
            ).strip().upper() == initialization.case_number:
                return row
        return None

    def _find_press_release_row(
        self, initialization: CaseInitialization
    ) -> dict[str, str] | None:
        case_details = initialization.case_details_path.read_text(encoding="utf-8")
        primary_defendant = self._extract_primary_defendant(case_details)
        charge_sheet_row = self._find_charge_sheet_row(initialization)
        charge_title = (charge_sheet_row or {}).get("title") or ""
        search_terms = [initialization.case_number, charge_title]
        if primary_defendant:
            search_terms.append(primary_defendant)
        normalized_terms = [
            self._normalize_text(term) for term in search_terms if term and term.strip()
        ]
        rows = self._read_csv(ciaa_press_releases_path())
        for row in rows:
            haystacks = [
                self._normalize_text(row.get("title") or ""),
                self._normalize_text(row.get("full_text") or ""),
            ]
            if any(
                term and any(term in haystack for haystack in haystacks)
                for term in normalized_terms
            ):
                return row
        return None

    async def gather_sources(self, initialization: CaseInitialization) -> SourceBundle:
        """Look up source URLs from CSV indexes and return a bundle with expected paths.

        Files are NOT downloaded here. The prepare-information agent downloads them.
        """
        bundle = self._base_bundle(initialization)

        press_row = self._find_press_release_row(initialization)
        if press_row is not None:
            press_id = (
                press_row.get("press_id") or initialization.case_number.lower()
            ).strip()
            press_url = (press_row.get("source_url") or "").strip()
            if press_url:
                raw_path = (
                    global_raw_sources_dir(initialization.case_number)
                    / f"ciaa-press-release-{press_id}.html"
                )
                markdown_path = (
                    global_markdown_sources_dir(initialization.case_number)
                    / f"ciaa-press-release-{press_id}.md"
                )
                artifact = SourceArtifact(
                    source_type="press_release",
                    title=(
                        press_row.get("title") or initialization.case_number
                    ).strip(),
                    raw_path=raw_path,
                    markdown_path=markdown_path,
                    source_url=press_url,
                    identifier=press_id,
                    publication_date=(press_row.get("publication_date") or "").strip()
                    or None,
                )
                bundle = self._append_artifact(bundle, artifact)

        charge_row = self._find_charge_sheet_row(initialization)
        if charge_row is None:
            raise RuntimeError(
                f"No AG charge sheet row found for case {initialization.case_number}"
            )
        pdf_url = (charge_row.get("pdf_url") or "").strip()
        if not pdf_url:
            raise RuntimeError(
                f"AG index row for {initialization.case_number} is missing pdf_url"
            )
        raw_path = (
            global_raw_sources_dir(initialization.case_number)
            / f"charge-sheet-{initialization.case_number}.pdf"
        )
        markdown_path = (
            global_markdown_sources_dir(initialization.case_number)
            / f"charge-sheet-{initialization.case_number}.md"
        )
        artifact = SourceArtifact(
            source_type="charge_sheet",
            title=(charge_row.get("title") or initialization.case_number).strip(),
            raw_path=raw_path,
            markdown_path=markdown_path,
            source_url=pdf_url,
            identifier=initialization.case_number,
            publication_date=(charge_row.get("filing_date") or "").strip() or None,
        )
        bundle = self._append_artifact(bundle, artifact)
        return bundle
