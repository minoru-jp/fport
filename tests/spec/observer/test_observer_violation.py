from fport.observer import ProcessObserver, ExceptionKind

def test_process_observer_condition_violation():
    """When a condition returns False, it should be marked as violation."""
    conditions = {
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # First call with invalid value -> condition fails
    observer.listen("positive", -1)

    # Violation flags must be set
    assert observer.violation
    assert observer.local_violation
    assert not observer.global_violation  # not a global error
    violated = observer.get_violated()
    assert "positive" in violated
    obs = violated["positive"]
    assert obs.violation
    assert obs.first_violation_at == 0
    assert obs.fail_reason == "condition violation"

    # After violation, count should still increment
    assert obs.count == 1


def test_process_observer_condition_exception():
    """When a condition raises an exception, violation and exception handler should trigger."""
    conditions = {
        "boom": lambda x: (_ for _ in ()).throw(ValueError("bad input")),
    }
    observer = ProcessObserver(conditions)  # type: ignore

    # Record exception handler calls
    called = {}
    def exc_handler(tag, kind, observation, exc):
        called["tag"] = tag
        called["kind"] = kind
        called["observation"] = observation
        called["exc"] = exc

    observer.set_exception_handler(exc_handler)

    # Calling listen should not propagate the exception
    observer.listen("boom", 1)

    # Local violation flag must be set
    assert observer.violation
    assert observer.local_violation
    # Global violation is not set because exception is handled locally
    assert not observer.global_violation
    assert observer.global_fail_reason == ""
    assert observer.global_exception is None

    # Exception handler must have been called at least once
    assert called["tag"] == "boom"
    assert called["kind"] == ExceptionKind.ON_CONDITION
    assert isinstance(called["exc"], ValueError)

    obs = observer.get_violated()["boom"]
    assert obs.violation
    assert isinstance(obs.exc, ValueError)
    assert "exception at boom" in obs.fail_reason


def test_process_observer_wrong_tag_sets_global_violation():
    """Using an undefined tag should set global violation and reason."""
    conditions = {
        "defined": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # Call with a tag that is not defined
    observer.listen("undefined", 123)

    # Global violation must be set
    assert observer.global_violation
    assert observer.violation
    assert not observer.local_violation  # it's not a condition failure, just wrong tag
    assert "wrong tag" in observer.global_fail_reason

    # No exceptions recorded in global_exception
    assert observer.global_exception is None

    # Defined tag observation should remain untouched
    obs_defined = observer.get_all()["defined"]
    assert obs_defined.count == 0
    assert not obs_defined.violation


def test_process_observer_violation_handler_called():
    """Violation handler should be invoked when condition fails."""
    conditions = {
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # Record handler calls
    called = {}
    def violation_handler(observation):
        called["count"] = observation.count
        called["reason"] = observation.fail_reason

    observer.set_violation_handler("positive", violation_handler)

    # Trigger violation: condition returns False
    observer.listen("positive", -5)

    # Violation handler must have been called
    assert "count" in called
    assert "reason" in called
    assert called["reason"] == "condition violation"

    # Observation should be marked as violated
    obs = observer.get_violated()["positive"]
    assert obs.violation
    assert obs.fail_reason == "condition violation"



def test_process_observer_violation_handler_exception_triggers_exception_handler():
    """If a violation handler raises, the exception handler should be called with ON_VIOLATION."""
    conditions = {
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # Define a violation handler that raises
    def bad_violation_handler(observation):
        raise RuntimeError("handler failed")

    observer.set_violation_handler("positive", bad_violation_handler)

    # Record calls to exception handler
    called = {}
    def exc_handler(tag, kind, observation, exc):
        called["tag"] = tag
        called["kind"] = kind
        called["exc"] = exc

    observer.set_exception_handler(exc_handler)

    # Trigger violation: condition returns False
    observer.listen("positive", -1)

    # Exception handler should have been called for ON_VIOLATION
    assert called["tag"] == "positive"
    assert called["kind"] == ExceptionKind.ON_VIOLATION
    assert isinstance(called["exc"], RuntimeError)

    # Observation still shows violation
    obs = observer.get_violated()["positive"]
    assert obs.violation

def test_process_observer_exception_handler_errors_are_suppressed():
    """If exception handler itself raises, it should be suppressed silently."""
    conditions = {
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # Violation handler just records call
    called = {}
    def violation_handler(observation):
        called["fail_reason"] = observation.fail_reason

    observer.set_violation_handler("positive", violation_handler)

    # Exception handler that raises its own error
    def bad_exc_handler(tag, kind, observation, exc):
        raise RuntimeError("exception handler itself failed")

    observer.set_exception_handler(bad_exc_handler)

    # Trigger violation -> condition returns False
    # Even though exception handler raises, it must be suppressed
    observer.listen("positive", -1)

    # The violation handler should still have run
    assert called["fail_reason"] == "condition violation"

    # And the test reaches here without RuntimeError escaping
    obs = observer.get_violated()["positive"]
    assert obs.violation


def test_process_observer_get_stat_after_violation():
    """get_stat should reflect violation details after a condition fails."""
    conditions = {
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # Trigger violation on first call
    observer.listen("positive", -10)

    stat = observer.get_stat("positive")

    # count is 1 (one attempt made)
    assert stat.count == 1
    # violation is True
    assert stat.violation is True
    # first_violation_at must be 0 (first attempt failed)
    assert stat.first_violation_at == 0

def test_process_observer_partial_violation_with_multiple_conditions():
    """Only the failing condition should be marked as violated when multiple are defined."""
    conditions = {
        "positive": lambda x: x > 0,
        "even": lambda x: x % 2 == 0,
    }
    observer = ProcessObserver(conditions)

    # Trigger violation on "positive" (x <= 0), "even" is satisfied
    observer.listen("positive", -1)
    observer.listen("even", 4)

    # Overall violation flag must be True
    assert observer.violation
    assert observer.local_violation
    assert not observer.global_violation

    # "positive" should be in violated observations
    violated = observer.get_violated()
    assert "positive" in violated
    assert violated["positive"].violation

    # "even" should still be compliant
    compliant = observer.get_compliant()
    assert "even" in compliant
    assert not compliant["even"].violation


def test_process_observer_violation_after_success():
    """If condition passes first and fails later, first_violation_at should reflect the failing attempt."""
    conditions = {
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # First call passes
    observer.listen("positive", 10)
    # Second call fails
    observer.listen("positive", -5)

    obs = observer.get_all()["positive"]

    # Count must be 2 after two attempts
    assert obs.count == 2

    # Violation flag must be set
    assert obs.violation

    # First violation should be recorded at the second attempt (index 1)
    assert obs.first_violation_at == 1
    assert obs.fail_reason == "condition violation"

def test_process_observer_reset_after_exception():
    """After an exception and reset_observations, observer should behave as fresh."""

    def bad_condition(x):
        raise ValueError("boom")

    conditions = {
        "bad": bad_condition,
        "positive": lambda x: x > 0,
    }
    observer = ProcessObserver(conditions)

    # Trigger an exception (should not propagate)
    observer.listen("bad", 1)

    # Violation flags should be set and exception recorded internally
    assert observer.violation
    assert observer.local_violation
    violated = observer.get_violated()
    assert "bad" in violated
    assert isinstance(violated["bad"].exc, ValueError)

    # Reset
    observer.reset_observations()

    # After reset, flags must be cleared
    assert not observer.violation
    assert not observer.global_violation
    assert not observer.local_violation
    assert observer.global_fail_reason == ""
    assert observer.global_exception is None

    # New compliant call should work without violation
    observer.listen("positive", 10)
    assert not observer.violation
    obs = observer.get_all()["positive"]
    assert obs.count == 1
    assert not obs.violation