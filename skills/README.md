# 可复用 Skill

每项能力使用独立目录 `skills/<名称>/`，以 `SKILL.md` 为入口，固定六节：触发口令、目的、输入、输出、步骤、完成判据。模板放在 `templates/`，代码放在 `scripts/`。判据只链接 [要求书](../specs/tb-science-requirements.md)，不另写规则。

| Skill | 口令 | 执行方 | 产出 |
| --- | --- | --- | --- |
| [tb-topic](tb-topic/SKILL.md) | `启动选题`、`登记素材 <素材号>` | 任意 Agent | GPT Pro 提示词；登记贴回的素材（不是题目） |
| [tb-codex-boot](tb-codex-boot/SKILL.md) | `构建执行单元 <机器名>` | 任意 Agent | Codex 启动 prompt |
| [tb-run](tb-run/SKILL.md) | `持续执行`、`执行题目 <题号>` | Codex 执行单元 | 本机题包、证据；台账 1 行；`runs/<题号>/` 运行摘要 |
| [tb-review](tb-review/SKILL.md) | `审查`、`审查 <题号>` | tb-run 第 10 步自动起的独立 `codex exec` 进程；补审时在执行机上另开 Codex 对话 | 审查详情（退回项分校准类 / 材料类）；台账 2 行；补审退回的题回队列顶 |
| [tb-research](tb-research/SKILL.md) | `研究出题` | 出题侧 Claude（云端或本地，手动或定时） | 一轮 ≥ 3 件：先给队列顶部 ≤ 3 道旧题回补首发解检验；素材逐候选按[对抗出题规范](../flows/tb-science/adversarial-design.md)成题（头部 `对抗清单`，草稿含 `first_shot.py` 实跑 0 分）或否决，不足再自主研究，待执行满 50 停；重排 `queue.md`（对抗档在前） |
| [tb-quick](tb-quick/SKILL.md) | `快速出题` | 出题侧 Claude（云端或本地，可多开） | 和 tb-research 同输入同输出、同判据，但不写草稿、不实跑、不探针；对抗设计照做，首发解写成算法交执行机闸门实跑；一轮 ≥ 5 道，题头部“对抗清单”“草稿：无” |
| [tb-harden](tb-harden/SKILL.md) | `复审改难` | 出题侧 Claude（云端或本地，手动或定时；可多开） | `runs/scores.md` 打分行与对手档案行；改难后的新选题（有旋钮的拧旋钮，没有的全套对抗设计）置顶队列；过程中占用 `claims/` |
| [tb-prescreen](tb-prescreen/SKILL.md) | `预筛 <题号>`（写题时自动） | 本机有弱模型 key 和 Docker 的 Agent | 出题阶段快速探针：一次性探针（DS 写一份脚本跑一次，最多修两次），结果进 `drafts/<题号>/prescreen.md` 与题头部 `预筛` 行；被轻易解出就改设计 |
| [tb-board](tb-board/SKILL.md) | `刷新看板` | 任意 Agent | `flows/tb-science/board.md` |

依赖顺序：tb-topic（素材）→ tb-research 或 tb-quick（成题，共用素材锁）→ tb-run → tb-review（退回回到 tb-run）；tb-harden 读 `runs/` 写 `topics/`，回到 tb-run；tb-prescreen 读 `drafts/` 写题头部，有 key 时被 tb-research、tb-harden 第 5 步调用（写题循环的一环），结果也用于 tb-research 第 6 步排序；tb-board 被以上各 Skill 的登记步骤调用；tb-codex-boot 独立，为 tb-run 准备执行单元。
