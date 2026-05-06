# ADR-053: Skill可视化管理 开源方案选型

> **日期**: 2026-05-06 | **状态**: 提议 | **决策者**: 架构组

---

## 1. 背景与需求

### 1.1 ODAP的Skill管理需求

| 需求 | 优先级 |
|------|--------|
| 可视化Skill列表、分类筛选（情报/作战/分析/可视化等） | P0 |
| Skill创建/编辑界面，支持Markdown编辑 | P0 |
| Skill启用/禁用热切换（与OpenHarness联动） | P0 |
| Skill测试/运行功能 | P1 |
| Skill版本管理（diff、回滚、发布） | P1 |
| Skill工作流编排（多Skill串行/并行组合） | P2 |
| Skill导入/导出功能 | P2 |

### 1.2 技术约束

- 须与现有React 19 + TypeScript + Ant Design 6技术栈兼容
- 须与OpenHarness的技能热插拔机制（ADR-014）集成
- Skill存储于文件系统，支持热加载
- 开源协议允许商用

---

## 2. 候选方案

### 2.1 Dify

| 维度 | 详情 |
|------|------|
| **GitHub Stars** | ~110K |
| **技术栈** | Python (FastAPI) + React + TypeScript |
| **开源协议** | Apache 2.0 |
| **插件市场** | 600+插件，分类：模型、工具、Agent策略、扩展、数据源 |

**核心能力**：
-   可视化AI工作流编排（拖拽节点构建流程）
-   插件市场机制：插件分类、安装、版本管理
-   RAG知识管道：文档解析→分块→清洗→嵌入全可见
-   分层架构：数据层→开发层→编排层→基础设施层

**与ODAP Skill系统的对比**：

| 维度 | Dify 插件 | ODAP Skill | 对齐度 |
|------|----------|------------|--------|
| 定义语言 | YAML Manifest | Python + Markdown | ⭐⭐ |
| 热加载 | 插件安装后即时可用 | Skill Registry 动态扫描 | ⭐⭐⭐⭐ |
| 分类管理 | Tags + Categories | Category enum | ⭐⭐⭐⭐ |
| 版本管理 | 插件版本号 | 内置版本控制 | ⭐⭐⭐ |
| 安全校验 | 无内置 | OPA集成 | ⭐ (ODAP更强) |
| 工作流 | AI工作流编排 | 尚未实现 | ⭐⭐ |

**复用价值**：
- ✅ 插件市场UI交互模式可参考
- ✅ 工作流编排的节点拖拽交互
- ❌ 技术栈不同（Python后端vs OpenHarness），无法直接集成
- ❌ 插件定义格式不同（YAML Manifest vs Python Skill）

### 2.2 n8n

| 维度 | 详情 |
|------|------|
| **GitHub Stars** | ~127K |
| **技术栈** | Node.js + Vue.js |
| **开源协议** | Sustainable Use License (Fair-code) |
| **节点系统** | 400+内置集成节点 |

**核心能力**：
-   可视化工作流编辑器：拖拽节点+连线
-   400+预配置集成
-   自定义JS/Python代码节点
-   LangChain AI节点集成
-   MCP协议支持

**复用价值**：
- ✅ 工作流编排的交互范式业界最成熟
- ✅ 节点系统架构可参考
- ❌ 技术栈完全不兼容（Vue.js + Node.js vs React + Python）
- ❌ 开源协议非标准MIT/Apache，有使用限制
- ❌ 定位是"通用自动化"而非"AI Skill专有管理"

### 2.3 Flowise

| 维度 | 详情 |
|------|------|
| **GitHub Stars** | ~35K |
| **技术栈** | Node.js + React |
| **开源协议** | Apache 2.0 |
| **定位** | 低代码LLM应用构建器 |

**核心能力**：
-   可视化拖拽构建LLM应用
-   支持LangChain/LlamaIndex
-   节点类型：Agent、Chain、Tool、Memory等

**复用价值**：
- ✅ 专注LLM工具链，与ODAP场景贴近
- ❌ 技术栈冲突（Node.js + React 但非Ant Design）
- ❌ 偏向LLM应用构建，Skill管理不是核心场景

### 2.4 React Flow (作为可视化组件)

