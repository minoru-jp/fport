import standman.policy
from standman.port import Port
from standman.session import SessionState

def test_port_state_error_is_cleared_after_session_end():
    """Port internal state.error must be cleared when the session ends."""

    # Get the role directly so we can access the factory
    role = standman.policy._create_session_policy_role()
    core = role.core

    # Create a port role via factory (not via core.create_port)
    port_role = role.kernel.create_port(role.port_bridge)
    assert not isinstance(port_role, Port) # port_role must be not noop port
    port = port_role.interface

    class CustomError(Exception):
        pass

    def bad_listener(tag, *args, **kwargs):
        raise CustomError("listener failure")

    # Trigger an error inside a session
    with core.session(bad_listener, port) as state:
        port.send("oops")
        assert not state.ok
        assert isinstance(state.error, CustomError)

        # Port internal state must hold the error during the session
        assert isinstance(port_role.state.error, CustomError)

    # After leaving the context, Port must be reset
    assert role.port_bridge.get_session(port) is None
    assert port_role.state.error is None
    assert port_role.state.listen_func is None

def test_port_can_be_reconnected_after_session_end():
    """A Port must allow a new session after the previous one has ended."""

    role = standman.policy._create_session_policy_role()
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

    # After the first session ends, port should be free
    assert role.port_bridge.get_session(port) is None

    # Second session with a different listener
    with core.session(second_listener, port) as state2:
        assert isinstance(state2, SessionState)
        assert state2.ok
        port.send("msg2")

    # Both listeners should have received their own messages
    assert ("first", "msg1") in calls
    assert ("second", "msg2") in calls

def test_reconnect_after_error_in_first_session():
    """A Port must be reusable even if the first session ended with an error."""

    role = standman.policy._create_session_policy_role()
    core = role.core
    port = core.create_port()

    calls = []

    class CustomError(Exception):
        pass

    def bad_listener(tag, *args, **kwargs):
        raise CustomError("listener failed")

    def good_listener(tag, *args, **kwargs):
        calls.append(("good", tag))

    # First session with a bad listener that always raises
    with core.session(bad_listener, port) as state1:
        port.send("oops")
        assert not state1.ok
        assert isinstance(state1.error, CustomError)

    # After error session ended, Port must be reset
    assert role.port_bridge.get_session(port) is None

    # Second session should start normally with a good listener
    with core.session(good_listener, port) as state2:
        assert isinstance(state2, SessionState)
        assert state2.ok
        port.send("msg2")

    # The second listener must receive its message
    assert ("good", "msg2") in calls
