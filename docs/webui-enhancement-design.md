# ODAP WebUI 增强设计方案

**项目**: ODAP (Ontology-Driven Analytics Platform)  
**日期**: 2026-05-05  
**版本**: v1.0.0  
**状态**: 设计中

---

## 1. 现状分析

### 1.1 技术栈概览

| 层级 | 技术 | 版本 | 评估 |
|------|------|------|------|
| **前端框架** | React | 19.2.4 | ✅ 最新版 |
| **构建工具** | Vite | 8.0.4 | ✅ 现代工具 |
| **UI 组件库** | Ant Design | 6.3.5 | ✅ 企业级组件 |
| **状态管理** | Zustand | 5.0.12 | ✅ 轻量高效 |
| **图可视化** | @antv/g6 | 5.1.0 | ✅ 成熟方案 |
| **AI 集成** | Vercel AI SDK + @openharness/react | - | ✅ 集成良好 |

### 1.2 当前问题

| 问题 | 严重程度 | 描述 |
|------|----------|------|
| **本体图谱不可用** | 🔴 高 | `OntologySemanticNetwork.tsx` 使用 Mock 数据，未连接真实 API |
| **三栏布局缺失** | 🟡 中 | `AppLayout.tsx` 只有左右两栏，缺少右栏扩展面板 |
| **Skill 管理简陋** | 🟡 中 | `SkillManagement.tsx` 功能基础，缺少可视化编辑器 |
| **问答缺乏上下文** | 🟡 中 | QA 页面无法显示本体相关信息和执行建议 |
| **端到端流程断点** | 🔴 高 | 数据摄入→本体构建→问答→执行建议 流程未打通 |

### 1.3 现有资产盘点

**前端模块**:
- `modules/qa/` - 智能问答模块 (完善度: ⭐⭐⭐⭐)
- `modules/ontology/` - 本体图谱模块 (完善度: ⭐⭐)
- `modules/system/pages/SkillManagement.tsx` - Skill 管理 (完善度: ⭐⭐⭐)
- `modules/shared/components/AppLayout.tsx` - 布局组件 (完善度: ⭐⭐)

**后端模块**:
- `odap/biz/ontology/` - 本体业务逻辑
- `odap/biz/skill_system/` - Skill 系统
- `odap/biz/qa/` - 问答系统
- `odap/infra/graph/` - Graphiti 集成
- `odap/infra/openharness/` - OpenHarness 集成

---

## 2. 三栏布局设计方案

### 2.1 目标布局

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ODAP 本体平台                        [工作空间 ▼]  [场景 ▼]        [管理员] │
├────────┬────────────────────────────────────────────────────────┬───────────┤
│        │                                                        │           │
│ 左侧栏 │                    主内容区                            │  右侧栏   │
│  200px │                                                        │   280px   │
│        │  ┌──────────────────────────────────────────────────┐  │           │
│ 用户操作│  │                                                  │  │ 扩展面板  │
│  • 首页 │  │              功能页面内容                        │  │           │
│  • 问答 │  │                                                  │  │ • 本体详情│
│  • 时间线│  │                                                  │  │ • 建议   │
│  • 态势 │  │                                                  │  │ • 工具   │
│  • 模拟 │  │                                                  │  │           │
│        │  │                                                  │  │           │
│ 本体管理│  │                                                  │  │           │
│  • 图谱 │  │                                                  │  │           │
│  • 摄入 │  │                                                  │  │           │
│  • 版本 │  └──────────────────────────────────────────────────┘  │           │
│        │                                                        │           │
│ 系统配置│                                                        │           │
│  • 工作空间│                                                     │           │
│  • 审计日志│                                                     │           │
│  • 角色管理│                                                     │           │
│  • OPA策略│                                                      │           │
│  • Skill管理│                                                    │           │
│  • 配置中心│                                                      │           │
│        │                                                        │           │
└────────┴────────────────────────────────────────────────────────┴───────────┘
```

### 2.2 各栏职责

| 区域 | 宽度 | 折叠 | 职责 |
|------|------|------|------|
| **左侧栏** | 200px / 80px(折叠) | ✅ 可折叠 | 导航菜单、工作空间/场景选择 |
| **主内容区** | 自适应 | - | 功能页面、问答交互、图谱展示 |
| **右侧栏** | 280px / 0px(折叠) | ✅ 可折叠 | 上下文信息、执行建议、快捷操作 |

### 2.3 右侧栏上下文场景

| 当前页面 | 右栏内容 | 交互触发 |
|----------|----------|----------|
| `/qa` (问答) | 执行建议列表、相关本体实体 | AI 回复后自动展开 |
| `/ontology` (图谱) | 选中节点详情、关系列表 | 节点点击时展开 |
| `/ingest` (摄入) | 摄入进度、构建状态 | 摄入开始时展开 |
| `/skills` (Skill管理) | Skill 编辑器、依赖分析 | 编辑按钮点击时展开 |
| `/map` (态势地图) | 选中单位详情、可用动作 | 单位选中时展开 |

### 2.4 实现方案

**文件**: `frontend/src/modules/shared/components/AppLayout.tsx`

```typescript
// 新增 RightPanelContext
interface RightPanelContextType {
  showRightPanel: boolean;
  setShowRightPanel: (show: boolean) => void;
  rightPanelContent: React.ReactNode;
  setRightPanelContent: (content: React.ReactNode) => void;
  rightPanelTitle: string;
  setRightPanelTitle: (title: string) => void;
}

