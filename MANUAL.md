# 使用手册

一条“**人类说口令、Agent 照 Skill 做、结果记台账**”的科学任务生产流水线。目标是出**够难又可交付**的题：GPT 5.6 Sol (max) with Codex 四次成功 1–2 次（不是稳过、也不是全不会），且至少一条成功轨迹 ≥ 60 个 agent 步（50–59 步算近达标）。仓库只放三样：[要求书](specs/tb-science-requirements.md)（唯一判断依据）、固定 [Skill](skills/README.md)、两个台账。题目、轨迹、题包都是运行产物，本仓库**不含**。

## 1. 十分钟部署

1. **得到仓库**：fork 或 clone 本仓库，推到你们自己的（建议私有）GitHub 仓库。把 [flows/tb-science/boot/cloud-research.md](flows/tb-science/boot/cloud-research.md) 里的 `<owner>/<repo>` 换成你们的仓库。
2. **出题侧（云端或本地 Claude）**：会话挂载该仓库即可。想用弱模型做“出题阶段探针”（可选）才需要本机 `.env` 放弱模型 key 并装 Docker。
3. **每台执行机**：前提——Docker Desktop（Windows 需 WSL ≥ 3.0.3；macOS 需 Docker Desktop ≥ 4.86）、Harbor 0.25.0、Codex CLI（已 `codex login`）、Python ≥ 3.9。在任意 Agent 里说 **`构建执行单元 <机器名>`**，得到一段启动 prompt，贴进新 Codex 对话；它自己装环境、过验收、在 [boot/registry.md](flows/tb-science/boot/registry.md) 登记后回“就绪”。弱模型 key 现在可选（校准不再要求弱模型失败），要填就填在启动 prompt 的占位符里。
4. **出第一批题**：云会话说 **`研究出题`**（或 `快速出题`）。之后可在 claude.ai 界面建定时任务，prompt 见 [boot/cloud-research.md](flows/tb-science/boot/cloud-research.md)。
5. **开跑**：执行机说 **`持续执行`**，打开 [flows/tb-science/board.md](flows/tb-science/board.md) 看结果。

> **密钥规则**：key 只写在本机 `<工作目录>/.env`（已被 `.gitignore` 忽略），不进仓库、不进镜像。

## 2. 口令表

| 口令 | 谁执行 | 做什么 |
| --- | --- | --- |
| `启动选题` → `登记素材` | 任意 Agent（+ GPT Pro，可选） | 生成带难度画像的提示词，GPT Pro 的回复或外部题目作为**素材**入库（成不成题由 `研究出题` 判断） |
| `研究出题` | 出题侧 Claude | 先加工全部待加工素材（每个可成题的候选各成一题），再自主研究；每题带“构建简报”和**可运行草稿**（生成器、参考解、验证器实跑通过），按[对抗出题规范](flows/tb-science/adversarial-design.md)设计难度 |
| `快速出题` | 出题侧 Claude（可多开） | 不写草稿、不实跑，靠领域知识把设计和简报写清楚，由执行机构建；用来在执行机空闲时填满队列 |
| `复审改难` | 出题侧 Claude（可多开，靠 `claims/` 错开） | 给跑过的题打分，强模型没落进难度带的题改成新题置顶，并追加“对手档案” |
| `预筛 <题号>` | 有弱模型 key 的出题会话 | 出题阶段用弱模型快速探题，只作排序参考（有 key 时前几个口令自动做） |
| `持续执行` / `执行题目 <题号>` | Codex 执行单元 | 队列顶部领题 → 本机建题包 → `harbor run` 校准 → 登记台账 1 → **自动独立审查**（G1–G8，材料类退回自修）→ 领下一题；障碍自己推进，不问人类 |
| `审查` | 执行机另开对话 | 仅补审 |
| `同步规则` / `刷新看板` | 任意 Agent | 立即拉取比对规则 / 重生成 `board.md`（其他口令会自动做） |

## 3. 流水线一图

```
素材（GPT Pro / 外部题目）─┐
                          ├─> 研究出题 / 快速出题 ─> topics/ (+ drafts/) ─> queue.md ─> 持续执行（执行机）
自主研究 ─────────────────┘            ^                                               │
                                       │                                               v
        复审改难（runs/scores.md 打分、对手档案，改难成新题置顶）<──── 台账1 ─> 自动审查 ─> 台账2 + 达标 zip
全程：board.md 看板由脚本派生；要求书是唯一判断依据
```

达标交付物 = 每题一个压缩包 `<题号>-<task_id>-v<N>.zip`（标准题目 + 判定用真实轨迹 + 脚本生成的 README + SHA-256）。只用 `pack_delivery.py` 打包、`check_delivery.py` 自检；达标版本自检后立即冻结，不被后续修复覆盖。

