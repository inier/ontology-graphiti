# ADR-052: 智能问答WebUI 开源项目选型

> **日期**: 2026-05-06 | **状态**: 提议 | **决策者**: 架构组

---

## 1. 背景与需求

ODAP系统需要一个现代化的智能问答WebUI，核心需求如下：

### 1.1 功能需求

| 需求 | 优先级 |
|------|--------|
| WorkBuddy式三栏弹性布局（左栏工作空间+场景+会话，中栏问答，右栏扩展） | P0 |
| 左栏支持工作空间切换、场景管理、会话历史、Skill/本体管理入口 | P0 |
| 中栏支持Markdown渲染、流式输出、消息引用、代码高亮 | P0 |
| 右栏支持执行建议、Skill状态、本体详情 | P1 |
| 三栏均可折叠，响应式适配 | P1 |
| 与OpenHarness后端通过标准API通信 | P0 |
| 支持文件上传、多模态输入 | P1 |

### 1.2 技术约束

- 须与现有React 19 + TypeScript + Ant Design 6技术栈兼容
- 须支持私有化部署
- 须支持通过反向代理挂载到主应用子路径
- 开源协议允许商用

---

## 2. 候选项目概览

### 2.1 LobeChat

| 维度 | 详情 |
|------|------|
| **GitHub Stars** | ~58K |
| **技术栈** | React + TypeScript + Ant Design |
| **开源协议** | Apache 2.0 |
| **布局** | 左侧会话列表 + 右侧聊天区（双栏） |
| **核心能力** | 多模型切换、插件生态系统、知识库RAG、多模态、主题定制 |

**关键特性**：
-   **统一ModelProvider接口**：抽象了20+家模型服务商，支持OpenAI/Claude/Gemini/DeepSeek/Ollama
-   **插件系统**：基于JSON Schema定义工具能力，语义理解自动触发调用
-   **知识库**：文件上传、知识管理、RAG检索增强生成
-   **高颜值UI**：圆润设计、丝滑动效、深色模式、自定义主题

**与ODAP匹配度分析**：

| 维度 | 匹配度 | 说明 |
|------|--------|------|
| 技术栈兼容性 | ⭐⭐⭐⭐⭐ | 同为React+TS+Ant Design，可直接复用组件 |
| 布局模式 | ⭐⭐ | 原生仅双栏，需大量改造才能实现三栏布局 |
| 多模型支持 | ⭐⭐⭐⭐⭐ | 完美支持，可对接OpenHarness后端 |
| 插件/工具系统 | ⭐⭐⭐⭐ | 插件机制可映射到Skill系统 |
| 工作空间概念 | ⭐ | 无原生工作空间/场景管理 |
| RAG/知识库 | ⭐⭐⭐⭐ | 支持知识库，可对接Graphiti |
| 可定制性 | ⭐⭐⭐ | 代码结构清晰但核心逻辑耦合度中等 |

### 2.2 Open WebUI

| 维度 | 详情 |
|------|------|
| **GitHub Stars** | ~105K |
| **技术栈** | Svelte + Python (后端) |
| **开源协议** | MIT |
| **布局** | 经典ChatGPT风格（侧边栏+聊天区） |
| **核心能力** | Ollama原生集成、多模型管理、团队管理、文档RAG、Pipeline插件 |

**关键特性**：
-   开发速度极快，功能深度高
-   模型管理、提示预设、团队用户管理、语音输入
-   内置PDF文档解析器
-   Pipeline插件框架（UI无关的OpenAI兼容插件）

**与ODAP匹配度分析**：

| 维度 | 匹配度 | 说明 |
|------|--------|------|
| 技术栈兼容性 | ⭐ | Svelte vs React，完全不兼容现有技术栈 |
| 布局模式 | ⭐⭐ | 经典双栏，无三栏原生支持 |
| 多模型支持 | ⭐⭐⭐⭐⭐ | Ollama原生+OpenAI兼容API |
| 插件/工具系统 | ⭐⭐⭐⭐ | Pipeline框架，灵活但需适配 |
| 工作空间概念 | ⭐⭐ | 有团队管理，但非工作空间 |
| RAG/知识库 | ⭐⭐⭐⭐ | 内置文档解析 |
| 可定制性 | ⭐⭐ | Svelte生态小，团队成员不熟悉 |

### 2.3 LibreChat

| 维度 | 详情 |
|------|------|
| **GitHub Stars** | ~25K |
| **技术栈** | React + Node.js + MongoDB |
| **开源协议** | MIT |
| **布局** | 经典ChatGPT风格 |
| **核心能力** | 多模型、多用户、预设管理、代码执行沙箱、消息搜索 |

