from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol

from .listener import Listener
from .policy import LeakPolicy

class Port(Protocol):
    def leak(self, tag: str, *args, **kwargs) -> None:
        ...

    @property
    def policy_definer_path(self) -> Path:
        ...

    @property
    def leak_policy(self) -> LeakPolicy:
        ...

    @property    
    def listener(self) -> Listener | None:
        ...
    
    @property
    def listened_function(self) -> Callable[..., Any]:
        ...

    @property
    def base_scope(self) -> Path:
        ...

class VerifiedPort(Port):
    __slots__ = ()

class UnverifiedPort(Port):
    __slots__ = ()


def create_verified_port_unit(
        listener: Listener,
        policy_definer_location: Path,
        leak_policy: LeakPolicy,
        base_scope: Path,
        target: Callable[..., Any],
        tag_validator: Callable[[str], None]
) -> tuple[VerifiedPort, VerifiedPort]:
    
    listened_function = listener.listen

    class _Port(VerifiedPort):
        __slots__ = ()
        def leak(self, tag: str, *args, **kwargs) -> None:
            tag_validator(tag)
            try:
                listened_function(*args, **kwargs)
            except Exception:
                pass
        @property
        def policy_definer_path(self) -> Path:
            return policy_definer_location
        @property
        def leak_policy(self) -> LeakPolicy:
            return leak_policy
        @property
        def base_scope(self) -> Path:
            return base_scope
        @property
        def listener(self) -> Listener:
            return listener
        @property
        def listened_function(self) -> Callable[..., Any]:
            return target

    class _NoOpPort(VerifiedPort):
        __slots__ = ()
        def leak(self, tag: str, *args, **kwargs) -> None:
            tag_validator(tag)
        
        @property
        def policy_definer_path(self) -> Path:
            return policy_definer_location
        @property
        def leak_policy(self) -> LeakPolicy:
            return leak_policy
        @property
        def base_scope(self) -> Path:
            return base_scope
        @property
        def listener(self) -> Listener:
            return listener
        @property
        def listened_function(self) -> Callable[..., Any]:
            return target
    
    return (_Port(), _NoOpPort())

