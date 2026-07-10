# 会话记忆与思维链可视化模块 (Session Memory & CoT Visualization) - 设计文档

> **模块 ID**: M-21 | **优先级**: P1 | **相关 ADR**: ADR-030, ADR-039
> **版本**: 1.0.0 | **日期**: 2026-05-07 | **架构层**: L3-L4 业务层 / L6 交互层
> **对应需求**: FR-401 (Agent 决策过程可视化), FR-1101 (推理路径可视化), FR-1102 (解释引擎)

---

## 1. 模块概述

### 1.1 模块定位

会话记忆与思维链可视化模块负责两件事：
1. **会话记忆管理**：多轮对话的上下文窗口、记忆压缩、状态持久化
2. **思维链可视化**：Agent 推理过程的树形/流程式渲染，支持步骤回溯和交互解释

### 1.2 与 OpenHarness Memory 的关系

```
┌─────────────────────────────────────────────────────────────┐
│                      记忆分层架构                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐     ┌──────────────────┐            │
│  │  OpenHarness     │     │  SessionMemory   │            │
│  │  Memory          │     │  (本模块)         │            │
│  ├──────────────────┤     ├──────────────────┤            │
│  │ Agent 运行时会话  │     │ 用户问答历史       │            │
│  │ CLAUDE.md 发现   │     │ 推理链持久化       │            │
│  │ Auto-Compaction  │     │ 上下文窗口管理     │            │
│  │ Agent 内部状态    │     │ CoT 渲染数据       │            │
│  └──────────────────┘     └──────────────────┘            │
│           │                          │                      │
│           └──────────┬───────────────┘                      │
│                      ▼                                      │
│              ┌──────────────┐                              │
│              │   Graphiti   │  持久化存储                   │
│              │  (长期记忆)   │                              │
│              └──────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **上下文连贯** | 多轮对话 | 智能管理上下文窗口，自动压缩和裁剪 |
| **推理可解释** | CoT 可视化 | 树形渲染 Agent 推理过程，可逐步回溯 |
| **用户信任** | 决策依据展示 | 展示"为什么得出这个结论"的完整链路 |

---

## 2. 会话记忆管理

### 2.1 上下文窗口模型

```python
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

class ChatMessage(BaseModel):
    id: str
    role: MessageRole
    content: str
    tokens: int                    # token 估算
    timestamp: datetime
    entities: list[str] = []       # 消息中涉及的实体 ID
    cot_nodes: list[str] = []      # 关联的推理节点 ID

class ContextWindow(BaseModel):
    """上下文窗口 - 围绕当前对话裁剪的记忆范围"""
    max_tokens: int = 8000          # 窗口容量 (token)
    system_prompt_tokens: int       # 系统 Prompt 固定消耗
    messages: list[ChatMessage]     # 窗口内的消息
    summary: str = ""               # 被裁剪消息的摘要

    @property
    def used_tokens(self) -> int:
        return sum(m.tokens for m in self.messages)

    @property
    def available_tokens(self) -> int:
        return self.max_tokens - self.system_prompt_tokens - self.used_tokens
```

### 2.2 记忆压缩策略

当会话长度超出上下文窗口时，自动压缩：

```python
class MemoryCompactor:
    COMPACTION_THRESHOLD = 0.7      # 使用率超过 70% 触发压缩

    def should_compact(self, window: ContextWindow) -> bool:
        return window.used_tokens / window.max_tokens > self.COMPACTION_THRESHOLD

    async def compact(self, window: ContextWindow) -> ContextWindow:
        """压缩策略：保留最近 N 条 + 历史摘要"""
        recent_count = 4             # 保留最近 4 条
        older_messages = window.messages[:-recent_count]
        recent_messages = window.messages[-recent_count:]

        # 用 LLM 生成旧消息摘要
        summary = await self._summarize(older_messages, existing_summary=window.summary)

        return ContextWindow(
            max_tokens=window.max_tokens,
            system_prompt_tokens=window.system_prompt_tokens,
            messages=recent_messages,
            summary=summary,
        )

    async def _summarize(self, messages: list[ChatMessage],
                         existing_summary: str = "") -> str:
        prompt = self._build_summary_prompt(messages, existing_summary)
        return await self._llm.complete(prompt, max_tokens=200)
