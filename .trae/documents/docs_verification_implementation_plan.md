# 文档核实与功能补全实施计划 v2.0

> **创建日期**: 2026-05-21
> **目标**: 分批次核实 docs 中的架构文档、设计文档和 ADR 是否完整实现，补全缺失功能，补齐测试用例，最终提交代码

---

## 一、现状分析总结

### 1.1 代码实现状态

| 分类 | 模块数 | 完整实现 | 部分 Stub | 纯 Stub |
|------|--------|----------|-----------|---------|
| odap/biz/ | 24 | 22 | 2 (knowledge_base RAG/爬取) | 0 |
| odap/infra/ | 14 | 13 | 0 | 1 (config/ 仅注释) |
| odap/tools/ | 13 | 13 | 0 | 0 |
| odap/web/ | 3 | 3 | 0 | 0 |
| frontend/ | 13模块 | 13 | 0 | 0 |

### 1.2 测试状态

| 层级 | 文件数 | 测试用例数 | 覆盖情况 |
|------|--------|-----------|---------|
| 后端单元测试 | 12 | ~95 | 覆盖 12/24 模块 |
| 后端集成测试 | 3 | ~71 | 断言过于宽松 |
| 后端 E2E | 1 | 6 | 实为 mock 集成测试 |
| 前端测试 | 2 | ~30 | 零组件渲染测试 |

### 1.3 关键缺口

1. **后端测试失败**: 决策管道和动作服务测试因惰性属性(self.opa vs self._opa_manager)不匹配导致失败
2. **后端 Stub**: knowledge_base RAG 查询和 Web 爬取返回占位响应
3. **前端测试**: 完全缺失组件渲染/交互测试
4. **ADR 实现差距**: ADR-051(40%)、ADR-052(25%)、ADR-053(50%)、ADR-011(45%)
5. **前端登录页面**: 后端认证逻辑存在但无登录 UI
6. **集成测试断言**: 大量 `assert status_code in [200, 404, 500]` 无实际验证
7. **Stub 代码**: 12 项占位实现需完成（2 P0、5 P1、5 P2）

---

## 二、分批次实施计划

### 批次 1: 后端测试修复与补齐（P0）

**目标**: 修复已有测试失败，为无测试覆盖的核心后端模块补齐单元测试

#### 1.1 修复决策管道测试失败

**问题根因**: 测试设置 `pipeline._opa_manager = None`，但代码通过 `self.opa` 惰性属性访问，该属性在 `_opa_manager` 为 None 时会尝试导入 `OPAManagerV2` 并创建实例，导致 fail-closed 路径无法触发。

**修复方案**: 使用 `patch.object(type(pipeline), 'opa', new_callable=PropertyMock, return_value=None)` mock 属性本身。

**涉及文件**:
- `tests/unit/test_decision_pipeline.py`
  - `TestDecisionPipelineValidateFailClosed::test_fail_closed_no_opa` — patch opa 属性
  - `TestDecisionPipelineDecideFailure::test_decide_failure` — patch decision_engine 属性
  - `TestDecisionPipelineOPARejection::test_opa_rejection_skips_perform` — 确认 mock 设置一致性
  - `TestPipelineStagesTracking::test_stages_progress_on_partial_failure` — patch decision_engine 属性

#### 1.2 修复动作服务测试失败

**问题根因**: 同上，`self.opa` 惰性属性问题。

**涉及文件**:
- `tests/unit/test_action_service.py`
  - `TestCheckOPA::test_no_opa_configured_fail_closed` — patch opa 属性
  - `TestCheckOPA::test_opa_exception_fail_closed` — patch opa 属性返回 mock

#### 1.3 补齐认知引擎测试

- 文件: `tests/unit/test_cognition.py`（已有，需确认通过率）
- 测试内容:
  - `UserCognitionEngine` 意图识别（军事/分析/管理/通用）
  - 角色视图获取（commander/intelligence_officer/operator/admin）
  - 知识导航（基于图谱路径检索）
  - 决策解释（推理链生成）
- 对应文档: ADR-038, ADR-049, ARCHITECTURE_BIZ.md §22-23

#### 1.4 补齐图谱服务测试

- 文件: `tests/unit/test_graph_service.py`（已有，需确认通过率）
- 测试内容:
  - `GraphManager` NetworkX 回退模式（节点/边 CRUD、查询、路径查找）
  - Graphiti 客户端适配（mock Neo4j 场景）
  - 工作空间隔离查询
- 对应文档: ADR-002, ARCHITECTURE_INFRA.md §4

