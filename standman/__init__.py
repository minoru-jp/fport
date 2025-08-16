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

__version__ = '0.3.0'

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
        assert state.active
        assert state.error is None
        print("Result:", result)

    # Output:
    # Received: add, args=(2, 3), kwargs={}
    # Result: 5

if __name__ == "__main__":
    example()
