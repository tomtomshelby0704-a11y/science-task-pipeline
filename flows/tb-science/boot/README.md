# 执行单元启动 prompt

每台执行机一个文件 `<机器名>.md`，由 [tb-codex-boot](../../../skills/tb-codex-boot/SKILL.md) 生成。文件里弱模型几项是占位符，2026-10-29 起可留空（校准不跑弱模型）；真实 key 不进仓库。

`registry.md`：已就绪执行机的登记表，由各机 Codex 自己追加。

`cloud-research.md`：云端定时任务"研究出题"的 prompt，人类在 claude.ai 定时任务界面建任务时粘贴（仓库、模型、Effort、频率在界面里选）。

`<机器名>-environment.md`：该执行机“坑与修法”表的脱敏副本，由执行机在坑表有新行时推上来（格式见 [tb-run](../../../skills/tb-run/SKILL.md)“推进深度”第 6 条）。新机器或新对话装环境前先读同系统机器的这份，修过的坑不再 debug。
