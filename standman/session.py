from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Lock

class SessionState(ABC):
    __slots__ = ()
    @property
    @abstractmethod
    def active(self) -> bool:
        ...
    
    @property
    @abstractmethod
    def error(self) -> Exception | None:
        ...

class Session:
    __slots__ = ('_lock', '_active', '_error')
    def __init__(self):
        self._lock = Lock()
        self._active = True
        self._error = None
    
    @property
    def active(self) -> bool:
        with self._lock:
            return self._active
    
    @property
    def error(self) -> Exception | None:
        with self._lock:
            return self._error

    def set_error(self, exc: Exception) -> None:
        with self._lock:
            if self._error is None:
                self._error = exc
            self._active = False
    
    def get_state_reader(self):
        outer = self

        class _SessionState(SessionState):
            @property
            def active(self) -> bool:
                return outer.active
            
            @property
            def error(self) -> Exception | None:
                return outer.error
        
        return _SessionState()

