# 智能问答功能升级 - OpenHarness React 集成规范

## 1. 概述

### 1.1 项目背景
本项目旨在集成 `@openharness/react` 库，结合 AI SDK，实现智能问答功能的前端升级。

### 1.2 库分析

| 属性 | 值 |
|------|-----|
| **npm 包名** | `@openharness/react` |
| **版本** | 1.0.1 |
| **主依赖** | `ai: ^6.0.97` |
| **描述** | React hooks and provider for OpenHarness AI SDK 5 integration |
| **维护者** | maxgfeller |
| **许可证** | MIT |

### 1.3 技术栈兼容性

| 组件 | @openharness/react | 当前项目 | 兼容性 |
|------|---------------------|----------|--------|
| React | 18+ | 19.2.4 | 高 |
| ai SDK | 6.0.97+ | - | 高 |
| UI 框架 | 无限制 | Ant Design | 高 |
| TypeScript | 支持 | 支持 | 高 |

## 2. 功能需求

### 2.1 新增功能
- **FR-1**: 集成 @openharness/react 库
- **FR-2**: 实现基于 AI SDK 的问答功能
- **FR-3**: 多轮对话能力（上下文理解）
- **FR-4**: 历史会话管理（存储、加载、删除）
- **FR-5**: 对话状态保持（页面刷新恢复）

### 2.2 修改功能
- **FR-6**: 升级现有 QAChat 界面

## 3. 架构设计

### 3.1 前端架构
```
┌─────────────────────────────────────────────┐
│              React Frontend                  │
├─────────────────────────────────────────────┤
│  @openharness/react                         │
│    ├── useChat (对话状态管理)               │
│    ├── useConversationalSession (会话管理)  │
│    └── <AI> Provider (AI SDK 集成)          │
├─────────────────────────────────────────────┤
│  QAChatPage                                │
│    ├── ChatHeader (会话选择)                │
│    ├── MessageList (消息列表)               │
│    ├── ChatInput (输入框)                   │
│    └── SessionDrawer (会话管理抽屉)         │
└─────────────────────────────────────────────┘
```

### 3.2 后端架构（复用现有）
```
┌─────────────────────────────────────────────┐
│              Python Backend                  │
├─────────────────────────────────────────────┤
│  QAEngineV2                                │
│    ├── DialogManager (对话管理)             │
│    ├── RAGPipeline (检索增强)              │
│    └── SourceTracer (溯源追踪)              │
├─────────────────────────────────────────────┤
│  API Routes                                │
│    ├── /api/qa/ask                        │
│    ├── /api/qa/sessions                    │
│    └── /api/qa/history                    │
└─────────────────────────────────────────────┘
```

## 4. API 设计

### 4.1 REST API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/qa/ask | 发送问答请求 |
| GET | /api/qa/sessions | 获取会话列表 |
| GET | /api/qa/sessions/{id} | 获取会话详情 |
| DELETE | /api/qa/sessions/{id} | 删除会话 |
| GET | /api/qa/sessions/{id}/history | 获取对话历史 |

### 4.2 数据模型
```typescript
// 消息
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  sources?: Source[];
  intent?: Intent;
}

// 会话
interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

// 请求
interface QARequest {
  question: string;
  session_id?: string;
  context?: Record<string, unknown>;
}

// 响应
interface QAResponse {
  answer: string;
  session_id: string;
  sources: Source[];
  intent?: Intent;
}
```

## 5. 实施计划

### 5.1 阶段划分
- **Phase 1**: 库集成和配置
- **Phase 2**: 前端界面开发
- **Phase 3**: 后端 API 集成
- **Phase 4**: 会话持久化
- **Phase 5**: 测试和优化

### 5.2 任务分解
1. 安装 @openharness/react 和 ai SDK
2. 创建 AI Provider 配置
3. 实现 useChat Hooks
4. 开发 QAChatPage 组件
5. 集成后端 API
6. 实现会话管理
7. 实现状态持久化
8. 编写文档
9. 测试验证

## 6. 验收标准

### 6.1 功能验收
- [ ] @openharness/react 库成功集成
- [ ] 构建成功，无兼容性错误
- [ ] 多轮对话正常工作
- [ ] 会话管理功能正常
- [ ] 状态持久化正常

### 6.2 性能验收
- [ ] 简单问答响应 < 2s
- [ ] 界面交互流畅

### 6.3 文档验收
- [ ] 技术方案文档完整
- [ ] API 文档更新