
# standman

> !!現在のバージョン0.3.0では、このドキュメントに含まれる使用例が実際に動くかどうかを含めてテストが実施されていません。  
> APIや挙動が予告なく変わる可能性があります。利用は自己責任でお願いします。

## 概要

疎結合による単方向関数連携モジュール。  
主に簡単なホワイトボックステストの実施を目的としている。  
また、簡単なアドオンなどの作成に使用することを想定している。

- standman 外部向けインターフェースのファクトリ関数などが定義されている。
- standman.observer Listenerの実装例としてホワイトボックステスト用のモジュールを定義している。

## 特徴

- 少ない手順で実装(送信側)に情報のリークポイントを埋め込む手段を提供する。
- 実装側の行うリークの内容に関するフィルタリング手段を提供する。
- 実装側が使用するすべてのインターフェースはfail-silent。受信側の失敗やフレームワーク側の失敗が実装側に伝わらないので実装側は副作用を気にせずリークポイントを埋め込むことができる。
- 受信関数はfail-soft。受信関数内で例外が起こっても、セッションは終了せず、クエリにより、セッションの継続の確認、例外の取得が行える。
- 受信側のPortへの接続の失敗はfail-fast。セッションの開始前に例外が投げられる。
- 受信側が送信側のPortインターフェースを指定して接続する構造になっており、送信側はPortインターフェースの定義の仕方で受信側関数へ流す情報の範囲を定義することができる。->使用例・最小構成を参照


## 警告

- 個人情報、認証情報そのほか、リークされて困るような情報を扱うプログラムにこのフレームワークを使用しないこと。(実装側から見ると不明な場所への情報のリークを行うことと同じであるため)

## 使用例

### 最小構成 - 関数ごとにPortを設定

```python
from standman import create_session_policy

policy = create_session_policy()
create_port = policy.create_port

def sender():
    port = sender._port
    port.send("example", "sender")

sender._port = create_port()

```

### 最小構成 - クラスレベルでPortを設定

```python
from standman import create_session_policy

policy = create_session_policy()
create_port = policy.create_port

class Foo:
    _port = create_port()

    def method(self):
        Foo._port.send("example", "Foo.method")
    
class Bar(Foo):
    def method(self):
        super().method()
        Foo._port.send("example", "Bar.method")

```

### 最小構成 - モジュールレベルでPortを設定

```python
from standman import create_session_policy

policy = create_session_policy()
port = policy.create_port()

def func1():
    port.send("example", "func1")

def func2():
    port.send("example", "func2")

```

### observerの使用例

```python
from standman import create_session_policy
from standman.observer import create_process_observer

# management.py
def message_validator(tag, *args, **kwargs):
    if not all(isinstance(a, int) for a in (*args, *kwargs.values())):
        raise TypeError("Sending data is int only.")

policy = create_session_policy(message_validator = message_validator)

# sender.py (implementation module)

create_port = policy.create_port

def bake_cookies(num_children):
    port = bake_cookies._port
    ... # process: Mom baking some cookies
    port.send("Share nicely", num_children, len(cookies))
    ... # process: Dad doing something
    return cookies

bake_cookies._port = create_port()

# receiver.py (test module in pytest etc..)
def test_bake_cookies_share_nicely():
    share_nicely = lambda ch, co: co % ch == 0
    observer = create_process_observer({"Share nicely": share_nicely})

    with policy.session(observer.listen, bake_cookies._port) as state:

        bake_cookies(3)
        
        if state.active:
            back_then = not observer.get_condition_stat("Share nicely").violation
            if not share_nicely(num_children, len(cookies)):
                if back_then:
                    assert False, "Mom is suspicious."
                else:
                    assert False, "Dad is suspicious."
        else:
            if state.error:
                assert False, f"Observing is fail with {state.error}"
```

### 接続の拒否とPortの無効化

接続の必要のない場合にポリシーまたは実装側の各所でPortへの接続を拒否、または無効化する方法

#### SessionPolicy生成時に接続のブロックを指定する

```python
policy = create_session_policy(block_port = True)
```

#### 実装側のcreate_portへno-opのPortを返すディスパッチャを指定

```python
create_port = policy.create_noop_port
```

