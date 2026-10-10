"""`Port` と `Connection` の契約に対するテスト。"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import cast

import pytest
from shikumi_contrace import Phase, binds, upholds, violates

import fport
from contract.port_contract import ConnectionContract, PortContract
from contract.ports.surface import Connection, Port
from tests.conftest import TIMEOUT

# 実装が公開 API の形を満たすことの静的な確認。
# `@binds[...]` の引数の型 `T | Callable[..., T]` では、basedpyright 1.40.2 が
# クラスオブジェクトと Protocol を比べた途中結果を誤って再利用し、相互に参照し合う
# Port と Connection の適合を失敗と判定する(gpframe の STATUS_006 と同じ問題)。
# binds より先にここでインスタンスの形として確かめておくと、その誤判定が起きない。
_PORT_SHAPE: Callable[..., Port] = fport.Port
_CONNECTION_SHAPE: Callable[..., Connection] = fport.Connection


class Recorder:
    """受け取った呼び出しを記録するリスナー。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def __call__(self, tag: str, /, *args: object, **kwargs: object) -> str:
        self.calls.append((tag, args, kwargs))
        return "ignored"


def failing(tag: str, /, *args: object, **kwargs: object) -> None:
    raise ValueError(tag)


@binds[Port](fport.Port)
class TestSend:
    @upholds(PortContract.send.WithoutListenerDoesNothing)
    @upholds(PortContract.send.ReturnsNone)
    def test_send_without_listener_does_nothing(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()

        with Phase.MAIN:
            result = port.send("tag", 1, key="value")

        with Phase.VERIFY:
            assert result is None
            assert not port.connected

    @upholds(PortContract.send.CallsListenerInCallerThread)
    @upholds(PortContract.send.ReturnsNone)
    def test_send_calls_listener_in_caller_thread_before_returning(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            threads: list[int] = []
            finished: list[str] = []

            def listener(tag: str, /, *args: object, **kwargs: object) -> str:
                threads.append(threading.get_ident())
                finished.append(tag)
                return "not returned to the sender"

            _ = port.connect(listener)

        with Phase.MAIN:
            result = port.send("tag", 1, 2, key="value")
            seen_on_return = list(finished)

        with Phase.VERIFY:
            assert result is None
            assert threads == [threading.get_ident()]
            assert seen_on_return == ["tag"]

    @upholds(PortContract.send.CallsListenerInCallerThread)
    def test_send_passes_tag_and_arguments_unchanged(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            recorder = Recorder()
            payload = object()
            _ = port.connect(recorder)

        with Phase.MAIN:
            port.send("first")
            port.send("second", payload, 2, key=payload)

        with Phase.VERIFY:
            assert recorder.calls == [
                ("first", (), {}),
                ("second", (payload, 2), {"key": payload}),
            ]

    @upholds(PortContract.SendNeverRaisesException)
    @upholds(PortContract.send.ListenerFailureGoesToErrorHandler)
    def test_listener_failure_goes_to_error_handler_every_time(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            errors: list[Exception] = []
            _ = port.connect(failing, on_error=errors.append)

        with Phase.MAIN:
            port.send("first")
            port.send("second")

        with Phase.VERIFY:
            assert [str(e) for e in errors] == ["first", "second"]
            assert all(isinstance(e, ValueError) for e in errors)

    @upholds(PortContract.SendNeverRaisesException)
    @upholds(PortContract.send.ListenerFailureGoesToErrorHandler)
    def test_listener_keeps_being_called_after_a_failure(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            seen: list[str] = []
            errors: list[Exception] = []

            def flaky(tag: str, /) -> None:
                seen.append(tag)
                if tag == "bad":
                    raise ValueError(tag)

            _ = port.connect(flaky, on_error=errors.append)

        with Phase.MAIN:
            for tag in ("ok", "bad", "ok again"):
                port.send(tag)

        with Phase.VERIFY:
            assert seen == ["ok", "bad", "ok again"]
            assert len(errors) == 1

    @upholds(PortContract.SendNeverRaisesException)
    @upholds(PortContract.send.LeftoverFailureIsDiscarded)
    def test_failure_without_error_handler_is_discarded(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            _ = port.connect(failing)

        with Phase.MAIN:
            result = port.send("tag")

        with Phase.VERIFY:
            assert result is None
            assert port.connected

    @upholds(PortContract.SendNeverRaisesException)
    @upholds(PortContract.send.LeftoverFailureIsDiscarded)
    def test_error_handler_failure_is_discarded(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()

            def broken_handler(exc: Exception) -> None:
                raise RuntimeError("handler failed") from exc

            _ = port.connect(failing, on_error=broken_handler)

        with Phase.MAIN:
            result = port.send("tag")

        with Phase.VERIFY:
            assert result is None

    @upholds(PortContract.send.BaseExceptionIsNotCaught)
    @pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
    def test_base_exception_from_listener_reaches_sender(
        self, exc_type: type[BaseException]
    ) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            errors: list[Exception] = []

            def interrupted(tag: str, /) -> None:
                raise exc_type

            _ = port.connect(interrupted, on_error=errors.append)

        with Phase.MAIN, pytest.raises(exc_type):
            port.send("tag")

        with Phase.VERIFY:
            assert errors == []

    @upholds(PortContract.send.BaseExceptionIsNotCaught)
    def test_base_exception_from_error_handler_reaches_sender(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()

            def interrupted(exc: Exception) -> None:
                raise KeyboardInterrupt

            _ = port.connect(failing, on_error=interrupted)

        with Phase.MAIN, pytest.raises(KeyboardInterrupt):
            port.send("tag")

    @upholds(PortContract.AddsNoSerialization)
    def test_sends_from_several_threads_run_the_listener_concurrently(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            senders = 4
            # すべての送信スレッドが同時にリスナーの中にいなければ通れない門。
            # send() が直列化していれば、門は時間切れで壊れ、その失敗が errors に入る。
            barrier = threading.Barrier(senders, timeout=TIMEOUT)
            met: list[int] = []
            errors: list[Exception] = []

            def listener(tag: str, /) -> None:
                _ = barrier.wait()
                met.append(threading.get_ident())

            _ = port.connect(listener, on_error=errors.append)
            threads = [
                threading.Thread(target=port.send, args=("tag",))
                for _ in range(senders)
            ]

        with Phase.MAIN:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(TIMEOUT * 2)

        with Phase.VERIFY:
            assert errors == []
            assert len(met) == senders


@binds[Port](fport.Port)
class TestConnect:
    @upholds(PortContract.connect.ReturnsActiveConnection)
    def test_connect_returns_active_connection(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()

        with Phase.MAIN:
            connection = port.connect(Recorder())

        with Phase.VERIFY:
            assert connection.active
            assert connection.port is port
            assert port.connected

    @violates(PortContract.connect.ListenerIsCallable)
    def test_connect_rejects_non_callable_listener(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()

        with Phase.MAIN, pytest.raises(TypeError):
            _ = port.connect(cast("fport.Listener", "not callable"))

        with Phase.VERIFY:
            assert not port.connected

    @violates(PortContract.connect.ListenerIsCallable)
    def test_connect_rejects_non_callable_error_handler(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()

        with Phase.MAIN, pytest.raises(TypeError):
            _ = port.connect(
                Recorder(), on_error=cast("fport.ErrorHandler", "not callable")
            )

        with Phase.VERIFY:
            assert not port.connected

    @violates(PortContract.connect.PortIsFree)
    def test_second_connect_is_rejected_and_keeps_the_first(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            first = Recorder()
            second = Recorder()
            connection = port.connect(first)

        with Phase.MAIN, pytest.raises(fport.OccupiedError):
            _ = port.connect(second)

        with Phase.VERIFY:
            port.send("tag")
            assert connection.active
            assert len(first.calls) == 1
            assert second.calls == []


@binds[Connection](fport.Connection)
class TestConnection:
    @upholds(ConnectionContract.disconnect.StopsDelivery)
    def test_disconnect_stops_delivery_and_frees_the_port(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            first = Recorder()
            connection = port.connect(first)

        with Phase.MAIN:
            connection.disconnect()
            port.send("after")
            second = Recorder()
            _ = port.connect(second)
            port.send("again")

        with Phase.VERIFY:
            assert not connection.active
            assert first.calls == []
            assert second.calls == [("again", (), {})]

    @upholds(ConnectionContract.disconnect.AffectsOnlyThisConnection)
    def test_stale_disconnect_does_not_touch_a_newer_connection(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            old = port.connect(Recorder())
            old.disconnect()
            newer = port.connect(Recorder())

        with Phase.MAIN:
            old.disconnect()
            old.disconnect()

        with Phase.VERIFY:
            assert newer.active
            assert port.connected

    @upholds(ConnectionContract.__exit__.DisconnectsEvenOnError)
    def test_with_block_disconnects(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()
            recorder = Recorder()

        with Phase.MAIN, port.connect(recorder) as connection:
            port.send("inside")

        with Phase.VERIFY:
            port.send("outside")
            assert not connection.active
            assert recorder.calls == [("inside", (), {})]

    @upholds(ConnectionContract.__exit__.DisconnectsEvenOnError)
    def test_with_block_disconnects_on_error_without_suppressing_it(self) -> None:
        with Phase.PREPARE:
            port = fport.Port()

        with Phase.MAIN:
            with pytest.raises(ValueError, match="inside"), port.connect(Recorder()):
                raise ValueError("inside")
            # 1.x では、ここで OccupiedError になった。
            connection = port.connect(Recorder())

        with Phase.VERIFY:
            assert connection.active
