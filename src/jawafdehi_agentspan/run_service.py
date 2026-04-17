from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from jawafdehi_agentspan.agents import (
    build_critique_extractor,
    build_draft_agent,
    build_review_agent,
    build_revise_agent,
)
from jawafdehi_agentspan.assets import ciaa_workflow_root
from jawafdehi_agentspan.dependencies import (
    build_default_dependencies,
    use_dependencies,
)
from jawafdehi_agentspan.logging_utils import configure_run_logging
from jawafdehi_agentspan.models import (
    ACCEPTED_REVIEW_OUTCOMES,
    CaseInitialization,
    CIAACaseInput,
    Critique,
    OrchestratedRefinementOutput,
    PublishInput,
    RefinementIteration,
    RefinementResult,
    SourceBundle,
    TraversalNode,
    TraversalNodeStatus,
    WorkflowResult,
)
from jawafdehi_agentspan.runtime import AgentExecutor, AgentSpanExecutor
from jawafdehi_agentspan.settings import Settings, get_settings
from jawafdehi_agentspan.workspace import build_case_initialization, create_workspace

logger = logging.getLogger(__name__)


def _validate_required_output(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Expected output file was not created: {path}")
    if path.stat().st_size == 0:
        raise RuntimeError(f"Expected output file is empty: {path}")


def _run_async(awaitable):
    return asyncio.run(awaitable)


class RunService:
    def __init__(
        self,
        *,
        dependencies=None,
        executor_factory=None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.dependencies = dependencies or build_default_dependencies()
        self.executor_factory = executor_factory or (
            lambda: AgentSpanExecutor(self.settings)
        )

    def start_run(self, case_number: str) -> WorkflowResult:
        case_input = CIAACaseInput(case_number=case_number)
        workspace = create_workspace(case_input.case_number)
        log_path = configure_run_logging(workspace.logs_dir, case_input.case_number)
        logger.debug("Starting AgentSpan workflow run for %s", case_input.case_number)
        logger.debug("Run workspace initialized at %s", workspace.root_dir)
        logger.debug("Verbose log file configured at %s", log_path)

        with use_dependencies(self.dependencies):
            with self.executor_factory() as executor:
                return self._run(case_input, workspace.root_dir, executor)

    def _run(
        self,
        case_input: CIAACaseInput,
        workspace_root: Path,
        executor: AgentExecutor,
    ) -> WorkflowResult:
        workspace_root = workspace_root.resolve()
        initialization = self._initialize_casework(
            case_input.case_number,
            workspace_root,
        )

        source_bundle = self._gather_sources(initialization)
        source_bundle = self._gather_news(source_bundle)

        traversal_history = self._initial_traversal_history()
        self._log_refinement_context(case_input.case_number, source_bundle, traversal_history)

        draft_markdown = self._run_drafter(
            executor,
            case_input.case_number,
            source_bundle,
            traversal_history,
        )
        self._complete_next_node(traversal_history, "drafter")

        review_markdown = self._run_reviewer(
            executor,
            case_input.case_number,
            source_bundle,
            draft_markdown,
            traversal_history,
        )
        self._complete_next_node(traversal_history, "reviewer")

        critique = self._run_critique_extractor(
            executor,
            review_markdown,
            traversal_history,
        )
        self._complete_next_node(traversal_history, "critique_extractor", critique.outcome.value)

        revision_used = False
        initial_critique: Critique | None = None
        if critique.outcome not in ACCEPTED_REVIEW_OUTCOMES or critique.score < 8:
            if critique.outcome != critique.outcome.blocked:
                revision_used = True
                initial_critique = critique
                self._activate_revision_path(traversal_history)
                draft_markdown = self._run_reviser(
                    executor,
                    case_input.case_number,
                    source_bundle,
                    draft_markdown,
                    review_markdown,
                    critique,
                    traversal_history,
                )
                self._complete_next_node(traversal_history, "reviser")

                review_markdown = self._run_reviewer(
                    executor,
                    case_input.case_number,
                    source_bundle,
                    draft_markdown,
                    traversal_history,
                )
                self._complete_next_node(traversal_history, "reviewer")

                critique = self._run_critique_extractor(
                    executor,
                    review_markdown,
                    traversal_history,
                )
                self._complete_next_node(
                    traversal_history,
                    "critique_extractor",
                    critique.outcome.value,
                )

        orchestrated = OrchestratedRefinementOutput(
            draft_markdown=draft_markdown,
            review_markdown=review_markdown,
            critique=critique,
            revision_used=revision_used,
            initial_critique=initial_critique,
            traversal_history=[node.model_copy() for node in traversal_history],
        )

        draft_path = workspace_root / "draft.md"
        review_path = workspace_root / "draft-review.md"
        draft_path.write_text(orchestrated.draft_markdown.strip() + "\n", encoding="utf-8")
        review_path.write_text(
            orchestrated.review_markdown.strip() + "\n", encoding="utf-8"
        )
        _validate_required_output(draft_path)
        _validate_required_output(review_path)

        final_critique = orchestrated.critique
        iterations: list[RefinementIteration] = []
        if orchestrated.initial_critique is not None:
            iterations.append(
                RefinementIteration(
                    iteration=1,
                    critique=orchestrated.initial_critique,
                    revised=orchestrated.revision_used,
                )
            )
            iterations.append(
                RefinementIteration(
                    iteration=2,
                    critique=final_critique,
                    revised=False,
                )
            )
        else:
            iterations.append(
                RefinementIteration(
                    iteration=1,
                    critique=final_critique,
                    revised=False,
                )
            )

        if final_critique.outcome == final_critique.outcome.blocked:
            raise RuntimeError("Draft review was blocked")
        if (
            final_critique.outcome not in ACCEPTED_REVIEW_OUTCOMES
            or final_critique.score < 8
        ):
            raise RuntimeError(
                "Draft refinement exhausted maximum iterations without approval"
            )

        refinement_result = RefinementResult(
            workspace=initialization.workspace,
            draft_path=draft_path,
            review_path=review_path,
            final_score=final_critique.score,
            final_outcome=final_critique.outcome,
            iterations=iterations,
        )

        published_case = self._publish_case(
            PublishInput(
                case_number=case_input.case_number,
                source_bundle=source_bundle,
                refinement_result=refinement_result,
            )
        )
        return WorkflowResult(
            case_number=case_input.case_number,
            published=True,
            case_id=published_case.case_id,
            final_outcome=final_critique.outcome,
        )

    def _initialize_casework(
        self,
        case_number: str,
        workspace_root: Path,
    ) -> CaseInitialization:
        return build_case_initialization(
            case_number,
            workspace_root,
            self.dependencies.adapter,
            asset_root=ciaa_workflow_root(),
        )

    def _gather_sources(self, initialization: CaseInitialization) -> SourceBundle:
        return _run_async(
            self.dependencies.source_gatherer.gather_sources(initialization)
        )

    def _gather_news(self, source_bundle: SourceBundle) -> SourceBundle:
        return _run_async(self.dependencies.news_gatherer.gather_news(source_bundle))

    def _publish_case(self, publish_input: PublishInput):
        return _run_async(
            self.dependencies.publish_finalizer.publish_and_finalize(publish_input)
        )

    def _run_drafter(
        self,
        executor: AgentExecutor,
        case_number: str,
        source_bundle: SourceBundle,
        traversal_history: list[TraversalNode],
    ) -> str:
        prompt = self._build_draft_prompt(
            case_number=case_number,
            source_bundle=source_bundle,
            traversal_history=traversal_history,
        )
        logger.debug("Draft prompt for %s:\n%s", case_number, prompt)
        draft = executor.run(build_draft_agent(self.settings), prompt)
        if not isinstance(draft, str):
            raise RuntimeError(f"Expected draft markdown string, got {type(draft).__name__}")
        return draft.strip()

    def _run_reviewer(
        self,
        executor: AgentExecutor,
        case_number: str,
        source_bundle: SourceBundle,
        draft_markdown: str,
        traversal_history: list[TraversalNode],
    ) -> str:
        prompt = self._build_review_prompt(
            case_number=case_number,
            source_bundle=source_bundle,
            draft_markdown=draft_markdown,
            traversal_history=traversal_history,
        )
        logger.debug("Review prompt for %s:\n%s", case_number, prompt)
        review = executor.run(build_review_agent(self.settings), prompt)
        if not isinstance(review, str):
            raise RuntimeError(f"Expected review markdown string, got {type(review).__name__}")
        return review.strip()

    def _run_critique_extractor(
        self,
        executor: AgentExecutor,
        review_markdown: str,
        traversal_history: list[TraversalNode],
    ) -> Critique:
        prompt = self._build_critique_prompt(
            review_markdown=review_markdown,
            traversal_history=traversal_history,
        )
        logger.debug("Critique extractor prompt:\n%s", prompt)
        return executor.run(
            build_critique_extractor(self.settings),
            prompt,
            output_type=Critique,
        )

    def _run_reviser(
        self,
        executor: AgentExecutor,
        case_number: str,
        source_bundle: SourceBundle,
        draft_markdown: str,
        review_markdown: str,
        critique: Critique,
        traversal_history: list[TraversalNode],
    ) -> str:
        prompt = self._build_revise_prompt(
            case_number=case_number,
            source_bundle=source_bundle,
            draft_markdown=draft_markdown,
            review_markdown=review_markdown,
            critique=critique,
            traversal_history=traversal_history,
        )
        logger.debug("Revise prompt for %s:\n%s", case_number, prompt)
        revised = executor.run(build_revise_agent(self.settings), prompt)
        if not isinstance(revised, str):
            raise RuntimeError(
                f"Expected revised draft markdown string, got {type(revised).__name__}"
            )
        return revised.strip()

    def _log_refinement_context(
        self,
        case_number: str,
        source_bundle: SourceBundle,
        traversal_history: list[TraversalNode],
    ) -> None:
        logger.debug(
            "Running deterministic refinement flow for %s with %d source artifacts",
            case_number,
            len(source_bundle.source_artifacts),
        )
        logger.debug(
            "Refinement source artifact paths for %s: %s",
            case_number,
            [
                {
                    "source_type": artifact.source_type,
                    "raw_path": str(artifact.raw_path),
                    "markdown_path": str(artifact.markdown_path),
                }
                for artifact in source_bundle.source_artifacts
            ],
        )
        logger.debug(
            "Initial traversal history for %s:\n%s",
            case_number,
            self._format_traversal_history(traversal_history),
        )

    @staticmethod
    def _initial_traversal_history() -> list[TraversalNode]:
        return [
            TraversalNode(
                node_name="initialize_casework",
                status=TraversalNodeStatus.completed,
            ),
            TraversalNode(node_name="gather_sources", status=TraversalNodeStatus.completed),
            TraversalNode(node_name="gather_news", status=TraversalNodeStatus.completed),
            TraversalNode(node_name="drafter", status=TraversalNodeStatus.pending),
            TraversalNode(node_name="reviewer", status=TraversalNodeStatus.pending),
            TraversalNode(
                node_name="critique_extractor",
                status=TraversalNodeStatus.pending,
            ),
            TraversalNode(node_name="reviser", status=TraversalNodeStatus.conditional),
            TraversalNode(node_name="reviewer", status=TraversalNodeStatus.conditional),
            TraversalNode(
                node_name="critique_extractor",
                status=TraversalNodeStatus.conditional,
            ),
        ]

    @staticmethod
    def _complete_next_node(
        traversal_history: list[TraversalNode],
        node_name: str,
        notes: str | None = None,
    ) -> None:
        for node in traversal_history:
            if node.node_name == node_name and node.status != TraversalNodeStatus.completed:
                node.status = TraversalNodeStatus.completed
                if notes is not None:
                    node.notes = notes
                return
        raise RuntimeError(f"No pending traversal node available for {node_name}")

    @staticmethod
    def _activate_revision_path(traversal_history: list[TraversalNode]) -> None:
        for node in traversal_history:
            if node.status == TraversalNodeStatus.conditional:
                node.status = TraversalNodeStatus.pending

    @classmethod
    def _format_source_manifest(cls, source_bundle: SourceBundle) -> str:
        blocks: list[str] = []
        for artifact in source_bundle.source_artifacts:
            blocks.append(
                "\n".join(
                    [
                        f"## {artifact.title}",
                        f"Source type: {artifact.source_type}",
                        f"Raw path: {artifact.raw_path}",
                        f"Markdown path: {artifact.markdown_path}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    @classmethod
    def _format_traversal_history(cls, traversal_history: list[TraversalNode]) -> str:
        return "\n".join(
            (
                f"- {node.node_name}: {node.status.value}"
                if not node.notes
                else f"- {node.node_name}: {node.status.value} ({node.notes})"
            )
            for node in traversal_history
        )

    @classmethod
    def _build_context_sections(
        cls,
        *,
        case_number: str,
        source_bundle: SourceBundle,
        traversal_history: list[TraversalNode],
    ) -> str:
        source_manifest = cls._format_source_manifest(source_bundle)
        rendered_history = cls._format_traversal_history(traversal_history)
        return (
            f"Case number: {case_number}\n\n"
            "## Traversal History\n\n"
            f"{rendered_history}\n\n"
            "## Source Manifest\n\n"
            f"{source_manifest}"
        )

    @classmethod
    def _build_draft_prompt(
        cls,
        *,
        case_number: str,
        source_bundle: SourceBundle,
        traversal_history: list[TraversalNode],
    ) -> str:
        return (
            "Draft the case from the source documents listed in the Source Manifest below.\n"
            "Step 1: Use run_shell_command with `cat <markdown_path>` to read each source file.\n"
            "Step 2: Write the complete Nepali markdown draft based on what you read.\n"
            "Return only the final Nepali markdown draft text, without code fences.\n\n"
            + cls._build_context_sections(
                case_number=case_number,
                source_bundle=source_bundle,
                traversal_history=traversal_history,
            )
        )

    @classmethod
    def _build_review_prompt(
        cls,
        *,
        case_number: str,
        source_bundle: SourceBundle,
        draft_markdown: str,
        traversal_history: list[TraversalNode],
    ) -> str:
        return (
            "Review the draft against the listed sources.\n"
            "Use traversal history as workflow control state only.\n"
            "Return only the review markdown.\n\n"
            + cls._build_context_sections(
                case_number=case_number,
                source_bundle=source_bundle,
                traversal_history=traversal_history,
            )
            + "\n\n## Draft Markdown\n\n"
            + draft_markdown
        )

    @classmethod
    def _build_critique_prompt(
        cls,
        *,
        review_markdown: str,
        traversal_history: list[TraversalNode],
    ) -> str:
        return (
            "Extract the structured critique from the review below.\n"
            "Use traversal history as workflow control state only.\n\n"
            "## Traversal History\n\n"
            f"{cls._format_traversal_history(traversal_history)}\n\n"
            "## Review Markdown\n\n"
            f"{review_markdown}"
        )

    @classmethod
    def _build_revise_prompt(
        cls,
        *,
        case_number: str,
        source_bundle: SourceBundle,
        draft_markdown: str,
        review_markdown: str,
        critique: Critique,
        traversal_history: list[TraversalNode],
    ) -> str:
        return (
            "Revise the draft to address the critique and review.\n"
            "Use traversal history as workflow control state only.\n"
            "Return only the improved Nepali markdown draft.\n\n"
            + cls._build_context_sections(
                case_number=case_number,
                source_bundle=source_bundle,
                traversal_history=traversal_history,
            )
            + "\n\n## Current Draft Markdown\n\n"
            + draft_markdown
            + "\n\n## Review Markdown\n\n"
            + review_markdown
            + "\n\n## Structured Critique\n\n"
            + critique.model_dump_json(indent=2)
        )
