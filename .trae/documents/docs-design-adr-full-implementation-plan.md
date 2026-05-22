# 设计文档与 ADR 完整实现计划（更新版）

> **目标**: 分批次核实 docs/ 中所有架构文档、设计文档和 ADR 的实现状态，对未实现项逐一实现，补充测试用例（含 UI 测试），使用实际数据验证功能可用性，最终提交代码。

---

## 当前进度总览

| 批次 | 状态 | 完成项 | 剩余项 |
|------|------|--------|--------|
| Batch 1: 后端核心缺失模块 | ✅ 已完成 | 3/3 | 0 |
| Batch 2: 后端部分实现补全 | 🔶 进行中 | 9/11 | 2 |
| Batch 3: 前端核心缺失组件 | ⬜ 未开始 | 0/8 | 8 |
| Batch 4: 前端高级功能 | ⬜ 未开始 | 0/5 | 5 |
| Batch 5: 集成测试与端到端验证 | ⬜ 未开始 | 0/5 | 5 |
| Batch 6: 运维与提交 | ⬜ 未开始 | 0/3 | 3 |

---

## Batch 1: 后端核心缺失模块（P0）— ✅ 已完成

| # | 任务 | 状态 | 验证结果 |
|---|------|------|----------|
| 1.1 | 实现模拟数仓与统一查询服务 (QueryService) | ✅ 完成 | 51个测试全部通过 |
| 1.2 | 实现会话记忆模块 (ContextWindow/MemoryCompactor/CoTBuilder) | ✅ 完成 | 单元测试通过 |
| 1.3 | 实现完整 Markdown→Rego 转换器 | ✅ 完成 | 单元测试通过 |

---

## Batch 2: 后端部分实现补全（P1）— 🔶 进行中

| # | 任务 | 状态 | 实现详情 |
|---|------|------|----------|
| 2.1 | 多数据源适配器 (Sensor/API/DB) | ✅ 完成 | 三个适配器已实现 |
| 2.2 | 多模态模型选择层 | ✅ 完成 | MultimodalProcessor 已实现（含回退链） |
| 2.3 | 本体热写入管道 | ✅ 完成 | HotWriteService 已实现 |
| 2.4 | Agent 语义路由 | ✅ 完成 | AgentRouter 已实现（关键词匹配版） |
| 2.5 | 语义发现 + 工具链 | ✅ 完成 | SemanticDiscovery + CompositeExecutor 已实现 |
| 2.6 | SkillOrchestrator + WorkflowEngine | ✅ 完成 | 拓扑排序 + 三种执行模式已实现 |
| 2.7 | OODA 四阶段循环 + 流式执行 | ✅ 完成 | DomainSwarm 已实现完整 OODA + 流式 |
| 2.8 | 方案版本管理/分支/回退 | ✅ 完成 | create_plan_branch/rollback_plan 已实现 |
| 2.9 | 模拟时钟 + 触发器注册 | ✅ 完成 | advance_clock/register_trigger 已实现 |
| 2.10 | OAuth2 流程 + API Key 认证 | ⬜ 待实现 | API Key 已实现，OAuth2 仅预留接口 |
| 2.11 | LLM 增强风险评估 | ⬜ 待实现 | 规则化评估已有，LLM 增强未实现 |

### 2.10 详细实现计划：OAuth2 流程

**当前状态**: `auth_service.py` 已有本地认证（bcrypt/SHA256）和 API Key 管理，OAuth2 仅为注释预留。

**实现方案**:
- 在 `AuthService` 中新增 `authenticate_oauth2(provider, code, redirect_uri)` 方法
- 支持通用 OAuth2 Authorization Code Flow
- 实现 `get_oauth2_authorize_url(provider)` 生成授权 URL
- 实现 OAuth2 token 交换和用户信息获取
- 支持多 Provider 配置（Google/GitHub/自定义 OIDC）
- 新增 `OAuth2ProviderConfig` Pydantic 模型
- 新增 `odap/infra/security/oauth2_providers.py` 存放 Provider 配置

