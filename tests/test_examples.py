"""作例(examples/)のテスト。

作例が書いてあるとおりに動き、送信口がそれぞれの場面で約束どおりに振る舞うことを確かめる。
pipeline_monitor は gpframe を使うので、gpframe がなければ飛ばす。
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from examples import lru_cache, progress

# ---------------------------------------------------------------- lru_cache


def test_lru_cache_eviction_order_is_observable() -> None:
    cache: lru_cache.LRUCache[str, str] = lru_cache.LRUCache(2, load=str.upper)
    events: list[tuple[str, str]] = []

    with cache.port.connect(lambda tag, key: events.append((tag, key))):
        values = [cache.get(key) for key in ["a", "b", "a", "c", "b", "a"]]

    assert values == ["A", "B", "A", "C", "B", "A"]
    assert [key for tag, key in events if tag == "evict"] == ["b", "a", "c"]
    assert [tag for tag, _ in events].count("hit") == 1


def test_lru_cache_works_without_a_listener() -> None:
    cache: lru_cache.LRUCache[int, int] = lru_cache.LRUCache(1, load=lambda n: n * 2)

    assert [cache.get(n) for n in (1, 1, 2)] == [2, 2, 4]
    assert not cache.port.connected


def test_lru_cache_main_prints_the_trace(capsys: pytest.CaptureFixture[str]) -> None:
    lru_cache.main()

    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines] == [
        "miss", "miss", "hit", "miss", "evict", "miss", "evict", "miss", "evict",
    ]  # fmt: skip


# ---------------------------------------------------------------- progress


def write(path: Path, text: str) -> Path:
    _ = path.write_text(text, encoding="utf-8")
    return path


def test_progress_reports_each_file(tmp_path: Path) -> None:
    paths = [write(tmp_path / "a.txt", "one two three"), write(tmp_path / "b.txt", "x")]
    seen: list[tuple[object, ...]] = []

    with progress.progress.connect(lambda *message: seen.append(message)):
        count = progress.count_words(paths)

    assert count == progress.Count(files=2, words=4)
    assert seen == [("start", 2), ("file", 1, paths[0], 3), ("file", 2, paths[1], 1)]


def test_progress_display_failure_does_not_stop_counting(tmp_path: Path) -> None:
    paths = [write(tmp_path / "a.txt", "one two"), write(tmp_path / "b.txt", "three")]
    closed = io.StringIO()
    closed.close()
    failures: list[Exception] = []

    listener = progress.ProgressLine(closed)
    with progress.progress.connect(listener, on_error=failures.append):
        count = progress.count_words(paths)

    assert count == progress.Count(files=2, words=3)
    assert len(failures) == 2
    assert all(isinstance(e, ValueError) for e in failures)


def test_progress_main_separates_result_and_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = [write(tmp_path / "a.txt", "one two three"), write(tmp_path / "b.txt", "x")]

    assert progress.main([str(p) for p in paths]) == 0

    captured = capsys.readouterr()
    assert captured.out == "2 files, 4 words\n"
    assert captured.err.splitlines() == ["[1/2] a.txt: 3 words", "[2/2] b.txt: 1 words"]
    assert not progress.progress.connected


# ---------------------------------------------------------------- pipeline_monitor


def test_pipeline_monitor_counts_every_job() -> None:
    _ = pytest.importorskip("gpframe")
    from examples import pipeline_monitor

    summary = pipeline_monitor.run(count=50, workers=3)

    assert summary.total == 50
    assert summary.failed == [7, 14, 21, 28, 35, 42, 49]
    assert sum(summary.done.values()) == 43
    assert set(summary.done) <= {"Worker-1", "Worker-2", "Worker-3"}
    assert not pipeline_monitor.port.connected


def test_pipeline_monitor_surfaces_an_unexpected_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gpframe = pytest.importorskip("gpframe")
    from examples import pipeline_monitor

    def chatty(job: int) -> int:
        pipeline_monitor.port.send("unexpected", job)  # 監視の側が知らない形
        return job

    monkeypatch.setattr(pipeline_monitor, "handle", chatty)

    with pytest.raises(gpframe.SessionFailed) as caught:
        _ = pipeline_monitor.run(count=5, workers=2)

    [work] = caught.value.frames
    assert work.name == "Work"
    report = work.incomplete
    assert report is not None
    assert [frame.name for frame in report.broken] == ["Monitor"]
    # 接続を外すまでに届いた分だけ失敗が集まる。1 件ならその例外、複数なら ExceptionGroup。
    error = report.broken[0].error
    leaves = error.exceptions if isinstance(error, ExceptionGroup) else (error,)
    assert leaves
    assert all(isinstance(e, ValueError) for e in leaves)
    assert not pipeline_monitor.port.connected


def test_pipeline_monitor_main_prints_a_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = pytest.importorskip("gpframe")
    from examples import pipeline_monitor

    assert pipeline_monitor.main(["--jobs", "20", "--workers", "2"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("done: 18 (")
    assert lines[1] == "failed: 2 (jobs 7, 14)"
    assert lines[2].startswith("slowest: ")
