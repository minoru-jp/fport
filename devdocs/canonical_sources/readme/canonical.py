"""fport の README の正本。

コード例は `test_target_field` に分け、文字列そのものを定数として持つ。
tests/test_devdocs.py がこの定数を実行して、例が実装と食い違っていないことを確かめる。
"""

from shikumi_devdoc.norms.common import canonical_source
from shikumi_devdoc.norms.document import test_target_field, title

QUICK_START = """\
import fport

port = fport.Port()


def add(a: int, b: int) -> int:
    port.send("add", a, b)  # 何も接続されていなければ、何もしない
    return a + b


print(add(1, 2))

with port.connect(lambda tag, *args: print("received:", tag, args)):
    print(add(2, 3))
"""

QUICK_START_OUTPUT = """\
3
received: add (2, 3)
5"""

ON_ERROR_EXAMPLE = """\
import fport

port = fport.Port()
errors: list[Exception] = []


def must_be_positive(tag: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{tag}: {value} is not positive")


with port.connect(must_be_positive, on_error=errors.append):
    for value in (1, -1, 2):
        port.send("value", value)  # 送信側には何も起きない

print(errors)
"""

ON_ERROR_OUTPUT = "[ValueError('value: -1 is not positive')]"

FAN_OUT_EXAMPLE = """\
from collections.abc import Callable

import fport


def fan_out(*listeners: Callable[..., object]) -> Callable[..., None]:
    def listener(tag: str, *args: object, **kwargs: object) -> None:
        for fn in listeners:
            fn(tag, *args, **kwargs)

    return listener


port = fport.Port()
seen: list[str] = []

with port.connect(fan_out(seen.append, lambda tag: print("got", tag))):
    port.send("ready")

print(seen)
"""

FAN_OUT_OUTPUT = """\
got ready
['ready']"""

TAP_EXAMPLE = """\
import gpframe

import fport
from fport.gpframe import Message, tap

port = fport.Port()
events: gpframe.Channel[Message] = gpframe.Channel(tuple)


def show(ctx: gpframe.Context, events: gpframe.Channel[Message]) -> None:
    for tag, args, _ in events.receive(ctx):
        print(tag, args)
        if tag == "done":
            return


with gpframe.session(timeout=5) as s:
    tapping = s.spawn(tap, port, events)
    shown = s.spawn(show, events)
    while not port.connected:  # 接続される前の send() は届かない
        tapping.wait(0.01)
    port.send("progress", 50)
    port.send("done")
    shown.wait()
    s.stop()  # tap は接続を外し、Channel を閉じて終わる

print(port.connected, events.closed)
"""

TAP_OUTPUT = """\
progress (50,)
done ()
False True"""

quick_start = test_target_field("quick start")
on_error_example = test_target_field("on_error example")
fan_out_example = test_target_field("fan-out example")
tap_example = test_target_field("tap example")
quick_start_output = test_target_field("quick start output")
on_error_output = test_target_field("on_error output")
fan_out_output = test_target_field("fan-out output")
tap_output = test_target_field("tap output")


