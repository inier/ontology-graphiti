---
name: tdd-run-pytest
description: 在 ODAP 项目中运行 pytest 测试，解读结果，处理常见错误（导入失败、fixture 错误、asyncio 冲突、SQLite 路径问题）。
compatibility: Requires Python 3.10+ and pytest
metadata:
  author: odap-project
  source: AGENTS.md testing-rules
---

# 运行 pytest 测试

在 ODAP 项目中运行 pytest 测试并解读结果。

## 用户输入

$ARGUMENTS

## 常用命令

### 1. 运行全部单元测试（修改代码后必跑）
```bash
pytest tests/unit/ -v
```

### 2. 运行单个测试文件
```bash
pytest tests/unit/test_agent_management.py -v
```

### 3. 运行单个测试类
```bash
pytest tests/unit/test_agent_management.py::TestSQLiteAgentStorage -v
```

### 4. 运行单个测试方法
```bash
pytest tests/unit/test_agent_management.py::TestSQLiteAgentStorage::test_save_xxx -v
```

### 5. 运行集成测试（需 Neo4j+MongoDB）
```bash
pytest tests/integration/ -v
```

### 6. 按 marker 过滤
```bash
pytest tests/unit/ -v -m unit          # 只跑 unit marker
pytest tests/unit/ -v -m "not slow"     # 排除 slow marker
pytest tests/unit/ -v -m integration    # 只跑 integration
pytest tests/ -v -m e2e                 # 只跑 e2e
```

### 7. 显示详细输出
```bash
pytest tests/unit/test_xxx.py -v -s                # 禁用捕获，显示 print
pytest tests/unit/test_xxx.py -v --tb=short        # 短回溯
pytest tests/unit/test_xxx.py -v --tb=long         # 长回溯
pytest tests/unit/test_xxx.py -v --tb=line         # 单行回溯
```

### 8. 失败时立即停止
```bash
pytest tests/unit/ -v -x           # 第一个失败就停
pytest tests/unit/ -v --maxfail=3  # 3 个失败后停
```

### 9. 覆盖率报告
```bash
pytest tests/unit/ -v --cov=odap --cov-report=term-missing
pytest tests/unit/ -v --cov=odap/biz/management/agent_management --cov-report=html
```

### 10. 重新运行上次失败的测试
```bash
pytest tests/unit/ -v --lf           # last-failed
pytest tests/unit/ -v --ff           # failed-first
```

## 常见错误与诊断

### 错误 1: `ModuleNotFoundError: No module named 'odap'`
**原因**：pytest 未找到项目根目录。
**修复**：
```bash
# 方案 1：在项目根目录运行
cd e:\DEMO\AI\ontology-graphiti
pytest tests/unit/ -v

# 方案 2：设置 PYTHONPATH
$env:PYTHONPATH = "e:\DEMO\AI\ontology-graphiti"
pytest tests/unit/ -v
```

### 错误 2: `ModuleNotFoundError: No module named 'graphiti_core'`
**原因**：外部依赖未安装。
**修复**：
```python
# 测试文件使用 try/except + skip 模式（AGENTS.md 要求）
try:
    from graphiti_core import ...
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False

@pytest.mark.skipif(not GRAPHITI_AVAILABLE, reason="graphiti-core not installed")
def test_graphiti_feature():
    ...
```

### 错误 3: `asyncio.run() cannot be called from a running event loop`
**原因**：在 FastAPI 异步路由中调用了同步方法内的 `asyncio.run()`。
**修复**：
- 路由层用 `run_in_executor` 包装同步方法
- 或在 GraphManager 中用 `_run_async()` 辅助函数（已修复）
- 详见 `odap/infra/graph/graph_service.py`

### 错误 4: `sqlite3.OperationalError: no such table`
**原因**：存储层 `__init__` 中 `_init_db()` 未执行或表名拼写错误。
**诊断**：
```python
def test_init_db(tmp_path):
    db_path = tmp_path / "xxx.db"
    SQLiteXxxStorage(db_path=str(db_path))
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    print(f"Tables: {tables}")
    conn.close()
```

### 错误 5: `MagicMock` 影响真实 DB 行为
**原因**：存储层测试用了 `MagicMock` 模拟数据库。
**修复**（AGENTS.md 强制）：
- 存储层**必须**用 `tmp_path` fixture 真实 DB
- 非存储层可以用 `MagicMock` Mock Storage 类

### 错误 6: `Pydantic ValidationError: ... default ... is mutable`
**原因**：容器字段用了 `= []` 或 `= {}`。
**修复**：
```python
# ❌ 错误
class Xxx(BaseModel):
    tags: List[str] = []

# ✅ 正确
class Xxx(BaseModel):
    tags: List[str] = Field(default_factory=list)
```

### 错误 7: `HTTPException` 被 500 吞掉
**原因**：路由缺少 `except HTTPException: raise`。
**诊断**：测试中显式验证
```python
def test_http_exception_propagates():
    with pytest.raises(HTTPException) as exc_info:
        client.get("/api/xxx/missing")
    assert exc_info.value.status_code == 404
```
**修复**：
```python
@router.get("/{id}")
async def get_xxx(id: str):
    try:
        ...
    except HTTPException:
        raise  # 必须透传
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 输出解读

### 全部通过 ✅
```
tests/unit/test_xxx.py::TestXxx::test_foo PASSED                      [100%]
========== 1 passed in 0.05s ==========
```

### 失败 ❌
```
tests/unit/test_xxx.py::TestXxx::test_foo FAILED                      [100%>
__________ TestXxx.test_foo __________
    def test_foo():
>       assert result["status"] == "success"
E       AssertionError: assert 'error' == 'success'
E        +  where 'error' = result['status']
========== short test summary info ==========
FAILED tests/unit/test_xxx.py::TestXxx::test_foo - AssertionError
========== 1 failed in 0.10s ==========
```

### 跳过 ⏭️
```
tests/unit/test_xxx.py::TestXxx::test_graphiti SKIPPED                [100%]
```
**原因**：依赖未安装（`graphiti-core` 等），符合 AGENTS.md 规范。

## ODAP 测试命令速查

```bash
# 单元测试（最常用）
pytest tests/unit/ -v

# 集成测试（需 Neo4j+MongoDB）
pytest tests/integration/ -v

# E2E 测试
pytest tests/e2e/ -v

# 性能测试
pytest tests/perf/ -v

# 全部测试
pytest tests/ -v

# 覆盖率
pytest tests/unit/ -v --cov=odap --cov-report=term-missing

# 失败重跑
pytest tests/unit/ -v --lf
```

## 输出总结

向用户报告：
- 运行的测试文件/测试数
- 通过/失败/跳过数量
- 失败原因（如果是失败）
- 修复建议（如果是失败）
- 下一步行动
