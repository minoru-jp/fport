"""
Session and session state management for standman.

This module defines the Session lifecycle and provides a read-only
SessionState interface to check whether a session is active and if
any error has occurred.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Lock

class SessionState(ABC):
    """Read-only interface for observing a session's state."""
    __slots__ = ()
    @property
    @abstractmethod
    def active(self) -> bool:
        """Whether the session is still active."""
    
    @property
    @abstractmethod
    def error(self) -> Exception | None:
        """Error that caused the session to stop, or None if none."""


class Session:
    """Internal session controller.

    Tracks active state and error status. Provides
    a SessionState reader for external observers.
    """
    
    __slots__ = ('_lock', '_active', '_error')
    def __init__(self):
        self._lock = Lock()
        self._active = True
        self._error = None
    
    @property
    def active(self) -> bool:
        """Whether the session is still active."""
        with self._lock:
            return self._active
    
    @property
    def error(self) -> Exception | None:
        """Return the first error recorded, if any."""
        with self._lock:
            return self._error

    def set_error(self, exc: Exception) -> None:
        """Mark the session as failed with the given exception."""
        with self._lock:
            if self._error is None:
                self._error = exc
            self._active = False
    
    def get_state_reader(self):
        """Return a read-only view of the session state."""

        outer = self

        class _SessionState(SessionState):
            @property
            def active(self) -> bool:
                return outer.active
            
            @property
            def error(self) -> Exception | None:
                return outer.error
        
        return _SessionState()

