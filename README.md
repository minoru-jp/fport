# standman

> **As of version 0.2.0, the examples in this document have not been tested for actual execution.**
> The API and behavior may change without notice. Use at your own risk.

## Overview

A loosely-coupled, one-way function linkage module.
Primarily intended for simple white-box testing.
Also designed for creating small add-ons.

* **`standman`** defines factory functions and other interfaces for external use.
* **`standman.observer`** provides an example implementation of a Listener for white-box testing.

## Features

* Provides a way to easily insert *leak points* in the implementation (sender side) with minimal steps.
* Provides filtering mechanisms for the content of leaks performed by the implementation.
* The implementation side is **fail-silent**, the receiving side is **fail-fast**. Failures on the receiving side or in the framework are not propagated to the implementation, so the implementation can insert leak points without worrying about side effects.
* The receiving side connects to the sender's `Port` interface by specifying it, and the sender can define the scope of information passed to the receiving function by how it defines the `Port` interface. → See "Examples / Minimum Configuration" below.

## Warning

* **Do not** use this framework in programs that handle personal information, authentication credentials, or any other data whose leakage would cause problems. (From the implementation side's perspective, it is equivalent to leaking information to an unknown location.)

## Examples

### Minimum Configuration – Set a Port per function

```python
from standman import create_session_policy

policy = create_session_policy()
create_port = policy.create_port

def sender():
    port = sender._port
    port.send("example", "sender")

sender._port = create_port()
```

### Minimum Configuration – Set a Port at the class level

```python
from standman import create_session_policy

policy = create_session_policy()
create_port = policy.create_port

class Foo:
    _port = create_port()

    def method(self):
        Foo._port.send("example", "Foo.method")
    
class Bar(Foo):
    def method(self):
        super().method()
        Foo._port.send("example", "Bar.method")
```

### Minimum Configuration – Set a Port at the module level

```python
from standman import create_session_policy

policy = create_session_policy()
port = policy.create_port()

def func1():
    port.send("example", "func1")

def func2():
    port.send("example", "func2")
```

### Example using `observer`

```python
from standman import create_session_policy
from standman.observer import create_process_observer

# management.py
def message_validator(tag, *args, **kwargs):
    if not all(isinstance(a, int) for a in (*args, *kwargs.values())):
        raise TypeError("Sending data is int only.")

policy = create_session_policy(message_validator=message_validator)

# sender.py (implementation module)

create_port = policy.create_port

def bake_cookies(num_children):
    port = bake_cookies._port
    ... # process: Mom baking some cookies
    port.send("Share nicely", num_children, len(cookies))
    ... # process: Dad doing something
    return cookies

bake_cookies._port = create_port()

# receiver.py (test module in pytest, etc.)
def test_bake_cookies_share_nicely():
    share_nicely = lambda ch, co: co % ch == 0
    observer = create_process_observer({"Share nicely": share_nicely})

    with policy.session(observer.listen, bake_cookies._port) as state:

        bake_cookies(3)
        
        if state.active:
            back_then = not observer.get_condition_stat("Share nicely").violation
            if not share_nicely(num_children, len(cookies)):
                if back_then:
                    assert False, "Mom is suspicious."
                else:
                    assert False, "Dad is suspicious."
        else:
            if state.error:
                assert False, f"Observing failed with {state.error}"
```

### Rejecting Connections and Disabling Ports

How to reject or disable connections to Ports at the policy level or in specific parts of the implementation.

#### Block connections when creating the SessionPolicy

```python
policy = create_session_policy(block_port=True)
```

#### Specify a dispatcher for `create_port` that returns a no-op Port in the implementation

```python
create_port = policy.create_noop_port
```
