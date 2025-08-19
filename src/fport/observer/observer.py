
from __future__ import annotations

import enum
from typing import Callable


class ProcessObserver:
    __slots__ = ('_conditions', '_global_violation', '_global_fail_reason', '_global_exception',
                 '_local_violation', '_observations', '_violation_handlers', '_exception_handler')

    def __init__(self, conditions: dict[str, Callable[..., bool]]):
        self._conditions = conditions

        self._global_violation = False
        self._global_fail_reason = ''
        self._global_exception = None

        self._local_violation = False

        self._observations = {tag: Observation() for tag in conditions.keys()}

        self._violation_handlers = {}

        self._exception_handler = None


    def reset_observations(self) -> None:
        self._global_violation = False
        self._global_fail_reason = ''
        self._global_exception = None

        self._local_violation = False

        self._observations = {tag: Observation() for tag in self._conditions.keys()}

    
    def listen(self, tag: str, *args, **kwargs) -> None:
        try:
            if tag not in self._observations:
                if not self._global_violation:
                    self._global_violation = True
                    self._global_fail_reason = f"wrong tag '{tag}'"
                return
            
            observation = self._observations[tag]
            condition = self._conditions[tag]
            pass_ = False
            try:
                pass_ = condition(*args, **kwargs)
            except Exception as e:
                self._local_violation = True
                if not observation.violation:
                    observation.violation = True
                    observation.first_violation_at = observation.count
                    observation.fail_condition = condition
                    observation.fail_reason = f'exception at {tag} at {observation.count}th attempt'
                    observation.exc = e
                    self._call_exception_handler(tag, ExceptionKind.ON_CONDITION, observation, e)
                self._call_violation_handler(tag, observation)


            if not pass_:
                self._local_violation = True
                if not observation.violation:
                    observation.violation = True
                    observation.first_violation_at = observation.count
                    observation.fail_condition = condition
                    observation.fail_reason = 'condition violation'
                self._call_violation_handler(tag, observation)
            
            observation.count += 1
        except Exception as e:
            # overrides all global violations
            self._global_violation = True
            self._global_fail_reason = "internal error"
            self._global_exception = e
            self._call_exception_handler(tag, ExceptionKind.ON_INTERNAL, None, e)


    def _call_violation_handler(self, tag, observation):
        if tag in self._violation_handlers:
            try:
                self._violation_handlers[tag](observation)
            except Exception as e:
                self._call_exception_handler(tag, ExceptionKind.ON_VIOLATION, observation, e)
                pass
    
    def _call_exception_handler(self, tag, kind, observation, e):
        if self._exception_handler:
            try:
                self._exception_handler(tag, kind, observation, e)
            except Exception:
                pass
    
    @property
    def violation(self):
        return self._global_violation or self._local_violation
    
    @property
    def global_violation(self):
        return self._global_violation
    
    @property
    def local_violation(self):
        return self._local_violation
    
    @property
    def global_fail_reason(self) -> str:
        return self._global_fail_reason
    
    @property
    def global_exception(self) -> Exception | None:
        return self._global_exception
    
    def get_all(self) -> dict[str, Observation]:
        return {k: v for k, v in self._observations.items()}
    
    def get_violated(self) -> dict[str, Observation]:
        return {k: v for k, v in self._observations.items() if v.violation}
    
    def get_compliant(self) -> dict[str, Observation]:
        return {k: v for k, v in self._observations.items() if not v.violation}
    
    def get_unevaluated(self) -> dict[str, Observation]:
        return {k: v for k, v in self._observations.items() if v.count == 0}

    def set_violation_handler(self, tag: str, fn: Callable[[Observation], None]) -> None:
        if tag not in self._conditions:
            raise ValueError(f"Condition '{tag}' is not defined")
        self._violation_handlers[tag] = fn
    
    def set_exception_handler(self, fn: Callable[[str, ExceptionKind, Observation | None, Exception], None]) -> None:
        self._exception_handler = fn

    def get_stat(self, tag: str) -> ConditionStat:
        observation = self._observations[tag]
        stat = ConditionStat(observation.count, observation.violation, observation.first_violation_at)
        return stat


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

