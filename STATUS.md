<!-- Published from devdocs/canonical_documents/STATUS.md sha256:34b799495d5cc7410928d69621da6a0fe4231604dce364b12a1a650ffab35830. Translated from the Japanese canonical document; edit the canonical source instead of this file. -->
# fport Project Status

This document describes the current state of `fport` and its future direction as seen from now.
Changes that actually happened in the past belong to the CHANGELOG.

## STATUS_001

The current development stage is Alpha. The current version is `2.0.0`, and it is published on PyPI. The `1.x` series is the old implementation from before the rebuild and is not compatible with `2.0.0`.

title: Development stage

## STATUS_002

The supported Python version range is `>=3.11`, because `fport.gpframe.tap` gathers several failures of the listener with the standard `ExceptionGroup`. There are no runtime dependencies.

title: Supported Python

## STATUS_003

The following is provided.

- The sending point `Port` placed on the implementation side, and its `send()`. It does nothing without a connection, does not pass an `Exception` to the sending side, and takes no lock
- Connecting a listener with `Port.connect()`, and the connection `Connection` (`disconnect()`, the `with` statement). Only one listener can be connected, and connecting to a `Port` that is already connected raises `OccupiedError`
- The error handler that passes failures of the listener to the receiving side (`on_error` of `connect()`)
- The routine for a gpframe frame, `fport.gpframe.tap`. It passes what arrives at a `Port` into a `Channel`, ends on a stop, and turns failures of the listener into a failure of the frame

Authentication of connections and restrictions on where things are sent are not covered. All code in the same process is within the same scope of trust, and separating it is the role of process or OS boundaries. Sessions that keep the exchange with the listener as state are not covered either. To manage the period of a connection, use the `with` statement or the lifetime of a gpframe frame.

title: Scope

## STATUS_004

fport has no Specification document; the `shikumi-contrace` contracts in `contract/` are the authoritative source of behavior. The shape of the public API is placed in `contract/ports/surface.py` as Protocols. There are three contracts: `PortContract`, `ConnectionContract` and `TapContract`.

pytest confirms that every clause of the contracts is tied to at least one test. pytest always runs with `--contrace-check` and treats every warning as an error.

The tests of `TapContract` use fakes that imitate the behavior of gpframe's `Context` and `Channel`. The tests combined with gpframe itself, the gpframe example in the README, and the tests of the example `pipeline_monitor.py` run only in an environment where gpframe is installed, and are skipped otherwise.

title: Contracts and tests

## STATUS_005

Every check is gathered in `tools/check.py`. There are seven: `docs` (the canonical documents are up to date, and the English published documents do not disagree with the canonical documents), `format`, `lint`, `types`, `types-tests`, `tests` and `dist` (build an sdist and a wheel, `twine check --strict`, inspect their contents, confirm that the wheel works in a clean venv without dependencies, and confirm that the version agrees across the tag, the package, the documents and the CHANGELOG). `python tools/check.py` runs all of them, and listing names runs only some. Separately, there is `published`, which runs at the end of the release workflow. It confirms that `docs` passes, that the version agrees, and that the CHANGELOG entry for that version has a release date (`released_on`); that is, that the documents are in the state of having published that version.

The versions of the tools used for checking are fixed by the extras in `pyproject.toml` (`ruff==0.17.0`, `basedpyright==1.40.2`, `shikumi-contrace==0.1.0`, `shikumi-devdoc==0.3.5`, `gpframe==0.1.0`, `build==1.6.1`, `twine==7.0.0`). `dev` includes all of them. BasedPyright checks `src`, `contract/ports`, `scripts`, `tools` and `examples` in `recommended` mode, and the tests, contracts and canonical sources of the documents as users of the API in `standard` mode, both with 0 errors / 0 warnings.

title: Checks

## STATUS_009

GitHub Actions consists of three workflows.

- `checks.yml`: a reusable workflow that runs `python tools/check.py` on Python 3.11, 3.12 and 3.13. The content of the checks is kept only in `tools/check.py`.
- `ci.yml`: calls `checks.yml` on every push and pull request.
- `release.yml`: when a Release is published on GitHub, it first calls `checks.yml` and passes the same checks as on push. It then builds and checks the distributions with `python tools/check.py dist --tag <tag>` (also confirming that the tag matches `v<version>`), and finally confirms with `python tools/check.py published --tag <tag>` that the documents are in the published state before publishing with PyPI Trusted Publishing. No API token is used.

For Trusted Publishing, this repository, the workflow `release.yml` and the environment `pypi` must be registered as a Trusted Publisher on PyPI.

title: Checks, CI and release

## STATUS_007

gpframe is not a runtime dependency of fport. In development, however, it is used to check `fport.gpframe` together with gpframe itself, and it is fixed to `gpframe==0.1.0` by the `test` extra.

In an environment without gpframe, the tests that use gpframe (the integration tests, the gpframe example in the README, and the example `pipeline_monitor.py`) are skipped, and the remaining tests pass. The type check of the tests (`types-tests`) refers to the types of gpframe, so gpframe is required for it.

title: gpframe in development

## STATUS_008

`examples/` holds three examples, one for each use of a sending point: `lru_cache.py` for observing internal decisions in tests, `progress.py` for a hook point for measurement, and `pipeline_monitor.py` for combining with gpframe. `tests/test_examples.py` confirms that each of them works as written.

With `pipeline_monitor.py`, it was confirmed that when the monitoring side receives something it does not expect, the failures for what the workers sent before the Monitor frame disconnects are gathered. One failure is raised as that exception, and several as an `ExceptionGroup`; in either case nothing happens to the workers. This is the behavior as stated in `TapContract`.

There is no example of an entry point for extensions (such as plugin hooks). A sending point is one-way and returns no value, so such an example would make people expect hooks that change behavior.

title: Examples

## STATUS_006

There are three documents: README, Project Status and CHANGELOG. They are generated with `shikumi-devdoc` from the Japanese canonical sources in `devdocs/canonical_sources/` into `devdocs/canonical_documents/`. Generation is done with `python scripts/render_devdocs.py`.

The English published documents are made by translating the Japanese canonical documents and are placed at the root of the repository, and the package README uses the `README.md` at the root. The translation itself is not automated; `scripts/published_docs.py` checks the following mechanically (included in `tools/check.py docs`).

- Every canonical document has a published document
- The stamp at the top of each published document matches the SHA-256 of the current canonical document. When a canonical document changes, the check fails until it is re-translated and stamped again with `python scripts/published_docs.py stamp <published document>`
- The Python code examples are the same as in the canonical document, apart from comments and docstrings
- The identifier headings (such as `STATUS_001`) are the same, in the same order and number
- The targets of links exist

title: Documents
