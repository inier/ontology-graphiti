# 文档核实与功能补全实施计划 v3.0

> **创建日期**: 2026-05-21
> **目标**: 分批次核实 docs 中的架构文档、设计文档和 ADR 是否完整实现，补全缺失功能，补齐测试用例，最终提交代码

---

## 一、当前状态总结

### 已完成的工作（上一轮会话）

1. ✅ 修复决策管道测试（PropertyMock 方案）
2. ✅ 修复动作服务测试（PropertyMock + patch 路径修正）
3. ✅ 修复 HealthStatus 枚举 AttributeError（str+Enum 继承）
4. ✅ 修复工具注册表测试（HealthStatus mock + 工具链输入映射）

### 待完成的工作

| 批次 | 内容 | 优先级 | 状态 |
|------|------|--------|------|
| 批次1 | 后端单元测试补齐（12个无测试模块） | P0 | 待开始 |
| 批次2 | 后端集成测试强化（81处松散断言+新增链路测试） | P0 | 待开始 |
| 批次3 | 后端Stub功能实现（RAG/Web爬取/图谱构建） | P1 | 待开始 |
| 批次4 | 前端组件测试补齐 | P0 | 待开始 |
| 批次5 | ADR未实现功能补全（ADR-051/ADR-011） | P1 | 待开始 |
| 批次6 | 架构文档修复 | P2 | 待开始 |
| 批次7 | 实际数据端到端测试 | P0 | 待开始 |

### 关键缺口数据

- **后端模块测试覆盖率**: 9/24 模块有正式测试（37.5%）
- **集成测试松散断言**: 81处 `assert status_code in [...]` 模式
- **前端测试**: 0个组件渲染测试（仅2个导出验证+API mock测试）
- **Stub端点**: 3个（rag_query、crawl_web、build_graph）
- **ADR实现差距**: ADR-051(40%)、ADR-011(45%)

---

## 二、分批次实施计划

### 批次1: 后端单元测试补齐（P0）

**目标**: 为12个无测试的核心后端模块补齐单元测试

#### 1.1 无测试模块清单（按优先级排序）

| 优先级 | 模块 | 核心类 | 测试文件 |
|--------|------|--------|----------|
| P0 | `agent` | AgentRouterV2, SelfCorrectingOrchestratorV2, DomainSwarm | `tests/unit/test_agent.py` |
| P0 | `workspace` | WorkspaceManager, IsolationManager | `tests/unit/test_workspace.py` |
| P0 | `skill_system` | SkillManager, HotplugManager, SkillOrchestrator | `tests/unit/test_skill_system.py` |
| P1 | `knowledge_base` | KnowledgeBaseStorage + 3个stub端点 | `tests/unit/test_knowledge_base.py` |
| P1 | `qa` | QAEngineV2, DialogManager, RAGPipeline | `tests/unit/test_qa_engine.py` |
| P1 | `roles` | RoleStorage, 角色CRUD | `tests/unit/test_roles.py` |
| P1 | `hook_system` | EnhancedHookManager, SecuritySandbox | `tests/unit/test_hook_system.py` |
| P2 | `simulation_sandbox` | SimulationSandbox | `tests/unit/test_simulation_sandbox.py` |
| P2 | `mcp_adapter` | MCPServerManagerV2, ConnectionPool | `tests/unit/test_mcp_adapter.py` |
| P2 | `visualization` | VisualizationEngineV2, GraphLayoutEngine | `tests/unit/test_visualization.py` |
| P2 | `business` | BusinessStorage, CRUD | `tests/unit/test_business.py` |
| P2 | `event_simulator` | EventSimulatorService | `tests/unit/test_event_simulator.py` |

#### 1.2 每个模块测试内容要求

- **核心类初始化测试**: 验证构造函数和默认属性
- **核心方法测试**: 每个公开方法至少1个正向+1个边界用例
- **异步接口测试**: 使用 `pytest-asyncio` 的 `async def test_` 模式
- **Mock外部依赖**: GraphManager、LLM、OPA 等通过 PropertyMock 或 patch 隔离
- **最小测试用例数**: 每模块 ≥ 8个

#### 1.3 实施步骤

1. 读取目标模块源码，识别核心类和公开方法
2. 创建测试文件，导入目标类
3. 编写 fixture（Mock 外部依赖）
4. 编写测试用例（初始化 → 核心方法 → 边界情况）
5. 运行 `pytest tests/unit/test_{module}.py -v` 确认通过
6. 重复上述步骤直到所有12个模块完成

