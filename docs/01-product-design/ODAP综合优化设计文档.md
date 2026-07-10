# 本体驱动分析决策平台(ODAP) 综合优化设计文档

> **版本**: 2.2.0 | **日期**: 2026-05-07 | **状态**: 设计稿
>
> **目标**: 梳理现有架构、优化WebUI、完善图谱可视化、构建完整链路、改进Skill管理

---

## 快速导航

本综合文档是6个目标的顶层概述。每个目标的**详细设计、技术选型分析、开源项目对比**请查阅独立文档：

| 目标 | 详细文档 | 类型 |
|------|---------|------|
| 1. 架构检查与补充 | [全链路架构设计](02-architecture/ARCHITECTURE_FULL_CHAIN.md) | 架构设计 |
| 2. WebUI选型 | [ADR-052: 智能问答WebUI开源项目选型](07-adr/ADR-052_webui_opensource_selection.md) | 选型报告 |
| 3. 图谱可视化 | [图谱可视化优化设计](03-modules/visualization/DESIGN_GRAPH_OPTIMIZATION.md) | 详细设计 |
| 4. 全链路闭环 | [全链路架构设计](02-architecture/ARCHITECTURE_FULL_CHAIN.md) | 架构设计 |
| 5. Skill管理选型 | [ADR-053: Skill可视化管理开源方案选型](../07-adr/ADR-053_skill_management_selection.md) | 选型报告 |
| 6. 设计文档 | 本目录下所有上述文档 | 综合输出 |
| 🔧 深入实现 | [全链路深入设计 v2.0](02-architecture/ARCHITECTURE_FULL_CHAIN.md) | **5118行完整代码** |

---

## 目录

