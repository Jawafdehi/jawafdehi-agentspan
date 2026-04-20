from __future__ import annotations

from jawafdehi_agentspan.agents import (
    build_prepare_information_agent,
    build_section_drafter_agent,
    build_short_description_agent,
)
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
