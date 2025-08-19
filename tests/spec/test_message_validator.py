import fport.policy
from fport.session import SessionState

def test_message_validator_error_ends_session():
    """If message_validator raises, Port.send must not propagate the error but end the session."""

    class ValidatorError(Exception):
        pass

    # message_validator that always raises
    def bad_validator(tag, *args, **kwargs):
        raise ValidatorError("invalid message")

    # Create policy with validator
    policy = fport.policy.create_session_policy(message_validator=bad_validator)
    port = policy.create_port()

    calls = []

    def listener(tag, *args, **kwargs):
        calls.append(tag)  # should never be called

    with policy.session(listener, port) as state:
        assert isinstance(state, SessionState)
        assert state.ok
        assert state.error is None

        # Send triggers validator error, must not propagate
        port.send("oops")

        # Session must be terminated silently
        assert not state.ok
        assert isinstance(state.error, ValidatorError)
        assert "oops" not in calls

