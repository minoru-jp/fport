from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Lock
from typing import TYPE_CHECKING

from .protocols import ListenFunction
from .exceptions import OccupiedError, DeniedError

if TYPE_CHECKING:
    from .policy import _PortBridgeTOC

class Port(ABC):
    __slots__ = ()
    @abstractmethod
    def send(self, tag: str, *args, **kwargs) -> None:
        ...
    @abstractmethod
    def _set_listen_func(self, key: object, listen: ListenFunction) -> None:
        ...
    @abstractmethod
    def _remove_listen_func(self, key: object) -> None:
        ...

def create_port(bridge: _PortBridgeTOC) -> Port:

    lock = Lock()
    listen_func = None
    error = None

    class _Interface(Port):
        __slots__ = ()
        
        def send(self, tag: str, *args, **kwargs) -> None:
            nonlocal error
            bridge.get_message_validator()(tag, *args, **kwargs)
            try:
                if listen_func and not error:
                    listen_func(tag, *args, **kwargs)
            except Exception as e:
                error = e
                session = bridge.get_session(self)
                if session is not None:
                    session.set_error(e)
            finally:
                return None
        
        def _set_listen_func(self, key: object, listen: ListenFunction) -> None:
            nonlocal listen_func
            with lock:
                if key is not bridge.get_permit():
                    raise PermissionError # without any infomation.
                if listen_func is not None:
                    raise OccupiedError("Port is already occupied by another session.")
                listen_func = listen
        
        def _remove_listen_func(self, key: object) -> None:
            nonlocal listen_func
            with lock:
                if key is not bridge.get_permit():
                    raise PermissionError # without any infomation.
                listen_func = None

    interface = _Interface()

    return interface

def create_noop_port(bridge: _PortBridgeTOC) -> Port:
    class _Interface(Port):
        __slots__ = ()
        def send(self, tag: str, *args, **kwargs) -> None:
            pass
        
        def _set_listen_func(self, key: object, listen: ListenFunction) -> None:
            if key is not bridge.get_permit():
                raise PermissionError # without any infomation.
            raise DeniedError("Connection is denied by the policy.")
        
        def _remove_listen_func(self, key: object) -> None:
            if key is not bridge.get_permit():
                raise PermissionError # without any information.

    interface = _Interface()

    return interface

