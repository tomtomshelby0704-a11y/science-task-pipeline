# {{PACKAGE}}

> 题号 {{TOPIC_ID}} · 任务 `{{TASK_ID}}` · 版本 v{{VERSION}} · 执行机 {{MACHINE}}。本文件由 `skills/tb-run/scripts/pack_delivery.py` 按交付规范 `skills/tb-run/delivery.md` 生成；第 2 节表格是脚本从轨迹和验证器输出算出来的，不是手填的。

## 1. 目录说明

| 路径 | 内容 |
| --- | --- |
| `README.md` | 本说明 |
| `MANIFEST.json` | 题号、版本、执行机、打包时间，以及包内每个文件的 SHA-256；证明全部材料属于同一任务版本 |
| `task/{{TASK_ID}}/` | 题包，目录结构与要求书 2.1“任务交付格式要求”一致。`solution/`、`tests/` 交付给评测系统，对解题 Agent 隐藏；参考解说明在 `solution/reference_solution.md` 与 `solution/solution_explanation.md` |
| `runs/calibration.md` | 校准记录：模型名单与层级、步骤计数定义、全部运行（含未入包的）、三项条件判定、结论 |
| `runs/index.csv` | 入包运行一览，每行一次 `harbor run` |
| `runs/<运行>/harbor/` | 该次运行的 Harbor 原生输出，原样未改：完整轨迹 `trajectory.json`、配置、结果、验证器输出 |
| `runs/<运行>/metadata.json` | 运行元数据与评测记录：模型准确标识、分组与层级、智能体框架及版本、系统提示词、工具、采样配置、执行预算、开始时间、用时、退出状态、任务与验证器版本、有效性、失败分类 |
| `runs/<运行>/summary.md` | 该次运行的逐步摘要与失败归因 |

运行命名：`weak-<k>` 弱模型组（2026-10-29 前的旧运行才有），`gpt56-<k>` GPT 5.6 Sol (max) with Codex，`gpt6-<k>` GPT-6 Astra with Codex；`<k>` 与执行机上的序号一致，`index.csv` 的 `local_run` 列是执行机上的原目录名。步数为 `trajectory.json` 中 `steps[source == "agent"]` 的条目数。

## 2. 真实轨迹总结

本包只收判定用的运行，即支撑三项条件与成功轨迹深度的、本版本上的有效运行。

{{RUN_TABLE}}

{{CONDITIONS}}

各次失败或成功的原因，见对应 `summary.md` 第 3 节；完整论证见 `runs/calibration.md`。

## 3. 未入包运行

未入包 {{N_OMITTED}} 次：旧版本、无效运行，以及多余的重复运行。它们完整保留在执行机 {{MACHINE}} 的 `{{LOCAL_RUNS}}` 下，摘要在仓库 `flows/tb-science/runs/{{TOPIC_ID}}/`，逐次列在 `runs/calibration.md` 的全部运行表里。

{{OMITTED}}
