---
name: tdd-write-test-first
description: 在 ODAP 项目中为新增模块/函数编写测试用例。严格遵循 AGENTS.md 测试规则：新增模块必须测试、SQLite 用 tmp_path 真实 DB、HTTPException 透传、Docker 镜像用 conftest 真实构建。
compatibility: Requires pytest
metadata:
  author: odap-project
  source: AGENTS.md testing-rules
---

# TDD 先写测试

在 ODAP 项目中**先**为新代码编写测试用例，**再**实现功能。

## 适用场景

- 新增 biz 模块（按 AGENTS.md "新增模块必须同步新增测试文件"，**不允许零测试提交**）
- 新增 SQLite 存储层方法
- 新增 FastAPI 路由
- 新增服务层方法
- 新增 Pydantic 模型字段

## 用户输入

$ARGUMENTS

## Step 1: 定位目标

1. 识别要测试的代码路径：
   - 业务模块：`odap/biz/{领域}/{模块名}/{层}/{文件}.py`
   - 基础设施：`odap/infra/{模块}/{文件}.py`
2. 确定测试文件目标路径：
   - 单元测试：`tests/unit/test_{module}.py`（文件名与模块名对应）
   - 集成测试：`tests/integration/test_{module}.py`（需外部依赖）

## Step 2: 选择测试模式（按 AGENTS.md 规范）

### Fixture 级联模式
```python
@pytest.fixture
def mock_storage():
    """Mock 存储层（用于非存储层测试）"""
    with patch("odap.xxx.storage.Storage") as mock:
        yield mock

@pytest.fixture
def xxx_service(mock_storage):
    """服务层 fixture，依赖 mock_storage"""
    return XxxService()
```

### 工厂函数模式
```python
def _make_xxx(**overrides) -> Dict[str, Any]:
    """构造测试数据，默认值 + 覆盖"""
    data = {
        "id": "test-001",
        "name": "Test Xxx",
        "tags": [],
        "created_at": "2026-01-01T00:00:00",
    }
    data.update(overrides)
    return data
```

### 真实 SQLite 模式（**存储层必须**）
```python
def test_storage_crud(tmp_path):
    """SQLite 存储层用真实临时 DB，不用 MagicMock 模拟"""
    db_path = tmp_path / "xxx.db"
    storage = SQLiteXxxStorage(db_path=str(db_path))

    # 测试 CRUD 全流程
    storage.save_xxx(_make_xxx())
    result = storage.get_xxx("test-001")
    assert result is not None
    assert result["name"] == "Test Xxx"
```

## Step 3: 按层编写测试（AGENTS.md 强制要求）

