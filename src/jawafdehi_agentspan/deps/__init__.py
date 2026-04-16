from __future__ import annotations

from jawafdehi_agentspan.deps.container import (
    WorkflowDependencies,
    build_default_dependencies,
    get_dependencies,
    use_dependencies,
)
from jawafdehi_agentspan.deps.fetcher import BraveSearchClient, RemoteDocumentFetcher
from jawafdehi_agentspan.deps.news_gatherer import SearchBackedNewsGatherer
from jawafdehi_agentspan.deps.publish_finalizer import MCPPublishFinalizer
from jawafdehi_agentspan.deps.source_gatherer import WorkspaceSourceGatherer
from jawafdehi_agentspan.deps.utils import (
    ensure_within_workspace,
    ensure_within_workspace_or_assets,
    render_review_markdown,
)

__all__ = [
    "BraveSearchClient",
    "MCPPublishFinalizer",
    "RemoteDocumentFetcher",
    "SearchBackedNewsGatherer",
    "WorkflowDependencies",
    "WorkspaceSourceGatherer",
    "build_default_dependencies",
    "ensure_within_workspace",
    "ensure_within_workspace_or_assets",
    "get_dependencies",
    "render_review_markdown",
    "use_dependencies",
]
