"""テストで内部の判断を観察する: LRU キャッシュ。

キャッシュが「どのキーを、どの順で追い出したか」は、`get()` の戻り値からは見えない。
普通はモックを差し込むか、内部の状態を覗くことになる。ここではキャッシュに送信口を
置き、当たり・外れ・追い出しを `send()` するだけにしておく。テストはそれをつないで
観察し、本番では何もつながないので、何も起きない。

    python examples/lru_cache.py
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

import fport

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """容量を超えたら、最も長く使われていないものを追い出すキャッシュ。

    `port` には次を送る。

    - `("hit", key)`: キャッシュにあった
    - `("miss", key)`: キャッシュになく、`load(key)` で読み込んだ
    - `("evict", key)`: 容量を超えたので追い出した
    """

    def __init__(self, capacity: int, load: Callable[[K], V]) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.port: fport.Port = fport.Port()
        self._capacity: int = capacity
        self._load: Callable[[K], V] = load
        self._items: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> V:
        if key in self._items:
            self._items.move_to_end(key)
            self.port.send("hit", key)
            return self._items[key]
        self.port.send("miss", key)
        value = self._load(key)
        self._items[key] = value
        if len(self._items) > self._capacity:
            evicted, _ = self._items.popitem(last=False)
            self.port.send("evict", evicted)
        return value


def show(tag: str, key: object) -> None:
    print(f"{tag:<5} {key}")


def main() -> None:
    cache: LRUCache[str, str] = LRUCache(2, load=str.upper)
    with cache.port.connect(show):
        for key in ["a", "b", "a", "c", "b", "a"]:
            _ = cache.get(key)


if __name__ == "__main__":
    main()