**新增/修改文件**:
- 修改: `odap/infra/security/auth_service.py` — 添加 OAuth2 方法
- 新增: `odap/infra/security/oauth2_providers.py` — Provider 配置和 token 交换
- 新增: `odap/infra/security/api/routes.py` — OAuth2 登录/回调端点（如不存在）
- 新增: `tests/unit/test_oauth2.py` — OAuth2 流程单元测试

**测试要求**:
- OAuth2 授权 URL 生成
- Token 交换流程（Mock HTTP 请求）
- 用户信息获取和本地账号关联
- 无效 code / 过期 token 处理
- API Key 创建/验证/吊销（已有，补充边界测试）

### 2.11 详细实现计划：LLM 增强风险评估

**当前状态**: `engine.py` 的 `_assess_risk()` 使用硬编码规则评分（4个维度固定权重），未调用 LLM。

**实现方案**:
- 在 `_assess_risk()` 中增加 LLM 调用路径
- 当 LLM 可用时，使用 LLM 分析风险因素（上下文感知、语义化风险识别）
- 当 LLM 不可用时，回退到现有规则化评估
- 新增 `_assess_risk_with_llm()` 方法
- LLM Prompt 设计：输入方案描述 + 上下文，输出结构化风险评估 JSON
- 合并规则评分和 LLM 评分（加权融合：规则0.3 + LLM0.7）

**新增/修改文件**:
- 修改: `odap/biz/decision_recommendation/engine.py` — 添加 LLM 风险评估
- 新增: `tests/unit/test_decision_recommendation.py` — 决策推荐引擎测试

**测试要求**:
- 规则化风险评估（已有逻辑的回归测试）
- LLM 增强风险评估（Mock LLM 响应）
- LLM 不可用时回退到规则评估
- 评分融合逻辑
- 方案排序算法验证

---

## Batch 3: 前端核心缺失组件（P0-P1）— ⬜ 待开始

**范围**: 产品设计文档和 UI 设计文档中要求但未实现的前端组件

| # | 来源 | 任务 | 新增/修改文件 | 测试要求 |
|---|------|------|-------------|---------|
| 3.1 | 产品设计 | 替换 OntologySemanticNetwork Mock 数据为真实 API | 修改 `frontend/src/modules/ontology/components/OntologySemanticNetwork.tsx` | 组件测试: 数据加载、渲染、交互 |
| 3.2 | 产品设计 | QA→Skill 建议改为 AI 驱动推荐 | 修改 `frontend/src/modules/qa/pages/QAChatPage.tsx` | 组件测试: 建议生成、点击执行 |
| 3.3 | 产品设计/04-ui | 实现 SchemaEditor.tsx (JSON Schema 可视化编辑器) | `frontend/src/modules/system/components/SchemaEditor.tsx` | 组件测试: Schema 编辑、验证、预览 |
| 3.4 | 产品设计 | 实现图谱时序可视化 (双时态时间轴) | `frontend/src/modules/ontology/components/TemporalTimeline.tsx` | 组件测试: 时间轴滑块、数据更新 |
| 3.5 | 04-ui COMPONENT_SPEC | 实现 ProgressTracker 进度展示组件 | `frontend/src/modules/shared/components/ProgressTracker.tsx` | 组件测试: 阶段切换、进度更新 |
| 3.6 | ADR-031 L1 | 实现模拟器 Web 可视化 (事件时间线/关系图谱/态势地图) | `frontend/src/modules/ingest/components/SimulatorDashboard.tsx`, `EventTimeline.tsx`, `SituationMap.tsx` | 组件测试: 时间线播放、图谱交互 |
| 3.7 | ADR-037 | 实现响应式布局适配 (Mobile First) | 修改 `frontend/src/modules/shared/components/AppLayout.tsx` | 组件测试: 断点切换、布局变化 |
| 3.8 | ADR-037 | 实现 i18n 国际化框架 | `frontend/src/locales/zh-CN/messages.json`, `en-US/messages.json`, `frontend/src/i18n/` | 组件测试: 语言切换 |

