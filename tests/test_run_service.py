from __future__ import annotations

from pathlib import Path

import pytest

from jawafdehi_agentspan.assets import ciaa_workflow_root
from jawafdehi_agentspan.models import (
    CaseInitialization,
    PublishedCaseResult,
    SourceArtifact,
    SourceBundle,
    WorkflowResult,
    WorkspaceContext,
)
from jawafdehi_agentspan.run_service import RunService
from jawafdehi_agentspan.settings import Settings
from jawafdehi_agentspan.workspace import global_raw_sources_dir

_DRAFT_MARKDOWN = (
    "# Jawafdehi Case Draft\n\n"
    "## Title\nu0928u092eu0941u0928u093e u092eu0941u0926u094du0926u093e\n\n"
    "## Short Description\nu091bu094bu091fu094b u0935u093fu0935u0930u0923\n\n"
    "## Key Allegations\n- u0906u0930u094bu092a u0967\n- u0906u0930u094bu092a u0968\n\n"
    "## Timeline\n- 2082-01-01: u0926u0930u094du0924u093e\n\n"
    "## Description\n"
    + ("u0935u093fu0938u094du0924u0943u0924 u0935u093fu0935u0930u0923u0964" * 60)
    + "\n"
)
_REVIEW_MARKDOWN = "## Overall Review\n\nInitial review result\n"


def _workspace(tmp_path: Path) -> WorkspaceContext:
    root = tmp_path / "run"
    logs_dir = root / "logs"
    data_dir = root / "data"
    logs_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    return WorkspaceContext(
        root_dir=root,
        logs_dir=logs_dir,
        data_dir=data_dir,
    )


def _initialization(
    tmp_path: Path, case_number: str = "081-CR-0046"
) -> CaseInitialization:
    workspace = _workspace(tmp_path)
    case_details_path = workspace.data_dir / f"case_details-{case_number}.md"
    case_details_path.write_text(
        "# Case Details\n\n- **Ram Bahadur Karki**\n", encoding="utf-8"
    )

    return CaseInitialization(
        case_number=case_number,
        workspace=workspace,
        asset_root=ciaa_workflow_root(),
        case_details_path=case_details_path,
    )


def _source_bundle(initialization: CaseInitialization) -> SourceBundle:
    raw_path = (
        initialization.workspace.root_dir.parent
        / "global_store"
        / "cases"
        / initialization.case_number
        / "sources"
        / "raw"
        / "charge-sheet.pdf"
    )
    markdown_path = (
        initialization.workspace.root_dir.parent
        / "global_store"
        / "cases"
        / initialization.case_number
        / "sources"
        / "markdown"
        / "charge-sheet.md"
    )
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("raw", encoding="utf-8")
    markdown_path.write_text("# Charge Sheet\n", encoding="utf-8")
    artifact = SourceArtifact(
        source_type="charge_sheet",
        title="Charge Sheet",
        raw_path=raw_path,
        markdown_path=markdown_path,
    )
    return SourceBundle(
        case_number=initialization.case_number,
        workspace=initialization.workspace,
        asset_root=initialization.asset_root,
        case_details_path=initialization.case_details_path,
        source_artifacts=[artifact],
        charge_sheet_artifact=artifact,
    )


class FakeExecutor:
    """Writes draft-final.md to workspace when the case-draft agent runs."""

    def __init__(self, publish_case_id: int = 7) -> None:
        self.publish_case_id = publish_case_id
        self.calls: list[str] = []
        self._workspace_root: Path | None = None
        self._press_release_path: Path | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def run(self, agent, prompt: str, output_type=None):
        self.calls.append(agent.name)
        if agent.name == "orchestrator":
            # Simulate the router dispatching through phases
            if self._press_release_path and not self._press_release_path.is_file():
                self._press_release_path.parent.mkdir(parents=True, exist_ok=True)
                self._press_release_path.write_text("pdf", encoding="utf-8")
            if self._workspace_root is not None:
                (self._workspace_root / "draft-final.md").write_text(
                    _DRAFT_MARKDOWN, encoding="utf-8"
                )
                (self._workspace_root / "draft-review.md").write_text(
                    _REVIEW_MARKDOWN, encoding="utf-8"
                )
        return None


