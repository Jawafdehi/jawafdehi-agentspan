"""Verify both patches work: Worker pickling + local function pickling."""
import pickle
from multiprocessing.reduction import ForkingPickler
import io

# Apply patches
from jawafdehi_agentspan.win_compat import apply_patches
apply_patches()

# Test 1: Worker pickling
from conductor.client.worker.worker import Worker
from agentspan.agents.tool import tool

@tool(isolated=False)
def my_tool(x: str) -> str:
    return x

worker = Worker(
    task_definition_name="my_tool",
    execute_function=my_tool,
    poll_interval=100,
    domain=None,
    worker_id=None,
    thread_count=1,
)

try:
    data = pickle.dumps(worker)
    print(f"OK: Worker picklable ({len(data)} bytes)")
except Exception as e:
    print(f"FAIL Worker: {type(e).__name__}: {e}")

# Test 2: Local function pickling via ForkingPickler
def make_closure():
    secret = 42
    def local_fn(x):
        return x + secret
    return local_fn

closure = make_closure()
buf = io.BytesIO()
try:
    ForkingPickler(buf).dump(closure)
    buf.seek(0)
    restored = pickle.loads(buf.read())
    assert restored(10) == 52
    print("OK: Local function picklable via ForkingPickler")
except Exception as e:
    print(f"FAIL local function: {type(e).__name__}: {e}")

# Test 3: Worker with local function via ForkingPickler
def make_worker_fn():
    def router_worker(task):
        return {"result": "routed"}
    return router_worker

local_worker_fn = make_worker_fn()
worker2 = Worker(
    task_definition_name="router",
    execute_function=local_worker_fn,
    poll_interval=100,
    domain=None,
    worker_id=None,
    thread_count=1,
)

buf2 = io.BytesIO()
try:
    ForkingPickler(buf2).dump(worker2)
    buf2.seek(0)
    restored2 = pickle.loads(buf2.read())
    print(f"OK: Worker with local function picklable via ForkingPickler")
except Exception as e:
    print(f"FAIL Worker+local fn: {type(e).__name__}: {e}")

print("\nAll tests passed!" if "FAIL" not in open(__file__).read() else "")