```

### 2.3 会话持久化

```python
class SessionStore:
    """会话持久化 - PostgreSQL 存储"""

    async def save_session(self, session: Session) -> str:
        """保存完整会话（消息列表 + 上下文窗口 + 推理链）"""

    async def load_session(self, session_id: str) -> Session | None:
        """加载会话"""

    async def list_sessions(self, workspace_id: str,
                            limit: int = 20) -> list[SessionSummary]:
        """列出工作空间下的历史会话"""

    async def delete_session(self, session_id: str):
        """删除会话（软删除）"""

class Session(BaseModel):
    id: str
    workspace_id: str
    title: str                     # 自动生成或用户编辑
    messages: list[ChatMessage]
    cot_tree: CoTTree              # 推理链树
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
```

---

## 3. 思维链 (CoT) 可视化设计

### 3.1 CoT 树形数据结构

```
┌─────────────────────────────────────────────────────────────┐
│                    CoT 树形结构示例                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                     ┌─────────────────┐                    │
│                     │ 用户: 报告态势   │                    │
│                     └────────┬────────┘                    │
│                              │                             │
│                     ┌────────▼────────┐                    │
│                     │ 意图识别          │                    │
│                     │ 类型: 态势查询    │                    │
│                     └────────┬────────┘                    │
│                              │                             │
│               ┌──────────────┼──────────────┐              │
│               ▼              ▼              ▼              │
│         ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│         │实体链接   │  │上下文检索  │  │RAG增强   │         │
│         │匹配到3个实体│  │获取子图   │  │注入Prompt │         │
│         └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│              │             │             │                │
│              └─────────────┼─────────────┘                │
│                            ▼                              │
│                    ┌───────────────┐                      │
│                    │   LLM 推理    │                      │
│                    │ 生成态势摘要   │                      │
│                    └───────┬───────┘                      │
│                            │                              │
│                    ┌───────▼───────┐                      │
│                    │   回答 + 建议  │                      │
│                    └───────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 数据模型

```python
class CoTNodeType(str, Enum):
    INTENT = "intent"                # 意图识别
    ENTITY_LINK = "entity_link"      # 实体链接
    CONTEXT_FETCH = "context_fetch"  # 上下文检索
    RAG_AUGMENT = "rag_augment"      # RAG 增强
    LLM_INFER = "llm_infer"          # LLM 推理
    TOOL_CALL = "tool_call"          # 工具调用
    TOOL_RESULT = "tool_result"      # 工具结果
    DECISION = "decision"            # 决策节点
    SYNTHESIS = "synthesis"          # 综合回答

class CoTNode(BaseModel):
    id: str
    type: CoTNodeType
    label: str                       # UI 展示标签
    detail: str                      # 展开后的详细内容
    status: str = "pending"          # pending / running / done / error / skipped
    parent_id: str | None = None
    children_ids: list[str] = []
    metadata: dict = {}              # 类型特定元数据
    timing: CoTTiming | None = None

class CoTTiming(BaseModel):
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None

class CoTTree(BaseModel):
    root_id: str
    nodes: dict[str, CoTNode]        # node_id → CoTNode
    current_focus_id: str | None = None
    version: int = 1
```

### 3.3 构建器

```python
class CoTBuilder:
    """思维链构建器 - 在 QA 推理过程中逐步构建思维链"""

    def __init__(self):
        self._tree = CoTTree(root_id="", nodes={})

    def start(self, user_query: str) -> CoTNode:
        root = CoTNode(id=self._next_id(), type=CoTNodeType.INTENT,
                       label=f"用户问题: {user_query[:50]}...",
                       detail=user_query, status="done")
        self._tree.root_id = root.id
        self._tree.nodes[root.id] = root
        return root

    def add_child(self, parent: CoTNode, node_type: CoTNodeType,
                  label: str, detail: str = "") -> CoTNode:
        node = CoTNode(id=self._next_id(), type=node_type, label=label,
                       detail=detail, parent_id=parent.id)
        parent.children_ids.append(node.id)
        self._tree.nodes[node.id] = node
        return node

    def update_status(self, node_id: str, status: str,
                      detail: str = "", timing: CoTTiming | None = None):
        node = self._tree.nodes[node_id]
        node.status = status
        if detail:
            node.detail = detail
        if timing:
            node.timing = timing

    def to_serializable(self) -> dict:
        """序列化为前端可渲染结构"""
        return {
            "rootId": self._tree.root_id,
            "nodes": {nid: self._serialize_node(n) for nid, n in self._tree.nodes.items()},
            "version": self._tree.version,
        }

    def _serialize_node(self, node: CoTNode) -> dict:
        return {
            "id": node.id, "type": node.type.value,
            "label": node.label, "detail": node.detail,
            "status": node.status, "parentId": node.parent_id,
            "childrenIds": node.children_ids,
            "metadata": node.metadata,
            "timing": node.timing.model_dump() if node.timing else None,
        }
```

