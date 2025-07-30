from __future__ import annotations

from pathlib import Path
from types import CodeType
from typing import Any, Callable, Protocol

from .policy import LeakPolicy
from .observer import ProcessObserver


class Anchor(Protocol):
    def observe(self, *args, **kwargs) -> None:
        ...

    @property
    def policy_definer_path(self) -> Path:
        ...

    @property
    def leak_policy(self) -> LeakPolicy:
        ...

    @property    
    def process_observer(self) -> ProcessObserver | None:
        ...
    
    @property
    def observed_target_function(self) -> Callable[..., Any]:
        ...

    @property
    def base_scope(self) -> Path:
        ...

class VerifiedAnchor(Anchor):
    __slots__ = ()

class UnverifiedAnchor(Anchor):
    __slots__ = ()


