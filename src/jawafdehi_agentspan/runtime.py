from __future__ import annotations

import json
import logging
import time
from contextlib import AbstractContextManager
from typing import Any, Protocol, TypeVar

from agentspan.agents import Agent, AgentRuntime
from pydantic import BaseModel

from jawafdehi_agentspan.settings import Settings

T = TypeVar("T")


class AgentExecutor(Protocol):
    def run(
        self, agent: Agent, prompt: str, output_type: type[T] | None = None
    ) -> T | Any: ...


class AgentSpanExecutor(AbstractContextManager["AgentSpanExecutor"]):
    logger = logging.getLogger(__name__)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime = AgentRuntime(
            server_url=settings.agentspan_server_url,
            api_key=settings.agentspan_auth_key,
            api_secret=settings.agentspan_auth_secret,
        )

    def __enter__(self) -> "AgentSpanExecutor":
        self.runtime.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.runtime.__exit__(exc_type, exc, tb)

    @staticmethod
    def _unwrap_output(output: Any) -> Any:
        if not isinstance(output, dict):
            return output
        if "result" not in output:
            return output
        wrapper_keys = {"result", "finishReason", "context", "media"}
        if set(output).issubset(wrapper_keys):
            return output["result"]
        return output

    @staticmethod
    def _should_retry_error(error: str | None) -> bool:
        if not error:
            return False
        lowered = error.lower()
        return "cooling down" in lowered or "429" in lowered or "rate limit" in lowered

    @staticmethod
    def _preview_text(value: Any, *, limit: int = 800) -> str:
        if isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(value, ensure_ascii=False, default=str)
            except TypeError:
                text = repr(value)
        if len(text) <= limit:
            return text
        return text[:limit] + "...<truncated>"

    def run(
        self, agent: Agent, prompt: str, output_type: type[T] | None = None
    ) -> T | Any:
        last_error = "AgentSpan execution failed"
        max_attempts = 6
        for attempt in range(max_attempts):
            result = self.runtime.run(agent, prompt)
            if not result.is_failed:
                break
            last_error = result.error or last_error
            if attempt == max_attempts - 1 or not self._should_retry_error(
                result.error
            ):
                raise RuntimeError(last_error)
            delay = min(30 * (attempt + 1), 120)
            logging.getLogger(__name__).warning(
                "Agent '%s' rate-limited (attempt %d/%d), retrying in %ds",
                agent.name,
                attempt + 1,
                max_attempts,
                delay,
            )
            time.sleep(delay)

        output = self._unwrap_output(result.output)
        self.logger.debug(
            "Agent '%s' raw output type=%s preview=%s",
            agent.name,
            type(result.output).__name__,
            self._preview_text(result.output),
        )
        self.logger.debug(
            "Agent '%s' unwrapped output type=%s preview=%s",
            agent.name,
            type(output).__name__,
            self._preview_text(output),
        )
        if output_type is None:
            return output
        if isinstance(output, output_type):
            return output
        if isinstance(output_type, type) and issubclass(output_type, BaseModel):
            expected_fields = list(output_type.model_fields)
            actual_fields = list(output) if isinstance(output, dict) else None
            self.logger.debug(
                "Agent '%s' validating against model=%s "
                "expected_fields=%s actual_fields=%s",
                agent.name,
                output_type.__name__,
                expected_fields,
                actual_fields,
            )
            try:
                if isinstance(output, str):
                    return output_type.model_validate_json(output)
                return output_type.model_validate(output)
            except Exception:
                self.logger.exception(
                    "Agent '%s' failed model validation for %s with output preview=%s",
                    agent.name,
                    output_type.__name__,
                    self._preview_text(output),
                )
                raise
        return output
