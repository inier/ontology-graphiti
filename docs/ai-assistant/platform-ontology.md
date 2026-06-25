# 平台功能本体建模 v1.0

> **文档定位**：定义 ODAP 平台功能本体的 EntityType、RelationType、属性、实例数据填充策略。
>
> **关联文档**：
> - `ARCHITECTURE_AI_ASSISTANT.md` — AI 助手统一架构设计（引用本文档第 3 节）
> - `ARCHITECTURE_BIZ.md` — 业务层设计（本体设计器实现）

---

## 1. 建模思路

### 1.1 核心洞察

**ODAP 平台本身就是一个"领域"**，可以用本体来描述它。

用现有本体设计能力为平台建模，意味着：
1. 平台功能本体**存储在本体系统中**（`ontology_id = "platform"`）
2. AI 助手通过现有 `get_ontology_context` 工具查询平台功能本体
3. 操作手册中的关键操作**链接到本体实体**，实现"知识图谱 + 文档"混合检索

### 1.2 与设计器的关系

| 维度 | 业务本体（用户设计） | 平台功能本体（系统内置） |
|------|----------------|--------------------------|
| `ontology_id` | 用户创建（如 `"default"`） | `"platform"`（系统内置） |
| 定义者 | 业务用户 | 平台开发者 |
| 实例数据 | 业务实体（如"里程碑"、"任务"） | 功能模块、页面、操作 |
| AI 助手用途 | 回答业务数据问题 | 回答平台使用问题 |

**关键设计决策**：复用 `OntologyService` 管理平台功能本体，不引入新存储。

---

## 2. 本体模型定义

### 2.1 Entity Types

#### `FunctionalModule`（功能模块）

| 属性 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `name` | STRING | ✅ | 模块名称（如"本体管理"） |
| `description` | TEXT | ❌ | 模块描述 |
| `route_prefix` | STRING | ❌ | 路由前缀（如 `"/ontology"`） |
| `icon` | STRING | ❌ | Ant Design 图标名（如 `"ApartmentOutlined"`） |
| `order` | INTEGER | ❌ | 排序权重 |

#### `Page`（页面）

| 属性 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `name` | STRING | ✅ | 页面名称（如"本体设计器"） |
| `description` | TEXT | ❌ | 页面描述 |
| `route` | STRING | ✅ | 前端路由路径（如 `"/ontology/designer"`） |
| `module_id` | STRING | ❌ | 所属功能模块 ID（FK → FunctionalModule） |
| `is_entry` | BOOLEAN | ❌ | 是否为模块入口页 |

#### `Operation`（操作）

| 属性 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `name` | STRING | ✅ | 操作名称（如"新增属性"） |
| `description` | TEXT | ❌ | 操作描述 |
| `page_id` | STRING | ❌ | 所属页面 ID（FK → Page） |
| `shortcut` | STRING | ❌ | 操作快捷方式（如"点击「+ 属性」按钮"） |
| `difficulty` | STRING | ❌ | 难度（`"easy"` / `"medium"` / `"hard"`） |
| `preconditions` | TEXT | ❌ | 前置条件（Markdown） |

#### `Concept`（概念）

| 属性 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `name` | STRING | ✅ | 概念名称（如"本体"、"工作空间"） |
| `description` | TEXT | ❌ | 概念描述 |
| `related_module` | STRING | ❌ | 相关功能模块 |

#### `Tutorial`（教程）

| 属性 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `name` | STRING | ✅ | 教程名称（如"5分钟快速入门"） |
| `description` | TEXT | ❌ | 教程描述 |
| `steps_json` | TEXT | ❌ | 步骤列表（JSON 数组，每个元素含 `title`、`content`、`screenshot`） |
| `module_id` | STRING | ❌ | 所属功能模块 ID（FK → FunctionalModule） |

### 2.2 Relation Types

