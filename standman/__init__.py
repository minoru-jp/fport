"""
standman: A minimal framework for runtime modular relations

A foundational framework for loosely coupled function linking,
mainly designed for testing and observation purposes.

The framework emphasizes clear boundaries of responsibility.
It does not propagate exceptions across those boundaries,
nor does it return values.

Because of its loosely coupled nature, the source (caller)
cannot reliably know the destination (callee), even at runtime.
(You can get hints, but not guarantees.)

To help manage this uncertainty, the framework supports policies
that specify which modules are allowed to participate in linking,
based on their location. However, this is only a partial measure.

### The Core Issue

This framework isn't meant to spy on the source or set traps
to extract information.

Instead, it provides a way for the source to voluntarily leak
information if it chooses to do so. That choice—and its
consequences—belong entirely to the source.

By calling `anchor = get_anchor()`, the source creates a
potential leak point. Then, with `anchor.observe(...)`,
it actually performs the leak.

While policies can restrict where the leak is allowed to go,
that’s just one layer of control. What truly matters is whether
the information being passed to `.observe()` is appropriate
to leak in the first place.

That’s the real heart of the matter.
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