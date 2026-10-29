#!/usr/bin/env python3
"""交付压缩包自检（规范见 skills/tb-run/delivery.md）。

入口：  python3 skills/tb-run/scripts/check_delivery.py <题号>-<task_id>-v<N>[-d50].zip
环境：  Python 3.9+，只用标准库（3.11+ 用 tomllib 解析 task.toml，低版本用简易解析）。
输入：  pack_delivery.py 生成的 zip。
输出：  逐项打印 FAIL；全部通过打印 "ok <zip>"，近达标档（最长成功 50–59 步，包名带 -d50）再追加“（深度档 50–59，近达标）”。退出码 0 = 通过，1 = 有问题，2 = 用法错误。
示例：  python3 skills/tb-run/scripts/check_delivery.py D:/tbs-work/win-a/tasks/tbs-003/delivery/tbs-003-detector-deadtime-correction-v2.zip

pack_delivery.py 会 import 本文件的规则函数，打包前先按同一套规则校验，两边口径不会分叉。
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re
import sys
import tempfile
import zipfile

ROOT_RE = re.compile(r"^(tbs-\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)-v(\d+)(-d50)?$")

README_SECTIONS = ("## 1. 目录说明", "## 2. 真实轨迹总结", "## 3. 未入包运行")

# 要求书 2.1「任务交付格式要求」的树。以 / 结尾的是目录。
TASK_TREE = (
    "instruction.md",
    "task.toml",
    "environment/Dockerfile",
    "environment/requirements.txt",
    "environment/resources/",
    "solution/solve.sh",
    "solution/reference_solution.md",
    "solution/solution_explanation.md",
    "tests/test.sh",
    "tests/fixtures/",
)

# 要求书 4.2「来源与数据记录」落到 task.toml [metadata] 的字段名（字段名借自参考样例）。
SOURCE_FIELDS = ("license", "source_repo", "source_commit", "ai_assistance")

# 要求书 3.2「轨迹与运行记录」的运行元数据与评测记录字段。
RUN_FIELDS = (
    "model_id", "group", "tier", "agent_framework", "agent_version",
    "system_prompt", "tools", "sampling", "budget",
    "started_at", "duration_sec", "exit_status",
    "task_version", "verifier_version", "valid", "failure_class",
)

INDEX_COLUMNS = (
    "run_id", "local_run", "task_version", "group", "model_id", "agent",
    "agent_version", "started_at", "duration_sec", "exit_status",
    "agent_steps", "reward", "valid", "roles",
)

ROLES = {"A", "B", "C", "D", "N"}  # A 强模型成功；B 弱模型失败（2026-10-29 起可选，不再要求）；C GPT 5.6 四次；D 成功轨迹深度 ≥ 60；N 近达标档 50–59
MIN_DEPTH = 60
MIN_NEAR_DEPTH = 50
LAST_TIER = None  # check_root 判出的深度档（"60" / "50"），供 main 打印
C_RUNS = 4


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_first(root: pathlib.Path, name: str):
    hits = sorted(p for p in root.rglob(name) if p.is_file())
    return hits[0] if hits else None


def agent_steps(trajectory: pathlib.Path):
    """ATIF trajectory.json 中 steps[source == "agent"] 的条目数（tb-run 第 5 步的步骤计数定义）。"""
    try:
        data = json.loads(trajectory.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list):
        return None
    return sum(1 for s in steps if isinstance(s, dict) and s.get("source") == "agent")


def _find_reward(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "reward" and isinstance(v, (int, float)):
                return float(v)
        for v in obj.values():
            r = _find_reward(v)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_reward(v)
            if r is not None:
                return r
    return None


def verifier_reward(harbor_dir: pathlib.Path):
    """优先读 verifier 写出的 reward.txt，没有再从 result.json 里找 reward 字段。"""
    txt = find_first(harbor_dir, "reward.txt")
    if txt:
        try:
            return float(txt.read_text(encoding="utf-8").strip().split()[0])
        except (OSError, ValueError, IndexError):
            return None
    res = find_first(harbor_dir, "result.json")
    if res:
        try:
            return _find_reward(json.loads(res.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None
    return None


def load_toml_metadata(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(text).get("metadata", {})
    except ModuleNotFoundError:
        meta, section = {}, None
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"^\[([^\]]+)\]$", line)
            if m:
                section = m.group(1).strip()
                continue
            m = re.match(r'^([A-Za-z0-9_]+)\s*=\s*"(.*)"\s*$', line)
            if section == "metadata" and m:
                meta[m.group(1)] = m.group(2)
        return meta


def check_task(task: pathlib.Path) -> list:
    """2.1 的树、4.2 来源字段、2.1 防泄漏。"""
    problems = []
    for rel in TASK_TREE:
        p = task / rel.rstrip("/")
        if rel.endswith("/"):
            if not p.is_dir():
                problems.append(f"题包缺目录 {rel}")
        elif not p.is_file():
            problems.append(f"题包缺文件 {rel}")
    if not any(p.is_file() for p in (task / "tests").glob("verifier.*")):
        problems.append("题包缺文件 tests/verifier.*")
    if problems:
        return problems

    meta = load_toml_metadata(task / "task.toml")
    for key in SOURCE_FIELDS:
        value = str(meta.get(key, "")).strip()
        if not value or "<FILL" in value:
            problems.append(f"task.toml [metadata] 缺 {key}（要求书 4.2 来源与数据记录）")

    hidden = {}
    for sub in ("solution", "tests"):
        for p in (task / sub).rglob("*"):
            if p.is_file() and p.stat().st_size > 0:
                hidden.setdefault(sha256(p), str(p.relative_to(task)))
    for p in (task / "environment").rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(task)
        if p.name in ("solve.sh", "test.sh", "reference_solution.md", "solution_explanation.md"):
            problems.append(f"泄漏：{rel} 是解答或判分文件名")
        twin = hidden.get(sha256(p))
        if twin:
            problems.append(f"泄漏：{rel} 与 {twin} 内容相同")
    dockerfile = (task / "environment" / "Dockerfile").read_text(encoding="utf-8", errors="ignore")
    for line in dockerfile.splitlines():
        if re.match(r"^\s*(COPY|ADD)\b", line, re.I) and re.search(r"(^|[\s/])(solution|tests)(/|\s|$)", line):
            problems.append(f"泄漏：environment/Dockerfile 复制了解答或判分目录：{line.strip()}")
    return problems


def check_roles(rows: list) -> list:
    """入包运行与三项条件、成功轨迹深度是否自洽（要求书 3.2 校准结果要求、成功轨迹深度）。"""
    problems = []
    c_runs, d_ok, n_ok = [], False, False
    for r in rows:
        roles = set(filter(None, r["roles"].split("+")))
        rid = r["run_id"]
        if not roles or not roles <= ROLES:
            problems.append(f"{rid}：roles 必须是 A/B/C/D/N 的组合，实际 {r['roles']!r}")
            continue
        if r["valid"] != "true":
            problems.append(f"{rid}：无效运行不能入包作判定依据")
        reward = float(r["reward"]) if r["reward"] not in ("", "None") else None
        steps = int(r["agent_steps"]) if r["agent_steps"].isdigit() else None
        if "A" in roles and not (r["group"] == "strong" and reward == 1.0):
            problems.append(f"{rid}：A 需要强模型组且 reward = 1")
        if "B" in roles and not (r["group"] == "weak" and reward == 0.0):
            problems.append(f"{rid}：B 需要弱模型组且 reward = 0")
        if "C" in roles:
            if not rid.startswith("gpt56-"):
                problems.append(f"{rid}：C 只能是 GPT 5.6 Sol (max) 的运行（gpt56-*）")
            c_runs.append(reward)
        if "D" in roles:
            if reward == 1.0 and steps is not None and steps >= MIN_DEPTH:
                d_ok = True
            else:
                problems.append(f"{rid}：D 需要 reward = 1 且步数 ≥ {MIN_DEPTH}，实际 reward={reward} 步数={steps}")
        if "N" in roles:
            if reward == 1.0 and steps is not None and MIN_NEAR_DEPTH <= steps < MIN_DEPTH:
                n_ok = True
            else:
                problems.append(f"{rid}：N 需要 reward = 1 且 {MIN_NEAR_DEPTH} ≤ 步数 < {MIN_DEPTH}，实际 reward={reward} 步数={steps}")
    all_roles = [set(r["roles"].split("+")) for r in rows]
    if not any("A" in s for s in all_roles):
        problems.append("缺条件 A 的运行（强模型组成功）")
    # 条件 B（弱模型组失败）2026-10-29 甲方取消：不再要求；旧包带 B 时上面照旧校验其正确性
    if len(c_runs) != C_RUNS:
        problems.append(f"条件 C 需要恰好 {C_RUNS} 次 GPT 5.6 有效运行，实际 {len(c_runs)} 次")
    else:
        passed = sum(1 for x in c_runs if x == 1.0)
        if passed > 2:
            problems.append(f"条件 C 不满足：GPT 5.6 通过 {passed}/4 > 2/4")
        if passed == 0 and not any(r["run_id"].startswith("gpt6-") and "A" in r["roles"] for r in rows):
            problems.append("GPT 5.6 为 0/4，需要一条 GPT-6 Astra 成功运行（gpt6-*，roles 含 A）")
    if d_ok and any("N" in s for s in all_roles):
        problems.append(f"D 与 N 不能同时出现：已有 ≥ {MIN_DEPTH} 步的成功轨迹，按达标档打包，不标 N")
    if not d_ok and not n_ok:
        problems.append(f"缺成功轨迹深度证据：至少一条成功轨迹 ≥ {MIN_DEPTH} 步（roles 含 D），"
                        f"或近达标档一条 {MIN_NEAR_DEPTH}–{MIN_DEPTH - 1} 步（roles 含 N）")
    return problems


def depth_tier(runs: pathlib.Path):
    """按 index.csv 的角色判深度档：有 D 为 "60"，只有 N 为 "50"，都没有为 None。"""
    index = runs / "index.csv"
    if not index.is_file():
        return None
    with index.open(encoding="utf-8", newline="") as f:
        roles = [set(filter(None, r.get("roles", "").split("+"))) for r in csv.DictReader(f)]
    if any("D" in s for s in roles):
        return "60"
    if any("N" in s for s in roles):
        return "50"
    return None


def check_runs(runs: pathlib.Path, task_version: str) -> list:
    problems = []
    if not (runs / "calibration.md").is_file():
        problems.append("缺 runs/calibration.md")
    index = runs / "index.csv"
    if not index.is_file():
        return problems + ["缺 runs/index.csv"]
    with index.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != INDEX_COLUMNS:
            return problems + [f"index.csv 列名应为 {','.join(INDEX_COLUMNS)}"]
        rows = list(reader)
    if not rows:
        return problems + ["index.csv 没有运行"]
    listed = {r["run_id"] for r in rows}
    on_disk = {p.name for p in runs.iterdir() if p.is_dir()}
    for extra in sorted(on_disk - listed):
        problems.append(f"runs/{extra}/ 不在 index.csv 里")
    for r in rows:
        rid = r["run_id"]
        d = runs / rid
        if not d.is_dir():
            problems.append(f"index.csv 列了 {rid}，但没有 runs/{rid}/")
            continue
        if r["task_version"] != task_version:
            problems.append(f"{rid}：任务版本 v{r['task_version']} 与包版本 v{task_version} 不一致")
        for name in ("metadata.json", "summary.md"):
            if not (d / name).is_file():
                problems.append(f"{rid}：缺 {name}")
        if (d / "metadata.json").is_file():
            try:
                meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
            except ValueError:
                meta = None
                problems.append(f"{rid}：metadata.json 不是合法 JSON")
            if isinstance(meta, dict):
                for key in RUN_FIELDS:
                    if key not in meta or meta[key] in (None, ""):
                        problems.append(f"{rid}：metadata.json 缺 {key}（要求书 3.2 轨迹与运行记录）")
        harbor = d / "harbor"
        for secret in ("auth.json", ".env"):
            if harbor.is_dir() and any(harbor.rglob(secret)):
                problems.append(f"{rid}：harbor/ 里有 {secret}，交付包不能带密钥")
        traj = find_first(harbor, "trajectory.json") if harbor.is_dir() else None
        if not traj:
            problems.append(f"{rid}：harbor/ 下没有 trajectory.json（完整轨迹）")
            continue
        steps, reward = agent_steps(traj), verifier_reward(harbor)
        if steps is None:
            problems.append(f"{rid}：trajectory.json 读不出 steps")
        elif str(steps) != r["agent_steps"]:
            problems.append(f"{rid}：index.csv 步数 {r['agent_steps']} 与轨迹实数 {steps} 不符")
        if reward is None:
            problems.append(f"{rid}：harbor/ 下找不到验证器 reward（reward.txt 或 result.json）")
        elif r["reward"] in ("", "None") or float(r["reward"]) != reward:
            problems.append(f"{rid}：index.csv reward {r['reward']} 与验证器 {reward} 不符")
    return problems + check_roles(rows)


def check_manifest(root: pathlib.Path) -> list:
    path = root / "MANIFEST.json"
    if not path.is_file():
        return ["缺 MANIFEST.json"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return ["MANIFEST.json 不是合法 JSON"]
    problems = []
    for key in ("topic_id", "task_id", "version", "machine", "packed_at", "files"):
        if key not in manifest:
            problems.append(f"MANIFEST.json 缺 {key}")
    files = manifest.get("files", {})
    actual = {str(p.relative_to(root)).replace("\\", "/"): p
              for p in root.rglob("*") if p.is_file() and p != path}
    for rel in sorted(set(actual) - set(files)):
        problems.append(f"MANIFEST.json 未登记 {rel}")
    for rel in sorted(set(files) - set(actual)):
        problems.append(f"MANIFEST.json 登记的 {rel} 不存在")
    for rel in sorted(set(files) & set(actual)):
        if sha256(actual[rel]) != files[rel]:
            problems.append(f"哈希不符：{rel}")
    return problems


def check_root(root: pathlib.Path) -> list:
    m = ROOT_RE.match(root.name)
    if not m:
        return [f"根目录名 {root.name!r} 不符合 <题号>-<task_id>-v<N>[-d50]"]
    global LAST_TIER
    topic, task_id, version, suffix = m.groups()
    problems = []
    tier = depth_tier(root / "runs")
    LAST_TIER = tier
    name_tier = "50" if suffix else "60"
    if tier and tier != name_tier:
        problems.append(f"深度档与包名不符：判定为 {tier} 档，包名{'带' if suffix else '不带'} -d50"
                        f"（近达标档 50–59 必须带 -d50，达标档 ≥ 60 不带）")
    mpath = root / "MANIFEST.json"
    if mpath.is_file():
        try:
            declared = json.loads(mpath.read_text(encoding="utf-8")).get("depth_tier")
        except ValueError:
            declared = None
        if suffix and declared != "50":
            problems.append(f"MANIFEST.json 的 depth_tier 应为 \"50\"，实际 {declared!r}")
        if declared is not None and declared != name_tier:
            problems.append(f"MANIFEST.json 的 depth_tier {declared!r} 与包名档位 {name_tier!r} 不符")
    readme = root / "README.md"
    if not readme.is_file():
        problems.append("缺 README.md")
    else:
        text = readme.read_text(encoding="utf-8")
        for h in README_SECTIONS:
            if h not in text:
                problems.append(f"README.md 缺小节 {h!r}")
    tops = sorted(p.name for p in root.iterdir())
    if tops != ["MANIFEST.json", "README.md", "runs", "task"]:
        problems.append(f"根目录应只有 README.md、MANIFEST.json、task/、runs/，实际 {tops}")
    tasks = sorted(p.name for p in (root / "task").iterdir()) if (root / "task").is_dir() else []
    if tasks != [task_id]:
        problems.append(f"task/ 下应只有 {task_id}/，实际 {tasks}")
    else:
        problems += check_task(root / "task" / task_id)
    if (root / "runs").is_dir():
        problems += check_runs(root / "runs", version)
    problems += check_manifest(root)
    return problems


def check_zip(zip_path: pathlib.Path) -> list:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            bad = [n for n in names if n.startswith("/") or ".." in pathlib.PurePosixPath(n).parts]
            if bad:
                return [f"zip 内有非法路径：{bad[:3]}"]
            tops = {n.split("/")[0] for n in names}
            if len(tops) != 1:
                return [f"zip 内应只有一个根目录，实际 {sorted(tops)}"]
            zf.extractall(tmp)
        root = pathlib.Path(tmp) / tops.pop()
        if root.name + ".zip" != zip_path.name:
            return [f"zip 文件名应为 {root.name}.zip"]
        return check_root(root)


def main(argv) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    zip_path = pathlib.Path(argv[0])
    problems = check_zip(zip_path)
    for p in problems:
        print(f"FAIL {p}")
    if problems:
        return 1
    print(f"ok {zip_path}" + ("（深度档 50–59，近达标）" if LAST_TIER == "50" else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
