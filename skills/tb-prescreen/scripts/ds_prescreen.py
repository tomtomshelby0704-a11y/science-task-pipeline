#!/usr/bin/env python3
"""Quick design-time probes of a runnable draft (drafts/<topic>/) against the real weak model (DeepSeek).

Not calibration evidence. The default probe is "oneshot" (a few minutes, a few calls, one short-lived container);
a full-length run belongs to the execution machines only.

  --check        print whether a key and Docker are available (never prints the key); exit 0 / 3 / 4.
  --mode idea    ~1 min, 1 API call, no tools: the model sees the task text plus a short data overview and
                 says how it would solve it and which data problems it would check. Saved as idea.md for the
                 author to compare against the topic's traps. Verdict "思路探针完成".
  --mode oneshot DEFAULT gate, ~1.5-3 min (thinking off by default: --effort none, ~30 s per call): the model sees the task text plus a short data overview and writes ONE complete
                 script; it runs once in an offline container (<= 180 s) and is verified. If it fails, the model gets the
                 script's own output (not the verifier's) and may revise it, at most 2 times. Verdict
                 "一次性解出（第 k 次）" = too easy / "一次性未解出" = not cheaply solvable (says nothing more).
  --mode idea --no-data
                 task-text leak probe, ~20 s, no Docker: only the task text goes to the model (no data). If it names a
                 trap that is meant to be diagnosable only from the data, the task text leaks it (tb-harden gate).
  --mode run     OPTIONAL, manual only: short agent run in an offline container (default <= 40 turns, <= 12 min, <= 120 s per command,
                 full history with older command output shortened, commands killed in-container on timeout). The verifier runs every 5 turns once results exist and
                 at the end; reward 1 stops the run early. Verdict "短跑解出（第 N 回合）" / "短跑未解出".

Entry (repo root):
    python skills/tb-prescreen/scripts/ds_prescreen.py --check
    python skills/tb-prescreen/scripts/ds_prescreen.py --topic tbs-020 [--mode oneshot] \
        --gen "python generate_data.py --seed {seed} --out {data} --truth {truth}" \
        --verify "python verify.py --results {results} --truth {truth}" [--results-dir results] [--round 1] [--write-summary]

Env:      python >= 3.9, standard library only; Docker CLI with a running daemon.
Creds:    WEAK_MODEL_API_KEY / WEAK_MODEL_NAME / WEAK_MODEL_BASE_URL / WEAK_MODEL_TIER from os.environ, then --env-file,
          then <repo>/.env, then the main worktree's .env (all gitignored). The key is never printed or written.
Service:  OpenAI-compatible /chat/completions (DeepSeek: https://api.deepseek.com, model deepseek-flash).
Inputs:   flows/tb-science/drafts/<topic>/{instruction.md, requirements.txt, generator, verifier}.
          Placeholders in --gen / --verify: {seed} {data} {truth} {results}; commands run with cwd = the draft.
Outputs:  tmp/prescreen/<topic>/<UTC stamp>-<mode>/ (gitignored): logs, idea.md or trajectory.jsonl, verify.txt,
          summary.json, prescreen.md. --write-summary appends the same section to drafts/<topic>/prescreen.md.
Exit:     0 probe done, 2 usage error, 3 no API key, 4 no Docker, 5 invalid probe (API/infra/verifier output).

Isolation: one image (python:3.11-slim + the draft's requirements.txt). The agent container mounts only <work>/app at
/app with --network none; the hidden truth stays in <work>/truth; the draft (with the reference solution) is mounted
read-only only into the generator/verifier containers. Model calls go out from the host.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
DRAFTS = ROOT / "flows" / "tb-science" / "drafts"
OUT_CHARS = 3000
RECENT_FULL = 6        # turns whose command output is kept in full; older outputs are shortened
OLD_OBS_CHARS = 400
FINALIZE_TURNS = 3     # wrap-up turns after the budget, so the verifier always sees an answer
FINALIZE_PROMPT = ("The time budget is used up. In at most {n} more turns, write all required output files under "
                   "/app/{results} using your current best approach (do not start new exploration), then call task_complete.")
VERIFY_EVERY = 5
CMD_TIMEOUT_DEFAULT = 60
CMD_TIMEOUT_MAX = 120
NO_ACTION_LIMIT = 3
OVERVIEW_CHARS = 4000
ONESHOT_ATTEMPTS = 3   # first script + at most 2 revisions
SCRIPT_TIMEOUT = 180
# Every container this script starts gets CPU/memory caps and single-threaded BLAS, so design-time
# probes never crowd out executor runs on a shared machine (AGENTS.md: 出题侧算力与时间预算).
THREAD_ENV = ["-e", "OPENBLAS_NUM_THREADS=1", "-e", "MKL_NUM_THREADS=1",
              "-e", "OMP_NUM_THREADS=1", "-e", "NUMEXPR_NUM_THREADS=1"]
RUN_TIMEOUT = 600  # single run <= 10 min


def caps(a):
    return ["--cpus", a.cpus, "--memory", a.memory, *THREAD_ENV]

RUN_PROMPT = """You are an AI agent solving a task inside a Linux container. Your working directory is /app.
Use the `bash` tool to run commands and the `task_complete` tool when you are sure the task is fully done.
Rules:
- Each bash call runs in a fresh non-interactive `bash -lc` at /app; shell state (cd, variables) does not persist,
  files do. Do not start interactive programs. Max timeout_sec is 120.
