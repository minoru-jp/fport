"""fport のすべての検査をまとめて走らせる。CI とリリースも、これと同じものを使う。

リポジトリのルートで実行する。

    python tools/check.py                  # すべての検査(リリース用の published を除く)
    python tools/check.py lint tests       # 選んだ検査だけ
    python tools/check.py dist --tag v2.0.0 --dist-dir dist
                                           # 配布物を作って確かめ、dist/ に残す(リリース用)
    python tools/check.py published --tag v2.0.0
                                           # 文書が公開済みの状態か(リリース用)

検査:

    docs         canonical document が正本から生成し直したものと同じで、英語の公開文書が
                 canonical document と食い違っていない
    format       ruff format --check
    lint         ruff check
    types        basedpyright(src、contract/ports、scripts、tools、examples)
    types-tests  basedpyright -p tests(テスト、契約、文書の正本を利用側として)
    tests        pytest(契約の検査を含む)
    dist         sdist と wheel を作り、twine check、中身の検査、きれいな venv での動作確認。
                 版が pyproject.toml・パッケージ・文書・CHANGELOG で揃っていること
    published    (リリース用。名前を省略したときには走らない)文書が、その版を公開した
                 状態になっている。docs が通り、版が揃い、CHANGELOG の項に公開日がある

失敗した検査があっても残りを続け、最後にまとめて報告する。一つでも失敗すれば終了コードは 1。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import venv
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class Options:
    tag: str | None = None
    dist_dir: str | None = None


@dataclass(frozen=True)
class Outcome:
    ok: bool
    output: str


def command(*argv: str) -> Callable[[Options], Outcome]:
    def run(_: Options) -> Outcome:
        done = subprocess.run(
            argv, cwd=ROOT, capture_output=True, text=True, check=False
        )
        return Outcome(done.returncode == 0, done.stdout + done.stderr)

    return run


# ---------------------------------------------------------------- docs


def check_docs(_: Options) -> Outcome:
    # ROOT を sys.path に入れた後で読む。
    from scripts import published_docs, render_devdocs

    stale = render_devdocs.stale_documents()
    lines = [
        f"stale canonical document: {name} (run: python scripts/render_devdocs.py)"
        for name in stale
    ]
    lines += published_docs.problems()
    return Outcome(not lines, "\n".join(lines))


# ---------------------------------------------------------------- dist

REQUIRED_IN_WHEEL = (
    "fport/__init__.py",
    "fport/_port.py",
    "fport/gpframe.py",
    "fport/py.typed",
)
REQUIRED_IN_SDIST = (
    "PKG-INFO",
    "pyproject.toml",
    "README.md",
    "LICENSE",
    *(f"src/{name}" for name in REQUIRED_IN_WHEEL),
)
# gpframe なしで動くこと(fport の実行時の依存がないこと)も、ここで確かめる。
SMOKE = """
import fport
from fport.gpframe import tap

port = fport.Port()
seen = []
port.send("before")
with port.connect(lambda tag, *args: seen.append((tag, args))):
    port.send("hello", 1)
