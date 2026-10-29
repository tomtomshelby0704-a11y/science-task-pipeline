# tb-prescreen：出题阶段探针

## 触发口令

- **自动**：[tb-research](../tb-research/SKILL.md)、[tb-harden](../tb-harden/SKILL.md) 开局运行 `ds_prescreen.py --check`，本机有弱模型 key 和 Docker 就**默认**在第 5 步写题时做探针，不问人类，但第一句话告知 `本轮出题使用本机 DeepSeek key（deepseek-flash）做出题阶段探针`。没有 key（云端一般没有）就不做、不提，流程照旧。
- `预筛 <题号>`：给已经在排的题（例如云端出的题）补一次探针，只探不改设计。

## 目的

13 道已跑题里有 9 道被弱模型直接解掉，每道都耗掉执行机几个小时才发现。探针在**出题阶段**用同一个弱模型（[calibration-models.md](../../flows/tb-science/calibration-models.md) 第 1 节 deepseek-flash，Tier 1.5）**大概测一下**。2026-10-29 起条件 B 取消，弱模型做对**不再否决题、也不触发改设计**，只作排序参考：弱模型一次就做对，常意味着 GPT 5.6 也容易 4/4，所以排到队列后面。

- **一次性探针（默认，只作排序参考）**：DS 看题面和数据概览，写**一份完整脚本**，在断网容器里跑一次（≤ 180 s）后验证；没过就把脚本自己的输出（不给验证器结果）回传，让它最多修两次。默认关闭 DS 的思考（`--effort none`，每次调用约 30 秒、6 千输出 token），全程约 1.5–3 分钟、一个用完即删的容器；不思考都能做对，常意味着 GPT 5.6 也容易 4/4。实测开思考一次调用要 220–290 秒、4–5 万 token，不用作默认。
  - `一次性解出（第 k 次）`：排序落末档（tb-research 第 6 步），回报里建议 `复审改难`；**不改设计、不拦题**。
  - `一次性未解出` 只说明“没被轻易做对”，不说明题合格；合格与否只看执行机的 `harbor run`。
- **题面泄漏探针（tb-harden 写题时的门槛）**：`--mode idea --no-data`，约 20 秒、1 次调用，只给 DS 题面、不给数据，问它要先查什么。改难题的陷阱本该只能从数据诊断，DS 不看数据就点出了它 = 题面泄漏，改材料。
- **思路探针（可选参考）**：约 20 秒、1 次调用，DS 看题面和数据概览说做法和要查的坑。不是门槛：实测 tbs-012（弱模型解出）与 tbs-020（弱模型失败）的陷阱都被 DS 全部点出，“说得出”不等于“做得出”。
- **短跑探针（手动可选，不默认）**：断网多回合作答，≤ 40 回合 / 12 分钟，资源和 token 都重（一次 0.6–1.2M 输入 token）。只在人类点名时用。
- **都不是校准证据**：不是 `harbor run`，也不是[校准结果要求](../../specs/tb-science-requirements.md#校准结果要求合并验收标准-11--交付要求-21)的任何一条（条件 B 已于 2026-10-29 取消）；台账与 calibration 不引用。

## 输入

| 文件 / 资源 | 用途 |
| --- | --- |
| `flows/tb-science/drafts/<题号>/` | `instruction.md`、`requirements.txt`、生成器、验证器（参考解不进作答容器） |
| `flows/tb-science/topics/<题号>.md` | “核心难点”陷阱清单、简报第 6 小节：改设计时对照 |
| 本机 `.env`（仓库根或主 worktree 根，已被 `.gitignore` 忽略） | `WEAK_MODEL_API_KEY`、`WEAK_MODEL_NAME`（默认 `deepseek-flash`）、`WEAK_MODEL_BASE_URL`（默认 `https://api.deepseek.com`）、`WEAK_MODEL_TIER` |
| Docker、DeepSeek API（[文档](https://api-docs.deepseek.com/zh-cn/)） | 断网沙箱；外部服务，按 token 计费 |

## 输出

- `flows/tb-science/drafts/<题号>/prescreen.md`：每次探针追加一节（第几轮、模式、结论、各次 exit 与奖励、用量、未过子检查）。
- `topics/<题号>.md` 头部一行 `- **预筛**：通过（…）` / `解出（…）`；再探追加新行，排序看最新一行。
- 本机 `tmp/prescreen/<题号>/<时间>-<模式>/`（不入库）：DS 写的各版脚本、运行日志、`summary.json`。

## 步骤

0. 资源：脚本起的每个容器（生成数据、数据概览、作答、判分）都带 `--cpus 2 --memory 4g` 和单线程线性代数环境变量，单次运行 ≤ 10 分钟；同一会话同时至多跑 1 个探针。依据 [AGENTS.md 出题侧算力与时间预算](../../AGENTS.md#出题侧算力与时间预算)。
1. 自检：`python skills/tb-prescreen/scripts/ds_prescreen.py --check`。不是 `key: 有, docker: 有` → 不做，什么都不写。
2. 读 `drafts/<题号>/README.md`，找出生成器、验证器的实际命令行（各题参数名不统一），写成模板，`{seed}` `{data}` `{truth}` `{results}` 由脚本替换成容器内路径，命令工作目录是草稿目录。默认就是一次性探针：

   ```
   python skills/tb-prescreen/scripts/ds_prescreen.py --topic <题号> --round 1 --write-summary \
     --gen "python generate_data.py --seed {seed} --out {data} --truth {truth}" \
     --verify "python verify.py --results {results} --truth {truth}" --results-dir results
   ```

   生成器把公开数据和隐藏真值写进同一目录的，用 `--gen "python generate_data.py --out {truth}/s --seed {seed} && mkdir -p {data} && cp -r {truth}/s/public/. {data}/"` 这类组合命令把公开部分拷进 `{data}`。退出码：0 完成；3 无 key、4 无 Docker（不写）；5 无效（API、镜像、生成器或验证器输出问题：修命令重跑一次，仍无效就记 `无效`，按未预筛处理）。这台机器同时是执行机时，一次只跑一个探针。
3. 看结论：`一次性解出` → 记录，排序落末档；`一次性未解出` → 打开 `tmp/.../run-*.log`，确认不是环境问题（找不到数据、缺依赖），是的话按无效处理。需要更多参考时可加 `--mode idea` 看 DS 的思路。
4. 写题阶段（tb-research / tb-harden 第 5 步）：一次性探针只记录、不改设计；tb-harden 的题面泄漏探针点出陷阱就改材料、`--round` 加 1 重探。单独口令 `预筛 <题号>`：只跑一次不改设计，头部追加 `预筛` 行（`通过` 或 `解出`），`prescreen.md` 同一 commit push（台账类，直接推 `main`）；题为 `待执行` 时按 tb-research 第 6 步分档挪动它在 queue.md 的位置，刷新看板。push 前确认 `git status` 里没有 `.env`、`tmp/`。
5. 单独口令时回报一行：`<题号> 预筛：<通过 / 解出（第 k 次）>`，附题文件 `blob` 链接；解出的加一句“建议 复审改难”。

## 完成判据

- key 没有出现在任何提交、摘要和回报里；`.env`、`tmp/` 未提交。
- 每次探针都在 `drafts/<题号>/prescreen.md` 有一节；用到探针的题头部有 `预筛` 行。
- 默认只跑一次性探针（关闭思考，单题一轮约 1.5–3 分钟）；短跑探针只在人类点名时用。
