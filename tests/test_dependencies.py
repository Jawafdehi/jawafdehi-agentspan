from __future__ import annotations

from pathlib import Path

from jawafdehi_agentspan.dependencies import SearchBackedNewsGatherer
from jawafdehi_agentspan.models import (
    DocumentSource,
    DocumentSourceType,
    SourceArtifact,
    SourceBundle,
    WorkspaceContext,
)
from jawafdehi_agentspan.settings import Settings


class UnusedAdapter:
    async def convert_to_markdown(self, arguments):
        raise AssertionError(
            "convert_to_markdown should not be called when Brave is disabled"
        )


class UnusedSearchClient:
    async def search(self, query: str, *, count: int = 10):
        raise AssertionError("search should not be called when Brave is disabled")


class UnusedFetcher:
    async def download(self, url: str, output_path: Path) -> Path:
        raise AssertionError("download should not be called when Brave is disabled")


def _workspace(tmp_path: Path) -> WorkspaceContext:
    root = tmp_path / "run"
    logs_dir = root / "logs"
    data_dir = root / "data"
    memory_file = root / "MEMORY.md"
    (root / "sources" / "raw").mkdir(parents=True)
    (root / "sources" / "markdown").mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    memory_file.write_text("# MEMORY\n", encoding="utf-8")
    return WorkspaceContext(
        root_dir=root,
        logs_dir=logs_dir,
        data_dir=data_dir,
        memory_file=memory_file,
    )


async def test_news_gatherer_skips_when_brave_key_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "jawafdehi_agentspan.deps.news_gatherer.get_settings",
        lambda: Settings(
            JAWAFDEHI_API_TOKEN="test-token",
            OPENAI_API_KEY="test-openai-key",
        ),
    )

    workspace = _workspace(tmp_path)
    case_details_path = workspace.root_dir / "case_details-081-CR-0123.md"
    case_details_path.write_text("# Case Details\n", encoding="utf-8")
    raw_path = workspace.root_dir / "sources" / "raw" / "charge-sheet.pdf"
    markdown_path = workspace.root_dir / "sources" / "markdown" / "charge-sheet.md"
    raw_path.write_text("pdf", encoding="utf-8")
    markdown_path.write_text("# Charge Sheet\n", encoding="utf-8")

    document_source = DocumentSource(
        name="Charge Sheet",
        type=DocumentSourceType.CHARGE_SHEET,
        raw=raw_path,
        markdown=markdown_path,
    )
    workspace = workspace.model_copy(update={"sources": [document_source]})

    bundle = SourceBundle(
        case_number="081-CR-0123",
        workspace=workspace,
        asset_root=workspace.root_dir,
        case_details_path=case_details_path,
        charge_sheet_artifact=SourceArtifact(
            source_type="charge_sheet",
            title="Charge Sheet",
            raw_path=raw_path,
            markdown_path=markdown_path,
        ),
    )
    gatherer = SearchBackedNewsGatherer(
        adapter=UnusedAdapter(),
        search_client=UnusedSearchClient(),
        fetcher=UnusedFetcher(),
        article_limit=6,
    )

    updated = await gatherer.gather_news(bundle)

    assert updated == bundle
