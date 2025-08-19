# fport

## Version

[![PyPI version](https://img.shields.io/pypi/v/fport.svg)](https://pypi.org/project/fport/)

## Overview

A generic unidirectional function coupling module based on loose coupling.

This module provides an interface for the implementation side to send information.

## Main Purpose and Use Cases

* Submitting information from the implementation side for white-box testing
* Creating entry points for simple add-ons

## Supported Environment

* Python 3.10 or later
* No external dependencies

## License

This module is provided under the MIT License.
See the [LICENSE](./LICENSE) file for details.

## Installation

PyPI
```bash
pip install fport
```

GitHub
```bash
pip install git+https://github.com/minoru_jp/fport.git
```

## Features

* Provides a communication channel to the implementation side with minimal setup.
* Designed so that the sending interface has no side effects on the implementation side (only computation cost on the receiving side).
* The sending interface does not propagate errors from the receiver or framework to the implementation side.
* The sending interface always returns `None`.
* The scope of information transfer can be flexibly defined by where and how the interface is defined and shared.
* You can configure the sending interface to reject connections.
* Even if the connection is rejected, the implementation side always gets a valid interface.

## Warning

The communication mechanism adopted by this module is loosely coupled and does not explicitly specify the destination from the implementation side.
Information transmitted from the implementation must be carefully considered. Careless transmission may lead to leaks of authentication data, personal information, or other critical data. The same applies to information that can be reconstructed into such sensitive data.

## About Parallel Processing

The sending interface is **thread-unsafe**.
This design avoids unintended serialization on the implementation side.
Maintaining overall consistency, including the use of interfaces in parallel processing, is the responsibility of the implementation side.

## Simple Usage Example

```python
from fport import create_session_policy

policy = create_session_policy()
port = policy.create_port()

def add(a, b):
    port.send("add", a, b)
    return a + b

def listener(tag, *args, **kwargs):
    print("Received:", tag, args, kwargs)

with policy.session(listener, port) as state:
    result = add(2, 3)
    print("Result:", result)

# Output:
# Received: add (2, 3) {}
# Result: 5
```

---

## Main API Reference

### `create_session_policy(*, block_port: bool = False, message_validator: SendFunction | None = None) -> SessionPolicy`

Factory function to generate a `SessionPolicy`.

* **Parameters**

  * `block_port: bool`
    If `True`, all `Port`s created by this policy reject connections.
  * `message_validator: SendFunction | None`
    Optional validation function for sending. Called before `Port.send()`.
    If an exception is raised, the send is rejected.
    The exception does not propagate to the sender; instead, it is treated as a session termination.

* **Returns**
  `SessionPolicy`

---

### `class SessionPolicy`

Interface for managing `Port` creation and session establishment.

* **Methods**

  * `create_port() -> Port`
    Creates a connectable `Port`.

  * `create_noop_port() -> Port`
    Creates a no-op `Port` that rejects connections.

  * `session(listener: ListenFunction, target: Port) -> ContextManager[SessionState]`
    Returns a context manager to start a session by connecting `listener` to the specified `Port`.

    * **Parameters**

      * `listener: ListenFunction`
        A callback function that receives messages sent via `Port.send()`.
        Takes arguments `(tag: str, *args, **kwargs)`.
      * `target: Port`
        The target `Port` instance.

    * **Returns**
      `ContextManager[SessionState]`
      Used in a `with` block. Provides `SessionState` for monitoring with `ok` and `error`.

    * **Exceptions**

      * `TypeError`: If `target` is not a `Port` instance
      * `OccupiedError`: If the specified `Port` is already used by another session
      * `DeniedError`: If the `Port` or `SessionPolicy` is set to reject connections
      * `RuntimeError`: Unexpected internal inconsistencies

---

### `class Port`

Interface for the implementation (sending side) to transmit information.

* **Methods**

  * `send(tag: str, *args, **kwargs) -> None`
    Sends arbitrary information to registered listeners.

    * Does nothing if no listener is registered
    * Exceptions are not propagated to the sender (fail-silent)
    * **Thread-unsafe**: designed to avoid unintended serialization

---

### `class SessionState`

Read-only interface for monitoring session status.

* **Properties**

  * `ok: bool`
    Whether the session is still active
  * `error: Exception | None`
    The first error that caused the session to end, or `None`

---

### Exceptions

* `class DeniedError(Exception)`
  Raised when a policy or `Port` rejects a connection.

* `class OccupiedError(Exception)`
  Raised when a `Port` is already occupied by another session.

---

### Protocols (Types)

* `class SendFunction(Protocol)`

  ```python
  def __call__(tag: str, *args, **kwargs) -> None
  ```

  Callable object used by the sender to send messages.

* `class ListenFunction(Protocol)`

  ```python
  def __call__(tag: str, *args, **kwargs) -> None
  ```

  Callable object used by the receiver to process messages.

---

## Observer

This library includes an `observer` implementation as a listener.

### Example usage with fport

```python
from fport import create_session_policy
from fport.observer import ProcessObserver

def create_weather_sensor(port):
    """Weather sensor
    Specification:
        temp < 0        -> "Freezing" + send("freezing")
        0 <= temp <= 30 -> "Normal"   + send("normal")
        temp > 30       -> "Hot"      + send("hot")
    """
    def check_weather(temp: int) -> str:
        # If there is a bug here, it will be detected by the test
        if temp <= 0:   # ← Common place to inject a bug
            port.send("freezing", temp)
            return "Freezing"
        elif temp <= 30:
            port.send("normal", temp)
            return "Normal"
        else:
            port.send("hot", temp)
            return "Hot"
    return check_weather

policy = create_session_policy()
port = policy.create_port()

# Define expected conditions according to the specification
conditions = {
    "freezing": lambda t: t < 0,
    "normal":   lambda t: 0 <= t <= 30,
    "hot":      lambda t: t > 30,
}
observer = ProcessObserver(conditions)
check_weather = create_weather_sensor(port)

with policy.session(observer.listen, port) as state:
    # Test coverage for all three branches
    for i in (-5, 0, 31):
        check_weather(i)
        if not state.ok:
            raise AssertionError(f"observation failed on '{i}'")

    # Verify that the Observer did not detect any specification violations
    if observer.violation:
        details = []
        for tag, obs in observer.get_violated().items():
            details.append(
                f"[{tag}] reason={obs.fail_reason}, "
                f"count={obs.count}, first_violation_at={obs.first_violation_at}"
            )
        raise AssertionError("Observer detected violations:\n" + "\n".join(details))

print("All checks passed!")
```

---

## Observer API Reference

### Class `ProcessObserver`

Monitors process state, handling condition violations and exceptions.

#### Constructor

```python
ProcessObserver(conditions: dict[str, Callable[..., bool]])
```

Initializes with the given set of conditions to monitor.

#### Methods

* `reset_observations() -> None`
  Reset all observation results.

* `listen(tag: str, *args, **kwargs) -> None`
  Evaluate the condition for the given tag.
  Calls handlers on violation or exception.

* `get_all() -> dict[str, Observation]`
  Returns all observation results.

* `get_violated() -> dict[str, Observation]`
  Returns observations where violations occurred.

* `get_compliant() -> dict[str, Observation]`
  Returns observations with no violations.

* `get_unevaluated() -> dict[str, Observation]`
  Returns unevaluated observations.

* `set_violation_handler(tag: str, fn: Callable[[Observation], None]) -> None`
  Sets a violation handler for the specified tag.

* `set_exception_handler(fn: Callable[[str, ExceptionKind, Observation | None, Exception], None]) -> None`
  Sets an exception handler.

* `get_stat(tag: str) -> ConditionStat`
  Returns statistical information for the specified tag.

#### Properties

* `violation: bool`
  Whether any violation exists.

* `global_violation: bool`
  Whether any global violation exists.

* `local_violation: bool`
  Whether any local violation exists.

* `global_fail_reason: str`
  Returns the reason for the global violation.

* `global_exception: Exception | None`
  Returns the global exception, if any.

---

### Class `Observation`

Holds detailed observation results per condition.

#### Fields

* `count: int` – Number of evaluations
* `violation: bool` – Whether a violation occurred
* `first_violation_at: int` – Trial number of the first violation
* `exc: Exception | None` – Exception that occurred
* `fail_condition: Callable[..., bool] | None` – Condition function that failed
* `fail_reason: str` – Reason for the violation

---

### Class `ConditionStat`

Simplified statistical representation of condition results.

#### Constructor

```python
ConditionStat(count: int, violation: bool, first_violation_at: int)
```

#### Properties

* `count: int` – Number of evaluations
* `violation: bool` – Whether a violation occurred
* `first_violation_at: int` – Trial number of the first violation

---

### Enum `ExceptionKind`

Indicates where an exception occurred.

#### Constants

* `ON_CONDITION` – Exception during condition evaluation
* `ON_VIOLATION` – Exception during violation handler execution
* `ON_INTERNAL` – Exception during internal processing

---

## Testing

This module uses `pytest` for testing.
Tests are located in the `tests/` directory.
The `legacy/` directory contains disabled tests and should be skipped.