#### 1.5 补齐工具注册表测试

- 文件: `tests/unit/test_tool_registry.py`（已有，需确认通过率）
- 测试内容:
  - `ToolRegistry` 注册/发现/执行（Skill/MCP/REST/Function 四种类型）
  - `SemanticDiscovery` TF-IDF 语义搜索
  - `CompositeExecutor` 组合执行与回滚
  - OPA 权限桥接
- 对应文档: ADR-029, ADR-047, ARCHITECTURE_INFRA.md §5

#### 1.6 补齐感知中枢测试

- 文件: `tests/unit/test_perception.py`（已有，需确认通过率）
- 测试内容:
  - `PerceptionHub` 多源数据接入
  - 观察者注册/注销
  - 数据摄入与处理
- 对应文档: ADR-050, ARCHITECTURE_BIZ.md §感知层

#### 1.7 补齐仿真沙箱测试

- 文件: `tests/unit/test_simulation_sandbox.py`（需新建或确认已有）
- 测试内容:
  - What-if 仿真执行
  - 计划分支与对比
- 对应文档: ADR-018, ADR-031

**验收标准**: 所有后端单元测试通过（pytest tests/unit/ -v 零失败）

---

### 批次 2: 后端集成测试强化（P0）

**目标**: 修复集成测试中的宽松断言，增加实际数据验证

#### 2.1 修复 `test_api_integration.py` 断言

- 将 `assert status_code in [200, 404, 500]` 改为精确断言
- 验证响应体结构和关键字段
- 增加业务逻辑正确性验证

#### 2.2 新增数据摄入完整流程测试

- 文件: `tests/integration/test_ingest_pipeline.py`（新建）
- 测试内容:
  - 文本摄入 → 本体构建 → 版本快照完整链路
  - 新闻摄入 → 实体抽取 → 关系识别
  - JSON 摄入 → Schema 验证 → 写入图谱

#### 2.3 新增 OADP 闭环集成测试

- 文件: `tests/integration/test_oadp_loop.py`（新建）
- 测试内容:
  - 感知 → 理解 → 决策 → 执行 完整闭环
  - 反馈收集 → 分析 → 聚合
  - 工作空间隔离下的闭环执行

**验收标准**: 集成测试断言精确，新增 ≥ 20 个测试用例

---

### 批次 3: 后端 Stub 功能实现（P1）

**目标**: 实现知识库 RAG 查询和 Web 爬取的占位功能

#### 3.1 知识库 RAG 查询实现

- 文件: `odap/biz/knowledge_base/api/routes.py` — 修改 `rag_query` 端点
- 实现方案（MVP）:
  - 基于关键词检索的简单 RAG（不依赖嵌入模型）
  - 从 SQLite 知识库存储中检索相关文档片段
  - 使用 LLM 服务生成答案
  - 返回答案 + 来源文档 + 相关实体
- 对应文档: ADR-019, ARCHITECTURE_FULL_CHAIN.md §Phase 3

#### 3.2 知识库 Web 爬取实现

- 文件: `odap/biz/knowledge_base/api/routes.py` — 修改 `crawl_web` 端点
- 实现方案（MVP）:
  - 使用 `odap/utils/web_scraper.py` 已有的爬取工具
  - URL 爬取 → HTML 解析 → 文本清洗 → 入库
  - 返回异步任务 ID 和状态
- 对应文档: ADR-013

#### 3.3 知识库图谱构建实现

- 文件: `odap/biz/knowledge_base/api/routes.py` — 修改 `build_graph` 端点
- 实现方案:
  - 从文档中提取实体和关系
  - 调用 GraphManager 写入图谱
  - 返回异步任务 ID 和状态

#### 3.4 补充知识库测试

- 文件: `tests/unit/test_knowledge_base.py`（新建）
- 测试 RAG 查询、Web 爬取、图谱构建功能

#### 3.5 修复其他 Stub 代码

- `odap/biz/ontology/services/pipeline_service.py`: 实现 `get_context` 和 `get_stage_logs`
- `odap/biz/tool_registry/api/routes.py`: 改进 `placeholder_func` 为可配置的函数执行器
- `odap/biz/simulation_sandbox/sandbox.py`: 删除死代码（第一个 `_project_impact_with_llm` 定义）
- `odap/infra/config/__init__.py`: 补充配置管理基础功能

**验收标准**: 所有 Stub 端点返回真实数据，知识库功能可用

---

### 批次 4: 前端组件测试补齐（P0）

