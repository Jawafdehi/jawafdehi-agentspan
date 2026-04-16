from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from jawaf_span.agents import (
    build_critique_extractor,
    build_draft_agent,
    build_review_agent,
    build_revise_agent,
)
from jawaf_span.assets import ciaa_workflow_root
from jawaf_span.dependencies import (
    build_default_dependencies,
    use_dependencies,
)
from jawaf_span.logging_utils import configure_run_logging
from jawaf_span.models import (
    ACCEPTED_REVIEW_OUTCOMES,
    CaseInitialization,
    CIAACaseInput,
    Critique,
    PublishInput,
    RefinementIteration,
    RefinementResult,
    SourceBundle,
    WorkflowResult,
)
from jawaf_span.runtime import AgentExecutor, AgentSpanExecutor
from jawaf_span.settings import Settings, get_settings
from jawaf_span.workspace import create_workspace

logger = logging.getLogger(__name__)

DRAFT_SOURCE_CHAR_LIMIT = 120000
REVIEW_SOURCE_CHAR_LIMIT = 140000
REVISION_SOURCE_CHAR_LIMIT = 140000
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
        draft_text = executor.run(
            build_draft_agent(self.settings),
            self._build_draft_prompt(
                case_number=case_input.case_number,
                draft_path=draft_path,
                initialization=initialization,
                source_bundle=source_bundle,
            ),
        )
        draft_path.write_text(str(draft_text).strip() + "\n", encoding="utf-8")
        _validate_required_output(draft_path)

        iterations: list[RefinementIteration] = []
        review_path = workspace_root / "draft-review.md"

        review_text = str(
            executor.run(
                build_review_agent(self.settings),
                self._build_review_prompt(
                    case_number=case_input.case_number,
                    initialization=initialization,
                    source_bundle=source_bundle,
                    draft_path=draft_path,
                ),
            )
        ).strip()
        review_path.write_text(review_text, encoding="utf-8")
        critique = executor.run(
            build_critique_extractor(self.settings),
            f"Extract the structured critique from this review:\n\n{review_text}",
            output_type=Critique,
        )

        if critique.outcome == critique.outcome.blocked:
            iterations.append(
                RefinementIteration(iteration=1, critique=critique, revised=False)
            )
            raise RuntimeError("Draft review was blocked")

        if critique.outcome not in ACCEPTED_REVIEW_OUTCOMES or critique.score < 8:
            iterations.append(
                RefinementIteration(iteration=1, critique=critique, revised=True)
            )
            revised_draft = executor.run(
                build_revise_agent(self.settings),
                self._build_revision_prompt(
                    case_number=case_input.case_number,
                    initialization=initialization,
                    source_bundle=source_bundle,
                    draft_path=draft_path,
                    review_path=review_path,
                ),
            )
            draft_path.write_text(str(revised_draft).strip() + "\n", encoding="utf-8")
            _validate_required_output(draft_path)
            review_text = str(
                executor.run(
                    build_review_agent(self.settings),
                    self._build_review_prompt(
                        case_number=case_input.case_number,
                        initialization=initialization,
                        source_bundle=source_bundle,
                        draft_path=draft_path,
                    ),
                )
            ).strip()
            review_path.write_text(review_text, encoding="utf-8")
            critique = executor.run(
                build_critique_extractor(self.settings),
                f"Extract the structured critique from this review:\n\n{review_text}",
                output_type=Critique,
            )
            iterations.append(
                RefinementIteration(iteration=2, critique=critique, revised=False)
            )
            if critique.outcome == critique.outcome.blocked:
                raise RuntimeError("Draft review was blocked")
            if critique.outcome not in ACCEPTED_REVIEW_OUTCOMES or critique.score < 8:
                raise RuntimeError(
                    "Draft refinement exhausted maximum iterations without approval"
                )
        else:
            iterations.append(
                RefinementIteration(iteration=1, critique=critique, revised=False)
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
        workspace = {
            "root_dir": workspace_root,
            "logs_dir": workspace_root / "logs",
            "data_dir": workspace_root / "data",
            "sources_raw_dir": workspace_root / "sources" / "raw",
            "sources_markdown_dir": workspace_root / "sources" / "markdown",
            "memory_file": workspace_root / "MEMORY.md",
        }
        case_details_path = workspace_root / f"case_details-{case_number}.md"
        content = _run_async(
            self.dependencies.ngm_client.fetch_case_details(
                case_number, case_details_path
            )
        )
        summary_path = workspace_root / "logs" / "case-summary.md"
        summary_path.write_text(
            f"# Case Summary\n\n- Case number: {case_number}\n\n{content[:1200]}\n",
            encoding="utf-8",
        )
        return CaseInitialization(
            case_number=case_number,
            workspace=workspace,
            asset_root=ciaa_workflow_root(),
            case_details_path=case_details_path,
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
        for path in source_bundle.markdown_sources:
            if remaining <= 0:
                break
            source_limit = min(cls._select_source_char_limit(path), remaining)
            blocks.append(
                cls._format_document_block(
                    path.name,
                    path,
                    max_chars=source_limit,
                )
            )
            remaining -= source_limit
        return "\n\n".join(blocks)

    @classmethod
    def _build_draft_prompt(
        cls,
        *,
        case_number: str,
        draft_path: Path,
        initialization: CaseInitialization,
        source_bundle: SourceBundle,
    ) -> str:
        instructions_path = (
            initialization.asset_root / "instructions" / "INSTRUCTIONS.md"
        )
        template_path = initialization.asset_root / "instructions" / "case-template.md"
        return (
            f"Case number: {case_number}\n"
            f"Destination draft path: {draft_path}\n\n"
            "Prepare a complete Nepali Jawafdehi case draft.\n"
            "Follow the workflow instructions and template closely, reconcile the source documents, "
            "and produce a publishable draft in Markdown.\n\n"
            f"{cls._format_document_block('Workflow Instructions', instructions_path)}\n\n"
            f"{cls._format_document_block('Case Template', template_path)}\n\n"
            f"{cls._format_source_documents(source_bundle, total_limit=DRAFT_SOURCE_CHAR_LIMIT)}"
        )

    @classmethod
    def _build_review_prompt(
        cls,
        *,
        case_number: str,
        initialization: CaseInitialization,
        source_bundle: SourceBundle,
        draft_path: Path,
    ) -> str:
        instructions_path = (
            initialization.asset_root / "instructions" / "INSTRUCTIONS.md"
        )
        template_path = initialization.asset_root / "instructions" / "case-template.md"
        return (
            f"Case number: {case_number}\n\n"
            "Review this draft for factual grounding, completeness, and publishability.\n"
            "Be strict about unsupported claims and missing key facts.\n\n"
            f"{cls._format_document_block('Workflow Instructions', instructions_path)}\n\n"
            f"{cls._format_document_block('Case Template', template_path)}\n\n"
            f"{cls._format_document_block('Current Draft', draft_path)}\n\n"
            f"{cls._format_source_documents(source_bundle, total_limit=REVIEW_SOURCE_CHAR_LIMIT)}"
        )

    @classmethod
    def _build_revision_prompt(
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
        return (
            f"Case number: {case_number}\n\n"
            "Revise the draft to resolve the review findings while staying faithful to the sources.\n"
            "Return the full corrected Markdown draft.\n\n"
            f"{cls._format_document_block('Workflow Instructions', instructions_path)}\n\n"
            f"{cls._format_document_block('Case Template', template_path)}\n\n"
            f"{cls._format_document_block('Current Draft', draft_path)}\n\n"
            f"{cls._format_document_block('Review Findings', review_path)}\n\n"
            f"{cls._format_source_documents(source_bundle, total_limit=REVISION_SOURCE_CHAR_LIMIT)}"
        )
