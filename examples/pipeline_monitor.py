"""gpframe と組み合わせる: ワーカーの仕事ぶりを監視する。

    Pipeline
    ├── Aggregate        events を集計する。events が閉じて空になれば終わる
    └── Work             監視つきで仕事をする段
        ├── Monitor      port に届いたものを events へ流す(fport.gpframe.tap)
        ├── Produce      jobs に仕事を入れ、入れ終われば jobs を閉じる
        └── Worker × K   jobs から仕事を取り、結果を port に送る

ワーカーは監視のことを何も知らず、結果を `port.send()` するだけである。`send()` は
ロックを取らないので、K 個のワーカーが同時に送ってよい。送られたものを別のスレッドへ
運ぶのは gpframe の `Channel` の役目である。

仕事が全部終わると、Work は自分のセッションを止める。Monitor は接続を外して events を
閉じ、Aggregate は残りを集計し終えてから終わる。Aggregate を Work の外に置いているのは、
Work を止めても Aggregate の受け取りを止めないためである。

監視の側が想定していないものを受け取った場合(`to_event()` の失敗)、ワーカーには何も
起きず、Monitor のフレームが失敗し、それが Work の失敗としてルートまで上がる。

    python examples/pipeline_monitor.py --jobs 200 --workers 4
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import cast

import gpframe

import fport
from fport.gpframe import tap

port = fport.Port()
"""ワーカーが結果を送る口。

- `("done", worker, job, elapsed)`: 仕事を終えた。`elapsed` は秒
- `("failed", worker, job, reason)`: 仕事に失敗した
"""


# ---------------------------------------------------------------- 仕事をする側


def handle(job: int) -> int:
    """一つの仕事。7 の倍数は失敗する(失敗の扱いを見せるため)。"""
    if job % 7 == 0:
        raise ValueError(f"job {job} is unlucky")
    return sum(i * i for i in range(job * 100))


def worker(ctx: gpframe.Context, jobs: gpframe.Channel[int]) -> None:
    for job in jobs.receive(ctx):
        started = time.perf_counter()
        try:
            _ = handle(job)
        except ValueError as exc:
            port.send("failed", ctx.name, job, str(exc))
        else:
            port.send("done", ctx.name, job, time.perf_counter() - started)


def produce(ctx: gpframe.Context, jobs: gpframe.Channel[int], count: int) -> None:
    try:
        for job in range(1, count + 1):
            if not jobs.put(job, ctx):
                return
    finally:
        jobs.close()


# ---------------------------------------------------------------- 監視する側


@dataclass(frozen=True)
class Event:
    """Monitor が events に流す、型の付いた 1 件。"""

    tag: str
    worker: str
    job: int
    elapsed: float = 0.0
    reason: str = ""


def to_event(tag: str, /, *args: object) -> Event:
    """`port.send()` の引数を `Event` にする。想定外のものは受け取らない。"""
    match (tag, *args):
        case ("done", str(name), int(job), float(elapsed)):
            return Event(tag, name, job, elapsed=elapsed)
        case ("failed", str(name), int(job), str(reason)):
            return Event(tag, name, job, reason=reason)
        case _:
            raise ValueError(f"unexpected message: {(tag, *args)!r}")


def monitor(ctx: gpframe.Context, events: gpframe.Channel[Event]) -> None:
    tap(ctx, port, events, convert=to_event)


@dataclass
class Summary:
    done: Counter[str] = field(default_factory=Counter)
    failed: list[int] = field(default_factory=list)
    slowest: float = 0.0

    @property
    def total(self) -> int:
        return sum(self.done.values()) + len(self.failed)


def aggregate(ctx: gpframe.Context, events: gpframe.Channel[Event]) -> Summary:
    summary = Summary()
    for event in events.receive(ctx):
        if event.tag == "done":
            summary.done[event.worker] += 1
            summary.slowest = max(summary.slowest, event.elapsed)
        else:
            summary.failed.append(event.job)
    summary.failed.sort()
    return summary


# ---------------------------------------------------------------- 全体


def work(
    ctx: gpframe.Context, events: gpframe.Channel[Event], count: int, workers: int
) -> None:
    jobs = gpframe.Channel(int, maxsize=16)
    with ctx.session(timeout=5) as s:
        watching = s.spawn(monitor, events, name="Monitor")
        # 接続される前の send() は届かないので、つながってから仕事を始める。
        while not port.connected and watching.running:
            _ = watching.wait(0.01)
        _ = s.spawn(produce, jobs, count, name="Produce")
        crew = [
            s.spawn(worker, jobs, name=f"Worker-{n}") for n in range(1, workers + 1)
        ]
        for frame in crew:
            _ = frame.wait()
        s.stop()  # Monitor を止める。Monitor は接続を外し、events を閉じる
        for frame in s.broken():
            frame.escalate()


def run(count: int, workers: int) -> Summary:
    events = gpframe.Channel(Event)
    with gpframe.session(timeout=10) as s:
        totals = s.spawn(aggregate, events, name="Aggregate")
        _ = s.spawn(work, events, count, workers, name="Work")
        for frame in s.wait_broken():
            frame.escalate()
        s.stop()
    return totals.result()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ワーカーの仕事ぶりを監視する。")
    _ = parser.add_argument("--jobs", type=int, default=200)
    _ = parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    summary = run(cast("int", args.jobs), cast("int", args.workers))

    per_worker = ", ".join(f"{name}: {n}" for name, n in sorted(summary.done.items()))
    print(f"done: {sum(summary.done.values())} ({per_worker})")
    shown = ", ".join(map(str, summary.failed[:5]))
    more = ", ..." if len(summary.failed) > 5 else ""
    print(f"failed: {len(summary.failed)} (jobs {shown}{more})")
    print(f"slowest: {summary.slowest * 1000:.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
