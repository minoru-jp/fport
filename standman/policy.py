
from __future__ import annotations

import enum
import inspect

from pathlib import Path
from threading import Lock
from types import CodeType, FunctionType, TracebackType
from typing import Any, Callable, Generic, Literal, Protocol, TypeVar, cast

from .anchor import Anchor, UnverifiedAnchor, VerifiedAnchor
from .caller import check_in_scope, get_callable_location, get_caller_code, get_caller_location, get_nth_caller_frame
from .observer import ObserveFunction, ProcessObserver

class LeakPolicy(Protocol):
    def get_leak_port(self) -> LeakPort:
        ...
    
    def get_observation_port(self) -> ObservationPort:
        ...
    
    def get_rejected_paths(self) -> dict[Path, dict[Path, int]]:
        ...

class LeakPort(Protocol):
    def get_anchor_verifier(self, accepted_observer_scope: Path | None = None, burst: bool = False, *, deny:bool = False) -> Leakage:
        ...

class Leakage(Protocol):
    def __call__(self, *, deny: bool) -> Anchor:
        ...
    
class ObservationPort(Protocol):
    def session_entry(self, observe_function: ObserveFunction, target: Callable[..., Any]) -> Session:
        ...


# T = TypeVar("T", bound = Callable[..., Any])

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
    
    def get_anchor(self) -> VerifiedAnchor:
        ...
    
    def get_noop_anchor(self) -> VerifiedAnchor:
        ...
    
    def get_invoker(self) -> Callable[..., Any]:
        ...
    
    def get_invocation_identifier(self) -> str:
        ...
    
    def set_unverified_reason(self, reason: SessionUnverifiedReason) -> None:
        ...
    
    def set_as_verified(self) -> None:
        ...

def _create_session_full(observer: ProcessObserver, target: Callable[..., Any], anchor_unit: tuple[VerifiedAnchor, VerifiedAnchor]) -> SessionFull:

    consumed = False
    unverified_reason = SessionUnverifiedReason.PENDING

    invocation_identifier = f"invoke{id(object())}"

    lock = Lock()

    running = False

    def function_template_code(*args, **kwargs) -> Any:
        return target(*args, **kwargs)

    template_code = function_template_code.__code__

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
        globals = function_template_code.__globals__,
        name = invocation_identifier,
        argdefs = function_template_code.__defaults__,
        closure = function_template_code.__closure__
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
        
        def get_anchor(self) -> VerifiedAnchor:
            return anchor_unit[0]
        
        def get_noop_anchor(self) -> VerifiedAnchor:
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

def _create_verified_anchor_unit(
        observe_function: Callable[..., Any],
        policy_definer_location: Path,
        leak_policy: LeakPolicy,
        base_scope: Path,
        observer: ProcessObserver,
        target: Callable[..., Any],
) -> tuple[VerifiedAnchor, VerifiedAnchor]:

    class _Anchor(VerifiedAnchor):
        __slots__ = ()
        def observe(self, *args, **kwargs) -> None:
            try:
                observe_function(*args, **kwargs)
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
        def process_observer(self) -> ProcessObserver:
            return observer
        @property
        def observed_target_function(self) -> Callable[..., Any]:
            return target

    class _NoOpAnchor(VerifiedAnchor):
        __slots__ = ()
        def observe(self, *args, **kwargs) -> None:
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
        def process_observer(self) -> ProcessObserver:
            return observer
        @property
        def observed_target_function(self) -> Callable[..., Any]:
            return target
    
    return (_Anchor(), _NoOpAnchor())


