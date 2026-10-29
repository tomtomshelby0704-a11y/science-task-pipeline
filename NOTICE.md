# NOTICE

## 许可范围

本仓库中由维护者原创的内容（Skill、流程说明、脚本、模板、文档）按 [CC BY-NC-SA 4.0](LICENSE) 发布：可以署名、非商业地使用、修改、再分发，衍生作品需以相同方式共享。**不得用于商业目的。**

## 第三方材料（不在本许可范围内）

下面两处包含第三方文件的转录原文，**版权与使用条件归原权利人所有，不适用本仓库的许可**：

| 位置 | 内容 |
| --- | --- |
| [specs/tb-science-requirements.md](specs/tb-science-requirements.md) | 《TB science 数据质量标准》《Terminal Bench Science 任务数据交付要求》《TB-Science 任务验收标准》三份文件的原文合并（按做题顺序重排，冲突处取交集，已在正文标注）。它是流水线各 Skill 唯一的判断依据，因此随仓库附上 |
| [flows/tb-science/steps/01-merge-specs/README.md](flows/tb-science/steps/01-merge-specs/README.md) | 上述合并的过程记录，含三份原始文件的名称与 SHA-256 |

如果你是这些文件的权利人，希望下架或改为链接，请开 Issue 说明，维护者会及时处理。使用者自行判断是否有权在自己的场景使用这些要求。

## 非官方声明

本项目是个人维护的流水线工具，与 Terminal-Bench、Harbor、OpenAI、DeepSeek、Anthropic 等项目或公司**没有隶属或背书关系**；文中出现的名称与商标归各自所有者所有。

## 不含的内容

仓库不包含任何题目、轨迹、运行记录、真实标注数据、密钥或凭据。弱模型等密钥只写在使用者本机的 `.env`（已被 `.gitignore` 忽略），不进仓库。
