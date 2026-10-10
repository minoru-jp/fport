"""devdocs の正本から canonical document を生成する。

リポジトリのルートで実行する。

    python scripts/render_devdocs.py            # devdocs/canonical_documents に生成
    python scripts/render_devdocs.py --check    # 生成結果が最新かだけを確かめる

生成する文書の一覧は `RENDERS` が唯一の置き場所で、テストもこれを使う。
"""

from __future__ import annotations

import argparse
import contextlib
import filecmp
import io
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from shikumi_devdoc.cli import main as devdoc_main

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "devdocs" / "config"
DOCUMENTS = ROOT / "devdocs" / "canonical_documents"


@dataclass(frozen=True)
class Render:
    module: str
    uses_context: bool = False


RENDERS: tuple[Render, ...] = (
    Render("devdocs.canonical_sources.readme.canonical", uses_context=True),
    Render("devdocs.canonical_sources.status.canonical", uses_context=True),
    Render("devdocs.canonical_sources.changelog.canonical"),
)


def render(output: Path) -> None:
    """すべての正本を `output` に生成する。失敗すれば `RuntimeError`。"""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    context = (CONFIG / "context.json").read_text(encoding="utf-8")
    for item in RENDERS:
        argv = ["render", "document", item.module, "-o", str(output)]
        if item.uses_context:
            argv += ["--context", context]
        argv += ["--notice", str(CONFIG / "notice.toml"), "--translation-source"]
        log = io.StringIO()
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            status = devdoc_main(argv)
        if status != 0:
            raise RuntimeError(f"failed to render {item.module}:\n{log.getvalue()}")


def _markdown_files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*.md")}


def stale_documents() -> list[str]:
    """生成し直すと内容が変わる、または過不足のある canonical document を返す。"""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        render(fresh)
        names = sorted(_markdown_files(fresh) | _markdown_files(DOCUMENTS))
        return [
            name
            for name in names
            if not (fresh / name).exists()
            or not (DOCUMENTS / name).exists()
            or not filecmp.cmp(fresh / name, DOCUMENTS / name, shallow=False)
        ]


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="devdocs の正本から canonical document を生成する。"
    )
    _ = parser.add_argument(
        "--check", action="store_true", help="生成結果が最新かだけを確かめる"
    )
    check = bool(parser.parse_args().check)  # pyright: ignore[reportAny] - argparse の値は Any
    if check:
        stale = stale_documents()
        for name in stale:
            print(f"stale: {name}")
        return 1 if stale else 0
    render(DOCUMENTS)
    for name in sorted(_markdown_files(DOCUMENTS)):
        print(Path("devdocs/canonical_documents") / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