**关键特性**：
-   企业级多用户认证系统
-   Docker Compose + Helm Charts一键部署
-   支持OpenAI/GPT-4 Vision/Bing/Anthropic/Google Gemini
-   沙箱化代码执行环境

**与ODAP匹配度分析**：

| 维度 | 匹配度 | 说明 |
|------|--------|------|
| 技术栈兼容性 | ⭐⭐⭐ | React但非Ant Design，后端Node.js |
| 布局模式 | ⭐⭐ | 经典双栏 |
| 多模型支持 | ⭐⭐⭐⭐ | 多模型但不如LobeChat灵活 |
| 插件/工具系统 | ⭐⭐ | 主要通过预设扩展 |
| 工作空间概念 | ⭐ | 无 |
| 可定制性 | ⭐⭐⭐ | 代码结构清晰但扩展点有限 |

### 2.4 Dify (Web前端部分)

| 维度 | 详情 |
|------|------|
| **GitHub Stars** | ~110K |
| **技术栈** | React + TypeScript + Python后端 |
| **开源协议** | Apache 2.0 |
| **布局** | 左侧应用列表 + 中间聊天/工作流区（管理后台风格） |
| **核心能力** | AI工作流、RAG管道、Agent编排、插件市场 |

**关键特性**：
-   **一体化AI工作台**：可视化工作流+知识库+Agent+模型管理
-   **RAG引擎**：完整的文档处理管道
-   **插件市场**：600+插件，覆盖模型/工具/策略/扩展
-   **分层架构**：数据层→开发层→编排层→基础设施层

**与ODAP匹配度分析**：

| 维度 | 匹配度 | 说明 |
|------|--------|------|
| 技术栈兼容性 | ⭐⭐⭐⭐ | React+TS，风格接近但非Ant Design |
| 布局模式 | ⭐⭐⭐ | 原生多栏管理后台风格，接近目标 |
| AI工作流 | ⭐⭐⭐⭐⭐ | 业界最佳AI工作流可视化 |
| RAG/知识库 | ⭐⭐⭐⭐⭐ | 最强的RAG管道能力 |
| 工作空间概念 | ⭐⭐⭐ | 有应用/项目隔离概念 |
| Skill/工具管理 | ⭐⭐⭐⭐ | 插件市场模式可参考 |

### 2.5 候选项目总结对比

| 维度 | LobeChat | Open WebUI | LibreChat | Dify |
|------|----------|-----------|-----------|------|
| **技术栈兼容** | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **布局接近目标** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **多模型支持** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **插件/工具系统** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **RAG/知识库** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **工作空间** | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ |
| **可定制性** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **社区活跃度** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **学习成本** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 3. 决策

### 3.1 推荐方案：**自研为主 + LobeChat插件系统参考**

**不建议直接Fork任何一个现有开源项目**，原因如下：

1. **布局需求不匹配**：所有候选项目均为双栏布局，与ODAP三栏布局目标差距大。改造现有项目的成本 ≈ 重写核心布局层。
2. **工作空间/场景管理缺失**：所有项目均缺乏ODAP核心的"工作空间-场景-本体"层级管理概念。
3. **技术栈绑定风险**：Open WebUI使用Svelte，LibreChat使用Node.js后端，与ODAP技术栈冲突。

### 3.2 技术选型决策

| 组件 | 选型 | 来源 |
|------|------|------|
| **应用框架** | React 19 + TypeScript | 现有 |
| **UI组件库** | Ant Design 6 + **Ant Design X** | 现有 + 新增 |
| **聊天消息组件** | Ant Design X (Bubble, Sender, Conversation) | 新增，专门为AI交互设计 |
| **布局组件** | 基于Ant Design Layout自研三栏组件 | 自研 |
| **Markdown渲染** | react-markdown + rehype-highlight | 新增 |
| **图谱可视化** | AntV G6 + Graphin | 现有强化 |
| **工作流可视化** | React Flow | 新增（Skill管理用） |
| **代码编辑器** | CodeMirror 6 | 新增 |

### 3.3 可复用的开源设计

| 来源 | 复用内容 |
|------|---------|
| **LobeChat** | ModelProvider抽象接口、插件JSON Schema定义、流式响应处理、主题系统 |
| **Dify** | 知识库RAG管道的UI交互模式、工作流节点拖拽交互 |
| **Ant Design X** | Bubble气泡组件、Sender发送器、Conversation会话列表、useXChat Hook |

---