| 关系名 | Source | Target | Cardinality | 描述 |
|---------|--------|--------|-------------|------|
| `contains` | `FunctionalModule` | `Page` | ONE_TO_MANY | 模块包含页面 |
| `has_operation` | `Page` | `Operation` | ONE_TO_MANY | 页面支持的操作 |
| `related_to` | `Concept` | `Concept` | MANY_TO_MANY | 概念相关 |
| `explained_in` | `Concept` | `Tutorial` | ONE_TO_MANY | 概念在教程中解释 |
| `has_tutorial` | `FunctionalModule` | `Tutorial` | ONE_TO_MANY | 模块有教程 |

---

## 3. 实例数据填充策略

### 3.1 数据来源

平台功能本体的实例数据来自两个来源：

| 来源 | 格式 | 维护者 | 同步方式 |
|--------|------|--------|----------|
| **JSON 定义文件** | `docs/ai-assistant/platform-ontology.json` | 开发者 | 管理命令同步 |
| **操作手册 Markdown** | `docs/user-manual/*.md` | 开发者/技术写手 | 入库 Pipeline 自动提取 |

### 3.2 JSON 定义文件格式

```json
{
  "$schema": "platform-ontology.v1.json",
  "version": "1.0.0",
  "modules": [
    {
      "name": "本体管理",
      "description": "定义和管理业务本体，包括实体类型、关系类型、属性",
      "route_prefix": "/ontology",
      "icon": "ApartmentOutlined",
      "order": 1,
      "pages": [
        {
          "name": "本体设计器",
          "description": "可视化设计本体，支持添加/编辑/删除实体类型和关系类型",
          "route": "/ontology/designer",
          "is_entry": true,
          "operations": [
            {
              "name": "新增属性",
              "description": "在对象类型中新增一个属性字段",
              "shortcut": "在类型卡片中点击「+ 属性」按钮",
              "difficulty": "easy"
            }
          ]
        }
      ]
    }
  ],
  "concepts": [
    {
      "name": "本体",
      "description": "描述业务领域的概念模型，包含实体类型、关系类型、属性",
      "related_module": "本体管理"
    }
  ],
  "tutorials": [
    {
      "name": "5分钟快速入门",
      "description": "从零开始创建第一个本体",
      "module_id": "本体管理",
      "steps_json": "[{\"title\": \"创建本体\", ...}]"
    }
  ]
}
```

### 3.3 同步 API

```bash
# 同步平台功能本体（从 JSON 定义文件）
POST /api/assistant/platform-ontology/sync
Content-Type: application/json

{
  "definition_path": "docs/ai-assistant/platform-ontology.json"
}
```

**同步逻辑**（幂等）：
1. 读取 JSON 定义文件
2. 如果 `ontology_id = "platform"` 不存在，创建它
3. 遍历 `modules`、`pages`、`operations` 等，基于 `name` 匹配：
   - 存在 → 更新属性
   - 不存在 → 创建新实例
4. 建立关系（`contains`、`has_operation` 等）

### 3.4 操作手册自动提取

操作手册 Markdown 通过后处理 Pipeline 自动提取 `Operation` 实例：

```
Markdown 文件（如 docs/user-manual/ontology.md）
    ↓ (正则提取 ## 详细操作 下的 ### 小节)
Operation 实例列表
    ↓ (调用 Ontology API)
写入平台功能本体（ontology_id = "platform"）
```

---

## 4. 与 AI 助手的集成

### 4.1 上下文注入

当 AI 助手收到用户消息时，`ContextManager` 按以下策略注入上下文：

```python
def build_context(self, ontology_id: str | None,
                  current_page: str | None) -> str:
    ctx_parts = []
    
    # 1. 业务本体上下文（如果 ontology_id 存在）
    if ontology_id:
        biz_ctx = _get_ontology_context(ontology_id)
        ctx_parts.append(biz_ctx)
    
    # 2. 平台功能本体上下文（根据 current_page 过滤）
    if current_page:
        # 从平台功能本体中查询与 current_page 相关的操作手册章节
        platform_ctx = _query_platform_ontology(
            ontology_id="platform",
            filter={"page_route": current_page}
        )
        ctx_parts.append(platform_ctx)
    
    return "\n\n".join(ctx_parts)
```

### 4.2 工具扩展

新增工具（注册到 `TOOL_REGISTRY`）：

