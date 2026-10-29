# 01 合并规格

- **状态**：已完成（2026-10-28 用户确认要求书并同意合入 `main`）
- **目标**：把三份原始要求合成一份最终要求书，按真实做题顺序排列。只组合，不改写；发现冲突报告给用户。
- **输入**：用户在会话中上传的三份文件（甲方资料，不入库，只记哈希）：

  | 文件 | SHA-256 |
  | --- | --- |
  | 《TB science 数据质量标准》`TB_science___________1.md` | `3bda2d792f3ccab7eda0b7d4611817e547f301fbcee09115de85c4ecff8ef1a4` |
  | 《Terminal Bench Science 任务数据交付要求》`Terminal_Bench_Science_________1.docx` | `5e7d2a6184bcbad61a65cd85f2e2ee7c04cc5ddc05ef15333ff7e141ad9d9424` |
  | 《TB-Science 任务验收标准》中文版 `TB-Science________1.docx` | `0d8fdc083bd4c496a53f64d5904948ecb30dc6f3c7b5b90696da88b37797934b` |

- **输出**：[specs/tb-science-requirements.md](../../../../specs/tb-science-requirements.md)
- **所需 Skill**：无
- **前置步骤**：无
- **执行方法**：用 pandoc 把 docx 转成文本；按做题顺序分为总则加五个阶段（立项与设计 → 构建题包 → 验证与校准 → 质检与交付 → 批次验收），阶段下分章节，章节下放原文段落并标注出处。只对 C1、C2 两处冲突做合并，其余原文不改。
- **验证**：用脚本逐行比对三份原文。没对上的只有：原章节标题（改成〔出处 §编号〕标注）、docx 代码块的“Plain Text”标签，以及按 C1、C2 合并掉的 4 处原句（见下方“裁决”）。

## 发现的冲突

| 编号 | 内容 | 验收标准 §1.1 | 交付要求 §2 |
| --- | --- | --- | --- |
| C1 | 难度校准方式 | 强模型组任选一个模型成功 + 弱模型组任选一个模型失败；明确“不设置固定的四模型评测组合，不限制通过的模型数量，也不要求任何指定模型必须失败” | 固定用 GPT 5.6 Sol (max) with Codex，pass rate ≤ 2/4（即指定模型、4 次、通过上限）；为 0 时补 GPT-6 Astra (with Codex) 成功轨迹一条 |
| C2 | 成功轨迹步数 | 每条成功轨迹 ≥ 100 个智能体步骤，批次 P50 目标 150；与 token 无关 | Output tokens ≥ 65k 时 agent turns ≥ 60–70 即可；< 65k 时 ≥ 100。“60–70”本身也没说取哪个值 |

## 裁决（2026-10-28，用户决定）

- C1、C2 取两边要求的交集，合并后写入要求书，标〔合并〕：
  - C1：强模型组成功 + 弱模型组失败 + GPT 5.6 Sol (max) with Codex pass rate ≤ 2/4（为 0 时补 GPT-6 Astra 成功轨迹）。删除验收标准中“不设置固定的四模型评测组合，不限制通过的模型数量，也不要求任何指定模型必须失败”一句，它与 ≤ 2/4 直接矛盾。
  - C2：每条成功轨迹 ≥ 100 步，不分 token 档；交付要求中“≥ 65k tokens 时 ≥ 60–70 步”被更严的一档覆盖。
- 模型名称写法差异（“GPT 5.6 Sol (max)”与“GPT-5.6”）忽略，不视为冲突。

## 样例对照发现

用户提供的参考样例（甲方/第三方资料，不入库，只记哈希）：

| 文件 | SHA-256 |
| --- | --- |
| `terniquaternaria-passport.zip`（已通过的样例题包） | `dfe6fe4e63940b44eba041bd72f30dbe8c2d5f8e40c333771f210863d64163f5` |
| `terniquaternaria_multimodel_report.html`（该题的多模型运行报告） | `5b983f46af5b1dae4f2a810e37a8423b8719904df902f5afb09efefe6398a242` |
| `harbor-tasks-5_2.zip`（5 道题包 + 作者自检工具） | `201b64228668e59fc548a8ea7d9f70d21138f2c8b4a017a9ed2c3e7aa60bdefd` |

只做了静态阅读和 `tools/gate.py` 静态检查；样例中的 `solve.sh` 和自检脚本未运行（会话权限不允许执行外部代码）。

1. **目录格式与交付要求 §1 不一致。**（已决：2026-10-28 用户定为按《交付要求》§1。） 样例用的是 Harbor/TB-Science 官方格式：说明写在 `README.md`（Difficulty / Solution / Verification explanation、Relevant experience 四节），另有 `tests/Dockerfile`、`tests/test_outputs.py`。交付要求 §1 列出的 `solution/reference_solution.md`、`solution/solution_explanation.md`、`tests/verifier.*`、`tests/fixtures/`、`environment/requirements.txt`、`environment/resources/` 在样例中都没有。样例的 `tools/gate.py` 引用了“Appendix A / Appendix B.1”，仓库里没有这份文件。
2. **样例的模型校准达不到合并后的 C1、C2。** 报告中用的是 direct chat-completion harness，一次回答出结果，没有 agent 步数；模型是 gpt-5.5、Claude Opus 4.7、Kimi K2.6、DeepSeek V4 Pro，没有 GPT 5.6 Sol 跑 4 次的记录。大部分失败来自限流、接口不兼容和超时，按验收标准不算有效失败。所以样例只能作为题包、验证器写法的参考，不能作为校准的参考。
3. **样例有未填项。** `license`、`author_name`、README 的 `Relevant experience` 都是 `<FILL>`；Dockerfile 未按 digest 固定；terniquaternaria 的 `expert_time_estimate_hours = 1.0`，低于 gate.py 要求的 ≥ 2。
4. **harbor-tasks-5 的自检记录无效。** `metadata/selfcheck.json` 中全部为 `missing`，`all_passed: false`。原因是 `selfcheck.sh` 里写的任务名不带 `taskN-` 前缀，和目录名对不上（读代码得出，未运行验证）。但各题 README 写着“Oracle verified three consecutive times”，与质量标准 §8“不能手填通过”相冲突，需要重新跑出真实记录。
5. **领域范围。** harbor-tasks-5 中 breach-cost-model、pledge-loss-waterfall（Operations）、preview-handoff-auditor（Software）不属于验收标准 §1.4 的五个科学领域。terniquaternaria 是原创数学谜题，不是真实科研流程，但它已通过，说明甲方对质量标准 §1“源于真实科研问题”执行得比较宽松。

## 下一步

- 无。后续工作见 [流程台账](../../README.md)。
