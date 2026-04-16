from __future__ import annotations

import asyncio
import csv
import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

import httpx

from jawafdehi_agentspan.assets import (
    ciaa_ag_index_path,
    ciaa_press_releases_path,
    ciaa_workflow_root,
)
from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter
from jawafdehi_agentspan.models import (
    CaseInitialization,
    PublishedCaseResult,
    PublishInput,
    SourceArtifact,
    SourceBundle,
)
from jawafdehi_agentspan.settings import get_settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


class NGMClient(Protocol):
    async def fetch_case_details(self, case_number: str, output_path: Path) -> str: ...


class SourceGatherer(Protocol):
    async def gather_sources(
        self, initialization: CaseInitialization
    ) -> SourceBundle: ...


class NewsGatherer(Protocol):
    async def gather_news(self, source_bundle: SourceBundle) -> SourceBundle: ...


class PublishFinalizer(Protocol):
    async def publish_and_finalize(
        self, publish_input: PublishInput
    ) -> PublishedCaseResult: ...


class MCPNGMClient:
    def __init__(
        self, adapter: MCPToolAdapter, court_identifier: str = "special"
    ) -> None:
        self.adapter = adapter
        self.court_identifier = court_identifier

    async def fetch_case_details(
        self,
        case_number: str,
        output_path: Path,
        *,
        max_retries: int = 4,
        base_delay: float = 5.0,
    ) -> str:
        args = {
            "court_identifier": self.court_identifier,
            "case_number": case_number,
            "file_path": str(output_path),
        }
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                await self.adapter.ngm_extract_case_data(args)
                return output_path.read_text(encoding="utf-8")
            except RuntimeError as exc:
                last_exc = exc
                msg = str(exc).lower()
                if "429" in msg or "too many requests" in msg or "rate" in msg:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "NGM API rate-limited (attempt %d/%d), retrying in %.0fs: %s",
                        attempt + 1,
                        max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        raise RuntimeError(
            f"NGM fetch failed after {max_retries} attempts: {last_exc}"
        ) from last_exc


class RemoteDocumentFetcher:
    def __init__(self, *, timeout: float = 60.0) -> None:
        self.timeout = timeout

    @staticmethod
    def guess_extension(url: str, content_type: str | None) -> str:
        normalized = url.lower().split("?")[0]
        for extension in (
            ".pdf",
            ".docx",
            ".doc",
            ".html",
            ".htm",
            ".txt",
            ".jpg",
            ".jpeg",
        ):
            if normalized.endswith(extension):
                return extension
        if content_type:
            lowered = content_type.lower()
            if "pdf" in lowered:
                return ".pdf"
            if "wordprocessingml" in lowered:
                return ".docx"
            if "msword" in lowered:
                return ".doc"
            if "html" in lowered:
                return ".html"
            if "jpeg" in lowered:
                return ".jpg"
            if "text/plain" in lowered:
                return ".txt"
        return ".bin"

    async def download(self, url: str, output_path: Path) -> Path:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout
        ) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path

    async def download_with_detected_extension(
        self, url: str, output_stem: Path
    ) -> Path:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout
        ) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        extension = self.guess_extension(url, response.headers.get("content-type"))
        output_path = output_stem.with_suffix(extension)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path

    async def fetch_text(self, url: str) -> str:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout
        ) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.text


class BraveSearchClient:
    def __init__(self, *, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def search(self, query: str, *, count: int = 10) -> list[dict[str, str]]:
        settings = get_settings()
        if not settings.brave_search_api_key:
            raise RuntimeError("BRAVE_SEARCH_API_KEY is required for Brave search.")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": count},
                headers={
                    "X-Subscription-Token": settings.brave_search_api_key,
                    "Accept": "application/json",
                },
            )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("web", {}).get("results", [])
        normalized: list[dict[str, str]] = []
        for result in results:
            url = (result.get("url") or "").strip()
            title = (result.get("title") or "").strip()
            if not url or not title:
                continue
            normalized.append(
                {
                    "url": url,
                    "title": title,
                    "description": (result.get("description") or "").strip(),
                }
            )
        return normalized