| 工具名 | 描述 | 参数 |
|---------|------|------|
| `get_platform_context` | 获取平台功能本体上下文 | `page_route`（可选） |
| `search_manual` | 搜索操作手册 | `query`、`module`（可选） |
| `get_tutorial` | 获取教程步骤 | `tutorial_name` |

### 4.3 SYSTEM_PROMPT 更新

```python
SYSTEM_PROMPT = """你是 ODAP 本体驱动分析决策平台的 AI 助手。

你的能力:
1. **查询业务数据**: 列出实体、搜索实体、查询关系（基于业务本体）
2. **平台使用辅助**: 回答"如何创建本体"等使用问题（基于平台功能本体和操作手册）
3. **本体设计辅助**: 获取本体上下文、建议属性、建议关系、检查完整性
4. **本体增删改查**: 直接修改本体设计

## 平台功能本体
你可以通过 `get_platform_context` 工具获取平台功能说明。
当用户问"如何xxx"、"怎么xxx"、"xxx 在哪里"时，先调用此工具。

## 操作手册
你可以通过 `search_manual` 工具搜索详细操作手册。
当用户需要分步骤指导时，调用此工具获取详细步骤。
"""
```

---

## 5. 实例数据（节选）

### 5.1 FunctionalModule 实例

| name | route_prefix | icon | order |
|------|---------------|------|-------|
| 本体管理 | `/ontology` | ApartmentOutlined | 1 |
| 业务配置 | `/business` | FundOutlined | 2 |
| 数据采集 | `/ingest` | DatabaseOutlined | 3 |
| 知识库 | `/knowledge` | BookOutlined | 4 |
| 问答系统 | `/qa` | QuestionCircleOutlined | 5 |
| 工作空间 | `/workspace` | TeamOutlined | 6 |
| 系统管理 | `/settings` | SettingOutlined | 7 |
| 智能体 | `/agent` | RobotOutlined | 8 |

### 5.2 Page 实例（本体管理模块）

| name | route | module | is_entry |
|------|-------|--------|----------|
| 本体设计器 | `/ontology/designer` | 本体管理 | true |
| 本体图谱 | `/ontology/graph` | 本体管理 | false |
| 目标看板 | `/ontology/goals` | 本体管理 | false |
| 蓝图设计器 | `/blueprint` | 本体管理 | false |

### 5.3 Operation 实例（本体设计器页面）

| name | page | shortcut | difficulty |
|------|------|----------|------------|
| 新增属性 | 本体设计器 | 在类型卡片中点击「+ 属性」按钮 | easy |
| 新增关系 | 本体设计器 | 在"关系类型"板块点击「+ 关系」按钮 | easy |
| 删除属性 | 本体设计器 | 点击属性旁边的删除图标 | easy |
| 检查完整性 | 本体设计器 | 点击 AI 助手中的「完整性检查」按钮 | easy |
| 批量导入 | 本体设计器 | 点击「导入」按钮，上传 JSON 文件 | medium |

---

## 6. 维护指南

### 6.1 新增功能模块

1. 在 `docs/ai-assistant/platform-ontology.json` 的 `modules` 数组中添加新模块定义
2. 运行同步命令：`POST /api/assistant/platform-ontology/sync`
3. 编写操作手册：`docs/user-manual/<module-name>.md`
4. 运行入库 Pipeline：`POST /api/assistant/knowledge/ingest`

### 6.2 修改现有模块

1. 修改 `docs/ai-assistant/platform-ontology.json` 中的对应定义
2. 运行同步命令（幂等，仅更新变化部分）

### 6.3 验证

```bash
# 查询平台功能本体
curl -H "Authorization: Bearer $TOKEN" \
  "<http://localhost:8000/api/ontology/platform/object-types>"

# 测试 AI 助手回答平台使用问题
curl -X POST <http://localhost:8000/api/assistant/chat> \
  -H "Content-Type: application/json" \
  -d '{"message": "如何创建本体", "ontology_id": null}'
```

---

**变更记录**

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| v1.0 | 2026-06-21 | 架构通 | 初始版本 |