**目标**: 为核心前端组件添加渲染和交互测试

#### 4.1 测试基础设施确认

- 确认 Vitest + @testing-library/react + jsdom 配置正确
- 确认 `frontend/src/test/setup.ts` mock 配置完整
- 确认 Ant Design 组件在 jsdom 环境下可渲染

#### 4.2 共享组件测试

- 文件: `frontend/src/modules/shared/components/__tests__/`（新建目录）
- 测试内容:
  - `AppLayout` 布局渲染、工作空间切换
  - `QAPanel` 消息渲染、输入发送
  - `StatCard` 数据展示
  - `ToolHealthIndicator` 健康状态

#### 4.3 本体模块组件测试

- 文件: `frontend/src/modules/ontology/components/__tests__/`（新建目录）
- 测试内容:
  - `GraphCanvas` G6 图谱渲染（mock G6）
  - `ActionPanel` 动作面板交互
  - `OntologyIngestPipeline` 摄入流水线步骤

#### 4.4 QA 模块测试

- 文件: `frontend/src/modules/qa/__tests__/`（新建目录）
- 测试内容:
  - `useQAI` Hook 流式问答、SSE 解析
  - `SessionDrawer` 会话管理
  - QA 页面渲染和交互

#### 4.5 工作空间模块测试

- 文件: `frontend/src/modules/workspace/__tests__/`（新建目录）
- 测试内容:
  - `WorkspaceSwitcher` 工作空间切换
  - 场景管理交互

**验收标准**: 新增 ≥ 20 个前端组件测试用例，`npm run test` 通过

---

### 批次 5: ADR 未实现功能核实与补全（P1）

**目标**: 逐个核实 ADR 决策的实现状态，补全关键缺失实现

#### 5.1 ADR-051 闭环反馈机制补全

**当前完成度**: ~40%
**需补全**:
- 创建 `odap/biz/feedback/` 独立模块目录
- 实现 `FeedbackType` 枚举（四种反馈类型）
- 重构 `FeedbackCollector` 支持多种反馈类型
- 实现异步接口
- 补充闭环反馈测试
- 对应文档: ADR-051, ARCHITECTURE_BIZ.md §22

#### 5.2 ADR-011 角色配置热生效补全

**当前完成度**: ~45%
**需补全**:
- 实现角色变更 → OPA 策略重载的联动机制
- 在角色 CRUD API 中添加 OPA 策略同步逻辑
- 编写热生效集成测试（验证角色变更后权限即时更新）
- 对应文档: ADR-011

#### 5.3 ADR-014 技能热插拔验证

**当前完成度**: ~60%
**需补全**:
- 验证热插拔 API 端点是否完整暴露
- 编写热插拔集成测试（运行时加载/卸载技能）
- 清理 SkillWatcher/SkillValidator 的 TODO 标记
- 对应文档: ADR-014

#### 5.4 ADR-009 Markdown→Rego 验证

**当前完成度**: ~65%
**需补全**:
- 验证前端策略管理页面是否集成 Markdown 编辑器
- 验证 Rego 预览功能是否可用
- 补充 Markdown→Rego 转换的边界用例测试
- 对应文档: ADR-009

#### 5.5 ADR-052/053 前端选型验证

**当前完成度**: ADR-052 ~25%, ADR-053 ~50%
**需补全**:
- 验证三栏布局功能完整性（ADR-052）
- 验证 Skill 管理界面功能完整性（ADR-053）
- 记录未引入的选型组件（Ant Design X / React Flow / CodeMirror 6）为后续迭代项
- 对应文档: ADR-052, ADR-053

**验收标准**: ADR-051 闭环反馈机制实现，ADR-011 热生效联动打通，其他 ADR 验证完成

---

### 批次 6: 架构文档核实与修复（P2）

**目标**: 修复文档中的已知问题，确保文档与代码一致

#### 6.1 修复 ARCHITECTURE_WEB.md 章节号

- 问题: §11.5.1 应为 §11.6.1
- 来源: DEEP_REVIEW_REPORT_20260505.md

#### 6.2 更新 ARCHITECTURE.md 行数统计

- 问题: 多个子文档行数统计不准确
- 来源: DEEP_REVIEW_REPORT_20260505.md

#### 6.3 修复 ARCHITECTURE_BIZ.md 代码语法

- 问题: f-string 引号转义错误
- 来源: DEEP_REVIEW_REPORT_20260505.md

#### 6.4 更新模块实现状态矩阵

