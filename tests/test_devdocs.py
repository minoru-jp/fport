"""文書の正本に関するテスト。

- canonical document が正本から生成し直したものと一致していること
- README のコード例が実際に動き、書いてあるとおりの結果を出すこと
- 文書に注入するバージョンが pyproject.toml とパッケージと一致していること
- CHANGELOG に現在のバージョンの項があること
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tomllib
from pathlib import Path

import pytest

import fport
from devdocs.canonical_sources.changelog import canonical as changelog
from devdocs.canonical_sources.readme import canonical as readme
from scripts import render_devdocs

ROOT = Path(__file__).resolve().parent.parent
HAS_GPFRAME = importlib.util.find_spec("gpframe") is not None


def test_canonical_documents_are_up_to_date() -> None:
    stale = render_devdocs.stale_documents()
    assert stale == [], "python scripts/render_devdocs.py で生成し直してください"


@pytest.mark.parametrize(
    ("example", "expected"),
    [
        (readme.QUICK_START, readme.QUICK_START_OUTPUT),
        (readme.ON_ERROR_EXAMPLE, readme.ON_ERROR_OUTPUT),
        (readme.FAN_OUT_EXAMPLE, readme.FAN_OUT_OUTPUT),
        pytest.param(
            readme.TAP_EXAMPLE,
            readme.TAP_OUTPUT,
            marks=pytest.mark.skipif(
                not HAS_GPFRAME, reason="gpframe is not installed"
            ),
        ),
    ],
    ids=["quick start", "on_error", "fan-out", "tap"],
)
def test_readme_examples_run(example: str, expected: str) -> None:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(example, "<README example>", "exec"), {"__name__": "__readme__"})  # noqa: S102 - README の例そのものを実行して確かめる
    assert output.getvalue().strip() == expected


def test_versions_agree() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    context = json.loads(
        (ROOT / "devdocs" / "config" / "context.json").read_text(encoding="utf-8")
    )
    assert context["project"]["version"] == project["project"]["version"]
    assert fport.__version__ == project["project"]["version"]
    assert (
        context["project"]["requires-python"] == project["project"]["requires-python"]
    )


def test_changelog_has_the_current_version() -> None:
    entry = "V" + fport.__version__.replace(".", "_")
    assert hasattr(changelog.CHANGELOG, entry)
