from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from jawafdehi_agentspan.agents import (
    build_ciaa_orchestrator,
    build_file_system_prompt,
    build_prepare_information_agent,
    build_section_drafter_agent,
    build_short_description_agent,
)
from jawafdehi_agentspan.assets import ciaa_workflow_root
from jawafdehi_agentspan.dependencies import (
    build_default_dependencies,
    use_dependencies,
)
from jawafdehi_agentspan.evidence.contracts import TraceabilityEntry, ValidationReport
from jawafdehi_agentspan.evidence.finalizer import ensure_missing_data_marker
from jawafdehi_agentspan.logging_utils import configure_run_logging
from jawafdehi_agentspan.models import (
    CaseInitialization,
    CIAACaseInput,
    PublishInput,
    SourceBundle,
    WorkflowResult,
)
from jawafdehi_agentspan.runtime import AgentExecutor, AgentSpanExecutor
from jawafdehi_agentspan.settings import Settings, get_settings
from jawafdehi_agentspan.workspace import (
    build_case_initialization,
    create_workspace,
    global_raw_sources_dir,
)

logger = logging.getLogger(__name__)
_SECTION_DRAFT_SEQUENCE = ("title", "key_allegations", "timeline", "description")


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
        self.dependencies = dependencies or build_default_dependencies(self.settings)
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

        prompt = self._build_prompt(
            case_number=case_input.case_number,
            workspace_root=workspace_root,
            source_bundle=source_bundle,
            settings=self.settings,
        )
        staged_flow_failed = False
        try:
            self._run_payload_safe_stages(
                case_number=case_input.case_number,
                workspace_root=workspace_root,
                prompt=prompt,
                executor=executor,
            )
        except Exception:
            staged_flow_failed = True
            logger.exception(
                "Payload-safe staged flow failed for %s; falling back to orchestrator.",
                case_input.case_number,
            )

        draft_final_path = workspace_root / "draft-final.md"
        if (
            staged_flow_failed
            or not draft_final_path.is_file()
            or draft_final_path.stat().st_size == 0
        ):
            router = self._make_router(
                case_number=case_input.case_number,
                workspace_root=workspace_root,
            )
            logger.debug(
                "Falling back to orchestrator for %s because staged drafting did not"
                " produce draft-final.md",
                case_input.case_number,
            )
            logger.debug(
                "Orchestrator prompt for %s:\n%s",
                case_input.case_number,
                prompt,
            )
            executor.run(build_ciaa_orchestrator(self.settings, router), prompt)
        _validate_required_output(draft_final_path)
        self._persist_payload_safe_artifacts(workspace_root, draft_final_path)

        published_case = self._publish_case(
            PublishInput(
                case_number=case_input.case_number,
                source_bundle=source_bundle,
                draft_path=draft_final_path,
            )
        )
        return WorkflowResult(
            case_number=case_input.case_number,
            published=True,
            case_id=published_case.case_id,
        )

    def _run_payload_safe_stages(
        self,
        *,
        case_number: str,
        workspace_root: Path,
        prompt: str,
        executor: AgentExecutor,
    ) -> None:
        logger.debug("Starting payload-safe staged flow for %s", case_number)
        executor.run(build_prepare_information_agent(self.settings), prompt)

        for section_name in _SECTION_DRAFT_SEQUENCE:
            section_prompt = (
                f"{prompt}\n\n"
                f"Stage: draft section '{section_name}' into draft-final.md for"
                " this case."
            )
            executor.run(
                build_section_drafter_agent(self.settings, section_name),
                section_prompt,
            )

        short_description_prompt = (
            f"{prompt}\n\n"
            "Stage: write short-description.txt using the current draft-final.md."
        )
        executor.run(
            build_short_description_agent(self.settings),
            short_description_prompt,
        )
        logger.debug(
            "Completed payload-safe staged flow for %s in workspace %s",
            case_number,
            workspace_root,
        )

    def _make_router(self, *, case_number: str, workspace_root: Path):
        raw_sources_dir = global_raw_sources_dir(case_number, self.settings)
        draft_final_path = workspace_root / "draft-final.md"

        def _press_release_exists() -> bool:
            for ext in ("pdf", "doc", "docx", "html", "md"):
                if any(raw_sources_dir.glob(f"ciaa-press-release-*.{ext}")):
                    return True
            return False

        def route(prompt: str) -> str:
            if not _press_release_exists():
                return "prepare_information"
            if not draft_final_path.is_file():
                return "case_draft"
            return "case_publisher"

        return route

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
            settings=self.settings,
        )

    def _gather_sources(self, initialization: CaseInitialization) -> SourceBundle:
        return _run_async(
            self.dependencies.source_gatherer.gather_sources(initialization)
        )

    def _publish_case(self, publish_input: PublishInput):
        return _run_async(
            self.dependencies.publish_finalizer.publish_and_finalize(publish_input)
        )

    @classmethod
    def _extract_short_description_from_draft(cls, draft_markdown: str) -> str:
        match = re.search(
            r"(?ms)^##\s*Short Description\s*\n(.*?)(?=^##\s|\Z)",
            draft_markdown,
        )
        if match:
            return match.group(1).strip()

        for line in draft_markdown.splitlines():
            normalized = line.strip()
            if normalized and not normalized.startswith("#"):
                return normalized
        return "No short description available."

    @classmethod
    def _load_traceability_entries(
        cls, traceability_map_path: Path
    ) -> list[TraceabilityEntry]:
        if not traceability_map_path.is_file():
            return []

        payload = json.loads(traceability_map_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("traceability-map.json must contain a JSON list")
        return [TraceabilityEntry.model_validate(entry) for entry in payload]

    @classmethod
    def _build_validation_report(
        cls, traceability_entries: list[TraceabilityEntry]
    ) -> ValidationReport:
        unmapped_claims = [
            entry.claim_text for entry in traceability_entries if not entry.source_refs
        ]
        errors = ["unmapped claims found"] if unmapped_claims else []
        return ValidationReport(
            is_valid=not errors,
            missing_sections=[],
            unmapped_claims=unmapped_claims,
            errors=errors,
        )

    @classmethod
    def _persist_payload_safe_artifacts(
        cls, workspace_root: Path, draft_final_path: Path
    ) -> None:
        draft_markdown = draft_final_path.read_text(encoding="utf-8")
        normalized_draft = ensure_missing_data_marker(draft_markdown)
        if normalized_draft != draft_markdown:
            draft_final_path.write_text(normalized_draft, encoding="utf-8")

        short_description_path = workspace_root / "short-description.txt"
        traceability_map_path = workspace_root / "traceability-map.json"
        validation_report_path = workspace_root / "validation-report.json"

        if not short_description_path.is_file():
            draft_markdown = draft_final_path.read_text(encoding="utf-8")
            short_description = cls._extract_short_description_from_draft(
                draft_markdown
            )
            short_description_path.write_text(short_description, encoding="utf-8")

        traceability_entries = cls._load_traceability_entries(traceability_map_path)
        if not traceability_map_path.is_file():
            traceability_map_path.write_text(
                json.dumps(
                    [entry.model_dump() for entry in traceability_entries],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        if validation_report_path.is_file():
            payload = json.loads(validation_report_path.read_text(encoding="utf-8"))
            ValidationReport.model_validate(payload)

        report = cls._build_validation_report(traceability_entries)
        validation_report_path.write_text(
            json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        _validate_required_output(short_description_path)
        _validate_required_output(traceability_map_path)
        _validate_required_output(validation_report_path)

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
    def _build_prompt(
        cls,
        *,
        case_number: str,
        workspace_root: Path,
        source_bundle: SourceBundle,
        settings: Settings,
    ) -> str:
        filesystem_prompt = build_file_system_prompt(
            settings, case_number=case_number, workspace_root=workspace_root
        )
        source_manifest = cls._format_source_manifest(source_bundle)
        return (
            f"Case number: {case_number}\n\n"
            f"{filesystem_prompt}\n\n"
            "## Source Manifest\n\n"
            f"{source_manifest}"
        )
