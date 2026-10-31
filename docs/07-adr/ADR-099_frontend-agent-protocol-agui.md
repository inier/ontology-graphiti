---
id: odap.l7.adr-099-frontend-agent-protocol-agui
status: active
owner: architect
version: ''
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-22'
citations: []
---

# ADR-099: 前端 Agent 集成协议收敛为 AG-UI（放弃 AI SDK Data Stream 路线）

## Status

**已接受（2026-10-22）**。前端 Agent 集成唯一协议为 **AG-UI**；移除 `@openharness/react` 与 `ai` 两个运行时依赖。

---

## Background

关联需求：模块化/组件化解耦、提升可组合性；**不得保留伪实现，也不得保留「文档声明了、代码没有」的能力描述**。

**现状（文件:行证据）**：

1. **依赖是在册的**：`apps/web/package.json:31` 声明 `"@openharness/react": "1.0.1"`；`:37` 声明 `"ai": "^6.0.97"`。
2. **实际引用为零**：`apps/web/src` 下对二者**零 import**。唯一的 import 点 `modules/qa/providers/QAIProvider.tsx` 已于 2026-10-21 随 QA v1 旧对话栈整批删除（6 文件 / 782 行，见 `docs/decisions/OPEN-DECISIONS.md`）。
3. **协议层不兼容**（这才是关键，不是「暂时没用到」）：
   - `@openharness/react@1.0.1` 的核心导出 `createOHTransport(endpoint)` 返回 `DefaultChatTransport`，类型声明原文：*"parses the AI SDK 5 data stream protocol"*（`node_modules/@openharness/react/dist/transport.d.ts`）。
   - 同一包的 `useOpenHarness` / `useSubagentStatus` / `useSessionStatus` / `useSandboxStatus`（`dist/index.d.ts`）全部建立在该 transport 之上。
   - 后端**不实现** AI SDK data stream 协议：`apps/api/odap` 对 `data stream` / `ai_sdk` / `x-vercel` 全量**零命中**。实际实现是 AG-UI，落在 `apps/api/odap/infra/openharness/agui/`（`agui_handler.py`、`agui_transport.py`、`agui_models.py`、`agui_extensions.py`）。
4. **决策层早已定调**：ADR-070 明文「所有降级路径输出相同的 **AG-UI 事件格式**，前端无需感知降级」（`ADR-070:273`）、「AG-UI 协议覆盖所有场景 → 前端只需一套解析器」（`ADR-070:287`）。装载 second 解析器与该结论直接冲突。
5. **文档侧仍在按旧路线描述**：
   - `docs/02-architecture/ARCHITECTURE-v2.md:410` 列「AI SDK | `ai` | `^6.0.97`」、`:411` 列「Agent 前端 | `@openharness/react` | `1.0.1`」为在役技术栈；
   - `docs/03-modules/qa_engine/INTEGRATION.md` 整篇以「`@openharness/react` 库集成」为主题；
   - `docs/07-adr/ADR-039_qa_engine_architecture.md:216` 给出 `OpenHarnessProvider` 集成片段；
   - `docs/01-product-design/webui-enhancement-design.md:37` 标注「AI 集成 | Vercel AI SDK + @openharness/react | ✅ 集成良好」。
6. **现行实现（ADR-070 合规）**：
   - `apps/web/src/modules/qa/agui/AGUIProvider.tsx` — 自研 AG-UI 客户端，具备 heartbeat / autoReconnect / maxRetries / namespace / `AGUIErrorBoundary`；
   - `apps/web/src/modules/ai-assistant/hooks/useAIChat.ts` — `apiClient.stream('/api/assistant/chat')`，解析 AG-UI 事件 `RUN_STARTED` / `TEXT_MESSAGE_START|CONTENT|END` / `TOOL_CALL_START|ARGS|END|RESULT` / `CUSTOM` / `RUN_FINISHED` / `ERROR`。

**问题定性**：这不是「依赖暂时闲置」，而是**架构声明与实现漂移**。留着依赖会让人误以为 SDK 可用；删掉依赖却不改文档，则文档继续误导。两者必须同时收敛。

---

## Decision

1. **前端 Agent 集成唯一协议 = AG-UI**。不引入 AI SDK 5 data stream 协议的第二套解析器，与 ADR-070 保持一致。
2. **移除依赖**：从 `apps/web/package.json` 删除 `@openharness/react` 与 `ai`；随之传递移除 `@openharness/core`、`@ai-sdk/react`（peer）及 `zod` 的该条依赖链。同步重生成 `pnpm-lock.yaml`。
3. **文档对齐**：
   - `ARCHITECTURE-v2.md` 技术栈表删除上述两行，并在表下注明「Agent 前端集成走 AG-UI，见 ADR-099」；
   - `docs/03-modules/qa_engine/INTEGRATION.md` 改写为 AG-UI 集成说明，AI SDK 路线降级为「历史方案（已废弃）」段落保留，不删除历史；
   - `ADR-039` 的 Provider 片段加注指向本 ADR（ADR-039 为 `lifecycle: frozen` 的冻结记录，不改其决策正文）；
   - `webui-enhancement-design.md:37` 的「✅ 集成良好」改为如实描述。
4. **复引入条件**（唯一合法路径）：仅当①后端新增 AI SDK 5 data stream 端点，且②ADR-070「前端只需一套解析器」被显式修订为允许双协议时，方可重新评估。**不得以「框架自带能力」「未来可能用到」为由单方面加回依赖。**

---

## Consequences

**正面**：

- 依赖面收窄：移除 3 个直接/传递包（`@openharness/react`、`ai`、`@ai-sdk/react`）及其 `@openharness/core` 链路，安装体积与供应链面同步下降。
- 文档与代码一致，消除「架构声明了但代码没有」的误导，也消除后续维护者在两条路线间选错实现的风险。
- 与 ADR-070、ADR-091（图谱渲染栈 7→3）、ADR-098（frontend_compat 收敛）执行同一治理口径：**每个能力只保留一套真实实现**。

**负面**：

- 放弃 SDK 提供的 `useSessionStatus` / `useSubagentStatus` / `useSandboxStatus` 三个状态 hook。若未来需要这些视图，须自行实现或先走「复引入条件」修订协议。
- 沙箱状态展示目前由 `modules/simulation/stores/simulationStore.ts` 自研承担，与 SDK 的 `useSandboxStatus` 无复用关系 —— 本 ADR 确认这一现状为正式方案，而非临时状态。
- 若后端将来迁移到 AI SDK 生态（如接入 Vercel AI Gateway 原生流），需重新评估。

---

## Related ADRs

- ADR-070（基于 OpenHarness 全能力的 AI 助手架构）— AG-UI 为唯一前端协议，本 ADR 是其落地收敛
- ADR-039（问答引擎架构）— 其中 OpenHarness Provider 集成片段已由本 ADR 取代，正文保留作历史
- ADR-091（graph-render-stack-consolidation）— 同类「第三套实现」清理先例
- ADR-098（frontend-compat-convergence）— 同属「文档声明 vs 实现」收敛治理
- ADR-025（openharness_integration）— 复用策略总纲
