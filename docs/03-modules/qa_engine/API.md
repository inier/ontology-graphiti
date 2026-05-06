# 问答引擎模块 (QA Engine) - API 使用文档

> **文档版本**: 1.0.0 | **日期**: 2026-04-28 | **模块**: M-12

---

## 1. 概述

本文档描述问答引擎模块的 API 接口规范，包括请求格式、响应格式、数据模型及使用示例。

### 1.1 基础信息

| 项目 | 说明 |
|------|------|
| 基础路径 | `/api/qa` |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |
| 认证方式 | Header Authorization (Bearer Token) |

### 1.2 错误响应格式

```json
{
  "detail": "错误描述信息",
  "code": "ERROR_CODE",
  "timestamp": "2026-04-28T10:30:00Z"
}
```

---

## 2. 核心接口

### 2.1 问答接口 - POST /api/qa/ask

发送问题并获取回答。

**请求头**：

```
Content-Type: application/json
Authorization: Bearer {token}
```

**请求体**：

```json
{
  "question": "string",          // 用户问题（必填）
  "session_id": "string",        // 会话 ID（可选，不传则创建新会话）
  "workspace_id": "string",      // 工作空间 ID（可选）
  "user_id": "string"            // 用户 ID（可选，默认 "anonymous"）
}
```

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/qa/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "B区有哪些雷达目标?",
    "session_id": "SESSION-ABC12345",
    "workspace_id": "ws-001"
  }'
```

**响应体**：

```json
{
  "session_id": "SESSION-ABC12345",
  "answer": "根据查询，B区发现了3个雷达目标...",
  "sources": [
    {
      "source": "graphiti_entity_001",
      "excerpt": "B区雷达站部署于2024年...",
      "confidence": 0.92
    }
  ],
  "dialog_state": "in_progress",
  "intent": {
    "type": "entity_lookup",
    "confidence": 0.95
  },
  "sources_used": ["graphiti", "rag"]
}
```

**响应字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID，用于多轮对话 |
| answer | string | 生成的回答内容 |
| sources | array | 参考来源列表 |
| sources[].source | string | 来源标识 |
| sources[].excerpt | string | 来源内容摘要 |
| sources[].confidence | float | 来源置信度 (0-1) |
| dialog_state | string | 对话状态：new/in_progress/completed/escalated |
| intent | object | 识别到的用户意图 |
| intent.type | string | 意图类型 |
| intent.confidence | float | 意图置信度 |
| sources_used | array | 使用的检索源 |

### 2.2 会话列表 - GET /api/qa/sessions

获取用户的会话列表。

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 否 | 按用户 ID 过滤 |
| limit | int | 否 | 返回数量，默认 50，最大 200 |

**请求示例**：

```bash
curl -X GET "http://localhost:8000/api/qa/sessions?limit=10" \
  -H "Authorization: Bearer {token}"
```

**响应体**：

```json
{
  "sessions": [
    {
      "session_id": "SESSION-ABC12345",
      "summary": "关于雷达目标查询的对话",
      "message_count": 5,
      "model": "gpt-4",
      "created_at": 1714294800
    }
  ],
  "total": 1,
  "limit": 10
}
```

### 2.3 获取会话详情 - GET /api/qa/sessions/{session_id}

获取指定会话的详细信息。

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |

**请求示例**：

```bash
curl -X GET "http://localhost:8000/api/qa/sessions/SESSION-ABC12345" \
  -H "Authorization: Bearer {token}"
```

**响应体**：

```json
{
  "session_id": "SESSION-ABC12345",
  "messages": [
    {
      "message_id": "MSG-001",
      "role": "user",
      "content": "B区有哪些雷达目标?",
      "timestamp": "2026-04-28T10:30:00Z"
    },
    {
      "message_id": "MSG-002",
      "role": "assistant",
      "content": "根据查询，B区发现了3个雷达目标...",
      "timestamp": "2026-04-28T10:30:05Z"
    }
  ],
  "total": 2
}
```

### 2.4 删除会话 - DELETE /api/qa/sessions/{session_id}

关闭并删除指定会话。

**请求示例**：

```bash
curl -X DELETE "http://localhost:8000/api/qa/sessions/SESSION-ABC12345" \
  -H "Authorization: Bearer {token}"
```

**响应体**：

```json
{
  "status": "success",
  "session_id": "SESSION-ABC12345"
}
```

### 2.5 获取会话历史 - GET /api/qa/sessions/{session_id}/history

获取会话的消息历史。

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| limit | int | 否 | 返回消息数量，默认 50 |

**请求示例**：

```bash
curl -X GET "http://localhost:8000/api/qa/sessions/SESSION-ABC12345/history?limit=20" \
  -H "Authorization: Bearer {token}"
