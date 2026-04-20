from __future__ import annotations

from contextlib import contextmanager

from jawafdehi_agentspan.deps.fetcher import BraveSearchClient, RemoteDocumentFetcher
from jawafdehi_agentspan.deps.news_gatherer import SearchBackedNewsGatherer
from jawafdehi_agentspan.deps.publish_finalizer import MCPPublishFinalizer
from jawafdehi_agentspan.deps.source_gatherer import WorkspaceSourceGatherer
from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter
from jawafdehi_agentspan.settings import Settings, get_settings


class WorkflowDependencies:
    def __init__(
        self,
        *,
        adapter: MCPToolAdapter,
        source_gatherer: WorkspaceSourceGatherer,
        news_gatherer: SearchBackedNewsGatherer,
        publish_finalizer: MCPPublishFinalizer,
        fetcher: RemoteDocumentFetcher,
        search_client: BraveSearchClient,
    ) -> None:
        self.adapter = adapter
        self.source_gatherer = source_gatherer
        self.news_gatherer = news_gatherer
        self.publish_finalizer = publish_finalizer
        self.fetcher = fetcher
        self.search_client = search_client


def build_default_dependencies(
    settings: Settings | None = None,
) -> WorkflowDependencies:
    settings = settings or get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for live AgentSpan drafting.")
    adapter = MCPToolAdapter()
    fetcher = RemoteDocumentFetcher()
    search_client = BraveSearchClient()
    return WorkflowDependencies(
        adapter=adapter,
        source_gatherer=WorkspaceSourceGatherer(adapter=adapter),
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
