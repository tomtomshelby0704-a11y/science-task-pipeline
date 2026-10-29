# 交付压缩包规范

> 读者：执行单元（[tb-run](SKILL.md) 第 8–9 步）、审查（[tb-review](../tb-review/SKILL.md)）。本文只规定**交付物怎么组织**；里面每样东西该满足什么，一律以[要求书](../../specs/tb-science-requirements.md)为准，本文不加判据。参考样例（他人交付的题包与自检工具）只借鉴了服务要求书条款的做法，见文末。

## 1. 交付什么

每道**达标**题交一个压缩包，三样东西：标准题目、真实轨迹及相关记录、一份 README。

- 文件名：`<题号>-<task_id>-v<版本>.zip`，例如 `tbs-003-detector-deadtime-correction-v2.zip`。近达标档（判定里用 `N` 不用 `D`）由脚本自动加后缀 `-d50`，如 `tbs-003-detector-deadtime-correction-v2-d50.zip`，`MANIFEST.json` 写 `"depth_tier": "50"`；达标档不带后缀，写 `"60"`。包名、`depth_tier`、实际角色三者不一致，自检就 FAIL。同名 zip 已存在时脚本拒绝打包，不覆盖。
- 位置：执行机 `{{WORKDIR}}/tasks/<题号>/delivery/`。不进仓库：体积大，且包含 `solution/` 和 `tests/`。
- 生成方式：只用脚本，不手工拼目录。
  - 打包：`python3 skills/tb-run/scripts/pack_delivery.py`；
  - 自检：`python3 skills/tb-run/scripts/check_delivery.py`；
  - 用法写在两个脚本的文件头。打包脚本会先按自检的同一套规则校验，不通过就不生成 zip。
