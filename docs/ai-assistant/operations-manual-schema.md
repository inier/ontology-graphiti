# 操作手册知识库 Schema v1.0

> **文档定位**：定义操作手册的 Markdown 格式规范、结构化 JSON Schema、入库 Pipeline 设计。
>
> **关联文档**：
> - `ARCHITECTURE_AI_ASSISTANT.md` — AI 助手统一架构设计（引用本文档第 4 节）
> - `platform-ontology.md` — 平台功能本体建模（操作手册链接到本体实体）

---

## 1. 设计目标

### 1.1 为什么需要操作手册知识库

AI 助手目前只能回答**业务数据问题**（基于业务本体）和**平台功能问题**（基于平台功能本体）。

但用户经常需要**分步骤的操作指导**（如"如何配置 OPA 策略"），这类知识：
- 不适合用本体建模（本体擅长概念/关系，不擅长步骤序列）
- 适合用 **Markdown 操作手册** 编写（结构化、易维护）
- 需要**语义检索**（用户输入"怎么加属性"应匹配"新增属性"章节）

### 1.2 设计目标

1. **Markdown 源文件**：技术写手用熟悉的 Markdown 编写，无需学习新格式
2. **结构化 JSON**：入库 Pipeline 将 Markdown 转化为结构化 JSON，便于检索
3. **向量索引**：文本块向量化，支持语义检索
4. **本体链接**：关键操作链接到平台功能本体，实现"知识图谱 + 文档"混合检索
5. **可扩展**：后续接入 FAQ、版本变更日志、社区问答等

---

## 2. Markdown 格式规范

### 2.1 文件组织

```
docs/
└── user-manual/
    ├── ontology.md       # 本体管理模块操作手册
    ├── qa.md              # 问答系统模块操作手册
    ├── workspace.md       # 工作空间模块操作手册
    ├── knowledge.md       # 知识库模块操作手册
    ├── simulation.md      # 模拟器模块操作手册
    ├── agent.md           # 智能体模块操作手册
    ├── business.md        # 业务配置模块操作手册
    ├── settings.md        # 系统设置模块操作手册
    └── getting-started.md  # 快速入门（跨模块）
```

### 2.2 章节结构规范

每个操作手册文件遵循以下结构：

```markdown
# 模块名称：<模块名>

> **适用于**：<适用角色/场景>
> **前置条件**：<前置条件列表>

## 概述
<简要描述本模块的功能和用途>

## 快速开始
### 前置条件
- 条件 1
- 条件 2

### 第一步：<操作名>
操作步骤：
1. 点击"XXX"按钮
2. 输入 YYY
3. 点击"保存"

⚠️ **注意**：<注意事项>

✅ **预期结果**：<操作后的预期结果>

## 详细操作
### <操作名>
<操作描述>

操作步骤：
1. <步骤 1>
2. <步骤 2>

💡 **提示**：<提示信息>

### <操作名>
...

## 常见问题（FAQ）
### Q: <问题>？
A: <回答>

### Q: <问题>？
A: <回答>

## 相关概念
- [概念名 1](#相关概念链接)
- [概念名 2](#相关概念链接)

## 相关教程
- [教程名 1](#相关教程链接)
```

### 2.3 格式标记规范

| 标记 | 用途 | 示例 |
|------|------|---------|
| `> **适用于**` | 适用性说明 | `> **适用于**：管理员` |
| `> **前置条件**` | 前置条件 | `> **前置条件**：已创建本体` |
| `### 前置条件` | 前置条件章节 | `### 前置条件` |
| `⚠️ **注意**` | 注意事项 | `⚠️ **注意**：名称不可重复` |
| `✅ **预期结果**` | 预期结果 | `✅ **预期结果**：类型创建成功` |
| `💡 **提示**` | 提示信息 | `💡 **提示**：可批量导入` |
| `1. ` | 操作步骤 | `1. 点击"新建"按钮` |

