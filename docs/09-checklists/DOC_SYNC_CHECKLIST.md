# 文档同步检查清单 (DOC_CHECKLIST)

> **用途**: 提交代码前逐项检查，确保文档与代码一致。
> **维护者**: 所有贡献者。发现文档过期时**立即修正**，不留 TODO。

---

## 一、模块变更检查

当 `odap/biz/` 下新增/删除/重命名模块时：

- [ ] `docs/03-modules/README.md` — 更新对应领域下的模块列表（模块名、路径、职责摘要）
- [ ] `docs/03-modules/{领域}/` — 新增或更新对应模块的 `DESIGN.md`
- [ ] `agents.md` § 3.1 — 更新后端包结构树（如有新领域或结构变更）

当 `frontend/src/modules/` 下新增/删除/重命名模块时：

- [ ] `docs/03-modules/README.md` — 更新前端模块表
- [ ] `agents.md` § 4.2 — 更新前端路由方案表（如有新页面路由）

---

## 二、路由变更检查

当新增 `api/routes.py` 路由模块时：

- [ ] `odap/web/router_registry.py` — 注册新路由到 `router_registry`
- [ ] `odap/web/app.py` — 确认 `include_router()` 已注册（生产入口）
- [ ] `agents.md` § 附录 E — 更新关键 API 路径速查表（如有新路径前缀）

---

## 三、架构决策检查

当引入新基础设施、新模式、新数据流、重大技术选型时：

- [ ] `docs/07-adr/` — 创建新 ADR 文件（按模板：状态/上下文/决策/后果/可逆性）
- [ ] `docs/07-adr/README.md` — 更新完整索引表（编号、标题、状态、文件链接）
- [ ] `docs/07-adr/README.md` — 更新分类索引（按领域归类到对应表格）
- [ ] `docs/07-adr/README.md` — 更新编号规则说明（新增 ADR 的编号范围）

---

## 四、环境/部署变更检查

当变更 `.env.docker`、`docker-compose*.yml`、`bootstep.py` 时：

- [ ] `agents.md` § 2.2 — 更新启动命令对照表
- [ ] `agents.md` § 2.3 — 更新环境变量速查
- [ ] `agents.md` § 2.2.6 — 更新关键文件速查表

---

## 五、存储层变更检查

当新增/修改 SQLite 表结构或字段时：

- [ ] 对应模块 `DESIGN.md` — 更新数据模型描述
- [ ] `agents.md` MEMORY — 记录关键陷阱（如字段名不匹配、位置索引禁用等）

---

## 六、过期检测机制

定期或在以下时机执行文档一致性审计：

| 触发时机 | 检查内容 | 方法 |
|---------|---------|------|
| 每次 PR/MR | 上述检查清单 | 提交者自检 + Reviewer 复核 |
| 新增 Phase/里程碑 | 全量文档审计 | 对比代码目录 vs 文档索引 |
| 季度 Review | ADR 状态更新 | 检查"提议"状态 ADR 是否已实现或废弃 |
| 发现文档不符 | 立即修正 | 不等不拖，修正后记录到 MEMORY |

### 快速审计命令

```bash
# 后端模块审计：对比代码目录与文档索引
ls odap/biz/*/  | sort
# 然后与 docs/03-modules/README.md 中的模块列表逐项对照

# 前端模块审计
ls frontend/src/modules/ | sort
# 然后与 docs/03-modules/README.md 前端模块表对照

# ADR 审计
ls docs/07-adr/ADR-*.md | sort
# 然后与 docs/07-adr/README.md 索引表逐项对照

# 路由审计
python -c "from odap.web.router_registry import router_registry; print(f'共 {len(router_registry)} 个路由模块')"
# 然后与 docs/03-modules/README.md 路由数量对照
```

---

## 七、文档层级与优先级

当不同文档对同一事项描述冲突时，按以下优先级裁决：

```
agents.md (工作手册)     ← 最高优先级，开发规则权威
  ↓
docs/02-architecture/   ← 架构设计权威
  ↓
docs/03-modules/        ← 模块设计权威
  ↓
docs/07-adr/            ← 决策记录权威
  ↓
代码注释                ← 最低优先级
```

**原则**: 高层文档定义"应该怎么做"，代码实现"实际怎么做"。两者不一致时，先修正文档（如果代码是正确的），或先修正代码（如果文档是正确的），**绝不允许两者长期不一致**。
