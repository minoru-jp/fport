"""gpframe と組み合わせて使う部品。

fport は gpframe に依存しない。ここにある部品は、gpframe の `Context` と
`Channel` が持つ操作(`ctx.on_stop()`、`out.put()`、`out.close()`)だけを前提にする。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol, TypeAlias, TypeVar, overload

T_contra = TypeVar("T_contra", contravariant=True)
T = TypeVar("T")

Message: TypeAlias = tuple[str, tuple[object, ...], dict[str, object]]
"""`tap()` が既定で流す値。`(tag, args, kwargs)`。"""


class StopHandle(Protocol):
    """停止コールバックの登録。gpframe の `StopHandle` が満たす。"""

    def cancel(self) -> object: ...


class StopSource(Protocol):
    """停止の要求を知らせるもの。gpframe の `Context` が満たす。

    登録した時点ですでに停止が要求されていれば、コールバックはすぐに呼ばれる
    ものとする(gpframe の STOP_012)。
    """

    def on_stop(self, callback: Callable[[], object], /) -> StopHandle: ...


class Connectable(Protocol):
    """リスナーを接続できるもの。`fport.Port` が満たす。"""

    def connect(
        self,
        listener: Callable[..., object],
        *,
        on_error: Callable[[Exception], object] | None = None,
    ) -> AbstractContextManager[object, None]: ...


class Sink(Protocol[T_contra]):
    """値の流し先。gpframe の `Channel` が満たす。"""

    def put(self, item: T_contra, /) -> object: ...
    def close(self) -> object: ...


def message(tag: str, /, *args: object, **kwargs: object) -> Message:
    """`send()` の引数を `(tag, args, kwargs)` にまとめる。`tap()` の既定の変換。"""
    return (tag, args, kwargs)


@overload
def tap(ctx: StopSource, port: Connectable, out: Sink[Message]) -> None: ...
@overload
def tap(
    ctx: StopSource, port: Connectable, out: Sink[T], *, convert: Callable[..., T]
) -> None: ...
def tap(
    ctx: StopSource,
    port: Connectable,
    out: Sink[T],
    *,
    convert: Callable[..., T] | Callable[..., Message] = message,
) -> None:
    """`port` に届いたものを `out` へ流し続ける、gpframe のフレーム用ルーティン。

    `send()` のたびに `out.put(convert(tag, *args, **kwargs))` を呼ぶ。停止が要求
    されると接続を外して普通に戻る。変換や `put()` が `Exception` を投げた場合は、
    接続を外してその例外をこのフレームの失敗として送出する(複数あれば
    `ExceptionGroup`)。どの終わり方でも、最後に `out.close()` を呼ぶ。

        with gpframe.session(timeout=5) as s:
            s.spawn(tap, port, events)
    """
    wake = threading.Event()
    errors: list[Exception] = []

    def forward(tag: str, /, *args: object, **kwargs: object) -> None:
        _ = out.put(convert(tag, *args, **kwargs))  # pyright: ignore[reportArgumentType] - convert と out の型の組は overload が保証する

    def on_error(exc: Exception) -> None:
        errors.append(exc)
        wake.set()

    handle = ctx.on_stop(wake.set)
    try:
        with port.connect(forward, on_error=on_error):
            _ = wake.wait()
    finally:
        _ = handle.cancel()
        _ = out.close()
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise ExceptionGroup("the listener of a tapped port failed", errors)
