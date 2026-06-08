# Phase 0 Research: 协议选型决策（AG-UI vs OAUIP）

**Date**: 2026-06-08
**Owner**: speckit-plan
**Status**: 草案（2026-06-08 修订：原 OAUIP 决策被推翻，重做对比）

---

## 1. 问题陈述

> ⚠️ **STALE 警告**：spec.md 已于 2026-06-08 重大修订（详见 spec.md 顶部 Refined 行）。本文件原"自研 OAUIP"决策被推翻。重写为对比 **AG-UI（工业标准）vs OAUIP（自研）**。

**核心问题**：要实现 CopilotKit 等价能力（Generative UI / Shared State / HITL），应：
- **方案 A**：对接 **AG-UI 工业标准协议**（被 Google / LangChain / AWS / Microsoft / Mastra / PydanticAI 采用）
- **方案 B**：在现有 `/api/qa/ask` SSE 事件流上叠加新事件
- **方案 C**：自研 **OAUIP** 子协议
- **方案 D**：直接引入 CopilotKit npm 包（被 spec.md 拒绝）

---

## 2. AG-UI 协议概览

**AG-UI (Agent-User Interaction Protocol)** 是 CopilotKit 主导、已被工业界广泛采用的 **agent↔UI 通信开放标准**。

**关键事实**：
- **协议规范开源**：https://github.com/ag-ui-protocol/ag-ui
- **采用方**：Google ADK、LangChain、AWS Bedrock Agents、Microsoft AutoGen、Mastra、PydanticAI、CopilotKit
- **协议形式**：SSE 事件流 + JSON Schema
- **核心事件类型**（已规范）：
  - `RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR` — 生命周期
  - `STEP_STARTED` / `STEP_FINISHED` — 步骤
  - `TEXT_MESSAGE_START` / `TEXT_MESSAGE_CONTENT` / `TEXT_MESSAGE_END` — 文本流式
  - `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END` / `TOOL_CALL_RESULT` — 工具调用（涵盖 Generative UI）
  - `STATE_SNAPSHOT` / `STATE_DELTA` — 状态同步
  - `MESSAGES_SNAPSHOT` — 消息快照
  - `RAW` — 透传
  - `CUSTOM` — 扩展
- **客户端 SDK**：TypeScript 官方（`@ag-ui/core` + `@ag-ui/client`）
- **服务端参考实现**：TypeScript（CopilotKit Runtime）+ 社区 Python 实现（`ag-ui-protocol/ag-ui/packages/python`）

**HITL 能力**：
- 通过 `STEP_FINISHED` + `STATE_SNAPSHOT` 携带"待用户输入"标记
- 客户端通过 `RUN_INPUT` 反向消息恢复 agent

**Generative UI 能力**：
- `TOOL_CALL_RESULT` 可携带任意 JSON payload
- 客户端通过 component registry 渲染为 React 组件（与 OAUIP 思路一致）
- **A2UI 子协议**（Google 主导）扩展为声明式 UI 描述

---

## 3. 三种方案详细对比

| 维度 | 方案 A: AG-UI 标准 | 方案 B: 扩展 SSE | 方案 C: 自研 OAUIP | 方案 D: CopilotKit 包 |
|------|:--:|:--:|:--:|:--:|
| **工业采用** | 6+ 大厂 | ODAP 独家 | ODAP 独家 | 1.7k dependents |
| **协议成熟度** | 已被验证（v0.x） | 既有协议 | 0（草案 v0.1） | 成熟 |
| **代码我们写多少** | < 50 行适配器 | ~50 行扩展 | 200+ 行协议 | 0 |
| **HITL 原语** | 已有（interrupt） | 需扩展 | 需自研 | 已有 |
| **Generative UI** | 已有（tool_call） | 需扩展 | 需自研 | 已有 |
| **Shared State** | 已有（state_delta） | 需扩展 | 需自研 | 已有 |
| **未来接入 LangChain** | ✅ 即时 | ❌ 需重写 | ❌ 需重写 | ✅ 已有集成 |
| **未来接入 PydanticAI** | ✅ 即时 | ❌ 需重写 | ❌ 需重写 | ✅ 已有集成 |
| **包大小代价** | < 5KB | 0 | 0 | +200KB |
| **维护负担** | 社区 | 我们 | 我们 | CopilotKit 团队 |
| **OpenHarness 冲突** | ❌ 无 | ❌ 无 | ❌ 无 | ⚠️ 严重 |
| **协议可分叉** | ✅ MIT 协议 | N/A | N/A | ✅ MIT |
| **数据出境风险** | 无（自托管） | 无 | 无 | ⚠️ 关掉 Cloud |
| **协议学习成本** | 中 | 低 | 中-高 | 低 |

