# tests/port/test_noop_port.py
import pytest
from fport.port import _create_noop_port
from fport.exceptions import DeniedError

class FakeBridge:
    """Minimal fake bridge to provide control/entry permits."""
    def __init__(self):
        self.control_permit = object()
        self.entry_permit = object()

    def get_control_permit(self):
        return self.control_permit

    def get_entry_permit(self):
        return self.entry_permit


def test_noop_port_send_is_noop():
    """send() should never raise, regardless of input."""
    bridge = FakeBridge()
    port = _create_noop_port(bridge)
    # No exception even with arbitrary args
    port.send("tag", 1, x=2)


def test_noop_port_set_listen_func_deniederror_with_correct_key():
    """Using the correct control permit raises DeniedError."""
    bridge = FakeBridge()
    port = _create_noop_port(bridge)
    with pytest.raises(DeniedError):
        port._set_listen_func(bridge.get_control_permit(), lambda *_: None)


def test_noop_port_set_listen_func_permissionerror_with_wrong_key():
    """Using the wrong key raises PermissionError."""
    bridge = FakeBridge()
    port = _create_noop_port(bridge)
    with pytest.raises(PermissionError):
        port._set_listen_func(object(), lambda *_: None)


def test_noop_port_remove_listen_func_behaves_as_specified():
    """Correct key works silently, wrong key raises PermissionError."""
    bridge = FakeBridge()
    port = _create_noop_port(bridge)

    # Correct key: should not raise
    port._remove_listen_func(bridge.get_control_permit())

    # Wrong key: should raise
    with pytest.raises(PermissionError):
        port._remove_listen_func(object())


def test_noop_port_entry_permit_is_bridge_value():
    """The entry permit returned by the port must be the one from the bridge."""
    bridge = FakeBridge()
    port = _create_noop_port(bridge)
    assert port._get_entry_permit() is bridge.get_entry_permit()
