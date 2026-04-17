from __future__ import annotations

from pathlib import Path

from jawafdehi_agentspan.dependencies import SearchBackedNewsGatherer
from jawafdehi_agentspan.models import (
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


class RecordingAdapter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def convert_to_markdown(self, arguments):
        self.calls.append(arguments)
        output_path = Path(arguments["output_path"])
        output_path.write_text("# News Article\n", encoding="utf-8")
        return str(output_path)


class RecordingSearchClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(self, query: str, *, count: int = 10):
        self.queries.append(query)
        slug = len(self.queries)
        return [
            {
                "url": f"https://example.com/news-{slug}",
                "title": f"News Result {slug}",
                "description": "Example",
            }
        ]


class RecordingFetcher:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []

    async def download(self, url: str, output_path: Path) -> Path:
        self.downloads.append((url, output_path))
        output_path.write_text("<html>news</html>", encoding="utf-8")
        return output_path


def _workspace(tmp_path: Path) -> WorkspaceContext:
    root = tmp_path / "run"
    logs_dir = root / "logs"
    data_dir = root / "data"
    memory_file = root / "MEMORY.md"
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
    case_details_path = workspace.data_dir / "case_details-081-CR-0123.md"
    case_details_path.write_text("# Case Details\n", encoding="utf-8")
    raw_path = (
        tmp_path
        / "global_store"
        / "cases"
        / "081-CR-0123"
        / "sources"
        / "raw"
        / "charge-sheet.pdf"
    )
    markdown_path = (
        tmp_path
        / "global_store"
        / "cases"
        / "081-CR-0123"
        / "sources"
        / "markdown"
        / "charge-sheet.md"
    )
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("pdf", encoding="utf-8")
    markdown_path.write_text("# Charge Sheet\n", encoding="utf-8")

    bundle = SourceBundle(
        case_number="081-CR-0123",
        workspace=workspace,
        asset_root=workspace.root_dir,
        case_details_path=case_details_path,
        source_artifacts=[
            SourceArtifact(
                source_type="charge_sheet",
                title="Charge Sheet",
                raw_path=raw_path,
                markdown_path=markdown_path,
            )
        ],
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


async def test_news_gatherer_uses_press_release_text_for_dynamic_queries(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        "jawafdehi_agentspan.deps.news_gatherer.get_settings",
        lambda: Settings(
            JAWAFDEHI_API_TOKEN="test-token",
            OPENAI_API_KEY="test-openai-key",
            BRAVE_SEARCH_API_KEY="brave-test-key",
        ),
    )

    workspace = _workspace(tmp_path)
    case_details_path = workspace.data_dir / "case_details-081-CR-0123.md"
    case_details_path.write_text("# Case Details\n", encoding="utf-8")

    charge_raw = (
        tmp_path
        / "global_store"
        / "cases"
        / "081-CR-0123"
        / "sources"
        / "raw"
        / "charge-sheet.pdf"
    )
    charge_md = (
        tmp_path
        / "global_store"
        / "cases"
        / "081-CR-0123"
        / "sources"
        / "markdown"
        / "charge-sheet.md"
    )
    charge_raw.parent.mkdir(parents=True, exist_ok=True)
    charge_md.parent.mkdir(parents=True, exist_ok=True)
    charge_raw.write_text("pdf", encoding="utf-8")
    charge_md.write_text("# Charge Sheet\n", encoding="utf-8")

    press_raw = (
        tmp_path
        / "global_store"
        / "cases"
        / "081-CR-0123"
        / "sources"
        / "raw"
        / "press-release.html"
    )
    press_md = (
        tmp_path
        / "global_store"
        / "cases"
        / "081-CR-0123"
        / "sources"
        / "markdown"
        / "press-release.md"
    )
    press_raw.parent.mkdir(parents=True, exist_ok=True)
    press_md.parent.mkdir(parents=True, exist_ok=True)
    press_raw.write_text("<html>press</html>", encoding="utf-8")
    press_md.write_text(
        "# प्रेस विज्ञप्ति\n\n"
        "अख्तियार दुरुपयोग अनुसन्धान आयोगले राम बहादुर कार्की सहितका व्यक्तिहरूविरुद्ध "
        "भ्रष्टाचार मुद्दा दायर गरेको जनाएको छ।\n\n"
        "कमिशनको दाबी अनुसार नक्कली बिल, सार्वजनिक खरिद अनियमितता, र राजस्व हिनामिना भएको थियो।\n",
        encoding="utf-8",
    )

    bundle = SourceBundle(
        case_number="081-CR-0123",
        workspace=workspace,
        asset_root=workspace.root_dir,
        case_details_path=case_details_path,
        source_artifacts=[
            SourceArtifact(
                source_type="charge_sheet",
                title="Charge Sheet Title",
                raw_path=charge_raw,
                markdown_path=charge_md,
            ),
            SourceArtifact(
                source_type="press_release",
                title="CIAA filed corruption case against Ram Bahadur Karki",
                raw_path=press_raw,
                markdown_path=press_md,
            ),
        ],
        charge_sheet_artifact=SourceArtifact(
            source_type="charge_sheet",
            title="Charge Sheet Title",
            raw_path=charge_raw,
            markdown_path=charge_md,
        ),
        press_release_artifact=SourceArtifact(
            source_type="press_release",
            title="CIAA filed corruption case against Ram Bahadur Karki",
            raw_path=press_raw,
            markdown_path=press_md,
        ),
    )

    adapter = RecordingAdapter()
    search_client = RecordingSearchClient()
    fetcher = RecordingFetcher()
    gatherer = SearchBackedNewsGatherer(
        adapter=adapter,
        search_client=search_client,
        fetcher=fetcher,
        article_limit=3,
    )

    updated = await gatherer.gather_news(bundle)

    assert len(search_client.queries) == 4
    assert search_client.queries[0] == "081-CR-0123"
    assert "Ram Bahadur Karki" in search_client.queries[1]
    assert any(
        "नक्कली बिल" in query or "सार्वजनिक खरिद" in query
        for query in search_client.queries[1:]
    )
    assert len(updated.news_artifacts) == 3
    assert len(fetcher.downloads) == 3
    assert len(adapter.calls) == 3
