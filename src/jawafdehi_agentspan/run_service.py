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

ORCHESTRATOR_SOURCE_CHAR_LIMIT = 50000
ORCHESTRATOR_INSTRUCTIONS_CHAR_LIMIT = 4000
ORCHESTRATOR_TEMPLATE_CHAR_LIMIT = 12000
CHARGE_SHEET_CHAR_LIMIT = 70000
STANDARD_SOURCE_CHAR_LIMIT = 20000


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
                initialization=initialization,
                source_bundle=source_bundle,
                draft_path=draft_path,
                review_path=review_path,
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

    @staticmethod
    def _read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8").strip()

    @classmethod
    def _condense_text(cls, content: str, max_chars: int | None) -> str:
        if max_chars is None or len(content) <= max_chars:
            return content
        head = max_chars * 3 // 4
        tail = max_chars - head
        return (
            f"{content[:head].rstrip()}\n\n"
            f"[TRUNCATED {len(content) - max_chars} CHARACTERS]\n\n"
            f"{content[-tail:].lstrip()}"
        )

    @classmethod
    def _format_document_block(
        cls,
        label: str,
        path: Path,
        *,
        max_chars: int | None = None,
    ) -> str:
        content = cls._read_text(path)
        content = cls._condense_text(content, max_chars)
        return f"## {label}\nPath: {path}\n<document>\n{content}\n</document>"

    @classmethod
    def _select_source_char_limit(cls, path: Path) -> int:
        if "charge-sheet" in path.name:
            return CHARGE_SHEET_CHAR_LIMIT
        return STANDARD_SOURCE_CHAR_LIMIT

    @classmethod
    def _format_source_documents(
        cls,
        source_bundle: SourceBundle,
        *,
        total_limit: int,
    ) -> str:
        blocks: list[str] = []
        remaining = total_limit
        for source in source_bundle.workspace.sources:
            if remaining <= 0:
                break
            path = source.markdown
            source_limit = min(cls._select_source_char_limit(path), remaining)
            blocks.append(
                cls._format_document_block(
                    source.name,
                    path,
                    max_chars=source_limit,
                )
            )
            remaining -= source_limit
        for artifact in source_bundle.news_artifacts:
            if remaining <= 0:
                break
            path = artifact.markdown_path
            source_limit = min(cls._select_source_char_limit(path), remaining)
            blocks.append(
                cls._format_document_block(
                    artifact.title,
                    path,
                    max_chars=source_limit,
                )
            )
            remaining -= source_limit
        return "\n\n".join(blocks)

    @classmethod
    def _build_refinement_orchestrator_prompt(
        cls,
        *,
        case_number: str,
        initialization: CaseInitialization,
        source_bundle: SourceBundle,
        draft_path: Path,
        review_path: Path,
    ) -> str:
        instructions_path = (
            initialization.asset_root / "instructions" / "INSTRUCTIONS.md"
        )
        template_path = initialization.asset_root / "instructions" / "case-template.md"
        instructions_block = cls._format_document_block(
            "Workflow Instructions",
            instructions_path,
            max_chars=ORCHESTRATOR_INSTRUCTIONS_CHAR_LIMIT,
        )
        template_block = cls._format_document_block(
            "Case Template",
            template_path,
            max_chars=ORCHESTRATOR_TEMPLATE_CHAR_LIMIT,
        )
        source_documents = cls._format_source_documents(
            source_bundle, total_limit=ORCHESTRATOR_SOURCE_CHAR_LIMIT
        )
        return (
            f"Case number: {case_number}\n"
            f"Destination draft path: {draft_path}\n"
            f"Destination review path: {review_path}\n\n"
            "Run the complete drafting-and-refinement workflow in one "
            "orchestrated pass.\n"
            "Case initialization, source gathering, and news gathering are "
            "already complete before this prompt.\n"
            "Start from the provided source documents only, then draft, "
            "review, extract critique, and optionally revise once before "
            "re-reviewing.\n"
            "Prefer primary source facts, avoid unsupported claims, and keep "
            "the final draft publishable in Nepali markdown.\n"
            "Return the final structured orchestrated refinement output only.\n\n"
            f"{instructions_block}\n\n"
            f"{template_block}\n\n"
            f"{source_documents}"
        )