## 4. 协作不打架

- **`main` 是唯一协调点**：先拉再算；**推送即占有**（占题号、占题先 push 一个文件）；只动自己占到的文件；台账只追加。
- **占用租约**：[claims/](flows/tb-science/claims/README.md) 里一件事一个文件，心跳 2 小时过期，过期可接手；多个出题 / 改难会话同时跑不会撞车。
- **规则自动同步**：规则放在 `specs/ skills/ AGENTS.md` 与两份 README；各 Agent 在会话开始、领题前、登记前、提交前自动 `git pull` 并比对 `.git/tbs-rules-seen`，有变化从下一步起照新规则做。**改规则的人**在[决策表](flows/tb-science/README.md#已定决策)加一行，并写“对进行中的题：无影响 / 从第 N 步起 / 需重判”。
- **同机多开**：每个 Codex 对话用自己的 clone（repo、repo-2…），贴同一份启动 prompt 即可。

## 5. 出题侧算力与时间预算（共用机器必读）

出题可以慢，**不能把机器吃光**——执行机的 `harbor run` 每次只有 2 核，被出题侧挤占时校准会失真。规则见 [AGENTS.md](AGENTS.md#出题侧算力与时间预算)：每个出题会话同时至多 2 个计算进程、线性代数单线程（`OPENBLAS/MKL/OMP/NUMEXPR_NUM_THREADS=1`）、容器 `--cpus 2 --memory 4g`；单次运行 ≤ 10 分钟，单题 ≤ 90 分钟（超时记“暂缓”，不算否决），单轮 ≤ 3 小时。

并发容量粗估：每个 `harbor run` 约 2 核 / 4 GB，槽位数 ≈（Docker 内存 GB − 2）÷ 4；Windows 要开页面文件，WSL 在 `.wslconfig` 里给足内存。

## 6. 我们是怎么开发、怎么优化的

每次改动都记在 [决策表](flows/tb-science/README.md#已定决策)（含起因）。几条主线：

1. **先定唯一判断依据**：多份原始要求冲突取交集合并成一份要求书；Skill 只规定输入、输出、步骤、判据，判据一律链接要求书，不另写规则。
2. **出题与校准分离**：出题侧写可运行草稿（参考解得 1 分、每个“合理简化”得 0 分、多种子推导容差）；执行机只管容器化、隔离、校准。校准唯一入口是 `harbor run`，构建会话自己不做题。
3. **难度靠数据驱动**：[calibration-models.md](flows/tb-science/calibration-models.md) 记难度带与模型画像；[对抗出题规范](flows/tb-science/adversarial-design.md)把“GPT 5.6 实际怎么做题”沉淀成设计手法，`复审改难` 持续追加对手档案。
4. **规则按事实调整**：成功轨迹深度改为“至少一条 ≥ 60 步”；弱模型条件取消；审查精简为 G1–G8；出题否决只能引要求书红线原句。
5. **执行器推进深度**：同一障碍连续 ≥ 6 小时或 ≥ 10 种办法才允许标 `阻塞`；每台机器维护环境经验库（`environment-check.md` + `env-kit/`），同类机器不再重复踩坑。
6. **并发规则是被事故逼出来的**：多个会话同时 `启动选题` 产生重复提示词，才有了推送即占有、`claims/` 租约和单一回报格式；机器被出题侧吃满，才有了算力与时间预算。

## 7. 常见坑

- **WSL / 内核**：Harbor 0.25.0 的离线任务需内核含 `CONFIG_NFT_FIB_INET`；Windows 升级 WSL 到 ≥ 3.0.3，macOS 用 Docker Desktop ≥ 4.86（启动 prompt §0 有自检命令）。
- **换行**：Windows 上保持 `.gitattributes` 的 LF，台账用 LF 追加，避免 rebase 假冲突。
- **泄漏红线**：`drafts/` 含参考解与真值；构建镜像只从 `package/<task_id>/environment/` 取上下文，整个仓库和 `.env` 不得进容器。
- **同一台机器不要共用一份 clone**，否则撞 git 锁。
- **BLAS 线程超订**：多会话并发时多线程 BLAS 会让线性代数慢两百多倍，务必单线程。

## 8. 关于本开源仓库

本仓库是维护者私有生产仓库的**净化同步版**：只含流水线本身（规则、Skill、模板、脚本、空台账），不含任何题目与运行记录。私有仓库更新后，规则类变更会同步到这里。贡献与反馈请开 Issue；许可与第三方材料说明见 [LICENSE](LICENSE)、[NOTICE.md](NOTICE.md)。
