import fport.policy
from fport.session import Session

def test_portbridge_returns_state_values():
    """_PortBridge methods must return values from state consistently."""
    role = fport.policy._create_session_policy_role()
    state = role.state
    bridge = role.port_bridge
    core = role.core

    # get_entry_permit / get_control_permit must match state
    assert bridge.get_entry_permit() is state.entry_permit
    assert bridge.get_control_permit() is state.control_permit

    # get_message_validator must be the same object as in state
    assert bridge.get_message_validator() is state.mess_validator[0]

    # get_session: initially no session
    port = core.create_port()
    assert bridge.get_session(port) is None

    # After registering, it must return the Session
    def listener(tag: str, *args, **kwargs): pass
    session = core.register_session(listener, port)
    assert isinstance(session, Session)
    assert bridge.get_session(port) is session

    # After unregistering, back to None
    core.unregister_session(port)
    assert bridge.get_session(port) is None