| 维度 | 详情 |
|------|------|
| **GitHub Stars** | ~27K |
| **技术栈** | React + TypeScript |
| **开源协议** | MIT |
| **定位** | 节点图可视化组件库 |

**核心能力**：
-   自定义节点/边渲染
-   拖拽、缩放、选择等交互内置
-   高度可定制的节点样式
-   丰富的插件生态（Minimap、Controls等）

**复用价值**：
- ✅ 技术栈完美匹配（React + TS）
- ✅ MIT协议，无使用限制
- ✅ 作为组件嵌入，与现有Ant Design界面统一
- ✅ 灵活可定制，可完全按ODAP需求设计Skill节点
- ❌ 不是完整应用，需自行构建管理层

### 2.5 总结对比

| 维度 | Dify | n8n | Flowise | React Flow |
|------|------|-----|---------|-------------|
| **技术栈兼容** | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **协议友好度** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Skill管理场景匹配** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **可定制性** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **集成成本** | 高（Fork改造） | 高（Fork改造） | 中高 | 低（组件嵌入） |
| **社区活跃度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 3. 决策

### 3.1 推荐方案：**React Flow 为核心 + 自研Skill管理层**

**不建议直接Fork Dify/n8n/Flowise**，原因：

1. **技术栈不兼容**：n8n用Vue.js+Node.js，Flowise用Node.js；只有Dify接近但仍有差距
2. **核心场景不同**：这些平台是"工作流编排平台"，ODAP需要的是"Skill注册管理+可视化"
3. **引入复杂度远大于收益**：Fork一个完整平台意味着维护一个独立代码分支

### 3.2 技术选型

| 组件 | 选型 | 用途 |
|------|------|------|
| **Skill列表/卡片** | Ant Design ProTable + Card | Skill CRUD基础界面 |
| **Skill编辑器** | CodeMirror 6 (Markdown) + Monaco Editor (Python) | 代码编辑 |
| **Skill工作流编排** | **React Flow** | 可视化拖拽组合Skill |
| **Skill测试** | 自定义RunPanel组件 | 参数输入+结果展示 |
| **版本管理** | Ant Design Timeline + diff2html | 版本历史和差异对比 |

### 3.3 可参考的开源设计

| 来源 | 复用内容 |
|------|---------|
| **Dify 插件市场** | 插件分类卡片布局、插件详情抽屉、安装/卸载交互 |
| **n8n 节点编辑器** | 节点拖拽连接交互、节点配置面板 |
| **Claude Code Skills** | Skill Markdown编写格式、Skill元数据规范 |

---

## 4. 集成设计

### 4.1 Skill管理整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ODAP Skill Management UI                          │
├──────────────────────────────┬──────────────────────────────────────┤
│     Skill 列表视图           │       Skill 工作流编排视图            │
│  ┌──────────────────────┐   │  ┌───────────────────────────────┐  │
│  │ ProTable + Card      │   │  │  React Flow Canvas            │  │
│  │ • 分类筛选           │   │  │  • 开始/结束节点              │  │
│  │ • 搜索Skill          │   │  │  • Skill节点 (可拖拽)         │  │
│  │ • 启用/禁用开关      │   │  │  • 条件节点                   │  │
│  │ • 查看/编辑/测试     │   │  │  • 连线+配置面板              │  │
│  └──────────────────────┘   │  └───────────────────────────────┘  │
├──────────────────────────────┴──────────────────────────────────────┤
│     Skill 编辑抽屉 (Drawer)                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Markdown编辑器 (CodeMirror 6) | 实时预览 | 元数据配置表单  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 React Flow Skill节点设计

```typescript
// 自定义Skill节点
const SkillNode: React.FC<NodeProps> = ({ data }) => {
  return (
    <div className="skill-node">
      <Handle type="target" position={Position.Top} />
      <div className="skill-node-content">
        <Icon component={getSkillIcon(data.category)} />
        <Text strong>{data.skillName}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {data.category}
        </Text>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

// Skill工作流数据模型
interface SkillWorkflow {
  id: string
  name: string
  description: string
  nodes: SkillWorkflowNode[]
  edges: SkillWorkflowEdge[]
  version: string
}

interface SkillWorkflowNode {
  id: string
  type: 'start' | 'skill' | 'condition' | 'end'
  data: {
    skillId?: string           // 关联的Skill ID
    skillName?: string
    category?: string
    params?: Record<string, any>  // 预设参数
    condition?: string         // 条件表达式(用于condition节点)
  }
  position: { x: number; y: number }
}
```

