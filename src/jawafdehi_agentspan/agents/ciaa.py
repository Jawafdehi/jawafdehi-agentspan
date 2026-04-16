from __future__ import annotations

from pathlib import Path

from agentspan.agents import Agent

from jawafdehi_agentspan.models import (
    CaseInitialization,
    Critique,
    OrchestratedRefinementOutput,
    PublishedCaseResult,
    SourceBundle,
)
from jawafdehi_agentspan.settings import Settings
from jawafdehi_agentspan.tools import (
    append_global_source_file,
    brave_search,
    convert_to_markdown,
    fetch_url,
    gather_news_step,
    gather_sources_step,
    initialize_casework_step,
    list_global_source_files,
    list_workspace_files,
    publish_case_step,
    write_global_source_file,
)

_HERE = Path(__file__).parent


def _load(filename: str) -> str:
    return (_HERE / filename).read_text(encoding="utf-8").strip()


def build_initialize_agent(settings: Settings) -> Agent:
    return Agent(
        name="ciaa_initialize",
        model=settings.llm_model,
        instructions=(
            "Initialize a CIAA casework run. "
            "Call initialize_casework_step exactly once using the case "
            "number and workspace path from the prompt, then return the "
            "structured initialization payload."
        ),
        tools=[initialize_casework_step],
        required_tools=["initialize_casework_step"],
        output_type=CaseInitialization,
        max_turns=2,
    )


def build_source_agent(settings: Settings) -> Agent:
    return Agent(
        name="ciaa_source_gatherer",
        model=settings.llm_model,
        instructions=(
            "Gather official case sources. "
            "Call gather_sources_step exactly once using the serialized "
            "initialization payload from the prompt, then return the "
            "updated source bundle."
        ),
        tools=[gather_sources_step],
        required_tools=["gather_sources_step"],
        output_type=SourceBundle,
        max_turns=2,
    )


def build_news_agent(settings: Settings) -> Agent:
    return Agent(
        name="ciaa_news_gatherer",
        model=settings.llm_model,
        instructions=(
            "Gather relevant news coverage. "
            "Call gather_news_step exactly once using the serialized "
            "source bundle from the prompt, then return the updated "
            "source bundle."
        ),
        tools=[gather_news_step, brave_search, fetch_url, convert_to_markdown],
        required_tools=["gather_news_step"],
        output_type=SourceBundle,
        max_turns=2,
    )


def build_draft_agent(settings: Settings) -> Agent:
    instructions = "\n\n".join(
        [
            _load("drafter.md"),
            _load("case-template.md"),
            (
                "Source documents are not embedded inline. Some live in the run "
                "workspace and others live in the global source store. Use the "
                "provided source manifest plus the default filesystem read tool to "
                "inspect source files as needed, including specific lines when "
                "helpful. Prefer markdown files over raw files."
            ),
        ]
    )
    return Agent(
        name="ciaa_drafter",
        model=settings.llm_model,
        instructions=instructions,
        tools=[
            list_workspace_files,
            list_global_source_files,
            write_global_source_file,
            append_global_source_file,
        ],
        max_turns=2,
    )


def build_review_agent(settings: Settings) -> Agent:
    instructions = "\n\n".join(
        [
            _load("reviewer.md"),
            (
                "Source documents are not embedded inline. Some live in the run "
                "workspace and others live in the global source store. Use the "
                "provided source manifest plus the default filesystem read tool to "
                "inspect source files as needed, including specific lines when "
                "helpful. Prefer markdown files over raw files."
            ),
        ]
    )
    return Agent(
        name="ciaa_reviewer",
        model=settings.llm_model,
        instructions=instructions,
        tools=[
            list_workspace_files,
            list_global_source_files,
        ],
        max_turns=2,
    )


def build_critique_extractor(settings: Settings) -> Agent:
    return Agent(
        name="ciaa_critique_extractor",
        model=settings.llm_model,
        instructions=(
            "Extract a structured critique from the provided review text. "
            "You are a deterministic JSON extractor, not a reviewer. "
            "Never return an empty object, prose, markdown, or code fences. "
            "Always return all required fields in valid JSON: "
            "score (integer 1-10), outcome (one of: "
            '"approved", "approved_with_minor_edits", '
            '"needs_revision", "blocked"), '
            "strengths (array of strings), improvements (array of strings), "
            "blockers (array of strings). "
            "Infer the outcome from the review recommendation even if "
            "phrased informally. "
            "Infer the score conservatively from the review if needed. "
            "If the review recommends revision, set outcome to needs_revision. "
            "If the review says blocked or identifies blocking factual "
            "issues, set outcome to blocked. "
            "If the review is positive with only small edits, set outcome "
            "to approved_with_minor_edits or approved as appropriate. "
            "Lists may be empty, but the keys must always be present. "
            "Do not use any tools. Return only the JSON object."
        ),
        output_type=Critique,
        max_turns=2,
    )


def build_revise_agent(settings: Settings) -> Agent:
    instructions = "\n\n".join(
        [
            _load("reviser.md"),
            (
                "Revise the provided draft to address every critical and major "
                "issue, plus straightforward minor ones. "
                "All content is provided inline in the prompt - do not attempt "
                "to read files or call any tools. "
                "Return only the improved Nepali Markdown draft text, without "
                "code fences."
            ),
        ]
    )
    return Agent(
        name="ciaa_reviser",
        model=settings.llm_model,
        instructions=instructions,
        max_turns=2,
    )


def build_publish_agent(settings: Settings) -> Agent:
    return Agent(
        name="ciaa_publisher",
        model=settings.llm_model,
        instructions=(
            "Publish and finalize the approved case. "
            "Call publish_case_step exactly once using the serialized "
            "publish payload from the prompt, then return the structured "
            "publication result."
        ),
        tools=[publish_case_step],
        required_tools=["publish_case_step"],
        output_type=PublishedCaseResult,
        max_turns=2,
    )


def build_refinement_orchestrator(settings: Settings) -> Agent:
    return Agent(
        name="ciaa_refinement_orchestrator",
        model=settings.llm_model,
        instructions=(
            "You orchestrate a single CIAA draft-refinement workflow across "
            "specialist sub-agents. "
            "Initialization, source gathering, and news gathering are already "
            "complete in Python before this agent starts. "
            "Do not call initialize, source gathering, or news gathering "
            "specialists. "
            "Begin from the provided case context and source documents, then "
            "use only the drafting, review, critique extraction, and "
            "optional single revision specialists. "
            "If the extracted critique says blocked, stop and return the "
            "final blocked result. "
            "If the extracted critique says approved or "
            "approved_with_minor_edits and the score is at least 8, stop and "
            "return the final result. "
            "Otherwise, you may use the reviser exactly once, then run "
            "reviewer and critique extractor one more time. "
            "Never revise more than once. Never publish. "
            "Return only the final structured "
            "OrchestratedRefinementOutput with the final draft, final review, "
            "final critique, whether revision was used, and the initial "
            "critique when a revision happened."
        ),
        agents=[
            build_draft_agent(settings),
            build_review_agent(settings),
            build_critique_extractor(settings),
            build_revise_agent(settings),
        ],
        strategy="handoff",
        output_type=OrchestratedRefinementOutput,
        max_turns=6,
    )
