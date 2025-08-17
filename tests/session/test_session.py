import pytest
from standman.session import Session

def test_session_initial_state():
    """New Session starts active with no error."""
    s = Session()
    assert s.active is True
    assert s.error is None

def test_set_error_transitions_and_freezes_first_error():
    """set_error() marks inactive and preserves the first error."""
    s = Session()
    err1 = RuntimeError("first")
    s.set_error(err1)
    assert s.active is False
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
    assert state.active is True
    assert state.error is None

    # After an error, the reader reflects the change
    s.set_error(RuntimeError("boom"))
    assert state.active is False
    assert isinstance(state.error, RuntimeError)

    # Read-only: properties have no setters
    with pytest.raises(AttributeError):
        state.active = True  # type: ignore[attr-defined]