def create_leak_policy(base_scope: Path, *, deny: bool) -> LeakPolicy:

    policy_definer_location = get_caller_location(inspect.currentframe()).resolve(strict = True)

    base_scope_location = base_scope.resolve(strict = True)

    registered_observers: dict[Callable, ProcessObserver] = {} # observe function: ProcessObserver

    unverified_sessions: dict[str, SessionFull] = {} # invocation id: SessionFull
    verified_sessions: dict[str, SessionFull] = {}
    injected_sessions: dict[str, SessionFull] = {}

    deny_on_leak_policy = deny

    MAX_REJECTED_PATHS = 10
    rejected_paths: dict[Path, dict[Path, int]] = {} # scope: list[rejected path, attemps]

    def 

    class _UnverifiedAnchor(UnverifiedAnchor):
        __slots__ = ()
        def observe(self, *args, **kwargs) -> None:
            pass
        @property
        def policy_definer_path(self) -> Path:
            return policy_definer_location
        @property
        def leak_policy(self) -> LeakPolicy:
            return leak_policy
        @property
        def process_observer(self) -> ProcessObserver | None:
            return None
        @property
        def observed_target_function(self) -> Callable[..., Any] | None:
            return None
        @property
        def base_scope(self) -> Path:
            return base_scope_location
    
    NOOP_ANCHOR = _UnverifiedAnchor()

    class _ObservationPort(ObservationPort):
        __slots__ = ()
        def session_entry(self, observer: ProcessObserver, target: Callable[..., Any]) -> Session:
            
            check_in_scope(base_scope_location, get_caller_location(inspect.currentframe()))
            
            observe_function = observer.observe
            check_in_scope(base_scope_location, get_callable_location(observe_function))
            if observe_function in registered_observers:
                raise RuntimeError(f"ProcessObserver has been already registered.")
            
            check_in_scope(base_scope_location, get_callable_location(target))

            anchor_unit = _create_verified_anchor_unit(
                observe_function,
                policy_definer_location,
                leak_policy,
                base_scope_location,
                observer,
                target,
            )
            
            session_full = _create_session_full(observer, target, anchor_unit)

            unverified_sessions[session_full.get_invocation_identifier()] = session_full

            return session_full.get_session()
    
    observation_port = _ObservationPort()

    def get_session_full_with_index(inv_id: str):
        unver = unverified_sessions.get(inv_id)
        ver = verified_sessions.get(inv_id)
        inj = injected_sessions.get(inv_id)
        
        states = [
            ("unverified", unver),
            ("verified", ver),
            ("injected", inj),
        ]

        present = [(name, s) for name, s in states if s]
        if len(present) == 1:
            return present[0]
        else:
            raise RuntimeError("InternalError: session_full in multiple states")


    class _LeakPort(LeakPort):
        __slots__ = ()
        def get_anchor_verifier(self, accepting_observer_scope: Path | None = None, *, deny: bool = False) -> Leakage:
            
            deny_on_anchor_verifier = deny | deny_on_leak_policy

            # check caller is in base scope
            check_in_scope(base_scope_location, get_caller_location(inspect.currentframe()))

            if accepting_observer_scope:
                accepting_observer_scope_location = accepting_observer_scope.resolve(strict = True)
                check_in_scope(base_scope_location, accepting_observer_scope_location)
            

            def leak_port(*, deny: bool = False) -> Anchor:
                try:
                    deny_on_leak_port = deny | deny_on_anchor_verifier
                    
                    f_current = inspect.currentframe()
                    # def target(): # target invoked invoker
                    #    anchor = get_anchor() # get_anchor called caller

                    caller_location = get_caller_location(f_current)
                    check_in_scope(base_scope_location, caller_location)
                    
                    invoker_frame = get_nth_caller_frame(f_current, back = 2)
                    invocation_identifier = invoker_frame.f_code.co_name

                    tag, session_full = get_session_full_with_index(invocation_identifier)

                    match(tag):
                        case "unverified":
                            observer = session_full.get_anchor().process_observer
                            if not observer:
                                session_full.set_unverified_reason(SessionUnverifiedReason.FAILED)
                                raise RuntimeError("Internal error: process_observer should be exist")
                            try:
                                check_in_scope(accepting_observer_scope_location, get_callable_location(observer.observe))
                            except PermissionError:



                    if not session_full:
                        if invocation_identifier in injected_sessions:
                            session_full = 
                        # There is no session, no observer
                        return NOOP_ANCHOR
                    
                    
                    
                    try:
                        
                    except PermissionError:
                        session_full.set_unverified_reason(SessionUnverifiedReason.INVALID)
                        raise
                    if invocation_identifier in unverified_sessions:
                        try:
                            session_full.set_as_verified()
                            unverified_sessions.pop(invocation_identifier)
                            if not deny_on_leak_port:
                                anchor = session_full.get_anchor()
                                session_full.set_as_verified()
                            else:
                                anchor = session_full.get_noop_anchor()
                                session_full.set_unverified_reason(SessionUnverifiedReason.DENIED)
                            return anchor
                        except Exception:
                            # Let an upper-level except clause catch it
                            session_full.set_unverified_reason(SessionUnverifiedReason.FAILED)
                            raise
                    else:
                        session_full.set_unverified_reason(SessionUnverifiedReason.FAILED)
                        raise RuntimeError("Internal Error: Incorrectly accepted a session that had already been consumed.")
                except PermissionError:
                    # Always re-raise permission errors
                    raise
                except Exception:
                    return NOOP_ANCHOR
            
            return leak_port

    leak_port = _LeakPort()

    class _Interface(LeakPolicy):
        __slots__ = ()
        def get_leak_port(self) -> LeakPort:
            return leak_port
        
        def get_observation_port(self) -> ObservationPort:
            return observation_port
        
        def get_rejected_paths(self) -> dict[Path, dict[Path, int]]:
            return {p: {**d} for p, d in rejected_paths.items()}


    leak_policy =  _Interface()

    return leak_policy

