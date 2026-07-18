# ADR-067: `biz/shared` 归属问题 —— 下沉到 `infra/storage/`

## Status
Proposed

## Context

`biz/shared/` 是 biz 层中唯一一个不以"业务领域"命名的子包。它仅包含一个模块：

```
biz/shared/
├── __init__.py          # 只有一行 docstring: "Shared stores and singletons for biz layer."
└── stores.py            # ScenarioStore 类 (380行) + 模块级单例 scenario_store
```

### 当前内容分析

`ScenarioStore` 是一个 SQLite 支持的场景持久化类，提供 CRUD + 克隆 + Graphiti 同步等操作。它：

| 维度 | 事实 |
|------|------|
| **内容本质** | SQLite CRUD wrapper + 图同步逻辑。无领域实体、值对象、业务规则。 |
| **自身依赖** | 依赖 `biz/core`（IngestService、OntologyVersionManager）和 `infra/security`（审计） |
| **被谁引用** | 仅 3 方：web 层(1次注入)、`biz/platform`(7次回退查询)、`biz/integration`(1次类型引用) |
| **引用方式** | 全部是延迟 import 的回退/兜底数据源，不是核心业务路径 |
| **领域关联** | `ScenarioStore` 管理的是仿真场景的持久化，但场景本身属于 `biz/simulation` 领域 |

### 问题

`biz/shared` 违反了 DDD 分层原则：

1. **语义混淆**：`biz/` 层应有 9 个清晰的业务子域（core/data/decision/integration/management/platform/semantic_admin/simulation + 本不应存在的 shared）。`shared` 破坏了这一一致性。
2. **依赖方向错误**：`shared` 依赖 `biz/core`（领域层），而 DDD 中共享内核应被其他域依赖，而非依赖领域层。这使 `shared` 处于一个尴尬的"半基础设施"位置。
3. **ADR-046 的模块边界约束**要求"依赖方向：web/ → biz/ → infra/，禁止反向依赖"。但 `shared` 跨在 biz 和 infra 的边界上，混淆了这条规则。
4. **命名暗示"垃圾桶"**：`shared` 容易成为未来放置杂项代码的倾向于，应该尽早关闭这个缺口。

## Decision

**将 `biz/shared/stores.py` 迁移到 `infra/storage/scenario_store.py`，删除 `biz/shared/`。**

具体步骤：

1. **新建** `odap/infra/storage/scenario_store.py`，内容从 `biz/shared/stores.py` 迁移
2. **更新 3 个引用方**的 import 路径：
   - `odap/web/api/app.py`: `from odap.biz.shared.stores` → `from odap.infra.storage.scenario_store`
   - `odap/biz/platform/workspace/api/routes.py`: 同上（7处）
   - `odap/biz/integration/frontend_compat/api/_deps.py`: 同上（1处类型引用）
3. **保留** 原 `biz/shared/__init__.py` 作为废弃重定向（re-export from new location + deprecation warning），一个版本后删除
4. **删除** `biz/shared/stores.py`

### 为什么不放到 `biz/simulation`？

`ScenarioStore` 虽然服务于仿真场景，但它本身不是领域逻辑——它是一个纯数据持久化层。放到 `biz/simulation` 会让 simulation 领域承担基础设施职责。`infra/storage/` 已经是 SQLite 存储基类（`SqliteBaseStorage`）的所在地，`ScenarioStore` 是它的自然扩展。

### 为什么不保留 `biz/shared`？

- 当前只有 3 个引用方，迁移成本极低
- 越早删除，越能避免它成为"垃圾桶"
- Biz 层应该只包含以业务领域命名的子包

## Consequences

### 变得更容易

- **分层清晰**：`biz/` 层目录项从 9 个变为 8 个，全部是业务领域名
- **规则可执行**：ADR-046 的依赖方向 `web → biz → infra` 不再有模糊地带
- **发现性提高**：`ScenarioStore` 和 `SqliteBaseStorage` 放在同一个包下，开发者自然知道在哪里找持久化类
- **可逆性高**：如果未来 ScenarioStore 承载了更多领域逻辑，迁回 biz 层只需改 import 路径

### 变得更难

- **短期迁移摩擦**：3 个引用方需要更新 import（约 10 分钟工作量）
- **废弃重定向维护**：需保留一个版本的兼容层

### 风险与缓解

| 风险 | 概率 | 缓解 |
|------|------|------|
| 其他未发现的引用方 | 低 | 全局 grep `biz.shared` 确认 |
| ScenarioStore 未来承载领域逻辑 | 低 | 真有那一天时迁回 biz/simulation，改变成本极低 |

## 可逆性

**高。** 只是 import 路径变化，类签名和行为不变。回滚只需改回 3 个文件的 import。

## 关联

- ADR-046（模块边界约束规则：web → biz → infra）
- ADR-065（拆分预案的候选模块不涉及 shared）
