from __future__ import annotations

from jawaf_span.runtime import AgentSpanExecutor


def test_unwrap_output_returns_inner_result_for_agentspan_wrapper():
    wrapped = {
        "result": {"score": 9, "outcome": "approved"},
        "finishReason": "STOP",
        "context": {},
    }

    assert AgentSpanExecutor._unwrap_output(wrapped) == {
        "score": 9,
        "outcome": "approved",
    }


def test_unwrap_output_preserves_regular_dicts():
    payload = {"score": 9, "outcome": "approved"}

    assert AgentSpanExecutor._unwrap_output(payload) == payload


def test_should_retry_error_matches_cooldown_and_rate_limit():
    assert AgentSpanExecutor._should_retry_error(
        "429: All credentials for model gpt-5.4 are cooling down via provider codex"
    )
    assert AgentSpanExecutor._should_retry_error("rate limit exceeded")
    assert not AgentSpanExecutor._should_retry_error("validation failed")
