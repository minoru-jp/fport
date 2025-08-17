import pytest
import standman.policy
from standman.session import SessionState
from standman.exceptions import DeniedError

def test_session_context_registers_and_unregisters():
    """core.session() must register a session, yield a SessionState, and unregister on exit."""
    role = standman.policy._create_session_policy_role()
    core = role.core
    state = role.state

    port = core.create_port()

    calls = []
    def listener(tag: str, *args, **kwargs) -> None:
        calls.append((tag, args, kwargs))

    # Use the session context manager
    with core.session(listener, port) as session_state:
        # Must yield a SessionState
        assert isinstance(session_state, SessionState)

        # The session must be ok and mapped
        assert session_state.ok
        assert port in state.session_map

        # Send a message and check listener was called
        port.send("hello", 1, x=2)
        assert calls == [("hello", (1,), {"x": 2})]

    # After exiting the context, the session must still be ok (no error occurred)
    assert session_state.ok
    assert session_state.error is None
    # And it must be removed from the map
    assert port not in state.session_map


def test_session_raises_typeerror_when_target_is_not_port():
    """core.session() must raise TypeError if target is not a Port instance."""
    role = standman.policy._create_session_policy_role()
    core = role.core

    def listener(tag: str, *args, **kwargs): pass

    with pytest.raises(TypeError):
        with core.session(listener, 123):  # type: ignore[arg-type]
            pass

    with pytest.raises(TypeError):
        with core.session(listener, None):  # type: ignore[arg-type]
            pass


def test_session_raises_deniederror_when_port_belongs_to_other_policy():
    """core.session() must raise DeniedError if the port was created by another policy."""
    role1 = standman.policy._create_session_policy_role()
    core1 = role1.core

    role2 = standman.policy._create_session_policy_role()
    core2 = role2.core

    port_from_other_policy = core2.create_port()

    def listener(tag: str, *args, **kwargs): pass

    with pytest.raises(DeniedError):
        with core1.session(listener, port_from_other_policy):
            pass

