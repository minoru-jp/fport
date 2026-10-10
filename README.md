<!-- Published from devdocs/canonical_documents/README.md sha256:0d8124eafb3127de81401684e3090b1e7d9a56ffa96e8d2c89cf822036da3d72. Translated from the Japanese canonical document; edit the canonical source instead of this file. -->
# fport

`fport` is a **one-way sending point** that you place inside an implementation.

The implementation side places a `Port` and sends information with `port.send(tag, *args, **kwargs)`, and the receiving side receives it with `port.connect(listener)`. If nothing is connected, `send()` does nothing. The implementation side does not know where it is connected to, and being connected does not change how the implementation side behaves.

You can use it to observe what happens inside an implementation in tests, to make a hook point for logging or measurement, or to provide an entry point for simple extensions.

## Usage

```python
import fport

port = fport.Port()


def add(a: int, b: int) -> int:
    port.send("add", a, b)  # does nothing if nothing is connected
    return a + b


print(add(1, 2))

with port.connect(lambda tag, *args: print("received:", tag, args)):
    print(add(2, 3))
```

When you run it, it prints the following.

```text
3
received: add (2, 3)
5
```

The `Connection` returned by `connect()` can be used in a `with` statement, and it disconnects when leaving the block. The same is true when an exception occurs inside the `with` block. You can also disconnect with `connection.disconnect()` without using `with`.

## What is promised to the sending side

The sending point promises only to protect the sending side (the implementation side).

- **`send()` does not pass exceptions to the sending side.** An `Exception` raised by the listener does not reach the sending side, and the return value is always `None`.
- **`send()` takes no lock.** Placing a sending point does not bring serialization into the implementation side. If you `send()` from several threads, the listener may also run at the same time. This is because serialization brought in from outside would hide concurrency problems in the implementation side.
- **The listener is called right there, in the thread that called `send()`.** Nothing is queued or handed to another thread. If that is needed, the listener side does it.
- **Requests to interrupt or exit go through.** A `BaseException` that is not an `Exception` (such as `KeyboardInterrupt` or `SystemExit`) is not caught and reaches the sending side as it is.

Anything else, such as how to carry the received information or how to handle failures of the listener, is decided by the receiving side.

## Failures of the listener

If the listener raises an `Exception` and you passed `on_error` to `connect()`, the exception is passed to it.

```python
import fport

port = fport.Port()
errors: list[Exception] = []


def must_be_positive(tag: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{tag}: {value} is not positive")


with port.connect(must_be_positive, on_error=errors.append):
    for value in (1, -1, 2):
        port.send("value", value)  # nothing happens on the sending side

print(errors)
```

When you run it, it prints `[ValueError('value: -1 is not positive')]`.

The listener keeps being called on every `send()` even after it has failed. If you want to stop it after a failure, `disconnect()` on the receiving side. If you did not pass `on_error`, or if `on_error` itself raises an exception, that exception is discarded. This is the only place where the sending point silently discards an exception.

## One listener

Only one listener can be connected to a `Port`, and calling `connect()` on a `Port` that is already connected raises `OccupiedError`. A second connection never silently replaces the previous one.

To deliver to several listeners, the listener that receives passes it on to the others.

```python
from collections.abc import Callable

import fport


def fan_out(*listeners: Callable[..., object]) -> Callable[..., None]:
    def listener(tag: str, *args: object, **kwargs: object) -> None:
        for fn in listeners:
            fn(tag, *args, **kwargs)

    return listener


port = fport.Port()
seen: list[str] = []

with port.connect(fan_out(seen.append, lambda tag: print("got", tag))):
    port.send("ready")

print(seen)
```

When you run it, it prints the following.

```text
got ready
['ready']
```

In what order to call them, and what to do with the rest when one fails, is decided by the side that delivers.

## Combining with gpframe

Combined with [gpframe](https://github.com/minoru-jp/gpframe), you can carry the received information to another thread, or match the period of a connection to the lifetime of a frame. `fport.gpframe.tap` is a routine for a frame that keeps passing what arrives at a `Port` into a gpframe `Channel`.

```python
import gpframe

import fport
from fport.gpframe import Message, tap

port = fport.Port()
events: gpframe.Channel[Message] = gpframe.Channel(tuple)


def show(ctx: gpframe.Context, events: gpframe.Channel[Message]) -> None:
    for tag, args, _ in events.receive(ctx):
        print(tag, args)
        if tag == "done":
            return


with gpframe.session(timeout=5) as s:
    tapping = s.spawn(tap, port, events)
    shown = s.spawn(show, events)
    while not port.connected:  # a send() before the connection is made does not arrive
        tapping.wait(0.01)
    port.send("progress", 50)
    port.send("done")
    shown.wait()
    s.stop()  # tap disconnects, closes the Channel and ends

print(port.connected, events.closed)
```

When you run it, it prints the following.

```text
progress (50,)
done ()
False True
```

When a stop is requested, `tap` disconnects and returns, and however it ends, it closes the `Channel` last. If `put()` into the `Channel` fails (because it is full, or after it has been closed, for example), nothing happens on the sending side, and the frame of `tap` fails with that exception. The receiving side can choose to `escalate()` or `ignore()` it in the gpframe way.

fport does not depend on gpframe. All that `tap` uses is `ctx.on_stop()`, `out.put()` and `out.close()`.

## Examples

[`examples/`](https://github.com/minoru-jp/fport/tree/main/examples) holds one example for each situation where a sending point is useful. Each can be run with `python examples/<name>.py`.

- [`lru_cache.py`](https://github.com/minoru-jp/fport/blob/main/examples/lru_cache.py): **Observing internal decisions in tests.** The cache sends hits, misses and evictions, and the test checks "which keys were evicted, in what order". You can observe what the return values do not show, without mocks and without peeking at internal state.
- [`progress.py`](https://github.com/minoru-jp/fport/blob/main/examples/progress.py): **A hook point for measurement.** The library-side function only sends its progress, and the side that uses it decides whether to display it. Even if the display fails, the processing does not stop.
- [`pipeline_monitor.py`](https://github.com/minoru-jp/fport/blob/main/examples/pipeline_monitor.py): **Combining with gpframe.** Several workers send their results to the same `Port`, and a monitoring frame gathers them with `tap` and aggregates them. The workers know nothing about the monitoring, and carrying is done by a gpframe `Channel`. gpframe is required.

## Installation

```bash
pip install "fport>=2.0.0"
```

Python `>=3.11` is required. There are no runtime dependencies.

`2.0.0` is a version rebuilt from the design, and it is not compatible with the `1.x` series at all.

## Related documents

- [STATUS.md](STATUS.md): development stage, scope, state of quality, and future direction
- [CHANGELOG.md](CHANGELOG.md): changes in each version
- `contract/`: the promises of behavior. In fport, the `shikumi-contrace` contracts are the authoritative source of behavior