- 问题: ARCHITECTURE_REVIEW 中的状态矩阵需要更新
- 需反映: decision_recommendation 已实现、user_cognition_engine 已实现、feedback 模块已创建等

**验收标准**: 所有已知文档问题修复，状态矩阵与代码一致

---

### 批次 7: 实际数据端到端测试（P0）

**目标**: 使用实际数据验证完整功能链路

#### 7.1 数据摄入端到端测试

- 使用真实新闻文本进行摄入
- 验证: 文本摄入 → 实体抽取 → 关系识别 → 本体构建 → 版本快照
- 验证: 前端摄入界面完整流程

#### 7.2 智能问答端到端测试

- 基于已摄入的本体数据进行问答
- 验证: 意图识别 → 上下文检索 → 流式回答
- 验证: 前端问答界面完整流程

#### 7.3 工作空间隔离端到端测试

- 创建多个工作空间，验证数据隔离
- 验证: 切换工作空间后数据正确隔离
- 验证: 跨工作空间查询（如果支持）

#### 7.4 OPA 策略端到端测试

- 创建 Markdown 策略 → 转换 Rego → 加载 OPA → 权限校验
- 验证: 高危操作被正确拦截
- 验证: 前端策略管理界面

**验收标准**: 4 条核心链路全部通过端到端验证

---

## 三、实施顺序与依赖关系

```
批次 1 (后端测试修复) ──→ 批次 2 (集成测试强化) ──→ 批次 7 (端到端测试)
                                                               ↓
批次 3 (Stub 实现)     ────────────────────────────────→ 批次 7
                                                               ↓
批次 4 (前端组件测试) ────────────────────────────────→ 批次 7
                                                               ↓
批次 5 (ADR 功能补全) ──→ 批次 6 (文档修复) ──────────→ 批次 7
```

**推荐执行顺序**: 1 → 2 → 3 → 4 → 5 → 6 → 7

---

## 四、详细实施步骤

### 批次 1 详细步骤

#### 步骤 1.1: 修复决策管道测试

1. 读取 `tests/unit/test_decision_pipeline.py` 全文
2. 读取 `odap/biz/decision_pipeline/pipeline.py` 全文，确认所有惰性属性
3. 修改 `test_fail_closed_no_opa`:
   ```python
   with patch.object(type(pipeline), 'opa', new_callable=PropertyMock, return_value=None):
       result = await pipeline.execute(inp)
   ```
4. 修改 `test_decide_failure`:
   ```python
   with patch.object(type(pipeline), 'decision_engine', new_callable=PropertyMock, return_value=None):
       # ... test body
   ```
5. 检查所有使用 `_opa_manager`、`_decision_engine`、`_semantic_retriever`、`_action_executor`、`_feedback_loop` 的测试
6. 运行 `pytest tests/unit/test_decision_pipeline.py -v` 确认通过

#### 步骤 1.2: 修复动作服务测试

1. 读取 `tests/unit/test_action_service.py` 全文
2. 读取 `odap/biz/action_service/executor.py` 全文
3. 修改 `test_no_opa_configured_fail_closed`:
   ```python
   with patch.object(type(executor), 'opa', new_callable=PropertyMock, return_value=None):
       result = await executor._check_opa(record, action_type_def)
   ```
4. 修改 `test_opa_exception_fail_closed`:
   ```python
   with patch.object(type(executor), 'opa', new_callable=PropertyMock, return_value=mock_opa):
       result = await executor._check_opa(record, action_type_def)
   ```
5. 运行 `pytest tests/unit/test_action_service.py -v` 确认通过

#### 步骤 1.3-1.7: 补齐其他模块测试

1. 运行现有测试确认通过率
2. 为缺失模块新建测试文件
3. 每个模块至少 10 个测试用例
4. 运行 `pytest tests/unit/ -v` 确认全部通过

### 批次 2 详细步骤

#### 步骤 2.1: 修复集成测试断言

1. 读取 `tests/integration/test_api_integration.py`
2. 搜索所有 `assert status_code in [` 模式
3. 逐个替换为精确断言
4. 添加响应体结构验证

#### 步骤 2.2-2.3: 新增集成测试

1. 创建 `tests/integration/test_ingest_pipeline.py`
2. 创建 `tests/integration/test_oadp_loop.py`
3. 编写完整链路测试
4. 运行 `pytest tests/integration/ -v` 确认通过

### 批次 3 详细步骤

#### 步骤 3.1: 实现 RAG 查询