class WorkspaceSourceGatherer:
    def __init__(
        self,
        *,
        adapter: MCPToolAdapter,
        fetcher: RemoteDocumentFetcher | None = None,
    ) -> None:
        self.adapter = adapter
        self.fetcher = fetcher or RemoteDocumentFetcher()

    def _base_bundle(self, initialization: CaseInitialization) -> SourceBundle:
        raw_case_details_path = (
            initialization.workspace.sources_raw_dir / "special-court-case-details.txt"
        )
        markdown_case_details_path = (
            initialization.workspace.sources_markdown_dir
            / "special-court-case-details.md"
        )
        case_details = initialization.case_details_path.read_text(encoding="utf-8")
        raw_case_details_path.write_text(case_details, encoding="utf-8")
        markdown_case_details_path.write_text(case_details, encoding="utf-8")
        return SourceBundle(
            case_number=initialization.case_number,
            workspace=initialization.workspace,
            asset_root=initialization.asset_root,
            case_details_path=initialization.case_details_path,
            raw_sources=[raw_case_details_path],
            markdown_sources=[markdown_case_details_path],
            case_details_artifact=SourceArtifact(
                source_type="case_details",
                title="Special Court case details",
                raw_path=raw_case_details_path,
                markdown_path=markdown_case_details_path,
            ),
        )

    @staticmethod
    def _append_artifact(
        bundle: SourceBundle, artifact: SourceArtifact
    ) -> SourceBundle:
        raw_sources = list(bundle.raw_sources)
        markdown_sources = list(bundle.markdown_sources)
        if artifact.raw_path not in raw_sources:
            raw_sources.append(artifact.raw_path)
        if artifact.markdown_path not in markdown_sources:
            markdown_sources.append(artifact.markdown_path)
        updates: dict[str, Any] = {
            "raw_sources": raw_sources,
            "markdown_sources": markdown_sources,
        }
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

    async def _convert_to_markdown(self, raw_path: Path, markdown_path: Path) -> None:
        await self.adapter.convert_to_markdown(
            {"file_path": str(raw_path), "output_path": str(markdown_path)}
        )

    async def gather_sources(self, initialization: CaseInitialization) -> SourceBundle:
        bundle = self._base_bundle(initialization)

        press_row = self._find_press_release_row(initialization)
        if press_row is not None:
            press_id = (
                press_row.get("press_id") or initialization.case_number.lower()
            ).strip()
            press_url = (press_row.get("source_url") or "").strip()
            if press_url:
                raw_path = (
                    initialization.workspace.sources_raw_dir
                    / f"ciaa-press-release-{press_id}.html"
                )
                markdown_path = (
                    initialization.workspace.sources_markdown_dir
                    / f"ciaa-press-release-{press_id}.md"
                )
                await self.fetcher.download(press_url, raw_path)
                await self._convert_to_markdown(raw_path, markdown_path)
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
        raw_path = await self.fetcher.download_with_detected_extension(
            pdf_url,
            initialization.workspace.sources_raw_dir
            / f"charge-sheet-{initialization.case_number}",
        )
        markdown_path = (
            initialization.workspace.sources_markdown_dir
            / f"charge-sheet-{initialization.case_number}.md"
        )
        await self._convert_to_markdown(raw_path, markdown_path)
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


class SearchBackedNewsGatherer:
    def __init__(
        self,
        *,
        adapter: MCPToolAdapter,
        search_client: BraveSearchClient,
        fetcher: RemoteDocumentFetcher,
        article_limit: int,
    ) -> None:
        self.adapter = adapter
        self.search_client = search_client
        self.fetcher = fetcher
        self.article_limit = article_limit

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "news"

    async def gather_news(self, source_bundle: SourceBundle) -> SourceBundle:
        if not get_settings().brave_search_api_key:
            logger.warning(
                "BRAVE_SEARCH_API_KEY is not configured; "
                "skipping news gathering for %s",
                source_bundle.case_number,
            )
            return source_bundle

        hints: list[str] = [source_bundle.case_number]
        if source_bundle.press_release_artifact is not None:
            hints.append(source_bundle.press_release_artifact.title)
        if source_bundle.charge_sheet_artifact is not None:
            hints.append(source_bundle.charge_sheet_artifact.title)

        queries = list(dict.fromkeys(hints))[:4]
        results = await asyncio.gather(
            *[self.search_client.search(query, count=8) for query in queries]
        )
        candidates: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for query_results in results:
            for result in query_results:
                if result["url"] in seen_urls:
                    continue
                seen_urls.add(result["url"])
                candidates.append(result)
        candidates = candidates[: self.article_limit]

        bundle = source_bundle
        for index, result in enumerate(candidates, start=1):
            slug = self._slugify(result["title"])
            raw_path = (
                bundle.workspace.sources_raw_dir / f"news-{index:02d}-{slug}.html"
            )
            markdown_path = (
                bundle.workspace.sources_markdown_dir / f"news-{index:02d}-{slug}.md"
            )
            await self.fetcher.download(result["url"], raw_path)
            await self.adapter.convert_to_markdown(
                {"file_path": str(raw_path), "output_path": str(markdown_path)}
            )
            artifact = SourceArtifact(
                source_type="news",
                title=result["title"],
                raw_path=raw_path,
                markdown_path=markdown_path,
                source_url=result["url"],
                external_url=result["url"],
                identifier=f"{index:02d}-{slug}",
            )
            bundle = bundle.model_copy(
                update={
                    "raw_sources": [*bundle.raw_sources, raw_path],
                    "markdown_sources": [*bundle.markdown_sources, markdown_path],
                    "news_artifacts": [*bundle.news_artifacts, artifact],
                }
            )
        return bundle


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
        for raw_source in publish_input.source_bundle.raw_sources:
            title = raw_source.stem.replace("-", " ").title()
            source_type = "OFFICIAL_GOVERNMENT"
            if "charge-sheet" in raw_source.name:
                source_type = "LEGAL_PROCEDURAL"
            elif "court-order" in raw_source.name:
                source_type = "LEGAL_COURT_ORDER"
            payload = await self.adapter.upload_document_source(
                {
                    "title": title,
                    "description": f"{publish_input.case_number} source document",
                    "file_path": str(raw_source),
                    "source_type": source_type,
                }
            )
            uploaded.append(
                {
                    "source_id": str(
                        payload["source_id"]
                        if "source_id" in payload
                        else payload["id"]
                    )
                }
            )
        for artifact in publish_input.source_bundle.news_artifacts:
            arguments = {
                "title": artifact.title,
                "description": f"{publish_input.case_number} news coverage",
                "file_path": str(artifact.markdown_path),
                "source_type": "MEDIA_NEWS",
                "url": [artifact.external_url] if artifact.external_url else [],
            }
            if artifact.publication_date:
                arguments["publication_date"] = artifact.publication_date
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
        draft_text = publish_input.refinement_result.draft_path.read_text(
            encoding="utf-8"
        )
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
                        "description": f"{publish_input.case_number} supporting source",
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
                {"op": "replace", "path": "/key_allegations", "value": key_allegations},
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


