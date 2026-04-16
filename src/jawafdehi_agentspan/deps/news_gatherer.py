from __future__ import annotations

import asyncio
import logging
import re

from jawafdehi_agentspan.deps.fetcher import BraveSearchClient, RemoteDocumentFetcher
from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter
from jawafdehi_agentspan.models import SourceArtifact, SourceBundle
from jawafdehi_agentspan.settings import get_settings
from jawafdehi_agentspan.workspace import markdown_sources_dir, raw_sources_dir

logger = logging.getLogger(__name__)


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
            raw_path = raw_sources_dir(bundle.workspace.root_dir) / (
                f"news-{index:02d}-{slug}.html"
            )
            markdown_path = markdown_sources_dir(bundle.workspace.root_dir) / (
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
                update={"news_artifacts": [*bundle.news_artifacts, artifact]}
            )
        return bundle
