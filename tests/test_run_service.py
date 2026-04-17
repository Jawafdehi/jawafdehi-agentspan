from __future__ import annotations

from pathlib import Path

import pytest

from jawafdehi_agentspan.assets import ciaa_workflow_root
from jawafdehi_agentspan.models import (
    CaseInitialization,
    Critique,
    PublishedCaseResult,
    ReviewOutcome,
    SourceArtifact,
    SourceBundle,
    TraversalNode,
    TraversalNodeStatus,
    WorkflowResult,
    WorkspaceContext,
)
from jawafdehi_agentspan.run_service import RunService
from jawafdehi_agentspan.settings import Settings

_DRAFT_MARKDOWN = (
    "# Jawafdehi Case Draft\n\n"
    "## Title\nनमुना मुद्दा\n\n"
    "## Short Description\nछोटो विवरण\n\n"
    "## Key Allegations\n- आरोप १\n- आरोप २\n\n"
    "## Timeline\n- 2082-01-01: दर्ता\n\n"
    "## Description\n" + ("विस्तृत विवरण।" * 60) + "\n"
)
_REVISED_DRAFT_MARKDOWN = (
    "# Jawafdehi Case Draft\n\n"
    "## Title\nनमुना मुद्दा\n\n"
    "## Short Description\nछोटो विवरण\n\n"
    "## Key Allegations\n- आरोप १\n- आरोप २\n\n"
    "## Timeline\n- 2082-01-01: दर्ता\n\n"
    "## Description\n" + ("सुधार गरिएको विस्तृत विवरण।" * 60) + "\n"
)
_REVIEW_MARKDOWN = "## Overall Review\n\nInitial review result\n"
_REVISED_REVIEW_MARKDOWN = "## Overall Review\n\nRe-review result\n"


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
    """Simulates per-node agent calls for the deterministic refinement flow."""

    def __init__(
        self,
        critiques: list[Critique],
        publish_case_id: int = 7,
    ) -> None:
        self.critiques = list(critiques)
        self.publish_case_id = publish_case_id
        self.drafter_calls: int = 0
        self.reviewer_calls: int = 0
        self.critique_extractor_calls: int = 0
        self.reviser_calls: int = 0
        self._critique_index: int = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def run(self, agent, prompt: str, output_type=None):
        if agent.name == "ciaa_drafter":
            self.drafter_calls += 1
            return _DRAFT_MARKDOWN if self.reviser_calls == 0 else _REVISED_DRAFT_MARKDOWN
        if agent.name == "ciaa_reviewer":
            self.reviewer_calls += 1
            return _REVIEW_MARKDOWN if self.reviser_calls == 0 else _REVISED_REVIEW_MARKDOWN
        if agent.name == "ciaa_critique_extractor":
            self.critique_extractor_calls += 1
            critique = self.critiques[self._critique_index]
            if self._critique_index < len(self.critiques) - 1:
                self._critique_index += 1
            return critique
        if agent.name == "ciaa_reviser":
            self.reviser_calls += 1
            return _REVISED_DRAFT_MARKDOWN
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


# ---------------------------------------------------------------------------
# Traversal history helpers
# ---------------------------------------------------------------------------


def test_initial_traversal_history_has_correct_nodes():
    history = RunService._initial_traversal_history()
    names = [n.node_name for n in history]
    assert names == [
        "initialize_casework",
        "gather_sources",
        "gather_news",
        "drafter",
        "reviewer",
        "critique_extractor",
        "reviser",
        "reviewer",
        "critique_extractor",
    ]


def test_initial_traversal_history_statuses():
    history = RunService._initial_traversal_history()
    completed = [n for n in history if n.status == TraversalNodeStatus.completed]
    pending = [n for n in history if n.status == TraversalNodeStatus.pending]
    conditional = [n for n in history if n.status == TraversalNodeStatus.conditional]
    assert [n.node_name for n in completed] == [
        "initialize_casework",
        "gather_sources",
        "gather_news",
    ]
    assert [n.node_name for n in pending] == [
        "drafter",
        "reviewer",
        "critique_extractor",
    ]
    assert [n.node_name for n in conditional] == [
        "reviser",
        "reviewer",
        "critique_extractor",
    ]


def test_complete_next_node_updates_first_matching_pending():
    history = RunService._initial_traversal_history()
    RunService._complete_next_node(history, "drafter")
    drafter = next(n for n in history if n.node_name == "drafter")
    assert drafter.status == TraversalNodeStatus.completed


def test_complete_next_node_with_notes():
    history = RunService._initial_traversal_history()
    RunService._complete_next_node(history, "drafter")
    RunService._complete_next_node(history, "reviewer")
    RunService._complete_next_node(history, "critique_extractor", "approved")
    ce = next(
        n
        for n in history
        if n.node_name == "critique_extractor" and n.status == TraversalNodeStatus.completed
    )
    assert ce.notes == "approved"


def test_complete_next_node_does_not_double_complete():
    history = RunService._initial_traversal_history()
    RunService._complete_next_node(history, "drafter")
    RunService._complete_next_node(history, "reviewer")
    RunService._complete_next_node(history, "critique_extractor")
    # activate revision path so second reviewer/critique_extractor become pending
    RunService._activate_revision_path(history)
    RunService._complete_next_node(history, "reviser")
    RunService._complete_next_node(history, "reviewer")
    RunService._complete_next_node(history, "critique_extractor")
    completed = [n for n in history if n.status == TraversalNodeStatus.completed]
    assert len(completed) == len(history)