// 导出 Hook
export const useRightPanel = () => useContext(RightPanelContext);
```

**API 设计**:

```typescript
// 右栏内容更新 (Context API)
interface RightPanelState {
  show: boolean;
  title: string;
  content: React.ReactNode;
}

// 各页面使用示例
function QAChatPage() {
  const { setShowRightPanel, setRightPanelContent, setRightPanelTitle } = useRightPanel();

  const handleAIResponse = (response: AIResponse) => {
    if (response.suggestions?.length > 0) {
      setRightPanelTitle('执行建议');
      setRightPanelContent(<SuggestionList suggestions={response.suggestions} />);
      setShowRightPanel(true);
    }
  };
}
```

---

## 3. 本体图谱展示修复方案

### 3.1 问题诊断

`OntologySemanticNetwork.tsx` (第 28-52 行) 当前使用 Mock 数据:

```typescript
// 问题代码
const mockData = {
  nodes: [
    { id: '1', name: 'Entity 1', type: 'person', side: 'blue' },
    // ...
  ],
  edges: [...]
};
```

### 3.2 API 对接方案

**可用 API** (`api.ts`):

| API | 端点 | 返回数据 |
|-----|------|----------|
| `getEntities(scenarioId)` | `/api/scenarios/{id}/entities` | Entity[] |
| `getRelations(scenarioId)` | `/api/scenarios/{id}/relations` | { nodes, links } |
| `getSituationMap(scenarioId)` | `/api/scenarios/{id}/situation-map` | Unit[] (含位置) |

### 3.3 数据映射

```typescript
interface GraphNode {
  id: string;           // entity_id
  name: string;        // name
  type: string;        // entity_type
  side?: string;       // 方位 (red/blue/neutral)
  properties?: Record<string, unknown>;
}

interface GraphEdge {
  id: string;
  source: string;      // source_entity_id
  target: string;      // target_entity_id
  type: string;        // relation_type
}
```

### 3.4 修复实现

```typescript
// 文件: frontend/src/modules/ontology/pages/OntologySemanticNetwork.tsx

