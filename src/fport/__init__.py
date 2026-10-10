"""fport: 送信側に影響を与えない、一方向の送信口。

実装側に `Port` を置き、`port.send(tag, *args, **kwargs)` で情報を出す。
受信側は `port.connect(listener)` で接続する。接続がなければ `send()` は何もしない。

gpframe と組み合わせる部品は `fport.gpframe` にある(gpframe への依存はない)。
"""

from ._port import Connection, ErrorHandler, Listener, OccupiedError, Port

__version__ = "2.0.0"

__all__ = (
    "Connection",
    "ErrorHandler",
    "Listener",
    "OccupiedError",
    "Port",
    "__version__",
)
