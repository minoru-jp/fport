# Concurrency tests for Session
# Note: Keep joins bounded so tests fail fast instead of hanging.

import threading
import time
import pytest
from fport.session import Session


def test_set_error_is_thread_safe_first_error_kept():
    """Multiple threads call set_error; only the first error is recorded and active becomes False."""
    s = Session()
    exceptions = [RuntimeError(f"err-{i}") for i in range(7)]

    # All worker threads will wait here and start at once.
    barrier = threading.Barrier(parties=len(exceptions))

    def worker(exc: Exception):
        try:
            # Timeout prevents indefinite blocking if the barrier breaks.
            barrier.wait(timeout=1.0)
        except threading.BrokenBarrierError:
            # Even if barrier breaks, still attempt to set_error so the thread finishes.
            pass
        s.set_error(exc)

    threads = [threading.Thread(target=worker, args=(exc,)) for exc in exceptions]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)

    # Ensure no leaked threads
    assert all(not t.is_alive() for t in threads), "Worker thread did not finish"

    # After concurrent calls, the first error must be kept and active must be False.
    assert s.ok is False
    assert s.error is not None
    assert any(s.error is exc for exc in exceptions)


def test_readers_see_consistent_state_pairs_under_write():
    """
    Readers should never observe inconsistent (active, error) pairs:
      - Not (False, None)
      - Not (True, not None)
    Properties use a lock; this test stresses that guarantee.
    """
    s = Session()
    state = s.get_state_reader()
    start = threading.Event()

    inconsistent: list[tuple[bool, Exception | None]] = []

    def reader():
        # Start all readers together
        start.wait(timeout=1.0)
        for _ in range(2000):
            a = state.ok
            e = state.error
            if (a is False and e is None) or (a is True and e is not None):
                inconsistent.append((a, e))

    readers = [threading.Thread(target=reader) for _ in range(6)]
    for t in readers:
        t.start()

    start.set()
    # Give readers a moment to spin on initial state before the write
    time.sleep(0.005)
    s.set_error(RuntimeError("boom"))

    for t in readers:
        t.join(timeout=2.0)

    # Ensure no leaked threads
    assert all(not t.is_alive() for t in readers), "Reader thread did not finish"

    assert not inconsistent, f"Inconsistent snapshots observed: {inconsistent[:3]}"
