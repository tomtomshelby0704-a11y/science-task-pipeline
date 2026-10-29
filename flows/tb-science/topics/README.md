# 选题

- `<题号>.md`：一道可执行的题，格式见 [模板](../../../skills/tb-topic/templates/topic.md)；由 [tb-research](../../../skills/tb-research/SKILL.md)（素材加工或自主研究）或 [tb-harden](../../../skills/tb-harden/SKILL.md)（改难）写入，[tb-run](../../../skills/tb-run/SKILL.md) 读取。GPT Pro 的回复不直接进这里，先进 [materials/](../materials/README.md)。

- `queue.md`：执行队列，只列 `待执行` 的题，执行机 `持续执行` 从顶部领。`研究出题` / `复审改难` 全量重排，`审查` 退回的题置顶。

题号格式 `tbs-NNN`，从 `tbs-001` 起顺延。来源写在头部“来源对话”：`GPT Pro 素材 mat-XXX，Claude 加工`、`Claude 研究`（均来自 tb-research）、`改难自 tbs-XXX`（tb-harden）。审查退回的题头部会多一行 `退回`，状态为 `待执行（退回，<执行机>）`，只有该执行机会领。