### 4.3 与OpenHarness集成流程

```
用户保存Skill
    │
    ▼
┌────────────────────┐
│ Skill Registry API │  ← FastAPI endpoint
│ POST /skill/sync   │
└────────┬───────────┘
         │ 1. 验证Skill结构
         │ 2. 写入文件系统
         │ 3. 触发热加载
         ▼
┌─────────────────────┐
│ OpenHarness          │
│ Skill Bridge         │  ← 扫描+注册+热加载
│ @skill_registry      │
└────────┬────────────┘
         │ 返回注册结果
         ▼
┌────────────────────┐
│ 前端刷新Skill列表   │  ← WebSocket/SSE 推送变更
└────────────────────┘
```

```python
# Skill Registry 热加载接口
@router.post("/skill/sync")
async def sync_skills():
    """扫描文件系统，同步Skill到OpenHarness"""
    skills_dir = Path("skills")
    registered_skills = SkillRegistry.scan(skills_dir)

    # 热加载：OpenHarness原生支持动态注册
    for skill in registered_skills:
        SkillRegistry.register(skill)
        logger.info(f"Skill热加载: {skill.name} v{skill.version}")

    return {
        "success": True,
        "registered": len(registered_skills),
        "skills": [s.dict() for s in registered_skills]
    }
```

### 4.4 Skill Markdown编辑器

```typescript
const SkillEditor: React.FC = () => {
  const [content, setContent] = useState('')
  const [previewMode, setPreviewMode] = useState<'edit' | 'split' | 'preview'>('split')

  return (
    <div className="skill-editor">
      {/* 工具栏 */}
      <div className="editor-toolbar">
        <Radio.Group value={previewMode} onChange={e => setPreviewMode(e.target.value)}>
          <Radio.Button value="edit">编辑</Radio.Button>
          <Radio.Button value="split">分栏</Radio.Button>
          <Radio.Button value="preview">预览</Radio.Button>
        </Radio.Group>
        <Space>
          <Button icon={<SaveOutlined />} type="primary">保存</Button>
          <Button icon={<PlayCircleOutlined />}>测试运行</Button>
        </Space>
      </div>

      {/* 编辑区 */}
      <div className={`editor-body mode-${previewMode}`}>
        <CodeMirror
          value={content}
          onChange={setContent}
          extensions={[markdown(), python()]}
          theme="dark"
        />
        {previewMode !== 'edit' && (
          <ReactMarkdown className="preview-pane">
            {content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  )
}
```

---

## 5. 实施计划

| 阶段 | 内容 | 预估 |
|------|------|------|
| P0-1 | Skill列表视图（ProTable + 分类筛选 + 启用/禁用） | 2天 |
| P0-2 | Skill Markdown编辑器（CodeMirror + 实时预览） | 2天 |
| P0-3 | OpenHarness热加载集成（Sync API + WebSocket通知） | 1天 |
| P1-1 | Skill测试运行面板 | 2天 |
| P1-2 | Skill版本管理（Timeline + diff） | 2天 |
| P2-1 | React Flow工作流编排（节点拖拽 + 连线） | 3天 |

---

## 6. 结论

- **不引入完整的外部Skill管理平台**：Dify/n8n/Flowise定位和技术栈不匹配
- **React Flow作为核心可视化组件**：最匹配的技术栈+MIT协议+完全可定制
- **自研Skill管理员层**：基于Ant Design ProTable/Card/CodeMirror构建
- **复用设计参考**：Dify插件市场交互、n8n节点编排、Claude Code Skill规范

---

*关联文档: [全链路架构设计](../02-architecture/ARCHITECTURE_FULL_CHAIN.md), [全链路深入实现设计 v2.0](../02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md), [ADR-014 技能热插拔架构](ADR-014_技能热插拔架构.md), [Skills DESIGN](../03-modules/skills/DESIGN.md), [ODAP综合优化设计文档.md](../ODAP综合优化设计文档.md)*
