"""テスト共通の部品。

`tap` の契約テストは gpframe を使わず、gpframe の `Context` と `Channel` の
振る舞いを真似た偽物で行う。gpframe そのものとの組み合わせは
`test_gpframe_integration.py` で確かめる。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

TIMEOUT = 5.0


class FakeStopHandle:
    def __init__(self, ctx: FakeContext, callback: Callable[[], object]) -> None:
        self._ctx = ctx
        self._callback = callback

    def cancel(self) -> None:
        with self._ctx.lock:
            if self._callback in self._ctx.callbacks:
                self._ctx.callbacks.remove(self._callback)


class FakeContext:
    """gpframe の `Context.on_stop()` の約束を真似た偽物。

    - 停止の要求で、登録済みのコールバックを別のスレッドで一度だけ呼ぶ
    - 停止の要求の後に登録したコールバックは、登録直後に呼ぶ(gpframe の STOP_012)
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.stopping = False
        self.callbacks: list[Callable[[], object]] = []

    def on_stop(self, callback: Callable[[], object], /) -> FakeStopHandle:
        with self.lock:
            call_now = self.stopping
            if not call_now:
                self.callbacks.append(callback)
        if call_now:
            threading.Thread(target=callback).start()
        return FakeStopHandle(self, callback)

    def stop(self) -> None:
        with self.lock:
            self.stopping = True
            callbacks, self.callbacks = self.callbacks, []
        for callback in callbacks:
            threading.Thread(target=callback).start()


class SinkClosedError(Exception):
    """閉じた `RecordingSink` に `put()` した。"""


@dataclass
class RecordingSink:
    """gpframe の `Channel` の代わりに、受け取った値を記録する流し先。

    閉じた後の `put()` は `Channel` と同じく例外にする。`fail_on` に一致する
    値の `put()` も例外にする。
    """

    items: list[object] = field(default_factory=list)
    closed: bool = False
    fail_on: object = None

    def put(self, item: object, /) -> None:
        if self.closed:
            raise SinkClosedError("the sink is closed")
        if self.fail_on is not None and item == self.fail_on:
            raise ValueError(f"cannot put {item!r}")
        self.items.append(item)

    def close(self) -> None:
        self.closed = True


class Runner:
    """ルーティンを gpframe のフレームのように別のスレッドで動かす。"""

    def __init__(self, routine: Callable[[], None]) -> None:
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, args=(routine,))
        self._thread.start()

    def _run(self, routine: Callable[[], None]) -> None:
        try:
            routine()
        except BaseException as exc:  # noqa: BLE001 - テストで検証するために受け取る
            self.error = exc

    def join(self) -> None:
        self._thread.join(TIMEOUT)
        assert not self._thread.is_alive(), "the routine did not return"


def wait_until(condition: Callable[[], bool]) -> None:
    """`condition` が真になるまで待つ。`TIMEOUT` 秒で失敗。"""
    deadline = threading.Event()
    for _ in range(int(TIMEOUT / 0.005)):
        if condition():
            return
        _ = deadline.wait(0.005)
    raise AssertionError("the condition did not become true")
