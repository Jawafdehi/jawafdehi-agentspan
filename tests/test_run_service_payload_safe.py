from __future__ import annotations

from pathlib import Path

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
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def run(self, agent, prompt: str, output_type=None):
        (self.workspace_root / "draft-final.md").write_text(
            "## Description\nPayload-safe draft\n", encoding="utf-8"
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

    service = RunService(
        settings=settings,
        dependencies=object(),
        executor_factory=lambda: _FakeExecutor(workspace_root),
    )
    service._initialize_casework = lambda *_args, **_kwargs: initialization
    service._gather_sources = lambda _initialization: source_bundle
    service._publish_case = lambda _publish_input: PublishedCaseResult(case_id=77)

    result = service._run(
        case_input=type("CaseInput", (), {"case_number": "081-CR-0046"})(),
        workspace_root=workspace_root,
        executor=_FakeExecutor(workspace_root),
    )

    assert result.case_id == 77
    assert (workspace_root / "draft-final.md").is_file()
    assert (workspace_root / "short-description.txt").is_file()
    assert (workspace_root / "traceability-map.json").is_file()
    assert (workspace_root / "validation-report.json").is_file()