class FailingStagedExecutor(FakeExecutor):
    def run(self, agent, prompt: str, output_type=None):
        if agent.name == "prepare_information":
            self.calls.append(agent.name)
            raise RuntimeError("staged flow failed")
        return super().run(agent, prompt, output_type)


class FakeAdapter:
    async def call_text(self, tool_name: str, arguments: dict) -> str:
        if tool_name == "ngm_extract_case_data":
            output_path = Path(arguments["file_path"])
            content = "# Case Details\n\n- **Ram Bahadur Karki**\n"
            output_path.write_text(content, encoding="utf-8")
            return content
        raise AssertionError(f"Unexpected call_text: {tool_name}")


class FakeSourceGatherer:
    def __init__(self, source_bundle: SourceBundle) -> None:
        self.source_bundle = source_bundle

    async def gather_sources(self, initialization: CaseInitialization) -> SourceBundle:
        return self.source_bundle


class FakeNewsGatherer:
    def __init__(self, source_bundle: SourceBundle) -> None:
        self.source_bundle = source_bundle

    async def gather_news(self, source_bundle: SourceBundle) -> SourceBundle:
        return self.source_bundle


class FakePublishFinalizer:
    def __init__(self, publish_case_id: int) -> None:
        self.publish_case_id = publish_case_id

    async def publish_and_finalize(self, publish_input) -> PublishedCaseResult:
        return PublishedCaseResult(
            case_id=self.publish_case_id,
            entity_ids=[100],
            source_ids=["src-1"],
            updated_fields=["title"],
        )


class FakeDependencies:
    def __init__(self, source_bundle: SourceBundle, publish_case_id: int) -> None:
        self.adapter = FakeAdapter()
        self.source_gatherer = FakeSourceGatherer(source_bundle)
        self.news_gatherer = FakeNewsGatherer(source_bundle)
        self.publish_finalizer = FakePublishFinalizer(publish_case_id)


def _service_with_executor(
    executor: FakeExecutor,
    source_bundle: SourceBundle,
    settings: Settings | None = None,
) -> RunService:
    if settings is None:
        settings = Settings(
            JAWAFDEHI_API_TOKEN="test-token",
            OPENAI_API_KEY="test-key",
        )
    return RunService(
        dependencies=FakeDependencies(source_bundle, executor.publish_case_id),
        executor_factory=lambda: executor,
        settings=settings,
    )


def _case_input(case_number: str):
    return type("CaseInput", (), {"case_number": case_number})()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def _isolated_settings(tmp_path: Path) -> Settings:
    return Settings(
        JAWAFDEHI_API_TOKEN="t",
        OPENAI_API_KEY="k",
        GLOBAL_STORE_ROOT=str(tmp_path / "global_store"),
        RUNS_ROOT=str(tmp_path / "runs"),
    )


def test_router_routes_to_prepare_information_when_no_press_release(tmp_path: Path):
    initialization = _initialization(tmp_path)
    workspace_root = initialization.workspace.root_dir
    settings = _isolated_settings(tmp_path)
    service = RunService(settings=settings)
    router = service._make_router(
        case_number=initialization.case_number,
        workspace_root=workspace_root,
    )
    assert router("anything") == "prepare_information"


def test_router_routes_to_case_draft_when_press_release_exists(tmp_path: Path):
    initialization = _initialization(tmp_path)
    workspace_root = initialization.workspace.root_dir
    settings = _isolated_settings(tmp_path)
    service = RunService(settings=settings)

    press_release = (
        global_raw_sources_dir(initialization.case_number, settings)
        / f"ciaa-press-release-{initialization.case_number}.pdf"
    )
    press_release.parent.mkdir(parents=True, exist_ok=True)
    press_release.write_text("pdf", encoding="utf-8")

    router = service._make_router(
        case_number=initialization.case_number,
        workspace_root=workspace_root,
    )
    assert router("anything") == "case_draft"


def test_router_routes_to_publisher_when_draft_final_exists(tmp_path: Path):
    initialization = _initialization(tmp_path)
    workspace_root = initialization.workspace.root_dir
    settings = _isolated_settings(tmp_path)
    service = RunService(settings=settings)

    press_release = (
        global_raw_sources_dir(initialization.case_number, settings)
        / f"ciaa-press-release-{initialization.case_number}.pdf"
    )
    press_release.parent.mkdir(parents=True, exist_ok=True)
    press_release.write_text("pdf", encoding="utf-8")
    (workspace_root / "draft-final.md").write_text("draft", encoding="utf-8")

    router = service._make_router(
        case_number=initialization.case_number,
        workspace_root=workspace_root,
    )
    assert router("anything") == "case_publisher"


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------


