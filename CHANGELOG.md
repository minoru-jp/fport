<!-- Published from devdocs/canonical_documents/CHANGELOG.md sha256:bc2d3f030ba660dbee5f0851a8b6b811642ed87a98cf48f2cabb10d3e8b36b64. Translated from the Japanese canonical document; edit the canonical source instead of this file. -->
# fport Changelog

Records the changes in each version of `fport`. The versions before `2.0.0` (the `1.x` series) are the old implementation from before the rebuild, and their history is not included in this document.

## V2_0_0

**This version was rebuilt from the design, and it has no backward compatibility at all with the `1.x` series.** None of the `1.x` API remains, and no means of migration is provided.

`1.x` grew too large, carrying authentication to protect connections to the sending point (creating and verifying a `Port` through a policy), settings for refusing connections, passing session state around, and even an Observer that watched conditions. This version keeps only the idea that was the core of `1.x`: "a sending point placed on the implementation side does not change how the implementation side behaves". Authentication within the same process is no protection, so it is not covered, and how to carry the received information and how to handle failures of the listener are left to the receiving side (and to gpframe where needed).

This version has not been published on PyPI yet.

version: 2.0.0

Changed:

- Changed the supported Python version range from `>=3.10` to `>=3.11`.
- Changed `Port` to be created directly with `fport.Port()`, without going through a policy.
- Changed connecting a listener from a session of `SessionPolicy.session()` to the `Connection` returned by `Port.connect()`. A `Connection` can be used in a `with` statement and disconnected with `disconnect()`.
- Changed the listener to keep being called on every `send()` even after it has failed. `1.x` did not call the listener after the first failure until the session ended. Whether to stop after a failure is decided by the receiving side.

Added:

- Added the error handler that passes failures of the listener to the receiving side (`on_error` of `Port.connect()`).
- Added `Port.connected` and `Connection.active` for looking at the state of a connection.
- Added `fport.gpframe.tap`, a routine for a gpframe frame. It keeps passing what arrives at a `Port` into a `Channel`, disconnects and returns on a stop request, and raises failures of the listener as a failure of the frame. However it ends, it closes the `Channel`. fport does not depend on gpframe.
- Placed the promises of behavior in `contract/` as `shikumi-contrace` contracts, and tied every clause to tests.
- Added the PEP 561 `py.typed`.
- Added examples in `examples/`. There are three: `lru_cache.py` for observing internal decisions in tests, `progress.py` for a hook point for measurement, and `pipeline_monitor.py` for combining with gpframe.

Removed:

- Removed `create_session_policy()` and `SessionPolicy` (`create_port()`, `create_noop_port()`, `session()`).
- Removed the authentication between `SessionPolicy` and `Port` (refusing connections from policies other than the one that created the `Port`).
- Removed the settings for refusing connections (`block_port`, the no-op `Port`) and `DeniedError`.
- Removed `message_validator`, the validation function called before sending.
- Removed `SessionState` (`ok`, `error`). Failures of the listener are received with `on_error`.
- Removed the `SendFunction` and `ListenFunction` Protocols.
- Removed `fport.observer` (`ProcessObserver`, `Observation`, `ConditionStat`, `ExceptionKind`).

Fixed:

- Fixed the problem where, when an exception occurred inside a `with` statement, the `Port` stayed occupied and the next connection raised `OccupiedError`. A `Connection` disconnects even when the block is left by an exception.
- Fixed the problem where `send()` swallowed `BaseException`s such as `KeyboardInterrupt` raised by the listener, so that interrupts stopped working. A `BaseException` that is not an `Exception` reaches the sending side as it is.
