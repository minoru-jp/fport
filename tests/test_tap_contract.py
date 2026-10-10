"""`fport.gpframe.tap` の契約に対するテスト。

gpframe の代わりに `FakeContext` と `RecordingSink` を使う。
"""

from __future__ import annotations

import pytest
from shikumi_contrace import Phase, binds, upholds, violates

import fport
from contract.ports.surface import Tap
from contract.tap_contract import TapContract
from fport.gpframe import tap
from tests.conftest import FakeContext, RecordingSink, Runner, wait_until


def start(ctx: FakeContext, port: fport.Port, out: RecordingSink) -> Runner:
    """`tap` をフレームのように別のスレッドで始め、接続されるまで待つ。"""
    runner = Runner(lambda: tap(ctx, port, out))
    wait_until(lambda: port.connected)
    return runner


@binds[Tap](tap)
class TestTap:
    @upholds(TapContract.__call__.ForwardsEachSend)
    @upholds(TapContract.__call__.EndsOnStopRequest)
    @upholds(TapContract.__call__.AlwaysClosesTheSink)
    @upholds(TapContract.__call__.AlwaysDisconnects)
    def test_forwards_messages_until_stopped(self) -> None:
        with Phase.PREPARE:
            ctx, port, out = FakeContext(), fport.Port(), RecordingSink()
            runner = start(ctx, port, out)

        with Phase.MAIN:
            port.send("a", 1, key="v")
            port.send("b")
            ctx.stop()
            runner.join()

        with Phase.VERIFY:
            assert runner.error is None
            assert out.items == [("a", (1,), {"key": "v"}), ("b", (), {})]
            assert out.closed
            assert not port.connected

    @upholds(TapContract.__call__.ForwardsEachSend)
    def test_convert_decides_what_is_put(self) -> None:
        with Phase.PREPARE:
            ctx, port, out = FakeContext(), fport.Port(), RecordingSink()

            def convert(tag: str, /, *args: object, **kwargs: object) -> str:
                return f"{tag}:{len(args)}"

            runner = Runner(lambda: tap(ctx, port, out, convert=convert))
            wait_until(lambda: port.connected)

        with Phase.MAIN:
            port.send("a", 1, 2)
            ctx.stop()
            runner.join()

        with Phase.VERIFY:
            assert runner.error is None
            assert out.items == ["a:2"]

    @upholds(TapContract.__call__.EndsOnStopRequest)
    @upholds(TapContract.__call__.AlwaysClosesTheSink)
    @upholds(TapContract.__call__.AlwaysDisconnects)
    def test_returns_at_once_when_already_stopping(self) -> None:
        with Phase.PREPARE:
            ctx, port, out = FakeContext(), fport.Port(), RecordingSink()
            ctx.stop()

        with Phase.MAIN:
            runner = Runner(lambda: tap(ctx, port, out))
            runner.join()

        with Phase.VERIFY:
            assert runner.error is None
            assert out.closed
            assert not port.connected

    @upholds(TapContract.__call__.ListenerFailureFailsTheFrame)
    @upholds(TapContract.__call__.AlwaysClosesTheSink)
    @upholds(TapContract.__call__.AlwaysDisconnects)
    def test_put_failure_fails_the_frame_but_not_the_sender(self) -> None:
        with Phase.PREPARE:
            ctx = FakeContext()
            port = fport.Port()
            out = RecordingSink(fail_on=("bad", (), {}))
            runner = start(ctx, port, out)

        with Phase.MAIN:
            port.send("ok")
            sent = port.send("bad")  # 送信側には何も起きない
            runner.join()

        with Phase.VERIFY:
            assert sent is None
            assert isinstance(runner.error, ValueError)
            assert out.items == [("ok", (), {})]
            assert out.closed
            assert not port.connected

    @upholds(TapContract.__call__.ListenerFailureFailsTheFrame)
    def test_convert_failure_fails_the_frame(self) -> None:
        with Phase.PREPARE:
            ctx, port, out = FakeContext(), fport.Port(), RecordingSink()

            def convert(tag: str, /) -> str:
                raise LookupError(tag)

            runner = Runner(lambda: tap(ctx, port, out, convert=convert))
            wait_until(lambda: port.connected)

        with Phase.MAIN:
            port.send("tag")
            runner.join()

        with Phase.VERIFY:
            assert isinstance(runner.error, LookupError)
            assert out.closed

    @upholds(TapContract.__call__.ListenerFailureFailsTheFrame)
    def test_several_failures_are_grouped(self) -> None:
        with Phase.PREPARE:
            ctx, out = FakeContext(), RecordingSink()

            # 接続した直後に、リスナーの失敗を二つ報告する Port。
            class FailingTwice(fport.Port):
                def connect(
                    self,
                    listener: fport.Listener,
                    *,
                    on_error: fport.ErrorHandler | None = None,
                ) -> fport.Connection:
                    connection = super().connect(listener, on_error=on_error)
                    assert on_error is not None
                    _ = on_error(ValueError("first"))
                    _ = on_error(KeyError("second"))
                    return connection

            port = FailingTwice()

        with Phase.MAIN:
            runner = Runner(lambda: tap(ctx, port, out))
            runner.join()

        with Phase.VERIFY:
            assert isinstance(runner.error, ExceptionGroup)
            assert [type(e) for e in runner.error.exceptions] == [ValueError, KeyError]
            assert out.closed
            assert not port.connected

    @violates(TapContract.__call__.PortIsFree)
    @upholds(TapContract.__call__.AlwaysClosesTheSink)
    def test_occupied_port_fails_the_frame_and_closes_the_sink(self) -> None:
        with Phase.PREPARE:
            ctx, port, out = FakeContext(), fport.Port(), RecordingSink()
            existing = port.connect(lambda *a, **k: None)

        with Phase.MAIN, pytest.raises(fport.OccupiedError):
            tap(ctx, port, out)

        with Phase.VERIFY:
            assert out.closed
            assert existing.active
