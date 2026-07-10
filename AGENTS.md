# AGENTS.md — 项目工程规范

## Git 提交规范

### 核心原则：按逻辑变更单元提交

每个 commit 必须是一个**原子逻辑变更单元**，而不是按文件拆分或按功能混装。

#### 什么是逻辑变更单元

一个逻辑变更单元应满足以下全部条件：

1. **可独立编译通过** — 不能依赖未提交的代码
2. **可独立 revert** — revert 后不会破坏其他功能
3. **commit message 能一句话说清"为什么改"** — 而不是罗列改了哪些文件

#### 提交格式

```
<type>(<scope>): <subject>

- <变更点 1>
- <变更点 2>
```

**type** 取值：

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不改变外部行为） |
| `docs` | 文档变更 |
| `chore` | 构建、依赖、配置等杂项 |
| `test` | 测试相关 |
| `style` | 代码格式（不影响逻辑） |

**scope** 为可选的模块标识，如 `frontend`、`audit`、`docker`、`knowledge-base`。

#### 示例

```
fix(frontend): AdvancedTable toolbar icon vertical centering
feat(audit): instrument storage_audit across backend modules
chore(docker): upgrade Python 3.10 to 3.11 + fix container naming
```

### 禁止的行为

1. **禁止多关注点混装** — 一个 commit 不应同时包含"CSS 修复"和"API 重构"等不相关变更
2. **禁止跨功能大批量提交** — 单个 commit 不应超过 ~2000 行变更（文档删除除外）
3. **禁止"catch-all"提交** — 如 `chore: misc updates` 涵盖不相关变更
4. **禁止堆积不提交** — 工作区不应长期堆积大量未提交变更

### 操作指引

- **单文件包含完整逻辑** → 直接提交（如 CSS 修复）
- **多文件属于同一逻辑** → 一起提交（如接口 + 调用方 + 测试）
- **同文件有多个不相关变更** → 用 `git add -p` 按 hunk 拆分
- **不确定是否相关** → 问自己："如果需要 revert 这个 commit，会连带 revert 掉不相关的功能吗？" 如果会，就拆分
