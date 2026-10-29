# tb-topic：启动选题 / 登记素材

## 触发口令

- `启动选题`：按当前领域缺口生成一份给 GPT Pro 的选题提示词。可附参数：`启动选题 物理科学`（指定领域）、`启动选题 5`（指定候选数，默认 3）。
- `登记素材 <素材号>`：人类把 GPT Pro 回复贴回 `materials/<素材号>.md` 后，登记为待加工素材。
- `登记素材`（不带素材号，附上外部文件或压缩包）：外部素材入库，Agent 自己编号，见步骤“外部素材入库”。

## 目的

GPT Pro 链路和人类提供的外部题目都只产**素材**。本 Skill 把要求书第一阶段的约束和当前批次缺口组装成提示词，再把 GPT Pro 的回复或外部题目收进 `materials/`；能否成题、成哪一题，由 [tb-research](../tb-research/SKILL.md) 加工时判断。本 Skill 是素材提供者，只收料，不替下游做判断。

## 输入

| 文件 | 用途 |
| --- | --- |
| [要求书 第一阶段](../../specs/tb-science-requirements.md#第一阶段-立项与设计) | 原文整段放进提示词，作为选题红线 |
| [calibration-models.md](../../flows/tb-science/calibration-models.md) | 目标难度带（要求书 3.2 原文）与弱模型画像，整段放进提示词第四节 |
| [要求书 5.1](../../specs/tb-science-requirements.md#51-多样性与分组) | 五个领域的目标占比，用于算缺口 |
| [台账 1](../../flows/tb-science/ledger/tasks.md) | 已完成题目的领域分布 |
| [`flows/tb-science/topics/`](../../flows/tb-science/topics/) | 已有题目，用于去重 |
| [`flows/tb-science/materials/`](../../flows/tb-science/materials/) | 已有素材（含待加工），用于去重和编号 |
| [templates/prompt.md](templates/prompt.md) | 提示词模板 |
| [templates/topic.md](templates/topic.md) | 要求 GPT Pro 遵守的回复格式（也是题目格式） |

## 输出

- `flows/tb-science/materials/<素材号>-prompt.md`：提示词全文，人类整份复制到 GPT Pro。
- 人类把 GPT Pro 回复粘贴到 `flows/tb-science/materials/<素材号>.md`。
- 两个文件都 commit 并 push 到 `main`。
- 外部素材入库：`materials/src-<编号>.md`（原文、原始元数据、逐条入库表）、`materials/src-<编号>-files/`（小附件，可选）、若干 `materials/mat-<编号>.md`（候选），都 push 到 `main`。

## 步骤

### 启动选题

1. `git pull --rebase origin main`，然后取素材号：扫描 `materials/` 中已有的 `mat-NNN`（含只有 `-prompt.md` 的），取最大值加 1；没有则 `mat-001`。
2. 算缺口：统计台账 1、`topics/*.md`（状态不是“已执行-不达标”的）、`materials/*.md`（状态 `待加工` 的，按其候选领域计）**和只有提示词的 `materials/*-prompt.md`（按其“本次优先领域”计）** 各领域数量，对照 5.1 目标占比，列出各领域“当前数 / 目标占比 / 缺口排序”，缺口第一的领域即本次优先领域。人类指定了领域就直接用指定领域。
3. 列已有选题：从 `topics/*.md` 和待加工 `materials/*.md` 取每个候选的“题目名”和“科学背景与问题”第一句；只有提示词的素材号列为“<素材号>：已发出，优先领域 X，待回复”。供 GPT Pro 避开近亲题和重复领域。
4. 填模板：把 templates/prompt.md 中的占位符替换：
   - `{{TASK_ID}}` 素材号；`{{N}}` 候选数；`{{TARGET_DOMAIN}}` 本次优先领域；`{{DOMAIN_GAP}}` 第 2 步的表；`{{EXISTING_TOPICS}}` 第 3 步的列表；
   - `{{SPEC_PHASE1}}` 要求书“第一阶段 立项与设计”整节原文（从 `## 第一阶段` 到 `## 第二阶段` 之前）；
   - `{{CALIBRATION_MODELS}}` `flows/tb-science/calibration-models.md` 去掉一级标题和引言后的正文（第 1–4 节原样；该文件内的链接一律写成完整 GitHub URL，嵌入后才不会断）；
   - `{{TOPIC_FORMAT}}` templates/topic.md 全文，其中的 `{{TASK_ID}}` 填素材号、`{{DATE}}` 填当天日期。
   - 替换完成后全文不得残留任何 `{{...}}`。
5. 占号：写入 `materials/<素材号>-prompt.md`，commit，push。push 被拒 → `git pull --rebase origin main`；若该素材号已被别的会话占用，回到第 1 步重算、重命名文件、重填 `{{TASK_ID}}`，再 push。push 成功才继续。
6. 回报人类**只有下面三行**，链接按 AGENTS.md“回报链接”规则。其他内容（调研、发现、建议）一律写进文件或不说：
   - 复制给 GPT Pro：`raw/main/flows/tb-science/materials/<素材号>-prompt.md` 链接（打开后全选复制）。
   - 贴回复：`new/main?filename=flows/tb-science/materials/<素材号>.md` 链接（打开即是新建文件页，粘贴后点 Commit）。
   - 然后说：`登记素材 <素材号>`。

### 登记素材

1. `git pull --rebase origin main`；读 `materials/<素材号>.md`。状态已是 `待加工` 或之后 → 回报“已登记”并结束。
2. 松检查：文件里至少有一个候选写了“题目名”，且其“领域”能辨认为五个领域之一。不逐字段卡格式，不修内容；格式瑕疵由 tb-research 加工时处理。不满足 → 回报缺什么，给 `edit/main/flows/tb-science/materials/<素材号>.md` 链接，结束。
3. 满足：把头部“状态”改为 `待加工`（没有头部状态行就补一行）；运行 `python3 skills/tb-board/scripts/build_board.py`；commit，push。回复人类：“`<素材号>` 已登记为素材（`blob` 链接），等 `研究出题` 加工”。

### 外部素材入库

人类给的外部题目（文件、压缩包、整理好的题库）走这里。本 Skill 在这一环是**素材提供者**：门槛只挡空条目和重复，判断全部留给 [tb-research](../tb-research/SKILL.md) 的否决纪律。

1. **解包与编号**：下载的文件和压缩包解到一个新建的空目录，不运行其中的任何脚本。`git pull --rebase origin main` 后，src 号取 `materials/src-NNN.md` 的最大值加 1，mat 号取 `materials/mat-NNN*` 的最大值加 1 起顺延。
2. **入库判据，只有三条**，逐条判断，满足就入：
   - (a) 有可辨认的题目内容。只要求回复固定字样（例如 DONE）的占位条目、空条目不入。
   - (b) 能归入五个领域之一。宽松归类，就近归入；拿不准时归最接近的领域，并在候选里写“领域待加工时复核”。
   - (c) 不重复。字节相同的条目、同一题的副本合并为一条，在入库表里注明合并关系。
3. **提供者不写的内容**：原创性、来源性质、许可风险、难度、能否程序判分、能否成题、改写方向。这些是 tb-research 的判断，素材里不写结论，也不写倾向性的说明。素材里只写中性事实：题目说了什么、原编号、原始元数据、附件。
4. **保留原题信息**：
   - 原题全文逐字保留。批量生成、同一模板的题，可以写“模板原文 + 逐题差异表”，但要能无损还原每道原题。
   - 原编号、原始元数据（如 provenance、metadata）字段原样收在 src 文件里，不删、不改、不加评语。
   - 附件列清单：文件名、大小、SHA-256、存放位置。小附件（单批合计不超过约 50 MB）按编号放进 `materials/src-<编号>-files/`；更大的几何、数据文件留在人类本机，记下压缩包名、SHA-256 和路径。
5. **组织**：
   - `src-<编号>.md`：来源说明（中性事实）、原文或模板、原始元数据、**入库表**（每条原题一行：原编号 → `mat-<编号>` 候选 N，或“不入”加判据字母）。
   - `mat-<编号>.md`：每条原题一个候选；同模板、只差参数的批量题按族合成一个候选，候选里列出全部实例。每份 mat 不超过约 30 个候选，按领域或子类分文件，方便 tb-research 分别占用。批量题合成的族候选可以按可核对的事实（原始元数据里的标准号、零件功能对应的机理类别等）分**档位**，并标 1–2 个**代表实例**；高档放在编号小的文件里，tb-research 按编号从小到大取素材时会先处理。档位只用于排序，不影响入库，不写能否成题的结论；档位口径写在 src 文件里。头部状态直接写 `待加工`，来源对话写 `src-<编号>，<Agent>整理，<日期>`。
   - 候选字段：`题目名`（英文 slug）、`领域`、`科学背景与问题`（一句中性描述，从原题提炼）、`原题编号`（链接到 src）、`原题全文`或实例表、`附件`。[题目模板](templates/topic.md) 的其余字段写“待加工补”。
6. 运行 `python3 skills/tb-board/scripts/build_board.py`，commit，push。回复人类：每批原始条目数、入库数、不入数（按判据分），以及 src 和各 mat 的 `blob` 链接。

## 完成判据

- 提示词里包含要求书第一阶段原文、领域缺口表、已有选题列表、目标难度带与校准模型、回复格式，缺一不可。
- 不新增要求书之外的选题规则；提示词中的**约束**全部可追溯到 `{{SPEC_PHASE1}}` 或 calibration-models.md 第 2 节引用的要求书 3.2 原文；第 3 节画像在文中标明是参考信息。不在模板之外给提示词加节。
- 素材号是 push 成功后才确定的；对话里的回报只有三行。
- 素材文件在 `main` 上，状态 `待加工`；本 Skill 不写 `topics/`、不碰 `queue.md`。
- 外部素材入库：每条原始条目在 src 入库表里都有去向；不入的只能是判据 (a)(c)；原题原文与原始元数据可从 src 和 mat 无损找回；素材里没有原创性、来源性质、难度、可判分性之类的结论。