**前端测试基础设施**:
- 测试运行器: Vitest 3.2.4
- DOM 环境: jsdom
- 组件测试: @testing-library/react 16.x
- DOM 断言: @testing-library/jest-dom 6.x
- 覆盖率: @vitest/coverage-v8
- 需新增: `frontend/src/test/test-utils.tsx`（自定义 render 封装，包含 Provider 包裹）

**验证方式**: 每个组件使用 React Testing Library + Vitest 测试渲染和交互；响应式使用 viewport 模拟测试；i18n 使用语言切换测试。

---

## Batch 4: 前端高级功能（P1-P2）— ⬜ 待开始

| # | 来源 | 任务 | 新增/修改文件 | 测试要求 |
|---|------|------|-------------|---------|
| 4.1 | 产品设计 | 实现 React Flow Skill 工作流编排 | `frontend/src/modules/system/components/SkillWorkflow.tsx`, 安装 `@xyflow/react` | 组件测试: 节点拖拽、连线、执行 |
| 4.2 | 产品设计 | 实现前端反馈仪表盘 | `frontend/src/modules/feedback/pages/FeedbackDashboard.tsx` | 组件测试: 数据展示、图表交互 |
| 4.3 | ADR-020 | 完善管理员控制台 (配置中心双模式编辑器+版本历史) | 修改 `frontend/src/modules/config/pages/PolicyManagement.tsx` | 组件测试: 编辑器交互、版本切换 |
| 4.4 | web_frontend DESIGN | 实现 WebSocket 管理器和 SSE 流式输出 | `frontend/src/modules/shared/hooks/useWebSocket.ts`, `useSSE.ts` | Hook 测试: 连接、消息接收、断线重连 |
| 4.5 | 04-ui UI_DESIGN | 实现节点右键菜单和自定义 Cypher 查询 | 修改 `frontend/src/modules/ontology/components/GraphCanvas.tsx` | 组件测试: 右键菜单、查询执行 |

---

## Batch 5: 集成测试与端到端验证（P0）— ⬜ 待开始

| # | 来源 | 任务 | 新增/修改文件 | 测试要求 |
|---|------|------|-------------|---------|
| 5.1 | TEST_DESIGN §2.1 | 补齐后端单元测试 (覆盖率 > 80%) | `tests/unit/test_*.py` | 覆盖率报告 |
| 5.2 | TEST_DESIGN §3 | 补齐集成测试 (关键路径 100%) | `tests/integration/test_*.py` | 关键路径通过 |
| 5.3 | TEST_DESIGN §4 | 补齐 E2E 测试 (核心流程 100%) | `tests/e2e/test_*.py` | 核心流程通过 |
| 5.4 | ADR-044 | 前端组件测试 (Vitest + React Testing Library) | `frontend/src/**/*.test.tsx` | 组件覆盖率 > 70% |
| 5.5 | - | 实际数据端到端验证 | 使用真实场景数据运行完整 OADP 闭环 | 全流程通过 |

**当前测试覆盖情况**:
- 后端单元测试: 5 个文件（OPA转换器、会话记忆、数据仓库、存储层、本体引擎）
- 后端集成测试: 3 个文件（本体集成、完整API端点、API可用性）
- 后端E2E测试: 1 个文件
- 前端测试: 2 个文件（API集成、模块导出验证）
- **缺失**: 工具注册表、Agent系统、技能系统、仿真沙箱、事件模拟器、认证服务、决策推荐等模块的单元测试