### 2.4 示例：本体管理操作手册（节选）

```markdown
# 模块名称：本体管理

> **适用于**：所有用户
> **前置条件**：已创建工作空间

## 概述
本体是业务领域的概念模型，包含实体类型、关系类型、属性。

## 快速开始
### 前置条件
- 已登录系统
- 已创建工作空间

### 第一步：创建本体
操作步骤：
1. 进入"本体管理"模块
2. 点击"新建本体"按钮
3. 输入本体名称（如"作战本体"）
4. 点击"保存"

⚠️ **注意**：本体名称不可重复。

✅ **预期结果**：本体创建成功，进入本体设计器。

## 详细操作
### 新增属性
操作步骤：
1. 在类型卡片中，点击"属性"板块的「+ 属性」按钮
2. 输入属性名称（如"name"）
3. 选择数据类型（STRING / INTEGER / FLOAT / BOOLEAN / DATETIME / TEXT）
4. 点击"保存"

💡 **提示**：可一次添加多个属性，用逗号分隔。

### 建议属性（AI 助手）
1. 打开 AI 助手（侧边栏或对话框）
2. 点击"建议属性"按钮
3. AI 分析当前类型，给出属性建议
4. 点击建议中的"添加"按钮，批量添加

## 常见问题（FAQ）
### Q: 如何删除属性？
A: 在类型卡片中，找到要删除的属性，点击右侧"删除"图标。

### Q: 如何导入本体？
A: 点击"导入"按钮，上传 JSON 格式本体文件。

## 相关概念
- [本体](#概述)
- [实体类型](#详细操作)
- [关系类型](#详细操作)

## 相关教程
- [5 分钟快速入门](#快速开始)
```

---

## 3. 结构化 JSON Schema

