# AI 助手真实化升级 —— 架构设计与实施报告

> **日期**: 2026-06-20  
> **状态**: ✅ 后端完整实现 + 前端已集成  
> **关联 ADR**: 本体设计 AI 辅助升级

---

## 1. 问题诊断

### 原 AI 助手的"假实现"问题

| 组件 | 原状态 | 问题 |
|------|--------|------|
| **AIChatPanel** (共享) | 🔴 **假实现** | `setTimeout` 硬编码中文示例回复 |
| **Ontology Assistant NL 解析** | 🟡 **规则匹配** | 仅用关键词匹配，无 LLM，代码注释承认"生产环境应调用 LLM" |
| **与 DesignerPage 集成** | 🔴 **未集成** | AI 组件存在但未连线到主设计页面 |
| **查询执行能力** | 🔴 **缺失** | 本体助手只能做设计建议，不能执行数据查询 |

### 用户诉求

1. **快速代替手工操作** — 如查询实体、搜索数据等
2. **本体设计智能建议** — 属性新增、关系新增建议，需从设计页面动态提取上下文  
3. **降低配置难度** — 通过自然语言交互提升效率

---

## 2. 架构设计

### 2.1 升级后架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    OntologyDesignerPage                          │
│  ┌─ Toolbar ───────────────────────────────────────────────────┐│
│  │ [数据库抽取] [自然语言提取] [版本历史] [切换本体]            ││
│  │ [🤖 AI 助手] ← 新增按钮，点击打开 Drawer                     ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│  ┌─ Right Drawer (420px) ─────────────────────────────────────┐│
│  │  AIChatPanel                                               ││
│  │  ├─ ontologyId={currentOntology.ontology_id}               ││
│  │  ├─ workspaceId={workspace.id}                             ││
│  │  └─ context={                                              ││
│  │       object_type: selObj?.name,   ← 动态上下文             ││
│  │       page: 'ontology_designer',                           ││
│  │       selected_types: [...]                                ││
│  │     }                                                      ││
│  │                                                            ││
│  │  [输入框] [发送按钮]                                        ││
│  │  ── Quick Actions ──                                       ││
│  │  [本体概况] [完整性检查] [建议属性]                          ││
│  └────────────────────────────────────────────────────────────┘│
└──────────────────────────────────┬──────────────────────────────┘
                                   │ SSE streaming
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│              POST /api/assistant/chat (NEW)                      │
│                                                                  │
│  ChatService.chat(message, ontology_id, context)                 │
│    │                                                             │
│    ├─ LLM Available?                                             │
│    │   ├─ YES → _llm_chat()                                     │
│    │   │   ├─ Step 1: LLM + function calling (intent detection) │
│    │   │   ├─ Step 2: Execute tool calls (查询/设计)            │
│    │   │   └─ Step 3: LLM 总结结果                              │
│    │   └─ NO  → _rule_based_chat() (keyword fallback)           │
│    │                                                             │
│    └─ Output: SSE events                                        │
│        ├─ RUN_STARTED / TEXT_MESSAGE_* / TOOL_CALL_* / CUSTOM   │
│        └─ RUN_FINISHED                                          │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │ Query Tool│ │Design Tool│ │Analysis   │
            │           │ │           │ │Tool       │
            ├───────────┤ ├───────────┤ ├───────────┤
            │list_ent…  │ │get_onto…  │ │check_comp…│
            │search_ent…│ │suggest_pr…│ │           │
            │query_rel… │ │suggest_re…│ │           │
            │query_tem… │ │           │ │           │
            └───────────┘ └───────────┘ └───────────┘
