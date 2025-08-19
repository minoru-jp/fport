import fport.policy
from fport.exceptions import DeniedError
import threading
import time

def test_massive_concurrent_send_noop_stress():
    """Stress test: NoopPort.send must silently ignore all calls, even under heavy load."""

    policy = fport.policy.create_session_policy(block_port=True)
    port = policy.create_port()  # this will be a NoopPort

    N_THREADS = 50
    N_MSG = 5000

    def worker(tid: int):
        for i in range(N_MSG):
            port.send("msg", (tid, i))  # should do nothing

    start = time.time()

    # NoopPort cannot start a session at all
    try:
        with policy.session(lambda tag, *a, **kw: None, port):
            raise AssertionError("NoopPort must not allow sessions")
    except DeniedError:
        pass

    # Run concurrent send calls
    threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.time() - start

    # Nothing to assert about messages (they are ignored),
    # just check we survived without exceptions
    print(f"Noop stress test completed: {N_THREADS * N_MSG} ignored messages in {elapsed:.2f}s")