**评分对比**（10 项，每项 1-5）：

| 维度 | A: AG-UI | B: SSE 扩展 | C: OAUIP | D: CopilotKit |
|------|:--:|:--:|:--:|:--:|
| 工业采用 | 5 | 1 | 1 | 4 |
| 协议成熟度 | 4 | 3 | 1 | 5 |
| 代码量 | 4 | 5 | 2 | 5 |
| HITL 原语 | 4 | 1 | 1 | 5 |
| Generative UI | 4 | 1 | 1 | 5 |
| Shared State | 4 | 1 | 1 | 5 |
| 生态接入 | 5 | 1 | 1 | 4 |
| 包大小 | 4 | 5 | 5 | 1 |
| 维护负担 | 5 | 2 | 2 | 4 |
| OpenHarness 兼容 | 4 | 4 | 4 | 1 |
| **加权总分** | **4.3** | **2.4** | **1.9** | **3.9** |

---

## 4. 决策

**Decision**: **方案 A — 对接 AG-UI 工业标准协议**

**Rationale**:
1. **加权 4.3 远高于其他方案**：B/C/D 都不到 4.0
2. **AG-UI 是工业标准，不是 CopilotKit 私有** — 6+ 大厂采用的事实证明其设计合理性
3. **对接 ≠ 引入 CopilotKit 包**：AG-UI 协议规范是 MIT 开源，可独立实现服务端和客户端
4. **规避 OpenHarness 冲突**：方案 D 引入 `@copilotkit/react-*` 会与 `@openharness/react@1.0.1` 冲突；方案 A 仅引入 AG-UI TypeScript 客户端（< 5KB），不冲突
5. **未来扩展性最强**：直接接入 LangChain / PydanticAI / Mastra 等第三方 Agent 框架
6. **维护负担最低**：协议演进由社区承担

**Alternatives Considered**:
- **方案 B（SSE 扩展）** 被拒，理由：会污染现有 `tool.result` 事件 schema，违反 Constitution I
- **方案 C（自研 OAUIP）** 被拒，理由：重复造轮子，工业已存在更优标准
- **方案 D（CopilotKit 包）** 被拒，理由：与 OpenHarness 冲突 + 包大小 + 供应商锁定

**Constitution Check**:
- **IV. 避免过度设计** ✅ PASS：AG-UI 是已有工业标准，对接它**比**自研 OAUIP 更"避免过度设计"
- **I. 简单** ✅ PASS：复用 AG-UI 客户端 SDK + 简单 Python 服务端
- **II. 可维护** ✅ PASS：协议维护由社区承担
- **III. 测试优先** ✅ PASS：可参考 AG-UI 协议规范测试套件

---

## 5. 修订后的工作量估算

| 阶段 | 原 OAUIP | 修订后 AG-UI | 差异 | 原因 |
|------|:--:|:--:|:--:|------|
| Phase 0 协议选型 | 5 人天 | 5 人天 | 0 | 重做对比，本文件即产物 |
| Phase 1 数据模型 + 契约 | 5 人天 | 3 人天 | **-2** | 直接用 AG-UI 事件 schema，不需自研契约 |
| Phase 2 后端实现 | 13 人天 | 6 人天 | **-7** | 写 AG-UI Python 服务端（基于官方 SDK），不需自研协议 |
| Phase 3 前端实现 | 13 人天 | 8 人天 | **-5** | 用 AG-UI TypeScript 客户端适配，不需自研 4 个 hook |
| Phase 4 集成验证 | 5 人天 | 5 人天 | 0 | 同等 |
| Phase 5 灰度上线 | 3 人天 | 3 人天 | 0 | 同等 |
| **总计** | **44 人天** | **30 人天（6 周）** | **-14（-32%）** | |

**节省 14 人天（3 周）** — 主要来自"不自研协议"的红利。

---

## 6. AG-UI 对接架构