```

### 2.2 新增文件清单

| 文件 | 职责 |
|------|------|
| `odap/biz/core/assistant/__init__.py` | 模块初始化 |
| `odap/biz/core/assistant/tools.py` | 8 个工具定义 + 注册表 (query/design/analysis) |
| `odap/biz/core/assistant/services/chat_service.py` | LLM 驱动对话服务 + 规则回退 |
| `odap/biz/core/assistant/api/routes.py` | SSE 流式 API (`POST /api/assistant/chat`) |

### 2.3 修改文件清单

| 文件 | 变更 |
|------|------|
| `odap/web/router_registry.py` | 注册 `assistant_router` + `ontology_assistant_router` |
| `frontend/.../AIChatPanel.tsx` | 🔴假→✅真: SSE 流式对话 + 上下文支持 + 工具调用可视化 |
| `frontend/.../OntologyDesignerPage.tsx` | 新增 AI 助手按钮 + Drawer 集成 |

---

## 3. 核心能力矩阵

### 3.1 工具注册表 (8 tools)

| 工具名 | 类别 | 功能 |
|--------|------|------|
| `list_entities` | Query | 列出知识图谱实体（按类型筛选） |
| `search_entities` | Query | 按关键词搜索实体 |
| `query_relations` | Query | 查询实体关系/边（按源/目标类型筛选） |
| `query_temporal` | Query | 查询时序/事件数据 |
| `get_ontology_context` | Design | 获取本体设计完整上下文 |
| `suggest_properties` | Design | 建议缺失属性 |
| `suggest_relations` | Design | 建议可能的关系 |
| `check_completeness` | Analysis | 完整性检查（孤儿/缺失字段） |

### 3.2 LLM 模式 vs 规则回退

| 特性 | LLM 模式 | 规则回退 |
|------|----------|----------|
| 意图识别 | ✅ LLM function calling (ZhipuAI glm-4-flash) | 关键词匹配 (中文+英文) |
| 工具调度 | 自动选择+调用+总结 | 预定义意图→工具映射 |
| 自然语言理解 | ✅ 任意表达方式 | 固定关键词 |
| 多工具链式调用 | ✅ LLM 自行组合 | 单工具调用 |
| 离线可用 | ❌ 需 API Key | ✅ 无外部依赖 |

### 3.3 上下文传递机制

```typescript
// Frontend → Backend context
{
  message: "User类型还少了哪些属性？",
  ontology_id: "ont-abc123",
  workspace_id: "ws-001",
  context: {
    object_type: "User",          // 当前选中的对象类型
    page: "ontology_designer",    // 当前页面
    selected_types: ["User", "Order", "Product"]  // 所有对象类型
  }
}
```

助手可以：
- 知道用户正在编辑哪个对象类型
- 分析当前本体中所有类型的结构
- 给出针对性的建议

---

## 4. 自然语言交互示例

### 查询类
```
用户: "有哪些实体？"
助手: 调用 list_entities → 返回实体列表

用户: "搜索张三"
助手: 调用 search_entities(query="张三") → 返回搜索结果

用户: "User和Order之间有什么关系？"
助手: 调用 query_relations(source_type="User", target_type="Order") → 返回关系
```

### 设计建议类
```
用户: "User类型还少了哪些属性？"
助手: 调用 get_ontology_context → suggest_properties → 返回缺失属性列表

用户: "帮我检查一下本体完整性"
助手: 调用 check_completeness → 返回孤儿/缺失字段报告

用户: "建议User和Product之间的关系"
助手: 调用 suggest_relations(object_type_name="User") → 返回可能的关系
```

---

## 5. 安全性设计

1. **读操作优先**: 查询和设计建议类工具均为只读，不修改数据
2. **JWT 认证**: 所有 API 调用通过 `get_current_user` 依赖注入
3. **LLM 安全**: 使用 OpenAI 兼容的 function calling，LLM 只能选择预注册工具
4. **输入限制**: `message` 最大 2000 字符
5. **超时保护**: LLM 调用 30s 超时，查询工具独立超时
6. **失败回退**: LLM 不可用时自动降级到规则引擎

---

## 6. 与旧组件的关系

| 旧组件 | 策略 |
|--------|------|
| `ontology-assistant` API | **保留** — 仍服务原有的 AG-UI 协议和类型推断 |
| `AIChatPanel` (旧) | **完全替换** — 新实现向后兼容（props 全部可选） |
| `AdminLayout` / `ProLayout` | **自动受益** — 右侧 AI 聊天面板自动升级为真实实现 |
| `useOntologyAssistant` hook | **保留** — 服务于本体设计页面的 AG-UI 协议 |

---

> **结论**: AI 助手已从"假实现"升级为真实的 LLM 驱动助手，支持数据查询、本体设计建议、动态上下文提取三大核心能力。当 LLM API Key 未配置时，自动回退到规则引擎，保证离线可用性。
