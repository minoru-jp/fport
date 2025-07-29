
from pathlib import Path
from types import CodeType
from typing import Protocol


class Anchor(Protocol):
    def observe(self, *args, **kwargs) -> None:
        ...

    def policy_definer_path(self) -> Path:
        ...
    
    def source_module_path(self) -> Path:
        ...
    
    def observed_target_function(self) -> CodeType:
        ...
    
    def observer_scope_path(self) -> Path:
        ...

    def observed_target_scope_path(self) -> Path:
        ...
    
    def enable_burst(self, flag: bool) -> None:
        ...

NOOP_ANCHOR_TARGET_FUNCTION_CODE = (lambda *a, **kw: '<no-op>').__code__

class _NoOpAnchor(Anchor):
    __slot__ = ()
    def observe(self, *args, **kwargs) -> None:
        pass

    def policy_definer_path(self) -> Path:
        return Path("<no-op>")
    
    def source_module_path(self) -> Path:
        return Path("<no-op>")
    
    def observed_target_function(self) -> CodeType:
        return NOOP_ANCHOR_TARGET_FUNCTION_CODE
    
    def observer_scope_path(self) -> Path:
        return Path("<no-op>")

    def observed_target_scope_path(self) -> Path:
        return Path("<no-op>")
    
    def enable_burst(self, flag: bool) -> None:
        pass

NOOP_ANCHOR = _NoOpAnchor()