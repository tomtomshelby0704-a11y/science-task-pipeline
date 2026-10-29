#!/usr/bin/env python3
"""Build flows/tb-science/board.md from repository files.

Entry:   python3 skills/tb-board/scripts/build_board.py   (run from repo root)
Env:     python3 >= 3.9, standard library only.
Inputs:  flows/tb-science/topics/*.md, topics/queue.md, ledger/tasks.md,
         ledger/reviews.md, runs/<id>/calibration.md, runs/scores.md, claims/*.md
Output:  flows/tb-science/board.md (overwritten; derived file, never hand-edited)
"""
import datetime
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
FLOW = ROOT / "flows" / "tb-science"
TOPICS = FLOW / "topics"
MATERIALS = FLOW / "materials"
BOOT = FLOW / "boot"
RUNS = FLOW / "runs"
LEDGER = FLOW / "ledger"
REVIEWS = FLOW / "reviews"

STATUS_ORDER = ["待登记", "待执行", "改写中", "退回出题", "执行中", "阻塞", "已执行-达标", "已执行-近达标", "已执行-不达标", "已撤回"]
DRAFTS = FLOW / "drafts"
CLAIMS = FLOW / "claims"
CLAIM_LEASE_H = 2


def table_rows(path, key_prefix="tbs-"):
    """Return list of cell-lists for table rows whose first cell starts with key_prefix."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].startswith(key_prefix):
            rows.append(cells)
    return rows


def header_field(text, name):
    m = re.search(r"^- \*\*" + re.escape(name) + r"\*\*：(.*)$", text, re.M)
    return m.group(1).strip() if m else ""


def last_header_field(text, name):
    hits = re.findall(r"^- \*\*" + re.escape(name) + r"\*\*：(.*)$", text, re.M)
    return hits[-1].strip() if hits else ""


def prescreen_cell(value):
    """Short label for the latest `预筛` header line: 弱模型失败 / 弱模型解出 / 无效 / empty."""
    for k in ("弱模型失败", "弱模型解出", "无效"):
        if value.startswith(k):
            return k
    return value[:12]


def adversarial_cell(value):
    """Short label for the latest `对抗清单` header line: `v1` / `v1（回补）` / `v2` …; empty if the topic
    was written before the adversarial flow (2026-10-29)."""
    m = re.match(r"(v\d+(?:（[^）]*）)?)", value)
    return m.group(1) if m else (value[:10] if value else "")


def parse_claims(now):
    claims = []
    for p in sorted(CLAIMS.glob("*.md")) if CLAIMS.exists() else []:
        if p.name == "README.md":
            continue
        text = p.read_text(encoding="utf-8")
        beat = header_field(text, "心跳")
        expired = "?"
        try:
            ts = datetime.datetime.fromisoformat(beat.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            expired = "已过期" if (now - ts).total_seconds() > CLAIM_LEASE_H * 3600 else "有效"
        except ValueError:
            pass
        claims.append({"file": p.name, "kind": header_field(text, "类型"), "obj": header_field(text, "对象"),
                       "owner": header_field(text, "占用者"), "beat": beat, "state": expired})
    return claims


def parse_topics():
    topics = {}
    for p in sorted(TOPICS.glob("tbs-*.md")):
        if p.name.endswith("-prompt.md"):
            continue
        tid = p.stem
        text = p.read_text(encoding="utf-8")
        status = header_field(text, "状态") or "待登记"
        source = header_field(text, "来源对话")
        start = header_field(text, "起始候选")
        start = re.match(r"\d+", start).group(0) if re.match(r"\d+", start) else "1"
        cands = []
        for m in re.finditer(r"^## 候选 (\d+)\n(.*?)(?=^## 候选 |\Z)", text, re.M | re.S):
            body = m.group(2)
            cands.append({
                "n": m.group(1),
                "slug": header_field(body, "题目名").strip("`"),
                "domain": header_field(body, "领域"),
            })
        topics[tid] = {"status": status, "source": source, "start": start, "cands": cands,
                       "prescreen": prescreen_cell(last_header_field(text, "预筛")),
                       "adversarial": adversarial_cell(last_header_field(text, "对抗清单"))}
    # prompt-only topics
    for p in sorted(TOPICS.glob("tbs-*-prompt.md")):
        tid = p.stem[: -len("-prompt")]
        if tid not in topics:
            dom = ""
            m = re.search(r"本次优先领域：(.*)", p.read_text(encoding="utf-8"))
            if m:
                dom = m.group(1).strip()
            topics[tid] = {"status": "已发出提示词，待回复", "source": "GPT Pro（提示词已发出）",
                           "start": "1", "cands": [{"n": "-", "slug": "", "domain": dom}], "prescreen": ""}
    return topics


def parse_materials():
    mats = {}
    for p in sorted(MATERIALS.glob("mat-*.md")) if MATERIALS.exists() else []:
        if p.name.endswith("-prompt.md"):
            continue
        text = p.read_text(encoding="utf-8")
        slugs = [m.group(1).strip("`") for m in re.finditer(r"^- \*\*题目名\*\*：(.*)$", text, re.M)]
        n_cand = len(re.findall(r"^## 候选 \d+", text, re.M))
        # latest verdict per candidate: lines like "  - 候选 3：成题 tbs-011" / "  - 候选 3：否决——..." (later sections override earlier)
        verdict = {}
        for m in re.finditer(r"^\s*- 候选 (\d+)：(成题|否决)", text, re.M):
            verdict[m.group(1)] = m.group(2)
        status = header_field(text, "状态") or "待登记"
        n_ok = sum(1 for v in verdict.values() if v == "成题")
        # a material back in 待加工 (复审) keeps old verdicts as history only: everything not yet 成题 is open again
        n_rej = 0 if status.startswith("待加工") else sum(1 for v in verdict.values() if v == "否决")
        mats[p.stem] = {"status": status, "slugs": slugs,
                        "n_cand": n_cand, "n_ok": n_ok, "n_rej": n_rej, "n_open": max(n_cand - n_ok - n_rej, 0)}
    for p in sorted(MATERIALS.glob("mat-*-prompt.md")) if MATERIALS.exists() else []:
        mid = p.stem[: -len("-prompt")]
        if mid not in mats:
            mats[mid] = {"status": "已发出提示词，待回复", "slugs": []}
    return mats


def parse_workers(topics, tasks_rows, review_rows):
    """Registered machines (boot/registry.md + boot/<name>.md) with per-machine counts."""
    reg = {r[0].strip("`"): r for r in table_rows(BOOT / "registry.md", key_prefix="")
           if r and r[0] and r[0] not in ("机器名", "---") and not r[0].startswith("-")}
    names = set(reg)
    if BOOT.exists():
        for p in BOOT.glob("*.md"):
            if p.name not in ("README.md", "registry.md", "cloud-research.md") and not p.stem.endswith("-environment"):
                names.add(p.stem)
    # topic -> machine from the latest ledger-1 row
    topic_machine = {}
    for r in tasks_rows:
        if len(r) > 3:
            topic_machine[r[0].strip("`")] = r[3]
    workers = []
    for name in sorted(names):
        rows = [r for r in tasks_rows if len(r) > 3 and r[3] == name]
        passed = sum(1 for r in rows if len(r) > 5 and r[5].startswith("达标"))
        near = sum(1 for r in rows if len(r) > 5 and r[5].startswith("近达标"))
        rv_ok = sum(1 for r in review_rows if len(r) > 1 and r[1].startswith("通过")
                    and topic_machine.get(r[0].strip("`")) == name)
        running = [t for t, v in topics.items() if v["status"].startswith("执行中") and name in v["status"]]
        blocked = [t for t, v in topics.items() if v["status"].startswith("阻塞") and name in v["status"]]
        last = rows[-1][7] if rows and len(rows[-1]) > 7 else ""
        r = reg.get(name)
        workers.append({
            "name": name,
            "registered": "已就绪" if r else "有启动 prompt，未登记就绪",
            "system": r[1] if r and len(r) > 1 else "",
            "ready_at": r[5] if r and len(r) > 5 else "",
            "weak": r[4] if r and len(r) > 4 else "",
            "running": running, "blocked": blocked,
            "runs": len(rows), "passed": passed, "near": near, "rv_ok": rv_ok, "last": last,
        })
    return workers


def status_bucket(status):
    for s in STATUS_ORDER:
        if status.startswith(s):
            return s
    return "其他"


def source_family(source):
    """Which production line a topic came from: 快速出题 / 改难 / 研究出题 / 其他."""
    if "快速出题" in source:
        return "快速出题"
    if "改难自" in source:
        return "改难"
    if "素材" in source or "Claude" in source:
        return "研究出题"
    return "其他"


def source_kind(source):
    if "快速出题" in source:
        m = re.search(r"(mat-\d+)", source)
        return f"快速出题（素材 {m.group(1) if m else '?'}）"
    if "改难自" in source:
        m = re.search(r"改难自 (tbs-\d+(?: 候选 \d+)?)", source)
        return "改难自 " + (m.group(1) if m else "?")
    if "素材" in source:
        m = re.search(r"(mat-\d+)", source)
        return f"GPT Pro 素材 {m.group(1) if m else '?'} → Claude 加工"
    if "Claude" in source:
        return "Claude 研究"
    if "GPT Pro" in source:
        return "GPT Pro"
    return source or "未知"


def parse_calibration(tid):
    p = RUNS / tid / "calibration.md"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    cond = {}
    sec = re.search(r"^## 三项条件判定\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if sec:
        for line in sec.group(1).splitlines():
            if line.startswith("|") and not line.startswith("| ---") and not line.startswith("| 条件"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 2:
                    key = cells[0][:1]
                    cond[key] = cells[1]
    concl = ""
    sec = re.search(r"^## 结论\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if sec:
        lines = [l.strip() for l in sec.group(1).splitlines() if l.strip()]
        concl = lines[0] if lines else ""
    n_runs = len([q for q in (RUNS / tid).glob("*.md") if q.name != "calibration.md"])
    return {"cond": cond, "concl": concl, "n_runs": n_runs}


def latest_review(tid):
    rows = [r for r in table_rows(LEDGER / "reviews.md") if r[0].strip("`") == tid]
    return rows[-1] if rows else None


def md_link(label, rel):
    return f"[{label}]({rel})"


def main():
    topics = parse_topics()
    tasks = {r[0].strip("`"): r for r in table_rows(LEDGER / "tasks.md")}
    queue = table_rows(TOPICS / "queue.md", key_prefix="")
    queue = [r for r in queue if len(r) >= 2 and r[1].startswith("tbs-")]
    scores = table_rows(RUNS / "scores.md")
    mats = parse_materials()
    tasks_rows = table_rows(LEDGER / "tasks.md")
    mat_counts = {"待加工": 0, "已加工": 0, "已否决": 0, "其他": 0}
    for m in mats.values():
        for k in ("待加工", "已加工", "已否决"):
            if m["status"].startswith(k):
                mat_counts[k] += 1
                break
        else:
            mat_counts["其他"] += 1

    counts = {s: 0 for s in STATUS_ORDER}
    counts["其他"] = 0
    running = []
    for tid, t in topics.items():
        b = status_bucket(t["status"])
        counts[b] = counts.get(b, 0) + 1
        if b == "执行中":
            m = re.search(r"执行中[（(](.*?)[）)]", t["status"])
            running.append(f"{tid}@{m.group(1) if m else '?'}")
    review_rows = table_rows(LEDGER / "reviews.md")
    rv_pass = sum(1 for r in review_rows if len(r) > 1 and r[1].startswith("通过"))
    rv_back = sum(1 for r in review_rows if len(r) > 1 and r[1].startswith("退回"))
    rv_block = sum(1 for r in review_rows if len(r) > 1 and r[1].startswith("阻塞"))

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now = now_dt.strftime("%Y-%m-%d %H:%M UTC")
    out = []
    out.append("# TB-Science 结果看板\n")
    out.append(f"> 由 `skills/tb-board/scripts/build_board.py` 从 `topics/`、`ledger/`、`runs/` 生成，勿手改。生成时间 {now}。事实来源仍是 [台账 1](ledger/tasks.md) 与 [台账 2](ledger/reviews.md)。\n")
    out.append("## 总览\n")
    try:
        rv = subprocess.run(["git", "log", "-1", "--format=%h %cs", "--", "specs", "skills", "AGENTS.md", "README.md", "flows/tb-science/README.md", "flows/tb-science/calibration-models.md", "flows/tb-science/adversarial-design.md"], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        rv = ""
    if rv:
        out.append(f"规则最新版本：`{rv.split()[0]}`（{rv.split()[-1]}）。执行机登记回报里的“规则版本”与此一致即已跟上，见 [AGENTS.md 规则同步](../../AGENTS.md#规则同步)。\n")
    out.append("| 选题总数 | 待执行 | 执行中 | 阻塞 | 已执行-达标（≥ 60） | 已执行-近达标（50–59） | 已执行-不达标 | 待登记 / 待回复 | 审查通过 | 审查退回 | 审查阻塞 |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    pending = counts.get("待登记", 0) + counts.get("其他", 0)
    out.append(f"| {len(topics)} | {counts['待执行']} | {counts['执行中']}{'（' + '，'.join(running) + '）' if running else ''} | {counts['阻塞']} | {counts['已执行-达标']} | {counts['已执行-近达标']} | {counts['已执行-不达标']} | {pending} | {rv_pass} | {rv_back} | {rv_block} |\n")

    tot = {k: sum(m.get(k, 0) for m in mats.values()) for k in ("n_cand", "n_ok", "n_rej", "n_open")}
    out.append("| 素材总数 | 待加工 | 已加工 | 已否决 | 待登记 / 待回复 | 候选总数 | 候选成题 | 候选否决 | 候选待判 |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    out.append(f"| {len(mats)} | {mat_counts['待加工']} | {mat_counts['已加工']} | {mat_counts['已否决']} | {mat_counts['其他']} | {tot['n_cand']} | {tot['n_ok']} | {tot['n_rej']} | {tot['n_open']} |\n")

    # per production line: compare yield of 研究出题 vs 快速出题 vs 改难
    fams = {}
    for tp in topics.values():
        f = fams.setdefault(source_family(tp["source"]),
                            {k: 0 for k in ("n", "待执行", "执行中", "已执行-达标", "已执行-近达标", "已执行-不达标")})
        f["n"] += 1
        b = status_bucket(tp["status"])
        if b in f:
            f[b] += 1
    out.append("| 来源链路 | 题数 | 待执行 | 执行中 | 已执行-达标 | 已执行-近达标 | 已执行-不达标 | 达标率（已执行） |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for name in ("研究出题", "快速出题", "改难", "其他"):
        f = fams.get(name)
        if not f:
            continue
        done = f["已执行-达标"] + f["已执行-近达标"] + f["已执行-不达标"]
        rate = f"{f['已执行-达标'] / done:.0%}（{f['已执行-达标']}/{done}）" if done else "-"
        out.append(f"| {name} | {f['n']} | {f['待执行']} | {f['执行中']} | {f['已执行-达标']} | {f['已执行-近达标']} | {f['已执行-不达标']} | {rate} |")
    out.append("")

    # adversarial flow (2026-10-29) vs topics written before it: same yield columns
    advs = {}
    for tp in topics.values():
        key = "对抗题（有对抗清单）" if tp.get("adversarial") else "非对抗题"
        f = advs.setdefault(key, {k: 0 for k in ("n", "待执行", "退回出题", "执行中", "已执行-达标", "已执行-近达标", "已执行-不达标")})
        f["n"] += 1
        b = status_bucket(tp["status"])
        if b in f:
            f[b] += 1
    out.append("| 出题流程 | 题数 | 待执行 | 退回出题 | 执行中 | 已执行-达标 | 已执行-近达标 | 已执行-不达标 | 达标率（已执行） |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for name in ("对抗题（有对抗清单）", "非对抗题"):
        f = advs.get(name)
        if not f:
            continue
        done = f["已执行-达标"] + f["已执行-近达标"] + f["已执行-不达标"]
        rate = f"{f['已执行-达标'] / done:.0%}（{f['已执行-达标']}/{done}）" if done else "-"
        out.append(f"| {name} | {f['n']} | {f['待执行']} | {f['退回出题']} | {f['执行中']} | {f['已执行-达标']} | {f['已执行-近达标']} | {f['已执行-不达标']} | {rate} |")
    out.append("")

    workers = parse_workers(topics, tasks_rows, review_rows)
    out.append("## 执行机（来自 [boot/registry.md](boot/registry.md) 与两个台账）\n")
    if workers:
        out.append("| 机器名 | 就绪状态 | 系统 | 弱模型 / 层级 | 就绪时间 | 正在执行 | 阻塞 | 执行登记次数 | 达标数（≥ 60） | 近达标数（50–59） | 审查通过数 | 最近登记 |")
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for w in workers:
            out.append(f"| {w['name']} | {w['registered']} | {w['system']} | {w['weak']} | {w['ready_at']} | {', '.join(w['running'])} | {', '.join(w['blocked'])} | {w['runs']} | {w['passed']} | {w['near']} | {w['rv_ok']} | {w['last']} |")
        out.append("")
    else:
        out.append("尚无执行机。\n")

    out.append("## 执行队列（来自 [queue.md](topics/queue.md)）\n")
    if queue:
        out.append("| 顺位 | 题号 | 起始候选 | 领域 | 当前状态 | 对抗 | 预筛 | 排序理由 |")
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in queue:
            tid = r[1]
            st = topics.get(tid, {}).get("status", "（无选题文件）")
            pre = topics.get(tid, {}).get("prescreen", "")
            adv = topics.get(tid, {}).get("adversarial", "")
            reason = r[4] if len(r) > 4 else ""
            out.append(f"| {r[0]} | {md_link(tid, f'topics/{tid}.md')} | {r[2] if len(r) > 2 else ''} | {r[3] if len(r) > 3 else ''} | {st} | {adv} | {pre} | {reason} |")
        out.append("")
    else:
        out.append("队列为空。\n")

    out.append("## 每题一行\n")
    out.append("| 题号 | 领域（起始候选） | 候选数 | 来源 | 状态 | 草稿 | 对抗 | 预筛 | 执行机 | 校准结果（台账 1） | A / C（B 已取消） | 运行摘要 | 审查 |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for tid in sorted(topics):
        t = topics[tid]
        start = t["start"]
        cand = next((c for c in t["cands"] if c["n"] == start), t["cands"][0] if t["cands"] else {"domain": "", "slug": ""})
        dom = cand["domain"] + (f"（候选 {start} `{cand['slug']}`）" if cand.get("slug") else "")
        task = tasks.get(tid)
        machine = task[3] if task and len(task) > 3 else ""
        calib_result = task[5] if task and len(task) > 5 else ""
        cal = parse_calibration(tid)
        abc = ""
        runs_link = ""
        if cal:
            abc = " / ".join(cal["cond"].get(k, "-") or "-" for k in "AC")
            runs_link = md_link(f"runs/{tid}/（{cal['n_runs']} 次）", f"runs/{tid}/")
        rv = latest_review(tid)
        rv_cell = ""
        if rv:
            detail = rv[3] if len(rv) > 3 else ""
            m = re.search(r"\(([^)]+)\)", detail)
            fname = pathlib.PurePosixPath(m.group(1)).name if m else ""
            rv_cell = rv[1] + (f"（{md_link('详情', f'reviews/{fname}')}）" if fname else "")
        elif calib_result.startswith("不达标"):
            rv_cell = "不需审查"
        elif calib_result.startswith("达标") or calib_result.startswith("近达标"):
            rv_cell = "待审查"
        topic_link = md_link(tid, f"topics/{tid}.md") if (TOPICS / f"{tid}.md").exists() else md_link(tid, f"topics/{tid}-prompt.md")
        draft_cell = md_link("有", f"drafts/{tid}/") if (DRAFTS / tid).is_dir() else ""
        out.append(f"| {topic_link} | {dom} | {len(t['cands'])} | {source_kind(t['source'])} | {t['status']} | {draft_cell} | {t.get('adversarial', '')} | {t.get('prescreen', '')} | {machine} | {calib_result} | {abc} | {runs_link} | {rv_cell} |")
    out.append("")

    if mats:
        out.append("## 素材（来自 [materials/](materials/README.md)）\n")
        out.append("| 素材号 | 状态 | 候选数 | 成题 | 否决 | 待判 | 候选题目名 | 文件 |")
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for mid, m in mats.items():
            f = f"materials/{mid}.md" if (MATERIALS / f"{mid}.md").exists() else f"materials/{mid}-prompt.md"
            out.append(f"| {mid} | {m['status']} | {m.get('n_cand', 0)} | {m.get('n_ok', 0)} | {m.get('n_rej', 0)} | {m.get('n_open', 0)} | {', '.join('`' + x + '`' for x in m['slugs'])} | {md_link(pathlib.PurePosixPath(f).name, f)} |")
        out.append("")

    claims = parse_claims(now_dt)
    out.append(f"## 进行中的占用（来自 [claims/](claims/README.md)，租期 {CLAIM_LEASE_H} 小时）\n")
    if claims:
        out.append("| 文件 | 类型 | 对象 | 占用者 | 心跳 | 状态 |")
        out.append("| --- | --- | --- | --- | --- | --- |")
        for c in claims:
            out.append(f"| {md_link(c['file'], 'claims/' + c['file'])} | {c['kind']} | {c['obj']} | {c['owner']} | {c['beat']} | {c['state']} |")
        out.append("")
    else:
        out.append("无。\n")

    if scores:
        out.append("## 复审打分（来自 [runs/scores.md](runs/scores.md)）\n")
        out.append("| 题号 | 候选 | 结果 | 5.6 通过数/4 | 弱模型结论 | 最小成功步数 | 距目标判断 | 处置 |")
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in scores:
            cells = (r + [""] * 8)[:8]
            out.append("| " + " | ".join(cells) + " |")
        out.append("")

    (FLOW / "board.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"board.md written: {len(topics)} topics, {len(mats)} materials, {len(workers)} workers, {len(tasks)} ledger rows, {len(queue)} queued")


if __name__ == "__main__":
    sys.exit(main())
