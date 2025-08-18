import standman.policy
from standman.port import Port
from standman.session import SessionState

def test_role_contains_kernel():
    """SessionPolicy role must provide a kernel with create_port and create_noop_port."""

    role = standman.policy._create_session_policy_role()

    # role must have a kernel attribute
    assert hasattr(role, "kernel")

    kernel = role.kernel

    # kernel must provide the expected methods
    assert hasattr(kernel, "create_port")
    assert hasattr(kernel, "create_noop_port")

    # create_port must return a PortRole with .interface being a Port
    port_role = kernel.create_port(role.port_bridge)
    assert not isinstance(port_role, Port)     # must not be a Port directly
    assert isinstance(port_role.interface, Port)

    # create_noop_port must return a Port (no role, just interface)
    noop_port = kernel.create_noop_port(role.port_bridge)
    assert isinstance(noop_port, Port)


def test_kernel_create_port_and_noop_differences():
    """kernel.create_port returns a PortRole, while create_noop_port returns only a Port."""

    role = standman.policy._create_session_policy_role()
    kernel = role.kernel

    # Normal port role
    port_role = kernel.create_port(role.port_bridge)
    assert not isinstance(port_role, Port)     # must be a PortRole
    assert isinstance(port_role.interface, Port)

    # Noop port (interface only, no state)
    noop_port = kernel.create_noop_port(role.port_bridge)
    assert isinstance(noop_port, Port)


def test_kernel_created_port_can_be_used_in_session():
    """A port created through kernel must work correctly with core.session."""

    role = standman.policy._create_session_policy_role()
    kernel = role.kernel
    core = role.core

    port_role = kernel.create_port(role.port_bridge)
    assert not isinstance(port_role, Port)     # must be a PortRole
    port = port_role.interface

    calls = []

    def listener(tag, *args, **kwargs):
        calls.append(tag)

    with core.session(listener, port) as state:
        assert isinstance(state, SessionState)
        assert state.ok
        port.send("hello")

    assert "hello" in calls


def test_kernel_created_port_error_and_reset():
    """Errors must be reflected in port_role.state during session and cleared after session end."""

    role = standman.policy._create_session_policy_role()
    kernel = role.kernel
    core = role.core

    port_role = kernel.create_port(role.port_bridge)
    assert not isinstance(port_role, Port)     # must be a PortRole
    port = port_role.interface

    class CustomError(Exception):
        pass

    def bad_listener(tag, *args, **kwargs):
        raise CustomError("boom")

    # Trigger error
    with core.session(bad_listener, port) as state:
        port.send("oops")
        assert not state.ok
        assert isinstance(state.error, CustomError)
        # Internal state must also record the error
        assert isinstance(port_role.state.error, CustomError)

    # After session end, port internal state must be cleared
    assert port_role.state.error is None
    assert port_role.state.listen_func is None

