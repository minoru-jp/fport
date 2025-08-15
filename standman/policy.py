
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from threading import Lock
from typing import ContextManager, Protocol
from contextlib import contextmanager

from .port import Port, create_port, create_noop_port
from .protocols import ListenFunction, SendFunction
from .session import Session, SessionState

class SessionPolicy(ABC):
    @abstractmethod
    def create_port(self) -> Port:
        ...
    @abstractmethod
    def create_noop_port(self) -> Port:
        ...
    @abstractmethod
    def session(self, listener: ListenFunction, target: Port) -> ContextManager[SessionState]:
        ...

class _ConstantTOC(Protocol):
    DEFAULT_MESSAGE_VALIDATOR: SendFunction

class _StateTOC(Protocol):
    local_lock: Lock

    session_map: dict[Port, Session]

    mess_validator: SendFunction

    permit: object

class _CoreTOC(Protocol):
    def register_session(self, listen: ListenFunction, target: Port) -> None:
        ...
    
    def unregister_session(self, target: Port) -> None:
        ...

    def create_port(self, permit: object) -> Port:
        ...
    
    def create_noop_port(self, permit: object) -> Port:
        ...
    
    def session(self, listen: ListenFunction, target: Port) -> ContextManager[SessionState]:
        ...

class _PortBridgeTOC(Protocol):
    def get_session(self, port: Port) -> Session | None:
        ...
    
    def get_permit(self) -> object:
        ...
    
    def get_message_validator(self) -> SendFunction:
        ...

class _RoleTOC(Protocol):
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
        DEFAULT_MESSAGE_VALIDATOR: SendFunction = lambda tag, *a, **kw: None
    
    constant = _Constant()


    @dataclass(slots = True)
    class _State(_StateTOC):
        local_lock: Lock = field(default_factory = Lock)

        session_map: dict[Port, Session] = field(default_factory = dict)

        mess_validator: SendFunction = field(default = message_validator if message_validator else constant.DEFAULT_MESSAGE_VALIDATOR)

        permit: object = field(default = object())

    state = _State()

    class _Core(_CoreTOC):
        
        def register_session(self, listen: ListenFunction, target: Port) -> Session:
            with state.local_lock:

                target._set_listen_func(state.permit, listen)
                
                if target in state.session_map:
                    raise RuntimeError("A session for this target is already registered.")
                
                session = Session()
                state.session_map[target] = session
            
            return session
        
        
        def unregister_session(self, target: Port) -> None:
            with state.local_lock:
                try:
                    target._remove_listen_func(state.permit)
                    state.session_map.pop(target)
                except KeyError as e:
                    raise RuntimeError(f"Session not found") from e

        def create_port(self) -> Port:
            if not block_port:
                return create_port(port_bridge)
            else:
                return create_noop_port(port_bridge)
        
        def create_noop_port(self) -> Port:
            return create_noop_port(port_bridge)
        
        def session(self, listen: ListenFunction, target: Port) -> ContextManager[SessionState]:
            if not isinstance(target, Port):
                raise TypeError(f"target must be Port but receives '{type(target)}'")
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
        
        def get_permit(self) -> object:
            return state.permit
        
        def get_message_validator(self):
            return state.mess_validator
    
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
    role = _create_session_policy_role(
        block_port = block_port,
        message_validator= message_validator)
    return role.interface


if __name__ == '__main__':
    pass