```

**响应体**：

```json
{
  "session_id": "SESSION-ABC12345",
  "history": [
    {
      "message_id": "MSG-001",
      "role": "user",
      "content": "B区有哪些雷达目标?",
      "timestamp": "2026-04-28T10:30:00Z"
    }
  ],
  "total": 1
}
```

### 2.6 提交反馈 - POST /api/qa/sessions/{session_id}/feedback

提交对回答的反馈。

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |

**请求体**：

```json
{
  "feedback": {
    "helpful": true,
    "accuracy": 5,
    "comment": "回答很准确"
  },
  "rating": 5,
  "user_id": "user-001"
}
```

**请求示例**：

```bash
curl -X POST "http://localhost:8000/api/qa/sessions/SESSION-ABC12345/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": {"helpful": true, "accuracy": 5},
    "rating": 5
  }'
```

**响应体**：

```json
{
  "status": "success",
  "feedback_id": "fb_abc123def456"
}
```

---

## 3. 统计接口

### 3.1 获取统计数据 - GET /api/qa/stats

获取问答统计数据。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_id | string | 否 | 工作空间 ID |
| start_time | string | 否 | 开始时间 (ISO 8601) |
| end_time | string | 否 | 结束时间 (ISO 8601) |

**请求示例**：

```bash
curl -X GET "http://localhost:8000/api/qa/stats?workspace_id=ws-001" \
  -H "Authorization: Bearer {token}"
```

**响应体**：

```json
{
  "total": 486,
  "today": 42,
  "by_intent": {
    "entity_lookup": 320,
    "relation_query": 89,
    "comparison": 45,
    "time_series": 32
  },
  "by_source": {
    "graphiti": 280,
    "rag": 156,
    "mock": 50
  },
  "time_distribution": {
    "0": 5,
    "1": 3,
    "9": 28,
    "14": 45,
    "18": 32
  },
  "period": {
    "start": "2026-04-01T00:00:00Z",
    "end": "2026-04-28T23:59:59Z"
  }
}
```

### 3.2 获取用户统计 - GET /api/qa/stats/users

获取用户使用统计。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_id | string | 否 | 工作空间 ID |
| limit | int | 否 | 返回数量，默认 10 |

**响应体**：

```json
{
  "user_stats": [
    {
      "user_id": "admin",
      "count": 156,
      "first_time": "2026-04-01T08:00:00Z",
      "last_time": "2026-04-28T18:30:00Z"
    }
  ],
  "total_users": 5,
  "limit": 10
}
```

### 3.3 获取话题统计 - GET /api/qa/stats/topics

获取热门话题统计。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_id | string | 否 | 工作空间 ID |
| limit | int | 否 | 返回数量，默认 20 |

**响应体**：

```json
{
  "topics": [
    {
      "topic": "雷达目标查询",
      "count": 45,
      "trend": "up"
    },
    {
      "topic": "部队部署情况",
      "count": 32,
      "trend": "stable"
    }
  ],
  "limit": 20
}
```

---

## 4. 数据模型

### 4.1 会话模型 (Session)

```typescript
interface Session {
  session_id: string;           // 会话唯一标识
  summary: string;               // 会话摘要
  message_count: number;        // 消息数量
  model: string;                // 使用的 LLM 模型
  created_at: number;           // 创建时间戳
  updated_at?: number;          // 更新时间戳
  status?: 'new' | 'active' | 'closed';
}
```

### 4.2 消息模型 (Message)

```typescript
interface QAMessage {
  id: string;                   // 消息唯一标识
  session_id: string;           // 所属会话 ID
  role: 'user' | 'assistant' | 'system';
  content: string;              // 消息内容
  timestamp: string;            // 时间戳 (ISO 8601)
  metadata?: {
    intent?: IntentInfo;
    sources?: SourceInfo[];
    token_usage?: TokenUsage;
    latency_ms?: number;
  };
}

interface IntentInfo {
  type: string;                // 意图类型
  confidence: number;           // 置信度
  entities?: string[];          // 识别的实体
  relations?: string[];         // 识别的关系
}

interface SourceInfo {
  source: string;              // 来源标识
  excerpt: string;            // 内容摘要
  confidence: number;          // 置信度
  url?: string;               // 来源链接
}

interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}
```

### 4.3 对话上下文 (SessionContext)

```typescript
interface SessionContext {
  active_entities: string[];    // 当前关注的实体
  active_time_range?: TimeRange; // 当前讨论的时间范围
  topic_stack: string[];        // 话题栈
  mentioned_resources: string[]; // 提及的资源
  pending_clarifications: string[]; // 待澄清问题
}

interface TimeRange {
  start: string;               // 开始时间
  end: string;                 // 结束时间
  type: 'point' | 'range' | 'relative';
}
```

### 4.4 意图类型 (IntentType)

```typescript
enum IntentType {
  ENTITY_LOOKUP = "entity_lookup",       // 实体查询
  RELATION_QUERY = "relation_query",     // 关系查询
  TIME_SERIES = "time_series",           // 时序查询
  COMPARISON = "comparison",             // 对比查询
  AGGREGATION = "aggregation",           // 聚合查询
  CAUSALITY = "causality",               // 因果查询
  HYPOTHETICAL = "hypothetical",         // 假设查询
  CLARIFICATION = "clarification",       // 澄清请求
  GENERAL = "general"                    // 通用问答
}
```

---

## 5. 使用示例

### 5.1 单轮问答

```typescript
async function askQuestion(question: string) {
  const response = await fetch('/api/qa/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ question })
  });

  const data = await response.json();
  return data;
}

// 使用
const result = await askQuestion("B区有哪些雷达目标?");
console.log(result.answer);
```

### 5.2 多轮对话

```typescript
let sessionId: string | null = null;

async function sendMessage(question: string) {
  const response = await fetch('/api/qa/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      question,
      session_id: sessionId  // 传入 session_id 保持对话上下文
    })
  });

  const data = await response.json();
  sessionId = data.session_id;  // 更新 session_id
  return data;
}

// 多轮对话
const r1 = await sendMessage("B区有哪些雷达目标?");
const r2 = await sendMessage("还有其他的吗?");  // 使用同一 session_id
const r3 = await sendMessage("它们分别是什么型号?");  // 上下文保持
```

### 5.3 获取历史会话

```typescript
async function getSessionHistory(sessionId: string) {
  const response = await fetch(`/api/qa/sessions/${sessionId}/history`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  const data = await response.json();
  return data.history;
}

// 使用
const history = await getSessionHistory('SESSION-ABC12345');
history.forEach(msg => {
  console.log(`[${msg.role}]: ${msg.content}`);
});
```

### 5.4 提交反馈

```typescript
async function submitFeedback(sessionId: string, rating: number, comment: string) {
  const response = await fetch(`/api/qa/sessions/${sessionId}/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      rating,
      feedback: {
        helpful: rating >= 4,
        accuracy: rating,
        comment
      }
    })
  });

  return response.json();
}

// 使用
await submitFeedback('SESSION-ABC12345', 5, '回答很准确！');
```

### 5.5 React Hooks 集成

```typescript
import { useQAI, QAMessage } from '@/modules/qa/hooks/useQAI';

function QAComponent() {
  const {
    messages,
    sendMessage,
    status,
    isLoading,
    sessionId,
    clearMessages
  } = useQAI();

  return (
    <div>
      {/* 消息列表 */}
      <div className="messages">
        {messages.map((msg: QAMessage) => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <div className="content">{msg.content}</div>
            {msg.sources && (
              <div className="sources">
                来源: {msg.sources.map(s => s.source).join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 输入框 */}
      <input
        type="text"
        onKeyPress={(e) => {
          if (e.key === 'Enter') {
            sendMessage(e.currentTarget.value);
          }
        }}
        disabled={isLoading}
      />

      {/* 状态显示 */}
      <div>状态: {status}</div>
      {isLoading && <div>加载中...</div>}
    </div>
  );
}
```

---

## 6. 错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| QA_001 | 400 | 问题不能为空 |
| QA_002 | 404 | 会话不存在 |
| QA_003 | 500 | 问答引擎内部错误 |
| QA_004 | 503 | 图谱服务不可用 |
| QA_005 | 504 | 问答响应超时 |
| AUTH_001 | 401 | 未授权 |
| AUTH_002 | 403 | 权限不足 |

---

## 7. 限流策略

| 端点 | 限制 | 窗口 |
|------|------|------|
| POST /api/qa/ask | 60 请求 | 1 分钟 |
| GET /api/qa/sessions | 100 请求 | 1 分钟 |
| 其他接口 | 200 请求 | 1 分钟 |

---

## 8. 相关文档

- [集成方案文档](./INTEGRATION.md)
- [架构设计文档](./DESIGN.md)
- [ADR-039 问答引擎架构决策](../../07-adr/ADR-039_qa_engine_architecture.md)
