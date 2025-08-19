# test_example_with_observer.py
import pytest
from standman import example_with_observer

def test_example_with_observer_detects_bug():
    # Run and check that AssertionError is raised
    with pytest.raises(AssertionError) as excinfo:
        example_with_observer()

    # Full error message
    msg = str(excinfo.value)

    # Check core message header
    assert "Observer detected violations:" in msg

    # The violation should appear on the "freezing" condition
    assert "[freezing]" in msg

    # Ensure diagnostic details are present
    assert "reason=" in msg
    assert "count=" in msg
    assert "first_violation_at=" in msg