- 不达标题不打包。题被退回且改了作答可见内容或判分时，版本号加 1 重新打包；只修材料（作答可见内容与判分都不变）时按原版本号重打包，先把旧 zip 移到 `delivery/superseded/<时间>/`。旧 zip 一律留在本机，不删。
- **冻结**：达标版本的 zip 一旦自检 `ok`，就复制到 `{{WORKDIR}}/deliveries/frozen/` 并设为只读，SHA-256 写进题头 `达标版本` 行。之后不得覆盖、删除或重打包；需要新包时从冻结 zip 起步，再核对 MANIFEST（[tb-run“达标版本保护”](SKILL.md#达标版本保护)）。
- 审查通过后，最终 zip 复制一份到 `{{WORKDIR}}/deliveries/`（本机已通过交付的汇总目录），并在 `{{WORKDIR}}/deliveries/SHA256SUMS.txt` 追加一行（[tb-run](SKILL.md) 第 10 步）。

## 2. 目录结构

```text
<题号>-<task_id>-v<N>/
├── README.md            # 脚本按 templates/delivery-readme.md 生成
├── MANIFEST.json        # 题号、task_id、版本、执行机、打包时间、包内每个文件的 SHA-256
├── task/<task_id>/      # 题包：本机 package/<task_id>/ 原样
└── runs/
    ├── calibration.md   # 本机 evidence/calibration.md 原样
    ├── index.csv        # 每个入包运行一行
    └── <run_id>/
        ├── harbor/      # 该次 harbor run 的本机运行目录原样（除下面两个文件）
        ├── metadata.json
        └── summary.md
```

| 部分 | 要求 | 依据 |
| --- | --- | --- |
| `task/<task_id>/` | 目录树与要求书 2.1 完全一致，含 `environment/requirements.txt`、`environment/resources/`、`tests/verifier.*`、`tests/fixtures/`、`solution/reference_solution.md`、`solution/solution_explanation.md`。题目的解说只写在这两个 `solution/*.md` 里（模板见 [templates/](templates/)），不另写一份 | [2.1 任务交付格式要求](../../specs/tb-science-requirements.md#21-题包格式与运行环境) |
| `task.toml` 的 `[metadata]` | 必须有非空的 `license`、`source_repo`、`source_commit`、`ai_assistance`。字段名沿用参考样例；内容就是 4.2 要求写的许可、来源版本、AI 辅助方式 | [4.2 来源与数据记录](../../specs/tb-science-requirements.md#42-单题交付证据) |
| `runs/<run_id>/harbor/` | Harbor 原生输出，不改、不删，必须能找到 `trajectory.json` 和验证器 reward（`reward.txt` 或 `result.json`）。只删密钥：`auth.json` 和含密钥的 `.env` 不能出现在运行目录里 | [3.2 轨迹与运行记录](../../specs/tb-science-requirements.md#轨迹与运行记录验收标准-12)“完整轨迹” |
| `runs/<run_id>/metadata.json` | 按 [templates/run-metadata.json](templates/run-metadata.json) 填 3.2 的“运行元数据”和“评测记录”两行字段；文件引用一律写 `harbor/` 下的相对路径。每次运行结束立刻写，与 `summary.md` 同时写 | 同上“运行元数据”“评测记录” |
| `runs/<run_id>/summary.md` | 现有 [templates/trajectory.md](templates/trajectory.md) | 同上 |
| `runs/index.csv` | 由脚本生成。步数从 `trajectory.json` 实数，reward 从验证器输出读，不手填 | — |
| `MANIFEST.json` | 由脚本生成。任一文件改动，哈希即不符 | [4.2](../../specs/tb-science-requirements.md#42-单题交付证据)“这些材料应关联到同一任务版本” |

`run_id` 就是本机运行目录名去掉开头的 `<候选号>-`，如 `1-gpt56-3` → `gpt56-3`；不改号、不重排。`index.csv` 的 `local_run` 列保留原名。

## 3. 哪些运行入包：只放判定用的

入包的运行必须是**本版本上的有效运行**，并且被 `calibration.md` 的“条件判定”或“成功轨迹深度”引用。打包时用 `--use <本机运行目录名>=<判定>` 逐个点名，判定写下面四种的组合，用 `+` 连接：

| 判定 | 入包的运行 | 自检要求 |
| --- | --- | --- |
| `A` | 强模型组成功的那条 | 强模型组，reward = 1 |
| `B` | 可选（2026-10-29 起不再要求，不跑弱模型）：旧版本有弱模型有效失败时可点名 | 弱模型组，reward = 0 |
| `C` | GPT 5.6 Sol (max) with Codex 的 **4 次有效运行**，成功、失败都放，通过率要四次一起算 | 恰好 4 次 `gpt56-*`，通过数 ≤ 2；为 0 时必须另有一条 `gpt6-*` 成功并标 `A` |
| `D` | 至少一条 ≥ 60 步的成功轨迹 | reward = 1 且步数 ≥ 60 |
| `N` | 近达标档：没有 ≥ 60 步的成功轨迹时，最长那条 50–59 步的成功轨迹 | reward = 1 且 50 ≤ 步数 < 60；不能和 `D` 同时出现 |

同一运行可以兼几项，例如 `1-gpt56-2=A+C+D`。

其余运行不入包：旧版本上的、无效的、多余的重复运行。它们留在执行机原目录，摘要照旧进仓库 `flows/tb-science/runs/<题号>/`，并逐次列在 `calibration.md` 的全部运行表里，满足 3.2“保留所有校准尝试”。README 第 3 节由脚本列出它们。

## 4. README

脚本按 [templates/delivery-readme.md](templates/delivery-readme.md) 生成，执行单元不手改。固定三节：

1. **目录说明**：每个路径放什么、运行怎么命名、步数怎么数。
2. **真实轨迹总结**：入包运行表，含分组、模型、agent、步数、reward、用时、判定；再加三项条件与成功轨迹深度的判定表。表中数字由脚本从轨迹和验证器输出算出。
3. **未入包运行**：数量、本机位置、仓库摘要位置。

## 5. 自检查什么

`check_delivery.py` 失败时逐条打印 `FAIL`。下表每一项都对应要求书的一条：

| 检查 | 对应要求书 |
| --- | --- |
| 根目录只有 README、MANIFEST、`task/`、`runs/`；README 三节齐全 | 本规范 |
| 题包树与 2.1 一致 | 2.1 任务交付格式要求 |
| `environment/` 里没有与 `solution/`、`tests/` 内容相同的文件，也没有解答或判分文件名；Dockerfile 不 `COPY`/`ADD` 这两个目录 | 2.1“答案、隐藏测试和评审材料不能出现在作答可见的镜像层” |
| `task.toml` 有 4 个来源字段 | 4.2 来源与数据记录 |
| 每个入包运行都有 `trajectory.json`、验证器 reward、`metadata.json` 的全部字段；`index.csv` 的步数、reward 与原生输出一致 | 3.2 轨迹与运行记录 |
| 判定组合满足 A、B、C 与深度 | 3.2 校准结果要求、成功轨迹深度 |
| 入包运行全部有效，版本都等于包版本 | 3.2 运行独立与无效结果；4.2 同一任务版本 |
| 清单哈希逐一吻合，没有未登记的文件 | 4.2 同一任务版本 |

自检通过只说明结构和记录齐全，不代替 [tb-review](../tb-review/SKILL.md) 对科学质量的审查。

## 6. 借鉴了参考样例的什么

用户提供的样例（`terniquaternaria-passport.zip`、`harbor-tasks-5_2.zip`，哈希见 [01 合并规格](../../flows/tb-science/steps/01-merge-specs/README.md#样例对照发现)）只作参考，借鉴了三样：

- `metadata/file_manifest.json` 的 SHA-256 清单做法，对应这里的 `MANIFEST.json`；
- `task.toml [metadata]` 的来源字段名；
- `tools/gate.py` 的防泄漏思路。

样例里要求书没有的规定不采用：README 四节格式、`instruction.md` 固定结尾句、难度等级与专家耗时下限等。