@canonical_source(
    "{{project.name}}",
    filename="README.md",
    merge_policy="all",
    heading="title",
)
class SECTION_001:
    r"""
    `{{project.name}}` は、実装の中に置く**一方向の送信口**です。

    実装側は `Port` を置いて `port.send(tag, *args, **kwargs)` で情報を出し、受信側は `port.connect(listener)` でそれを受け取ります。何も接続されていなければ `send()` は何もしません。どこにつながっているかを実装側は知らず、つながっていることで実装側の振る舞いが変わることもありません。

    テストで実装の内部の様子を観察したり、ログや計測の差し込み口を作ったり、簡単な拡張のための入口を用意したりするのに使えます。
    """

    class SECTION_002:
        r"""
        ```python
        {{quick_start}}
        ```

        実行すると、次のように表示されます。

        ```text
        {{quick_start_output}}
        ```

        `connect()` が返す `Connection` は `with` 文で使え、抜けるときに接続を外します。`with` の中で例外が起きた場合も同じです。`with` を使わずに、`connection.disconnect()` で外すこともできます。
        """

        title @= "使い方"
        quick_start @= QUICK_START
        quick_start_output @= QUICK_START_OUTPUT

    class SECTION_003:
        r"""
        送信口は、送信側(実装側)を守ることだけを約束します。

        - **`send()` は送信側に例外を伝えません。** リスナーが投げた `Exception` は送信側に届かず、戻り値は常に `None` です。
        - **`send()` はロックを取りません。** 送信口を置いたことで、実装側に直列化が持ち込まれることはありません。複数のスレッドから `send()` すれば、リスナーも同時に動きえます。直列化が持ち込まれると、実装側の並行性の問題が隠れてしまうためです。
        - **リスナーは、`send()` を呼んだスレッドで、その場で呼ばれます。** キューに積んだり、別のスレッドへ渡したりはしません。それが必要なら、リスナーの側で行います。
        - **中断や終了の要求は通します。** `Exception` ではない `BaseException`(`KeyboardInterrupt` や `SystemExit` など)は捕まえず、送信側へそのまま伝わります。

        それ以外のこと、たとえば受け取った情報をどう運ぶか、リスナーの失敗をどう扱うかは、受信側が決めます。
        """

        title @= "送信側に約束すること"

    class SECTION_004:
        r"""
        リスナーが `Exception` を投げた場合、`connect()` に `on_error` を渡しておけば、その例外が渡されます。

        ```python
        {{on_error_example}}
        ```

        実行すると、`{{on_error_output}}` と表示されます。

        リスナーは失敗した後も、`send()` のたびに呼ばれ続けます。失敗したら止めたいなら、受信側で `disconnect()` してください。`on_error` を渡さなかった場合や、`on_error` 自身が例外を投げた場合、その例外は捨てられます。送信口が例外を黙って捨てるのはここだけです。
        """

        title @= "リスナーの失敗"
        on_error_example @= ON_ERROR_EXAMPLE
        on_error_output @= ON_ERROR_OUTPUT

    class SECTION_005:
        r"""
        一つの `Port` に接続できるリスナーは一つだけで、接続済みの `Port` に `connect()` すると `OccupiedError` になります。2 つ目の接続が、黙って前の接続を上書きすることはありません。

        複数のリスナーに配りたい場合は、受けたリスナーが他へつなぎます。

        ```python
        {{fan_out_example}}
        ```

        実行すると、次のように表示されます。

        ```text
        {{fan_out_output}}
        ```

        どの順に呼ぶか、一つが失敗したら残りをどうするかは、配る側が決めます。
        """

        title @= "リスナーは一つ"
        fan_out_example @= FAN_OUT_EXAMPLE
        fan_out_output @= FAN_OUT_OUTPUT

    class SECTION_006:
        r"""
        [gpframe](https://github.com/minoru-jp/gpframe) と組み合わせると、受け取った情報を別のスレッドへ運んだり、接続の期間をフレームの寿命に合わせたりできます。`fport.gpframe.tap` は、`Port` に届いたものを gpframe の `Channel` へ流し続けるフレーム用のルーティンです。

        ```python
        {{tap_example}}
        ```

        実行すると、次のように表示されます。

        ```text
        {{tap_output}}
        ```

        `tap` は停止が要求されると接続を外して戻り、どの終わり方でも最後に `Channel` を閉じます。`Channel` への `put()` が失敗した場合(満杯や、閉じた後など)は、送信側には何も起きず、`tap` のフレームがその例外で失敗します。受信側は gpframe のやり方で、`escalate()` するか `ignore()` するかを選べます。

        fport は gpframe に依存しません。`tap` が使うのは `ctx.on_stop()`、`out.put()`、`out.close()` だけです。
        """

        title @= "gpframe と組み合わせる"
        tap_example @= TAP_EXAMPLE
        tap_output @= TAP_OUTPUT

    class SECTION_009:
        r"""
        [`examples/`](https://github.com/minoru-jp/fport/tree/main/examples) に、送信口が役に立つ場面を一つずつ作例として置いています。どれも `python examples/<名前>.py` で実行できます。

        - [`lru_cache.py`](https://github.com/minoru-jp/fport/blob/main/examples/lru_cache.py): **テストで内部の判断を観察する。** キャッシュが当たり・外れ・追い出しを送り、テストは「どのキーがどの順で追い出されたか」を確かめます。戻り値からは見えないことを、モックも内部の覗き見も使わずに観察できます。
        - [`progress.py`](https://github.com/minoru-jp/fport/blob/main/examples/progress.py): **計測の差し込み口。** ライブラリ側の関数は進み具合を送るだけで、表示するかどうかは使う側が決めます。表示が失敗しても、処理は止まりません。
        - [`pipeline_monitor.py`](https://github.com/minoru-jp/fport/blob/main/examples/pipeline_monitor.py): **gpframe と組み合わせる。** 複数のワーカーが同じ `Port` に結果を送り、監視のフレームが `tap` で集めて集計します。ワーカーは監視のことを知らず、運ぶのは gpframe の `Channel` です。gpframe が必要です。
        """

        title @= "作例"

    class SECTION_007:
        r"""
        ```bash
        pip install "fport>={{project.version}}"
        ```

        Python `{{project.requires-python}}` が必要です。実行時の依存パッケージはありません。

        `2.0.0` は設計から作り直した版で、`1.x` 系との互換性はまったくありません。
        """

        title @= "インストール"

    class SECTION_008:
        r"""
        - [STATUS.md](STATUS.md): 開発段階、範囲、品質の状態、今後の方向
        - [CHANGELOG.md](CHANGELOG.md): 版ごとの変更
        - `contract/`: 振る舞いの約束。fport では `shikumi-contrace` の契約が振る舞いの正本です
        """

        title @= "関連文書"
