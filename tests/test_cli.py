from __future__ import annotations

from typer.testing import CliRunner

from jawafdehi_agentspan.cli import app
from jawafdehi_agentspan.models import ReviewOutcome, WorkflowResult


def test_cli_run_publishes_case(monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("JAWAFDEHI_API_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    class FakeRunService:
        def start_run(self, case_number: str) -> WorkflowResult:
            return WorkflowResult(
                case_number=case_number,
                published=True,
                case_id=42,
                final_outcome=ReviewOutcome.approved,
            )

    monkeypatch.setattr("jawafdehi_agentspan.cli.RunService", lambda: FakeRunService())
    result = runner.invoke(app, ["run", "081-CR-0046"])

    assert result.exit_code == 0
    assert "Published Jawafdehi case 42" in result.stdout


def test_cli_rejects_invalid_case_number(monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("JAWAFDEHI_API_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    result = runner.invoke(app, ["run", "bad-case-number"])
    assert result.exit_code != 0
