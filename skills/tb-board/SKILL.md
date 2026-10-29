# tb-board：刷新看板

## 触发口令

- `刷新看板`：重新生成 [flows/tb-science/board.md](../../flows/tb-science/board.md) 并推到 `main`。其他 Skill 在登记步骤里也会自动调用本脚本，人类一般不需要单独说。

## 目的

给人类一个唯一的看结果入口。看板是从台账、选题、队列和运行摘要**派生**出来的静态页面，事实来源仍是两个台账；看板只负责把它们汇成一页。

## 输入

| 文件 | 用途 |
| --- | --- |
| `flows/tb-science/topics/tbs-*.md`、`*-prompt.md` | 每题状态、来源、起始候选、各候选题目名与领域 |
| [queue.md](../../flows/tb-science/topics/queue.md) | 执行队列 |
| [台账 1](../../flows/tb-science/ledger/tasks.md)、[台账 2](../../flows/tb-science/ledger/reviews.md) | 执行机、校准结果、审查结论 |
| `flows/tb-science/runs/<题号>/calibration.md` | 三项条件判定、运行次数（存在时） |
| [runs/scores.md](../../flows/tb-science/runs/scores.md) | 复审打分（存在时） |

## 输出

- `flows/tb-science/board.md`：总览计数（选题数、待执行、执行中含机器名、阻塞、达标、不达标、审查通过/退回）、执行队列、每题一行（领域、来源、状态、执行机、校准结果、A/B/C、运行摘要链接、审查结论）、复审打分表。

## 步骤

1. `git pull --rebase origin main`。
2. 在仓库根运行：

   ```
   python3 skills/tb-board/scripts/build_board.py
   ```

   运行环境：python3 ≥ 3.9，仅标准库，无需安装。输出一行 `board.md written: N topics, M ledger rows, K queued`。
3. commit `flows/tb-science/board.md`，push。rebase 时 `board.md` 冲突：不手工合并，重跑脚本覆盖后继续。
4. 回报一行：看板的 `blob` 链接。

调用约定（其他 Skill）：tb-run 第 9 步、tb-review 第 5 步、tb-topic 登记第 3 步、tb-research、tb-harden 在各自最后一次 commit 前运行第 2 步，把 `board.md` 放进同一个 commit。

## 完成判据

- `board.md` 生成时间晚于本次改动的台账/选题文件，且在 `main` 上。
- 总览里的计数与 `topics/` 文件状态、两个台账的行数一致。
