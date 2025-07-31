"""
standman: A minimal framework for runtime modular relations

A foundational framework for loosely coupled function linking,
mainly designed for testing and observation purposes.

The framework emphasizes clear boundaries of responsibility.
It does not propagate exceptions across those boundaries,
nor does it return values.

Because of its loosely coupled nature, the source (leaker)
cannot reliably know the destination (listener), even at runtime.
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

By calling `port = get_port()`, the source creates a
potential leak point. Then, with `port.leak(...)`,
it actually performs the leak.

While policies can restrict where the leak is allowed to go,
that’s just one layer of control. What truly matters is whether
the information being passed to `.observe()` is appropriate
to leak in the first place.

That’s the real heart of the matter. And honestly, that’s all there is.
"""

__version__ = "0.1.0"
# This is an initial working version.
# Public API is not yet stable and may change without notice.

from .port import Port

from .policy import create_leak_policy
from .policy import LeakPolicy, LeakImplementation, Listener, Session, SessionUnverifiedReason

import process_observer

__all__ = (
    "Port",
    "create_leak_policy",
    "LeakPolicy",
    "LeakImplementation",
    "Listener",
    "Session",
    "SessionUnverifiedReason",
    "process_observer"
)