const loadGraph = async (scenarioId: string) => {
  try {
    setLoading(true);
    
    // 并行获取实体和关系
    const [entitiesResult, relationsResult] = await Promise.all([
      api.getEntities(scenarioId),
      api.getRelations(scenarioId)
    ]);

    // 转换为 G6 格式
    const nodes: GraphNode[] = entitiesResult.map((e) => ({
      id: e.entity_id,
      name: e.name,
      type: e.entity_type,
      side: e.side,
      properties: e.properties
    }));

    const edges: GraphEdge[] = relationsResult.links.map((l) => ({
      id: l.id || `${l.source}-${l.target}`,
      source: l.source,
      target: l.target,
      type: l.type || l.relation_type
    }));

    setNodes(nodes);
    setEdges(edges);
  } catch (error) {
    console.error('加载语义网络失败', error);
    message.error('加载语义网络失败');
  } finally {
    setLoading(false);
  }
};
```

### 3.5 增强功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **节点搜索** | 输入关键词高亮匹配节点 | P1 |
| **类型筛选** | 按实体类型过滤显示 | P1 |
| **节点详情 Drawer** | 点击节点显示完整信息 | P1 |
| **关系探索** | 点击节点展开关联节点 | P2 |
| **布局切换** | 力导向/环形/网格布局切换 | P1 |
| **缩放/平移** | 支持鼠标滚轮缩放、拖拽平移 | P1 |
| **实时更新** | WebSocket 推送本体变化 | P3 |

---

## 4. 端到端流程设计

### 4.1 完整业务流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ODAP 端到端工作流                                     │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
  │ 数据摄入 │───▶│ 本体构建    │───▶│ 知识图谱存储  │───▶│ 智能问答    │
  └─────────┘    └─────────────┘    └──────────────┘    └─────────────┘
       │              │                    │                   │
       ▼              ▼                    ▼                   ▼
  ┌─────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
  │ 原始数据 │    │ Graphiti    │    │ Neo4j        │    │ OpenHarness │
  │ (多源)   │    │ 实体抽取    │    │ 双时态图谱    │    │ Agent Loop  │
  └─────────┘    └─────────────┘    └──────────────┘    └─────────────┘
                                                                   │
                                                                   ▼
  ┌─────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
  │ 执行反馈 │◀───│ 动作建议    │◀───│ 意图识别      │◀───│ 用户输入    │
  └─────────┘    └─────────────┘    └──────────────┘    └─────────────┘
       │              │                    │
       ▼              ▼                    ▼
  ┌─────────┐    ┌─────────────┐    ┌──────────────┐
  │ Skill   │    │ OPA 策略    │    │ 本体约束     │
  │ 执行引擎│    │ 权限校验     │    │ 关系推理     │
  └─────────┘    └─────────────┘    └──────────────┘
```

### 4.2 数据摄入 → 本体构建

**摄入类型**:

| 类型 | 入口 | 处理方式 |
|------|------|----------|
| **News 摄入** | URL 输入 | 爬取网页 → LLM 实体抽取 → 关系提取 |
| **Manual 摄入** | 表单输入 | 结构化数据 → 直接入库 |
| **JSON 摄入** | 文件上传 | 批量数据 → 映射入库 |
| **自然语言** | 文本输入 | LLM 理解 → 实体关系抽取 |
| **随机生成** | 参数配置 | 模拟数据 → 规则生成 |

**API 端点**:

```typescript
// 摄入入口
POST /api/ontology/ingest
{
  "source_type": "news" | "manual" | "json" | "natural_language" | "random",
  "scenario_id": "xxx",
  // 根据 source_type 不同字段
}

// 构建触发
POST /api/ontology/ingest/{ingest_id}/build
```

### 4.3 智能问答 → 执行建议

**问答流程**:

```
用户输入 → 意图识别 → 本体检索 → 回答生成 → 动作建议
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
 自然语言    Intent API   Graphiti    LLM生成     Skill列表
              ↓↓↓
         OPA 权限校验
```

**API 端点**:

```typescript
// 流式问答
POST /api/qa/ask/stream
{
  "question": "红方部队目前的位置在哪里?",
  "scenario_id": "xxx",
  "workspace_id": "xxx"
}
// 返回: SSE 流

// 动作建议
GET /api/qa/suggestions?context=xxx
// 返回: 
{
  "suggestions": [
    {
      "action": "查询部队位置",
      "skill": "location_query",
      "params": { "unit": "红方部队" },
      "confidence": 0.95
    }
  ]
}
```

### 4.4 Skill 自动生效

**机制**:

1. **Skill 扫描**: 启动时扫描 `~/.workbuddy/skills/` 和项目目录
2. **元数据解析**: 解析 SKILL.md 提取描述、参数、返回值
3. **自动注册**: 解析后的 Skill 自动注册到 SkillRegistry
4. **权限配置**: 通过 OPA 策略控制 Skill 可见性
5. **动态加载**: Agent 根据上下文动态选择可用 Skill

**Skill 注册 API**:

```typescript
// 扫描目录
GET /api/skill/skills

// 上传 Skill
POST /api/skill/upload
Content-Type: multipart/form-data
{
  file: SKILL.md,
  category: "custom"
}

// 注册 Skill
POST /api/skill/register
{
  "name": "location_query",
  "category": "intelligence",
  "description": "查询部队位置信息",
  "input_schema": { ... },
  "output_schema": { ... }
}

// 启用/禁用
POST /api/skill/{name}/toggle
{ "enabled": true }
```

---

## 5. Skill 可视化管理方案

### 5.1 现有问题

- `SkillManagement.tsx` 功能基础
- 缺少 Skill 编辑器
- 缺少 Skill 可视化工作流

