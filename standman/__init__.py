"""

疎結合、最少手順による関数接続のためのフレームワーク

ホワイトボックステストを簡単に行いたいという目的で作成しました。

全体図:
    from pathlib import Path

    from standman import create_session_policy
    from standman.process_observer import create_process_observer

    from foo import SuperSecretData
    
    # 管理側
    def args_validator(*args, **kwargs):
        if any(isinstance(a, SuperSecretData) for a in (*args, *kwargs.values())):
            raise TypeError("Don't send it!")

    policy = create_session_policy(Path(__file__), args_validator = args_validator)
    
    # 送信側
    get_port = policy.get_port_dispatcher()

    def bake_cookies(num_children):
        port = get_port()
        ... # process: Mom baking some cookies
        port.send("Share nicely", num_children, len(cookies)) # port sends specified args to `somewhere`
        ... # process: Dad doing something
        return cookies
    
    # 受信側
    share_nicely = lambda ch, co: co % ch == 0
    observer = create_process_observer({"Share nicely": share_nicely})
    session = policy.session_entry(observer, bake_cookies)

    with session as invoker:
        num_children = 3
        cookies = invoker(num_children) # invoker invokes bake_cookies

    back_then = not observer.get_condition_stat("Share nicely").violation
    if not share_nicely(num_children, len(cookies)):
        if back_then:
            assert False, "Mom sus."
        else:
            assert False, "Dad sus."
    

警告:
    port.send("Share nicely", num_children, len(cookies)) # port sends specified args to `somewhere`
    port.send(...)は「自分でする不特定に対するリーク」と同じです。これは送信側は自分から
    接続する場所を指定することができないので構造的に避けられません。

注記:
    単純な呼び出しで使用されることを想定しています。
    フレームを用いて呼び出し側の情報を取るので結構オーバーヘッドが大きそう

    誤接続に対しては、いくつかの対策をしているつもりですが断言できません。
    基本的にリスナー側のファイルパスを確認するくらいです。

    port = get_port()のみでは再帰・再入・多態には対応できません。
    単純な再帰用に
        def fn(port = None):
            port = get_port(port)
    という使い方をサポートしています。

    並列の実行はいけますが、やはり上記のような複雑な呼び出しが絡んでくると
    何とも言えません。

特徴：
    送信側と受信側の責任境界をはっきりとさせるために次のような設計になっています。
    
    - 受信側がいかなる理由で接続に失敗しても(接続の拒絶、認証失敗、例外の発生など)送信側には
      常に同じプロトコルを実装した`有効な`インターフェースが返されます。接続に失敗している場合
      返されたインターフェースは引数のチェックのみを行い、受信側にそれを送信しません。

    - `Port.send()`は責任境界を示します。送信側が渡したタグと引数は`.send()`でポリシーに
      よるチェックにかけられます。この時点で不正となった場合、送信側に例外が投げられます。
      チェックが通り、受信側へ処理が移ってからは例外は送信側に伝播しません。
    
    - `Port.send()`の戻り値は常にNoneです。

"""

__version__ = "0.1.0"
# This is an initial working version.
# Public API is not yet stable and may change without notice.

from .port import Port

from .policy import create_session_policy
from .policy import SessionPolicy, Listener, Session, SessionUnverifiedReason

import process_observer

__all__ = (
    "Port",
    "create_session_policy",
    "SessionPolicy",
    "Listener",
    "Session",
    "SessionUnverifiedReason",
    "process_observer"
)