"""送信口 `Port` と接続 `Connection` の契約。

fport が約束するのは、送信側(実装側)を守ることだけである。送信口を置いたことで、
実装側の振る舞い(例外、戻り値、直列化)が変わってはならない。リスナーの失敗を
どう扱うかは受信側が決め、fport は決め打ちしない。
"""

from shikumi_contrace import (
    INV,
    POST,
    PRE,
    REJECTED,
    caution,
    kind,
    member,
    on_violation,
    rationale,
    regression,
    subject,
)

from contract.ports.surface import Connection, Port


class PortContract:
    subject @= Port

    class SendNeverRaisesException:
        """`send()` は、リスナーやエラーハンドラが投げた `Exception` を送信側へ伝えない。"""

        kind @= INV
        rationale @= "送信口の使用が、実装側の制御の流れを変えないようにする。"

    class AddsNoSerialization:
        """fport は `send()` の中でロックを取らない。複数のスレッドからの `send()` は、リスナーを同時に実行しうる。"""

        kind @= INV
        rationale @= (
            "送信口の使用が実装側に直列化を持ち込むと、実装側の並行性の問題が隠れる。"
        )

    class send:
        member @= Port.send

        class WithoutListenerDoesNothing:
            """接続がなければ何もせずに戻る。"""

            kind @= POST

        class CallsListenerInCallerThread:
            """接続中は、渡された `tag` と引数をそのままリスナーに渡す。リスナーは `send()` を呼んだスレッドで呼ばれ、`send()` はリスナーが戻ってから戻る。"""

            kind @= POST

        class ReturnsNone:
            """戻り値は常に `None` で、リスナーの戻り値は送信側に返らない。"""

            kind @= POST

        class ListenerFailureGoesToErrorHandler:
            """リスナーが `Exception` を投げた場合、接続時に渡したエラーハンドラにその例外を渡す。その後の `send()` でも、リスナーは呼ばれ続ける。"""

            kind @= POST
            rationale @= "失敗後にリスナーを止めるかどうかは受信側の判断で、fport は決め打ちしない。"

        class LeftoverFailureIsDiscarded:
            """エラーハンドラが投げた `Exception`、およびエラーハンドラがない場合のリスナーの `Exception` は捨てられる。"""

            kind @= POST
            rationale @= "送信側を守る最後の防衛線。黙って捨てるのはここだけである。"

        class BaseExceptionIsNotCaught:
            """`Exception` ではない `BaseException`(`KeyboardInterrupt`、`SystemExit` など)は捕まえず、送信側へそのまま伝わる。"""

            kind @= POST
            rationale @= "中断や終了の要求は、送信口を通っても効かなければならない。"
            regression @= (
                "1.x では `send()` が `KeyboardInterrupt` まで握りつぶしていた。"
            )

    class connect:
        member @= Port.connect

        class ListenerIsCallable:
            """リスナーは呼び出し可能で、エラーハンドラは呼び出し可能か `None` である。違反した場合は `TypeError` で、接続は変わらない。"""

            kind @= PRE
            on_violation @= REJECTED

        class PortIsFree:
            """`Port` にはまだリスナーが接続されていない。違反した場合は `OccupiedError` で、既存の接続は変わらない。"""

            kind @= PRE
            on_violation @= REJECTED
            rationale @= "2 つ目の接続が黙って前の接続を上書きすることを防ぐ。"

        class ReturnsActiveConnection:
            """接続した `Connection` を返す。返った時点で、その接続は有効である。"""

            kind @= POST


class ConnectionContract:
    subject @= Connection

    class disconnect:
        member @= Connection.disconnect

        class StopsDelivery:
            """戻った後に始まった `send()` は、このリスナーを呼ばない。`Port` には再び接続できる。"""

            kind @= POST
            caution @= "fport は `send()` を直列化しないので、他のスレッドですでに始まっていた `send()` は、`disconnect()` が戻った後にリスナーを一度呼び終えることがある。"

        class AffectsOnlyThisConnection:
            """何度呼んでもよい。すでに外れた接続で呼んでも何もせず、同じ `Port` の新しい接続は外さない。"""

            kind @= POST

    class __exit__:
        member @= Connection.__exit__

        class DisconnectsEvenOnError:
            """`with` 文を抜けると、例外で抜けた場合も接続を外す。例外は抑えない。"""

            kind @= POST
            regression @= (
                "1.x では `with` の中で例外が起きると `Port` が占有されたまま残った。"
            )
