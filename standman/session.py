from __future__ import annotations

import enum
from threading import Lock
from types import CodeType, FunctionType, TracebackType
from typing import Any, Callable, Literal, Protocol


from .port import VerifiedPort


class Session(Protocol):
    @property
    def verified(self) -> Literal[True] | SessionUnverifiedReason:
        ...
    
    def __repr__(self):
        ...
    
    def __enter__(self) -> Callable[..., Any]:
        ...

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        ...

    def get_invocation_identifier(self) -> str:
        ...


class SessionUnverifiedReason(enum.Enum):
    PENDING = "Execution and verification have not been performed yet"
    INVALID = "Verification failed due to policy constraints"
    DENIED = "Connection was rejected by the target"
    FAILED = "Policy verification failed due to internal error"
    def __bool__(self):
        return False
    def __str__(self):
        return self.value


class SessionFull(Protocol):
    def get_session(self) -> Session:
        ...
    
    def get_port(self) -> VerifiedPort:
        ...
    
    def get_noop_port(self) -> VerifiedPort:
        ...
    
    def get_invoker(self) -> Callable[..., Any]:
        ...
    
    def get_invocation_identifier(self) -> str:
        ...
    
    def set_unverified_reason(self, reason: SessionUnverifiedReason) -> None:
        ...
    
    def set_as_verified(self) -> None:
        ...


def create_session_full(target: Callable[..., Any], anchor_unit: tuple[VerifiedPort, VerifiedPort]) -> SessionFull:

    ID_TEMPLATE = 'invoke_session_{ID}'
    
    consumed = False
    unverified_reason = SessionUnverifiedReason.PENDING

    id_object = object()

    invocation_identifier = ID_TEMPLATE.format(ID = str(id(id_object)))

    lock = Lock()

    running = False

    def target_invoker(*args, **kwargs) -> Any:
        return target(*args, **kwargs)

    template_code = target_invoker.__code__

    invoker_code = CodeType(
        template_code.co_argcount,
        template_code.co_posonlyargcount,
        template_code.co_kwonlyargcount,
        template_code.co_nlocals,
        template_code.co_stacksize,
        template_code.co_flags,
        template_code.co_code,
        template_code.co_consts,
        template_code.co_names,
        template_code.co_varnames,
        template_code.co_filename,
        invocation_identifier,                 # co_name
        template_code.co_qualname,
        template_code.co_firstlineno,
        template_code.co_linetable,
        template_code.co_exceptiontable,
        template_code.co_freevars,
        template_code.co_cellvars
    )

    invoker = FunctionType(
        code = invoker_code,
        globals = target_invoker.__globals__,
        name = invocation_identifier,
        argdefs = target_invoker.__defaults__,
        closure = target_invoker.__closure__
    )

    class _Session(Session):
        __slots__ = ()
        @property
        def verified(self) -> Literal[True] | SessionUnverifiedReason:
            if unverified_reason:
                return unverified_reason
            return True
        
        def __repr__(self):
            verified = self.verified
            if verified:
                verified = 'Session is verified'
            return str(verified)

        def __enter__(self) -> Callable[..., Any]:
            if consumed:
                raise RuntimeError(f"This session has already ended. id = {invocation_identifier}")
            return invoker

        def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
            nonlocal consumed
            consumed = True

        def get_invocation_identifier(self) -> str:
            return invocation_identifier
    
    session = _Session()

    class _Interface(SessionFull):
        __slots__ = ()
        @property
        def running(self):
            with lock:
                return running
        
        def get_session(self) -> Session:
            return session
        
        def get_port(self) -> VerifiedPort:
            return anchor_unit[0]
        
        def get_noop_port(self) -> VerifiedPort:
            return anchor_unit[1]
        
        def get_invoker(self) -> Callable[..., Any]:
            return invoker
        
        def get_invocation_identifier(self) -> str:
            return invocation_identifier
        
        def set_unverified_reason(self, reason: SessionUnverifiedReason) -> None:
            nonlocal unverified_reason
            unverified_reason = reason
        
        def set_as_verified(self) -> None:
            nonlocal unverified_reason
            unverified_reason = None
        
    return _Interface()

