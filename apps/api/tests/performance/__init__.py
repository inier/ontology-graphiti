"""Performance benchmark tests for 008 semantic retrieval (SC-001 / SC-002).

运行方式：
  pytest -m perf apps/api/tests/performance/

框架验证模式：
  当前在空/降级 Neo4j 上运行，验证框架可用性 + P95 断言逻辑。
  真实 SC 验收需 10k 节点 Neo4j 测试集 + 100 并发压测（Phase 7+ 生产环境验证）。
"""
