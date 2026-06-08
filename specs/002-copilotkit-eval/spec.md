# Feature Specification: CopilotKit 前端智能问答集成评估

**Feature Branch**: `002-copilotkit-eval`

**Created**: 2026-06-08
**Refined**: 2026-06-08 — **重大决策反转**：从"自研 OAUIP"修订为"对接 AG-UI 工业标准协议"。原 [research.md](file:///e:/DEMO/AI/ontology-graphiti/specs/002-copilotkit-eval/research.md) 漏掉 AG-UI 选项，已在对比中完败。本次修订同步影响 plan.md / data-model.md / contracts/\* / quickstart.md，请运行 `/speckit.refine.propagate` 同步下游。

**Status**: Refined

**Input**: User description: "评估智能问答的前端结合此 git 项目的可行性和合理性 (<https://github.com/CopilotKit/CopilotKit>)"

***

## 背景与上下文 (Context)

ODAP（本体驱动分析决策平台）已经存在完整的智能问答后端实现（QA Engine, M-12 模块）和前端聊天页面 (`/qa`)，并已经集成了 OpenHarness（`@openharness/react@1.0.1`）作为智能体编排框架。架构组在 [ADR-052](../../docs/07-adr/ADR-052_webui_opensource_selection.md) 中已经对 LobeChat / Open WebUI / LibreChat / Dify 四个开源 Chat UI 项目做过评估，最终选择"自研为主 + Ant Design X 组件 + LobeChat 插件系统参考"。

本次评估的目标是 **第三方 SDK（CopilotKit）的可行性论证**，与 ADR-052 的"Fork 完整 Chat UI"路径不同。CopilotKit 定位是 **agentic SDK**（提供 Chat/Generative UI/Shared State/HITL 能力的基础设施），而非成品 Chat UI 模板，因此需要与现有技术栈做不同的对比。

***

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 架构师快速判断集成价值 (Priority: P1)

架构师/技术负责人希望基于事实而非直觉，判断"是否值得把 CopilotKit 集成到 ODAP 前端"。需要在 1 份评估文档中看到：

- 能力映射（CopilotKit 的哪些特性对应 ODAP 的哪些需求）
- 技术栈兼容性分析（React 19 / Ant Design 6 / OpenHarness / Zustand）
- 与已有决策（ADR-052、@openharness/react）的冲突与互补关系
- 工作量估算（若采用，需多少前端改造）
- 风险与回退成本

**Why this priority**: 这是本次评估的根本目的；没有此结论，后续动作无法启动。

**Independent Test**: 阅读 `specs/002-copilotkit-eval/spec.md` + 配套决策矩阵，能独立得出"采纳 / 部分采纳 / 拒绝"的结论。

**Acceptance Scenarios**:

1. **Given** 架构师阅读评估文档, **When** 查看"决策矩阵"小节, **Then** 能看到 CopilotKit 在"技术栈兼容 / 智能体编排 / 共享状态 / 流式输出 / 知识库 / 工作空间 / 学习成本"等维度的量化评分
2. **Given** 架构师已读过 ADR-052, **When** 翻到"与已有决策的兼容性"小节, **Then** 能清楚看到 CopilotKit 与 OpenHarness / Ant Design X 的关系（替代/共存/冲突）
3. **Given** 团队计划下周开始 QA 前端改造, **When** 评估建议为"拒绝", **Then** 文档给出明确的"不集成"理由清单（避免后续再被反复询问）

***

### User Story 2 - 前端开发人员识别"如果集成需要改什么" (Priority: P2)

前端开发人员想知道"如果决定集成 CopilotKit，要修改哪些文件 / 引入哪些依赖 / 是否破坏现有结构"。评估需要包含一份"集成剖面图"，列明：

- 涉及的前端模块（`frontend/src/modules/qa/`, `frontend/src/modules/agent/`, `frontend/src/modules/workspace/`）
- 与现有 Hook/Provider 的关系（`QAIProvider`, `useQAI`, `useSession`, `useChatStorage`）
- 包大小影响、构建影响、运行时影响

**Why this priority**: 帮助做出"工作量可控"判断；但次于决策本身。

**Independent Test**: 给定一份集成剖面图，前端能基于此在沙箱中产出 1 个最小 POC（Hello-world 级别的 CopilotKit Provider + ODAP 现有 QAPanel 共存示例）。

**Acceptance Scenarios**:

1. **Given** 前端查看"集成剖面图"小节, **When** 关注 `frontend/src/modules/qa/`, **Then** 能看到 QAChatPage / QAIProvider / qaStore 的改造点
2. **Given** 前端想评估包大小影响, **When** 查看"成本评估"小节, **Then** 能看到 CopilotKit 核心包 + 运行时的估算
3. **Given** 评估建议"渐进式集成", **When** 前端按文档步骤操作, **Then** 能在不破坏现有 `/qa` 页面的前提下，新增 1 个 `/qa/copilot` 演示页面

***

### User Story 3 - 产品经理理解"用户能感知到的新能力" (Priority: P3)

产品经理想知道：集成 CopilotKit 后，**ODAP 用户能多获得哪些以前没有的能力**（如 HITL 审批流、Generative UI、跨 Slack 推送等），以及这些能力是否真的能落地到 ODAP 的业务场景（本体/图谱/决策推演）。

**Why this priority**: 偏决策影响判断，但与架构决策的最终拍板间接相关。

**Independent Test**: 阅读"用户可感知能力映射"小节，能列出至少 3 个 CopilotKit 带来的新能力点 × ODAP 业务场景的对应关系。

**Acceptance Scenarios**:

1. **Given** 产品经理阅读"能力映射"小节, **When** 查看 Generative UI 对应, **Then** 能看到"基于本体的查询结果以动态图谱卡片呈现"这类具体场景
2. **Given** 产品经理关注跨平台能力, **When** 查看 Slack/Teams 集成, **Then** 能明确判断"ODAP 是否短期内需要"，避免被"未来潜力"误导

***

### Edge Cases

- **冲突场景**：CopilotKit 自带 Chat 组件 / Provider 与现有 QAIProvider + Ant Design X 同时使用，DOM 嵌套 / 状态订阅冲突如何处理
- **降级场景**：CopilotKit Cloud 不可用时（私有化部署），自托管 AG-UI Runtime 的最低可行配置
- **共存场景**：OpenHarness 已经在做 agent 编排，CopilotKit 也做 agent 编排，是否会出现"两个调度器打架"
- **数据出境场景**：CopilotKit 的 Self-Learning / Threads 持久化是否会把对话送出企业网络
- **国密/合规场景**：ODAP 多用于政企 / 军事 / 金融领域，MIT 协议 + 美国主导项目的合规审查可行性

***

## Requirements *(mandatory)*

### Functional Requirements

> 注：本评估的"功能需求"是**对评估产物本身**的需求（即评估文档必须包含什么），而非"被评估的 CopilotKit 必须支持什么"。

- **FR-001**: 评估必须输出 **能力映射矩阵**，覆盖 CopilotKit 六大特性（Chat UI / Generative UI / Shared State / Human-in-the-Loop / Backend Tool Rendering / Self-Learning），对应 ODAP 现有/规划中的需求点
- **FR-002**: 评估必须输出 **技术栈兼容性矩阵**，与现有依赖（`react@19.2.4`、`antd@^6.3.5`、`@openharness/react@1.0.1`、`zustand@^5.0.12`、`@antv/g6@^5.1.0`）逐项对照
- **FR-003**: 评估必须输出 **与 ADR-052 + 现有 @openharness/react 集成的关系图**，明确"替代 / 互补 / 冲突"中的哪种
- **FR-004**: 评估必须输出 **量化评分**（每项 1-5 星 + 文字理由），最终给出"采纳 / 部分采纳 / 拒绝"三档结论
- **FR-005**: 评估必须列出 **至少 5 个具体场景的 CopilotKit 应用示例**（覆盖本体问答 / 模拟推演 / 审计 / 角色 / 工作空间场景），用以判断"是否真的能解决 ODAP 的痛点"
- **FR-006**: 评估必须包含 **风险清单**（合规 / 数据出境 / 包大小 / 维护活跃度 / 供应商锁定 / 私有化部署可行性 / 升级成本）
- **FR-007**: 评估必须给出 **渐进式集成路径**（即使最终建议拒绝，也要说明"何种条件下可重新评估"）和 **回退方案**（如果集成后发现不合适，如何干净撤掉）
- **FR-008**: 评估必须基于 **CopilotKit 实际仓库信息**（截至评估日：`main` 分支 10,825 commits、1,371 releases、Latest v1.59.5、MIT License、SDK 含 Python 0.1.94、AG-UI 协议已被 Google/LangChain/AWS/Microsoft/Mastra/PydanticAI 采用），不允许凭印象评估

### Non-Functional Requirements

- **NFR-001**: 评估文档长度 ≤ 600 行 Markdown，确保 1 次阅读可读完
- **NFR-002**: 评估文档必须与本仓库现有文档体系一致（`docs/03-modules/...`、`docs/07-adr/...`），使用相同的中文术语
- **NFR-003**: 评估结论必须可在 30 秒内向非技术 stakeholder 口头说明（"做什么的 / 用不用 / 为什么"）

### Key Entities *(include if feature involves data)*

- **CopilotKit Feature Set**: 6 大特性 + Python SDK + AG-UI 协议 + 多前端支持（React/Angular/Vue/React Native）
- **ODAP Current Frontend Stack**: `frontend/src/modules/{qa,agent,workspace,simulation,audit,...}/`
- **ODAP QA Engine**: `odap/biz/core/.../qa/` + `docs/03-modules/qa_engine/DESIGN.md`
- **OpenHarness Integration**: `@openharness/react@1.0.1` + `odap/biz/integration/openharness_agent/`
- **ADR-052 Decision**: 自研 + Ant Design X + LobeChat 插件系统参考

***

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 架构师在 1 次会议（≤ 60 分钟）内，基于本评估文档 + 决策矩阵达成"采纳 / 部分采纳 / 拒绝"的明确决议
- **SC-002**: 评估文档至少覆盖 5 个 CopilotKit 核心能力 × ODAP 业务场景的具体映射（不接受空泛的"可以用"）
- **SC-003**: 评估文档对"CopilotKit 与 @openharness/react 共存可能性"给出可证伪的判断（不能只是"应该可以"）
- **SC-004**: 评估文档明确给出"私有化部署 / 数据不出域"的具体方案（CopilotKit Cloud vs Self-hosted Runtime 的取舍）
- **SC-005**: 评估文档产出后，1 个月内不需要因外部信息变更（如 CopilotKit 重大 release）而推翻结论（基线日期：2026-06-08，对应 v1.59.5）

***

## 评估方法论 (Methodology)

### 评分维度（与 ADR-052 对齐）

| #  | 维度                  |  权重 | 评分基准                                                     |
| -- | ------------------- | :-: | -------------------------------------------------------- |
| 1  | 技术栈兼容               | 25% | 是否与 React 19 / Ant Design 6 / Zustand 5 / OpenHarness 兼容 |
| 2  | 智能体编排               | 20% | 是否能替代或增强现有 OpenHarness 编排                                |
| 3  | 流式输出 / Chat UI      | 15% | 是否优于当前自研 + Ant Design X 方案                               |
| 4  | Generative UI 能力    | 10% | 是否能解决"答案+图谱卡片"等动态渲染                                      |
| 5  | Shared State / HITL | 10% | 是否能为审批流 / 协作场景带来提升                                       |
| 6  | 知识图谱 / RAG 集成       |  5% | 与 Graphiti / QA Engine 集成的复杂度                            |
| 7  | 工作空间 / 多租户          |  5% | 是否能识别并支持 ODAP 的 WS/Sce/Ont 三层隔离                          |
| 8  | 私有化 / 合规            |  5% | MIT 协议 + 自托管可行性 + 数据出境                                   |
| 9  | 社区活跃度               |  3% | 1.7k dependents, 1.4k+ releases, 10.8k commits           |
| 10 | 学习成本                |  2% | 团队上手所需时间                                                 |

### 结论分档

- **采纳 (Adopt)**: 加权得分 ≥ 4.0 且无 P0 级风险
- **部分采纳 (Partial)**: 2.5 ≤ 加权得分 < 4.0 或存在 P1 级风险但可缓解
- **拒绝 (Reject)**: 加权得分 < 2.5 或存在 P0 级无法缓解的风险

***

## CopilotKit 能力与 ODAP 需求映射 (Capability Mapping)

### 1. Chat UI（聊天界面）

| CopilotKit 能力                           | ODAP 对应需求                                                   | 评估                                                                                   |
| --------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `<CopilotChat>` / `<CopilotPopup>` 即用组件 | `frontend/src/modules/qa/components/` + Ant Design X Bubble | ⚠️ **重叠且落后** — ODAP 已经基于 Ant Design X 自研三栏布局（ADR-052 决策），CopilotKit 的双栏/弹窗布局反而需要回退样式 |
| 自定义 Chat UI（headless hooks）             | 现有 `QAIProvider` + `useQAI`                                 | ✅ **可能互补** — CopilotKit 提供 headless 模式，可接管 hook 层                                    |

### 2. Generative UI（动态生成 UI）

| CopilotKit 能力            | ODAP 对应需求                                                | 评估                                                                               |
| ------------------------ | -------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Backend Tool 返回 React 组件 | 现有 `InlineChart` / `ReportLinkView` / `TemporalCardView` | ✅ **强匹配** — ODAP 已有自定义渲染器，CopilotKit 的 Generative UI 协议可统一"Agent 输出一段 JSX/卡片"的流程 |
| A2UI 协议（Declarative UI）  | 无                                                        | 🆕 **新能力** — 可让 LLM 输出结构化 UI 描述                                                  |
| AG-UI 协议（Open-ended）     | 现有 QA Engine 自定义                                         | ✅ **可能** — AG-UI 是开源协议，可让 ODAP 接入 LangChain / PydanticAI / Mastra 等第三方 Agent     |

### 3. Shared State（共享状态）

| CopilotKit 能力           | ODAP 对应需求                      | 评估                                                                                                         |
| ----------------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| Agent ↔ UI 双向绑定         | `useQAI` / `qaStore` (Zustand) | ⚠️ **冲突** — CopilotKit 假设 agent backend 配合其状态协议；ODAP 的 QA Engine 后端是 Graphiti + LLM 直接调用，未实现 AG-UI，需要额外适配层 |
| `useAgent({ agentId })` | 无                              | 🆕 **新能力** — 让前端能订阅远端 agent 状态                                                                             |

### 4. Human-in-the-Loop（人机协作）

| CopilotKit 能力  | ODAP 对应需求        | 评估                                                                          |
| -------------- | ---------------- | --------------------------------------------------------------------------- |
| Agent 暂停请求用户确认 | 无                | 🆕 **新能力** — ODAP 决策推演（Simulation）场景天然需要"Agent 给出建议 → 用户确认 → 执行"，HITL 是核心需求 |
| 表单/审批嵌入        | 现有 OPA 策略 + 角色系统 | 🆕 **可结合** — 决策审批流                                                          |

### 5. Backend Tool Rendering

| CopilotKit 能力             | ODAP 对应需求                      | 评估                                                                                    |
| ------------------------- | ------------------------------ | ------------------------------------------------------------------------------------- |
| Agent 调工具 → 工具返回 React 组件 | 现有 `ToolRegistry` + `Skill` 系统 | ⚠️ **重叠** — ODAP 已有 Skills 体系（`odap/tools/`），需要看 CopilotKit 的工具协议能否映射到现有 Skill schema |
| 前端 `useFrontendTool`      | 现有自定义渲染组件                      | 🆕 **新能力** — 区分前端/后端工具                                                                |

### 6. Self-Learning（自学习 Agent）

| CopilotKit 能力 | ODAP 对应需求                                 | 评估                                                                                 |
| ------------- | ----------------------------------------- | ---------------------------------------------------------------------------------- |
| CLHF 持续学习     | 无（项目当前无自学习需求）                             | ❌ **不必要** — 且 Self-Learning 需要 CopilotKit Cloud 或 Enterprise Platform，**不满足私有化部署** |
| Threads 持久化   | 现有 `qa_sessions` / `qa_messages` SQLite 表 | ⚠️ **重叠** — 但 CopilotKit 的协议更现代（事件流）                                               |

### 7. 多平台 (React Native / Slack / Teams)

| CopilotKit 能力       | ODAP 对应需求       | 评估                                        |
| ------------------- | --------------- | ----------------------------------------- |
| React Native        | 无（ODAP 当前纯 Web） | ❌ **不必要** — 移动端不在当前 Roadmap               |
| Slack / Teams Agent | 无               | ❌ **不必要** — ODAP 用户群体为内部业务分析师，不在 Slack 工作 |

***

## 技术栈兼容性分析 (Tech Stack Compatibility)

| 维度            | CopilotKit 要求                  | ODAP 现状                               | 兼容性 | 备注                                                                         |
| ------------- | ------------------------------ | ------------------------------------- | :-: | -------------------------------------------------------------------------- |
| React 版本      | React 18+ / Next.js（GA）        | React 19.2.4                          |  ✅  | 官方未声明 React 19，但 React 18 兼容代码通常可上 19，需实测                                  |
| TypeScript    | 5+                             | TypeScript \~6.0.2                    |  ✅  | 兼容                                                                         |
| UI 组件库        | 无硬性要求                          | Ant Design 6.3.5                      |  ✅  | CopilotKit 头less 模式不绑定 UI 库                                                |
| 状态管理          | 自带 context（基于 React Context）   | Zustand 5                             |  ⚠️ | CopilotKit 的 `useAgent` hook 返回状态；与 Zustand 共存需要在 Provider 边界处做桥接          |
| Agent Runtime | AG-UI 协议                       | OpenHarness v1/v2 + 自研 FastAPI        |  ❌  | **关键冲突**：ODAP 后端未实现 AG-UI 协议；集成需要写 Adapter，把现有 `/api/qa/ask` 翻译为 AG-UI 事件流 |
| LLM Provider  | OpenAI / Anthropic / LangChain | `odap/infra/llm/llm_service.py`（自研抽象） |  ⚠️ | 需 CopilotKit 的 Provider 适配自研 LLM Service                                   |
| 包大小           | 核心 runtime + React 包           | 现有 bundle                             |  ⚠️ | CopilotKit + AG-UI 客户端 + LangGraph 等会显著增加首屏体积（需 code-splitting）            |
| 协议许可          | MIT                            | -                                     |  ✅  | 完全兼容商用                                                                     |
| 私有化部署         | 自托管 Runtime 可行                 | ODAP 全栈私有化                            |  ✅  | CopilotKit Runtime 可自托管，Self-Learning / Cloud 不用即可                         |
| 数据出境          | 默认无（除 Cloud）                   | ODAP 不出境                              |  ✅  | 关掉 CopilotKit Cloud 即可                                                     |

***

## 与已有决策的兼容性 (Compatibility with Existing Decisions)

### 与 ADR-052 的关系

ADR-052 评估的 4 个项目都是 **完整 Chat UI 模板**（LobeChat / Open WebUI / LibreChat / Dify），结论是"不自研基础聊天组件、用 Ant Design X"。

CopilotKit **不是 Chat UI 模板**，而是 **Agent SDK**，定位不同。两者不直接冲突，但需要在"基础聊天组件"和"Agent 编排层"两个层级分别考虑。

| 层级            | ADR-052 决策                                | CopilotKit 提议                | 关系                                     |
| ------------- | ----------------------------------------- | ---------------------------- | -------------------------------------- |
| **基础聊天组件**    | Ant Design X (Bubble/Sender/Conversation) | `<CopilotChat>` 组件           | **替代**（但 ADR-052 已基于 Ant Design X 重构过） |
| **Agent 编排层** | OpenHarness（自研/适配）                        | AG-UI Runtime + CopilotKit   | **潜在替代**（若 CopilotKit 接管 agent 编排）     |
| **状态管理**      | Zustand                                   | React Context（CopilotKit 内置） | **共存**（通过 Provider 桥接）                 |
| **图谱可视化**     | AntV G6                                   | 无                            | **无冲突**                                |

### 与 @openharness/react 的关系

ODAP 已通过 `@openharness/react@1.0.1` 集成 OpenHarness。OpenHarness 与 CopilotKit 在"Agent ↔ UI"领域存在 **直接竞争**：

| 维度   | OpenHarness              | CopilotKit                                                 |
| ---- | ------------------------ | ---------------------------------------------------------- |
| 协议   | OpenHarness 自研           | AG-UI（开源）                                                  |
| 生态   | 较小                       | LangChain / LangGraph / Mastra / PydanticAI / AWS / Google |
| 后端绑定 | OpenHarness Runtime      | 任意 AG-UI 兼容后端                                              |
| 状态协议 | 自研                       | useAgent hook + 状态共享                                       |
| 多平台  | 主要是 React                | React/Angular/Vue/RN                                       |
| 学习曲线 | 中                        | 中（文档齐全）                                                    |
| 维护   | 子模块方式维护（`./openharness`） | 独立 npm 包 + 10.8k commits                                   |

**判断**：如果团队已经在 OpenHarness 投入大量适配成本（已存在 `odap/biz/integration/openharness_agent/` + `odap/infra/openharness/`），再叠加 CopilotKit 会形成 **两个 agent 调度器**，显著增加复杂度。

***

## 量化评分 (Quantitative Score)

| 维度                     |  权重  | 评分 (1-5) |    加权    | 理由                                                          |
| ---------------------- | :--: | :------: | :------: | ----------------------------------------------------------- |
| 1. 技术栈兼容               |  25% |     4    |   1.00   | React 19 / TS / MIT 全兼容，仅 Zustand 需桥接                       |
| 2. 智能体编排               |  20% |     2    |   0.40   | **致命短板**：ODAP 后端未实现 AG-UI 协议，需写完整 Adapter；且 OpenHarness 已在做 |
| 3. 流式输出 / Chat UI      |  15% |     2    |   0.30   | 落后于 Ant Design X + 自研三栏布局                                   |
| 4. Generative UI       |  10% |     4    |   0.40   | 强匹配，特别是把 Skill 返回渲染为动态卡片                                    |
| 5. Shared State / HITL |  10% |     3    |   0.30   | HITL 对决策推演有吸引力，但需要重写后端协议                                    |
| 6. RAG 集成              |  5%  |     3    |   0.15   | AG-UI 协议对接 Graphiti 工作量未知                                   |
| 7. 工作空间 / 多租户          |  5%  |     2    |   0.10   | CopilotKit 无原生工作空间概念，WS/Sce/Ont 隔离需自实现                      |
| 8. 私有化 / 合规            |  5%  |     4    |   0.20   | MIT + 自托管 Runtime 可行，关掉 Cloud 即可                            |
| 9. 社区活跃度               |  3%  |     5    |   0.15   | 10.8k commits, 1.7k dependents, 多家大厂采用 AG-UI                |
| 10. 学习成本               |  2%  |     3    |   0.06   | 文档齐全但需学 AG-UI 事件流 + CopilotKit Hooks                        |
| **加权总分**               | 100% |  <br />  | **3.06** | <br />                                                      |

**分档判定**: **部分采纳 (Partial)**（2.5 ≤ 3.06 < 4.0），但 P1 级风险较多，且与 OpenHarness 投入冲突。

***

## 风险清单 (Risk Register)

| #   | 风险                                               |   等级   | 缓解措施                                |
| --- | ------------------------------------------------ | :----: | ----------------------------------- |
| R1  | 后端需重写为 AG-UI 协议（事件流），破坏现有 FastAPI + SSE 架构       | **P0** | 不集成，或仅在沙箱做 POC                      |
| R2  | 与 OpenHarness 形成"双编排器"，复杂度翻倍                     | **P0** | 二选一：先迁移 OpenHarness 到 AG-UI 再评估     |
| R3  | Self-Learning / Cloud 引入需关闭，否则数据出境风险             |   P1   | 默认关闭，配置开关                           |
| R4  | CopilotKit 组件风格与 Ant Design 6 不一致（混搭视觉割裂）        |   P1   | 仅使用 headless hooks，UI 全部自研          |
| R5  | 失去"工作空间 / 场景 / 本体"层级语义                           |   P1   | 在 CopilotKit 的 agentId 编码 WS/Sce 信息 |
| R6  | 包大小增加（粗估 +200KB gzip 仅 core）                     |   P2   | code-splitting，仅在 `/qa` 路由懒加载       |
| R7  | React 19 兼容性需实测（官方未明示）                           |   P2   | 先做 1 天 POC                          |
| R8  | AG-UI 协议尚新（CopilotKit 主导），长期维护风险                 |   P2   | 协议本身已开源，可 fork                      |
| R9  | 团队需学 CopilotKit 概念体系（agent/context/state/thread） |   P3   | 文档 + 培训 1 周                         |
| R10 | 升级到 CopilotKit v2 时部分 API breaking               |   P3   | 锁定版本，封装自有 Facade                    |

***

## 集成剖面图 (Integration Profile)

> **仅在"部分采纳"分支下使用**。当前文档定位为评估，最终采用需重新过 Plan/Tasks 阶段。

### 涉及文件（估算）

| 模块                                    | 文件                  | 改造点                                                                                                   |
| ------------------------------------- | ------------------- | ----------------------------------------------------------------------------------------------------- |
| `frontend/package.json`               | -                   | 新增 `@copilotkit/react-core`, `@copilotkit/react-ui`, `@copilotkit/runtime-client-gql`（估算 +250KB gzip） |
| `frontend/src/modules/qa/providers/`  | `QAIProvider.tsx`   | 包裹 `<CopilotKitProvider runtimeUrl="/api/copilotkit">` + 现有 QAI Provider                              |
| `frontend/src/modules/qa/hooks/`      | `useQAI.ts`         | 可选用 `useAgent({ agentId: "qa_engine" })` 替代自定义 fetch+SSE                                              |
| `frontend/src/modules/qa/stores/`     | `qaStore.ts`        | 桥接 CopilotKit 状态 ↔ Zustand store                                                                      |
| `frontend/src/modules/qa/components/` | `QAChatPage.tsx` 等  | 可保留 Ant Design X 气泡，仅用 CopilotKit 做 agent 连接                                                          |
| `frontend/src/modules/workspace/`     | `WorkspaceSwitcher` | agentId 中编码 workspaceId，触发 CopilotKit thread 切换                                                       |
| `odap/web/app.py`                     | -                   | 新增 `/api/copilotkit` 端点，挂载 CopilotKit Python Runtime                                                  |
| `odap/infra/copilotkit/`              | -                   | **新增**：AG-UI 协议适配层，把现有 `/api/qa/ask` 翻译为 AG-UI 事件流                                                    |
| `docs/03-modules/qa_engine/`          | `DESIGN.md`         | 增加 "CopilotKit 集成章节"                                                                                  |

### 最小可行 POC 步骤

1. 新建 `/qa/copilot` 演示路由（不影响现有 `/qa`）
2. 后端新增 `/api/copilotkit` 端点，写最小 AG-UI → `/api/qa/ask` 的 proxy
3. 前端在 `CopilotKitProvider` 内放置 `<CopilotChat>`，验证 hello world 流式输出
4. 验证工作空间隔离（不同 ws\_id 下，agentId 不同，thread 不串）
5. 验证 OPA 鉴权（CopilotKit 携带 JWT 后是否仍受 OPA 策略保护）
6. 评估包大小、TTI、内存占用

***

## 推荐结论 (Recommendation) — 【2026-06-08 重大修订】

### 结论：**不集成 CopilotKit 包，但对接 AG-UI 工业标准协议**

**修订说明**：原"拒绝全量集成"结论保留 — **不引入** **`@copilotkit/*`** **任何包**（与 OpenHarness 冲突 + 包大小）。**但协议层决策反转**：原计划自研 OAUIP 协议，**修订为对接 AG-UI 工业标准协议**。理由：

1. **AG-UI 是真正的工业标准**（已被 Google / LangChain / AWS / Microsoft / Mastra / PydanticAI 6+ 大厂采用），不是 CopilotKit 私有
2. **AG-UI 是协议规范，不是 npm 包** — 对接它 ≠ 引入 CopilotKit
3. **OAUIP 自研不必要** — AG-UI 已提供 Generative UI / Shared State / HITL / Backend Tool Rendering 全部原语
4. **工作量从 8.8 周降至 6 周**（节省 14 人天）
5. **未来可接入 LangChain / PydanticAI / Mastra**（ODAP 长期可受益）

### 不建议动作

- ❌ 不在生产环境引入 `@copilotkit/react-*` 系列包
- ❌ 不把现有 QAPanel / QAIProvider 重构为 CopilotKit
- ❌ 不替换 OpenHarness
- ❌ ~~不创建自研 OAUIP 协议~~（2026-06-08 修订：删除，改为对接 AG-UI）

### 建议动作（修订后）

- ✅ **对接 AG-UI 协议**（实现 AG-UI Python 服务端 + TypeScript 客户端适配）
- ✅ **保留对 AG-UI 协议演进跟踪**（订阅 <https://github.com/ag-ui-protocol/ag-ui）>
- ✅ 6 周内完成 Generative UI / HITL 三个最有价值能力

### 回退条件（任一为真时启动新一轮评估）

- OpenHarness 维护停滞（无 commit > 6 个月）
- AG-UI 协议主版本变更（v0.x → v1.0）且破坏接口
- ODAP 决定全面接入 LangChain / PydanticAI 等第三方 Agent 框架（AG-UI 已就绪）
- 出现比 AG-UI 更优的标准协议

### ~~原决策（已废止）~~

> ~~结论：**拒绝 (Reject) 全量集成；有条件地 (Conditional) 关注 Generative UI 子能力**~~
>
> ~~理由：~~
>
> 1. **~~加权得分 3.06，仅勉强"部分采纳"，且 P0 级风险不可缓解~~**
> 2. **~~后端需重写为 AG-UI 协议~~**~~（R1），工程量级 = 重新实现 QA Engine 事件流层~~
> 3. **~~与 OpenHarness 双编排器冲突~~**~~（R2），现有投入全部沉没~~
> 4. **~~基础聊天组件已基于 Ant Design X 落地~~**~~，替换收益低~~
>
> **~~修订原因（2026-06-08）~~**~~：漏掉了"AG-UI 是开源协议标准（不是 CopilotKit 私有）"这个事实。对接 AG-UI 不需要引入 CopilotKit 包，规避了 R1/R2 风险。~~

***

## Assumptions

- 评估基于 2026-06-08 仓库状态（CopilotKit `main` 分支 10,825 commits、Latest release v1.59.5、AG-UI 已被 6 家大厂采用）
- ODAP 后端不会在评估期内（1 个月内）开始 AG-UI 协议适配
- OpenHarness 子模块在评估期内持续维护
- 团队对 React 19 / Zustand 5 已熟悉，不存在额外学习成本
- ODAP 业务场景在 1 年内不会扩展到 Slack / Teams / React Native
- 数据合规要求"不出域"为硬约束
- 评估不涉及法律 / 法务 / 知识产权详细审查（仅 MIT 协议层）

***

## 关联文档

- [ADR-052 智能问答WebUI开源项目选型](../../docs/07-adr/ADR-052_webui_opensource_selection.md) — 已有的开源项目评估结论
- [QA Engine 设计文档](../../docs/03-modules/qa_engine/DESIGN.md) — ODAP 后端问答引擎设计
- [Web Frontend 设计文档](../../docs/03-modules/web_frontend/DESIGN.md) — ODAP 前端架构
- [前端 QA 模块当前实现](../006-copilotkit-eval-profile/QA_MODULE_MAP.md) — 实际文件清单（待补充）
- [CopilotKit GitHub](https://github.com/CopilotKit/CopilotKit) — 被评估项目
- [AG-UI 协议](https://github.com/ag-ui-protocol/ag-ui) — CopilotKit 主导的 Agent ↔ UI 协议

