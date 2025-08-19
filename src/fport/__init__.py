"""
standman package initializer.

This module defines the public API of standman by re-exporting
interfaces from internal modules. Users should import symbols
from here instead of directly accessing submodules.

Exports:
    - SessionPolicy, create_session_policy : Manage Ports and Sessions
    - Port                                : Interface for sending data
    - SessionState                        : Read-only session state
    - SendFunction, ListenFunction        : Protocols for callbacks
    - DeniedError, OccupiedError          : Exceptions for connection control
    - __version__                         : Package version

Design note:
    Asynchronous interfaces are intentionally not supported.
    Listener implementations may take any form, but the design
    ensures that sending side code is never affected by exceptions,
    serialization, or concurrency side effects introduced here.

See also:
    The `example()` function in this module demonstrates
    a minimal working usage of SessionPolicy, Port, and session.

"""

from .policy import SessionPolicy, create_session_policy
from .port import Port
from .session import SessionState
from .protocols import SendFunction, ListenFunction
from .exceptions import DeniedError, OccupiedError

from .observer import ProcessObserver

__version__ = '1.0.3'

__all__ = (
    'SessionPolicy', 'create_session_policy',
    'Port',
    'SessionState',
    'SendFunction', 'ListenFunction',
    'DeniedError', 'OccupiedError',
    '__version__')

def example():
    policy = create_session_policy()
    port = policy.create_port()

    # Implementation-side function
    def add(a, b):
        port.send("add", a, b)
        return a + b

    # Listener function
    def listener(tag, *args, **kwargs):
        print(f"Received: {tag}, args={args}, kwargs={kwargs}")

    # Run with session
    with policy.session(listener, port) as state:
        result = add(2, 3)
        assert state.ok
        assert state.error is None
        print("Result:", result)

    # Output:
    # Received: add, args=(2, 3), kwargs={}
    # Result: 5


def example_with_observer():

    def create_weather_sensor(port):
        """Weather sensor
        Specification:
            temp < 0        -> "Freezing" + send("freezing")
            0 <= temp <= 30 -> "Normal"   + send("normal")
            temp > 30       -> "Hot"      + send("hot")
        """
        def check_weather(temp: int) -> str:
            # If there is a bug here, it will be detected by the test
            if temp <= 0:   # ← Common place to inject a bug
                port.send("freezing", temp)
                return "Freezing"
            elif temp <= 30:
                port.send("normal", temp)
                return "Normal"
            else:
                port.send("hot", temp)
                return "Hot"
        return check_weather

    policy = create_session_policy()
    port = policy.create_port()

    # Define expected conditions according to the specification
    conditions = {
        "freezing": lambda t: t < 0,
        "normal":   lambda t: 0 <= t <= 30,
        "hot":      lambda t: t > 30,
    }
    observer = ProcessObserver(conditions)
    check_weather = create_weather_sensor(port)

    with policy.session(observer.listen, port) as state:
        # Test coverage for all three branches
        for i in (-5, 0, 31):
            check_weather(i)
            if not state.ok:
                raise AssertionError(f"observation failed on '{i}'")

        # Verify that the Observer did not detect any specification violations
        if observer.violation:
            details = []
            for tag, obs in observer.get_violated().items():
                details.append(
                    f"[{tag}] reason={obs.fail_reason}, "
                    f"count={obs.count}, first_violation_at={obs.first_violation_at}"
                )
            raise AssertionError("Observer detected violations:\n" + "\n".join(details))
    
    print("All checks passed!")


if __name__ == "__main__":
    example()
