import pytest
from fport.observer import ProcessObserver

def test_process_observer_normal_pass():
    """All conditions return True -> no violation should be recorded."""
    conditions = {
        "positive": lambda x: x > 0,
        "even": lambda x: x % 2 == 0,
    }
    observer = ProcessObserver(conditions)

    # Feed values that satisfy both conditions
    observer.listen("positive", 5)
    observer.listen("even", 4)

    # No violations expected
    assert not observer.violation
    assert not observer.global_violation
    assert not observer.local_violation
    assert observer.global_fail_reason == ""
    assert observer.global_exception is None

    # Stats should reflect one call each, both compliant
    all_obs = observer.get_all()
    assert all_obs["positive"].count == 1
    assert all_obs["even"].count == 1
    assert observer.get_violated() == {}
    compliant = observer.get_compliant()
    assert set(compliant.keys()) == {"positive", "even"}


def test_process_observer_multiple_calls():
    """Repeated calls with valid inputs should increase count and keep compliant."""
    conditions = {
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # Call the same condition multiple times with valid values
    for i in [1, 2, 3, 10]:
        observer.listen("positive", i)

    # No violations expected
    assert not observer.violation
    assert not observer.global_violation
    assert not observer.local_violation

    # Count should match number of calls
    obs = observer.get_all()["positive"]
    assert obs.count == 4
    assert not obs.violation
    assert observer.get_violated() == {}
    assert "positive" in observer.get_compliant()

def test_process_observer_get_stat():
    """get_stat should return correct statistics for compliant conditions."""
    conditions = {
        "even": lambda x: x % 2 == 0,
    }
    observer = ProcessObserver(conditions)

    # Call twice with valid values
    observer.listen("even", 2)
    observer.listen("even", 4)

    # get_stat should reflect the observation count and no violation
    stat = observer.get_stat("even")
    assert stat.count == 2
    assert stat.violation is False
    assert stat.first_violation_at == -1  # unchanged since no violation


def test_process_observer_reset_observations():
    """reset_observations should clear counts and violation flags."""
    conditions = {
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # Perform a couple of valid observations
    observer.listen("positive", 1)
    observer.listen("positive", 2)

    # Count should be 2 before reset
    obs_before = observer.get_all()["positive"]
    assert obs_before.count == 2
    assert not obs_before.violation

    # Reset
    observer.reset_observations()

    # After reset, count must be 0 and violation flags cleared
    obs_after = observer.get_all()["positive"]
    assert obs_after.count == 0
    assert not obs_after.violation
    assert observer.global_violation is False
    assert observer.local_violation is False
    assert observer.global_fail_reason == ""
    assert observer.global_exception is None


def test_process_observer_get_compliant_observations():
    """All defined tags should appear in get_compliant_observations when no violations occur."""
    conditions = {
        "positive": lambda x: x > 0,
        "nonzero": lambda x: x != 0,
    }
    observer = ProcessObserver(conditions)

    # Feed valid inputs for both conditions
    observer.listen("positive", 5)
    observer.listen("nonzero", 3)

    compliant = observer.get_compliant()

    # Both tags should be compliant
    assert set(compliant.keys()) == {"positive", "nonzero"}
    assert all(not obs.violation for obs in compliant.values())

