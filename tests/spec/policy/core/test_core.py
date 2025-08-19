import pytest

import fport.policy
from fport.session import Session, SessionState
from fport.exceptions import DeniedError, OccupiedError
from fport.port import Port, _create_noop_port

def test_register_and_unregister_session_success():
    """register_session must add a session and unregister_session must remove it."""
    role = fport.policy._create_session_policy_role()
    state = role.state
    core = role.core

    # Create a Port under this policy
    port = core.create_port()

    # Prepare a dummy listener
    called = {}
    def listener(tag, *args, **kwargs):
        called["ok"] = True

    # Register the session
    session = core.register_session(listener, port)

    # Returned object must be a Session
    assert isinstance(session, Session)

    # The session must be in session_map
    assert port in state.session_map
    assert state.session_map[port] is session

    # Unregister the session
    core.unregister_session(port)

    # The session must be removed from session_map
    assert port not in state.session_map

def test_register_session_twice_raises_occupiederror():
    """Registering twice on the same port must raise OccupiedError (normal case)."""
    role = fport.policy._create_session_policy_role()
    core = role.core

    port = core.create_port()

    def listener(tag, *args, **kwargs):
        pass

    # First registration should succeed
    core.register_session(listener, port)

    # Second registration should raise OccupiedError
    with pytest.raises(OccupiedError):
        core.register_session(listener, port)

def test_register_session_runtimeerror_on_inconsistent_state():
    """Force an inconsistent state so RuntimeError is raised instead of OccupiedError."""

    role = fport.policy._create_session_policy_role()
    core = role.core
    state = role.state

    # DummyPort inherits from Port and bypasses OccupiedError
    class DummyPort(Port):
        def send(self, tag: str, *args, **kwargs):
            pass
        def _set_listen_func(self, key, listen):
            return None  # Always succeed
        def _remove_listen_func(self, key):
            return None
        def _get_entry_permit(self):
            return state.entry_permit

    port = DummyPort()

    # Pre-populate session_map with the same port
    state.session_map[port] = Session()

    def listener(tag, *args, **kwargs):
        pass

    with pytest.raises(RuntimeError) as excinfo:
        core.register_session(listener, port)

    assert "already registered" in str(excinfo.value).lower()


def test_unregister_session_not_found_raises_runtimeerror():
    """Calling unregister_session on a port that has no session must raise RuntimeError."""
    role = fport.policy._create_session_policy_role()
    core = role.core

    # Create a port but never register it
    port = core.create_port()

    # Attempting to unregister should raise RuntimeError
    with pytest.raises(RuntimeError) as excinfo:
        core.unregister_session(port)

    assert "session not found" in str(excinfo.value).lower()


def test_create_port_returns_normal_port_when_not_blocked():
    """create_port() must return a functional Port when block_port=False."""
    role = fport.policy._create_session_policy_role(block_port=False)
    core = role.core

    port = core.create_port()

    # Normal port: first listener registration must succeed
    def listener(tag: str, *args, **kwargs) -> None:
        pass

    port._set_listen_func(role.state.control_permit, listener)

    # A second registration with the same key must fail with OccupiedError
    with pytest.raises(OccupiedError):
        port._set_listen_func(role.state.control_permit, listener)


def test_create_port_returns_noop_port_when_blocked():
    """create_port() must return a no-op Port when block_port=True."""
    role = fport.policy._create_session_policy_role(block_port=True)
    core = role.core

    port = core.create_port()

    # No-op port: listener registration must always raise DeniedError
    def dummy_listener(tag: str, *args, **kwargs) -> None:
        pass

    with pytest.raises(DeniedError):
        port._set_listen_func(role.state.control_permit, dummy_listener)


def test_create_noop_port_always_returns_noop():
    """create_noop_port() must always return a no-op Port."""
    role = fport.policy._create_session_policy_role()
    core = role.core

    port = core.create_noop_port()

    # No-op port: listener registration must always raise DeniedError
    def dummy_listener(tag: str, *args, **kwargs) -> None:
        pass

    with pytest.raises(DeniedError):
        port._set_listen_func(role.state.control_permit, dummy_listener)



def test_session_context_registers_and_unregisters():
    """core.session() must register a session, yield a SessionState, and unregister on exit."""
    role = fport.policy._create_session_policy_role()
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

        # The session must be active and mapped
        assert session_state.ok is True
        assert port in state.session_map

        # Send a message and check listener was called
        port.send("hello", 1, x=2)
        assert calls == [("hello", (1,), {"x": 2})]

    # After exiting the context, the session must be removed
    assert port not in state.session_map


def test_session_raises_typeerror_when_target_is_not_port():
    """core.session() must raise TypeError if target is not a Port instance."""
    role = fport.policy._create_session_policy_role()
    core = role.core

    def listener(tag: str, *args, **kwargs):
        pass

    # Passing an int instead of a Port must raise TypeError
    with pytest.raises(TypeError):
        with core.session(listener, 123):  # type: ignore[arg-type]
            pass

    # Passing None must also raise TypeError
    with pytest.raises(TypeError):
        with core.session(listener, None):  # type: ignore[arg-type]
            pass


def test_session_raises_deniederror_when_port_belongs_to_other_policy():
    """core.session() must raise DeniedError if the port was created by another policy."""
    # Create two separate policies
    role1 = fport.policy._create_session_policy_role()
    core1 = role1.core

    role2 = fport.policy._create_session_policy_role()
    core2 = role2.core

    port_from_other_policy = core2.create_port()

    def listener(tag: str, *args, **kwargs):
        pass

    # Attempting to use a port from another policy must raise DeniedError
    with pytest.raises(DeniedError):
        with core1.session(listener, port_from_other_policy):
            pass