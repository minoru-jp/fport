# standman v1.0.0

## 概要

疎結合による汎用単方向関数連携モジュール

このモジュールは実装側から情報を送信するためのインターフェースを提供します。

## 主な目的と使い道

- ホワイトボックステストの実装側からの情報提出用途
- 簡単なアドオンの作成の際のエントリポイントの作成用途

## 対応環境

- Python 3.10 以降
- 外部依存ライブラリ: なし

## ライセンス

本モジュールは MIT License の下で提供されます。
詳細は [LICENSE](./LICENSE) ファイルを参照してください。


## インストール

```bash
pip install git+https://github.com/minoru_jp/standman.git
```

## 特徴

- 少ない手順で実装側に情報の送信口を設置できます。
- 送信インターフェースの使用が実装側に副作用を及ぼさない設計。(受信側の計算量のみ)
- 送信インターフェースは受信側のエラー、フレームワークのエラーを実装側に伝えません。
- 送信インターフェースは常にNoneを返します。
- インターフェースを定義する場所と共有の仕方によって、情報の送信の範囲を柔軟に定義することができます。
- 送信インターフェースへの接続の拒否を設定することができます。
- 送信インターフェースへの接続を拒否した場合でも実装側には常に有効なインターフェースが提供されます。

## 警告

このモジュールが採用する関数の連携は疎結合であり、実装側から接続先を明示しない構造になっているので、
実装側から外部へ送信する情報はよく検討されなければなりません。実装側からの安易な情報の送信は認証情報、
個人情報、その他クリティカルな情報の漏洩につながる恐れがあります。また、それらを復元可能な情報も同様です。

## 並列処理について

送信インターフェースはスレッドアンセーフです。これはインターフェースの使用が実装側が意図しない直列化を招く
ことを防ぐものです。並列処理におけるインターフェースを含めた全体の整合性の確保は利用者である実装側に依存します。

## 簡単な使用例

```python
from standman import create_session_policy

policy = create_session_policy()
port = policy.create_port()

def add(a, b):
    port.send("add", a, b)
    return a + b

def listener(tag, *args, **kwargs):
    print("Received:", tag, args, kwargs)

with policy.session(listener, port) as state:
    result = add(2, 3)
    print("Result:", result)

# Output:
# Received: add (2, 3) {}
# Result: 5
```

---

## 主要な API リファレンス

### `create_session_policy(*, block_port: bool = False, message_validator: SendFunction | None = None) -> SessionPolicy`

`SessionPolicy` を生成するファクトリ関数

* **パラメータ**

  * `block_port: bool`
    `True` の場合、このポリシーで作成された `Port` はすべて接続を拒否する
  * `message_validator: SendFunction | None`
    任意の送信検証関数。`Port.send()` の前に呼び出され、例外を投げると送信が拒否される
    この例外は送信側に伝播せず、セッション終了として扱われる

* **戻り値**
  `SessionPolicy`

---

### `class SessionPolicy`

`Port` の生成とセッション確立を管理するインターフェース

* **メソッド**

  * `create_port() -> Port`
    接続可能な `Port` を生成する

  * `create_noop_port() -> Port`
    接続を拒否する（no-op）`Port` を生成する

  * `session(listener: ListenFunction, target: Port) -> ContextManager[SessionState]`
    指定した `Port` に `listener` を接続してセッションを開始するコンテキストマネージャを返す

    * **パラメータ**

      * `listener: ListenFunction`
        `Port.send()` から渡されたメッセージを受け取るコールバック関数
        引数 `(tag: str, *args, **kwargs)` を取る
      * `target: Port`
        接続対象となる `Port` インスタンス

    * **戻り値**
      `ContextManager[SessionState]`
      `with` ブロックで利用するセッションコンテキストマネージャ
      ブロック内で `SessionState` を取得でき、`ok` と `error` を通じて状態を監視できる

    * **例外**

      * `TypeError`: `target` が `Port` インスタンスでない場合
      * `OccupiedError`: 指定した `Port` がすでに他のセッションで使用中の場合
      * `DeniedError`: `Port` または `SessionPolicy` が接続を拒否する設定の場合
      * `RuntimeError`: 内部状態の不整合など、通常は発生しないエラー

---

### `class Port`

実装（送信）側が情報を送るためのインターフェース

* **メソッド**

  * `send(tag: str, *args, **kwargs) -> None`
    任意の情報を登録済みリスナに送信する

    * リスナ未登録時は何もしない
    * 発生した例外は送信側へ伝播しない（fail-silent）
    * **スレッドアンセーフ**: 意図的に直列化を避ける設計

---

### `class SessionState`

セッションの状態を監視する読み取り専用インターフェース

* **プロパティ**

  * `ok: bool`
    セッションがまだ有効かどうか
  * `error: Exception | None`
    セッション終了の原因となった最初のエラー。なければ `None`

---

### 例外

* `class DeniedError(Exception)`
  ポリシーまたは `Port` により接続が拒否された場合に送出

* `class OccupiedError(Exception)`
  `Port` がすでに他のセッションに占有されている場合に送出

---

### プロトコル（型）

