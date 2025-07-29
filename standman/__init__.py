"""
standman: A decoupled framework for runtime observation

WARNING:
- Misuse of this library may lead to false trust and critical oversights.
- Safeguards are in place, but they are not guaranteed to be foolproof.
- Scope restrictions are experimental and subject to change.
- This library has not undergone testing and is not production-proven.
- Recursive functions are not supported. Behavior is undefined if a target calls itself.

This module defines three distinct roles:

1. Policy author:
    Creates a policy via create_leak_policy(observer_scope, target_scope).
    The policy must reside within the specified scope directories.
    All access from outside these scopes will be blocked.
    If scope paths are omitted, the current working directory is used—
    take care in tests, as this may vary and cause crashes.

2. Observer:
    Creates a ProcessObserver with observation conditions.
    Obtains an ObservationPort from the policy author and calls:

        session = observation_port.session_entry(observer.observe, target_function)

    Then manually invokes target_function.
    After execution, inspects the session and observer to evaluate the results.

    Note:
        A session is valid for a single invocation only.
        To observe multiple runs, call observer.reset_observation(),
        and register a new session via session_entry().

3. Implementation:
    Receives a LeakPort from the policy author.
    Defines get_anchor = leak_port.get_anchor_verifier() outside functions.
    Inside each function or method:

        anchor = get_anchor()
        anchor.observe("tag", ...)

    If verification fails, a no-op anchor is returned.

Note:
    Parallelism is not currently supported.
    Attempting to observe the same function concurrently will result in a RuntimeError.

    NOOP_ANCHOR is an Anchor that guarantees observe() does nothing.
    It is applied either when explicitly selected, or automatically when verification fails
    and exception propagation is disabled.
    
    Implementation must decide where to place observations,
    but must never write logic that assumes it will be observed.
    It is strictly forbidden to offload condition checks to observers
    that should be performed by the implementation itself.

    It is currently unclear whether the scope restrictions are too strict or too permissive.
    This behavior is subject to change in the future as usage patterns become clearer.
    
    Polymorphism is untested. Subclass overrides may cause verification to fail.



# NOTE: 

Leak* naming means exactly what it says.
No matter how tightly you guard it—or how nicely you dress it up—a leak is still a leak.
The naming is a lesson carved from bad memories.
"""

__version__ = "0.1.0"
# This is an initial working version.
# Public API is not yet stable and may change without notice.

from .anchor import Anchor, NOOP_ANCHOR, NOOP_ANCHOR_TARGET_FUNCTION_CODE

from .policy import create_leak_policy
from .policy import LeakPolicy, LeakPort, ObservationPort, Session, SessionUnverifiedReason

from .observer import create_process_observer
from .observer import ProcessObserver, Observation, ConditionStat

__all__ = (
    "Anchor",
    "NOOP_ANCHOR",
    "NOOP_ANCHOR_TARGET_FUNCTION_CODE",
    "create_leak_policy",
    "LeakPolicy",
    "LeakPort",
    "ObservationPort",
    "Session",
    "SessionUnverifiedReason",
    "create_process_observer",
    "ProcessObserver",
    "Observation",
    "ConditionStat",
)