| 层 | 必须覆盖的场景 |
|---|---------|
| **storage/** | CRUD 全流程、get 不存在返回 None、delete 不存在返回 False、JSON 字段序列化/反序列化、非法 JSON 容错 |
| **models/** | 必填字段验证、默认值、容器字段 `default_factory`、Enum 值 |
| **services/** | 成功返回扁平 dict、错误返回 `{"status": "error"}`、类型转换 (Enum→.value, datetime→.isoformat) |
| **routes/** | HTTP 状态码映射、`except HTTPException: raise` 透传、404/400/500 场景 |

### 测试类组织（按层分组）
```python
class TestSQLiteXxxStorage:
    """存储层测试（真实 DB）"""

    def test_init_creates_table(self, tmp_path):
        ...

    def test_save_and_get(self, tmp_path):
        ...

    def test_get_not_found_returns_none(self, tmp_path):
        ...

    def test_delete_not_found_returns_false(self, tmp_path):
        ...


class TestXxxService:
    """服务层测试（Mock 存储）"""

    def test_get_xxx_success(self, xxx_service, mock_storage):
        ...

    def test_get_xxx_not_found(self, xxx_service, mock_storage):
        ...


class TestXxxRoutes:
    """路由层测试（TestClient）"""

    def test_get_xxx_returns_200(self, client):
        ...

    def test_get_xxx_not_found_returns_404(self, client):
        ...
```

## Step 4: 编写具体测试

### 存储层测试模板
```python
import pytest
import json
from odap.biz.xxx.storage.sqlite_xxx_storage import SQLiteXxxStorage


class TestSQLiteXxxStorage:

    def test_init_db_creates_table(self, tmp_path):
        db_path = tmp_path / "xxx.db"
        SQLiteXxxStorage(db_path=str(db_path))
        # 验证表存在
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='xxxs'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_save_xxx_upsert(self, tmp_path):
        storage = SQLiteXxxStorage(db_path=str(tmp_path / "xxx.db"))
        storage.save_xxx(_make_xxx())
        # 修改后再次 save 应 upsert
        storage.save_xxx(_make_xxx(name="Updated"))
        result = storage.get_xxx("test-001")
        assert result["name"] == "Updated"

    def test_list_xxxs_with_pagination(self, tmp_path):
        storage = SQLiteXxxStorage(db_path=str(tmp_path / "xxx.db"))
        for i in range(15):
            storage.save_xxx(_make_xxx(id=f"test-{i:03d}"))
        result = storage.list_xxxs(page=2, page_size=10)
        assert len(result) == 5  # 15-10=5

    def test_json_field_roundtrip(self, tmp_path):
        storage = SQLiteXxxStorage(db_path=str(tmp_path / "xxx.db"))
        storage.save_xxx(_make_xxx(tags=["a", "b", "c"]))
        result = storage.get_xxx("test-001")
        assert result["tags"] == ["a", "b", "c"]

    def test_invalid_json_returns_default(self, tmp_path):
        # 直接写入非法 JSON 验证容错
        ...
```

### 服务层测试模板
```python
from unittest.mock import patch, MagicMock


class TestXxxService:

    def test_get_xxx_success(self):
        with patch("odap.biz.xxx.api.routes.storage") as mock_storage:
            mock_storage.get_xxx.return_value = _make_xxx()
            result = XxxService().get_xxx("test-001")
            assert result["status"] == "success"
            assert result["xxx_id"] == "test-001"

    def test_get_xxx_not_found(self):
        with patch("odap.biz.xxx.api.routes.storage") as mock_storage:
            mock_storage.get_xxx.return_value = None
            result = XxxService().get_xxx("nonexistent")
            assert result["status"] == "error"
            assert "not found" in result["message"].lower()

    def test_enum_value_converted_to_string(self):
        with patch("odap.biz.xxx.api.routes.storage") as mock_storage:
            mock_storage.get_xxx.return_value = _make_xxx(status="active")
            result = XxxService().get_xxx("test-001")
            assert result["status"] == "active"  # 不是 XxxStatus.ACTIVE

    def test_datetime_converted_to_isoformat(self):
        # 验证 datetime 字段被转为 ISO 字符串
        ...
```

### 路由层测试模板
```python
from fastapi.testclient import TestClient
import pytest


class TestXxxRoutes:

    def test_get_xxx_returns_200(self):
        # 使用 TestClient
        ...

    def test_get_xxx_not_found_returns_404(self):
        ...

    def test_http_exception_propagates(self):
        """验证 except HTTPException: raise 透传，未被 500 吞掉"""
        ...

    def test_validation_error_returns_400(self):
        ...

    def test_create_xxx_success(self):
        ...
```

## Step 5: 运行测试确认失败

```bash
# 单元测试
pytest tests/unit/test_xxx.py -v

# 单个测试
pytest tests/unit/test_xxx.py::TestXxxService::test_get_xxx_success -v
```

确认：
- 导入失败 → 正常（模块还未实现）
- 测试失败 → 正常（功能未实现）
- **绝对不能跳过这一步**

## 关键 ODAP 测试约束

| 约束 | 说明 |
|------|------|
| **存储层用真实 DB** | `tmp_path` fixture 创建 `.db` 文件，不用 MagicMock |
| **非存储层用 Mock** | `patch()` 替换 Storage 类 |
| **延迟导入** | fixture 内部 `from odap.xxx import`，避免模块级导入失败 |
| **外部依赖 skip** | 依赖 graphiti-core/openharness 的测试，模块级 `try/except` + `pytest.skip()` |
| **HTTPException 透传** | 路由测试必须验证 `except HTTPException: raise` |
| **类型转换测试** | 服务层必须测试 Enum→.value、datetime→.isoformat 转换 |

## 完成检查

- [ ] 测试文件已创建在 `tests/unit/test_{module}.py`
- [ ] 存储层用 `tmp_path` 真实 DB
- [ ] 服务层用 `patch()` Mock Storage
- [ ] 路由层用 TestClient 测试 HTTP 状态码
- [ ] 覆盖了所有强制测试点（CRUD/None/False/JSON/类型转换/状态码/透传）
- [ ] 测试确认失败（Red 阶段）

## 下一步

调用 `tdd-red-green-refactor` 进入 Green 阶段实现功能。