**验收标准**: 所有后端单元测试通过，新增 ≥ 96 个测试用例（12模块 × 8用例）

---

### 批次2: 后端集成测试强化（P0）

**目标**: 修复81处松散断言，新增完整链路集成测试

#### 2.1 修复 `test_api_integration.py` 松散断言

**策略**: 按严重程度分4轮修复

**第1轮 - 极度松散（4处）**: 修复5状态码断言
- 行621: 空摄入数据 → `assert status_code in [422, 400]`
- 行630: 畸形JSON → `assert status_code in [422, 400]`
- 行636: 缺少必填字段 → `assert status_code in [422, 400]`
- 行647: 大数据量请求 → `assert status_code in [200, 201]`

**第2轮 - 严重松散（17处）**: 修复4状态码断言
- 写操作（POST/PUT）→ 期望 `200/201`，移除 `404/500`
- 读操作（GET）→ 区分"数据存在200"和"数据不存在404"两种场景分别测试

**第3轮 - 中度松散（19处）**: 修复3状态码断言
- 移除 `500`（服务崩溃不应通过测试）
- 区分正常和异常场景

**第4轮 - 轻度松散（41处）**: 修复2状态码断言 `[200, 404]`
- 对于CRUD操作，创建后应返回200/201
- 查询不存在的资源应单独测试返回404

**附加修复**:
- 行116: `data.get("status") in ["created", "ok", "success"]` → 精确断言
- 行124: `"scenarios" in data or isinstance(data, list)` → 统一响应格式验证
- 行252: 三重OR断言 → 精确字段验证
- 增加响应体结构验证（关键字段存在性、数据类型）

#### 2.2 新增数据摄入完整流程测试

**文件**: `tests/integration/test_ingest_pipeline.py`（新建）

测试用例:
1. 文本摄入 → 本体构建 → 版本快照完整链路
2. 新闻摄入 → 实体抽取 → 关系识别
3. JSON摄入 → Schema验证 → 写入图谱
4. 摄入失败回滚验证

#### 2.3 新增OADP闭环集成测试

**文件**: `tests/integration/test_oadp_loop.py`（新建）

测试用例:
1. 感知 → 理解 → 决策 → 执行完整闭环
2. 反馈收集 → 分析 → 聚合
3. 工作空间隔离下的闭环执行

**验收标准**: 0处松散断言，新增 ≥ 20个集成测试用例

---

### 批次3: 后端Stub功能实现（P1）

**目标**: 实现知识库3个stub端点的实际功能

#### 3.1 知识库RAG查询实现

**文件**: `odap/biz/knowledge_base/api/routes.py` — 修改 `rag_query` 端点

**实现方案（MVP - 关键词检索）**:
1. 定义 `RAGQueryRequest` schema（query, top_k, threshold）
2. 从 SQLiteKnowledgeBaseStorage 检索知识库文档
3. 对文档内容进行关键词匹配，提取相关片段
4. 如 LLM 服务可用，调用 LLM 生成答案；否则返回关键词匹配结果
5. 返回答案 + 来源文档 + 相关实体

```python
class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    threshold: float = 0.3

@router.post("/{kb_id}/rag-query")
async def rag_query(kb_id: str, request: RAGQueryRequest):
    storage = SQLiteKnowledgeBaseStorage()
    kb = storage.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    docs = storage.list_documents(kb_id)
    # 关键词匹配
    keywords = set(request.query.lower().split())
    scored = []
    for doc in docs:
        if doc.content:
            content_lower = doc.content.lower()
            score = sum(1 for kw in keywords if kw in content_lower) / max(len(keywords), 1)
            if score >= request.threshold:
                scored.append((doc, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    top_docs = scored[:request.top_k]
    sources = [{"doc_id": d.id, "title": d.title, "score": s} for d, s in top_docs]
    # 尝试LLM生成答案
    answer = await _generate_answer_with_llm(request.query, top_docs)
    return {"answer": answer, "sources": sources, "related_entities": []}
```

#### 3.2 知识库Web爬取实现

**文件**: `odap/biz/knowledge_base/api/routes.py` — 修改 `crawl_web` 端点

**实现方案**:
1. 定义 `CrawlRequest` schema（urls, max_depth）
2. 使用 `odap/utils/web_scraper.py` 已有的爬取工具
3. URL爬取 → HTML解析 → 文本清洗 → 入库
4. 返回任务ID和状态

