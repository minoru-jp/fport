"""計測の差し込み口: 処理の進み具合を表示する。

`count_words()` はライブラリ側の関数で、`progress` に進み具合を送るだけである。
表示のことは何も知らず、何もつながれていなければ何も起きない。進み具合を
表示するのは、それを使う CLI 側(`main()`)の判断である。

表示に失敗しても(たとえば出力先が閉じられても)、数える処理は止まらない。
失敗は `on_error` で受け取り、最後にまとめて知らせる。

    python examples/progress.py FILE...
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast

import fport

# ---------------------------------------------------------------- ライブラリ側

progress = fport.Port()
"""`count_words()` が進み具合を送る口。

- `("start", total)`: `total` 個のファイルを数え始める
- `("file", index, path, words)`: `index` 番目のファイルを数え終えた
"""


@dataclass(frozen=True)
class Count:
    files: int
    words: int


def count_words(paths: Sequence[Path]) -> Count:
    """ファイルの単語数を数える。"""
    progress.send("start", len(paths))
    words = 0
    for index, path in enumerate(paths, start=1):
        found = len(path.read_text(encoding="utf-8").split())
        words += found
        progress.send("file", index, path, found)
    return Count(files=len(paths), words=words)


# ---------------------------------------------------------------- CLI 側


class ProgressLine:
    """進み具合を 1 行ずつ表示するリスナー。"""

    def __init__(self, stream: TextIO) -> None:
        self._stream: TextIO = stream
        self._total: int = 0

    def __call__(self, tag: str, /, *args: object) -> None:
        match (tag, *args):
            case ("start", int(total)):
                self._total = total
            case ("file", int(index), Path() as path, int(words)):
                print(
                    f"[{index}/{self._total}] {path.name}: {words} words",
                    file=self._stream,
                )
            case _:
                raise ValueError(f"unexpected progress message: {tag!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ファイルの単語数を数える。")
    _ = parser.add_argument("paths", nargs="+", type=Path, metavar="FILE")
    paths = cast("list[Path]", parser.parse_args(argv).paths)

    failures: list[Exception] = []
    with progress.connect(ProgressLine(sys.stderr), on_error=failures.append):
        count = count_words(paths)

    print(f"{count.files} files, {count.words} words")
    if failures:
        print(
            f"(進み具合の表示に {len(failures)} 回失敗しました: {failures[0]!r})",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
