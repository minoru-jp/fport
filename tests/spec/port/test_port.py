import pytest
import threading

import fport
from fport.port import Port, _create_port_role
from fport.policy import _PortBridgeTOC
from fport.exceptions import OccupiedError
from fport.protocols import SendFunction
from fport.session import Session, SessionState
    
class FakeBridge(_PortBridgeTOC):
    def __init__(self):
        self._entry = object()
        self._control = object()

    def get_session(self, port: Port) -> Session | None:
        return None

    def get_entry_permit(self) -> object:
        return self._entry
    
    def get_control_permit(self) -> object:
        return self._control
    
    def get_message_validator(self) -> SendFunction:
        return lambda tag, *a, **kw: None
    

def test_port_state_initial_values():
    """State must start with no listener and no error."""
    bridge = FakeBridge()
    role = _create_port_role(bridge)
    state = role.state

    # At creation, state should be clean
    assert state.listen_func is None
    assert state.error is None

def test_set_listen_func_and_occupied_error():
    """Registering a listener works once; second registration raises OccupiedError."""
    bridge = FakeBridge()
    role = _create_port_role(bridge)
    port = role.interface
    state = role.state

    # First registration should succeed
    listener = lambda tag, *args, **kwargs: None
    port._set_listen_func(bridge.get_control_permit(), listener)
    assert state.listen_func is listener
    assert state.error is None

    # Second registration should fail with OccupiedError
    with pytest.raises(OccupiedError):
        port._set_listen_func(bridge.get_control_permit(), lambda tag, *args, **kwargs: None)


def test_send_calls_listener_and_preserves_clean_state():
    """send() must invoke the listener with args/kwargs when registered."""
    bridge = FakeBridge()
    role = _create_port_role(bridge)
    port = role.interface
    state = role.state

    calls = []
    def listener(tag, *args, **kwargs):
        calls.append((tag, args, kwargs))

    # Register listener
    port._set_listen_func(bridge.get_control_permit(), listener)

    # Act: call send
    port.send("hello", 1, x=2)

    # Listener must have been called once with the same arguments
    assert calls == [("hello", (1,), {"x": 2})]

    # No error should be latched
    assert state.error is None

def test_remove_resets_state_and_allows_reuse():
    """_remove_listen_func must reset listener and error, allowing reuse."""
    bridge = FakeBridge()
    role = _create_port_role(bridge)
    port = role.interface
    state = role.state

    # Register a bad listener that raises
    def bad_listener(tag, *args, **kwargs: None):
        raise RuntimeError("boom")

    port._set_listen_func(bridge.get_control_permit(), bad_listener)
    port.send("oops")

    # Error latched
    assert isinstance(state.error, RuntimeError)
    assert state.listen_func is bad_listener

    # Remove resets both listener and error
    port._remove_listen_func(bridge.get_control_permit())
    assert state.listen_func is None
    assert state.error is None

    # Now we can register a new listener
    calls = []
    def good_listener(tag, *args, **kwargs):
        calls.append((tag, args, kwargs))

    port._set_listen_func(bridge.get_control_permit(), good_listener)
    port.send("hello", 1, x=2)

    # Listener must be called
    assert calls == [("hello", (1,), {"x": 2})]
    assert state.error is None

def test_set_and_remove_with_wrong_key_raise_permissionerror():
    """Using a wrong key must raise PermissionError for both set and remove."""
    bridge = FakeBridge()
    role = _create_port_role(bridge)
    port = role.interface

    wrong_key = object()

    # Wrong key for set_listen_func
    with pytest.raises(PermissionError):
        port._set_listen_func(wrong_key, lambda tag, *args, **kwargs: None)

    # Wrong key for remove_listen_func
    with pytest.raises(PermissionError):
        port._remove_listen_func(wrong_key)

def test_get_entry_permit_returns_bridge_value():
    """_get_entry_permit must return the entry_permit from the bridge."""
    bridge = FakeBridge()
    role = _create_port_role(bridge)
    port = role.interface

    # The value returned by port must be exactly the bridge's entry permit
    assert port._get_entry_permit() is bridge.get_entry_permit()