### 3.4 前端渲染组件

```typescript
interface CoTNodeView {
  id: string
  type: CoTNodeType
  label: string
  detail: string
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped'
  parentId: string | null
  childrenIds: string[]
  metadata: Record<string, any>
  timing?: { startedAt: string; finishedAt: string; durationMs: number }
}

const CoTTreeView: React.FC<{
  tree: { rootId: string; nodes: Record<string, CoTNodeView> }
  onNodeClick: (nodeId: string) => void
  onBacktrack: (nodeId: string) => void
}> = ({ tree, onNodeClick, onBacktrack }) => {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set([tree.rootId]))
  const [selectedNode, setSelectedNode] = useState<string | null>(tree.rootId)
  const [focusPath, setFocusPath] = useState<string[]>([tree.rootId])

  const toggleExpand = (nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev)
      next.has(nodeId) ? next.delete(nodeId) : next.add(nodeId)
      return next
    })
  }

  const selectNode = (nodeId: string) => {
    setSelectedNode(nodeId)
    const path = buildPathToRoot(nodeId, tree.nodes)
    setFocusPath(path)
    onNodeClick(nodeId)
  }

  const renderNode = (nodeId: string, depth: number): React.ReactNode => {
    const node = tree.nodes[nodeId]
    if (!node) return null

    const isExpanded = expandedNodes.has(nodeId)
    const isSelected = selectedNode === nodeId
    const isOnFocusPath = focusPath.includes(nodeId)
    const hasChildren = node.childrenIds.length > 0

    return (
      <div key={nodeId} style={{ marginLeft: depth * 24 }}>
        <div
          className={`cot-node ${node.status} ${isSelected ? 'selected' : ''} ${isOnFocusPath ? 'focus-path' : ''}`}
          onClick={() => selectNode(nodeId)}
        >
          <span className="cot-node-icon">
            {hasChildren && (
              <button onClick={(e) => { e.stopPropagation(); toggleExpand(nodeId) }}>
                {isExpanded ? <CaretDownOutlined /> : <CaretRightOutlined />}
              </button>
            )}
          </span>
          <StatusBadge status={node.status} />
          <span className="cot-node-label">{node.label}</span>
          {node.timing && (
            <span className="cot-node-timing">{node.timing.durationMs}ms</span>
          )}
          {node.status === 'done' && (
            <button
              className="cot-backtrack-btn"
              onClick={(e) => { e.stopPropagation(); onBacktrack(nodeId) }}
              title="回溯到该步骤"
            >
              <UndoOutlined />
            </button>
          )}
        </div>

        {isSelected && node.detail && (
          <div className="cot-node-detail">
            <MarkdownRenderer content={node.detail} />
          </div>
        )}

        {isExpanded && node.childrenIds.map(childId => renderNode(childId, depth + 1))}
      </div>
    )
  }

  return (
    <div className="cot-tree-view">
      <div className="cot-tree-header">
        <Typography.Title level={5}>推理过程</Typography.Title>
        <Button.Group>
          <Button size="small" onClick={() => setExpandedNodes(new Set(Object.keys(tree.nodes)))}>
            全部展开
          </Button>
          <Button size="small" onClick={() => setExpandedNodes(new Set([tree.rootId]))}>
            全部折叠
          </Button>
        </Button.Group>
      </div>
      <div className="cot-tree-body">
        {renderNode(tree.rootId, 0)}
      </div>
    </div>
  )
}

function buildPathToRoot(nodeId: string, nodes: Record<string, CoTNodeView>): string[] {
  const path: string[] = []
  let current: string | null = nodeId
  while (current) {
    path.unshift(current)
    current = nodes[current]?.parentId ?? null
  }
  return path
}
```

### 3.5 回溯机制