assert seen == [("hello", (1,))], seen
assert not port.connected
assert callable(tap)
print(fport.__name__, fport.__version__, "ok")
"""


def project() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as file:
        data = tomllib.load(file)
    return cast("dict[str, object]", data["project"])


def version_problems(version: str, tag: str | None) -> list[str]:
    """版が、タグ・パッケージ・文書の context・CHANGELOG の正本で揃っているか。"""
    import fport
    from devdocs.canonical_sources.changelog import canonical as changelog

    lines: list[str] = []
    if tag is not None and tag != f"v{version}":
        lines.append(f"tag {tag!r} does not match the project version v{version}")
    if fport.__version__ != version:
        lines.append(f"fport.__version__ is {fport.__version__!r}, not {version!r}")
    context = cast(
        "dict[str, dict[str, str]]",
        json.loads(
            (ROOT / "devdocs" / "config" / "context.json").read_text(encoding="utf-8")
        ),
    )
    if context["project"]["version"] != version:
        lines.append("devdocs/config/context.json has a different version")
    if not hasattr(changelog.CHANGELOG, "V" + version.replace(".", "_")):
        lines.append(f"the CHANGELOG has no entry for {version}")
    return lines


def check_dist(args: Options) -> Outcome:
    version = str(project()["version"])
    lines = version_problems(version, args.tag)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "dist"
        built = subprocess.run(
            [
                PYTHON,
                "-m",
                "build",
                "--sdist",
                "--wheel",
                "--outdir",
                str(out),
                str(ROOT),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if built.returncode != 0:
            return Outcome(False, "\n".join([*lines, built.stdout, built.stderr]))
        wheels = sorted(out.glob("*.whl"))
        sdists = sorted(out.glob("*.tar.gz"))
        if [w.name for w in wheels] != [f"fport-{version}-py3-none-any.whl"]:
            lines.append(f"unexpected wheels: {[w.name for w in wheels]}")
        if [s.name for s in sdists] != [f"fport-{version}.tar.gz"]:
            lines.append(f"unexpected sdists: {[s.name for s in sdists]}")
        twine = subprocess.run(
            [PYTHON, "-m", "twine", "check", "--strict", *map(str, out.iterdir())],
            capture_output=True,
            text=True,
            check=False,
        )
        if twine.returncode != 0:
            lines.append("twine check failed:\n" + twine.stdout + twine.stderr)
        if wheels:
            lines += inspect_wheel(wheels[0], version)
            lines += smoke_test(wheels[0], Path(tmp))
        if sdists:
            lines += inspect_sdist(sdists[0], version)
        keep = args.dist_dir
        if keep is not None and not lines:
            target = ROOT / keep
            target.mkdir(parents=True, exist_ok=True)
            for path in out.iterdir():
                _ = shutil.copy2(path, target / path.name)
            kept = [f"kept {p.name} in {keep}/" for p in sorted(out.iterdir())]
            return Outcome(True, "\n".join(kept))
    return Outcome(not lines, "\n".join(lines))


def inspect_wheel(wheel: Path, version: str) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata = archive.read(f"fport-{version}.dist-info/METADATA").decode()
    problems = [
        f"wheel lacks {name}" for name in REQUIRED_IN_WHEEL if name not in names
    ]
    problems += [
        f"wheel contains {name}"
        for name in sorted(names)
        if not name.startswith(("fport/", f"fport-{version}.dist-info/"))
    ]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "Description-Content-Type: text/markdown" not in metadata:
        problems.append("the wheel metadata does not declare a Markdown description")
    if readme.strip() not in metadata:
        problems.append(
            "the wheel metadata does not carry README.md as its description"
        )
    requires = str(project()["requires-python"])
    if f"Requires-Python: {requires}" not in metadata:
        problems.append(f"the wheel metadata does not require Python {requires}")
    runtime = [
        line
        for line in metadata.splitlines()
        if line.startswith("Requires-Dist:") and "extra ==" not in line
    ]
    if runtime:
        problems.append(f"the wheel has runtime dependencies: {runtime}")
    return problems


def inspect_sdist(sdist: Path, version: str) -> list[str]:
    prefix = f"fport-{version}/"
    with tarfile.open(sdist) as archive:
        names = {name.removeprefix(prefix) for name in archive.getnames()}
    return [f"sdist lacks {name}" for name in REQUIRED_IN_SDIST if name not in names]


def smoke_test(wheel: Path, tmp: Path) -> list[str]:
    """依存なしの、きれいな venv に wheel を入れて動かす。"""
    env = tmp / "venv"
    venv.EnvBuilder(with_pip=True).create(env)
    python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    install = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--quiet",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if install.returncode != 0:
        return ["installing the wheel failed:\n" + install.stdout + install.stderr]
    # リポジトリの src を読まないよう、別のディレクトリで動かす。
    run = subprocess.run(
        [str(python), "-I", "-c", SMOKE],
        cwd=tmp,
        capture_output=True,
        text=True,
        check=False,
    )
    expected = f"fport {project()['version']} ok"
    if run.returncode != 0 or run.stdout.strip() != expected:
        return ["the installed wheel does not work:\n" + run.stdout + run.stderr]
    return []


# ---------------------------------------------------------------- published

RELEASED_ON = re.compile(r"^released on: (\d{4}-\d{2}-\d{2})$", re.MULTILINE)


def released_on(changelog: str, version: str) -> str | None:
    """canonical document の CHANGELOG で、その版の項に書かれた公開日。なければ None。"""
    heading = f"## V{version.replace('.', '_')}\n"
    start = changelog.find(heading)
    if start < 0:
        return None
    body = changelog[start + len(heading) :]
    end = body.find("\n## ")
    section = body if end < 0 else body[:end]
    found = RELEASED_ON.search(section)
    return found[1] if found else None


def check_published(args: Options) -> Outcome:
    """文書が、その版を公開した状態になっているか。リリースのときだけ走らせる。

    - canonical document が最新で、英語の公開文書がそれと食い違っていない(docs と同じ)
    - 版がタグ・パッケージ・文書・CHANGELOG で揃っている
    - CHANGELOG のその版の項に、公開日(`released_on`)がある
    """
    docs = check_docs(args)
    lines = [docs.output] if not docs.ok else []
    version = str(project()["version"])
    lines += version_problems(version, args.tag)
    changelog = (ROOT / "devdocs" / "canonical_documents" / "CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    if released_on(changelog, version) is None:
        lines.append(
            f"the CHANGELOG entry for {version} has no release date; set "
            + "`released_on` in devdocs/canonical_sources/changelog/canonical.py, "
            + "bring STATUS and the CHANGELOG text to the released state, then "
            + "re-render and re-translate the documents"
        )
    return Outcome(not lines, "\n".join(lines))


# ---------------------------------------------------------------- main

# basedpyright には、この検査を起動した Python を明示的に渡す。渡さないと、
# activate していない仮想環境から起動したときに PATH 上の別の Python を見てしまう。
CHECKS: dict[str, Callable[[Options], Outcome]] = {
    "docs": check_docs,
    "format": command(PYTHON, "-m", "ruff", "format", "--check", "."),
    "lint": command(PYTHON, "-m", "ruff", "check", "."),
    "types": command(PYTHON, "-m", "basedpyright", "--pythonpath", PYTHON),
    "types-tests": command(
        PYTHON, "-m", "basedpyright", "--pythonpath", PYTHON, "-p", "tests"
    ),
    "tests": command(PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider"),
    "dist": check_dist,
    "published": check_published,
}
# リリースのときだけ明示して走らせる検査。名前を省略したときには含めない。
RELEASE_ONLY = ("published",)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="fport のすべての検査を走らせる。")
    _ = parser.add_argument(
        "checks",
        nargs="*",
        metavar="CHECK",
        help=f"走らせる検査({', '.join(CHECKS)})。省略すると {', '.join(RELEASE_ONLY)} 以外のすべて",
    )
    _ = parser.add_argument(
        "--tag", help="dist、published: リリースのタグ。v<version> と一致すること"
    )
    _ = parser.add_argument(
        "--dist-dir", help="dist: 確かめた配布物をこのディレクトリに残す"
    )
    args = parser.parse_args(argv)
    selected = cast("list[str]", args.checks) or [
        name for name in CHECKS if name not in RELEASE_ONLY
    ]
    options = Options(
        tag=cast("str | None", args.tag), dist_dir=cast("str | None", args.dist_dir)
    )
    unknown = [name for name in selected if name not in CHECKS]
    if unknown:
        parser.error(f"unknown checks: {', '.join(unknown)}")

    failed: list[str] = []
    for name in selected:
        started = time.monotonic()
        outcome = CHECKS[name](options)
        elapsed = time.monotonic() - started
        print(
            f"{name}: {'ok' if outcome.ok else 'FAILED'} ({elapsed:.1f}s)", flush=True
        )
        if not outcome.ok:
            failed.append(name)
            print(outcome.output.rstrip(), flush=True)
        elif outcome.output and name == "dist":
            print(outcome.output.rstrip(), flush=True)
    if failed:
        print(f"failed: {', '.join(failed)}", flush=True)
        return 1
    print("all checks passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
