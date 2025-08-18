import standman.policy
from standman.session import SessionState

def test_massive_send_integrity():
    """Port.send can be called many times without breaking SessionState integrity."""

    policy = standman.policy.create_session_policy()
    port = policy.create_port()

    received = []

    def listener(tag, *args, **kwargs):
        received.append((tag, args, kwargs))

    N = 100000  # number of messages to send

    with policy.session(listener, port) as state:
        assert isinstance(state, SessionState)
        assert state.ok
        assert state.error is None

        for i in range(N):
            port.send("msg", i, key=i)

        # Session must remain active and error-free
        assert state.ok
        assert state.error is None

    # Listener must have received all messages
    assert len(received) == N
    assert all(tag == "msg" for tag, _, _ in received)
    assert set(arg[0] for _, arg, _ in received) == set(range(N))

