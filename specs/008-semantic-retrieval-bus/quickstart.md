# Quickstart: Semantic Retrieval Service Bus

**Feature**: 008-semantic-retrieval-bus
**Date**: 2026-07-30

> 本指南说明如何启动、调用和测试语义检索服务总线。当前处于规划阶段，以下为设计完成后的预期使用方式。

## 前置条件

1. ODAP 开发环境已启动（前端 http://localhost:5173，后端 http://localhost:8000）
2. Neo4j + SQLite 存储正常运行
3. 已通过认证获取 JWT token（`workspace_id` 包含在 JWT payload 中）
4. 本体中已有 ObjectType/RelationType 定义和实例数据

## 启动服务

语义检索服务作为现有 ODAP 单体应用的一部分，无需独立启动。后端 `uvicorn --reload` 会自动加载新模块路由。

```bash
# 后端开发模式（已在项目中配置）
python bootstep.py dev
```

路由注册后，访问 `http://localhost:8000/docs` 查看 `/api/semantic-retrieval/*` 端点文档。

## 快速调用示例

### 1. 统一检索（自动路由）

```bash
curl -X POST http://localhost:8000/api/semantic-retrieval/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "readiness 低于 0.6 的装备有哪些",
    "mode": "auto",
    "page": 1,
    "page_size": 20
  }'
```

### 2. BI 指标查询

```bash
curl -X POST http://localhost:8000/api/semantic-retrieval/metric \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "metric",
    "mode": "metric",
    "filters": {
      "metric_type": "trend",
      "target": "object_type",
      "target_filter": "装备",
      "granularity": "day"
    }
  }'
```

### 3. 自然语言查询（含 USL 术语消歧）

```bash
curl -X POST http://localhost:8000/api/semantic-retrieval/nl \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "低 readiness 装备部署在哪些平台上"
  }'
```

> "平台" 会通过 USL `get_domain_by_term` 自动映射为 ObjectType "系统"。

## 测试

### 运行单元测试

```bash
# 全部语义检索单元测试
pytest tests/unit/test_unified_router.py tests/unit/test_graph_engine.py \
         tests/unit/test_metric_engine.py tests/unit/test_nl_engine.py -v

# 循环检测（安全关键）
pytest tests/unit/test_chain_cycle_detection.py -v

# 混合编排容错
pytest tests/unit/test_hybrid_orchestrator.py -v
```

### 运行集成测试

```bash
# 路由端到端（含认证、workspace 隔离、审计）
pytest tests/integration/test_semantic_retrieval_routes.py -v
```

### 路由异常处理回归（G-7）

```bash
pytest tests/unit/test_route_exception_handling.py -q
```

### 全量回归（G-10）

```bash
pytest tests/unit/ -q
```

## TDD 开发流程

本特性严格遵循 TDD（Constitution III）。每个引擎按 Red-Green-Refactor 推进：

1. **Red**: 先写测试（如 `test_unified_router.py` 验证 NL 输入路由到 nl 引擎）
2. **Green**: 最小实现使测试通过
3. **Refactor**: 提取共享逻辑，保持函数 ≤ 40 行

## Phase 交付验证

| Phase | 验证命令 | 预期 |
|-------|---------|------|
| Phase 1 | `pytest tests/unit/test_{unified_router,graph_engine,metric_engine,nl_engine}.py` | 全绿，覆盖 P1 故事 |
| Phase 2 | `pytest tests/unit/test_chain_cycle_detection.py` | 循环检测 + 规则冲突通过 |
| Phase 3 | `pytest tests/unit/test_hybrid_orchestrator.py` + MCP 集成验证 | 容错策略 + MCP 工具调用通过 |

## 常见问题

**Q: 查询返回空结果？**
A: 检查 `valid=false`/`USL__Candidate` 默认过滤（FR-011）。若需查看推演/候选数据，显式传 `include_simulated=true` 或 `include_candidates=true`。

**Q: NL 查询术语未映射？**
A: 确认 USL 术语映射已配置（`get_domain_by_term`）。未映射的术语会原样传递，`warnings` 中会有提示。

**Q: 跨 workspace 查询报 403？**
A: `workspace_id` 从 JWT 提取，不可跨 workspace 查询（FR-012）。如需跨 workspace，需切换对应 workspace 的 token。

**Q: 审计日志在哪里看？**
A: 审计通过 `storage_audit` 写入现有审计表，`service="semantic_retrieval"`。仅记录操作类型/结果数/耗时，不记录查询内容（FR-013）。
