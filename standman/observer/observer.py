
from __future__ import annotations

from abc import ABC, abstractmethod
import enum
from typing import Callable

class ProcessObserver(ABC):
    '''A complete interface for managing anchors and collecting observations through them.

    For each condition, only the first violation is recorded in detail.'''

    @abstractmethod
    def listen(self, tag: str, *args, **kwargs) -> None:
        ...

    @property
    @abstractmethod
    def violation(self) -> bool:
        '''A flag indicating any violation, regardless of whether it is associated with a defined condition.'''
        ...
    

    @property
    @abstractmethod
    def global_violation(self) -> bool:
        '''A flag indicating a violation not associated with any defined condition.

        This includes cases where the implementation reports using an undefined tag,
        or where an undefined error occurs inside the observe() function.'''
        ...
    
    @property
    @abstractmethod
    def local_violation(self) -> bool:
        '''A flag indicating a violation associated with a defined condition.'''
        ...
    
    @property
    @abstractmethod
    def global_fail_reason(self) -> str:
        ...
    
    @property
    @abstractmethod
    def global_exception(self) -> Exception | None:
        ...

    @abstractmethod
    def get_all_observations(self) -> dict[str, Observation]:
        ...
    
    @abstractmethod
    def get_violated_observations(self) -> dict[str, Observation]:
        ...
    
    @abstractmethod
    def get_compliant_observations(self) -> dict[str, Observation]:
        ...
    
    @abstractmethod
    def set_violation_handler(self, tag: str, fn: Callable[[Observation], None]) -> None:
        '''Registers a handler to be called when a condition violation occurs for the specified tag.

        This handler is invoked each time the corresponding condition is violated.
        If the handler raises an exception, it is immediately suppressed and never propagated
        to the implementation side. No flags or logs are provided to indicate this.

        All handling and side effects are the full responsibility of the handler itself.'''
        ...
    
    @abstractmethod
    def set_exception_handler(self, fn: Callable[[str, ExceptionKind, Observation | None, Exception], None]) -> None:
            ...
    
    @abstractmethod
    def get_condition_stat(self, tag: str) -> ConditionStat:
        ...
    
    @abstractmethod
    def reset_observation(self) -> None:
        ...


class Observation:
    '''Detailed observation results by condition.'''

    __slots__ = ('count', 'violation', 'first_violation_at', 'exc', 'fail_condition', 'fail_reason')
    def __init__(self):
        self.count: int = 0
        self.violation: bool = False
        self.first_violation_at: int = -1
        self.exc: Exception | None = None
        self.fail_condition: Callable[..., bool] | None = None
        self.fail_reason: str = ''


class ConditionStat:
    '''Represents a simplified statistical view for a specific condition.'''

    __slots__ = ('_count', '_violation', '_first_violation_at')
    def __init__(self, count: int, violation: bool, first_violation_at: int):
        self._count = count
        self._violation = violation
        self._first_violation_at = first_violation_at
    
    @property
    def count(self) -> int:
        return self._count
    
    @property
    def violation(self) -> bool:
        return self._violation
    
    @property
    def first_violation_at(self) -> int:
        return self._first_violation_at

class ExceptionKind(enum.Enum):
    ON_CONDITION = 'Exception raised on condition.'
    ON_VIOLATION = 'Exception raised on violation handler'
    ON_INTERNAL = 'Exception raised on internal'

def create_process_observer(conditions: dict[str, Callable[..., bool]]) -> ProcessObserver:

    global_violation = False
    global_fail_reason = ''
    global_exception = None

    local_violation = False

    observations = {tag: Observation() for tag in conditions.keys()}

    violation_handlers = {}

    exception_handler = None

    def _reset_observations() -> None:
        nonlocal global_violation, global_fail_reason, global_exception, local_violation, observations
        global_violation = False
        global_fail_reason = ''
        global_exception = None

        local_violation = False

        observations = {tag: Observation() for tag in conditions.keys()}

    def _call_violation_handler(tag, observation):
        if tag in violation_handlers:
            try:
                violation_handlers[tag](observation)
            except Exception as e:
                _call_exception_handler(tag, ExceptionKind.ON_VIOLATION, observation, e)
                pass
    
    def _call_exception_handler(tag, kind, observation, e):
        if exception_handler:
            try:
                exception_handler(tag, kind, observation, e)
            except Exception:
                pass
    
    def observe(tag: str, *args, **kwargs) -> None:
        try:
            nonlocal global_violation, global_fail_reason, global_exception, local_violation

            if tag not in observations:
                if not global_violation:
                    global_violation = True
                    global_fail_reason = f"wrong tag '{tag}'"
                return
            
            observation = observations[tag]
            condition = conditions[tag]
            pass_ = False
            try:
                pass_ = condition(*args, **kwargs)
            except Exception as e:
                local_violation = True
                if not observation.violation:
                    observation.violation = True
                    observation.first_violation_at = observation.count
                    observation.fail_condition = condition
                    observation.fail_reason = f'exception at {tag} at {observation.count}th attempt'
                    observation.exc = e
                    _call_exception_handler(tag, ExceptionKind.ON_CONDITION, observation, e)
                _call_violation_handler(tag, observation)
                raise


            if not pass_:
                local_violation = True
                if not observation.violation:
                    observation.violation = True
                    observation.first_violation_at = observation.count
                    observation.fail_condition = condition
                    observation.fail_reason = 'condition violation'
                _call_violation_handler(tag, observation)
            
            observation.count += 1
        except Exception as e:
            # overrides all global violations
            global_violation = True
            global_fail_reason = "internal error"
            global_exception = e
            _call_exception_handler(tag, ExceptionKind.ON_INTERNAL, None, e)
            raise
    

    class _Interface(ProcessObserver):
        __slots__ = ()
        def listen(self, tag: str, *args, **kwargs) -> None:
            observe(tag, *args, **kwargs)

        @property
        def violation(self):
            return global_violation or local_violation
        
        @property
        def global_violation(self):
            return global_violation
        
        @property
        def local_violation(self):
            return local_violation
        
        @property
        def global_fail_reason(self) -> str:
            return global_fail_reason
        
        @property
        def global_exception(self) -> Exception | None:
            return global_exception
        
        def get_all_observations(self) -> dict[str, Observation]:
            return {k: v for k, v in observations.items()}
        
        def get_violated_observations(self) -> dict[str, Observation]:
            return {k: v for k, v in observations.items() if v.violation}
        
        def get_compliant_observations(self) -> dict[str, Observation]:
            return {k: v for k, v in observations.items() if not v.violation}
    
        def set_violation_handler(self, tag: str, fn: Callable[[Observation], None]) -> None:
            if tag not in conditions:
                raise ValueError(f"Condition '{tag}' is not defined")
            violation_handlers[tag] = fn
        
        def set_exception_handler(self, fn: Callable[[str, ExceptionKind, Observation | None, Exception], None]) -> None:
            nonlocal exception_handler
            exception_handler = fn

        
        def get_condition_stat(self, tag: str) -> ConditionStat:
            observation = observations[tag]
            stat = ConditionStat(observation.count, observation.violation, observation.first_violation_at)
            return stat
        
        def reset_observation(self) -> None:
            _reset_observations()
    
    return _Interface()

