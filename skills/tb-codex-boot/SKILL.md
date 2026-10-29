# tb-codex-boot：构建执行单元

## 触发口令

- `构建执行单元 <机器名>`：生成一段 Codex 启动 prompt。机器名用于台账里的“执行机”列，例如 `win-a`、`win-b`、`mac-a`。人类可附系统：`构建执行单元 mac-a macOS`。

## 目的

把一个新开的 Codex 对话变成本项目的标准执行单元：它自己把 Docker、Harbor 等环境装好并通过两条验收，知道去哪里拿要求书和 Skill、题包放在本机哪里、强模型怎么调用，就绪后在 [registry.md](../../flows/tb-science/boot/registry.md) 登记自己，之后只听四条口令：`持续执行`、`执行题目 <题号>`、`审查`（本机全部未审题）和 `审查 <题号>`。

## 输入

| 来源 | 用途 |
| --- | --- |
| [templates/boot-prompt.md](templates/boot-prompt.md) | 启动 prompt 模板 |
| `git remote get-url origin` | 仓库地址，填 `{{REPO_URL}}` |
| 人类给的机器名 | 填 `{{MACHINE}}` |

## 输出

- `flows/tb-science/boot/<机器名>.md`：填好仓库地址和机器名的启动 prompt，**模型占位符仍保留**，commit 并 push 到 `main`。
- Codex 就绪后自己向 `flows/tb-science/boot/registry.md` 追加一行并刷新看板。
- 人类把文件内容复制出来；`{{WEAK_MODEL_NAME}}`、`{{WEAK_MODEL_TIER}}`、`{{WEAK_MODEL_BASE_URL}}`、`{{WEAK_MODEL_API_KEY}}` 可留空（2026-10-29 起校准不跑弱模型，只有出题机做预筛时才用）；`{{OPENAI_API_KEY}}` 有就填、没有留空（复用本机 Codex 登录态）。再贴进新的 Codex 对话。真实值不进仓库。

## 步骤

1. 读模板，替换 `{{REPO_URL}}`、`{{MACHINE}}`、`{{WORKDIR}}`。`{{WORKDIR}}` 默认：Windows `D:\tbs-work\<机器名>`，macOS / Linux `~/tbs-work/<机器名>`；人类另有指定则按指定。模板本身跨平台，§0 的系统前提两种都列着，由 Codex 按本机取用。
2. 写入 `flows/tb-science/boot/<机器名>.md`，commit，`git pull --rebase origin main`，push。
3. 回报人类，链接按 AGENTS.md“回报链接”规则：`raw/main/flows/tb-science/boot/<机器名>.md` 链接（打开后全选复制）；“替换模型占位符后整段贴进新 Codex 对话”；“贴完后 Codex 会回报‘执行单元 <机器名> 就绪’”。

## 完成判据

- 输出文件中只剩模型占位符未填；`grep` 不到真实 key。
- Codex 贴入后能自行装齐环境、通过 §0 三条验收、clone 仓库、读完指定文件、在 registry.md 登记并回报就绪。
