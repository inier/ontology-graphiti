# neat-freak Skill Context Bundle

> 技能聚合上下文包 — 会话同步时一次性加载，避免多文件分散读取。

## 技能元信息

| 字段 | 值 |
|------|-----|
| name | neat-freak |
| 用途 | 会话结束后知识库洁癖级同步 + 规范审计 |
| 触发词 | sync up / tidy up / 同步 / 整理文档 / 梳理 / 收尾 / 规范体检 / audit the rules 等 |
| 核心铁律 | 规则真身在层级 CLAUDE.md，永不复制规则内容；毕业去向只有 docs/ 或 CLAUDE.md |

---

## 一、核心原则速查（必读）

### 三层知识受众不重叠

| 位置 | 受众 | 职责 |
|------|------|------|
| Agent 记忆系统 | Agent 自己跨会话 | 个人偏好、非显而易见的项目事实 |
| 项目根 CLAUDE.md / AGENTS.md | 当前项目的 AI | 硬边界规则、红线、环境变量、路由清单 |
| 项目 docs/ + README.md | **其他人**（同事、下游、未来 AI） | 接入指南、架构、运维、交接 |

**判断一条信息进 CLAUDE.md？** → 下次 AI 写代码时没看到会不会犯错？会就进，不会就删/迁 docs。

### 毕业机制（记忆膨胀的唯一治本手段）

记忆满足任一条，内容并进 docs/ 或 CLAUDE.md，原记忆文件删或缩成一行指针：
- 同一主题教训反复出现 ≥ 3 次
- 讲的是「系统怎么工作」而非「踩过什么坑」
- 是「X 上线/落地」事件记录

**判据**：下一个接手的人（不只是我自己）需要知道吗？需要 → 属于 docs，不是 memory。

### 尺寸上限（超过部分 = 静默不加载）

