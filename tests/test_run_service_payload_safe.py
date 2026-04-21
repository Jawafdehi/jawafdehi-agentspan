from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from jawafdehi_agentspan.agents import (
    build_prepare_information_agent,
    build_section_drafter_agent,
    build_short_description_agent,
)
from jawafdehi_agentspan.models import (
    CaseInitialization,
    PublishedCaseResult,
    SourceArtifact,
    SourceBundle,
    WorkspaceContext,
)
from jawafdehi_agentspan.run_service import RunService
from jawafdehi_agentspan.settings import Settings


def test_prepare_information_agent_has_payload_safe_toolset() -> None:
    settings = Settings(JAWAFDEHI_API_TOKEN="t", OPENAI_API_KEY="k")
    agent = build_prepare_information_agent(settings)
    tool_names = {
        getattr(tool, "name", getattr(tool, "__name__", str(tool)))
        for tool in agent.tools
    }

    assert tool_names == {
        "convert_to_markdown",
        "download_file",
        "fetch_url",
        "grepNew",
        "list_files",
        "mkdir",
        "read_file",
        "tree",
        "write_file",
    }


def test_build_section_drafter_agent_configuration() -> None:
    settings = Settings(JAWAFDEHI_API_TOKEN="t", OPENAI_API_KEY="k")
    section = "facts"
    agent = build_section_drafter_agent(settings, section)

    tool_names = {
        getattr(tool, "name", getattr(tool, "__name__", str(tool)))
        for tool in agent.tools
    }
    assert section in agent.name
    assert tool_names == {"read_file", "write_file"}
    assert agent.max_turns == 4
    assert f"Target section: {section}" in agent.instructions


def test_build_short_description_agent_configuration() -> None:
    settings = Settings(JAWAFDEHI_API_TOKEN="t", OPENAI_API_KEY="k")
    agent = build_short_description_agent(settings)

    tool_names = {
        getattr(tool, "name", getattr(tool, "__name__", str(tool)))
        for tool in agent.tools
    }
    assert agent.name == "draft_short_description"
    assert tool_names == {"read_file", "write_file"}
    assert agent.max_turns == 3


class _FakeExecutor:
    STAGED_SHORT_DESCRIPTION = "staged-short-description-from-agent"

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.calls: list[str] = []
        self._sections: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def run(self, agent, prompt: str, output_type=None):
        self.calls.append(agent.name)
        if agent.name.startswith("draft_section_"):
            section = agent.name.removeprefix("draft_section_")
            self._sections.append(section)
            draft_path = self.workspace_root / "draft-final.md"
            draft_path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                (
                    f"## {item.replace('_', ' ').title()}\n"
                    f"Staged content {index + 1}\n"
                )
                for index, item in enumerate(self._sections)
            ]
            draft_path.write_text("\n".join(lines), encoding="utf-8")
        if agent.name == "draft_short_description":
            short_description_path = self.workspace_root / "short-description.txt"
            short_description_path.parent.mkdir(parents=True, exist_ok=True)
            short_description_path.write_text(
                self.STAGED_SHORT_DESCRIPTION,
                encoding="utf-8",
            )
        return None


def test_run_service_persists_payload_safe_artifacts(tmp_path: Path) -> None:
    settings = Settings(
        JAWAFDEHI_API_TOKEN="test-token",
        OPENAI_API_KEY="test-key",
        GLOBAL_STORE_ROOT=str(tmp_path / "global_store"),
        RUNS_ROOT=str(tmp_path / "runs"),
    )
    workspace_root = tmp_path / "workspace"
    workspace = WorkspaceContext(
        root_dir=workspace_root,
        logs_dir=workspace_root / "logs",
        data_dir=workspace_root / "data",
    )
    workspace.logs_dir.mkdir(parents=True, exist_ok=True)
    workspace.data_dir.mkdir(parents=True, exist_ok=True)
    case_details_path = workspace.data_dir / "case_details-081-CR-0046.md"
    case_details_path.write_text("# Case Details", encoding="utf-8")

    initialization = CaseInitialization(
        case_number="081-CR-0046",
        workspace=workspace,
        asset_root=tmp_path,
        case_details_path=case_details_path,
    )
    artifact = SourceArtifact(
        source_type="charge_sheet",
        title="Charge Sheet",
        raw_path=tmp_path / "charge-sheet.pdf",
        markdown_path=tmp_path / "charge-sheet.md",
    )
    source_bundle = SourceBundle(
        case_number="081-CR-0046",
        workspace=workspace,
        asset_root=tmp_path,
        case_details_path=case_details_path,
        source_artifacts=[artifact],
        charge_sheet_artifact=artifact,
    )

    fake_executor = _FakeExecutor(workspace_root)
    service = RunService(
        settings=settings,
        dependencies=object(),
        executor_factory=lambda: fake_executor,
    )
    service._initialize_casework = lambda *_args, **_kwargs: initialization
    service._gather_sources = lambda _initialization: source_bundle
    service._publish_case = lambda _publish_input: PublishedCaseResult(case_id=77)

    result = service._run(
        case_input=type("CaseInput", (), {"case_number": "081-CR-0046"})(),
        workspace_root=workspace_root,
        executor=fake_executor,
    )

    assert result.case_id == 77
    assert fake_executor.calls == [
        "prepare_information",
        "draft_section_title",
        "draft_section_key_allegations",
        "draft_section_timeline",
        "draft_section_description",
        "draft_short_description",
    ]

    draft_final_path = workspace_root / "draft-final.md"
    assert draft_final_path.is_file()
    assert draft_final_path.read_text(encoding="utf-8").strip()

    short_description = (workspace_root / "short-description.txt").read_text(
        encoding="utf-8"
    ).strip()
    assert short_description
    assert short_description == _FakeExecutor.STAGED_SHORT_DESCRIPTION
    assert "orchestrator" not in fake_executor.calls

    traceability_payload = json.loads(
        (workspace_root / "traceability-map.json").read_text(encoding="utf-8")
    )
    assert isinstance(traceability_payload, list)

    validation_payload = json.loads(
        (workspace_root / "validation-report.json").read_text(encoding="utf-8")
    )
    assert isinstance(validation_payload, dict)
    assert {
        "is_valid",
        "missing_sections",
        "unmapped_claims",
        "errors",
    } <= set(validation_payload)


def test_persist_payload_safe_artifacts_rejects_invalid_existing_validation_report(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    draft_final_path = workspace_root / "draft-final.md"
    draft_final_path.write_text("## Title\nExample\n", encoding="utf-8")
    (workspace_root / "validation-report.json").write_text(
        json.dumps({"is_valid": True}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        RunService._persist_payload_safe_artifacts(workspace_root, draft_final_path)
