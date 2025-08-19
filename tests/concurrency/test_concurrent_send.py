import fport.policy
from fport.session import SessionState
import threading

def test_send_does_not_interfere_with_concurrent_processing():
    """Concurrent use of port.send must not serialize or break session state."""

    policy = fport.policy.create_session_policy()
    port = policy.create_port()

    received = []
    lock = threading.Lock()

    def listener(tag, *args, **kwargs):
        # record the message with thread id
        with lock:
            received.append((tag, args[0]))

    N_THREADS = 10
    N_MSG = 100

    def worker(tid: int):
        for i in range(N_MSG):
            port.send("msg", (tid, i))

    with policy.session(listener, port) as state:
        assert isinstance(state, SessionState)
        assert state.ok

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After all threads finished, session must still be ok
        assert state.ok
        assert state.error is None

    # Verify all messages are delivered (order not guaranteed)
    expected = {(tid, i) for tid in range(N_THREADS) for i in range(N_MSG)}
    got = {args for _, args in received}
    assert got == expected

