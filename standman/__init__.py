"""

A framework for loosely-coupled and minimal-step function connections

This was created to make white-box testing easier.

Overview:
    from pathlib import Path

    from standman import create_session_policy
    from standman.process_observer import create_process_observer

    from foo import SuperSecretData

    # Management side
    def args_validator(*args, **kwargs):
        if any(isinstance(a, SuperSecretData) for a in (*args, *kwargs.values())):
            raise TypeError("Don't send it!")

    policy = create_session_policy(Path(__file__), args_validator=args_validator)

    # Sender side
    get_port = policy.get_port_dispatcher()

    def bake_cookies(num_children):
        port = get_port()
        ... # process: Mom baking some cookies
        port.send("Share nicely", num_children, len(cookies))  # sends args to "somewhere"
        ... # process: Dad doing something
        return cookies

    # Receiver side
    share_nicely = lambda ch, co: co % ch == 0
    observer = create_process_observer({"Share nicely": share_nicely})
    session = policy.session_entry(observer, bake_cookies)

    with session as invoker:
        num_children = 3
        cookies = invoker(num_children)

    back_then = not observer.get_condition_stat("Share nicely").violation
    if not share_nicely(num_children, len(cookies)):
        if back_then:
            assert False, "Mom is suspicious."
        else:
            assert False, "Dad is suspicious."

Warning:
    `port.send(...)` is essentially a "self-initiated leak to an unspecified target".
    Since the sender cannot choose where the message goes, this is structurally unavoidable.

Note:
    This is intended to be used with simple function calls.
    The framework extracts call-site information via stack frames, so it likely has considerable overhead.

    Some measures are in place to prevent incorrect connections, but it’s not guaranteed.
    Basically, it just checks the file path on the receiver side.

    `port = get_port()` does not support recursion, reentrancy, or polymorphism by itself.
    For simple recursion, use:
        def fn(port=None):
            port = get_port(port)

    Parallel execution is possible, but if combined with complex calling structures like above,
    behavior is uncertain.

Features:
    To clearly define the responsibility boundaries between sender and receiver, the framework is designed as follows:

    - Even if the receiver fails to connect (e.g., rejects the connection, fails authentication, or raises an exception),
      the sender always receives a valid interface that implements the same protocol.
      If connection fails, the returned interface only performs argument checking and does not forward anything to the receiver.

    - `Port.send()` marks the responsibility boundary.
      The tag and arguments given by the sender are validated by the policy when `.send()` is called.
      If invalid, an exception is raised on the sender side.
      Once passed and control is handed to the receiver, any exceptions will not propagate back to the sender.

    - `Port.send()` always returns `None`.

"""



__version__ = "0.1.0"
# This is an initial working version.
# Public API is not yet stable and may change without notice.

from .port import Port

from .policy import create_session_policy
from .policy import SessionPolicy, Listener, Session, SessionUnverifiedReason

import process_observer

__all__ = (
    "Port",
    "create_session_policy",
    "SessionPolicy",
    "Listener",
    "Session",
    "SessionUnverifiedReason",
    "process_observer"
)