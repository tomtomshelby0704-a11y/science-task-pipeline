#!/usr/bin/env python3
"""把一道达标题打成交付压缩包（规范见 skills/tb-run/delivery.md）。

入口：  python3 skills/tb-run/scripts/pack_delivery.py <题目录> --candidate N --version N --machine <机器名> \
            --use <本机运行目录名>=<判定> [--use ...] [--out <输出目录>]
环境：  Python 3.9+，只用标准库；在执行机上运行（要读本机题包与 harbor 原生输出）。
输入：  <题目录> = {{WORKDIR}}/tasks/<题号>，其下 候选<N>/ 里要有：
          package/<task_id>/        要求书 2.1 的题包（只能有一个 task_id）
          evidence/calibration.md   校准记录
          runs/<本机运行目录名>/     每次 harbor run 的原生输出 + metadata.json + summary.md
        --use 指定入包的“判定用”运行及其判定，判定取 A/B/C/D 组合，用 + 连接：
          A 强模型组成功  B 弱模型组失败（可选，2026-10-29 起不再要求）  C GPT 5.6 Sol (max) 四次之一  D 成功轨迹深度 ≥ 60 步
          N 近达标档：成功且 50–59 步（没有 D 时用；包名自动加 -d50，与达标档分开）
输出：  <输出目录>/<题号>-<task_id>-v<N>[-d50].zip（默认输出目录为 <题目录>/delivery/），同名展开目录留作核对；
        同名 zip 已存在时拒绝打包（退出码 1），不覆盖：先按 tb-run“达标版本保护”把旧包移走；
        打印 zip 路径与 SHA-256。打包前按 check_delivery.py 的同一套规则校验，不通过则不生成 zip，退出码 1。
示例：  python3 skills/tb-run/scripts/pack_delivery.py D:/tbs-work/win-a/tasks/tbs-003 --candidate 1 --version 2 \
            --machine win-a --use 1-gpt56-1=A+C --use 1-gpt56-2=C --use 1-gpt56-4=C \
            --use 1-gpt56-5=C+D
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_delivery as rules  # noqa: E402

TEMPLATE = HERE.parent / "templates" / "delivery-readme.md"
ROLE_NAMES = {"A": "条件 A", "B": "条件 B", "C": "条件 C", "D": "深度", "N": "近达标深度"}


def parse_use(values):
    uses = []
    for v in values:
        local, sep, roles = v.partition("=")
        roles = "+".join(sorted(set(roles.replace(",", "+").split("+")) - {""}))
        if not sep or not local or not roles:
            sys.exit(f"--use 格式应为 <本机运行目录名>=<判定>，实际 {v!r}")
        uses.append((local, roles))
    return uses


def run_id_of(local: str, candidate: int) -> str:
    prefix = f"{candidate}-"
    return local[len(prefix):] if local.startswith(prefix) else local


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def build_readme(topic, task_id, version, machine, rows, omitted, cand_dir, name, tier):
    c = [r for r in rows if "C" in r["roles"].split("+")]
    c_pass = sum(1 for r in c if r["reward"] == "1.0")
    deepest = max((r for r in rows if r["reward"] == "1.0"),
                  key=lambda r: int(r["agent_steps"] or 0), default=None)
    run_table = md_table(
        ["运行", "分组", "模型", "agent", "步数", "reward", "用时（秒）", "判定", "摘要"],
        [[r["run_id"], r["group"], r["model_id"], f'{r["agent"]} {r["agent_version"]}',
          r["agent_steps"], r["reward"], r["duration_sec"],
          "、".join(ROLE_NAMES[x] for x in r["roles"].split("+")),
          f'[summary](runs/{r["run_id"]}/summary.md)'] for r in rows])
    cond = md_table(["条件", "结果", "依据运行"], [
        ["A 强模型组成功", "满足", "、".join(r["run_id"] for r in rows if "A" in r["roles"])],
        (["B 弱模型组失败", "满足", "、".join(r["run_id"] for r in rows if "B" in r["roles"])]
         if any("B" in r["roles"] for r in rows) else ["B 弱模型组失败", "不要求（2026-10-29 起）", "—"]),
        ["C GPT 5.6 Sol (max) 通过数 ≤ 2/4", f"{c_pass}/4", "、".join(r["run_id"] for r in c)],
        ([f"成功轨迹深度（至少一条 ≥ {rules.MIN_DEPTH} 步）",
          f'{deepest["agent_steps"]} 步' if deepest else "—",
          "、".join(r["run_id"] for r in rows if "D" in r["roles"])] if tier == "60" else
         [f"成功轨迹深度：近达标档（{rules.MIN_NEAR_DEPTH}–{rules.MIN_DEPTH - 1} 步，标准仍为 ≥ {rules.MIN_DEPTH}）",
          f'{deepest["agent_steps"]} 步' if deepest else "—",
          "、".join(r["run_id"] for r in rows if "N" in r["roles"])]),
    ])
    omitted_text = (md_table(["本机运行目录", "说明"], [[o, "见 runs/calibration.md 全部运行表"] for o in omitted])
                    if omitted else "无。")
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, value in {
        "{{PACKAGE}}": name,
        "{{TOPIC_ID}}": topic,
        "{{TASK_ID}}": task_id,
        "{{VERSION}}": str(version),
        "{{MACHINE}}": machine,
        "{{RUN_TABLE}}": run_table,
        "{{CONDITIONS}}": cond,
        "{{N_OMITTED}}": str(len(omitted)),
        "{{OMITTED}}": omitted_text,
        "{{LOCAL_RUNS}}": str((cand_dir / "runs").resolve()),
    }.items():
        text = text.replace(key, value)
    return text


def write_zip(src: pathlib.Path, zip_path: pathlib.Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, f"{src.name}/{p.relative_to(src).as_posix()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("topic_dir", type=pathlib.Path)
    ap.add_argument("--candidate", type=int, required=True)
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--machine", required=True)
    ap.add_argument("--use", action="append", default=[], required=True)
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args()

    topic = a.topic_dir.resolve().name
    cand = a.topic_dir / f"候选{a.candidate}"
    tasks = sorted(p for p in (cand / "package").iterdir() if p.is_dir()) if (cand / "package").is_dir() else []
    if len(tasks) != 1:
        sys.exit(f"{cand / 'package'} 下应只有一个 task_id 目录，实际 {[p.name for p in tasks]}")
    task_id = tasks[0].name
    uses = parse_use(a.use)
    all_roles = [set(r.split("+")) for _, r in uses]
    tier = "50" if any("N" in s for s in all_roles) and not any("D" in s for s in all_roles) else "60"
    name = f"{topic}-{task_id}-v{a.version}" + ("-d50" if tier == "50" else "")
    out = (a.out or a.topic_dir / "delivery").resolve()
    stage = out / name
    zip_path = out / f"{name}.zip"
    if zip_path.exists():
        print(f"FAIL {zip_path} 已存在，拒绝覆盖。按 tb-run“达标版本保护”先把旧包移到 delivery/superseded/<时间>/，再重打")
        return 1
    if stage.exists():
        shutil.rmtree(stage)  # 没有同名 zip 时，展开目录只是上次失败留下的草稿
    (stage / "runs").mkdir(parents=True)

    shutil.copytree(tasks[0], stage / "task" / task_id)
    shutil.copy2(cand / "evidence" / "calibration.md", stage / "runs" / "calibration.md")

    used_local = {u for u, _ in uses}
    rows = []
    for local, roles in uses:
        src = cand / "runs" / local
        if not (src / "metadata.json").is_file() or not (src / "summary.md").is_file():
            sys.exit(f"{src} 缺 metadata.json 或 summary.md（模板见 skills/tb-run/templates/）")
        meta = json.loads((src / "metadata.json").read_text(encoding="utf-8"))
        rid = run_id_of(local, a.candidate)
        dst = stage / "runs" / rid
        shutil.copytree(src, dst / "harbor", ignore=shutil.ignore_patterns("metadata.json", "summary.md"))
        shutil.copy2(src / "metadata.json", dst / "metadata.json")
        shutil.copy2(src / "summary.md", dst / "summary.md")
        traj = rules.find_first(dst / "harbor", "trajectory.json")
        steps = rules.agent_steps(traj) if traj else None
        reward = rules.verifier_reward(dst / "harbor")
        rows.append({
            "run_id": rid, "local_run": local, "task_version": str(meta.get("task_version", "")),
            "group": meta.get("group", ""), "model_id": meta.get("model_id", ""),
            "agent": meta.get("agent_framework", ""), "agent_version": meta.get("agent_version", ""),
            "started_at": meta.get("started_at", ""), "duration_sec": meta.get("duration_sec", ""),
            "exit_status": meta.get("exit_status", ""),
            "agent_steps": "" if steps is None else str(steps),
            "reward": "" if reward is None else str(float(reward)),
            "valid": "true" if meta.get("valid") is True else "false", "roles": roles,
        })
    with (stage / "runs" / "index.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rules.INDEX_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    omitted = sorted(p.name for p in (cand / "runs").iterdir() if p.is_dir() and p.name not in used_local)
    (stage / "README.md").write_text(
        build_readme(topic, task_id, a.version, a.machine, rows, omitted, cand, name, tier), encoding="utf-8")

    files = {p.relative_to(stage).as_posix(): rules.sha256(p) for p in sorted(stage.rglob("*")) if p.is_file()}
    manifest = {
        "topic_id": topic, "task_id": task_id, "version": a.version, "machine": a.machine, "depth_tier": tier,
        "packed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "files": files,
    }
    (stage / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    problems = rules.check_root(stage)
    if problems:
        for p in problems:
            print(f"FAIL {p}")
        print(f"未生成 zip；展开目录留在 {stage} 供排查")
        return 1
    write_zip(stage, zip_path)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"ok {zip_path}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
