import pytest
import standman
from standman.session import Session, SessionState

def test_session_initial_state():
    """New Session starts active with no error."""
    s = Session()
    assert s.ok is True
    assert s.error is None

def test_set_error_transitions_and_freezes_first_error():
    """set_error() marks inactive and preserves the first error."""
    s = Session()
    err1 = RuntimeError("first")
    s.set_error(err1)
    assert s.ok is False
    assert s.error is err1  # first error is kept

    # Subsequent errors must not overwrite the first one
    err2 = ValueError("second")
    s.set_error(err2)
    assert s.error is err1

def test_state_reader_reflects_and_is_read_only():
    """State reader mirrors Session and is read-only (no setters)."""
    s = Session()
    state = s.get_state_reader()

    # Mirrors initial state
    assert state.ok is True
    assert state.error is None

    # After an error, the reader reflects the change
    s.set_error(RuntimeError("boom"))
    assert state.ok is False
    assert isinstance(state.error, RuntimeError)

    # Read-only: properties have no setters
    with pytest.raises(AttributeError):
        state.ok = True  # type: ignore[attr-defined]


def test_session_state_set_error_updates_ok_and_error():
    """Session.set_error() must set ok=False and store the exception in the session state."""
    role = standman.policy._create_session_policy_role()
    core = role.core
    port = core.create_port()

    def listener(tag: str, *args, **kwargs):
        pass

    with core.session(listener, port) as session_state:
        assert isinstance(session_state, SessionState)
        assert session_state.ok
        assert session_state.error is None

        # Access the underlying Session instance
        session = role.state.session_map[port]
        assert isinstance(session, Session)

        # Call set_error explicitly on Session
        class DummyError(Exception):
            pass

        exc = DummyError("something went wrong")
        session.set_error(exc)

        # State reader must reflect the error
        assert not session_state.ok
        assert isinstance(session_state.error, DummyError)
        assert session_state.error is exc

def test_session_state_reflects_listener_exception():
    """If a listener raises an exception, the session state must record it and mark ok=False."""
    policy = standman.policy.create_session_policy()
    port = policy.create_port()

    class CustomError(Exception):
        pass

    def bad_listener(tag: str, *args, **kwargs):
        raise CustomError("listener failed")

    with policy.session(bad_listener, port) as session_state:
        assert isinstance(session_state, SessionState)
        # Initially the state is ok
        assert session_state.ok
        assert session_state.error is None

        # Sending should trigger the listener, which raises internally.
        # The exception must not propagate; instead it is stored in the session state.
        port.send("oops")

        # After exception, state must be updated
        assert not session_state.ok
        assert isinstance(session_state.error, CustomError)