- There is no network access. Python 3.11 and the packages needed for the task are installed.
- You will receive the output (truncated if long) and exit code of each command."""

LEAK_PROMPT = """You will be given only the text of a data-analysis task, not its data. Do not write code.
In at most 400 words, list what you would check in the data first, and which hidden complications, confounders or
data problems you expect this task to contain, as specifically as the text allows. Say which sentence of the task
text makes you expect each one."""

IDEA_PROMPT = """You will be given a data-analysis task and a short overview of its input files. Do not write code.
In at most 600 words, answer:
1. Your step-by-step approach and the methods you would use.
2. What you would check in the data before trusting it (anomalies, confounders, units, missing or inconsistent parts).
3. Where a straightforward approach would go wrong, and how you would validate your final result."""

ONESHOT_PROMPT = """You will be given a data-analysis task and a short overview of its input files under /app/data.
Write ONE complete Python 3.11 script that solves the whole task and writes every required output under /app/{results}.
It will be run once as `python /app/solve.py` in /app, offline, with the packages the task needs installed, limited to {timeout} s.
Reply with the full script in a single ```python code block and nothing else."""

ONESHOT_FIX = """This is the output of running your script (exit code {rc}):

{out}

Fix whatever is wrong and reply with the full revised script in a single ```python code block and nothing else."""

TOOLS = [
    {"type": "function", "function": {
        "name": "bash", "description": "Run one non-interactive bash command at /app and return its output and exit code.",
        "parameters": {"type": "object", "properties": {
            "cmd": {"type": "string", "description": "the bash command"},
            "timeout_sec": {"type": "integer", "description": "timeout in seconds (default 60, max 120)"}},
            "required": ["cmd"]}}},
    {"type": "function", "function": {
        "name": "task_complete", "description": "Declare that the task is fully done. Call only when finished.",
        "parameters": {"type": "object", "properties": {}}}},
]


def load_env(env_file):
    keys = ("WEAK_MODEL_API_KEY", "WEAK_MODEL_NAME", "WEAK_MODEL_BASE_URL", "WEAK_MODEL_TIER")
    cfg = {k: os.environ.get(k, "") for k in keys}
    candidates = [pathlib.Path(env_file)] if env_file else []
    candidates.append(ROOT / ".env")
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        if common:
            candidates.append(pathlib.Path(common).parent / ".env")
    except Exception:
        pass
    for p in candidates:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*?)\s*$", line)
            if m and m.group(1) in cfg and not cfg[m.group(1)]:
                cfg[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    cfg["WEAK_MODEL_NAME"] = cfg["WEAK_MODEL_NAME"] or "deepseek-flash"
    cfg["WEAK_MODEL_BASE_URL"] = (cfg["WEAK_MODEL_BASE_URL"] or "https://api.deepseek.com").rstrip("/")
    return cfg


def sh(args, timeout=None):
    """Run a command (list), return (code, combined output). Never raises on timeout."""
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, text=True, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        return 124, out + f"\n[timed out after {timeout}s]"


def docker_ok():
    return sh(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=60)[0] == 0


def truncate(text, limit=OUT_CHARS):
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n... [{len(text) - limit} chars omitted] ...\n" + text[-half:]


def chat(cfg, messages, tools=None, max_tries=5, effort=None):
    url = cfg["WEAK_MODEL_BASE_URL"] + "/chat/completions"
    payload = {"model": cfg["WEAK_MODEL_NAME"], "messages": messages}
    if tools:
        payload["tools"] = tools
    if effort:  # DeepSeek: none disables thinking; low / high / max set its strength (provider default: high)
        payload["reasoning_effort"] = effort
    body = json.dumps(payload).encode("utf-8")
    last = ""
    for attempt in range(max_tries):
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + cfg["WEAK_MODEL_API_KEY"]})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode("utf-8"))
            return data["choices"][0]["message"], data.get("usage", {})
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
            if e.code in (400, 401, 402, 403, 404, 422):
                break
        except Exception as e:  # network / timeout / malformed
            last = f"{type(e).__name__}: {e}"
        time.sleep(min(30, 3 * 2 ** attempt))
    raise RuntimeError("model API failed: " + last)


def tool_cmds(msg):
    """Native tool calls -> [(call_id, cmd, timeout)], completed flag, [(call_id, error)]."""
    cmds, done, bad = [], False, []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        name, cid = fn.get("name"), tc.get("id", "")
        if name == "task_complete":
            done = True
            continue
        try:
            args = json.loads(fn.get("arguments") or "{}")
            cmd = str(args.get("cmd") or args["command"])
        except (ValueError, KeyError, TypeError) as e:
            bad.append((cid, f"invalid arguments for {name}: {e}"))
            continue
        try:
            t = int(float(args.get("timeout_sec") or CMD_TIMEOUT_DEFAULT))
        except (TypeError, ValueError):
            t = CMD_TIMEOUT_DEFAULT
        cmds.append((cid, cmd, max(5, min(t, CMD_TIMEOUT_MAX))))
    return cmds, done, bad


def parse_reward(text):
    hits = re.findall(r"reward[\"']?\s*[:=]?\s*([01](?:\.0+)?)\b", text, re.I)
    return float(hits[-1]) if hits else None


def failed_checks(text):
    lines = [l.strip() for l in text.splitlines()
             if re.search(r"\bFAIL\b|\"pass(ed)?\"\s*:\s*false|✗", l, re.I)]
    return [l[:160] for l in lines[:10]]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Quick weak-model probes of a draft (design time; not calibration evidence).")
    ap.add_argument("--check", action="store_true", help="only report key / Docker availability")
    ap.add_argument("--topic", help="topic id, e.g. tbs-020")
    ap.add_argument("--mode", choices=("oneshot", "idea", "run"), default="oneshot")
    ap.add_argument("--gen", help="generator command template, cwd = draft")
    ap.add_argument("--verify", help="verifier command template, cwd = draft (oneshot / run)")
    ap.add_argument("--results-dir", default="results", help="results dir relative to /app (default results)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--round", type=int, default=1, help="design iteration number, for the summary")
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--max-minutes", type=float, default=12.0)
    ap.add_argument("--effort", choices=("none", "low", "high", "max"),
                    help="reasoning effort; default none for oneshot / idea (fast), provider default for run")
    ap.add_argument("--cpus", default="2")
    ap.add_argument("--memory", default="4g")
    ap.add_argument("--env-file", default="")
    ap.add_argument("--no-data", action="store_true",
                    help="idea mode only: send the task text without any data (leak probe; no Docker needed)")
    ap.add_argument("--write-summary", action="store_true", help="append the section to drafts/<topic>/prescreen.md")
    a = ap.parse_args()

    cfg = load_env(a.env_file)
    if a.effort is None and a.mode in ("oneshot", "idea"):
        a.effort = "none"
    has_key, has_docker = bool(cfg["WEAK_MODEL_API_KEY"]), docker_ok()
    if a.check:
        print(f"key: {'有' if has_key else '无'}, docker: {'有' if has_docker else '无'}, model: {cfg['WEAK_MODEL_NAME']}")
        return 0 if has_key and has_docker else (3 if not has_key else 4)
    if a.no_data and a.mode != "idea":
        print("usage error: --no-data only works with --mode idea")
        return 2
    if not a.topic or (not a.gen and not a.no_data) or (a.mode != "idea" and not a.verify):
        print("usage error: --topic and --gen are required (except idea --no-data); oneshot / run also need --verify")
        return 2
    draft = DRAFTS / a.topic
    if not (draft / "instruction.md").is_file() or not (draft / "requirements.txt").is_file():
        print(f"usage error: {draft} needs instruction.md and requirements.txt")
        return 2
    if not has_key:
        print("未预筛：no WEAK_MODEL_API_KEY (environment or local .env); skipped")
        return 3
    if not has_docker and not a.no_data:
        print("未预筛：Docker daemon not available; skipped")
        return 4

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work = ROOT / "tmp" / "prescreen" / a.topic / f"{stamp}-{a.mode}{'-nodata' if a.no_data else ''}"
    app_dir, truth_dir = work / "app", work / "truth"
    app_dir.mkdir(parents=True)
    truth_dir.mkdir()
    shutil.copy2(draft / "instruction.md", app_dir / "instruction.md")
    paths = {"seed": str(a.seed), "data": "/work/app/data", "truth": "/work/truth",
             "results": "/work/app/" + a.results_dir.strip("/")}
    gen_cmd = a.gen.format(**paths) if a.gen else ""
    verify_cmd = a.verify.format(**paths) if a.verify else ""

    s = {"topic": a.topic, "mode": "leak" if a.no_data else a.mode, "round": a.round, "date_utc": stamp, "model": cfg["WEAK_MODEL_NAME"],
         "tier": cfg["WEAK_MODEL_TIER"], "effort": a.effort or "默认", "seed": a.seed, "gen": a.gen, "verify": a.verify or "",
         "results_dir": a.results_dir, "budget": {"max_turns": a.max_turns, "max_minutes": a.max_minutes},
         "turns": 0, "wall_s": 0.0, "usage": {"prompt_tokens": 0, "completion_tokens": 0},
         "end": "", "reward": None, "solved_turn": None, "failed_checks": [], "verdict": "", "invalid_reason": ""}
    t_start = time.time()

    def add_usage(u):
        for k in ("prompt_tokens", "completion_tokens"):
            s["usage"][k] += int(u.get(k) or 0)

    def finish(verdict, reason=""):
        s["verdict"], s["invalid_reason"] = verdict, reason
        s["wall_s"] = round(time.time() - t_start, 1)
        (work / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
        md = render_section(s, work)
        (work / "prescreen.md").write_text(md, encoding="utf-8")
        if a.write_summary:
            target = draft / "prescreen.md"
            head = "" if target.exists() else (
                f"# {a.topic} 出题阶段探针记录\n\n> 由 `skills/tb-prescreen/scripts/ds_prescreen.py` 生成，每次探针追加一节。"
                "**不是校准证据**：不是 `harbor run`，不替代要求书条件 B。完整轨迹只留在运行机本地 `tmp/prescreen/`。\n\n")
            with open(target, "a", encoding="utf-8", newline="\n") as f:
                f.write(head + md)
        print(f"{verdict}{'：' + reason if reason else ''} | mode={a.mode} turns={s['turns']} "
              f"wall={s['wall_s']}s tokens={s['usage']['prompt_tokens']}+{s['usage']['completion_tokens']} | {work}")
        return 5 if verdict == "无效" else 0

    if a.no_data:
        return run_leak(a, cfg, s, work, add_usage, finish)

    # 1. image (cached by requirements hash)
    tag = "tbs-prescreen:" + hashlib.sha256((draft / "requirements.txt").read_bytes()).hexdigest()[:12]
    if sh(["docker", "image", "inspect", tag], timeout=60)[0] != 0:
        ctx = work / "image"
        ctx.mkdir()
        shutil.copy2(draft / "requirements.txt", ctx / "requirements.txt")
        (ctx / "Dockerfile").write_text(
            "FROM python:3.11-slim\nCOPY requirements.txt /tmp/requirements.txt\n"
            "RUN pip install --no-cache-dir -r /tmp/requirements.txt\nWORKDIR /app\n", encoding="utf-8")
        code, out = sh(["docker", "build", "-t", tag, str(ctx)], timeout=1800)
        (work / "build.log").write_text(out, encoding="utf-8")
        if code != 0:
            return finish("无效", "image build failed (see build.log)")
    mounts = ["-v", f"{draft}:/draft:ro", "-v", f"{work}:/work"]

    # 2. data; truth stays outside /app
    code, out = sh(["docker", "run", "--rm", "--network", "none", *caps(a), *mounts, "-w", "/draft", tag,
                    "bash", "-lc", gen_cmd], timeout=RUN_TIMEOUT)
    (work / "generate.log").write_text(out, encoding="utf-8")
    if code != 0:
        return finish("无效", "generator failed (see generate.log)")
    instruction = (app_dir / "instruction.md").read_text(encoding="utf-8")

    if a.mode == "idea":
        return run_idea(a, cfg, s, work, tag, instruction, add_usage, finish)
    if a.mode == "oneshot":
        return run_oneshot(a, cfg, s, work, tag, mounts, verify_cmd, instruction, add_usage, finish)
    return run_short(a, cfg, s, work, tag, mounts, verify_cmd, instruction, add_usage, finish)


def data_overview(work, tag, run_caps):
    listing_cmd = ("cd /app && find data -type f | sort | head -40 | while read f; do "
                   "echo \"=== $f ($(wc -c < \"$f\") bytes)\"; head -c 400 \"$f\" | head -8; echo; done")
    _, overview = sh(["docker", "run", "--rm", "--network", "none", *run_caps, "-v", f"{work / 'app'}:/app", tag,
                         "bash", "-lc", listing_cmd], timeout=120)
    return truncate(overview, OVERVIEW_CHARS)


def extract_script(text):
    m = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text or "", re.S)
    return max(m, key=len) if m else ""


def run_oneshot(a, cfg, s, work, tag, mounts, verify_cmd, instruction, add_usage, finish):
    app_dir = work / "app"
    results = a.results_dir.strip("/")
    overview = data_overview(work, tag, caps(a))
    msgs = [{"role": "system", "content": ONESHOT_PROMPT.format(results=results, timeout=SCRIPT_TIMEOUT)},
            {"role": "user", "content": f"Task:\n\n{instruction}\n\nInput data overview:\n\n{overview}"}]
    reward, vout = None, ""
    s["attempts"] = []
    for attempt in range(1, ONESHOT_ATTEMPTS + 1):
        try:
            reply, usage = chat(cfg, msgs, effort=a.effort)
        except RuntimeError as e:
            return finish("无效", str(e)[:300])
        add_usage(usage)
        s["turns"] = attempt
        content = reply.get("content") or ""
        msgs.append({"role": "assistant", "content": content})
        (work / f"solve-{attempt}.py").write_text(extract_script(content), encoding="utf-8")
        shutil.copy2(work / f"solve-{attempt}.py", app_dir / "solve.py")
        shutil.rmtree(app_dir / results, ignore_errors=True)
        rc, out = sh(["docker", "run", "--rm", "--network", "none", *caps(a),
                      "-v", f"{app_dir}:/app", "-w", "/app", tag, "timeout", "-k", "5", str(SCRIPT_TIMEOUT),
                      "python", "/app/solve.py"], timeout=SCRIPT_TIMEOUT + 60)
        (work / f"run-{attempt}.log").write_text(out, encoding="utf-8")
        reward, vout = None, ""
        if (app_dir / results).is_dir():
            _, vout = sh(["docker", "run", "--rm", "--network", "none", *caps(a), *mounts, "-w", "/draft", tag,
                          "bash", "-lc", verify_cmd], timeout=RUN_TIMEOUT)
            (work / "verify.txt").write_text(vout, encoding="utf-8")
            reward = parse_reward(vout)
        s["attempts"].append({"attempt": attempt, "exit": rc, "reward": reward})
        if reward is not None and reward >= 1:
            s["reward"], s["solved_turn"], s["end"] = reward, attempt, "solved"
            return finish(f"一次性解出（第 {attempt} 次）")
        # feedback is the script's own output only, never the verifier's
        msgs.append({"role": "user", "content": ONESHOT_FIX.format(rc=rc, out=truncate(out, OUT_CHARS) or "(no output)")})
    s["reward"] = reward if reward is not None else 0.0
    s["failed_checks"] = failed_checks(vout) or ([] if vout else ["no output files were written"])
    s["end"] = "attempts"
    return finish("一次性未解出")


def run_leak(a, cfg, s, work, add_usage, finish):
    instruction = (work / "app" / "instruction.md").read_text(encoding="utf-8")
    msgs = [{"role": "system", "content": LEAK_PROMPT}, {"role": "user", "content": f"Task:\n\n{instruction}"}]
    try:
        reply, usage = chat(cfg, msgs, effort=a.effort)
    except RuntimeError as e:
        return finish("无效", str(e)[:300])
    add_usage(usage)
    s["turns"], s["end"] = 1, "idea"
    (work / "idea.md").write_text(reply.get("content") or "", encoding="utf-8")
    return finish("题面泄漏探针完成（作者对照核心难点判断是否泄漏）")


def run_idea(a, cfg, s, work, tag, instruction, add_usage, finish):
    overview = data_overview(work, tag, caps(a))
    msgs = [{"role": "system", "content": IDEA_PROMPT},
            {"role": "user", "content": f"Task:\n\n{instruction}\n\nInput data overview:\n\n{overview}"}]
    try:
        reply, usage = chat(cfg, msgs, effort=a.effort)
    except RuntimeError as e:
        return finish("无效", str(e)[:300])
    add_usage(usage)
    s["turns"] = 1
    s["end"] = "idea"
    (work / "idea.md").write_text(reply.get("content") or "", encoding="utf-8")
    return finish("思路探针完成")


def run_short(a, cfg, s, work, tag, mounts, verify_cmd, instruction, add_usage, finish):
    app_dir = work / "app"
    results_host = app_dir / a.results_dir.strip("/")
    cname = f"tbs-prescreen-{a.topic}-{s['date_utc'].lower()}"
    code, out = sh(["docker", "run", "-d", "--name", cname, "--network", "none", *caps(a),
                    "-v", f"{app_dir}:/app", "-w", "/app", tag, "sleep", "infinity"], timeout=120)
    if code != 0:
        return finish("无效", "agent container failed to start: " + out.strip()[:200])

    def verify():
        rc, vout = sh(["docker", "run", "--rm", "--network", "none", *caps(a), *mounts, "-w", "/draft", tag,
                       "bash", "-lc", verify_cmd], timeout=RUN_TIMEOUT)
        (work / "verify.txt").write_text(vout, encoding="utf-8")
        return parse_reward(vout), vout

    head = [{"role": "system", "content": RUN_PROMPT},
            {"role": "user", "content": "Task instruction (also at /app/instruction.md):\n\n" + instruction}]
    groups = []  # one list of messages per turn: assistant (+ tool/user observations)
    t0 = time.time()
    no_action, reward, vout = 0, None, ""
    traj = open(work / "trajectory.jsonl", "w", encoding="utf-8")

    state = {"final_left": None}  # None = normal budget; int = wrap-up turns remaining
    s["finalize_turns"] = 0

    def run_cmd(cmd, tmo):
        if state["final_left"] is None:
            tmo = max(5, int(min(tmo, a.max_minutes * 60 - (time.time() - t0) + 5)))
        # kill inside the container too, so a timed-out command does not keep running in the background
        rc, o = sh(["docker", "exec", "-w", "/app", cname, "timeout", "-k", "5", str(tmo), "bash", "-lc", cmd],
                   timeout=tmo + 15)
        if rc == 124:
            o += f"\n[timed out after {tmo}s and was killed]"
        return f"$ {cmd}\n[exit {rc}]\n{truncate(o)}"

    def compact(groups):
        """Full history; observations older than the last RECENT_FULL turns are cut to OLD_OBS_CHARS."""
        out = []
        for i, g in enumerate(groups):
            old = i < len(groups) - RECENT_FULL
            for m in g:
                if old and m["role"] in ("tool", "user"):
                    m = dict(m, content=truncate(m["content"], OLD_OBS_CHARS))
                out.append(m)
        return out

    try:
        while True:
            if state["final_left"] is None:
                over = ("max_turns" if s["turns"] >= a.max_turns else
                        "time_budget" if time.time() - t0 > a.max_minutes * 60 else None)
                if over:  # budget used up: a few wrap-up turns so "not finished" still yields a verifiable answer
                    s["end"] = over
                    state["final_left"] = FINALIZE_TURNS
                    note = {"role": "user", "content": FINALIZE_PROMPT.format(n=FINALIZE_TURNS, results=a.results_dir.strip("/"))}
                    groups.append([note])
                    traj.write(json.dumps({"turn": s["turns"], "role": "observation", "content": note["content"]},
                                          ensure_ascii=False) + "\n")
            elif state["final_left"] <= 0:
                break
            if state["final_left"] is not None:
                state["final_left"] -= 1
                s["finalize_turns"] += 1
            messages = head + compact(groups)
            try:
                reply, usage = chat(cfg, messages, tools=TOOLS, effort=a.effort)
            except RuntimeError as e:
                return finish("无效", str(e)[:300])
            s["turns"] += 1
            add_usage(usage)
            content, calls = reply.get("content") or "", reply.get("tool_calls") or []
            amsg = {"role": "assistant", "content": content}
            if calls:
                amsg["tool_calls"] = calls
            if reply.get("reasoning_content"):  # thinking mode: DeepSeek expects it back during tool loops
                amsg["reasoning_content"] = reply["reasoning_content"]
            group = [amsg]
            traj.write(json.dumps({"turn": s["turns"], "role": "assistant", "content": content,
                                   "tool_calls": calls}, ensure_ascii=False) + "\n")
            done = False
            if calls:
                cmds, done, bad = tool_cmds(reply)
                for cid, cmd, tmo in cmds:
                    group.append({"role": "tool", "tool_call_id": cid, "content": run_cmd(cmd, tmo)})
                for cid, err in bad:
                    group.append({"role": "tool", "tool_call_id": cid, "content": err})
                for tc in calls:  # every tool call needs a tool message, incl. task_complete
                    if (tc.get("function") or {}).get("name") == "task_complete":
                        group.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": "ok"})
                no_action = 0
            else:
                group.append({"role": "user", "content": "No command was run. Use the bash tool to continue, "
                                                         "or call task_complete if the task is fully done."})
                no_action += 1
            for m in group[1:]:
                traj.write(json.dumps({"turn": s["turns"], "role": "observation", "content": m["content"]},
                                      ensure_ascii=False) + "\n")
            traj.flush()
            groups.append(group)
            if done:
                s["end"] = s["end"] + "+task_complete" if state["final_left"] is not None else "task_complete"
                break
            if no_action >= NO_ACTION_LIMIT and state["final_left"] is None:
                s["end"] = "no_action"
                break
            if s["turns"] % VERIFY_EVERY == 0 and results_host.is_dir() and any(results_host.iterdir()):
                reward, vout = verify()
                if reward is not None and reward >= 1:
                    s["end"], s["solved_turn"] = "solved", s["turns"]
                    break
    finally:
        traj.close()
        sh(["docker", "rm", "-f", cname], timeout=120)

    if s["end"] != "solved":
        reward, vout = verify()
        if reward is not None and reward >= 1:
            s["solved_turn"] = s["turns"]
    s["reward"] = reward
    s["failed_checks"] = failed_checks(vout)
    if reward is None:
        return finish("无效", "verifier output has no reward (see verify.txt)")
    if reward >= 1:
        tag = "，含收尾" if s["finalize_turns"] else ""
        return finish(f"短跑解出（第 {s['solved_turn']} 回合{tag}）")
    return finish("短跑未解出")


def render_section(s, work):
    base = (s["end"] or "").split("+")[0]
    end = {"task_complete": "模型自报完成", "max_turns": "回合预算用尽", "time_budget": "时间预算用尽",
           "no_action": f"连续 {NO_ACTION_LIMIT} 回合无动作", "solved": "中途验证已通过，提前停止",
           "idea": "单次回答", "attempts": f"{ONESHOT_ATTEMPTS} 次脚本均未通过"}.get(base, base or "-")
    if s.get("finalize_turns"):
        end += f"，之后收尾 {s['finalize_turns']} 回合"
    title = {"idea": "思路探针", "leak": "题面泄漏探针", "oneshot": "一次性探针", "run": "短跑探针"}[s["mode"]]
    lines = [
        f"## 第 {s['round']} 轮 · {title} · {s['date_utc']}",
        "",
        f"- **结论**：{s['verdict']}{'（' + s['invalid_reason'] + '）' if s['invalid_reason'] else ''}",
        f"- **模型**：{s['model']}（Tier {s['tier'] or '?'}，思考强度 {s.get('effort', '默认')}），种子 {s['seed']}",
        f"- **用量**：{s['turns']} 回合 / {s['wall_s']:.0f} s（{end}）；tokens 输入 {s['usage']['prompt_tokens']} / 输出 {s['usage']['completion_tokens']}",
    ]
    if s["mode"] == "oneshot":
        lines.append(f"- **预算**：最多 {ONESHOT_ATTEMPTS} 次脚本（首次 + 2 次修改，只回传脚本自己的输出），每次运行 ≤ {SCRIPT_TIMEOUT} s，断网")
        lines.append("- **各次**：" + "；".join(
            f"第 {x['attempt']} 次 exit {x['exit']} 奖励 {x['reward'] if x['reward'] is not None else '-'}"
            for x in s.get("attempts", [])))
    if s["mode"] == "run":
        lines.append(f"- **预算**：≤ {s['budget']['max_turns']} 回合、≤ {s['budget']['max_minutes']:.0f} 分钟、单命令 ≤ {CMD_TIMEOUT_MAX} s，断网")
    if s["mode"] not in ("idea", "leak"):
        lines.append(f"- **奖励**：{s['reward'] if s['reward'] is not None else '-'}")
        if s["failed_checks"]:
            lines.append("- **未过的子检查**：")
            lines += [f"  - `{c}`" for c in s["failed_checks"]]
    lines += ["- **命令**：", "", "```",
              f"--gen \"{s['gen']}\"" + (f" --verify \"{s['verify']}\"" if s['verify'] else "") + f" --results-dir {s['results_dir']} --seed {s['seed']}",
              "```", ""]
    if s["mode"] in ("idea", "leak"):
        idea = work / "idea.md"
        text = idea.read_text(encoding="utf-8").strip() if idea.exists() else ""
        lines += ["DS 的回答（作者据此对照“核心难点”的陷阱，结论写在题文件 `预筛` 行）：", "",
                  "\n".join("> " + l for l in text.splitlines()), ""]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