```python
class CoTBacktracker:
    """思维链回溯 - 允许从任意节点重新推理"""

    async def backtrack(self, session_id: str, target_node_id: str) -> Session:
        session = await self._store.load_session(session_id)
        tree = session.cot_tree
        target_node = tree.nodes[target_node_id]

        # 裁剪 target_node 之后的所有子孙节点
        pruned_ids = self._collect_descendants(tree, target_node_id)
        for nid in pruned_ids:
            del tree.nodes[nid]
        target_node.children_ids = []

        # 回滚会话消息到 target_node 对应的位置
        rollback_to = len(session.messages)
        for i, msg in enumerate(session.messages):
            if any(nid in msg.cot_nodes for nid in pruned_ids):
                rollback_to = i
                break
        session.messages = session.messages[:rollback_to]

        # 给用户展示：从 target_node 重新开始
        tree.current_focus_id = target_node_id
        target_node.status = "pending"

        await self._store.save_session(session)
        return session

    def _collect_descendants(self, tree: CoTTree, node_id: str) -> set[str]:
        result = set()
        for child_id in tree.nodes[node_id].children_ids:
            result.add(child_id)
            result.update(self._collect_descendants(tree, child_id))
        return result
```

---

## 4. 解释引擎集成

### 4.1 "为什么"查询

```python
class ExplanationEngine:
    """解释引擎 - 处理'为什么'类查询"""

    async def explain_node(self, session_id: str, node_id: str) -> str:
        session = await self._store.load_session(session_id)
        node = session.cot_tree.nodes[node_id]

        # 构建解释上下文
        context = {
            "node_label": node.label,
            "node_detail": node.detail,
            "parent_steps": self._get_ancestor_chain(session.cot_tree, node_id),
            "child_results": self._get_child_summaries(session.cot_tree, node_id),
            "metadata": node.metadata,
        }

        prompt = f"""请解释以下推理步骤的决策依据：

步骤: {context['node_label']}
详情: {context['node_detail']}

前置步骤:
{chr(10).join(f"- {s}" for s in context['parent_steps'])}

本步结果:
{chr(10).join(f"- {s}" for s in context['child_results'])}

请用中文给出清晰易懂的解释。"""

        return await self._llm.complete(prompt)
```

---

## 5. WebSocket 实时推送

```python
class CoTWebSocketHandler:
    """WebSocket 推送 - 推理过程的实时更新"""

    async def stream_cot_updates(self, session_id: str, websocket):
        session = await self._store.load_session(session_id)
        tree = session.cot_tree

        async for update in self._watch_tree_changes(tree.id):
            await websocket.send_json({
                "type": "cot_update",
                "payload": {
                    "nodeId": update.node_id,
                    "status": update.status,
                    "label": update.label,
                    "detail": update.detail,
                    "timing": update.timing,
                }
            })
```

---

## 6. 样式规范

```css
/* cot-tree.css */
.cot-tree-view {
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  height: 100%;
  overflow-y: auto;
}

.cot-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.cot-node:hover { background: rgba(0,0,0,0.04); }
.cot-node.selected { background: rgba(22,119,255,0.1); }
.cot-node.focus-path { border-left: 2px solid #1677ff; }

.cot-node.running .cot-node-label { color: #1677ff; font-weight: 500; }
.cot-node.error .cot-node-label { color: #ff4d4f; }
.cot-node.skipped .cot-node-label { color: #999; text-decoration: line-through; }

.cot-node-icon button {
  background: none; border: none; cursor: pointer;
  padding: 2px; color: #666;
}

.cot-node-detail {
  margin-left: 48px;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.6;
  max-width: 480px;
}

.cot-backtrack-btn {
  margin-left: auto;
  background: none; border: none; cursor: pointer;
  color: #999; padding: 2px 6px;
  visibility: hidden;
}

.cot-node:hover .cot-backtrack-btn { visibility: visible; }
.cot-backtrack-btn:hover { color: #1677ff; }
```

---

## 7. 相关文档

- [ADR-039: QA Engine 架构](../../07-adr/ADR-039_qa_engine_architecture.md)
- [全链路架构设计](../../02-architecture/ARCHITECTURE_FULL_CHAIN.md) — Phase 3 问答 & Phase 5 闭环反馈
- [全链路深入实现设计 v2.0](../../02-architecture/ARCHITECTURE_FULL_CHAIN.md) — §3.7 会话记忆管理, §3.8 上下文窗口
- [QA Engine 模块设计](../qa_engine/DESIGN.md)
- [Visualization 可视化模块设计](../visualization/DESIGN.md)
