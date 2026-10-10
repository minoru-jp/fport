"""送信口 `Port` と、その接続 `Connection`。

`Port.send()` は送信側(実装側)のコードから呼ばれる。送信側から見て、
`send()` は常に `None` を返し、リスナーやエラーハンドラが投げた `Exception` を
送信側へ伝えない。また fport 自身は `send()` の中でロックを取らない。
送信口の使用が実装側の振る舞い(例外、直列化)を変えないようにするためである。

リスナーの付け外し(`connect()` / `disconnect()`)だけはロックで守る。
これは受信側の操作であり、送信側の実行には関わらない。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from types import TracebackType
from typing import Self, TypeAlias

Listener: TypeAlias = Callable[..., object]
"""`send()` に渡された `tag` と引数を、そのまま受け取る呼び出し可能オブジェクト。"""

ErrorHandler: TypeAlias = Callable[[Exception], object]
"""リスナーが投げた `Exception` を受け取る呼び出し可能オブジェクト。"""


class OccupiedError(RuntimeError):
    """すでにリスナーが接続されている `Port` に、さらに接続しようとした。"""


class Port:
    """実装側に置く、一方向の送信口。

    接続できるリスナーは一つだけ。複数に配りたい場合は、受けたリスナーが
    他へつなぐ。
    """

    __slots__: tuple[str, ...] = ("_current", "_lock")

    def __init__(self) -> None:
        self._current: Connection | None = None
        self._lock: threading.Lock = threading.Lock()

    @property
    def connected(self) -> bool:
        """リスナーが接続されているか。"""
        return self._current is not None

    def send(self, tag: str, /, *args: object, **kwargs: object) -> None:
        """接続中のリスナーを、呼び出したスレッドでそのまま呼ぶ。

        接続がなければ何もしない。リスナーが `Exception` を投げた場合は、
        接続時に渡したエラーハンドラに渡し、送信側には伝えない。エラーハンドラが
        投げた `Exception` は捨てる。`Exception` ではない `BaseException`
        (`KeyboardInterrupt` など)は捕まえない。
        """
        # 接続を一度だけ読む。リスナーとエラーハンドラは同じ接続から取り出すので、
        # 並行した付け外しの途中の、食い違った組み合わせを見ることはない。
        connection = self._current
        if connection is None:
            return
        try:
            _ = connection._listener(tag, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - どの Exception も送信側へ伝えないことが送信口の約束
            handler = connection._on_error
            if handler is None:
                return
            try:
                _ = handler(exc)
            except Exception:  # noqa: BLE001, S110 - 送信側を守る最後の防衛線。ここでだけ黙って捨てる
                pass

    def connect(
        self, listener: Listener, *, on_error: ErrorHandler | None = None
    ) -> Connection:
        """リスナーを接続し、その接続を返す。

        すでに接続されていれば `OccupiedError`。返った `Connection` は
        `with` 文で使え、抜けるときに接続を外す。
        """
        # 型注釈を守らない呼び出しも、接続する前に拒否する(型検査だけでは防げない)。
        if not callable(listener):
            raise TypeError(f"listener must be callable, not {type(listener).__name__}")  # pyright: ignore[reportUnreachable] - 型注釈を守らない呼び出しへの実行時の検査
        if on_error is not None and not callable(on_error):
            raise TypeError(  # pyright: ignore[reportUnreachable] - 型注釈を守らない呼び出しへの実行時の検査
                f"on_error must be callable or None, not {type(on_error).__name__}"
            )
        connection = Connection(self, listener, on_error)
        with self._lock:
            if self._current is not None:
                raise OccupiedError("the port already has a listener")
            self._current = connection
        return connection

    def __repr__(self) -> str:
        state = "connected" if self.connected else "idle"
        return f"<fport.Port {state}>"


class Connection:
    """`Port.connect()` が返す、一つの接続。

    `disconnect()` はこの接続だけを外し、何度呼んでもよい。
    """

    __slots__: tuple[str, ...] = ("_listener", "_on_error", "_port")

    def __init__(
        self, port: Port, listener: Listener, on_error: ErrorHandler | None
    ) -> None:
        self._port: Port = port
        self._listener: Listener = listener
        self._on_error: ErrorHandler | None = on_error

    @property
    def port(self) -> Port:
        """接続先の `Port`。"""
        return self._port

    @property
    def active(self) -> bool:
        """この接続が、まだ `Port` に接続されているか。"""
        return self._port._current is self

    def disconnect(self) -> None:
        """この接続を外す。すでに外れていれば何もしない。"""
        port = self._port
        with port._lock:
            if port._current is self:
                port._current = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        state = "active" if self.active else "closed"
        return f"<fport.Connection {state}>"