class WorkflowDependencies:
    def __init__(
        self,
        *,
        adapter: MCPToolAdapter,
        ngm_client: NGMClient,
        source_gatherer: SourceGatherer,
        news_gatherer: NewsGatherer,
        publish_finalizer: PublishFinalizer,
        fetcher: RemoteDocumentFetcher,
        search_client: BraveSearchClient,
    ) -> None:
        self.adapter = adapter
        self.ngm_client = ngm_client
        self.source_gatherer = source_gatherer
        self.news_gatherer = news_gatherer
        self.publish_finalizer = publish_finalizer
        self.fetcher = fetcher
        self.search_client = search_client


def build_default_dependencies() -> WorkflowDependencies:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for live AgentSpan drafting.")
    adapter = MCPToolAdapter()
    fetcher = RemoteDocumentFetcher()
    search_client = BraveSearchClient()
    return WorkflowDependencies(
        adapter=adapter,
        ngm_client=MCPNGMClient(adapter),
        source_gatherer=WorkspaceSourceGatherer(adapter=adapter, fetcher=fetcher),
        news_gatherer=SearchBackedNewsGatherer(
            adapter=adapter,
            search_client=search_client,
            fetcher=fetcher,
            article_limit=settings.news_article_limit,
        ),
        publish_finalizer=MCPPublishFinalizer(adapter),
        fetcher=fetcher,
        search_client=search_client,
    )


_CURRENT_DEPENDENCIES: WorkflowDependencies | None = None


def get_dependencies() -> WorkflowDependencies:
    global _CURRENT_DEPENDENCIES
    if _CURRENT_DEPENDENCIES is None:
        _CURRENT_DEPENDENCIES = build_default_dependencies()
    return _CURRENT_DEPENDENCIES


@contextmanager
def use_dependencies(dependencies: WorkflowDependencies):
    global _CURRENT_DEPENDENCIES
    previous = _CURRENT_DEPENDENCIES
    _CURRENT_DEPENDENCIES = dependencies
    try:
        yield
    finally:
        _CURRENT_DEPENDENCIES = previous


def ensure_within_workspace(workspace_root: Path, path: Path) -> None:
    resolved_root = workspace_root.resolve()
    resolved_path = path.resolve()
    resolved_path.relative_to(resolved_root)


def ensure_within_workspace_or_assets(path: Path) -> None:
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(ciaa_workflow_root().resolve())
        return
    except ValueError as err:
        raise RuntimeError(f"Path is outside the allowed asset root: {path}") from err


def render_review_markdown(critique: Any) -> str:
    strengths = "\n".join(f"- {item}" for item in critique.strengths) or "- None"
    improvements = "\n".join(f"- {item}" for item in critique.improvements) or "- None"
    blockers = "\n".join(f"- {item}" for item in critique.blockers) or "- None"
    return (
        "# Draft Review\n\n"
        "## Overall Outcome\n\n"
        f"**`{critique.outcome.value}`**\n\n"
        f"## Score\n\n{critique.score}\n\n"
        "## Strengths\n\n"
        f"{strengths}\n\n"
        "## Improvements\n\n"
        f"{improvements}\n\n"
        "## Blockers\n\n"
        f"{blockers}\n"
    )
