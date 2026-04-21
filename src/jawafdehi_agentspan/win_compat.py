"""Windows compatibility patches for agentspan/conductor-python.

On Windows, ``multiprocessing`` uses the ``spawn`` start method, which
requires pickling all ``Process`` arguments.  Two issues arise:

1. The Conductor ``Worker`` class contains unpicklable attributes
   (``api_client`` with an ``_thread.RLock``, ``_pending_tasks_lock``
   which is a ``_thread.lock``).

2. Agentspan registers local/nested functions (e.g. router_worker
   closures) as Conductor workers.  Standard ``pickle`` cannot
   serialize local functions because they are not importable by
   qualified name.

This module applies patches to handle these issues on Windows.

Call :func:`apply_patches` once at startup (before any ``TaskHandler``
is created).
"""

from __future__ import annotations

import sys
import threading
import types


def _worker_getstate(self):
    """Exclude unpicklable attrs when pickling a Conductor Worker."""
    state = self.__dict__.copy()
    # api_client holds an RLock internally
    state.pop("api_client", None)
    # _pending_tasks_lock is a threading.Lock
    state.pop("_pending_tasks_lock", None)
    return state


def _worker_setstate(self, state):
    """Restore unpicklable attrs after unpickling a Conductor Worker."""
    self.__dict__.update(state)
    # Re-create the lock
    self._pending_tasks_lock = threading.Lock()
    # Re-create api_client lazily — TaskRunner reconstructs it anyway
    self.api_client = None


_patches_applied = False


def apply_patches() -> None:
    """Apply Windows compatibility patches if running on Windows."""
    global _patches_applied
    if _patches_applied:
        return
    _patches_applied = True

    if sys.platform != "win32":
        return

    # -- Patch 1: Make Worker picklable ----------------------------------
    try:
        from conductor.client.worker.worker import Worker
    except ImportError:
        pass
    else:
        # Only patch if not already patched by us.  Python 3.11+ exposes
        # ``object.__getstate__`` on every class, so ``hasattr`` always
        # returns True.  We check the class's own __dict__ instead.
        if "__getstate__" not in Worker.__dict__:
            Worker.__getstate__ = _worker_getstate
            Worker.__setstate__ = _worker_setstate

    # -- Patch 2: Use cloudpickle for all multiprocessing ---------------
    # The core issue is that dynamically created tool workers from agentspan
    # aren't importable by name in child processes. We need to use cloudpickle
    # for ALL multiprocessing serialization on Windows.
    try:
        import cloudpickle
        import multiprocessing.reduction as reduction
        from multiprocessing.reduction import ForkingPickler
        import pickle

        class CloudForkingPickler(ForkingPickler):
            """ForkingPickler that uses cloudpickle for functions only."""

            def reducer_override(self, obj):
                """Use cloudpickle for function objects only."""
                if isinstance(obj, types.FunctionType):
                    # Use cloudpickle for all functions to handle dynamically created ones
                    try:
                        return cloudpickle.loads, (cloudpickle.dumps(obj),)
                    except Exception:
                        # If cloudpickle fails, fall back to standard pickling
                        pass
                # Let the parent class handle everything else
                return NotImplemented

        def _cloud_dump(obj, file, protocol=None):
            """Drop-in replacement for reduction.dump using CloudForkingPickler."""
            CloudForkingPickler(file, protocol).dump(obj)

        # Replace both dump and the ForkingPickler class
        reduction.dump = _cloud_dump
        reduction.ForkingPickler = CloudForkingPickler

    except ImportError:
        pass

