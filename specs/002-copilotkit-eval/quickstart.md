# Quickstart: AG-UI + OpenHarness 纯扩展集成

**Date**: 2026-06-08 (v2.0 修订)
**目标读者**: ODAP 后端 / 前端开发人员
**预计阅读时间**: 10 分钟

---

## 1. 5 分钟理解：架构

**v2.0 核心原则**：
- ❌ **0 修改** OpenHarness 核心代码
- ❌ **0 新增** `odap/biz/core/qa/` 业务模块
- ❌ **0 新增** SQLite 表
- ✅ **在 OpenHarness 之上扩展**（派生 StreamEvent + 注入回调）
- ✅ **AG-UI 是 SSE 协议**（不是新框架）

```
┌──── 客户端 ─────────────┐         ┌──── 服务端 ─────────────────┐
│ useAGUI() / AGUIProvider│         │ POST /api/ag-ui/run         │
│  ↓                      │  SSE    │   ↓                         │
│ CardRenderer            │◄────────┤ agui_handler                │
│ HITLPanel               │ AG-UI   │   ├─ ask_user_prompt        │
│ StatePanel              │ events  │   ├─ permission_prompt      │
│ QACopilotDemoPage       │         │   └─ _PendingInterrupts     │
│                         │         │   ↓                         │
│                         │         │ agui_transport.to_agui_events│
│                         │         │   ↓                         │
│                         │         │ OpenHarness v2 QueryEngine  │
│                         │         │  (原样，0 修改)              │
│                         │         │  ├─ ask_user_prompt cb      │
│                         │         │  ├─ permission_prompt cb    │
│                         │         │  └─ HookExecutor            │
└─────────────────────────┘         └─────────────────────────────┘
```

**v1 适配器（tool_adapter.py）** vs **v2 适配器（v2_adapter.py）**：
- v1：轻量 tool 适配，**无 agent loop**（不能用于 AG-UI）
- v2：BaseTool + QueryEngine + agent loop（**完整 runtime**）
- AG-UI 强制接 v2（v1 无 ask_user_prompt / permission_prompt 回调）
- 两者并存于 `odap/infra/openharness/__init__.py`，互不影响

---

## 2. 5 分钟跑通：Hello AG-UI

### 2.1 后端：发起一次 AG-UI run

```bash
# 1. 登录获取 Token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r .access_token)

# 2. 发起 run
curl -N -X POST http://localhost:8000/api/ag-ui/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "thread-1",
    "runId": "run-1",
    "workspaceId": "ws-1",
    "messages": [
      {"id": "m1", "role": "user", "content": "你好"}
    ]
  }'

# 响应（SSE 流）：
# data: {"type": "RUN_STARTED", "threadId": "thread-1", "runId": "run-1", ...}
# data: {"type": "MESSAGES_SNAPSHOT", "messages": [...]}
# data: {"type": "STATE_SNAPSHOT", "snapshot": {...}}
# data: {"type": "TEXT_MESSAGE_START", "messageId": "msg-xxx"}
# data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg-xxx", "delta": "..."}
# data: {"type": "TEXT_MESSAGE_END", "messageId": "msg-xxx"}
# data: {"type": "RUN_FINISHED", "outcome": "success", "result": {...}}
```

### 2.2 前端：使用 useAGUI Hook

```typescript
import { useAGUI, CardRenderer, HITLPanel, StatePanel } from '@/modules/qa';

function MyCopilot() {
  const {
    flatMessages,
    toolCalls,
    status,
    send,
    resume,
    pendingInterrupts,
  } = useAGUI({ workspaceId: 'ws-1' });

  return (
    <div>
      {flatMessages.map((m) => (
        <div key={m.id}>{m.role}: {m.content}</div>
      ))}
      <button onClick={() => send('查询本月销售')}>发送</button>
      <HITLPanel />  {/* 自动渲染 RunFinished.interrupts 卡片 */}
      <StatePanel watchPath="/memory/facts" />
    </div>
  );
}
```

或使用完整演示页：

```typescript
import { QACopilotDemoPage } from '@/modules/qa';

// 路由 /qa/copilot
<Route path="/qa/copilot" element={<QACopilotDemoPage workspaceId="ws-1" />} />
```

---

