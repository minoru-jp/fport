
from __future__ import annotations

import enum
import inspect

from pathlib import Path
from types import CodeType, FunctionType, TracebackType
from typing import Any, Callable, Generic, Literal, Protocol, TypeVar, cast

from .anchor import Anchor, NOOP_ANCHOR
from .caller import get_callable_location, get_caller_code, get_caller_location, get_nth_caller_frame
from .observer import ObserveFunction

class LeakPolicy(Protocol):
    def get_leak_port(self) -> LeakPort:
        ...
    
    def get_observation_port(self) -> ObservationPort:
        ...

class LeakPort(Protocol):
    def get_anchor_verifier(self, accepted_observer_scope: Path | None = None, burst: bool = False) -> Callable[[], Anchor]:
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
    DENIED = "Verification failed due to policy constraints"
    FAILED = "Policy verification failed due to internal error"
    def __bool__(self):
        return False
    def __str__(self):
        return self.value


class SessionFull(Protocol):
    def get_session(self) -> Session:
        ...
    
    def get_anchor(self) -> Anchor:
        ...
    
    def get_invoker(self) -> Callable[..., Any]:
        ...
    
    def get_invocation_identifier(self) -> str:
        ...
    
    def set_unverified_reason(self, reason: SessionUnverifiedReason) -> None:
        ...
    
    def set_as_verified(self) -> None:
        ...

def _create_session_full(target: Callable[..., Any], anchor: Anchor) -> SessionFull:

    consumed = False
    unverified_reason = SessionUnverifiedReason.PENDING

    invocation_identifier = f"invoke{id(object())}"

    def function_template_code(*args, **kwargs) -> Any:
        nonlocal consumed
        if consumed:
            raise RuntimeError(f"This session has already ended. id = {invocation_identifier}")
        result = target(*args, **kwargs)
        consumed = True
        return result

    template_code = function_template_code.__code__

    # invoker_code = CodeType(
    #     template_code.co_argcount,
    #     template_code.co_posonlyargcount,
    #     template_code.co_kwonlyargcount,
    #     template_code.co_nlocals,
    #     template_code.co_stacksize,
    #     template_code.co_flags,
    #     template_code.co_code,
    #     template_code.co_consts,
    #     template_code.co_names,
    #     template_code.co_varnames,
    #     template_code.co_filename,
    #     invocation_identifier,
    #     template_code.co_firstlineno,
    #     template_code.co_lnotab,
    #     template_code.co_freevars,
    #     template_code.co_cellvars
    # )

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
            return invoker

        def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
            pass

        def get_invocation_identifier(self) -> str:
            return invocation_identifier
    
    session = _Session()

    class _Interface(SessionFull):
        __slots__ = ()
        def get_session(self) -> Session:
            return session
        
        def get_anchor(self) -> Anchor:
            return anchor
        
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



def create_leak_policy(observer_scope: Path | None = None, target_scope: Path | None = None) -> LeakPolicy:

    policy_definer_location = get_caller_location(inspect.currentframe()).resolve(strict = True)

    observer_scope_location = observer_scope.resolve(strict = True) if observer_scope else Path.cwd().resolve(strict = True)
    target_scope_location = target_scope.resolve(strict = True) if target_scope else Path.cwd().resolve(strict = True)

    unverified_sessions: dict[str, SessionFull] = {} # invocation id: SessionFull

    class _ObservationPort(ObservationPort):
        __slots__ = ()
        def session_entry(self, observe_function: ObserveFunction, target: Callable[..., Any]) -> Session:

            if target.__code__ in unverified_sessions:
                raise RuntimeError(
                    f"Session already registered for this function: {target.__name__} "
                    f"(code object id: {id(target.__code__)})"
                )
            
            requirer_location = get_caller_location(inspect.currentframe())
            if observer_scope_location not in requirer_location.parents:
                raise PermissionError(f"Session request denied: caller is outside of observer scope. (caller: {requirer_location})")
            observe_location = get_callable_location(observe_function)
            if observer_scope_location not in observe_location.parents:
                raise PermissionError(f"Session request denied: observe function is outside of observer scope. (observe: {observe_location})")
            target_location = get_callable_location(target)
            if target_scope_location not in target_location.parents:
                raise PermissionError(f"Session request denied: target function is outside of target scope. (target: {target_location})")
            

            burst = False

            class _Anchor(Anchor):
                def observe(self, *args, **kwargs) -> None:
                    try:
                        observe_function(*args, **kwargs)
                    except Exception:
                        if burst:
                            raise
                    
                def policy_definer_path(self) -> Path:
                    return policy_definer_location
                
                def enable_burst(self, flag: bool):
                    nonlocal burst
                    burst = flag
    
                def source_module_path(self) -> Path:
                    return observe_location
                
                def observed_target_function(self) -> CodeType:
                    return target.__code__
                
                def observer_scope_path(self) -> Path:
                    return observer_scope_location

                def observed_target_scope_path(self) -> Path:
                    return target_scope_location
            
            session_full = _create_session_full(target, _Anchor())

            unverified_sessions[session_full.get_invocation_identifier()] = session_full

            return session_full.get_session()
    
    observation_port = _ObservationPort()

    class _LeakPort(LeakPort):
        __slots__ = ()
        def get_anchor_verifier(self, accepting_observer_scope: Path | None = None, burst: bool = False) -> Callable[[], Anchor]:

            requirer_location = get_caller_location(inspect.currentframe())
            if target_scope_location not in requirer_location.parents:
                raise PermissionError(f"Leak port request denied: caller is outside of target scope. (caller: {requirer_location})")
            
            if accepting_observer_scope is None:
                accepting_observer_scope = Path.cwd().resolve()
            accepting_observer_scope_location = accepting_observer_scope.resolve(strict = True)
            try:
                accepting_observer_scope_location.relative_to(observer_scope_location)
            except ValueError:
                raise PermissionError(f"Leak port request denied: accepted observer scope must be within the actual observer scope.\n"
                     f"(actual observer: {observer_scope_location}, requested accepted: {accepting_observer_scope_location})")
            
            if accepting_observer_scope_location != policy_definer_location.parent:
                raise PermissionError("Leak port request denied: observer scope must match policy definer's module directory")

            def leak_port() -> Anchor:
                try:
                    
                    f_current = inspect.currentframe()

                    # def target(): # target invoked invoker
                    #    anchor = get_anchor() # get_anchor called caller

                    invoker_frame = get_nth_caller_frame(f_current, back = 2)
                    invocation_identifier = invoker_frame.f_code.co_name
                    session_full = unverified_sessions.get(invocation_identifier)
                    
                    caller_location = get_caller_location(f_current)

                    if not session_full:
                        return NOOP_ANCHOR
                    
                    if invocation_identifier in unverified_sessions:
                        try:
                            if target_scope_location in caller_location.parents:
                                session_full.set_as_verified()
                                unverified_sessions.pop(invocation_identifier)
                                return session_full.get_anchor()
                            else:
                                session_full.set_unverified_reason(SessionUnverifiedReason.DENIED)
                                raise PermissionError("Verifier must be called from within target_scope directory")
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
                    if burst:
                        raise
                    return NOOP_ANCHOR
            
            return leak_port

    leak_port = _LeakPort()

    class _Interface(LeakPolicy):
        __slots__ = ()
        def get_leak_port(self) -> LeakPort:
            return leak_port
        
        def get_observation_port(self) -> ObservationPort:
            return observation_port


    return _Interface()

