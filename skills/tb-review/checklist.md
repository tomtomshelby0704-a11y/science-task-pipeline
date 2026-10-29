# 审查条目表

只收《验收标准》《交付要求》里的硬性条款，共 8 条；不满足才退回。《质量标准》的其余验证证据不逐条审：执行单元在 `evidence/README.md` 如实标“待验证”即可（要求书 [4.2](../../specs/tb-science-requirements.md#42-单题交付证据)“缺少证据的项目标为待验证”）。判定时点开链接读原句，不加严。

**宽严原则**：退回只认《验收标准》《交付要求》，后者含官方 39 项 rubric 及其 guidance 原文（[task-implementation.toml](https://github.com/harbor-framework/terminal-bench-science/blob/main/rubrics/task-implementation.toml)）。《质量标准》某段比官方 rubric guidance 严时，按官方判。例：要求书 1.2 写“题面应明确数值容差”，但官方 #2 明确不要求公开阈值，所以不据此退回。同一根因只在一条 G 下计一次，其他条写“同 Gx，不重复计”。

审查只读这几样：`check_delivery.py` 的输出、`instruction.md`、题文件的“相似性自查”、`task.toml` 来源字段，以及 `evidence/` 下 `engineering.md` 的汇总、`calibration.md` 的名单与结论、`rubric.md` 中不通过的行。

| 编号 | 条款 | 要求书依据 | 怎么判 |
| --- | --- | --- | --- |
| G1 | 交付格式、防泄漏、运行记录字段、三项条件、成功轨迹深度、材料属于同一版本 | [2.1 任务交付格式要求](../../specs/tb-science-requirements.md#21-题包格式与运行环境)〔交付要求 §1〕、[轨迹与运行记录](../../specs/tb-science-requirements.md#轨迹与运行记录验收标准-12)、[校准结果要求](../../specs/tb-science-requirements.md#校准结果要求合并验收标准-11--交付要求-21)、[成功轨迹深度](../../specs/tb-science-requirements.md#成功轨迹深度合并验收标准-11--交付要求-22) | 对交付压缩包跑 `python3 skills/tb-run/scripts/check_delivery.py <zip>`，输出 `ok` 即通过；`FAIL` 行原样抄进详情 |
| G2 | 不复制或轻度改写已有基准任务；来源明确、许可适当 | [1.1 原创与来源](../../specs/tb-science-requirements.md#11-选题科学问题真实原创)〔验收标准 目的与范围〕 | 题文件“相似性自查”与 `task.toml` 的 `source_repo`、`license`，各写一句结论。未见复制或轻改的证据即通过；缺“相似性自查”段属材料类，补写即可 |
| G3 | 指令清晰、完整、无矛盾；数值容差及随机性评测规则预先声明 | [2.2 指令与验证一致、验证可靠](../../specs/tb-science-requirements.md#22-验证器与评分)〔验收标准 §1.3〕 | 只读 `instruction.md`（及其指明的公开资料）。以下都满足即通过：点名了**每一个**判分指标；写清交付物的路径与格式；判分含随机性时说明随机来源或判定方式；指令与验证不矛盾。**不要求公开阈值数值**（官方 #2 well_specified：“State the metrics; withhold the numbers”；#16 同）。只有某个判分指标完全没提到，或指令与验证矛盾，才退回。**粒度**：“判分指标”指被拿来和参考比对、或被判对错的那个量或产物，如事件表、状态、恢复时间、曲线。下面这些是判分细节，不必写出：汇总方式（中位数、P90、平均偏差）、阈值，以及同一比对下的细分口径（精确率与召回率、匹配窗口、最少匹配比例）。题面要求交付、显然要求正确的量，判它对错也算已提到。判不准时用官方的标准：两位合理的审查者按题面能把候选解排出同样的顺序，就算点名清楚。“预先声明”指校准前冻结在题包里、事后不收紧，不是必须写给作答模型看 |
| G4 | 能在干净环境中，用已记录的依赖、数据版本和资源配置独立运行 | [2.1 环境可复现](../../specs/tb-science-requirements.md#21-题包格式与运行环境)〔验收标准 §1.3〕 | `engineering.md` 有一次从干净环境构建并运行的记录 |
| G5 | 验证器接受已知正确解，拒绝空解、代表性错误解及绕过解；模型不得访问隐藏答案 | [2.2 指令与验证一致、验证可靠](../../specs/tb-science-requirements.md#22-验证器与评分)〔验收标准 §1.3〕 | `engineering.md` 有 oracle 得 1、空操作得 0、至少一个错误解或绕过解得 0 的实测记录；隐藏答案不进作答环境由 G1 的泄漏检查兜底 |
| G6 | 校准前登记强模型组名单（2026-10-29 起条件 B 取消，不跑弱模型；旧版本登记了弱模型的，核其为 Tier 1.5 或 Tier 2） | [3.2 校准分组](../../specs/tb-science-requirements.md#32-模型校准与运行记录)〔验收标准 §1.1〕 | `calibration.md` 名单表 |
| G7 | 无效结果不作校准证据 | [运行独立与无效结果](../../specs/tb-science-requirements.md#运行独立与无效结果验收标准-13)〔验收标准 §1.3〕 | `calibration.md` 判定所引运行都是有效运行；入包运行的有效性 G1 已核对 |
| G8 | 官方 39 项 rubric；不影响科学任务核心、训练效果的无关紧要不通过项可以驳回 | [4.1 官方 rubric](../../specs/tb-science-requirements.md#41-质检官方-rubric)〔交付要求 §3〕 | 只看 `rubric.md` 不通过和“建议驳回”的行，每行按官方该条 guidance 原文复判，不比原文严。只有**核心项**在官方口径下仍不通过、且影响科学核心或训练效果，才退回。核心项：verifiable、well_specified、solvable、scientifically_grounded、outcome_verified、anti_cheat_robustness、task_security、functional_verification、test_instruction_alignment、essential_difficulty、ground_truth_provenance、deterministic_reproducible、verifier_execution_isolation。其余项（格式、仓库流程、文档质量类，如 ctrf_reporting、task_readme、typos、category_and_tags、expert_time_estimate、artifact_efficiency）一律直接驳回，写一句理由。与 G2–G7 同根因的写“同 Gx，不重复计” |

**退回项类别**：每个退回项都标一个类别，供 [tb-run 第 10 步](../tb-run/SKILL.md) 决定修不修。
- `校准类`：只有新跑模型才能满足。包括 G1 中关于三项条件、成功轨迹深度、运行次数或有效性的 FAIL；G6 名单未在校准前登记；G7 去掉无效运行后条件不再成立。
- `题面类`：要修就得改作答可见内容或判分，即 `instruction.md`、`environment/`、`tests/`。改了就必须重新校准，可能毁掉已达标的轨迹。所以对**已有达标版本**的题标这一类之前，必须引《验收标准》《交付要求》或官方 rubric guidance 原句，证明现版本确实不满足；只引《质量标准》不够。拿不出原句就判通过或驳回。
- `材料类`：其余一切，即只动 `evidence/`、`solution/*.md`、`task.toml [metadata]`、运行的 `metadata.json` / `summary.md` 就能修的。

详情文件末尾固定两段短记录，各不超过 5 行。它们回应《质量标准》§1、§2、§10，不单独作为退回依据；发现的问题落在 G2–G8 的，按对应条退回：

1. **不看参考解的独立审题**：先只读 `instruction.md` 和作答可见资料，写下仅凭题面能否确定算什么、交什么、按什么判。
2. **独立领域复核**：科学上是否成立；复核者写“AI，独立会话，未参与出题”。