### 3.1 顶层 Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OperationsManual",
  "type": "object",
  "properties": {
    "schema_version": { "type": "string", "enum": ["1.0.0"] },
    "module_id": { "type": "string" },
    "module_name": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string", "format": "date-time" },
    "applies_to": { "type": "array", "items": { "type": "string" } },
    "preconditions": { "type": "array", "items": { "type": "string" } },
    "sections": {
      "type": "array",
      "items": { "$ref": "#/definitions/Section" }
    },
    "faq": {
      "type": "array",
      "items": { "$ref": "#/definitions/FAQItem" }
    },
    "related_concepts": {
      "type": "array",
      "items": { "type": "string" }
    },
    "related_tutorials": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "required": ["schema_version", "module_id", "module_name", "sections"],
  "definitions": {
    "Section": {
      "type": "object",
      "properties": {
        "title": { "type": "string" },
        "content": { "type": "string" },
        "level": { "type": "integer", "minimum": 2, "maximum": 4 },
        "related_operations": {
          "type": "array",
          "items": { "type": "string" }
        },
        "related_ontology_nodes": {
          "type": "array",
          "items": { "type": "string" }
        },
        "steps": {
          "type": "array",
          "items": { "$ref": "#/definitions/Step" }
        }
      },
      "required": ["title", "content"]
    },
    "Step": {
      "type": "object",
      "properties": {
        "step_number": { "type": "integer" },
        "description": { "type": "string" },
        "screenshot": { "type": "string" },
        "warning": { "type": "string" },
        "expected_result": { "type": "string" }
      },
      "required": ["step_number", "description"]
    },
    "FAQItem": {
      "type": "object",
      "properties": {
        "question": { "type": "string" },
        "answer": { "type": "string" },
        "related_sections": {
          "type": "array",
          "items": { "type": "string" }
        }
      },
      "required": ["question", "answer"]
    }
  }
}
```

### 3.2 示例 JSON（节选）

```json
{
  "schema_version": "1.0.0",
  "module_id": "ontology",
  "module_name": "本体管理",
  "version": "1.0.0",
  "last_updated": "2026-06-21T00:00:00Z",
  "applies_to": ["all-users"],
  "preconditions": [
    "已登录系统",
    "已创建工作空间"
  ],
  "sections": [
    {
      "title": "创建本体",
      "content": "本体是业务领域的概念模型...",
      "level": 3,
      "related_operations": ["create_ontology"],
      "related_ontology_nodes": ["本体", "实体类型"],
      "steps": [
        {
          "step_number": 1,
          "description": "进入"本体管理"模块",
          "screenshot": "/static/manual/ontology/step1.png"
        },
        {
          "step_number": 2,
          "description": "点击"新建本体"按钮",
          "warning": "名称不可重复"
        }
      ]
    }
  ],
  "faq": [
    {
      "question": "如何删除属性？",
      "answer": "在类型卡片中，找到要删除的属性，点击右侧"删除"图标。",
      "related_sections": ["新增属性"]
    }
  ],
  "related_concepts": ["本体", "实体类型", "关系类型"],
  "related_tutorials": ["5分钟快速入门"]
}
```

---

## 4. 入库 Pipeline 设计

### 4.1 整体流程

```
Markdown 文件（docs/user-manual/*.md）
    ↓ (1) 解析
结构化 JSON（符合 JSON Schema）
    ↓ (2) 拆分
文本块（chunk_size=512, overlap=128）
    ↓ (3) 向量化
向量索引（存储于向量数据库，如 Milvus / Chroma）
    ↓ (4) 链接
平台功能本体实例（文本块 → Ontology Node 链接关系）
```

### 4.2 步骤详解

#### 步骤 (1)：Markdown → 结构化 JSON

**工具**：使用 `markdown-it` 或 `remark` 解析 Markdown，提取章节结构。

**关键逻辑**：
- 提取 `# 模块名称：XXX` → `module_name`
- 提取 `> **适用于**：XXX` → `applies_to`
- 提取 `> **前置条件**：XXX` 和 `### 前置条件` 列表 → `preconditions`
- 提取 `## 详细操作` 下的 `### XXX` → `sections[]`
- 提取 `## 常见问题（FAQ）` 下的 `### Q: XXX` → `faq[]`
- 提取 `## 相关概念` 列表 → `related_concepts`
- 提取 `## 相关教程` 列表 → `related_tutorials`

#### 步骤 (2)：结构化 JSON → 文本块

**策略**：
- 每个 `Section` 作为一个文本块（如果内容超过 `chunk_size`，再按句子拆分）
- 每个 `FAQItem` 作为一个文本块
- 每个 `Step` 作为一个文本块（包含 `step_number` + `description`）

**文本块格式**（用于向量化）：
```
[模块名] 操作名
操作步骤：
1. 步骤 1
2. 步骤 2
...
⚠️ 注意：...
✅ 预期结果：...
```

#### 步骤 (3)：文本块 → 向量索引

**向量化模型**：使用 `text-embedding-ada-002` 或 `BAAI/bge-m3`（与现有 Embedder 一致）。

**存储**：
- 向量数据库：Milvus / Chroma（与 Graphiti 共用或独立）
- 每个文本块存储：
  - `doc_id`：唯一 ID（如 `ontology__add_property__step_1`）
  - `content`：文本内容（用于检索后展示）
  - `vector`：向量
  - `metadata`：
    - `module_id`：所属模块
    - `section_title`：所属章节
    - `operation_name`：关联操作名
    - `related_ontology_nodes`：关联本体节点（JSON 数组）

#### 步骤 (4)：链接到平台功能本体

**目的**：实现"知识图谱 + 文档"混合检索。

**逻辑**：
1. 读取 `related_ontology_nodes`（每个文本块的 `metadata` 中）
2. 在平台功能本体（`ontology_id = "platform"`）中查找匹配的 `Operation` 或 `Concept` 节点
3. 创建关系：
   - `Operation` → `has_manual_section` → `ManualSection`（新增 Entity Type）
   - `Concept` → `explained_in` → `ManualSection`

**新增 Entity Type**（在平台功能本体中）：
- `ManualSection`：操作手册章节
  - 属性：`doc_id` (STRING), `content` (TEXT), `module_id` (STRING)

---

## 5. 检索策略

### 5.1 混合检索

AI 助手回答用户问题时，采用**混合检索**策略：

```
用户问题
    ↓
┌─────────────────┬─────────────────┐
│  向量检索         │  本体检索         │
│  (语义匹配)      │  (精确匹配)      │
└─────────────────┴─────────────────┘
    ↓                 ↓
  相关文本块         相关本体节点
    ↓                 ↓
  合并去重
    ↓
  注入 LLM 上下文
    ↓
  生成回答
```

### 5.2 检索优先级

| 优先级 | 检索方式 | 触发条件 |
|---------|------------|------------|
| 1 | 本体检索（`get_platform_context` 工具） | 问题包含"本体"、"工作空间"等概念名 |
| 2 | 向量检索（`search_manual` 工具） | 问题为"如何XXX"、"怎么XXX"等操作型问题 |
| 3 | 混合检索 | 问题模糊，无法确定意图 |

### 5.3 检索结果注入格式

```python
def build_knowledge_context(self, query: str, 
                          platform_ontology_id: str = "platform") -> str:
    """构建知识上下文（注入到 LLM）"""
    # 1. 本体检索
    ontology_ctx = _query_platform_ontology(
        ontology_id=platform_ontology_id,
        query=query  # 用于匹配 Concept/Operation 名称
    )
    
    # 2. 向量检索
    manual_sections = self._knowledge_manager.search_manual(query, top_k=3)
    
    # 3. 合并注入
    ctx_parts = []
    if ontology_ctx:
        ctx_parts.append(f"【平台功能说明】\n{ontology_ctx}")
    if manual_sections:
        ctx_parts.append("【操作手册】")
        for sec in manual_sections:
            ctx_parts.append(f"### {sec['title']}\n{sec['content']}")
    
    return "\n\n".join(ctx_parts)
```

---

## 6. 管理接口

### 6.1 入库接口

```bash
# 入库单个操作手册
POST /api/assistant/knowledge/ingest
Content-Type: application/json

{
  "markdown_path": "docs/user-manual/ontology.md"
}

# 入库所有操作手册
POST /api/assistant/knowledge/ingest-all
```

### 6.2 检索接口

```bash
# 搜索操作手册（给 AI 助手调用）
POST /api/assistant/knowledge/search
Content-Type: application/json

{
  "query": "如何新增属性",
  "module_id": "ontology",  # 可选，限定模块
  "top_k": 3
}
```

### 6.3 管理接口

```bash
# 获取模块操作手册（完整）
GET /api/assistant/knowledge/manual?module_id=ontology

# 删除操作手册
DELETE /api/assistant/knowledge/manual?module_id=ontology
```

---

## 7. 实施路线图

### Phase 1：Schema 定义 + Pipeline 框架（1 周）

- [ ] 确定 JSON Schema 终稿
- [ ] 实现 Markdown → JSON 解析器
- [ ] 实现 JSON → 文本块拆分器
- [ ] 搭建向量数据库（Milvus / Chroma）

### Phase 2：操作手册编写（2 周）

- [ ] 编写各模块操作手册（Markdown）
- [ ] 实现向量化入库
- [ ] 链接到平台功能本体

### Phase 3：检索集成（1 周）

- [ ] 实现 `search_manual` 工具
- [ ] 更新 `ChatService` 支持知识上下文注入
- [ ] 测试 AI 助手回答质量

### Phase 4：扩展（后续）

- [ ] 接入 FAQ 知识源
- [ ] 接入版本变更日志
- [ ] 支持用户反馈

---

**变更记录**

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|-------|----------|
| v1.0 | 2026-06-21 | 架构通 | 初始版本 |
