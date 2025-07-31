
from __future__ import annotations

import inspect

from pathlib import Path
from types import CodeType, FunctionType, TracebackType
from typing import Any, Callable, Generic, Literal, Protocol, TypeVar, cast

from .listener import Listener
from .session import Session, SessionFull, SessionUnverifiedReason, create_session_full
from .port import Port, UnverifiedPort, VerifiedPort, create_verified_port_unit
from .caller import check_in_scope, get_callable_location, get_caller_code, get_caller_location, get_nth_caller_frame

class LeakPolicy(Protocol):
    def get_leak_implementation(self) -> LeakImplementation:
        ...
    
    def session_entry(self) -> Session:
        ...
    
    def get_rejected_paths(self) -> dict[Path, dict[Path, int]]:
        ...

class LeakImplementation(Protocol):
    def get_port_dispatcher(self, accepted_observer_scope: Path | None = None, *, deny:bool = False, verify: Literal[True] | None = None) -> PortDispatcher:
        ...

class PortDispatcher(Protocol):
    def __call__(self, *, deny: bool = False, verify: Literal[True] | None = None) -> Port:
        ...



def create_leak_policy(base_scope: Path, *, deny: bool = False, absolute_deny: Literal[True] | None = None, tag_maxlen: int | None = None, bad_chars: frozenset[str] = frozenset()) -> LeakPolicy:

    deny_on_leak_policy = deny
    
    policy_definer_location = get_caller_location(inspect.currentframe()).resolve(strict = True)

    base_scope_location = base_scope.resolve(strict = True)

    registered_observers: dict[Callable, Listener] = {} # observe function: ProcessObserver

    unverified_sessions: dict[str, SessionFull] = {} # invocation id: SessionFull
    verified_sessions: dict[str, SessionFull] = {} # invocation id: SessionFull

    MAX_REJECTED_PATHS = 10
    # scope: dict[tuple[reason, rejected path], attemps]
    rejected_paths: dict[Path, dict[tuple[str, Path], int]] = {} 

    class _UnverifiedPort(UnverifiedPort):
        __slots__ = ()
        def leak(self, *args, **kwargs) -> None:
            pass
        @property
        def policy_definer_path(self) -> Path:
            return policy_definer_location
        @property
        def leak_policy(self) -> LeakPolicy:
            return leak_policy
        @property
        def listener(self) -> Listener | None:
            return None
        @property
        def listened_function(self) -> Callable[..., Any] | None:
            return None
        @property
        def base_scope(self) -> Path:
            return base_scope_location
    
    UNVERIFIED_NOOP_PORT = _UnverifiedPort()


    def verify_path(tag: str, base: Path, target: Path):
        try:
            check_in_scope(base, target)
        except PermissionError:
            base_map = rejected_paths.setdefault(base, {})
            reason = (tag, target)
            if reason in base_map:
                base_map[reason] += 1
            else:
                if len(base_map) + 1 > MAX_REJECTED_PATHS:
                    base_map.pop(next(iter(base_map)))
                base_map[reason] = 1
            raise
    
    def verify_path_no_raise(tag: str, base: Path, target: Path) -> bool:
        try:
            verify_path(tag, base, target)
            return True
        except PermissionError:
            return False

    def get_session_full_with_index(inv_id: str):
        unver = unverified_sessions.get(inv_id)
        ver = verified_sessions.get(inv_id)
        
        states = [
            ("unverified", unver),
            ("verified", ver),
        ]

        present = [(name, s) for name, s in states if s]
        if len(present) == 1:
            return present[0]
        else:
            raise RuntimeError("InternalError: session_full in multiple states")


    class _LeakImplementation(LeakImplementation):
        __slots__ = ()
        def get_port_dispatcher(self, accepting_observer_scope: Path | None = None, *, deny: bool = False, verify: Literal[True] | None = None) -> PortDispatcher:
            
            deny_on_anchor_verifier = not verify if verify is not None else deny | deny_on_leak_policy

            # check caller is in base scope
            verify_path('anchor verifier: caller', base_scope_location, get_caller_location(inspect.currentframe()))

            if accepting_observer_scope:
                accepting_observer_scope_location = accepting_observer_scope.resolve(strict = True)
                verify_path('anchor verifier: observer scope', base_scope_location, accepting_observer_scope_location)
            

            def leak_port(*, deny: bool = False, verify: Literal[True] | None = None) -> Port:
                try:
                    deny_on_leak_port = not verify if verify is not None else deny | deny_on_anchor_verifier

                    f_current = inspect.currentframe()
                    if not f_current:
                        return UNVERIFIED_NOOP_PORT

                    # def target(): # target invoked invoker
                    #    anchor = get_anchor() # get_anchor called caller

                    caller_location = get_caller_location(f_current)
                    if not verify_path_no_raise('leak port: caller', base_scope_location, caller_location):
                        return UNVERIFIED_NOOP_PORT
                    
                    invoker_frame = get_nth_caller_frame(f_current, back = 2)
                    invocation_identifier = invoker_frame.f_code.co_name

                    tag, session = get_session_full_with_index(invocation_identifier)

                    match(tag):
                        case "unverified":
                            observer = session.get_port().listener
                            if not observer:
                                session.set_unverified_reason(SessionUnverifiedReason.FAILED)
                                raise RuntimeError("Internal error: process_observer should be exist")
                            if not verify_path_no_raise('leak port: out of observed target scope',
                                    accepting_observer_scope_location, get_callable_location(observer.observe)):
                                return UNVERIFIED_NOOP_PORT
                            if not deny_on_leak_port and not absolute_deny:
                                session.set_as_verified()
                                verified_sessions[invocation_identifier] = unverified_sessions.pop(invocation_identifier)
                                return session.get_port()
                            else:
                                session.set_unverified_reason(SessionUnverifiedReason.DENIED)
                                anchor = session.get_noop_port()
                        case "verified":
                            injected_sessions[invocation_identifier] = verified_sessions.pop(invocation_identifier)
                            return session.get_port()




                    if not session:
                        if invocation_identifier in injected_sessions:
                            session = 
                        # There is no session, no observer
                        return UNVERIFIED_NOOP_PORT
                    
                    
                    
                    try:
                        
                    except PermissionError:
                        session.set_unverified_reason(SessionUnverifiedReason.INVALID)
                        raise
                    if invocation_identifier in unverified_sessions:
                        try:
                            session.set_as_verified()
                            unverified_sessions.pop(invocation_identifier)
                            if not deny_on_leak_port:
                                anchor = session.get_port()
                                session.set_as_verified()
                            else:
                                anchor = session.get_noop_port()
                                session.set_unverified_reason(SessionUnverifiedReason.DENIED)
                            return anchor
                        except Exception:
                            # Let an upper-level except clause catch it
                            session.set_unverified_reason(SessionUnverifiedReason.FAILED)
                            raise
                    else:
                        session.set_unverified_reason(SessionUnverifiedReason.FAILED)
                        raise RuntimeError("Internal Error: Incorrectly accepted a session that had already been consumed.")
                except PermissionError:
                    # Always re-raise permission errors
                    raise
                except Exception:
                    return UNVERIFIED_NOOP_PORT
            
            return leak_port

    leak_implementation = _LeakImplementation()

    def validate_tag(tag: str):
        if not isinstance(tag, str):
            raise TypeError(f"tag must be a string, got {type(tag).__name__}")
        if tag_maxlen:
            if len(tag) > tag_maxlen:
                raise ValueError(f"tag length exceeds maximum of {tag_maxlen}")
        if any(c in bad_chars for c in tag):
            raise ValueError(f"tag contains disallowed characters: {bad_chars}")
        
    class _Interface(LeakPolicy):
        __slots__ = ()
        def get_leak_implementation(self) -> LeakImplementation:
            return leak_implementation
        
        def session_entry(self, listener: Listener, target: Callable[..., Any]) -> Session:
            
            verify_path('session entry: caller', base_scope_location, get_caller_location(inspect.currentframe()))
            
            listen_function = listener.listen
            verify_path('session entry: observe function', base_scope_location, get_callable_location(listen_function))
            if listen_function in registered_observers:
                raise RuntimeError(f"ProcessObserver has been already registered.")
            
            verify_path('session entry: observed target', base_scope_location, get_callable_location(target))

            anchor_unit = create_verified_port_unit(
                listener,
                policy_definer_location,
                leak_policy,
                base_scope_location,
                target,
                validate_tag,
            )
            
            session_full = create_session_full(target, anchor_unit)

            unverified_sessions[session_full.get_invocation_identifier()] = session_full

            return session_full.get_session()
        
        def get_rejected_paths(self) -> dict[Path, dict[Path, int]]:
            return {p: {**d} for p, d in rejected_paths.items()}


    leak_policy =  _Interface()

    return leak_policy