* `class SendFunction(Protocol)`&#x20;

  ```python
  def __call__(tag: str, *args, **kwargs) -> None
  ```

  送信側がメッセージ送信に用いる呼び出し可能オブジェクト

* `class ListenFunction(Protocol)`&#x20;

  ```python
  def __call__(tag: str, *args, **kwargs) -> None
  ```

  受信側がメッセージを処理するための呼び出し可能オブジェクト

---

## observer

このライブラリはリスナーの実装としてobserverを含みます。

### standmanと併用をした際の使用例

```python
from standman import create_session_policy
from standman.observer import ProcessObserver

def create_weather_sensor(port):
    """Weather sensor
    Specification:
        temp < 0        -> "Freezing" + send("freezing")
        0 <= temp <= 30 -> "Normal"   + send("normal")
        temp > 30       -> "Hot"      + send("hot")
    """
    def check_weather(temp: int) -> str:
        # If there is a bug here, it will be detected by the test
        if temp <= 0:   # ← Common place to inject a bug
            port.send("freezing", temp)
            return "Freezing"
        elif temp <= 30:
            port.send("normal", temp)
            return "Normal"
        else:
            port.send("hot", temp)
            return "Hot"
    return check_weather

policy = create_session_policy()
port = policy.create_port()

# Define expected conditions according to the specification
conditions = {
    "freezing": lambda t: t < 0,
    "normal":   lambda t: 0 <= t <= 30,
    "hot":      lambda t: t > 30,
}
observer = ProcessObserver(conditions)
check_weather = create_weather_sensor(port)

with policy.session(observer.listen, port) as state:
    # Test coverage for all three branches
    for i in (-5, 0, 31):
        check_weather(i)
        if not state.ok:
            raise AssertionError(f"observation failed on '{i}'")

    # Verify that the Observer did not detect any specification violations
    if observer.violation:
        details = []
        for tag, obs in observer.get_violated().items():
            details.append(
                f"[{tag}] reason={obs.fail_reason}, "
                f"count={obs.count}, first_violation_at={obs.first_violation_at}"
            )
        raise AssertionError("Observer detected violations:\n" + "\n".join(details))

print("All checks passed!")
```
---

## observer APIリファレンス

### Class `ProcessObserver`

プロセスの状態を監視し、条件違反や例外を管理する。

#### Constructor

```python
ProcessObserver(conditions: dict[str, Callable[..., bool]])
```

指定された条件群を監視対象として初期化する。

#### Methods

* `reset_observations() -> None`
  全ての観測結果をリセットする。

* `listen(tag: str, *args, **kwargs) -> None`
  指定タグの条件を評価する。条件違反または例外発生時にハンドラを呼び出す。

* `get_all() -> dict[str, Observation]`
  全ての観測結果を返す。

* `get_violated() -> dict[str, Observation]`
  違反が発生した観測結果を返す。

* `get_compliant() -> dict[str, Observation]`
  違反していない観測結果を返す。

* `get_unevaluated() -> dict[str, Observation]`
  未評価の観測結果を返す。

* `set_violation_handler(tag: str, fn: Callable[[Observation], None]) -> None`
  指定タグに違反ハンドラを設定する。

* `set_exception_handler(fn: Callable[[str, ExceptionKind, Observation | None, Exception], None]) -> None`
  例外ハンドラを設定する。

* `get_stat(tag: str) -> ConditionStat`
  指定タグの統計情報を返す。

#### Properties

* `violation: bool`
  いずれかの違反が存在するかを返す。

* `global_violation: bool`
  グローバルな違反が存在するかを返す。

* `local_violation: bool`
  ローカルな違反が存在するかを返す。

* `global_fail_reason: str`
  グローバル違反の理由を返す。

* `global_exception: Exception | None`
  グローバル例外を返す。

---

### Class `Observation`

条件ごとの詳細な観測結果を保持する。

#### Fields

* `count: int`
  評価回数を保持する。

* `violation: bool`
  違反が発生したかを保持する。

* `first_violation_at: int`
  初回違反発生の試行回数を保持する。

* `exc: Exception | None`
  発生した例外を保持する。

* `fail_condition: Callable[..., bool] | None`
  違反した条件関数を保持する。

* `fail_reason: str`
  違反理由を保持する。

---

### Class `ConditionStat`

条件の統計的な結果を簡易的に表現する。

#### Constructor

```python
ConditionStat(count: int, violation: bool, first_violation_at: int)
```

#### Properties

* `count: int`
  評価回数を返す。

* `violation: bool`
  違反が発生したかを返す。

* `first_violation_at: int`
  初回違反が発生した試行回数を返す。

---

### Enum `ExceptionKind`

例外の発生箇所を示す。

#### Constants

* `ON_CONDITION` – 条件評価時に例外発生。
* `ON_VIOLATION` – 違反ハンドラ実行時に例外発生。
* `ON_INTERNAL` – 内部処理中に例外発生。

---

## テスト

このモジュールはテストにpytestを用いています。  
tests/にテストは存在します。  
またlegacy/は無効になったテストが入っているため実行をスキップしてください。

