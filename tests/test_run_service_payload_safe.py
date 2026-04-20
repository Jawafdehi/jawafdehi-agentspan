from __future__ import annotations

from jawafdehi_agentspan.agents.ciaa import build_prepare_information_agent
from jawafdehi_agentspan.settings import Settings


def test_prepare_information_agent_has_payload_safe_toolset() -> None:
    settings = Settings(JAWAFDEHI_API_TOKEN="t", OPENAI_API_KEY="k")
    agent = build_prepare_information_agent(settings)
    tool_names = {
        getattr(tool, "name", getattr(tool, "__name__", str(tool)))
        for tool in agent.tools
    }

    assert "grepNew" in tool_names
    assert "read_file" in tool_names
