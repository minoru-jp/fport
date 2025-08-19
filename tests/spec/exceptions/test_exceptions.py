import pytest
import fport

@pytest.mark.parametrize("exc_cls", [
    fport.OccupiedError,
    fport.DeniedError,
])
def test_is_exception_subclass(exc_cls):
    """Classes must be exceptions."""
    assert issubclass(exc_cls, Exception)

@pytest.mark.parametrize("exc_cls, message", [
    (fport.OccupiedError, "already occupied"),
    (fport.DeniedError, "connection denied"),
])
def test_can_raise_and_catch(exc_cls, message):
    """Exceptions can be raised, caught, and preserve message."""
    with pytest.raises(exc_cls) as ei:
        raise exc_cls(message)
    assert message in str(ei.value)

def test_exception_classes_are_distinct():
    """Ensure distinct exception types."""
    assert fport.OccupiedError is not fport.DeniedError

