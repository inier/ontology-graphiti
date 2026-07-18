# AI 助手统一架构设计 v1.0

> **文档定位**：定义 ODAP 平台 AI 助手的分层架构、平台功能本体模型、前端组件化方案、操作手册知识库接入规范。
>
> **关联文档**：
> - `ARCHITECTURE.md` — 系统总体架构
> - `ARCHITECTURE_BIZ.md` — 业务层设计（含 AI 助手现有实现）
> - `ARCHITECTURE_WEB.md` — 接口层设计（含 AIChatPanel 现有实现）

---

## 1. 设计目标

### 1.1 现状问题

| 问题 | 说明 |
|------|------|
| **AI 助手不统一** | Header 入口和本体设计器中的 AI 助手是独立实例，状态不共享 |
| **只懂业务本体** | AI 助手只理解用户设计的业务本体，不懂平台功能（如何操作界面） |
| **无操作知识库** | 没有平台操作手册，AI 无法回答"如何创建本体"等使用问题 |
| **前端展示耦合** | `AIChatPanel` 单体组件，full/compact 模式通过 prop 切换，难以独立迁移 |
| **知识扩展困难** | 新增知识来源（操作手册、FAQ、版本变更日志）需要改代码 |

### 1.2 设计目标

1. **统一 AI 助手**：Header 入口、本体设计器、其他页面的 AI 助手是同一个服务，共享会话历史
2. **平台功能本体**：用 ODAP 本体设计能力为平台本身建模，AI 助手基于双本体问答
3. **操作手册知识库**：为平台各功能编写操作手册，结构化为知识库，AI 可检索回答
4. **前端组件化**：抽象 `AIChatProvider` + 展示层组件，支持 full/compact 两种模式，便于独立迁移
5. **知识可扩展**：知识层抽象接口，后续接入 FAQ、版本变更日志、社区问答等

---

