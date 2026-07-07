# ADR-052: 智能问答 WebUI 开源项目选型

## 状态

提议

## 上下文

ODAP 系统需要一个现代化的智能问答 WebUI，核心需求如下：

### 功能需求

| 需求 | 优先级 |
|------|--------|
| WorkBuddy 式三栏弹性布局（左栏工作空间+场景+会话，中栏问答，右栏扩展） | P0 |
| 左栏支持工作空间切换、场景管理、会话历史、Skill/本体管理入口 | P0 |
| 中栏支持 Markdown 渲染、流式输出、消息引用、代码高亮 | P0 |
| 右栏支持执行建议、Skill 状态、本体详情 | P1 |
| 三栏均可折叠，响应式适配 | P1 |
| 与 OpenHarness 后端通过标准 API 通信 | P0 |
| 支持文件上传、多模态输入 | P1 |

### 技术约束

- 须与现有 React 19 + TypeScript + Ant Design 6 技术栈兼容
- 须支持私有化部署
- 须支持通过反向代理挂载到主应用子路径
- 开源协议允许商用

### 候选项目评估

| 候选项目 | 技术栈兼容 | 布局匹配 | 多模型支持 | 插件/工具 | RAG/知识库 | 工作空间 | 可定制性 | 集成成本 |
|----------|------------|----------|------------|-----------|------------|----------|----------|----------|
| **LobeChat** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | 高(Fork) |
| **Open WebUI** | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | 高(Fork) |
| **LibreChat** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | 高(Fork) |
| **Dify** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 高(Fork) |

**关键发现**：所有候选项目均为双栏布局，与 ODAP 三栏布局目标差距大。改造现有项目的成本 ≈ 重写核心布局层。且所有项目均缺乏 ODAP 核心的"工作空间-场景-本体"层级管理概念。

## 决策

### 推荐方案：自研为主 + LobeChat 插件系统参考

**不建议直接 Fork 任何一个现有开源项目**，原因：

1. **布局需求不匹配**：所有候选项目均为双栏布局，改造成本 ≈ 重写
2. **工作空间/场景管理缺失**：所有项目均缺乏 ODAP 核心概念
3. **技术栈绑定风险**：Open WebUI 使用 Svelte，LibreChat 使用 Node.js，与 ODAP 技术栈冲突

### 技术选型

| 组件 | 选型 | 来源 |
|------|------|------|
| **应用框架** | React 19 + TypeScript | 现有 |
| **UI 组件库** | Ant Design 6 + **Ant Design X** | 现有 + 新增 |
| **聊天消息组件** | Ant Design X (Bubble, Sender, Conversation) | 新增，AI 交互专用 |
| **布局组件** | 基于 Ant Design Layout 自研三栏组件 | 自研 |
| **Markdown 渲染** | react-markdown + rehype-highlight | 新增 |
| **图谱可视化** | AntV G6 + Graphin | 现有强化 |
| **工作流可视化** | React Flow | 新增（Skill 管理用） |
| **代码编辑器** | CodeMirror 6 | 新增 |

### 可复用的开源设计

| 来源 | 复用内容 |
|------|---------|
| **LobeChat** | ModelProvider 抽象接口、插件 JSON Schema 定义、流式响应处理、主题系统 |
| **Dify** | 知识库 RAG 管道的 UI 交互模式、工作流节点拖拽交互 |
| **Ant Design X** | Bubble 气泡组件、Sender 发送器、Conversation 会话列表、useXChat Hook |

### 三栏布局组件树

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
          ├── <SkillStatus>          // Skill 状态
          └── <EntityDetail>         // 本体详情
```

## 后果

**正面**：
- 完全掌控三栏布局架构，可灵活调整
- 技术栈统一，维护成本低
- 工作空间/场景管理深度集成
- 可复用 Ant Design X 成熟 AI 组件

**负面**：
- 自研工作量较大（预估 4.5 周）
- 需自行实现流式响应、Markdown 渲染等基础能力
- Ant Design X 尚在 beta 阶段，存在稳定性风险

## 可逆性

高。自研方案可随时调整技术选型，不受外部项目约束。如后续发现更合适的开源方案，可平滑迁移。

## 关联 ADR

- ADR-007：前端采用 React + Ant Design 技术栈
- ADR-053：Skill 可视化管理开源方案选型
- ADR-025：基于 OpenHarness 实现多智能体协同
- ADR-039：问答引擎架构