```python
class CrawlRequest(BaseModel):
    urls: list[str]
    max_depth: int = 1

@router.post("/{kb_id}/crawl")
async def crawl_web(kb_id: str, request: CrawlRequest):
    storage = SQLiteKnowledgeBaseStorage()
    kb = storage.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    results = []
    for url in request.urls:
        try:
            from odap.utils.web_scraper import WebScraper
            scraper = WebScraper()
            content = await scraper.scrape(url)
            doc_id = storage.add_document(kb_id, title=url, content=content)
            results.append({"url": url, "doc_id": doc_id, "status": "success"})
        except Exception as e:
            results.append({"url": url, "status": "failed", "error": str(e)})
    return {"task_id": f"crawl_{kb_id}", "results": results}
```

#### 3.3 知识库图谱构建实现

**文件**: `odap/biz/knowledge_base/api/routes.py` — 修改 `build_graph` 端点

**实现方案**:
1. 从文档中提取实体和关系（使用LLM或规则）
2. 调用 GraphManager 写入图谱
3. 返回任务状态

#### 3.4 补充知识库测试

**文件**: `tests/unit/test_knowledge_base.py`（新建）

测试用例:
1. RAG查询 - 关键词匹配
2. RAG查询 - 知识库不存在
3. Web爬取 - 单URL
4. Web爬取 - 多URL含失败
5. 图谱构建 - 正常流程
6. 图谱构建 - 文档不存在

**验收标准**: 3个stub端点返回真实数据，知识库功能可用

---

### 批次4: 前端组件测试补齐（P0）

**目标**: 为核心前端组件添加渲染和交互测试

#### 4.1 测试基础设施确认

已有配置:
- Vitest 3.0 + jsdom + @testing-library/react 16.1 + @testing-library/jest-dom 6.6
- setup.ts: mock fetch + mock @/config
- 路径别名: `@` → `./src`

需确认:
- Ant Design 组件在 jsdom 下的渲染行为
- G6/ECharts mock 配置
- Zustand store 测试模式

#### 4.2 测试文件规划

| 测试文件 | 测试组件 | 测试内容 |
|----------|----------|----------|
| `src/modules/shared/components/__tests__/AppLayout.test.tsx` | AppLayout | 渲染布局、工作空间切换 |
| `src/modules/shared/components/__tests__/QAPanel.test.tsx` | QAPanel | 消息渲染、输入发送 |
| `src/modules/shared/components/__tests__/StatCard.test.tsx` | StatCard | 数据展示 |
| `src/modules/ontology/components/__tests__/GraphCanvas.test.tsx` | GraphCanvas | G6图谱渲染（mock G6） |
| `src/modules/ontology/components/__tests__/ActionPanel.test.tsx` | ActionPanel | 动作面板交互 |
| `src/modules/qa/__tests__/useQAI.test.ts` | useQAI Hook | 流式问答、SSE解析 |
| `src/modules/workspace/__tests__/WorkspaceSwitcher.test.tsx` | WorkspaceSwitcher | 工作空间切换 |

#### 4.3 实施步骤

1. 确认测试基础设施可用（`npm run test` 通过）
2. 创建 G6/ECharts mock 配置
3. 为每个组件编写渲染测试
4. 为交互组件编写用户交互测试
5. 为 Hook 编写状态变更测试
6. 运行 `npm run test` 确认全部通过

**验收标准**: 新增 ≥ 20个前端组件测试用例，`npm run test` 通过

---

### 批次5: ADR未实现功能补全（P1）

**目标**: 补全 ADR-051 闭环反馈和 ADR-011 角色热生效

#### 5.1 ADR-051 闭环反馈机制补全

**当前状态**: `odap/biz/action_service/feedback_loop.py` 已有基础实现（FeedbackCollector/Analyzer/Aggregator/Loop），但仅支持 `action_result` 一种反馈类型，缺少独立模块和多种反馈类型支持。

**需补全**:

1. **创建 `odap/biz/feedback/` 独立模块目录**
   - `__init__.py` — 模块初始化
   - `models.py` — 扩展反馈模型（4种FeedbackType + 通用Feedback模型）
   - `collector.py` — 增强FeedbackCollector（支持4种反馈类型 + 查询历史）
   - `analyzer.py` — 增强FeedbackAnalyzer（偏差分析 + 模式识别）
   - `aggregator.py` — 增强FeedbackAggregator（图谱更新 + 事件创建）
   - `loop.py` — FeedbackLoop闭环管理器（编排完整流程）

2. **扩展反馈类型**
   ```python
   class FeedbackType(str, Enum):
       ACTION_RESULT = "action_result"
       DECISION_FEEDBACK = "decision_feedback"
       OUTCOME_DEVIATION = "outcome_deviation"
       LESSON_LEARNED = "lesson_learned"
   ```

