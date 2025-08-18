import standman.policy
from standman.session import SessionState
import threading
import time

def test_massive_concurrent_send_stress():
    """Stress test: Port.send under heavy concurrent load must not break session integrity."""

    policy = standman.policy.create_session_policy()
    port = policy.create_port()

    received = []
    lock = threading.Lock()

    def listener(tag, *args, **kwargs):
        with lock:
            received.append((tag, args[0]))

    N_THREADS = 50     # more threads
    N_MSG = 5000       # more messages per thread

    def worker(tid: int):
        for i in range(N_MSG):
            port.send("msg", (tid, i))

    start = time.time()
    with policy.session(listener, port) as state:
        assert isinstance(state, SessionState)
        assert state.ok

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert state.ok
        assert state.error is None

    elapsed = time.time() - start

    # Verify all messages are delivered
    expected = {(tid, i) for tid in range(N_THREADS) for i in range(N_MSG)}
    got = {args for _, args in received}
    assert got == expected

    # Optional: log or assert on elapsed time (sanity check, not performance bound)
    print(f"Stress test completed: {N_THREADS * N_MSG} messages in {elapsed:.2f}s")
