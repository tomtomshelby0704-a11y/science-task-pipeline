#!/usr/bin/env python3
"""阻塞等待一批 harbor run 结束，期间不打印任何东西（tb-run“省力协议”）。

入口：  python3 skills/tb-run/scripts/wait_runs.py <运行目录>... --max-wait <秒> [--stall-min 30] [--poll 60]
        python3 skills/tb-run/scripts/wait_runs.py --probe <秒>
环境：  Python 3.9+，只用标准库；在执行机上运行（读本机 harbor 运行目录）。
输入：  <运行目录> = harbor 的 job 目录，即 tasks/<题号>/候选<N>/runs/<候选号>-<模型>-<序号>/。
        结束的判据：目录下 result.json 有 finished_at，且没有在跑或排队的 trial。
输出：  返回时每个运行一行，最后一行汇总：
          <运行> done reward=<r> steps=<agent 步数> dur=<秒>
          <运行> running elapsed=<秒>
          <运行> stalled idle=<分钟>       （目录里最新文件超过 --stall-min 分钟没变，运行还没结束）
          <运行> not-started               （等到返回时目录仍不存在）
        步数与 reward 的口径同 check_delivery.py（agent 步数、reward.txt 优先）。
退出码：0 = 全部结束；3 = 到 --max-wait 仍有在跑的；4 = 有卡住或目录不存在；2 = 用法错误。
        --probe 只静默等待指定秒数后打印 "probe ok <秒>"，用来测本机一条命令最多能阻塞多久。
示例：  python3 skills/tb-run/scripts/wait_runs.py D:/tbs-work/win-a/tasks/tbs-003/候选1/runs/1-gpt56-1 \\
            D:/tbs-work/win-a/tasks/tbs-003/候选1/runs/1-gpt56-2 --max-wait 1800
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_delivery as rules  # noqa: E402


def _parse_time(value):
    if not value:
        return None
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _job_result(run_dir: pathlib.Path):
    path = run_dir / "result.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # harbor 正在写，下一轮再读


def _newest_mtime(run_dir: pathlib.Path) -> float:
    newest = run_dir.stat().st_mtime
    for p in run_dir.rglob("*"):
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            pass
    return newest


def status(run_dir: pathlib.Path, stall_min: float, now: float) -> tuple:
    """返回 (状态, 一行说明)，状态取 done / running / stalled / not-started。"""
    name = run_dir.name
    if not run_dir.is_dir():
        return "not-started", f"{name} not-started"
    res = _job_result(run_dir)
    stats = (res or {}).get("stats", {}) if isinstance(res, dict) else {}
    finished = isinstance(res, dict) and res.get("finished_at") and \
        not stats.get("n_running_trials") and not stats.get("n_pending_trials")
    if finished:
        start, end = _parse_time(res.get("started_at")), _parse_time(res.get("finished_at"))
        dur = f"{(end - start).total_seconds():.0f}" if start and end else "?"
        traj = rules.find_first(run_dir, "trajectory.json")
        steps = rules.agent_steps(traj) if traj else None
        reward = rules.verifier_reward(run_dir)
        return "done", f"{name} done reward={reward} steps={steps} dur={dur}"
    idle_min = (now - _newest_mtime(run_dir)) / 60
    if idle_min > stall_min:
        return "stalled", f"{name} stalled idle={idle_min:.0f}"
    start = _parse_time((res or {}).get("started_at")) if isinstance(res, dict) else None
    elapsed = (dt.datetime.now(dt.timezone.utc) - start).total_seconds() if start else now - run_dir.stat().st_ctime
    return "running", f"{name} running elapsed={elapsed:.0f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="*", type=pathlib.Path)
    ap.add_argument("--max-wait", type=float, help="最多阻塞多少秒（取本机 MAX_BLOCK_SEC）")
    ap.add_argument("--stall-min", type=float, default=30, help="多少分钟没有文件变化算卡住（默认 30）")
    ap.add_argument("--poll", type=float, default=60, help="内部检查间隔秒数（默认 60）")
    ap.add_argument("--probe", type=float, help="只静默等待这么多秒，测本机阻塞上限")
    a = ap.parse_args(argv)

    if a.probe is not None:
        time.sleep(a.probe)
        print(f"probe ok {a.probe:g}")
        return 0
    if not a.runs or a.max_wait is None:
        ap.print_usage()
        return 2

    deadline = time.time() + a.max_wait
    while True:
        now = time.time()
        results = [status(r, a.stall_min, now) for r in a.runs]
        states = [s for s, _ in results]
        if all(s == "done" for s in states) or "stalled" in states or now >= deadline:
            break
        time.sleep(max(1.0, min(a.poll, deadline - now)))

    for _, line in results:
        print(line)
    counts = {s: states.count(s) for s in ("done", "running", "stalled", "not-started") if states.count(s)}
    print("summary " + " ".join(f"{k}={v}" for k, v in counts.items()))
    if "stalled" in states or "not-started" in states:
        return 4
    return 0 if all(s == "done" for s in states) else 3


if __name__ == "__main__":
    sys.exit(main())