## 2. 后端分层架构

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────┐
│                   API Layer                       │
│  /api/assistant/chat  (统一聊天接口)              │
│  /api/assistant/tools/* (工具执行)                │
│  /api/assistant/knowledge/* (知识管理·新增)       │
│  /api/assistant/platform-ontology/* (平台本体·新增)│
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
│                 Service Layer                     │
│  ChatService (问答引擎·扩展支持双本体)            │
│  ToolRegistry (工具调度·现有)                    │
│  ContextManager (上下文管理·新增，支持双本体)      │
│  KnowledgeManager (知识管理·新增，操作手册/QA)    │
│  SessionManager (会话管理·现有)                   │
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
│                Knowledge Layer                    │
│  ├── Business Ontology (业务本体·现有)           │
│  ├── Platform Ontology (平台功能本体·新增)        │
│  ├── Operations Manual (操作手册·新增)            │
│  └── Extensible Knowledge (可扩展知识·新增)       │
└─────────────────────────────────────────────────────┘
```

### 2.2 Knowledge Layer（知识层）

#### 2.2.1 双本体模型

AI 助手基于**两个本体**进行问答：

| 本体类型 | 描述 | 数据来源 | 用途 |
|----------|------|----------|------|
| **业务本体** | 用户在设计器中定义的实体类型、关系类型、属性 | 用户通过本体设计器创建 | 回答业务数据相关问题（"里程碑有哪些属性"） |
| **平台功能本体** | 描述平台自身的功能模块、页面、操作、概念 | 开发者通过 JSON 定义，存入本体系统 | 回答平台使用问题（"如何创建本体"） |

**关键设计决策**：平台功能本体**复用 ODAP 本体存储能力**，即：
- 平台功能本体以「特殊本体」形式存储在现有本体系统中（如 `ontology_id = "platform"`）
- 复用现有的 `OntologyService` 进行 CRUD
- AI 助手的 `get_ontology_context` 工具可指定 `ontology_id = "platform"` 查询平台功能

#### 2.2.2 平台功能本体建模

详见 `[平台功能本体建模](#3-平台功能本体建模)`。

#### 2.2.3 操作手册知识库

操作手册以**结构化 Markdown** 编写，通过知识入库 Pipeline 转化为：
- **向量索引**（用于语义检索）
- **结构化 JSON**（用于精确匹配）
- **平台功能本体实例**（关键操作链接到本体）

详见 `[操作手册知识库 Schema](#4-操作手册知识库-schema)`。

#### 2.2.4 可扩展知识接口

```python
class KnowledgeSource(ABC):
    """知识源抽象接口"""
    @abstractmethod
    def get_type(self) -> str: ...
    
    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[KnowledgeHit]: ...
    
    @abstractmethod
    async def get_by_id(self, doc_id: str) -> KnowledgeDoc | None: ...

class KnowledgeHit(TypedDict):
    doc_id: str
    content: str
    score: float
    metadata: dict
```

内置实现：
- `OntologyKnowledgeSource` — 从本体检索
- `ManualKnowledgeSource` — 从操作手册检索
- `FAQKnowledgeSource` — 从 FAQ 检索（后续扩展）

### 2.3 Service Layer（服务层）

#### 2.3.1 ChatService 扩展设计

现有 `ChatService` 增加：

```python
class ChatService:
    def __init__(self):
        self._llm = None
        self._knowledge_manager = KnowledgeManager()
        self._context_manager = ContextManager()
    
    async def chat(self, message: str, ontology_id: str | None = None,
                   platform_context: bool = True,  # 新增：是否注入平台功能本体上下文
                   ...) -> AsyncGenerator[Dict[str, Any], None]:
        """
        platform_context=True 时，自动注入平台功能本体上下文，
        让 LLM 同时理解业务本体和平台功能。
        """
```

**上下文注入策略**：

| 用户所在页面 | 注入的本体上下文 |
|-------------|-----------------|
| 本体设计器 | 业务本体上下文 + 平台功能本体中的"本体设计"相关章节 |
| 问答页面 | 业务本体上下文 + 平台功能本体中的"问答系统"相关章节 |
| 其他页面 | 仅平台功能本体上下文 |
| Header 入口（无页面上下文） | 仅平台功能本体上下文 |

#### 2.3.2 ContextManager（新增）

```python
class ContextManager:
    """管理 AI 助手对话的上下文"""
    
    def build_context(self, ontology_id: str | None,
                     current_page: str | None,
                     platform_ontology_id: str = "platform") -> str:
        """
        构建注入到 LLM 的上下文字符串。
        
        1. 如果 ontology_id 存在，注入业务本体上下文
        2. 如果 current_page 存在，从平台功能本体中检索相关操作手册章节
        3. 拼接为统一上下文
        """
```

#### 2.3.3 KnowledgeManager（新增）

```python
class KnowledgeManager:
    """管理操作手册等知识的检索和注入"""
    
    async def search_manual(self, query: str, 
                            module: str | None = None,
                            top_k: int = 3) -> list[KnowledgeHit]:
        """搜索操作手册"""
    
    async def get_module_manual(self, module_id: str) -> str:
        """获取某个功能模块完整操作手册（用于快捷操作）"""
    
    async def ingest_manual(self, markdown_path: str) -> IngestResult:
        """将 Markdown 操作手册入库（Markdown → JSON → 向量索引）"""
```

### 2.4 API Layer（接口层）

新增端点：

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/assistant/knowledge/search` | POST | 搜索操作手册 |
| `/api/assistant/knowledge/ingest` | POST | 入库操作手册 |
| `/api/assistant/platform-ontology/sync` | POST | 同步平台功能本体（从 JSON 定义同步到本体系统） |
| `/api/assistant/session/history` | GET | 获取会话历史（统一会话，跨页面共享） |

现有端点不变（`/api/assistant/chat`、`/api/assistant/tools/execute`）。

---

## 3. 平台功能本体建模

### 3.1 设计思路

**核心洞察**：ODAP 平台本身就是一个"领域"，可以用本体来描述它。

用现有本体设计能力为平台建模，意味着：
1. 平台功能本体**存储在本体系统中**（`ontology_id = "platform"`）
2. AI 助手通过现有 `get_ontology_context` 工具查询平台功能本体
3. 操作手册中的关键操作**链接到本体实体**，实现"知识图谱 + 文档"混合检索

### 3.2 本体模型

#### 3.2.1 Entity Types

| Entity Type | 描述 | 关键属性 |
|-------------|------|------------|
| `FunctionalModule` | 功能模块（如"本体管理"、"问答系统"） | `name`, `description`, `route_prefix`, `icon` |
| `Page` | 页面（如"本体设计器"、"问答页面"） | `name`, `description`, `route`, `module_id` |
| `Operation` | 操作（如"新增属性"、"保存本体"） | `name`, `description`, `shortcut`, `difficulty` |
| `Concept` | 概念（如"本体"、"工作空间"、"场景"） | `name`, `description`, `related_module` |
| `Tutorial` | 教程（如"5分钟快速入门"） | `name`, `description`, `steps_json` |

#### 3.2.2 Relation Types

| Relation Type | Source | Target | 描述 |
|--------------|--------|--------|------|
| `contains` | `FunctionalModule` | `Page` | 模块包含页面 |
| `has_operation` | `Page` | `Operation` | 页面支持的操作 |
| `related_to` | `Concept` | `Concept` | 概念相关 |
| `explained_in` | `Concept` | `Tutorial` | 概念在教程中解释 |
| `has_tutorial` | `FunctionalModule` | `Tutorial` | 模块有教程 |

#### 3.2.3 实例数据（节选）

```json
// FunctionalModule: 本体管理
{
  "name": "本体管理",
  "description": "定义和管理业务本体，包括实体类型、关系类型、属性",
  "route_prefix": "/ontology",
  "icon": "ApartmentOutlined"
}

// Page: 本体设计器
{
  "name": "本体设计器",
  "description": "可视化设计本体，支持添加/编辑/删除实体类型和关系类型",
  "route": "/ontology/designer",
  "module_id": "本体管理"
}

// Operation: 新增属性
{
  "name": "新增属性",
  "description": "在对象类型中新增一个属性字段",
  "shortcut": "在类型卡片中点击「+ 属性」按钮",
  "difficulty": "easy"
}
```

### 3.3 同步机制

平台功能本体定义存储在 `docs/ai-assistant/platform-ontology.json`，通过管理命令同步到本体系统：

```bash
# 同步平台功能本体
curl -X POST /api/assistant/platform-ontology/sync \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"definition_path": "docs/ai-assistant/platform-ontology.json"}'
```

同步逻辑：
1. 读取 JSON 定义
2. 如果 `ontology_id = "platform"` 不存在，创建它
3. 根据定义创建 EntityType、RelationType、实例数据
4. 幂等操作（基于 `name` 匹配，存在则更新）

---

## 4. 操作手册知识库 Schema

### 4.1 Markdown 格式规范

每个功能模块的操作手册是一个 Markdown 文件，存放于 `docs/user-manual/`。

```markdown
# 模块名称：本体管理

## 概述
简要描述本模块的功能和用途。

## 快速开始
### 前置条件
- 条件1
- 条件2

### 第一步：创建本体
操作步骤：
1. 点击"新建本体"按钮
2. 输入本体名称
3. 点击"保存"

⚠️ 注意：本体名称不可重复。

## 详细操作
### 添加实体类型
...

## 常见问题
### Q: 如何删除本体？
A: ...

## 相关概念
- 本体
- 实体类型
- 关系类型
```

### 4.2 JSON Schema（结构化）

Markdown 通过 Pipeline 转化为结构化 JSON：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OperationsManual",
  "type": "object",
  "properties": {
    "module_id": { "type": "string" },
    "module_name": { "type": "string" },
    "version": { "type": "string" },
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": { "type": "string" },
          "content": { "type": "string" },
          "related_operations": {
            "type": "array",
            "items": { "type": "string" }
          },
          "related_ontology_nodes": {
            "type": "array",
            "items": { "type": "string" }
          }
        }
      }
    }
  }
}
```

### 4.3 入库存 Pipeline

```
Markdown 文件
    ↓ (解析)
结构化 JSON
    ↓ (拆分)
文本块（chunk_size=512, overlap=128）
    ↓ (向量化)
向量索引（存储于向量数据库）
    ↓ (链接)
平台功能本体实例（文本块 → Ontology Node 链接关系）
```

---

## 5. 前端组件化方案

### 5.1 组件架构

```
AIChatProvider (上下文 Provider, 共享状态)
├── useAIChat (核心聊天逻辑 Hook)
├── useAIChatHistory (历史会话管理 Hook)
└── useAIChatTools (工具调用管理 Hook)

AIChatFullMode (完全体模式 - 全屏管理)
├── AIChatHistory (历史会话列表)
├── AIChatMessageList (消息列表)
├── AIChatInput (输入框)
└── AIChatToolVisualizer (工具调用可视化)

AIChatCompactMode (简洁模式 - 侧边栏/对话框)
├── AIChatBubble (对话气泡, 可折叠)
├── AIChatInput (输入框, 复用)
└── AIChatToolVisualizer (工具调用可视化, 复用)

AIChatPanel (对外暴露的统一入口组件)
├── mode="full" → 渲染 AIChatFullMode
└── mode="compact" → 渲染 AIChatCompactMode
```

### 5.2 关键设计

#### 5.2.1 AIChatProvider

```typescript
interface AIChatContextValue {
  // 状态
  messages: ChatMessage[];
  sending: boolean;
  sessionId: string | null;
  
  // 知识层配置
  ontologyId: string | null;
  platformContextEnabled: boolean;  // 是否注入平台功能本体
  
  // 操作
  sendMessage: (text: string) => Promise<void>;
  clearMessages: () => void;
  
  // 知识库快捷操作
  loadModuleManual: (moduleId: string) => Promise<string>;
}
```

#### 5.2.2 展示层差异

| 特性 | 完全体模式 | 简洁模式 |
|------|------------|------------|
| 历史会话 | 完整列表，左侧或顶部展示 | 折叠为图标，点击展开 |
| 消息列表 | 完整高度，支持滚动 | 限制最大高度，自动折叠 |
| 输入框 | 支持多行，显示快捷操作按钮 | 单行或限制3行，隐藏快捷按钮 |
| 工具调用展示 | 详细展示每个工具调用 | 简化为图标+状态 |
| 适用场景 | 独立页面（如 `/guide` 中的 AI 助手） | Header 入口、侧边栏嵌入 |

### 5.3 文件结构

```
apps/web/src/modules/shared/components/ai-chat/
├── AIChatProvider.tsx       # Context Provider
├── AIChatPanel.tsx         # 统一入口组件（对外暴露）
├── AIChatFullMode.tsx      # 完全体模式
├── AIChatCompactMode.tsx   # 简洁模式
├── AIChatMessageList.tsx   # 消息列表（共享）
├── AIChatInput.tsx         # 输入框（共享）
├── AIChatToolVisualizer.tsx # 工具调用可视化（共享）
├── AIChatHistory.tsx       # 历史会话（完全体模式专用）
├── AIChatBubble.tsx       # 对话气泡（简洁模式专用）
└── hooks/
    ├── useAIChat.ts        # 核心聊天逻辑
    ├── useAIChatHistory.ts # 历史会话管理
    └── useAIChatTools.ts  # 工具调用管理
```

---

## 6. 实施路线图

### Phase 1：知识层 + 后端抽象（2周）

- [ ] 定义平台功能本体 JSON Schema
- [ ] 实现 `PlatformOntologySyncer`（从 JSON 同步到本体系统）
- [ ] 实现 `KnowledgeManager` 和 `KnowledgeSource` 抽象接口
- [ ] 扩展 `ChatService`，支持 `platform_context` 参数
- [ ] 新增 API 端点（`/knowledge/*`、`/platform-ontology/*`）

### Phase 2：操作手册编写 + 入库（2周）

- [ ] 编写各功能模块操作手册（Markdown）
- [ ] 实现 Markdown → JSON → 向量索引 Pipeline
- [ ] 将操作手册链接到平台功能本体
- [ ] 测试 AI 助手回答平台使用问题

### Phase 3：前端组件化（1周）

- [ ] 抽象 `AIChatProvider` + Hooks
- [ ] 实现 `AIChatFullMode` 和 `AIChatCompactMode`
- [ ] 重构现有 `AIChatPanel`（兼容现有用法）
- [ ] 统一 Header 入口和本体设计器的 AI 助手实例

### Phase 4：知识扩展（后续）

- [ ] 接入 FAQ 知识源
- [ ] 接入版本变更日志知识源
- [ ] 支持用户反馈"这个答案是否有帮助"

---

## 7. 附录

### 7.1 平台功能本体 JSON 定义示例

见 `docs/ai-assistant/platform-ontology.json`（待创建）。

### 7.2 操作手册 Markdown 模板

见 `docs/ai-assistant/manual-template.md`（待创建）。

### 7.3 前端组件 API 文档

见 `docs/ai-assistant/frontend-api.md`（待创建）。

---

**变更记录**

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| v1.0 | 2026-06-21 | 架构通 | 初始版本 |
