"""Test: HybridPickler with copyreg and _extra_reducers properly merged."""
import pickle
import io
import types
import copyreg
import cloudpickle
from multiprocessing.reduction import ForkingPickler
import multiprocessing.reduction as reduction


class HybridPickler(cloudpickle.Pickler):
    """Cloudpickle-based pickler that also knows ForkingPickler's reducers."""
    
    _extra_reducers = ForkingPickler._extra_reducers.copy()

    def __init__(self, file, protocol=None, buffer_callback=None):
        super().__init__(file, protocol=protocol, buffer_callback=buffer_callback)
        # Merge ForkingPickler's extra reducers into our dispatch_table
        # This handles mp-specific types like Connection, Socket, etc.
        self.dispatch_table.update(self._extra_reducers)


def _hybrid_dump(obj, file, protocol=None):
    HybridPickler(file, protocol).dump(obj)


reduction.dump = _hybrid_dump


# Patch Worker
from jawafdehi_agentspan.win_compat import _worker_getstate, _worker_setstate
from conductor.client.worker.worker import Worker
Worker.__getstate__ = _worker_getstate
Worker.__setstate__ = _worker_setstate


# Test 1: local function through reduction.dump
def make_fn():
    secret = 42
    def inner(x):
        return x + secret
    return inner

fn = make_fn()
buf = io.BytesIO()
try:
    _hybrid_dump(fn, buf)
    buf.seek(0)
    restored = pickle.loads(buf.read())
    print(f"OK: local fn result={restored(10)}")
except Exception as e:
    print(f"FAIL local fn: {type(e).__name__}: {e}")


# Test 2: Worker with local function
def make_worker_fn():
    def router_worker(task):
        return {"result": "routed"}
    return router_worker

router_fn = make_worker_fn()
worker = Worker(
    task_definition_name="test_router",
    execute_function=router_fn,
    poll_interval=100,
    domain=None,
    worker_id=None,
    thread_count=1,
)
buf2 = io.BytesIO()
try:
    _hybrid_dump(worker, buf2)
    buf2.seek(0)
    restored_w = pickle.loads(buf2.read())
    print(f"OK: Worker name={restored_w.task_definition_name}")
except Exception as e:
    print(f"FAIL Worker: {type(e).__name__}: {e}")


# Test 3: Full Process object (what multiprocessing actually serializes)
from multiprocessing import Process
from conductor.client.configuration.configuration import Configuration
from conductor.client.automator.task_handler import _run_sync_worker_process

config = Configuration(server_api_url="http://localhost:6767/api")
proc = Process(
    target=_run_sync_worker_process,
    args=(worker, config, None, [])
)
proc.daemon = True

buf3 = io.BytesIO()
try:
    _hybrid_dump(proc, buf3)
    print("OK: Full Process object serialized")
except Exception as e:
    print(f"FAIL Process: {type(e).__name__}: {e}")