### 5.2 开源方案选型

| 方案 | License | 技术栈 | 特点 | 匹配度 |
|------|---------|--------|------|--------|
| **n8n** | Apache 2.0 | Vue/Node.js | 专业工作流引擎 | ⭐⭐⭐ |
| **ActivePieces** | MIT | Angular | 现代 UI | ⭐⭐⭐ |
| **ToolJet** | LGPL | React | 低代码平台 | ⭐⭐⭐⭐ |
| **Appsmith** | APL | React | 企业级 | ⭐⭐⭐ |
| **自研编辑器** | - | React | 定制化高 | ⭐⭐⭐⭐⭐ |

### 5.3 推荐方案: 自研 + 借鉴

**核心原则**: 不引入重型框架，基于现有 Ant Design 打造轻量级 Skill 可视化管理器

**功能规划**:

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **Skill 列表** | 目录扫描、注册状态、启用/禁用 | P0 |
| **Skill 详情** | 解析 SKILL.md，展示 schema | P0 |
| **Skill 上传** | 拖拽上传 .md/.yaml 文件 | P0 |
| **Skill 编辑** | 可视化编辑 SKILL.md 内容 | P1 |
| **分类管理** | Skill 分类、标签管理 | P2 |
| **依赖分析** | Skill 依赖关系可视化 | P2 |

### 5.4 Skill 编辑器设计

```typescript
// Skill 编辑器组件
interface SkillEditorProps {
  skill?: Skill;  // 编辑时传入
  onSave: (skill: SkillDefinition) => void;
  onCancel: () => void;
}

// Skill 定义结构
interface SkillDefinition {
  name: string;
  description: string;
  category: string;
  triggers: string[];          // 触发关键词
  input_schema: JSONSchema;
  output_schema: JSONSchema;
  sections?: {
    description?: string;
    instructions?: string;
    examples?: string;
    notes?: string;
  };
}
```

**编辑器 UI**:

```
┌─────────────────────────────────────────────────────────────────┐
│ Skill 编辑器                                           [保存] X │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  名称: [________________________]                               │
│                                                                 │
│  分类: [情报___▼]  触发词: [________________________]          │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ┌─────────────────────┐  ┌───────────────────────────────────┐  │
│  │  描述 (Description)  │  │  预览 (Preview)                   │  │
│  ├─────────────────────┤  │  ┌─────────────────────────────┐ │  │
│  │                      │  │  │ # skill_name               │ │  │
│  │  简洁描述此 Skill   │  │  │                             │ │  │
│  │  的用途和功能...    │  │  │ ## Description             │ │  │
│  │                      │  │  │ {description}             │ │  │
│  │                      │  │  │                             │ │  │
│  ├─────────────────────┤  │  │ ## Triggers                │ │  │
│  │  说明 (Instructions) │  │  │ - {triggers}              │ │  │
│  ├─────────────────────┤  │  │                             │ │  │
│  │                      │  │  │ ## Input Schema            │ │  │
│  │  使用说明和参数    │  │  │  {input_schema}            │ │  │
│  │  说明...            │  │  │                             │ │  │
│  │                      │  │  └─────────────────────────────┘ │  │
│  ├─────────────────────┤  │                                   │  │
│  │  示例 (Examples)    │  │                                   │  │
│  ├─────────────────────┤  │                                   │  │
│  │                      │  │                                   │  │
│  │  使用示例...        │  │                                   │  │
│  │                      │  │                                   │  │
│  └─────────────────────┘  └───────────────────────────────────┘  │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  输入 Schema:                          输出 Schema:             │
│  ┌─────────────────────────┐          ┌─────────────────────────┐│
│  │ {                       │          │ {                       ││
│  │   "unit_name": "string",│          │   "status": "string",    ││
│  │   "time_range": {       │          │   "location": {         ││
│  │     "start": "datetime",│          │     "lat": "number",     ││
│  │     "end": "datetime"   │          │     "lon": "number"     ││
│  │   }                      │          │   }                     ││
│  │ }                       │          │ }                       ││
│  └─────────────────────────┘          └─────────────────────────┘│
│  [添加字段]                           [添加字段]                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 技术选型与实施计划

### 6.1 技术栈确认

| 组件 | 当前 | 建议 | 理由 |
|------|------|------|------|
| **React** | 19.2.4 | ✅ 保持 | 最新稳定版 |
| **Vite** | 8.0.4 | ✅ 保持 | 快速构建 |
| **Ant Design** | 6.3.5 | ✅ 保持 | 企业级组件 |
| **G6** | 5.1.0 | ✅ 保持 | 图可视化 |
| **Zustand** | 5.0.12 | ✅ 保持 | 轻量状态管理 |

### 6.2 不引入的重型依赖

| 方案 | 原因 |
|------|------|
| ~~LangChain UI~~ | 与 OpenHarness 功能重叠 |
| ~~Dify~~ | 太重，与现有架构冲突 |
| ~~Flowise~~ | 面向 LangChain，不适用 |
| ~~LangFlow~~ | Python 后端，不需要 |

### 6.3 实施计划

#### Phase 1: 布局增强 (1 周)

| 任务 | 文件 | 优先级 |
|------|------|--------|
| 右栏 Context | `AppLayout.tsx` | P0 |
| useRightPanel Hook | `AppLayout.tsx` | P0 |
| 右栏组件 | `RightPanel.tsx` | P0 |
| 右栏样式整合 | `AppLayout.tsx` | P1 |

#### Phase 2: 本体图谱修复 (1 周)

| 任务 | 文件 | 优先级 |
|------|------|--------|
| API 对接 | `OntologySemanticNetwork.tsx` | P0 |
| 数据映射 | 同上 | P0 |
| 节点点击详情 | `GraphCanvas.tsx` | P1 |
| 搜索/筛选增强 | 同上 | P1 |

#### Phase 3: 问答增强 (1 周)

| 任务 | 文件 | 优先级 |
|------|------|--------|
| 右栏建议展示 | `QAChatPage.tsx` | P0 |
| 本体上下文注入 | `useQAI.ts` | P1 |
| 动作执行集成 | 待定 | P2 |

#### Phase 4: Skill 可视化 (2 周)

| 任务 | 文件 | 优先级 |
|------|------|--------|
| Skill 编辑器组件 | `SkillEditor.tsx` | P0 |
| Schema 编辑器 | `SchemaEditor.tsx` | P1 |
| 预览功能 | 同上 | P1 |
| 上传增强 | `SkillManagement.tsx` | P1 |

---

## 7. 关键文件清单

### 7.1 需要修改的文件

| 文件路径 | 修改内容 |
|----------|----------|
| `frontend/src/modules/shared/components/AppLayout.tsx` | 添加右栏 Context 和布局 |
| `frontend/src/modules/ontology/pages/OntologySemanticNetwork.tsx` | 接入真实 API |
| `frontend/src/modules/qa/pages/QAChatPage.tsx` | 添加右栏建议展示 |
| `frontend/src/modules/system/pages/SkillManagement.tsx` | 增强 Skill 管理 |

### 7.2 需要新建的文件

| 文件路径 | 用途 |
|----------|------|
| `frontend/src/modules/shared/components/RightPanel.tsx` | 右栏通用组件 |
| `frontend/src/modules/system/components/SkillEditor.tsx` | Skill 可视化编辑器 |
| `frontend/src/modules/system/components/SchemaEditor.tsx` | JSON Schema 编辑器 |

### 7.3 需要修改的后端文件

| 文件路径 | 修改内容 |
|----------|----------|
| `odap/biz/qa/` | 添加建议生成接口 |
| `odap/biz/skill_system/` | 添加 Skill 解析/验证 |

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| **G6 升级兼容** | 图可视化可能失效 | 保留旧版本 G6 v4 作为备选 |
| **API 不稳定** | 图谱数据加载失败 | 添加 Mock 数据降级 |
| **性能问题** | 大规模图谱渲染卡顿 | 添加虚拟化、分页加载 |

---

## 9. 成功标准

### 9.1 布局增强
- [ ] 三栏布局可正常显示
- [ ] 左右栏均可折叠
- [ ] 右侧栏可动态更新内容

### 9.2 本体图谱
- [ ] 图谱显示真实数据
- [ ] 节点可点击查看详情
- [ ] 支持搜索、筛选功能

### 9.3 端到端流程
- [ ] 数据摄入 → 本体构建 链路打通
- [ ] 问答 → 执行建议 链路打通
- [ ] 新增 Skill 自动生效

### 9.4 Skill 管理
- [ ] Skill 上传/编辑功能完整
- [ ] Schema 可视化编辑
- [ ] 预览与保存功能

---

**文档结束**