3. **保持向后兼容**: `action_service/feedback_loop.py` 继续工作，新模块提供增强功能

4. **补充闭环反馈测试**: `tests/unit/test_feedback.py`

#### 5.2 ADR-011 角色配置热生效补全

**当前状态**: `odap/biz/roles/api/routes.py` 有完整的角色CRUD，但缺少角色变更 → OPA策略重载的联动机制。

**需补全**:

1. **在角色CRUD API中添加OPA策略同步逻辑**
   - 创建/更新角色时，自动将角色权限转换为OPA策略
   - 删除角色时，自动删除对应的OPA策略
   - 通过 `odap/infra/opa/` 模块调用OPA API重载策略

2. **实现热生效流程**:
   ```
   角色变更 → 生成Rego策略 → 推送到OPA → OPA热加载 → 新权限即时生效
   ```

3. **编写热生效集成测试**: 验证角色变更后权限即时更新

**验收标准**: ADR-051闭环反馈4种类型全部实现，ADR-011角色变更触发OPA策略重载

---

### 批次6: 架构文档修复（P2）

**目标**: 修复文档中的已知问题，确保文档与代码一致

#### 6.1 修复项清单

| 文件 | 问题 | 修复方案 |
|------|------|----------|
| `ARCHITECTURE_WEB.md` | §11.5.1 应为 §11.6.1 | 修正章节号 |
| `ARCHITECTURE.md` | 子文档行数统计不准确 | 重新统计并更新 |
| `ARCHITECTURE_BIZ.md` | f-string引号转义错误 | 修复代码示例 |
| 架构审查报告 | 模块实现状态矩阵需更新 | 更新为当前实现状态 |

**验收标准**: 所有已知文档问题修复，状态矩阵与代码一致

---

### 批次7: 实际数据端到端测试（P0）

**目标**: 使用实际数据验证完整功能链路

#### 7.1 测试场景

| 场景 | 测试内容 | 验证点 |
|------|----------|--------|
| 数据摄入E2E | 真实新闻文本摄入 | 文本→实体抽取→关系识别→本体构建→版本快照 |
| 智能问答E2E | 基于已摄入数据问答 | 意图识别→上下文检索→流式回答 |
| 工作空间隔离E2E | 多工作空间数据隔离 | 切换空间后数据正确隔离 |
| OPA策略E2E | Markdown策略→Rego→权限校验 | 高危操作被正确拦截 |

#### 7.2 实施方式

- 使用 Docker Compose 启动完整服务栈
- 通过 API 调用执行端到端测试
- 验证前端界面可正常操作

**验收标准**: 4条核心链路全部通过端到端验证

---

## 三、实施顺序与依赖关系

```
批次1 (后端测试补齐) ──→ 批次2 (集成测试强化) ──→ 批次7 (端到端测试)
                                                            ↓
批次3 (Stub实现)     ────────────────────────────────→ 批次7
                                                            ↓
批次4 (前端组件测试) ────────────────────────────────→ 批次7
                                                            ↓
批次5 (ADR功能补全) ──→ 批次6 (文档修复) ──────────→ 批次7
```

**推荐执行顺序**: 1 → 2 → 3 → 4 → 5 → 6 → 7

---

## 四、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM服务依赖导致测试不稳定 | 高 | 使用mock替代LLM调用 |
| Neo4j不可用导致图谱测试失败 | 中 | 使用NetworkX回退模式测试 |
| 前端组件测试需要DOM环境 | 低 | Vitest + jsdom已配置 |
| OPA服务不可用 | 中 | 使用mock OPA响应 |
| 知识库RAG实现需要嵌入模型 | 高 | 使用关键词检索作为MVP |
| 惰性属性导致测试不稳定 | 高 | 统一使用PropertyMock |
| Docker环境不一致 | 中 | 使用bootstep.py统一管理 |

---

## 五、验收标准

1. **后端单元测试**: 新增 ≥ 96个测试用例，覆盖所有核心模块，全部通过
2. **集成测试**: 0处松散断言，新增 ≥ 20个链路测试
3. **前端组件测试**: 新增 ≥ 20个测试用例，覆盖核心组件
4. **Stub功能**: knowledge_base RAG/Web爬取/图谱构建功能可用
5. **ADR补全**: ADR-051闭环反馈4种类型实现，ADR-011热生效联动打通
6. **文档一致性**: 所有已知文档问题修复
7. **端到端验证**: 4条核心链路全部通过
8. **代码提交**: 所有变更提交到版本控制
