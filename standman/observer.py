
from __future__ import annotations

import inspect
from types import FunctionType
from typing import Any, Callable, Protocol


class ProcessObserver(Protocol):
    '''A complete interface for managing anchors and collecting observations through them.

    For each condition, only the first violation is recorded in detail.'''

    @property
    def observe(self) -> ObserveFunction:
        ...

    @property
    def violation(self) -> bool:
        '''A flag indicating any violation, regardless of whether it is associated with a defined condition.'''
        ...
    
    @property
    def global_violation(self) -> bool:
        '''A flag indicating a violation not associated with any defined condition.

        This includes cases where the implementation reports using an undefined tag,
        or where an undefined error occurs inside the observe() function.'''
        ...
    
    @property
    def local_violation(self) -> bool:
        '''A flag indicating a violation associated with a defined condition.'''
        ...
    
    @property
    def global_fail_reason(self) -> str:
        ...
    
    @property
    def global_exception(self) -> Exception | None:
        ...

    def get_all_observations(self) -> dict[str, Observation]:
        ...
    
    def get_violated_observations(self) -> dict[str, Observation]:
        ...
    
    def get_compliant_observations(self) -> dict[str, Observation]:
        ...

    def set_observe_handler(self, tag: str, fn: Callable[..., None]) -> None:
        ...
    
    def set_violation_handler(self, tag: str, fn: Callable[[Observation], None]) -> None:
        '''Registers a handler to be called when a condition violation occurs for the specified tag.

        This handler is invoked each time the corresponding condition is violated.
        If the handler raises an exception, it is immediately suppressed and never propagated
        to the implementation side. No flags or logs are provided to indicate this.

        All handling and side effects are the full responsibility of the handler itself.'''
        ...
    
    def get_condition_stat(self, tag: str) -> ConditionStat:
        ...
    
    def reset_observation(self) -> None:
        ...

class ObserveFunction(Protocol):
    def __call__(self, tag: str, *args: Any, **kwargs: Any) -> None:
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

def create_process_observer(conditions: dict[str, Callable[..., bool]]) -> ProcessObserver:

    global_violation = False
    global_fail_reason = ''
    global_exception = None

    local_violation = False

    observations = {tag: Observation() for tag in conditions.keys()}

    observe_handlers = {}

    violation_handlers = {}

    def _reset_observations() -> None:
        nonlocal global_violation, global_fail_reason, global_exception, local_violation, observations
        global_violation = False
        global_fail_reason = ''
        global_exception = None

        local_violation = False

        observations = {tag: Observation() for tag in conditions.keys()}

    def _call_observe_handler(tag, *args, **kwargs):
        if tag in observe_handlers:
            try:
                observe_handlers[tag](*args, **kwargs)
            except Exception:
                pass

    def _call_violation_handler(tag, observation):
        if tag in violation_handlers:
            try:
                violation_handlers[tag](observation)
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
                _call_observe_handler(tag, *args, **kwargs)
                pass_ = condition(*args, **kwargs)
            except Exception as e:
                local_violation = True
                if not observation.violation:
                    observation.violation = True
                    observation.first_violation_at = observation.count
                    observation.fail_condition = condition
                    observation.fail_reason = f'exception at {tag} at {observation.count}th attempt'
                    observation.exc = e
                _call_violation_handler(tag, observation)
                return


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
        finally:
            return
    

    class _ProcessObserver(ProcessObserver):
        __slots__ = ()
        @property
        def observe(self) -> ObserveFunction:
            return observe

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
        
        def set_observe_handler(self, tag: str, fn: Callable[..., None]) -> None:
            if tag not in conditions:
                raise ValueError(f"Condition '{tag}' is not defined")
            sig_handler = inspect.signature(fn)
            sig_condition = inspect.signature(conditions[tag])
            if sig_handler != sig_condition:
                raise TypeError("The call signature of the provided handler must exactly match that of the condition function.")
            observe_handlers[tag] = fn
    
        def set_violation_handler(self, tag: str, fn: Callable[[Observation], None]) -> None:
            if tag not in conditions:
                raise ValueError(f"Condition '{tag}' is not defined")
            violation_handlers[tag] = fn
        
        def get_condition_stat(self, tag: str) -> ConditionStat:
            observation = observations[tag]
            stat = ConditionStat(observation.count, observation.violation, observation.first_violation_at)
            return stat
        
        def reset_observation(self) -> None:
            _reset_observations()
    
    return _ProcessObserver()

