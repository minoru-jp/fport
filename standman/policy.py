"""
SessionPolicy implementation for standman.

This module provides the SessionPolicy interface and its factory
function create_session_policy(). A SessionPolicy manages Port
creation and session lifecycle, controlling how senders and
listeners are linked together.


Notes
-----

The implementation of this module is based on the `Verbose Pattern`,
which is intended to structure the implementation.

Verbose Pattern:
    https://github.com/minoru-jp/design-notes/blob/main/verbose-pattern/README.md

"""


from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from threading import Lock
from typing import Callable, ContextManager, Protocol, cast
from contextlib import contextmanager

from .port import Port, _create_port, _create_noop_port
from .protocols import ListenFunction, SendFunction
from .session import Session, SessionState
from .exceptions import DeniedError

class SessionPolicy(ABC):
    """Management interface for creating Ports and sessions."""

    @abstractmethod
    def create_port(self) -> Port:
        """Create a Port available for connections."""
    @abstractmethod
    def create_noop_port(self) -> Port:
        """Create a Port that rejects connections."""

    @abstractmethod
    def session(self, listener: ListenFunction, target: Port) -> ContextManager[SessionState]:
        """
        Establish a connection to the specified Port.

        Args:
            listener:
                Handler for inputs sent to the target.
            target:
                The Port to connect to.

        Raises:
            OccupiedError:
                Raised if another session has already started for the target.
            DeniedError:
                Raised if the Port or SessionPolicy is configured to reject connections.

        Returns:
            A context manager that controls the start and end of the session.
        """

# _*TOC: TOC = Table of Content

class _ConstantTOC(Protocol):
    """Internal structure: constants"""
    SENTINELS: dict[str, Callable]

class _StateTOC(Protocol):
    """Internal structure: state variables"""
    local_lock: Lock

    session_map: dict[Port, Session]

    mess_validator: tuple[Callable]

    entry_permit: object
    control_permit: object

class _CoreTOC(Protocol):
    """Internal structure: core functions"""
    def register_session(self, listen: ListenFunction, target: Port) -> Session:
        ...
    
    def unregister_session(self, target: Port) -> None:
        ...

    def create_port(self) -> Port:
        ...
    
    def create_noop_port(self) -> Port:
        ...
    
    def session(self, listen: ListenFunction, target: Port) -> ContextManager[SessionState]:
        ...

class _PortBridgeTOC(Protocol):
    """Internal structure: delegation functions for Port"""
    def get_session(self, port: Port) -> Session | None:
        ...

    def get_entry_permit(self):
        ...
    
    def get_control_permit(self) -> object:
        ...
    
    def get_message_validator(self) -> SendFunction:
        ...
    


class _RoleTOC(Protocol):
    """Internal structure: accessors to role-specific interfaces"""
    constant: _ConstantTOC
    state: _StateTOC
    core: _CoreTOC
    port_bridge: _PortBridgeTOC
    interface: SessionPolicy


def _create_session_policy_role(
        *,
        block_port: bool = False,
        message_validator: SendFunction | None = None
) -> _RoleTOC:

    class _Constant(_ConstantTOC):
        __slots__ = ()
        SENTINELS = {"DEFAULT_MESSAGE_VALIDATOR": lambda tag, *a, **kw: None}
    
    constant = _Constant()


    class _State(_StateTOC):
        __slots__ = ()

        local_lock: Lock = Lock()

        session_map: dict[Port, Session] = {}

        entry_permit: object = object()
        control_permit: object = object()

        mess_validator = (message_validator if message_validator else constant.SENTINELS["DEFAULT_MESSAGE_VALIDATOR"],)

    state = _State()

    class _Core(_CoreTOC):
        
        def register_session(self, listen: ListenFunction, target: Port) -> Session:
            with state.local_lock:

                target._set_listen_func(state.control_permit, listen)
                
                if target in state.session_map:
                    target._remove_listen_func(state.control_permit)
                    raise RuntimeError("Internal error: A session for this target is already registered.")
                
                session = Session()
                state.session_map[target] = session
            
            return session
        
        
        def unregister_session(self, target: Port) -> None:
            with state.local_lock:
                try:
                    target._remove_listen_func(state.control_permit)
                    state.session_map.pop(target)
                except KeyError as e:
                    raise RuntimeError(f"Internal error: Session not found") from e

        def create_port(self) -> Port:
            if not block_port:
                return _create_port(port_bridge)
            else:
                return _create_noop_port(port_bridge)
        
        def create_noop_port(self) -> Port:
            return _create_noop_port(port_bridge)
        
        def session(self, listen: ListenFunction, target: Port) -> ContextManager[SessionState]:
            if not isinstance(target, Port):
                raise TypeError(f"target must be Port but receives '{type(target)}'")
            
            if target._get_entry_permit() is not state.entry_permit:
                raise DeniedError("target is not created by this policy.")
            
            @contextmanager
            def session_context():
                session = core.register_session(listen, target)
                yield session.get_state_reader()
                core.unregister_session(target)
                
            return session_context()
    
    core = _Core()

    class _PortBridge(_PortBridgeTOC):
        def get_session(self, port: Port) -> Session | None:
            with state.local_lock:
                return state.session_map.get(port, None)
        
        def get_entry_permit(self):
            return state.entry_permit
        
        def get_control_permit(self) -> object:
            return state.control_permit
        
        def get_message_validator(self):
            return state.mess_validator[0]
    
    port_bridge = _PortBridge()

    class _Interface(SessionPolicy):
        def create_port(self) -> Port:
            return core.create_port()
        
        def create_noop_port(self) -> Port:
            return core.create_noop_port()
        
        def session(self, listener: ListenFunction, target: Port) -> ContextManager[SessionState]:
            return core.session(listener, target)

    interface = _Interface()


    @dataclass(slots = True)
    class _Role(_RoleTOC):
        constant: _ConstantTOC
        state: _StateTOC
        core: _CoreTOC
        port_bridge: _PortBridgeTOC
        interface: SessionPolicy

    return _Role(
        constant = constant,
        state = state,
        core = core,
        port_bridge = port_bridge,
        interface = interface)


def create_session_policy(
        *,
        block_port = False,
        message_validator: SendFunction | None = None
) -> SessionPolicy:
    """
    Create a SessionPolicy interface.

    Args:
        block_port:
            If True, connections to Ports created by this policy will be rejected.
        message_validator:
            A function to validate messages before Port.send() is called.
            By raising an exception, the send can be rejected.
            Exceptions raised by this validator are not propagated from Port.send(),
            and instead the session ends silently. Such errors can be detected
            through the receiver's SessionState.

    Returns:
        SessionPolicy:
            An interface for creating Ports and establishing sessions.
    """
    role = _create_session_policy_role(
        block_port = block_port,
        message_validator= message_validator)
    return role.interface



