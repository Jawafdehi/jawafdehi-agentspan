from __future__ import annotations

from pathlib import Path

from agentspan.agents import Agent, ConversationMemory

from jawafdehi_agentspan.assets import ciaa_ag_index_path
from jawafdehi_agentspan.models import (
    PublishedCaseResult,
    SourceBundle,
)
from jawafdehi_agentspan.settings import Settings
from jawafdehi_agentspan.tools import (
    brave_search,
    convert_to_markdown,
    download_file,
    fetch_url,
    gather_news_step,
    grep,
    list_files,
    publish_case_step,
    read_file,
    tree,
    write_file,
)

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "prompts"


def _load(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def _memory() -> ConversationMemory:
    return ConversationMemory(max_messages=100)


def build_file_system_prompt(settings: Settings, *, case_number: str, workspace_root: Path) -> str:
    template = _load("filesystem.md")
    data_dir = ciaa_ag_index_path().parent
    return (
        template
        .replace("{global_store_root}", str(settings.global_store_root.resolve()))
        .replace("{case_number}", case_number)
        .replace("{workspace_root}", str(workspace_root.resolve()))
        .replace("{data_dir}", str(data_dir.resolve()))
    )


def build_news_agent(settings: Settings) -> Agent:
    # TODO: We don't need news agent right now.
    # This will be worked upon later.
    return Agent(
        name="ciaa_news_gatherer",
        model=settings.llm_model,
        instructions=_load("news-gatherer.md"),
        tools=[gather_news_step, brave_search, fetch_url, convert_to_markdown],
        required_tools=["gather_news_step"],
        output_type=SourceBundle,
        memory=_memory(),
        max_turns=2,
    )


def build_draft_agent(settings: Settings) -> Agent:
    return Agent(
        name="create_ciaa_case_draft",
        model=settings.llm_model,
        instructions="\n\n".join([_load("drafter.md"), _load("case-template.md")]),
        tools=[read_file, write_file],
        memory=_memory(),
        max_turns=10,
    )


def build_review_agent(settings: Settings) -> Agent:
    return Agent(
        name="draft_reviewer",
        model=settings.llm_model,
        instructions=_load("reviewer.md"),
        tools=[read_file, write_file],
        memory=_memory(),
        max_turns=10,
    )


def build_critique_extractor(settings: Settings) -> Agent:
    return Agent(
        name="review_critique",
        model=settings.llm_model,
        instructions=_load("critique-extractor.md"),
        memory=_memory(),
        max_turns=2,
    )


def build_revise_agent(settings: Settings) -> Agent:
    return Agent(
        name="case_revisor",
        model=settings.llm_model,
        instructions=_load("reviser.md"),
        memory=_memory(),
        max_turns=2,
    )


def build_publish_agent(settings: Settings) -> Agent:
    return Agent(
        name="case_publisher",
        model=settings.llm_model,
        instructions=_load("publisher.md"),
        tools=[publish_case_step],
        required_tools=["publish_case_step"],
        output_type=PublishedCaseResult,
        memory=_memory(),
        max_turns=2,
    )


def build_case_draft_router(settings: Settings) -> Agent:
    return Agent(
        name="case_draft_router",
        model=settings.llm_model,
        instructions=_load("case-draft-router.md"),
        memory=_memory(),
    )


def build_case_draft_agent(settings: Settings) -> Agent:
    return Agent(
        name="case_draft",
        model=settings.llm_model,
        instructions=_load("case-draft.md"),
        agents=[
            build_draft_agent(settings),
            build_review_agent(settings),
            build_critique_extractor(settings),
            build_revise_agent(settings),
        ],
        strategy="router",
        router=build_case_draft_router(settings),
        memory=_memory(),
        max_turns=8,
    )


def build_prepare_information_agent(settings: Settings) -> Agent:
    return Agent(
        name="prepare_information",
        model=settings.llm_model,
        instructions=_load("prepare-information.md"),
        tools=[read_file, write_file, list_files, tree, grep, fetch_url, download_file, convert_to_markdown],
        memory=_memory(),
        max_turns=20,
    )


def build_ciaa_orchestrator(settings: Settings, router) -> Agent:
    return Agent(
        name="orchestrator",
        model=settings.llm_model,
        instructions=_load("orchestrator.md"),
        agents=[
            build_prepare_information_agent(settings),
            build_case_draft_agent(settings),
            # build_publish_agent(settings),
        ],
        strategy="router",
        router=router,
        max_turns=6,
    )