## 3. 关键文件位置

| 用途 | 后端 | 前端 |
|------|------|------|
| **协议模型** | `odap/infra/openharness/agui/agui_models.py` | `frontend/src/modules/qa/agui/agui_types.ts` |
| **派生 StreamEvent** | `odap/infra/openharness/agui/agui_extensions.py` | — |
| **字段映射** | `odap/infra/openharness/agui/agui_transport.py` | — |
| **FastAPI 端点 + 回调** | `odap/infra/openharness/agui/agui_handler.py` | — |
| **Provider（Context）** | — | `frontend/src/modules/qa/agui/AGUIProvider.tsx` |
| **Hook（独立）** | — | `frontend/src/modules/qa/agui/useAGUI.ts` |
| **Generative UI 注册** | — | `frontend/src/modules/qa/agui/CardRegistry.tsx` |
| **HITL 面板** | — | `frontend/src/modules/qa/agui/HITLPanel.tsx` |
| **Shared State 面板** | — | `frontend/src/modules/qa/agui/StatePanel.tsx` |
| **演示页** | — | `frontend/src/modules/qa/agui/QACopilotDemoPage.tsx` |
| **OPA 策略** | `odap/infra/opa/policies/ag_ui.rego` | — |
| **路由注册** | `odap/web/app.py:84, 190` | `frontend/src/modules/qa/index.ts` |

---

## 4. 30 分钟跑通：完整闭环

### 4.1 后端：跑测试

```bash
# 单元测试（3 套，99 个 case）
pytest tests/unit/test_agui_models.py -v        # 53 passed
pytest tests/unit/test_agui_transport.py -v     # 27 passed
pytest tests/unit/test_agui_handler.py -v       # 19 passed

# E2E 测试（8 个 case）
pytest tests/e2e/test_agui_full_flow.py -v      # 8 passed

# 全部 107 passed
```

### 4.2 架构不变量验证

```bash
# 0 修改 OpenHarness
git diff --stat openharness/    # 0 changed files

# 0 新建 biz/core/qa 模块
test ! -d odap/biz/core/qa && echo "PASS: no biz/core/qa"

# 0 新建 SQLite 表
# （v2_adapter.py / agui_handler.py 均不调用 _init_db 创建新表）

# 4 个后端文件 + 8 个前端文件
ls odap/infra/openharness/agui/        # 5 .py files
ls frontend/src/modules/qa/agui/        # 8 files
```

### 4.3 容器内启动

```bash
# 后端
python bootstep.py dev   # dev 模式
# 或
python bootstep.py up    # 生产模式
# 端点：http://localhost:8000/api/ag-ui/run

# 前端
# 自动 HMR；访问 http://localhost:5173/qa/copilot
```

---

## 5. HITL 完整流程

```
[用户] 客户端            [agui_handler]              [OpenHarness v2]
   │                          │                            │
   │ 1. POST /api/ag-ui/run   │                            │
   ├─────────────────────────►│                            │
   │                          │ 2. run_agent(query)        │
   │                          ├───────────────────────────►│
   │                          │                            │
   │                          │ 3. ask_user_question tool  │
   │                          │   (callback 触发)          │
   │                          │◄───────────────────────────┤
   │                          │                            │
   │ 4. SSE: TOOL_CALL_START  │                            │
   │◄─────────────────────────┤                            │
   │ 5. SSE: RunFinished      │                            │
   │    .interrupts[]         │                            │
   │    (含 reason, schema)   │                            │
   │◄─────────────────────────┤                            │
   │                          │                            │
   │ 6. UI 渲染 ConfirmCard   │                            │
   │    (HITLPanel)           │                            │
   │                          │                            │
   │ 7. POST /api/ag-ui/run   │                            │
   │    resume[] = {          │                            │
   │      interruptId: "int", │                            │
   │      response: {approved: true}                        │
   │    }                     │                            │
   ├─────────────────────────►│ 8. _pending.resolve()     │
   │                          │    → callback future 解除  │
   │                          │                            │
   │                          │ 9. 继续 run                │
   │                          ├───────────────────────────►│
   │                          │ 10. 返回 result            │
   │                          │◄───────────────────────────┤
   │ 11. SSE: TOOL_CALL_RESULT│                            │
   │◄─────────────────────────┤                            │
   │ 12. SSE: RUN_FINISHED    │                            │
   │◄─────────────────────────┤                            │
```