def test_send_invokes_validator_before_listener():
    """send() must call the bridge's validator before invoking the listener."""
    called = {"validator": False, "listener": False}

    class BridgeWithValidator(_PortBridgeTOC):
        def __init__(self):
            self._entry = object()
            self._control = object()
        def get_session(self, port: Port) -> Session | None:
            return None
        def get_entry_permit(self) -> object:
            return self._entry
        def get_control_permit(self) -> object:
            return self._control
        def get_message_validator(self) -> SendFunction:
            def validator(tag, *args, **kwargs):
                called["validator"] = True
            return validator

    bridge = BridgeWithValidator()
    role = _create_port_role(bridge)
    port = role.interface
    state = role.state

    def listener(tag, *args, **kwargs):
        called["listener"] = True

    # Register listener
    port._set_listen_func(bridge.get_control_permit(), listener)

    # Call send
    port.send("test", 123, x=456)

    # Validator must have been called before listener
    assert called["validator"] is True
    assert called["listener"] is True
    # No error must be latched
    assert state.error is None

def test_send_validator_exception_is_fail_silent_and_latched():
    """If validator raises, send() must be fail-silent, latch the error, and skip listener."""
    class BridgeWithFailingValidator(_PortBridgeTOC):
        def __init__(self):
            self._entry = object()
            self._control = object()
        def get_session(self, port: Port) -> Session | None:
            return None
        def get_entry_permit(self) -> object:
            return self._entry
        def get_control_permit(self) -> object:
            return self._control
        def get_message_validator(self) -> SendFunction:
            def validator(tag, *args, **kwargs):
                raise ValueError("validator failed")
            return validator

    bridge = BridgeWithFailingValidator()
    role = _create_port_role(bridge)
    port = role.interface
    state = role.state

    called = {"listener": False}
    def listener(tag, *args, **kwargs):
        called["listener"] = True

    # Register listener
    port._set_listen_func(bridge.get_control_permit(), listener)

    # Act: call send, must not raise
    port.send("oops")

    # Listener should not be called
    assert called["listener"] is False
    # Error must be latched
    assert isinstance(state.error, ValueError)
    assert "validator failed" in str(state.error)

def test_port_set_listen_func_after_error_is_ignored():
    """Once a Port has entered error state, setting a new listener must be ignored."""

    role = fport.policy._create_session_policy_role()
    core = role.core
    port = core.create_port()

    class CustomError(Exception):
        pass

    def bad_listener(tag, *args, **kwargs):
        raise CustomError("listener failure")

    # Start a session and trigger an error through the bad listener
    with core.session(bad_listener, port) as state:
        port.send("oops")
        assert not state.ok
        assert isinstance(state.error, CustomError)

    # After error, the session is gone but the Port still remembers the error
    assert role.port_bridge.get_session(port) is None

    def new_listener(tag, *args, **kwargs):
        pytest.fail("listener should never be called")

    # Even with a valid control permit, the Port must ignore the new listener
    port._set_listen_func(role.port_bridge.get_control_permit(), new_listener)

    # Sending again must not call the new listener (test will fail if it does)
    port.send("should_be_ignored")


def test_port_can_be_reused_after_session_end():
    """A Port must be reusable after a session ends."""

    role = fport.policy._create_session_policy_role()
    core = role.core
    port = core.create_port()

    calls = []

    def first_listener(tag, *args, **kwargs):
        calls.append(("first", tag))

    def second_listener(tag, *args, **kwargs):
        calls.append(("second", tag))

    # First session
    with core.session(first_listener, port) as state1:
        assert isinstance(state1, SessionState)
        assert state1.ok
        port.send("msg1")

    # After leaving the context, the first session is gone
    assert role.port_bridge.get_session(port) is None

    # Second session on the same port should be possible
    with core.session(second_listener, port) as state2:
        assert isinstance(state2, SessionState)
        assert state2.ok
        port.send("msg2")

    # Verify both listeners were called at the right times
    assert ("first", "msg1") in calls
    assert ("second", "msg2") in calls