"""gpframe 用ルーティン `fport.gpframe.tap` の契約。

`tap` は、接続の期間を gpframe のフレームの寿命に合わせ、リスナーの失敗を
受信側のフレームの失敗に変える。送信側は、ここでも何の影響も受けない。
"""

from shikumi_contrace import (
    POST,
    PRE,
    REJECTED,
    depends_on,
    kind,
    member,
    on_violation,
    rationale,
    subject,
)

from contract.port_contract import PortContract
from contract.ports.surface import Tap


class TapContract:
    subject @= Tap
    depends_on @= PortContract

    class __call__:
        member @= Tap.__call__

        class PortIsFree:
            """`port` にはまだリスナーが接続されていない。違反した場合は `OccupiedError` を送出し、`out` は閉じる。"""

            kind @= PRE
            on_violation @= REJECTED

        class ForwardsEachSend:
            """接続中の `send()` ごとに、`convert(tag, *args, **kwargs)` の結果を `out.put()` に渡す。`convert` の既定は `(tag, args, kwargs)` を作る。"""

            kind @= POST

        class EndsOnStopRequest:
            """停止が要求されると、接続を外して普通に戻る。始まる前にすでに停止が要求されていた場合も、すぐに戻る。"""

            kind @= POST

        class ListenerFailureFailsTheFrame:
            """`convert` や `out.put()` が `Exception` を投げると、接続を外してその例外を送出する。複数あれば `ExceptionGroup` にまとめる。送信側の `send()` は影響を受けない。"""

            kind @= POST
            rationale @= "送信側を守ったまま、受信側の失敗を gpframe の broken frame として扱えるようにする。"

        class AlwaysClosesTheSink:
            """どの終わり方でも、戻る前に `out.close()` を呼ぶ。"""

            kind @= POST
            rationale @= "下流で `receive()` しているフレームを、自然に終わらせる。"

        class AlwaysDisconnects:
            """どの終わり方でも、戻った後の `port` にはリスナーが接続されていない。"""

            kind @= POST
