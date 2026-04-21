from __future__ import annotations

import io
import sys

import pytest
from conductor.client.worker.worker import Worker

from jawafdehi_agentspan.win_compat import apply_patches

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-only multiprocessing spawn compatibility tests",
)


def _sample_tool(file_path: str) -> str:
    return file_path


def test_make_tool_worker_registers_pickle_reference():
    apply_patches()

    import agentspan.agents.runtime._dispatch as dispatch

    tool_worker = dispatch.make_tool_worker(_sample_tool, "sample_tool")

    assert getattr(dispatch, tool_worker.__name__, None) is tool_worker


def test_dispatch_tool_worker_serializes_inside_worker():
    apply_patches()

    import agentspan.agents.runtime._dispatch as dispatch
    import multiprocessing.reduction as reduction

    tool_worker = dispatch.make_tool_worker(_sample_tool, "sample_tool")
    worker = Worker(
        task_definition_name="sample_tool",
        execute_function=tool_worker,
        poll_interval=100,
        domain=None,
        worker_id=None,
        thread_count=1,
    )

    reduction.dump(worker, io.BytesIO())