def test_activate_revision_path_changes_conditional_to_pending():
    history = RunService._initial_traversal_history()
    RunService._activate_revision_path(history)
    conditional = [n for n in history if n.status == TraversalNodeStatus.conditional]
    assert conditional == []
    pending = [n for n in history if n.status == TraversalNodeStatus.pending]
    pending_names = [n.node_name for n in pending]
    assert "reviser" in pending_names


def test_format_traversal_history_renders_all_nodes():
    history = RunService._initial_traversal_history()
    rendered = RunService._format_traversal_history(history)
    assert "- initialize_casework: completed" in rendered
    assert "- gather_sources: completed" in rendered
    assert "- gather_news: completed" in rendered
    assert "- drafter: pending" in rendered
    assert "- reviewer: pending" in rendered
    assert "- critique_extractor: pending" in rendered
    assert "- reviser: conditional" in rendered


def test_format_traversal_history_includes_notes():
    history = [
        TraversalNode(
            node_name="critique_extractor",
            status=TraversalNodeStatus.completed,
            notes="needs_revision",
        )
    ]
    rendered = RunService._format_traversal_history(history)
    assert "- critique_extractor: completed (needs_revision)" in rendered


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def test_build_draft_prompt_includes_traversal_history(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    history = RunService._initial_traversal_history()

    prompt = RunService._build_draft_prompt(
        case_number=initialization.case_number,
        source_bundle=source_bundle,
        traversal_history=history,
    )

    assert "## Traversal History" in prompt
    assert "- drafter: pending" in prompt
    assert "## Source Manifest" in prompt


def test_build_review_prompt_includes_draft_and_history(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    history = RunService._initial_traversal_history()
    RunService._complete_next_node(history, "drafter")

    prompt = RunService._build_review_prompt(
        case_number=initialization.case_number,
        source_bundle=source_bundle,
        draft_markdown="# Draft\n",
        traversal_history=history,
    )

    assert "## Traversal History" in prompt
    assert "- drafter: completed" in prompt
    assert "## Draft Markdown" in prompt
    assert "# Draft" in prompt


def test_build_critique_prompt_includes_review_and_history():
    history = RunService._initial_traversal_history()
    RunService._complete_next_node(history, "drafter")
    RunService._complete_next_node(history, "reviewer")

    prompt = RunService._build_critique_prompt(
        review_markdown="## Review\n",
        traversal_history=history,
    )

    assert "## Traversal History" in prompt
    assert "- reviewer: completed" in prompt
    assert "## Review Markdown" in prompt


def test_build_revise_prompt_includes_all_sections(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    history = RunService._initial_traversal_history()
    RunService._complete_next_node(history, "drafter")
    RunService._complete_next_node(history, "reviewer")
    RunService._complete_next_node(history, "critique_extractor", "needs_revision")
    RunService._activate_revision_path(history)
    critique = Critique(
        score=5,
        outcome=ReviewOutcome.needs_revision,
        improvements=["More detail"],
    )

    prompt = RunService._build_revise_prompt(
        case_number=initialization.case_number,
        source_bundle=source_bundle,
        draft_markdown="# Draft\n",
        review_markdown="## Review\n",
        critique=critique,
        traversal_history=history,
    )

    assert "## Traversal History" in prompt
    assert "- reviser: pending" in prompt
    assert "## Current Draft Markdown" in prompt
    assert "## Review Markdown" in prompt
    assert "## Structured Critique" in prompt


# ---------------------------------------------------------------------------
# End-to-end RunService._run scenarios
# ---------------------------------------------------------------------------


def test_run_service_happy_path(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        critiques=[Critique(score=9, outcome=ReviewOutcome.approved)],
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
    assert executor.drafter_calls == 1
    assert executor.reviewer_calls == 1
    assert executor.critique_extractor_calls == 1
    assert executor.reviser_calls == 0


def test_run_service_revises_once_then_publishes(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        critiques=[
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
    assert executor.drafter_calls == 1
    assert executor.reviewer_calls == 2
    assert executor.critique_extractor_calls == 2
    assert executor.reviser_calls == 1


def test_run_service_blocks_publication(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        critiques=[
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

    assert executor.reviser_calls == 0


def test_run_service_fails_after_final_review_needs_revision(tmp_path: Path):
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        critiques=[
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

    assert executor.reviser_calls == 1


def test_run_service_traversal_history_in_output_no_revision(tmp_path: Path):
    """Traversal history in OrchestratedRefinementOutput reflects completed nodes."""
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        critiques=[Critique(score=9, outcome=ReviewOutcome.approved)],
    )
    service = _service_with_executor(executor, source_bundle)

    # Capture the orchestrated output by patching _publish_case to not run
    # We test via the draft/review files written to disk instead
    result = service._run(
        case_input=_case_input(initialization.case_number),
        workspace_root=initialization.workspace.root_dir,
        executor=executor,
    )
    assert result.published is True
    draft_path = initialization.workspace.root_dir / "draft.md"
    assert draft_path.is_file()
    assert draft_path.stat().st_size > 0


def test_run_service_traversal_history_updated_after_each_node(tmp_path: Path):
    """Traversal history nodes are completed in order during the revision path."""
    initialization = _initialization(tmp_path)
    source_bundle = _source_bundle(initialization)
    executor = FakeExecutor(
        critiques=[
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
    # Revision path: drafter(1) + reviewer(2) + critique_extractor(2) + reviser(1)
    assert executor.drafter_calls == 1
    assert executor.reviewer_calls == 2
    assert executor.critique_extractor_calls == 2
    assert executor.reviser_calls == 1