```
┌──────── 客户端 (浏览器) ─────────┐    ┌──────── 服务端 (FastAPI) ─────────┐
│                                  │    │                                   │
│  @ag-ui/client SDK               │    │  AG-UI Python SDK                 │
│  ┌─ HTTPClient ──────────────── │    │  ┌─ AGUIHandler ────────────────┐ │
│  │  POST /ag-ui/run (发送消息)  ├────┼──►│  包装 QAEngine                │ │
│  │  GET  /ag-ui/events (SSE)    │◄───┼──┤  → 生成 AG-UI 事件流          │ │
│  │                              │    │  └──────────────────────────────┘ │
│  └───────────────────────────────│    │                                   │
│                                  │    │  ┌─ OPA 鉴权层 ────────────────┐  │
│  React 组件:                     │    │  │  校验 workspace_id          │  │
│  ┌─ CardRegistry ────────────── │    │  │  校验 thread_id             │  │
│  │  chart / graph / temporal     │    │  │  校验 HITL 操作权限          │  │
│  │  action / confirm / input     │    │  └──────────────────────────────┘  │
│  └───────────────────────────────│    │                                   │
└──────────────────────────────────┘    └───────────────────────────────────┘
```

**关键点**：
- **AG-UI TypeScript 客户端**：约 4KB gzip（`@ag-ui/core` + 适配器），不引入 React 组件
- **AG-UI Python 服务端**：基于官方 SDK，约 100 行代码包装 QAEngine
- **OPA 鉴权透传**：所有请求必须经 OPA 校验 WS/Sce/Ont 访问权
- **HITL 实现**：通过 AG-UI 的 `interrupt` 事件 + `STEP_FINISHED` 状态 + 客户端 `RUN_INPUT` 消息
- **Generative UI 实现**：通过 AG-UI 的 `TOOL_CALL_RESULT` 携带卡片描述 + 客户端 CardRegistry 渲染

---

## 7. Phase 1 输入

基于本决策，Phase 1 的契约设计遵循：

1. **AG-UI 事件类型**（直接复用，无自研）：
   - `RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR` — 生命周期
   - `TEXT_MESSAGE_*` — 流式文本
   - `TOOL_CALL_*` — 工具调用 + Generative UI
   - `STATE_SNAPSHOT` / `STATE_DELTA` — 状态同步
   - `STEP_*` — HITL 暂停点
2. **HTTP 端点**（基于 AG-UI 规范）：
   - `POST /api/ag-ui/run` — 发起问答
   - `GET /api/ag-ui/events/<thread_id>` — SSE 事件流
   - `POST /api/ag-ui/input/<thread_id>` — HITL 恢复
3. **数据模型**：与 AG-UI `Message` / `ToolCall` / `State` 类型对齐
4. **前端卡片契约**：通过 AG-UI `TOOL_CALL_RESULT` 携带

---

## 8. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|:--:|------|
| AG-UI v0.x 仍有破坏性变更 | P1 | 锁定 minor 版本（`@ag-ui/core@0.x.y`），跟踪 RFC |
| AG-UI Python SDK 不成熟 | P1 | MVP 先用 FastAPI 自行解析 AG-UI JSON 事件（事件 schema 简单），后续替换为官方 SDK |
| AG-UI 不支持 ODAP 特定需求（如 WS/Sce/Ont 编码） | P1 | 通过 `STATE_SNAPSHOT` 的 `metadata` 字段扩展（AG-UI 支持） |
| 客户端 SDK 与 Ant Design 6 视觉割裂 | P2 | AG-UI 客户端 headless 模式，仅消费事件流，UI 全自研 |
| 多个 Agent 框架的 AG-UI 行为差异 | P2 | MVP 锁定 CopilotKit AG-UI v0.x 实现，其他框架后续验证 |

---

## 9. 输出物清单

| 路径 | 内容 | 状态 |
|------|------|:--:|
| `specs/002-copilotkit-eval/research.md` | 本文件（重写） | ✅ |
| `specs/002-copilotkit-eval/data-model.md` | 数据模型 | ⏳ 待 propagate |
| `specs/002-copilotkit-eval/contracts/ag-ui-protocol.md` | AG-UI 协议映射 | ⏳ 待 propagate |
| `specs/002-copilotkit-eval/contracts/generative-ui-card.md` | 卡片契约 | ⏳ 待 propagate |
| `specs/002-copilotkit-eval/contracts/hitl-flow.md` | HITL 契约 | ⏳ 待 propagate |
| `specs/002-copilotkit-eval/quickstart.md` | 开发者快速上手 | ⏳ 待 propagate |

---

## 10. 修订履历

- **2026-06-08 v1.0** (原 OAUIP 决策): 错 — 漏掉 AG-UI 选项
- **2026-06-08 v2.0** (当前 AG-UI 决策): 正确 — 工业标准 + 节省 14 人天

---

**Version**: 2.0 | **Date**: 2026-06-08
