import _thread
import standman.policy

def test_state_initial_values_defaults():
    """Initial state must have clean defaults."""
    role = standman.policy._create_session_policy_role()
    state = role.state
    const = role.constant

    # local_lock must be a Lock instance
    assert isinstance(state.local_lock, _thread.LockType)

    # session_map starts empty
    assert state.session_map == {}

    # # mess_validator defaults to the constant
    # assert state.mess_validator is const.DEFAULT_MESSAGE_VALIDATOR

    # mess_validator is tuple containing exactly one element
    assert isinstance(state.mess_validator, tuple)
    assert len(state.mess_validator) == 1

    assert state.mess_validator[0] is const.SENTINELS["DEFAULT_MESSAGE_VALIDATOR"]

    # entry_permit and control_permit are unique objects
    assert type(state.entry_permit) == object
    assert type(state.control_permit) == object
    assert state.entry_permit is not state.control_permit


import standman.policy


def test_state_instances_are_independent():
    """Each call to _create_session_policy_role() must produce an independent state object."""
    role1 = standman.policy._create_session_policy_role()
    role2 = standman.policy._create_session_policy_role()

    s1, s2 = role1.state, role2.state

    # Different state objects
    assert s1 is not s2

    # session_map must be independent (no shared dict)
    s1.session_map["dummy"] = "value" # type: ignore
    assert "dummy" not in s2.session_map

    # Permits must be unique per state
    assert s1.entry_permit is not s2.entry_permit
    assert s1.control_permit is not s2.control_permit


def test_state_respects_custom_message_validator():
    """If message_validator is passed, state.mess_validator must wrap it in a 1-element tuple."""
    called = {}

    def custom_validator(tag, *args, **kwargs):
        called["ok"] = True

    role = standman.policy._create_session_policy_role(message_validator=custom_validator)
    state = role.state

    # mess_validator should be a tuple of length 1
    assert isinstance(state.mess_validator, tuple)
    assert len(state.mess_validator) == 1

    # That element must be the custom validator
    validator = state.mess_validator[0]
    assert validator is custom_validator

    # It must be callable and used as-is
    validator("tag", 1, x=2)
    assert called.get("ok") is True