def test_build_prompt_includes_case_number(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    settings = _isolated_settings(tmp_path)

    prompt = RunService._build_prompt(
        case_number=initialization.case_number,
        workspace_root=initialization.workspace.root_dir,
        source_bundle=source_bundle,
        settings=settings,
    )

    assert "Case number: 081-CR-0046" in prompt
    assert "## Source Manifest" in prompt
    assert "Charge Sheet" in prompt


# ---------------------------------------------------------------------------
# End-to-end RunService._run scenarios
# ---------------------------------------------------------------------------


def test_run_service_happy_path(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    settings = _isolated_settings(tmp_path)
    executor = FakeExecutor()
    executor._workspace_root = initialization.workspace.root_dir
    executor._press_release_path = (
        global_raw_sources_dir(initialization.case_number, settings)
        / f"ciaa-press-release-{initialization.case_number}.pdf"
    )
    service = _service_with_executor(executor, source_bundle, settings)

    result = service._run(
        case_input=_case_input(initialization.case_number),
        workspace_root=initialization.workspace.root_dir,
        executor=executor,
    )

    assert isinstance(result, WorkflowResult)
    assert result.published is True
    assert result.case_id == 7
    assert "orchestrator" in executor.calls


def test_run_service_fails_if_draft_final_not_written(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    settings = _isolated_settings(tmp_path)
    executor = FakeExecutor()
    # Do NOT set _workspace_root so draft-final.md is never written
    service = _service_with_executor(executor, source_bundle, settings)

    with pytest.raises(RuntimeError, match="Expected output file was not created"):
        service._run(
            case_input=_case_input(initialization.case_number),
            workspace_root=initialization.workspace.root_dir,
            executor=executor,
        )


def test_run_service_writes_draft_final(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    settings = _isolated_settings(tmp_path)
    executor = FakeExecutor()
    executor._workspace_root = initialization.workspace.root_dir
    executor._press_release_path = (
        global_raw_sources_dir(initialization.case_number, settings)
        / f"ciaa-press-release-{initialization.case_number}.pdf"
    )
    service = _service_with_executor(executor, source_bundle, settings)

    result = service._run(
        case_input=_case_input(initialization.case_number),
        workspace_root=initialization.workspace.root_dir,
        executor=executor,
    )
    assert result.published is True
    draft_path = initialization.workspace.root_dir / "draft-final.md"
    assert draft_path.is_file()
    assert draft_path.stat().st_size > 0


def test_run_service_injects_missing_data_marker_when_draft_lacks_it(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    settings = _isolated_settings(tmp_path)
    executor = FakeExecutor()
    executor._workspace_root = initialization.workspace.root_dir
    executor._press_release_path = (
        global_raw_sources_dir(initialization.case_number, settings)
        / f"ciaa-press-release-{initialization.case_number}.pdf"
    )
    service = _service_with_executor(executor, source_bundle, settings)

    result = service._run(
        case_input=_case_input(initialization.case_number),
        workspace_root=initialization.workspace.root_dir,
        executor=executor,
    )

    assert result.published is True
    draft_path = initialization.workspace.root_dir / "draft-final.md"
    draft_content = draft_path.read_text(encoding="utf-8")
    assert "not available from sources" in draft_content


def test_run_service_falls_back_to_orchestrator_when_staged_flow_raises(
    tmp_path: Path,
):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    settings = _isolated_settings(tmp_path)
    executor = FailingStagedExecutor()
    executor._workspace_root = initialization.workspace.root_dir
    executor._press_release_path = (
        global_raw_sources_dir(initialization.case_number, settings)
        / f"ciaa-press-release-{initialization.case_number}.pdf"
    )
    service = _service_with_executor(executor, source_bundle, settings)

    result = service._run(
        case_input=_case_input(initialization.case_number),
        workspace_root=initialization.workspace.root_dir,
        executor=executor,
    )

    assert result.published is True
    assert result.case_id == 7
    assert "prepare_information" in executor.calls
    assert "orchestrator" in executor.calls
