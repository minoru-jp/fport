"""fport の公開 API の形。

実装はこの Protocol を満たす。テストの `@binds[...]` によって、実装が
この形を満たすことが型検査で確かめられる。
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self, TypeAlias, TypeVar

T_contra = TypeVar("T_contra", contravariant=True)

Message: TypeAlias = tuple[str, tuple[object, ...], dict[str, object]]


class Connection(Protocol):
    """`Port.connect()` が返す、一つの接続。"""

    @property
    def port(self) -> Port: ...
    @property
    def active(self) -> bool: ...
    def disconnect(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class Port(Protocol):
    """実装側に置く、一方向の送信口。"""

    @property
    def connected(self) -> bool: ...
    def send(self, tag: str, /, *args: object, **kwargs: object) -> None: ...
    def connect(
        self,
        listener: Callable[..., object],
        *,
        on_error: Callable[[Exception], object] | None = None,
    ) -> Connection: ...


class StopHandle(Protocol):
    """停止コールバックの登録。"""

    def cancel(self) -> object: ...


class StopSource(Protocol):
    """停止の要求を知らせるもの(gpframe の `Context`)。"""

    def on_stop(self, callback: Callable[[], object], /) -> StopHandle: ...


class Sink(Protocol[T_contra]):
    """値の流し先(gpframe の `Channel`)。"""

    def put(self, item: T_contra, /) -> object: ...
    def close(self) -> object: ...


class Tap(Protocol):
    """`fport.gpframe.tap`。Port に届いたものを Sink へ流すフレーム用ルーティン。"""

    def __call__(self, ctx: StopSource, port: Port, out: Sink[Message], /) -> None: ...
