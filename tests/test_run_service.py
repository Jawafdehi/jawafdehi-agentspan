from __future__ import annotations

from pathlib import Path

import pytest

from jawafdehi_agentspan.assets import ciaa_workflow_root
from jawafdehi_agentspan.models import (
    CaseInitialization,
    Critique,
    OrchestratedRefinementOutput,
    PublishedCaseResult,
    ReviewOutcome,
    SourceArtifact,
    SourceBundle,
    WorkflowResult,
    WorkspaceContext,
)
from jawafdehi_agentspan.run_service import RunService
from jawafdehi_agentspan.settings import Settings


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
    def __init__(
        self,
        initialization: CaseInitialization,
        source_bundle: SourceBundle,
        critiques: list[Critique],
        publish_case_id: int = 7,
    ) -> None:
        self.initialization = initialization
        self.source_bundle = source_bundle
        self.critiques = critiques
        self.publish_case_id = publish_case_id
        self.review_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def run(self, agent, prompt: str, output_type=None):
        if agent.name == "ciaa_refinement_orchestrator":
            if len(self.critiques) > 1:
                initial = self.critiques[0]
                final = self.critiques[1]
                self.review_calls = 2
                return OrchestratedRefinementOutput(
                    draft_markdown=(
                        "# Jawafdehi Case Draft\n\n"
                        "## Title\nनमुना मुद्दा\n\n"
                        "## Short Description\nछोटो विवरण\n\n"
                        "## Key Allegations\n- आरोप १\n- आरोप २\n\n"
                        "## Timeline\n- 2082-01-01: दर्ता\n\n"
                        "## Description\n" + ("सुधार गरिएको विस्तृत विवरण।" * 60) + "\n"
                    ),
                    review_markdown="## Overall Review\n\nRe-review result\n",
                    critique=final,
                    revision_used=True,
                    initial_critique=initial,
                )
            final = self.critiques[0]
            self.review_calls = 1
            return OrchestratedRefinementOutput(
                draft_markdown=(
                    "# Jawafdehi Case Draft\n\n"
                    "## Title\nनमुना मुद्दा\n\n"
                    "## Short Description\nछोटो विवरण\n\n"
                    "## Key Allegations\n- आरोप १\n- आरोप २\n\n"
                    "## Timeline\n- 2082-01-01: दर्ता\n\n"
                    "## Description\n"
                    + ("विस्तृत विवरण।" * 60)
                    + "\n\n## Missing Details\nथप पुष्टिकरण आवश्यक।\n"
                ),
                review_markdown="## Overall Review\n\nInitial review result\n",
                critique=final,
                revision_used=False,
                initial_critique=None,
            )
        raise AssertionError(f"Unexpected agent {agent.name}")


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
) -> RunService:
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


def test_run_service_happy_path(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        initialization,
        source_bundle,
        [Critique(score=9, outcome=ReviewOutcome.approved)],
    )
    service = _service_with_executor(executor, source_bundle)

    result = service._run(
        case_input=_case_input(initialization.case_number),
        workspace_root=initialization.workspace.root_dir,
        executor=executor,
    )

    assert isinstance(result, WorkflowResult)
    assert result.published is True
    assert result.case_id == 7
    assert initialization.case_details_path.parent == initialization.workspace.data_dir


def test_run_service_revises_once_then_publishes(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        initialization,
        source_bundle,
        [
            Critique(
                score=7,
                outcome=ReviewOutcome.needs_revision,
                improvements=["More detail"],
            ),
            Critique(score=9, outcome=ReviewOutcome.approved),
        ],
    )
    service = _service_with_executor(executor, source_bundle)

    result = service._run(
        case_input=_case_input(initialization.case_number),
        workspace_root=initialization.workspace.root_dir,
        executor=executor,
    )

    assert result.published is True
    assert executor.review_calls == 2


def test_run_service_blocks_publication(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        initialization,
        source_bundle,
        [
            Critique(
                score=2,
                outcome=ReviewOutcome.blocked,
                blockers=["Unsupported allegation"],
            )
        ],
    )
    service = _service_with_executor(executor, source_bundle)

    with pytest.raises(RuntimeError, match="blocked"):
        service._run(
            case_input=_case_input(initialization.case_number),
            workspace_root=initialization.workspace.root_dir,
            executor=executor,
        )


def test_run_service_fails_after_final_review_needs_revision(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        initialization,
        source_bundle,
        [
            Critique(
                score=7,
                outcome=ReviewOutcome.needs_revision,
                improvements=["More detail"],
            ),
            Critique(
                score=7,
                outcome=ReviewOutcome.needs_revision,
                improvements=["Still more detail"],
            ),
        ],
    )
    service = _service_with_executor(executor, source_bundle)

    with pytest.raises(RuntimeError, match="maximum iterations"):
        service._run(
            case_input=_case_input(initialization.case_number),
            workspace_root=initialization.workspace.root_dir,
            executor=executor,
        )
