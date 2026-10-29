# 证据清单 · {{TASK_ID}}

- **任务版本**：v{{VERSION}}（题包任何改动后加 1，全部证据对应同一版本）
- **执行机**：{{MACHINE}}
- **题包路径**：{{PACKAGE_PATH}}

下表逐行对应要求书 [4.2 每条高质量数据应附的最小证据](../../../specs/tb-science-requirements.md#42-单题交付证据)。“状态”只填 `已提供` 或 `待验证`，不得把计划写成结果。

| 材料 | 文件路径 | 状态 | 备注 |
| --- | --- | --- | --- |
| 任务说明 | `package/<task_id>/instruction.md` | | |
| 来源与数据记录 | `package/<task_id>/solution/solution_explanation.md` 来源节；数据加工记录路径 | | |
| 可运行题包 | `package/<task_id>/` | | |
| 正确性证据 | `solution/reference_solution.md`；需求到测试映射；替代解与错误解记录路径 | | |
| 工程验证记录 | `evidence/engineering.md` | | |
| 模型运行记录 | `evidence/calibration.md`；`runs/` | | |
| 评分可靠性记录 | 攻击检查、合法解回归、评分稳定性记录路径 | | |
| 复核结论 | 由 tb-review 产出，见仓库 `flows/tb-science/reviews/<题号>.md` | | |

## 校准结论

（摘自 `evidence/calibration.md`：达标 / 不达标，及三项条件与步数的结果）

## 未完成与待验证项

（如实列出）