**需新增的后端单元测试文件**:
- `tests/unit/test_auth_service.py` — 认证服务（OAuth2 + API Key）
- `tests/unit/test_decision_recommendation.py` — 决策推荐引擎
- `tests/unit/test_agent_router.py` — Agent 路由
- `tests/unit/test_tool_registry.py` — 工具注册表（已有根目录版本，需迁移到 unit/）
- `tests/unit/test_skill_system.py` — 技能系统（编排器 + 工作流引擎）
- `tests/unit/test_simulation_sandbox.py` — 仿真沙箱
- `tests/unit/test_event_simulator.py` — 事件模拟器
- `tests/unit/test_data_pipeline.py` — 数据管道 + 适配器
- `tests/unit/test_hot_write_service.py` — 热写入服务
- `tests/unit/test_swarm_orchestrator.py` — OODA 循环

**需新增的前端测试文件**:
- `frontend/src/modules/ontology/components/__tests__/OntologySemanticNetwork.test.tsx`
- `frontend/src/modules/qa/pages/__tests__/QAChatPage.test.tsx`
- `frontend/src/modules/system/components/__tests__/SchemaEditor.test.tsx`
- `frontend/src/modules/ontology/components/__tests__/TemporalTimeline.test.tsx`
- `frontend/src/modules/shared/components/__tests__/ProgressTracker.test.tsx`
- `frontend/src/modules/ingest/components/__tests__/SimulatorDashboard.test.tsx`
- `frontend/src/modules/shared/components/__tests__/AppLayout.test.tsx`
- `frontend/src/test/i18n.test.ts`

---

## Batch 6: 运维与提交（P2-P3）— ⬜ 待开始

| # | 来源 | 任务 | 新增/修改文件 | 测试要求 |
|---|------|------|-------------|---------|
| 6.1 | ARCHITECTURE_OPS | 配置 Prometheus+Grafana 监控 | `docker/monitoring/prometheus.yml`, `grafana/` | 验证指标采集 |
| 6.2 | - | 代码 Lint + 类型检查 | 无新增 | 0 error, 0 warning |
| 6.3 | - | Git 提交 (遵循 ADR-017 原子提交规范) | - | 提交信息符合 Conventional Commits |

---

## 执行顺序与优先级

### 立即执行（从上次中断处继续）

1. **2.10** — 实现 OAuth2 流程（`auth_service.py` + `oauth2_providers.py` + 路由 + 测试）
2. **2.11** — 实现 LLM 增强风险评估（`engine.py` + 测试）
3. **Batch 2 测试验证** — 运行全部后端测试确保无回归

### 接下来执行

4. **3.0** — 创建前端测试基础设施（`test-utils.tsx`）
5. **3.1~3.8** — 逐一实现前端核心组件 + 组件测试
6. **4.1~4.5** — 实现前端高级功能 + 测试
7. **5.1~5.5** — 补齐所有测试 + 实际数据验证
8. **6.1~6.3** — 运维监控 + Lint + 提交

---

## 执行原则

1. **每批次内并行开发**: 同一批次内的任务相互独立，可并行实施
2. **先实现后测试**: 每个功能先完成实现，再补充测试用例
3. **实际数据验证**: 每个功能使用真实/模拟数据端到端验证
4. **增量提交**: 每完成一个批次提交一次，遵循 Conventional Commits 格式
5. **测试先行修复**: 如果测试发现 bug，立即修复后再继续
6. **LLM 可选降级**: 所有 LLM 增强功能必须支持 LLM 不可用时降级到规则化实现

## 预计产出

| 产出 | 数量 |
|------|------|
| 新增后端 Python 文件 | ~5 (Batch 2 剩余) |
| 修改后端 Python 文件 | ~3 (Batch 2 剩余) |
| 新增前端 TSX/TS 文件 | ~15 |
| 修改前端 TSX/TS 文件 | ~8 |
| 新增后端单元测试文件 | ~10 |
| 新增前端测试文件 | ~10 |
| Git 提交次数 | ~6 (每批次1次) |
