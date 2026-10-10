"""gpframe そのものと組み合わせたときの確認。

fport は gpframe に依存しないので、gpframe が入っていない環境では飛ばす。
contrace はテストモジュールを読み込んで調べるため、モジュールの読み込みでは
gpframe を import せず、各テストの中で `pytest.importorskip()` する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import fport
from fport.gpframe import Message, tap

if TYPE_CHECKING:
    import gpframe


def collect(
    ctx: gpframe.Context, events: gpframe.Channel[Message], n: int
) -> list[str]:
    tags: list[str] = []
    while len(tags) < n:
        item = events.get(ctx, timeout=5)
        if item is None:
            break
        tags.append(item[0])
    return tags


def test_tap_feeds_a_channel_and_ends_with_the_session() -> None:
    gp = pytest.importorskip("gpframe")
    port = fport.Port()
    events: gpframe.Channel[Message] = gp.Channel(tuple)

    with gp.session(timeout=5) as s:
        tapping: gpframe.Frame[None] = s.spawn(tap, port, events)
        collector: gpframe.Frame[list[str]] = s.spawn(collect, events, 3)
        while not port.connected:
            _ = tapping.wait(0.01)
        for n in range(3):
            port.send(f"event-{n}", n)
        assert collector.wait(5)
        s.stop()

    assert collector.result() == ["event-0", "event-1", "event-2"]
    assert tapping.succeeded
    assert events.closed
    assert not port.connected


def test_listener_failure_becomes_a_broken_frame() -> None:
    gp = pytest.importorskip("gpframe")
    port = fport.Port()
    events: gpframe.Channel[Message] = gp.Channel(tuple, maxsize=1)

    with gp.session(timeout=5) as s:
        tapping: gpframe.Frame[None] = s.spawn(tap, port, events)
        while not port.connected:
            _ = tapping.wait(0.01)
        port.send("fills the channel")
        port.send("overflows")  # ChannelFullError は送信側に出ない
        broken: list[gpframe.Frame[object]] = list(s.wait_broken())
        for frame in broken:
            frame.ignore()

    assert [frame.name for frame in broken] == [tapping.name]
    assert isinstance(tapping.error, gp.ChannelFullError)
    assert events.closed
    assert not port.connected