1. [现有架构检查与问题分析](#1-现有架构检查与问题分析)
2. [WebUI选型与三栏布局设计](#2-webui选型与三栏布局设计)
3. [本体图谱可视化优化方案](#3-本体图谱可视化优化方案)
4. [完整链路架构设计](#4-完整链路架构设计)
5. [Skill可视化管理方案](#5-skill可视化管理方案)
6. [技术选型总结与实施建议](#6-技术选型总结与实施建议)

---

## 1. 现有架构检查与问题分析

### 1.1 现有架构概述

ODAP系统当前采用四层架构：

| 层次 | 组件 | 状态 |
|------|------|------|
| L1 | OpenHarness Agent基础设施 | 部分实现 |
| L2 | Graphiti双时态知识图谱 | 核心功能实现 |
| L3 | Python Skills | 基础框架存在 |
| L4 | OPA策略治理 | 部分实现 |
| L5-L6 | Web前端 | 基础框架存在 |

### 1.2 存在的问题

#### 1.2.1 WebUI层问题

1. **布局不完善**：当前采用基础侧边栏+内容区布局，缺少类似WorkBuddy的三栏弹性布局
2. **用户体验不足**：缺少会话历史、工作空间切换、场景管理等核心功能的直观界面
3. **功能分区不清**：问答、图谱、管理等功能混在一起，缺乏清晰的功能分区

#### 1.2.2 本体图谱可视化问题

1. **展示混乱**：当前图谱展示缺乏层次化、分组化的视觉设计
2. **交互能力弱**：节点选择、缩放、筛选、详情查看等功能不完善
3. **语义不清晰**：实体类型、关系类型的视觉区分不够明显

#### 1.2.3 链路完整度问题

1. **自动化程度低**：数据摄入→本体构建→用户问答→Skill执行缺少无缝衔接
2. **闭环反馈缺失**：执行结果未能有效反馈给本体更新
3. **智能推荐不足**：基于当前对话的Skill推荐能力弱

#### 1.2.4 Skill管理问题

1. **可视化缺失**：缺少直观的Skill编辑、组合、调试界面
2. **与OpenHarness集成不深**：Skill注册、热加载流程不够顺畅
3. **版本管理不完善**：Skill版本、回滚、发布流程缺失

---

## 2. WebUI选型与三栏布局设计

### 2.1 技术选型建议

#### 2.1.1 推荐方案：基于现有技术栈升级

**核心技术栈**：
- **框架**: React 19 + TypeScript (与现有保持一致)
- **UI组件库**: Ant Design 6 (现有) + Ant Design X (新增，适合AI交互)
- **状态管理**: Zustand (现有) + Jotai (可选，用于细粒度状态)
- **图可视化**: AntV G6 (现有，需要强化使用)
- **工作流**: React Flow (新增，用于Skill可视化)
- **代码高亮**: CodeMirror 6 (新增)

#### 2.1.2 可参考的开源项目

| 项目 | 特点 | 可复用部分 |
|------|------|-----------|
| ChatGPT官方界面 | 简洁的三栏布局 | 布局思路、消息渲染 |
| Claude Code | Skill集成、侧边栏 | Skill管理界面设计 |
| OpenHarness前端 | Agent交互 | 状态管理模式 |
| Ant Design X组件库 | AI专用组件 | 气泡、发送器组件 |

### 2.2 三栏布局设计

#### 2.2.1 总体布局结构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        顶部导航栏 (56px)                              │
├──────────────┬─────────────────────────────────┬─────────────────────┤
│  左侧栏      │       中间主栏                  │      右侧栏        │
│  (可折叠)    │       (核心交互区)              │      (可折叠)      │
│  240-320px  │                                 │      280-360px    │
├──────────────┼─────────────────────────────────┼─────────────────────┤
│ • 工作空间   │                                 │ • 执行建议         │
│ • 场景管理   │      智能问答会话区             │ • Skill状态        │
│ • 会话历史   │                                 │ • 本体详情         │
│ • 快捷操作   │      (消息列表 + 输入区)        │ • 相关实体         │
└──────────────┴─────────────────────────────────┴─────────────────────┘
```

#### 2.2.2 左侧栏详细设计

**功能分区**：
1. **顶部工作空间切换区**
   - 当前工作空间显示
   - 下拉切换/新建/编辑
   - 工作空间状态指示

2. **场景管理区**
   - 树形结构展示场景
   - 场景创建/编辑/删除
   - 场景状态标签

3. **会话历史区**
   - 按时间分组的会话列表
   - 会话摘要显示
   - 会话搜索/筛选

4. **底部快捷操作区**
   - 新建对话
   - 数据摄入入口
   - 本体管理入口

**组件实现要点**：
```typescript
// 左侧栏主组件
interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  currentWorkspaceId: string;
  currentScenarioId: string;
  currentSessionId: string;
  onWorkspaceSelect: (id: string) => void;
  onScenarioSelect: (id: string) => void;
  onSessionSelect: (id: string) => void;
  onNewSession: () => void;
}
```

#### 2.2.3 中间主栏详细设计

**顶部会话标题区**：
- 会话标题（可编辑）
- 会话操作按钮（清空、导出、分享等）
- 切换到图谱/设置视图

**消息列表区**：
- 用户消息（右侧对齐）
- AI消息（左侧对齐，支持Markdown渲染）
- 消息带时间戳、来源标注
- 流式渲染效果
- 消息可引用、可复制

**输入区**：
- 多行文本输入
- 附件上传
- 快捷回复建议
- 发送按钮
- 停止生成按钮

#### 2.2.4 右侧栏详细设计

**功能分区**：
1. **执行建议区**
   - 基于当前对话的推荐Skill
   - 置信度显示
   - 一键执行

2. **Skill状态区**
   - 当前启用的Skill列表
   - Skill健康状态
   - 快速禁用/启用

3. **本体详情区**
   - 当前对话涉及的实体
   - 实体属性展示
   - 关系图谱预览

4. **相关实体区**
   - 语义相似的实体
   - 关联路径展示

### 2.3 响应式设计策略

| 屏幕尺寸 | 布局调整 |
|---------|---------|
| <768px (手机) | 左右栏收起，底部Tab切换 |
| 768-1024px (平板) | 左栏收起，右栏可选展开 |
| 1024-1440px (笔记本) | 标准三栏 |
| ≥1440px (桌面) | 宽屏三栏优化 |

### 2.4 实施建议

1. **Phase 1**：基于现有QAChatPage重构为三栏布局
2. **Phase 2**：完善工作空间、场景管理、会话历史功能
3. **Phase 3**：添加右侧栏的执行建议、Skill状态等功能

---

## 3. 本体图谱可视化优化方案

### 3.1 当前问题分析

当前图谱展示存在的问题：
- ❌ 节点过多时视觉混乱
- ❌ 缺乏有效的筛选和搜索
- ❌ 节点详情展示不友好
- ❌ 缺乏时间维度的可视化
- ❌ 与问答界面集成不够

### 3.2 优化方案设计

#### 3.2.1 分层可视化架构

```
┌─────────────────────────────────────────────────────┐
│  顶层: 摘要视图 (按实体类型分组显示)               │
├─────────────────────────────────────────────────────┤
│  中层: 上下文视图 (显示相关实体+2跳关系)           │
├─────────────────────────────────────────────────────┤
│  底层: 详情视图 (单个实体的完整关系+时序信息)      │
└─────────────────────────────────────────────────────┘
```

#### 3.2.2 基于AntV G6的具体实现

**核心配置**：
```typescript
import G6 from '@antv/g6';

// 图谱初始化配置
const graph = new G6.Graph({
  container: 'graph-container',
  width: 800,
  height: 600,
  modes: {
    default: [
      'drag-canvas',
      'zoom-canvas',
      'drag-node',
      'click-select',
      'tooltip'
    ]
  },
  layout: {
    type: 'force',
    preventOverlap: true,
    nodeSpacing: 50,
    workerEnabled: true
  }
});
```

**节点类型设计**：

| 实体类型 | 形状 | 颜色 | 大小 |
|---------|------|------|------|
| 目标(目标) | 八边形 | #FF4D4F | 36px |
| 单位(Unit) | 六边形 | #1890FF | 32px |
| 武器(Weapon) | 五边形 | #52C41A | 28px |
| 情报(情报) | 圆形 | #FAAD14 | 24px |
| 决策指令(StrikeOrder) | 菱形 | #722ED1 | 30px |

**交互功能**：
1. **点击节点** → 显示右侧详情面板
2. **悬停节点** → 高亮1跳邻居
3. **缩放** → 自适应节点大小和标签
4. **拖拽** → 力导向重排
5. **右键菜单** → 快捷操作（查询、标记、删除等）

#### 3.2.3 筛选与搜索系统

**侧边栏筛选面板**：
- 按实体类型筛选
- 按时间范围筛选
- 按属性值筛选
- 自定义Cypher查询

**搜索功能**：
- 节点名称模糊搜索
- 关系类型搜索
- 搜索结果高亮显示

#### 3.2.4 时序可视化

利用Graphiti的双时态特性：
- 时间轴滑块控制显示时刻
- 动画展示图谱演变
- 差异高亮显示变化的节点/关系

### 3.3 与问答界面集成

**场景1：问答中引用图谱**
- AI回答中的实体可点击 → 跳转到图谱视图并高亮该实体
- "查看相关图谱"按钮 → 切换到图谱视图，显示相关子图

**场景2：图谱中发起问答**
- 选择节点 → 右键 → "问AI关于这个实体"
- 多选节点 → "问AI这些实体的关系"

---

## 4. 完整链路架构设计

### 4.1 链路总览

> **📘 完整实现代码参考**: [全链路深入实现设计 v2.3](./02-architecture/ARCHITECTURE_FULL_CHAIN.md) (~5310行，已去重精简)

```
┌─────────────┐    ┌──────────────┐    ┌─────────┐    ┌─────────┐
│  数据摄入   │───▶│  本体构建     │───▶│ 用户问答 │───▶│ Skill执行 │
│ Data Ingest │    │ Ontology Build│    │ Q&A     │    │ Execute │
└─────────────┘    └──────────────┘    └─────────┘    └────┬────┘
       ▲                                                     │
       │                       闭环反馈                       │
       └─────────────────────────────────────────────────────┘
```

### 4.2 各环节详细设计

#### 4.2.1 数据摄入 (Data Ingestion)

**输入源**：
- 文档上传（PDF、Word、Markdown）
- 数据库连接
- API数据源
- 手动输入

**处理流程**：
1. 文档解析
2. 文本分块
3. 实体提取（NER）
4. 关系抽取
5. 事件识别

**本体构建组件**：
```typescript
// 数据摄入状态管理
interface IngestionState {
  step: 'upload' | 'parsing' | 'extracting' | 'review' | 'complete';
  file?: File;
  extractedEntities: Entity[];
  extractedRelations: Relation[];
  extractedEvents: Event[];
  selectedForOntology: {
    entities: string[];
    relations: string[];
    events: string[];
  };
}
```

#### 4.2.2 本体构建 (Ontology Building)

**构建流程**：
1. 人工确认/编辑提取结果
2. 选择本体版本/分支
3. 验证实体关系一致性
4. 提交到Graphiti
5. 生成构建记录

**版本管理**：
- 每次构建创建新版本
- 版本间对比
- 一键回滚
- 分支合并

#### 4.2.3 用户问答 (User Q&A)

**问答链路**：
```
用户问题
   │
   ▼
意图识别 + 实体链接
   │
   ▼
本体检索 → RAG增强
   │
   ▼
LLM推理
   │
   ▼
生成回答 + 执行建议
   │
   ▼
展示 + 可选执行
```

**意图识别类型**：
- 信息查询（问什么）
- 数据分析（统计、趋势）
- 决策建议（怎么办）
- 动作执行（做什么）

#### 4.2.4 Skill执行 (Skill Execution)

**执行流程**：
1. 用户选择/AI推荐Skill
2. 确认参数（可编辑）
3. OPA权限检查
4. 执行Skill
5. 结果展示
6. 反馈记录 → 更新本体

**Skill编排能力**：
支持多Skill串行/并行执行
```
┌──────────┐
│ Skill A  │
└────┬─────┘
     │
     ▼
┌──────────┐
│ Skill B  │──┐
└──────────┘  │ 并行
┌──────────┐  │
│ Skill C  │◀─┘
└────┬─────┘
     │
     ▼
┌──────────┐
│ Skill D  │
└──────────┘
```

#### 4.2.5 闭环反馈 (Closed-loop Feedback)

**反馈收集点**：
- 用户对回答的评分
- Skill执行结果
- 新增的标注信息
- 用户手动修正

**反馈利用**：
- 优化提示词
- 更新本体
- 改进Skill
- 训练数据积累

### 4.3 状态流转设计

```typescript
// 完整会话状态
interface CompleteSessionState {
  // 基础信息
  sessionId: string;
  workspaceId: string;
  scenarioId: string;
  createdAt: string;
  updatedAt: string;
  
  // 问答历史
  messages: Message[];
  
  // 涉及的本体实体
  involvedEntities: string[];
  involvedRelations: string[];
  
  // 执行的Skill
  executedSkills: {
    skillId: string;
    params: any;
    result: any;
    timestamp: string;
  }[];
  
  // 本体变更
  ontologyChanges: {
    versionId: string;
    changes: Change[];
    timestamp: string;
  }[];
}
```

---

## 5. Skill可视化管理方案

### 5.1 技术选型

**推荐方案**：React Flow + 自定义组件

| 技术 | 用途 | 优势 |
|------|------|------|
| React Flow | Skill流程可视化 | 生态成熟、拖拽体验好 |
| Ant Design | UI组件 | 与现有风格统一 |
| CodeMirror 6 | Skill代码编辑 | 语法高亮、代码补全 |
| Monaco Editor | (可选)高级编辑 | VS Code体验 |

### 5.2 可视化界面设计

#### 5.2.1 Skill列表视图

**功能**：
- 分类筛选（情报/作战/分析/可视化）
- 搜索Skill
- 启用/禁用切换
- 查看详情/编辑
- 导入/导出

**卡片展示**：
```typescript
interface SkillCardProps {
  skill: Skill;
  enabled: boolean;
  onToggle: (id: string, enabled: boolean) => void;
  onEdit: (id: string) => void;
  onView: (id: string) => void;
}
```

#### 5.2.2 Skill编辑器

**分栏设计**：
- 左侧：可视化流程编辑区（React Flow）
- 中间：属性配置面板
- 右侧：Markdown编辑器 + 预览

**节点类型**：
- 开始节点
- 动作节点（Skill执行）
- 条件节点（逻辑判断）
- 循环节点
- 结束节点

#### 5.2.3 Skill组合设计

允许用户将多个Skill组合成工作流：
```typescript
interface SkillWorkflow {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  version: string;
  createdAt: string;
  updatedAt: string;
}

interface WorkflowNode {
  id: string;
  type: 'start' | 'skill' | 'condition' | 'loop' | 'end';
  data: {
    skillId?: string;
    condition?: string;
    loopConfig?: any;
  };
  position: { x: number; y: number };
}
```

### 5.3 与OpenHarness集成方案

#### 5.3.1 Skill注册流程

```
用户创建/编辑Skill
   │
   ▼
前端验证
   │
   ▼
保存到文件系统/数据库
   │
   ▼
通知Skill Registry服务
   │
   ▼
OpenHarness热加载
   │
   ▼
刷新前端列表 ✓
```

#### 5.3.2 API设计

```typescript
// Skill管理API
interface SkillAPI {
  // 扫描
  scanSkills(): Promise<ScanResult>;
  
  // CRUD
  getSkills(): Promise<Skill[]>;
  getSkill(id: string): Promise<Skill>;
  createSkill(data: SkillCreateData): Promise<Skill>;
  updateSkill(id: string, data: SkillUpdateData): Promise<Skill>;
  deleteSkill(id: string): Promise<void>;
  
  // 启用/禁用
  enableSkill(id: string): Promise<void>;
  disableSkill(id: string): Promise<void>;
  
  // 测试
  testSkill(id: string, params: any): Promise<TestResult>;
  
  // 版本
  getVersions(id: string): Promise<SkillVersion[]>;
  rollbackVersion(id: string, versionId: string): Promise<void>;
}
```

### 5.4 Skill版本管理

**版本控制能力**：
- 自动版本创建
- 版本对比（diff）
- 一键回滚
- 版本发布流程（草稿→测试→发布）

---

## 6. 技术选型总结与实施建议

### 6.1 技术栈整合

| 领域 | 技术 | 状态 |
|------|------|------|
| 前端框架 | React 19 + TypeScript | 现有 ✓ |
| UI组件库 | Ant Design 6 + Ant Design X | 现有 + 新增 |
| 图可视化 | AntV G6 | 现有 + 强化 |
| 工作流 | React Flow | 新增 |
| 代码编辑 | CodeMirror 6 | 新增 |
| 状态管理 | Zustand | 现有 ✓ |
| 后端框架 | FastAPI | 现有 ✓ |
| Agent框架 | OpenHarness | 现有 ✓ |
| 图数据库 | Neo4j | 现有 ✓ |
| 策略引擎 | OPA | 现有 ✓ |

### 6.2 实施路线图

#### Phase 1: WebUI重构（2-3周）

**目标**：实现WorkBuddy式三栏布局

- [ ] 重构QAChatPage为三栏布局
- [ ] 实现左侧栏（工作空间、场景、会话历史）
- [ ] 实现中间栏（问答会话）
- [ ] 实现右侧栏（执行建议、Skill状态）
- [ ] 响应式适配

#### Phase 2: 图谱可视化优化（1-2周）

**目标**：解决图谱展示混乱问题

- [ ] 设计节点类型视觉区分
- [ ] 实现筛选搜索功能
- [ ] 添加节点详情面板
- [ ] 集成到问答界面
- [ ] 时序可视化（可选）

#### Phase 3: 完整链路实现（3-4周）

**目标**：数据摄入→本体构建→用户问答→Skill执行闭环

- [ ] 数据摄入界面
- [ ] 本体构建流程
- [ ] 问答链路优化
- [ ] Skill执行集成
- [ ] 闭环反馈机制

#### Phase 4: Skill可视化管理（2-3周）

**目标**：直观的Skill管理界面

- [ ] Skill列表/卡片视图
- [ ] Skill编辑器（可视化+Markdown）
- [ ] Skill工作流编排
- [ ] 版本管理功能
- [ ] 与OpenHarness深度集成

#### Phase 5: 持续优化与闭环增强（持续进行）

**目标**：建立数据驱动优化飞轮，持续提升系统智能水平

- [ ] 反馈聚合仪表盘 (Section 5.8) — 核心指标实时监控
- [ ] A/B测试框架上线 (Section 5.7) — Prompt/策略效果量化对比
- [ ] 异常检测系统激活 (Section 5.9) — 自动告警 + 趋势分析
- [ ] 引用溯源机制完善 (Section 3.9) — 答案可信度可视化
- [ ] 本体增量更新自动化 — Skill执行结果自动反馈到图谱
- [ ] 会话摘要质量监控 — 上下文压缩率与信息保留率追踪

### 6.3 风险与注意事项

| 风险 | 缓解措施 |
|------|---------|
| 现有代码重构影响 | 采用增量式重构，保持向后兼容 |
| 性能问题（大图谱） | 实现虚拟滚动、分页加载、节点聚合 |
| 用户学习成本 | 提供引导教程、操作向导 |
| 跨浏览器兼容性 | 使用成熟库，充分测试主流浏览器 |

---

## 附录

### A. 相关文档链接

**架构设计文档**：
- [ODAP核心架构设计 v4.1](./02-architecture/ARCHITECTURE.md)
- [全链路架构设计](./02-architecture/ARCHITECTURE_FULL_CHAIN.md)
- [全链路深入实现设计 v2.0](./02-architecture/ARCHITECTURE_FULL_CHAIN.md) — **5118行完整代码实现**

**选型报告 (ADR)**：
- [ADR-052: 智能问答WebUI开源项目选型](07-adr/ADR-052_webui_opensource_selection.md)
- [ADR-053: Skill可视化管理开源方案选型](../07-adr/ADR-053_skill_management_selection.md)
- [ADR-054: 全链路深入实现设计](02-architecture/ARCHITECTURE_FULL_CHAIN.md)

**模块设计文档**：
- [Web前端设计文档](../03-modules/web_frontend/DESIGN.md)
- [图谱可视化优化设计](03-modules/visualization/DESIGN_GRAPH_OPTIMIZATION.md)
- [问答引擎设计文档](03-modules/qa_engine/DESIGN.md)
- [Skill模块设计文档](03-modules/skills/DESIGN.md)
- [本体模块设计文档](03-modules/ontology/DESIGN.md)
- [本体管理引擎设计文档](../03-modules/ontology_management_engine/DESIGN.md)
- [架构决策记录 (ADR)](07-adr/README.md)

### B. 参考项目

| 项目 | 用途 | 链接 |
|------|------|------|
| React Flow | Skill工作流可视化编排 | https://reactflow.dev/ |
| Ant Design X | AI聊天UI组件 (Bubble/Sender/useXChat) | https://x.ant.design/ |
| AntV G6 | 本体图谱可视化渲染引擎 | https://g6.antv.antgroup.com/ |
| CodeMirror 6 | Skill Markdown代码编辑器 | https://codemirror.net/ |
| LobeChat | AI聊天架构参考 (插件系统) | https://github.com/lobehub/lobe-chat |
| Dify | 工作流编排交互参考 | https://github.com/langgenius/dify |
| Open WebUI | 管道式Skill处理参考 | https://github.com/open-webui/open-webui |
| react-diff-viewer-continued | 本体版本差异可视化 | https://github.com/praneshr/react-diff-viewer |
| tiktoken | OpenAI token精确计数 | https://github.com/openai/tiktoken |
| watchdog | Skill文件热重载监听 | https://github.com/gorakhargosh/watchdog |
| scipy | A/B测试统计显著性计算 | https://scipy.org/ |

---

## 8. 完整度提升补充文档 (v2.1)

以下文档基于 2026-05-07 的需求vs架构缺口分析补建：

| 文档 | 用途 | 路径 |
|------|------|------|
| **身份认证模块设计** | SSO/OAuth2/本地认证/JWT Token/与OPA对接 | [modules/auth/DESIGN.md](03-modules/auth/DESIGN.md) |
| **运维架构设计** | Prometheus+Grafana监控/日志收集Loki/Neo4j+PG备份/Docker部署拓扑 | [02-architecture/ARCHITECTURE_OPS.md](02-architecture/ARCHITECTURE_OPS.md) |
| **会话记忆与思维链可视化** | 上下文窗口管理/CoT树渲染/步骤回溯/解释引擎 | [modules/session_memory/DESIGN.md](03-modules/session_memory/DESIGN.md) |
| **管理员控制台深化** | 双模式配置编辑器/用户-角色矩阵/审计日志时间线 | [adr/ADR-020_管理员控制台统一界面.md](../07-adr/ADR-020_管理员控制台统一界面.md) |
| **场景导入导出格式** | .owp包结构/manifest校验和/冲突处理策略 | [modules/workspace/DESIGN.md §3.4](03-modules/workspace/DESIGN.md) |
| **测试策略设计** | pytest+vitest+Playwright三层体系/CI流水线/API文档自动生成 | [modules/test/DESIGN.md](../03-modules/test/DESIGN.md) |

**文档结束**