| 文件 | 上限 |
|------|------|
| CLAUDE.md / AGENTS.md | ~300 行 / ~15KB（软） |
| MEMORY.md（记忆索引） | **≤200 行 且 ≤25KB（硬）** |
| 单条 memory | ~100 行（软） |
| 单份 docs/*.md | ~1500 行（软） |

**体检顺序**：先精简（破除膨胀）→ 再做本次增量同步。

---

## 二、执行流程（6步）

### 第零步：尺寸体检
`wc -l` + `wc -c` 测关键文件，记读数，超上限先精简。

### 第一步：盘点现状（强制枚举）
0. 平台探测（真实存在的才盘点）
1. 列 agent 记忆文件 + 读 MEMORY.md + 被引用 .md
2. 对每个项目：`ls` 根目录、`ls docs/`、读 README/CLAUDE.md/docs/*.md
3. 向上收集规则：项目根 → 工作空间根 → 全局的 CLAUDE.md/AGENTS.md
4. 回顾对话全文

输出内部文件清单：评估过 / 要改 / 不用改。

### 第二步：规范执行审计
**方向一：实践→规则**（提取可机械核验约定，按分级处置）
- 直接修：补软链、建脚手架、补 .gitignore、清已确认死引用
- 待拍板：重命名、删文件、合并分叉、规则漂移、规则矛盾、反复违规（建议 hook 化）

**方向二：规则本身有没有烂**
- 死引用（路径/项目存在吗？）
- 矛盾（上下级打架？）
- 漂移（规则说 X，所有项目做 Y 且良好 → 可能该改规则）

### 第三步：识别变更（用矩阵思考）
- 新增 API/路由 → 路由清单 + integration-guide + architecture Routes
- 新增/改名环境变量 → 环境变量表 + runbook + 下游 guide
- 新增大特性 → 以上全部 + architecture 新章节 + handoff
- **跨项目改动 → 上下游 docs 都要对齐**
- **退役/改名/下线 → grep 被删 symbol，清 docs+记忆 里的非载荷引用**
- **过期开放项扫描**：marker（待办/TODO/未决...）同行 + 绝对日期早于今天 → 强制处置

### 第四步：实际修改（用工具，不只是描述）
顺序：先 docs/ → 再 CLAUDE.md → 最后理记忆。

编辑原则：
- 减优于加（CLAUDE.md 净涨幅 > 30 行 = 红灯）
- 合并优于追加，删除优于保留
- 毕业优于内部挪腾（针对 memory）
- 绝对时间 `2026-04-29`，不写"今天"
- 受众不混，指针不重复，同源不分叉

### 第五步：自检清单（逐项打勾）
**尺寸组**（先查，不达标回头精简）：
- CLAUDE.md 净涨幅 ≤ 30 行
- 没新增 blockquote 历史叙事
- 没抄 docs 详细机制
- MEMORY.md ≤ 25KB 且 ≤ 200 行
- memory 体量 ≤ docs 体量

**规范组**：
- 层级规则从项目根读到了工作空间根 + 全局
- 每条违规：要么已修，要么进待拍板
- AGENTS.md ↔ CLAUDE.md 同源

**完整组**：
- 第一步列出的每个文件都判断了
- 记忆索引每个链接指向存在的文件
- 没有过期开放项冒充活计划
- 退役 symbol 的非载荷引用已清
- 新增 API：integration-guide **和** architecture 都出现
- 新增 env：runbook **和** 项目根 markdown 都出现
- 跨项目影响：下游 docs 也改了
- 相对时间清零

### 第六步：变更摘要
结构：记忆变更 / 文档变更（按项目分组）/ 规范审计（自动修复+待拍板）/ 体检读数（仅>70%时）/ 未处理。

---

## 三、变更影响矩阵（核心映射）

| 本次发生的事 | 要改的文件 |
|---|---|
| 新增 API/路由 | 项目根路由清单 · integration-guide API 速查表 · architecture Routes |
| 新增/改名 env | 项目根 env 表 · runbook env 章 · 下游 integration-guide |
| 新增 DB 表/列 | 项目根 DB 表 · architecture Data Model |
| 新增大特性 | 以上全部 + architecture 新章 + handoff 完成清单 |
| 部署/基建变化 | runbook · 项目根部署章 |
| 下游接入变化 | 下游 `<integration>.md` · 上游 integration-guide |
| 退役/改名/下线 | `grep -rn <symbol>` docs + 记忆，清非载荷引用 |

---

## 四、Agent 平台路径速查

| 平台 | 记忆/指令位置 | Skills |
|------|--------------|--------|
| Claude Code | `~/.claude/projects/<...>/memory/MEMORY.md` 索引 + `.md` 文件；全局 `~/.claude/CLAUDE.md` | `~/.claude/skills/<name>/` |
| Codex | **手改权威** → `~/.codex/AGENTS.md` + 项目根 AGENTS.md；**自动记忆库勿手改** → `~/.codex/memories/` | 全局 `~/.codex/skills/` + 钉住 `~/.codex/memories/skills/` + 项目内 `.codex/skills/` |
| OpenCode | 同时扫 Claude + Codex 目录 | `.opencode/skills/`、`.claude/skills/`、`.codex/skills/` |
| OpenClaw | 无独立记忆层，放项目根 markdown | `~/.openclaw/skills/` + `.openclaw/skills/` |

**跨平台共存**：CLAUDE.md 是真身，AGENTS.md 软链指向它，永远只编辑 CLAUDE.md。

---

## 五、规范审计处置分级

| 类型 | 例子 | 处置 |
|---|---|---|
| ✅ 直接修 | 补 AGENTS.md 软链 · 建 CLAUDE.md 脚手架 · 补 .gitignore 红线 · 清已确认死引用 | 直接动手 + 摘要报告 |
| ⚠️ 待拍板 | 目录重命名 · 删除文件 · 合并分叉 CLAUDE/AGENTS · 规则漂移 · 规则矛盾 · 反复违规（建议 hook 化） | 不动手，列证据+影响+建议，等用户决定 |

---

## 六、特殊情况

- 无 README/CLAUDE.md：有可运行代码 → 按模板创建；vibe 阶段 → 跳过但提一句
- 对话无新事实：仍审查现有记忆/文档过期/冲突/相对时间 + 跑第二步规范审计
- 需要用户介入只有两类：① 无法判断的矛盾；② 破坏性修复
- 跨项目改动：每个项目都跑一遍第一步 ls+读 docs
- 发现之前漏了：修掉，不推拖