**关键点**：
- AG-UI 协议是**单 run 生命周期**（interrupt 不是"断点续传"，是"新 run resume"）
- 服务端保留 `asyncio.Future` 直到客户端发新 run 带 `resume[]`
- 同一 thread 跨多个 run 共享 `_pending` 字典

---

## 6. 危险工具拦截（permission_prompt）

类似 HITL，但 `interrupts[].reason = "tool_call"`、`toolCallId` 携带工具名：

```typescript
// HITLPanel 自动处理 reason=tool_call 的 interrupt
// 用户可批准 / 拒绝 / 编辑参数（responseSchema 提供 editedArgs 字段）
```

服务端回调（`agui_handler.py:_create_permission_callback`）：

```python
async def permission_callback(tool_name, tool_input) -> bool:
    interrupt_id = make_interrupt_id()
    future = asyncio.Future()
    _pending.add(thread_id, interrupt_id, future)

    # emit RunFinished.interrupts[reason="tool_call"]
    await transport_queue.put(RunFinishedEvent(
        outcome={"type": "interrupt", "interrupts": [{
            "id": interrupt_id,
            "reason": "tool_call",
            "toolCallId": tool_name,
            "responseSchema": {
                "type": "object",
                "properties": {
                    "approved": {"type": "boolean"},
                    "editedArgs": {"type": "object"},  # 可选
                },
                "required": ["approved"],
            },
        }]},
    ))

    response = await asyncio.wait_for(future, timeout=1800)
    return response.get("approved", False)
```

---

## 7. 常见问题

**Q: 为什么不用 @ag-ui/core SDK？**
A: 项目已用 `@openharness/react`（OpenHarness 官方 React SDK）。AG-UI 协议是 SSE/JSON 而非新框架 — 自写 80 行 EventSource 客户端就够，避免 5KB 冗余依赖。

**Q: 为什么不用 @copilotkit/*？**
A: CopilotKit 是商业 SDK（部分闭源），且绑定特定 React 状态管理。AG-UI 是开放协议（被 Google/LangChain/AWS 采用），可移植性更强。

**Q: v1_adapter 怎么办？**
A: 不动。v1 是轻量 tool 适配（无 agent loop），AG-UI 不需要。v2_adapter 提供完整 runtime（ask_user_prompt + permission_prompt）。两者并存于 `odap/infra/openharness/__init__.py`。

**Q: OpenHarness 升级怎么办？**
A: `_verify_no_modification()` 函数在 import 时校验 7 类原生事件完整。如果 OpenHarness 升级删了某类，会立即抛 ImportError。

**Q: 中文 SSE 编码？**
A: JSON 序列化 `ensure_ascii=False`（见 `encode_sse`），中文 + emoji 直接保留。

---

## 8. 相关文档

- [spec.md](file:///e:/DEMO/AI/ontology-graphiti/specs/002-copilotkit-eval/spec.md) — 评估 spec
- [research.md](file:///e:/DEMO/AI/ontology-graphiti/specs/002-copilotkit-eval/research.md) — 决策依据
- [plan.md](file:///e:/DEMO/AI/ontology-graphiti/specs/002-copilotkit-eval/plan.md) — v2.0 纯扩展架构
- [tasks.md](file:///e:/DEMO/AI/ontology-graphiti/specs/002-copilotkit-eval/tasks.md) — 53 个任务
- [contracts/ag-ui-bridge.md](file:///e:/DEMO/AI/ontology-graphiti/specs/002-copilotkit-eval/contracts/ag-ui-bridge.md) — 事件映射表
- [contracts/hitl-flow.md](file:///e:/DEMO/AI/ontology-graphiti/specs/002-copilotkit-eval/contracts/hitl-flow.md) — HITL 时序
- [contracts/generative-ui-card.md](file:///e:/DEMO/AI/ontology-graphiti/specs/002-copilotkit-eval/contracts/generative-ui-card.md) — 卡片契约
- [AG-UI 官方文档](https://docs.ag-ui.com) — 协议规范

---

**Version**: 2.0 (FINAL) | **Date**: 2026-06-08
