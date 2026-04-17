"""Re-export shim — implementation lives in jawafdehi_agentspan.deps."""

from __future__ import annotations

from jawafdehi_agentspan.deps import (
    BraveSearchClient,
    MCPPublishFinalizer,
    RemoteDocumentFetcher,
    SearchBackedNewsGatherer,
    WorkflowDependencies,
    WorkspaceSourceGatherer,
    build_default_dependencies,
    ensure_within_global_store,
    ensure_within_workspace,
    ensure_within_workspace_or_assets,
    get_dependencies,
    render_review_markdown,
    use_dependencies,
)

__all__ = [
    "BraveSearchClient",
    "ensure_within_global_store",
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
