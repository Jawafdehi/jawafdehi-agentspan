from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from jawafdehi_agentspan.agents import build_refinement_orchestrator
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
    OrchestratedRefinementOutput,
    PublishInput,
    RefinementIteration,
    RefinementResult,
    SourceBundle,
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

        draft_path = workspace_root / "draft.md"
        review_path = workspace_root / "draft-review.md"
        orchestrated = executor.run(
            build_refinement_orchestrator(self.settings),
            self._build_refinement_orchestrator_prompt(
                case_number=case_input.case_number,
                source_bundle=source_bundle,
            ),
            output_type=OrchestratedRefinementOutput,
        )
        draft_path.write_text(
            orchestrated.draft_markdown.strip() + "\n", encoding="utf-8"
        )
        review_path.write_text(
            orchestrated.review_markdown.strip() + "\n", encoding="utf-8"
        )
        _validate_required_output(draft_path)
        _validate_required_output(review_path)

        critique = orchestrated.critique
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
                RefinementIteration(iteration=2, critique=critique, revised=False)
            )
        else:
            iterations.append(
                RefinementIteration(iteration=1, critique=critique, revised=False)
            )

        if critique.outcome == critique.outcome.blocked:
            raise RuntimeError("Draft review was blocked")
        if critique.outcome not in ACCEPTED_REVIEW_OUTCOMES or critique.score < 8:
            raise RuntimeError(
                "Draft refinement exhausted maximum iterations without approval"
            )

        refinement_result = RefinementResult(
            workspace=initialization.workspace,
            draft_path=draft_path,
            review_path=review_path,
            final_score=critique.score,
            final_outcome=critique.outcome,
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
            final_outcome=critique.outcome,
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
    def _build_refinement_orchestrator_prompt(
        cls,
        *,
        case_number: str,
        source_bundle: SourceBundle,
    ) -> str:
        source_manifest = cls._format_source_manifest(source_bundle)
        return (
            f"Case number: {case_number}\n\n"
            "Run the complete drafting-and-refinement workflow in one "
            "orchestrated pass.\n"
            "Case initialization, source gathering, and news gathering are "
            "already complete before this prompt.\n"
            "Source documents may live in the run workspace or the global "
            "source store. Use the source manifest below and the appropriate "
            "workspace/global file tools to read them.\n"
            "Start from the available source documents only, then draft, "
            "review, extract critique, and optionally revise once before "
            "re-reviewing.\n"
            "Prefer primary source facts, avoid unsupported claims, and keep "
            "the final draft publishable in Nepali markdown.\n"
            "Return the final structured orchestrated refinement output only.\n\n"
            "## Source Manifest\n\n"
            f"{source_manifest}"
        )