## 4. 集成架构设计

### 4.1 前后端通信架构

```
┌───────────────────────────────────────────────────────────────────────┐
│                        ODAP WebUI (React SPA)                          │
├───────────────┬────────────────────────────┬──────────────────────────┤
│   左栏组件    │        中栏组件            │      右栏组件            │
│  (Sidebar)    │     (ChatMain)             │    (ExtensionPanel)      │
└───────┬───────┴────────────┬───────────────┴──────────┬───────────────┘
        │                    │                          │
        └────────────────────┼──────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │   API Gateway   │
                    │  /api/v1/*       │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  QA Engine   │ │  Skill API   │ │  Ontology    │
    │  /qa/chat    │ │  /skill/*    │ │  /ontology/* │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │                │                │
           ▼                ▼                ▼
    ┌──────────────────────────────────────────────────┐
    │              OpenHarness Infrastructure            │
    └──────────────────────────────────────────────────┘
```

### 4.2 核心通信协议

```typescript
// SSE流式问答接口
interface ChatStreamRequest {
  session_id: string;
  workspace_id: string;
  scenario_id: string;
  message: string;
  attached_entities?: string[];  // 引用的本体实体ID
  preferred_skills?: string[];  // 用户指定的Skill
}

interface ChatStreamEvent {
  type: 'token' | 'tool_call' | 'suggestion' | 'error' | 'done';
  data: {
    content?: string;           // token增量
    tool_call?: ToolCallInfo;   // Skill调用信息
    suggestions?: Suggestion[]; // 执行建议
    error?: string;
  };
}
```

### 4.3 三栏布局组件树

```
<AppLayout>
  ├── <TopNav>                    // 顶部导航栏 (56px)
  │   ├── Logo + 系统名
  │   ├── 全局搜索
  │   └── 用户菜单
  │
  └── <ThreeColumnLayout>         // 三栏主体
      ├── <LeftSidebar>           // 左栏 (240-320px, 可折叠)
      │   ├── <WorkspaceSwitcher>    // 工作空间切换
      │   ├── <ScenarioTree>         // 场景管理
      │   ├── <SessionHistory>       // 会话历史
      │   └── <QuickActions>         // 快捷入口
      │
      ├── <MainContent>           // 中栏 (flex: 1)
      │   ├── <ChatHeader>           // 会话标题+操作
      │   ├── <MessageList>          // 消息列表
      │   │   └── <MessageBubble>    // 消息气泡 (Ant Design X)
      │   └── <ChatInput>            // 输入区
      │       └── <Sender>           // 发送器 (Ant Design X)
      │
      └── <RightPanel>            // 右栏 (280-360px, 可折叠)
          ├── <SuggestionPanel>      // 执行建议
          ├── <SkillStatus>          // Skill状态
          └── <EntityDetail>         // 本体详情
```

---

## 5. 实施建议

### 5.1 分阶段实施

| 阶段 | 内容 | 时间 |
|------|------|------|
| P0-1 | 基于现有QAChatPage，引入Ant Design X，重构为三栏弹性布局 | 1周 |
| P0-2 | 实现左侧栏：工作空间切换、场景管理、会话历史 | 1周 |
| P0-3 | 实现中间栏：Markdown渲染、流式输出、文件上传 | 1周 |
| P1-1 | 实现右侧栏：执行建议、Skill状态、本体详情 | 1周 |
| P1-2 | 响应式适配、移动端优化 | 0.5周 |

### 5.2 关键风险

| 风险 | 缓解措施 |
|------|---------|
| Ant Design X 尚在beta阶段 | 锁定版本，核心组件有替代方案 |
| 三栏布局性能问题 | 使用React.memo + 虚拟滚动优化消息列表 |
| 工作空间切换状态丢失 | Zustand persist中间件自动保存关键状态 |

---

## 6. 结论

- **不自研基础聊天组件**：使用Ant Design X的Bubble/Sender/Conversation等成熟AI组件
- **不Fork开源Chat UI项目**：布局和目标差异太大，改造不如自研
- **重点自研**：三栏布局框架、工作空间/场景管理、与OpenHarness的深度集成
- **参考设计**：LobeChat的插件系统、Dify的工作流交互模式

---

*关联文档: [全链路架构设计](../02-architecture/ARCHITECTURE_FULL_CHAIN.md), [全链路深入实现设计 v2.0](../02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md), [ARCHITECTURE_WEB.md](../02-architecture/ARCHITECTURE_WEB.md), [ODAP综合优化设计文档.md](../ODAP综合优化设计文档.md)*