1. 读取 `odap/biz/knowledge_base/` 目录结构和存储层
2. 实现 `rag_query` 端点:
   - 从 SQLite 存储检索文档
   - 关键词匹配相关片段
   - 调用 LLM 生成答案
   - 返回答案 + 来源 + 相关实体
3. 测试: `curl -X POST http://localhost:8000/api/kb/{kb_id}/rag-query`

#### 步骤 3.2: 实现 Web 爬取

1. 读取 `odap/utils/web_scraper.py`
2. 实现 `crawl_web` 端点:
   - 接收 URL 列表
   - 调用 web_scraper 爬取
   - 解析内容入库
   - 返回任务状态
3. 测试: `curl -X POST http://localhost:8000/api/kb/{kb_id}/crawl`

#### 步骤 3.3: 实现图谱构建

1. 实现 `build_graph` 端点:
   - 从文档提取实体/关系
   - 调用 GraphManager 写入
   - 返回任务状态

#### 步骤 3.4: 补充测试

1. 创建 `tests/unit/test_knowledge_base.py`
2. 测试 RAG 查询、Web 爬取、图谱构建
3. 运行 `pytest tests/unit/test_knowledge_base.py -v`

### 批次 4 详细步骤

#### 步骤 4.1: 确认测试基础设施

1. 读取 `frontend/vitest.config.ts`
2. 读取 `frontend/src/test/setup.ts`
3. 确认 Ant Design 组件 mock 配置
4. 运行 `cd frontend && npm run test` 确认现有测试通过

#### 步骤 4.2-4.5: 编写组件测试

1. 创建测试目录结构
2. 为每个组件编写渲染测试和交互测试
3. Mock 外部依赖（API、G6、ECharts 等）
4. 运行 `cd frontend && npm run test` 确认通过

### 批次 5 详细步骤

#### 步骤 5.1: ADR-051 闭环反馈

1. 创建 `odap/biz/feedback/` 目录
2. 实现 `FeedbackType` 枚举
3. 重构 `FeedbackCollector` 支持多种反馈类型
4. 创建 `tests/unit/test_feedback.py`
5. 运行测试确认通过

#### 步骤 5.2: ADR-011 角色热生效

1. 读取 `odap/biz/roles/api/routes.py`
2. 在角色 CRUD 操作中添加 OPA 策略同步逻辑
3. 编写热生效集成测试
4. 运行测试确认通过

#### 步骤 5.3-5.5: 其他 ADR 验证

1. 验证热插拔 API 端点
2. 验证 Markdown→Rego 前端集成
3. 验证三栏布局和 Skill 管理界面
4. 记录未完成项为后续迭代

### 批次 6 详细步骤

1. 修复 ARCHITECTURE_WEB.md 章节号
2. 更新 ARCHITECTURE.md 行数统计
3. 修复 ARCHITECTURE_BIZ.md f-string 语法
4. 更新模块实现状态矩阵

### 批次 7 详细步骤

1. 启动完整服务栈（Docker Compose）
2. 执行数据摄入端到端测试
3. 执行智能问答端到端测试
4. 执行工作空间隔离端到端测试
5. 执行 OPA 策略端到端测试
6. 记录测试结果

---

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 服务依赖导致测试不稳定 | 高 | 使用 mock 替代 LLM 调用，snapshot 测试 |
| Neo4j 不可用导致图谱测试失败 | 中 | 使用 NetworkX 回退模式测试 |
| 前端组件测试需要 DOM 环境 | 低 | Vitest + jsdom 已配置 |
| OPA 服务不可用 | 中 | 使用 mock OPA 响应 |
| 知识库 RAG 实现需要嵌入模型 | 高 | 使用简单的关键词检索作为 MVP |
| 惰性属性导致测试不稳定 | 高 | 统一使用 PropertyMock patch 属性 |

---

## 六、验收标准

1. **后端单元测试**: 修复所有失败测试，新增 ≥ 30 个测试用例，覆盖所有核心模块
2. **前端组件测试**: 新增 ≥ 20 个测试用例，覆盖核心组件
3. **集成测试**: 修复所有宽松断言，新增完整链路测试
4. **Stub 功能**: knowledge_base RAG 和 Web 爬取功能可用
5. **ADR 补全**: ADR-051 闭环反馈机制实现，ADR-011 热生效联动打通
6. **文档一致性**: 所有已知文档问题修复
7. **端到端验证**: 使用实际数据完成 4 条核心链路验证
8. **测试通过率**: 100%（所有测试用例通过）
9. **代码提交**: 所有变更提交到版本控制
