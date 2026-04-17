from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterable

from jawafdehi_agentspan.deps.fetcher import BraveSearchClient, RemoteDocumentFetcher
from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter
from jawafdehi_agentspan.models import SourceArtifact, SourceBundle
from jawafdehi_agentspan.settings import get_settings
from jawafdehi_agentspan.workspace import (
    ensure_case_store_dirs,
    global_news_markdown_dir,
    global_news_raw_dir,
)

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
    "विरुद्ध",
    "को",
    "का",
    "की",
    "ले",
    "मा",
    "र",
    "सहित",
    "सम्बन्धी",
}


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

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _extract_press_release_text(cls, source_bundle: SourceBundle) -> str:
        artifact = source_bundle.press_release_artifact
        if artifact is None or not artifact.markdown_path.is_file():
            return ""
        return cls._normalize_whitespace(
            artifact.markdown_path.read_text(encoding="utf-8")
        )

    @classmethod
    def _extract_candidate_phrases(cls, text: str) -> list[str]:
        phrases: list[str] = []
        for chunk in re.split(r"[\n\r.!?।:;•\-]+", text):
            normalized = cls._normalize_whitespace(chunk)
            if len(normalized) < 12:
                continue
            if normalized.startswith("#"):
                normalized = normalized.lstrip("# ")
            phrases.append(normalized)
        return phrases

    @classmethod
    def _select_press_release_queries(
        cls,
        case_number: str,
        press_release_title: str | None,
        press_release_text: str,
        charge_sheet_title: str | None,
    ) -> list[str]:
        queries: list[str] = [case_number]
        if press_release_title:
            queries.append(
                f'{case_number} "{cls._normalize_whitespace(press_release_title)}"'
            )

        phrases = cls._extract_candidate_phrases(press_release_text)
        for phrase in phrases:
            words = [
                word
                for word in re.split(r"\s+", phrase)
                if word and word.lower() not in _STOPWORDS
            ]
            if len(words) < 3:
                continue
            selected = " ".join(words[:8])
            queries.append(f'{case_number} "{selected}"')
            if len(queries) >= 4:
                break

        if len(queries) < 4 and charge_sheet_title:
            queries.append(
                f'{case_number} "{cls._normalize_whitespace(charge_sheet_title)}"'
            )

        deduped: list[str] = []
        seen: set[str] = set()
        for query in queries:
            normalized = cls._normalize_whitespace(query)
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(normalized)
        return deduped[:4]

    @staticmethod
    def _dedupe_candidates(
        query_results: Iterable[list[dict[str, str]]],
    ) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for results in query_results:
            for result in results:
                url = result["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append(result)
        return candidates

    async def gather_news(self, source_bundle: SourceBundle) -> SourceBundle:
        if not get_settings().brave_search_api_key:
            logger.warning(
                "BRAVE_SEARCH_API_KEY is not configured; "
                "skipping news gathering for %s",
                source_bundle.case_number,
            )
            return source_bundle

        press_release_text = self._extract_press_release_text(source_bundle)
        queries = self._select_press_release_queries(
            source_bundle.case_number,
            (
                source_bundle.press_release_artifact.title
                if source_bundle.press_release_artifact is not None
                else None
            ),
            press_release_text,
            (
                source_bundle.charge_sheet_artifact.title
                if source_bundle.charge_sheet_artifact is not None
                else None
            ),
        )
        logger.info(
            "[%s] gather_news: generated %d dynamic queries from press release context",
            source_bundle.case_number,
            len(queries),
        )
        results = await asyncio.gather(
            *[self.search_client.search(query, count=8) for query in queries]
        )
        candidates = self._dedupe_candidates(results)[: self.article_limit]

        bundle = source_bundle
        ensure_case_store_dirs(bundle.case_number)
        for index, result in enumerate(candidates, start=1):
            slug = self._slugify(result["title"])
            raw_path = global_news_raw_dir(bundle.case_number) / (
                f"news-{index:02d}-{slug}.html"
            )
            markdown_path = global_news_markdown_dir(bundle.case_number) / (
                f"news-{index:02d}-{slug}.md"
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
                    "news_artifacts": [*bundle.news_artifacts, artifact],
                    "source_artifacts": [*bundle.source_artifacts, artifact],
                }
            )
        return bundle
