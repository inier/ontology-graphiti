---
name: biz-module-scaffold
description: 在 ODAP 项目中按 AGENTS.md 规范的 6 层结构快速创建新 biz 模块（api/services/impl/interfaces/models/storage），自动生成所有必需文件并保持分层调用关系。
compatibility: Requires Python 3.10+ and Pydantic v2
metadata:
  author: odap-project
  source: AGENTS.md biz-module-structure
---

# Biz 模块脚手架

按 ODAP AGENTS.md 第 1 节规定的 **6 层结构** 快速创建新 biz 模块。

## 适用场景

- 新增业务模块到 `odap/biz/{领域}/{模块名}/`
- 包含 CRUD 业务逻辑
- 需要持久化（SQLite）
- 需要 HTTP API（FastAPI）

## 用户输入

```
$ARGUMENTS
```

格式：`<领域> <模块名> [简单描述]`

示例：
- `core ontology_extractor 抽取领域本体`
- `management audit_logger 审计日志`
- `data ingest_validator 摄取校验`

## ODAP 7 大业务领域

| 领域 | 路径 | 职责 |
|------|------|------|
| core | `odap/biz/core/` | ontology + cognition + agent |
| decision | `odap/biz/decision/` | action_service + decision_pipeline + decision_recommendation |
| integration | `odap/biz/integration/` | openharness_agent + mcp_adapter + hook_system + frontend_compat |
| platform | `odap/biz/platform/` | workspace + roles + skill_system + tool_registry + session_memory |
| data | `odap/biz/data/` | data_warehouse + knowledge_base + perception + qa |
| simulation | `odap/biz/simulation/` | event_simulator + simulation_sandbox + feedback + visualization |
| management | `odap/biz/management/` | agent_management + business |

## 生成的目录结构

```
odap/biz/{domain}/{module_name}/
├── __init__.py
├── api/
│   ├── __init__.py
│   ├── routes.py          # FastAPI 路由
│   └── schemas.py         # 请求/响应 Pydantic 模型
├── models/
│   ├── __init__.py
│   └── {module_name}.py   # 领域模型
├── interfaces/
│   ├── __init__.py
│   └── {module_name}.py   # 抽象基类 (ABC)
├── impl/
│   ├── __init__.py
│   └── {module_name}.py   # 接口实现（核心逻辑）
├── services/
│   ├── __init__.py
│   └── {module_name}_service.py  # 编排层
└── storage/
    ├── __init__.py        # 导出 Storage = SQLiteXxxStorage 别名
    └── sqlite_{module_name}_storage.py

tests/unit/test_{module_name}.py
```

## 调用链（必须遵守）

```
routes.py → services/ → impl/ → storage/
```

**禁止**跨层调用！

## 生成内容

### 1. `odap/biz/{domain}/{module_name}/__init__.py`
```python
"""<模块名> 业务模块"""
from .api.routes import router

__all__ = ["router"]
```

### 2. `odap/biz/{domain}/{module_name}/api/__init__.py`
```python
"""API 路由层"""
```

### 3. `odap/biz/{domain}/{module_name}/api/schemas.py`
```python
"""Pydantic 请求/响应模型"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class {ModuleName}Status(str, Enum):
    """状态枚举（必须 (str, Enum) 双继承）"""
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


class {ModuleName}Create(BaseModel):
    """创建请求模型"""
    name: str = Field(..., min_length=1, max_length=50)
    description: str = ""
    tags: List[str] = Field(default_factory=list)


class {ModuleName}Update(BaseModel):
    """更新请求模型（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    status: Optional[{ModuleName}Status] = None
    tags: Optional[List[str]] = None


class {ModuleName}(BaseModel):
    """响应模型"""
    id: str
    name: str
    description: str
    status: {ModuleName}Status = {ModuleName}Status.DRAFT
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
```

### 4. `odap/biz/{domain}/{module_name}/api/routes.py`
```python
"""FastAPI 路由层"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from .schemas import {ModuleName}, {ModuleName}Create, {ModuleName}Update
from ..services.{module_name}_service import {ModuleName}Service

router = APIRouter(prefix="/api/{module_name}", tags=["{module_name}"])

# 模块级单例
service = {ModuleName}Service()


@router.get("", response_model=List[{ModuleName}])
async def list_{module_name}s(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        return service.list_{module_name}s(page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{{id}}", response_model={ModuleName})
async def get_{module_name}(id: str):
    try:
        result = service.get_{module_name}(id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model={ModuleName})
async def create_{module_name}(request: {ModuleName}Create):
    try:
        return service.create_{module_name}(request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{{id}}", response_model={ModuleName})
async def update_{module_name}(id: str, request: {ModuleName}Update):
    try:
        data = request.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="无更新数据")
        result = service.update_{module_name}(id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{{id}}")
async def delete_{module_name}(id: str):
    try:
        result = service.delete_{module_name}(id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 5. `odap/biz/{domain}/{module_name}/models/__init__.py`
```python
"""领域模型层"""
```

### 6. `odap/biz/{domain}/{module_name}/models/{module_name}.py`
```python
"""{ModuleName} 领域模型"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid


class {ModuleName}Status(str, Enum):
    """状态枚举"""
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


class {ModuleName}(BaseModel):
    """{ModuleName} 领域模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: {ModuleName}Status = {ModuleName}Status.DRAFT
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """转为可序列化的扁平 dict"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,  # Enum → .value
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),  # datetime → ISO 字符串
            "updated_at": self.updated_at.isoformat(),
        }
```

### 7. `odap/biz/{domain}/{module_name}/interfaces/__init__.py`
```python
"""接口抽象层"""
```

### 8. `odap/biz/{domain}/{module_name}/interfaces/{module_name}.py`
```python
"""{ModuleName} 抽象接口"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class I{ModuleName}Storage(ABC):
    """存储层抽象接口"""

    @abstractmethod
    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """保存（upsert）"""
        pass

    @abstractmethod
    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查询，不存在返回 None"""
        pass

    @abstractmethod
    def list(self, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """分页查询"""
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """删除，不存在返回 False"""
        pass


class I{ModuleName}Service(ABC):
    """服务层抽象接口"""

    @abstractmethod
    def get_{module_name}(self, id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def list_{module_name}s(self, page: int, page_size: int) -> List[Dict[str, Any]]:
        pass
```

### 9. `odap/biz/{domain}/{module_name}/impl/__init__.py`
```python
"""实现层"""
```

### 10. `odap/biz/{domain}/{module_name}/impl/{module_name}.py`
```python
"""{ModuleName} 核心业务实现"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from ..models.{module_name} import {ModuleName}, {ModuleName}Status
from ..interfaces.{module_name} import I{ModuleName}Storage
from ..storage import Storage


class {ModuleName}Impl:
    """{ModuleName} 业务实现"""

    def __init__(self, storage: I{ModuleName}Storage = None):
        self.storage = storage or Storage()

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建{ModuleName}"""
        if not data.get("name"):
            raise ValueError("名称不能为空")

        # 构造领域模型（自动填充 id、created_at）
        model = {ModuleName}(
            name=data["name"],
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )
        return self.storage.save(model.to_dict())

    def update(self, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新{ModuleName}"""
        existing = self.storage.get(id)
        if not existing:
            return {"status": "error", "message": "{ModuleName}不存在"}

        # 合并更新
        existing.update(data)
        existing["updated_at"] = datetime.now().isoformat()
        return self.storage.save(existing)

    def delete(self, id: str) -> bool:
        return self.storage.delete(id)
```

### 11. `odap/biz/{domain}/{module_name}/services/__init__.py`
```python
"""服务编排层"""
```

### 12. `odap/biz/{domain}/{module_name}/services/{module_name}_service.py`
```python
"""{ModuleName}Service 编排层

按 AGENTS.md 规则：
- 返回 Dict[str, Any]，不直接返回 Pydantic 模型
- 类型转换在服务层完成（Enum→.value, datetime→.isoformat）
- 不抛 HTTPException，错误返回 {"status": "error", "message": "..."}
"""
from typing import Dict, Any, List
from datetime import datetime

from ..impl.{module_name} import {ModuleName}Impl
from ..storage import Storage


class {ModuleName}Service:
    def __init__(self):
        self.impl = {ModuleName}Impl(Storage())

    def get_{module_name}(self, id: str) -> Dict[str, Any]:
        try:
            result = self.impl.storage.get(id)
            if not result:
                return {"status": "error", "message": "{ModuleName}不存在"}
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_{module_name}s(self, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        try:
            return self.impl.storage.list(page=page, page_size=page_size)
        except Exception as e:
            return []

    def create_{module_name}(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.impl.create(data)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def update_{module_name}(self, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.impl.update(id, data)

    def delete_{module_name}(self, id: str) -> Dict[str, Any]:
        success = self.impl.delete(id)
        if not success:
            return {"status": "error", "message": "{ModuleName}不存在"}
        return {"status": "success", "message": "{ModuleName}删除成功"}
```

### 13. `odap/biz/{domain}/{module_name}/storage/__init__.py`
```python
"""存储层

按 AGENTS.md 规则：导出 Storage = SQLiteXxxStorage 别名
"""
from .sqlite_{module_name}_storage import SQLite{ModuleName}Storage

Storage = SQLite{ModuleName}Storage

__all__ = ["Storage", "SQLite{ModuleName}Storage"]
```

### 14. `odap/biz/{domain}/{module_name}/storage/sqlite_{module_name}_storage.py`
```python
"""SQLite 存储层

按 AGENTS.md 规则：
- 每次 sqlite3.connect() → 用完 conn.close()（无连接池）
- 复杂字段 (Dict/List) → JSON TEXT 列
- Enum → .value 字符串存储
- datetime → ISO 字符串存储
"""
import os
import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime


class SQLite{ModuleName}Storage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "{module_name}s.db"
        )
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS {module_name}s (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_{module_name}s_name ON {module_name}s(name)"
            )
            conn.commit()
        finally:
            conn.close()

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            # List/Dict → JSON
            tags_json = json.dumps(data.get("tags", []), ensure_ascii=False)
            conn.execute(
                """
                INSERT OR REPLACE INTO {module_name}s
                (id, name, description, status, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["id"],
                    data["name"],
                    data.get("description", ""),
                    data.get("status", "draft"),
                    tags_json,
                    data.get("created_at", datetime.now().isoformat()),
                    data.get("updated_at", datetime.now().isoformat()),
                ),
            )
            conn.commit()
            return data
        finally:
            conn.close()

    def get(self, id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM {module_name}s WHERE id = ?", (id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def list(self, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            offset = (page - 1) * page_size
            cursor = conn.execute(
                "SELECT * FROM {module_name}s ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete(self, id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM {module_name}s WHERE id = ?", (id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """行转 dict，包含 JSON 反序列化的容错"""
        try:
            tags = json.loads(row[4]) if row[4] else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "status": row[3],
            "tags": tags,
            "created_at": row[5],
            "updated_at": row[6],
        }
```

### 15. `tests/unit/test_{module_name}.py`
```python
"""{ModuleName} 模块测试

按 AGENTS.md 测试规则：
- 存储层用 tmp_path 真实 DB
- 服务层用 patch() Mock Storage
- 路由层用 TestClient 测试 HTTP 状态码
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


# ============ 测试数据工厂 ============

def _make_xxx(**overrides) -> dict:
    """构造测试数据"""
    data = {
        "id": "test-001",
        "name": "Test {ModuleName}",
        "description": "Test description",
        "status": "draft",
        "tags": ["a", "b"],
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    data.update(overrides)
    return data


# ============ 存储层测试（真实 DB）============

class TestSQLite{ModuleName}Storage:

    def test_init_creates_table(self, tmp_path):
        from odap.biz.{domain}.{module_name}.storage import SQLite{ModuleName}Storage
        storage = SQLite{ModuleName}Storage(db_path=str(tmp_path / "{module_name}.db"))

        import sqlite3
        conn = sqlite3.connect(str(tmp_path / "{module_name}.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='{module_name}s'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_save_xxx_upsert(self, tmp_path):
        from odap.biz.{domain}.{module_name}.storage import SQLite{ModuleName}Storage
        storage = SQLite{ModuleName}Storage(db_path=str(tmp_path / "{module_name}.db"))

        storage.save(_make_xxx())
        storage.save(_make_xxx(name="Updated"))
        result = storage.get("test-001")
        assert result["name"] == "Updated"

    def test_get_xxx_not_found_returns_none(self, tmp_path):
        from odap.biz.{domain}.{module_name}.storage import SQLite{ModuleName}Storage
        storage = SQLite{ModuleName}Storage(db_path=str(tmp_path / "{module_name}.db"))
        assert storage.get("nonexistent") is None

    def test_list_with_pagination(self, tmp_path):
        from odap.biz.{domain}.{module_name}.storage import SQLite{ModuleName}Storage
        storage = SQLite{ModuleName}Storage(db_path=str(tmp_path / "{module_name}.db"))
        for i in range(15):
            storage.save(_make_xxx(id=f"test-{i:03d}"))
        result = storage.list(page=2, page_size=10)
        assert len(result) == 5

    def test_delete_xxx(self, tmp_path):
        from odap.biz.{domain}.{module_name}.storage import SQLite{ModuleName}Storage
        storage = SQLite{ModuleName}Storage(db_path=str(tmp_path / "{module_name}.db"))
        storage.save(_make_xxx())
        assert storage.delete("test-001") is True
        assert storage.get("test-001") is None

    def test_delete_not_found_returns_false(self, tmp_path):
        from odap.biz.{domain}.{module_name}.storage import SQLite{ModuleName}Storage
        storage = SQLite{ModuleName}Storage(db_path=str(tmp_path / "{module_name}.db"))
        assert storage.delete("nonexistent") is False

    def test_json_field_roundtrip(self, tmp_path):
        from odap.biz.{domain}.{module_name}.storage import SQLite{ModuleName}Storage
        storage = SQLite{ModuleName}Storage(db_path=str(tmp_path / "{module_name}.db"))
        storage.save(_make_xxx(tags=["a", "b", "c"]))
        result = storage.get("test-001")
        assert result["tags"] == ["a", "b", "c"]

    def test_invalid_json_returns_default(self, tmp_path):
        """非法 JSON 容错"""
        from odap.biz.{domain}.{module_name}.storage import SQLite{ModuleName}Storage
        db_path = tmp_path / "{module_name}.db"
        storage = SQLite{ModuleName}Storage(db_path=str(db_path))
        # 手动写入非法 JSON
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO {module_name}s (id, name, tags) VALUES (?, ?, ?)",
            ("bad", "Bad", "invalid-json{"),
        )
        conn.commit()
        conn.close()

        result = storage.get("bad")
        assert result["tags"] == []  # 容错返回空列表


# ============ 服务层测试（Mock Storage）============

class Test{ModuleName}Service:

    def test_get_xxx_success(self):
        with patch("odap.biz.{domain}.{module_name}.services.{module_name}_service.Storage") as mock:
            mock.return_value.get.return_value = _make_xxx()
            from odap.biz.{domain}.{module_name}.services.{module_name}_service import {ModuleName}Service
            service = {ModuleName}Service()
            result = service.get_{module_name}("test-001")
            assert result["id"] == "test-001"
            assert result["status"] == "draft"  # 字符串而非 Enum

    def test_get_xxx_not_found(self):
        with patch("odap.biz.{domain}.{module_name}.services.{module_name}_service.Storage") as mock:
            mock.return_value.get.return_value = None
            from odap.biz.{domain}.{module_name}.services.{module_name}_service import {ModuleName}Service
            service = {ModuleName}Service()
            result = service.get_{module_name}("nonexistent")
            assert result["status"] == "error"

    def test_create_xxx_empty_name_raises(self):
        with patch("odap.biz.{domain}.{module_name}.services.{module_name}_service.Storage") as mock:
            from odap.biz.{domain}.{module_name}.services.{module_name}_service import {ModuleName}Service
            service = {ModuleName}Service()
            result = service.create_{module_name}({"name": ""})
            assert result["status"] == "error"


# ============ 路由层测试（TestClient）============

class Test{ModuleName}Routes:

    def test_get_xxx_returns_200(self):
        from fastapi.testclient import TestClient
        from odap.biz.{domain}.{module_name}.api.routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("odap.biz.{domain}.{module_name}.api.routes.service") as mock_service:
            mock_service.get_{module_name}.return_value = _make_xxx()
            response = client.get("/api/{module_name}/test-001")
            assert response.status_code == 200
            assert response.json()["id"] == "test-001"

    def test_get_xxx_not_found_returns_404(self):
        from fastapi.testclient import TestClient
        from odap.biz.{domain}.{module_name}.api.routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("odap.biz.{domain}.{module_name}.api.routes.service") as mock_service:
            mock_service.get_{module_name}.return_value = {"status": "error", "message": "不存在"}
            response = client.get("/api/{module_name}/missing")
            assert response.status_code == 404

    def test_http_exception_propagates(self):
        """验证 except HTTPException: raise 透传，未被 500 吞掉"""
        from fastapi.testclient import TestClient
        from fastapi import HTTPException
        from odap.biz.{domain}.{module_name}.api.routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("odap.biz.{domain}.{module_name}.api.routes.service") as mock_service:
            mock_service.get_{module_name}.side_effect = HTTPException(status_code=403, detail="forbidden")
            response = client.get("/api/{module_name}/test-001")
            assert response.status_code == 403  # 不是 500
```

## 注册到生产入口（ODAP 强制）

生成完成后，**必须** 在 [odap/web/app.py](file:///e:/DEMO/AI/ontology-graphiti/odap/web/app.py) 中注册路由：

```python
from odap.biz.{domain}.{module_name}.api.routes import router as {module_name}_router

app.include_router({module_name}_router)
```

## 验证步骤

生成完成后：
1. 运行 `pytest tests/unit/test_{module_name}.py -v` 确认测试通过
2. 运行 `pytest tests/unit/ -v` 确认无回归
3. 检查 `odap/web/app.py` 中已注册
4. 启动服务测试 API：
   ```bash
   curl -X POST http://localhost:8000/api/{module_name} -H "Content-Type: application/json" -d '{"name":"test"}'
   ```

## 输出

向用户报告：
- 生成的目录和文件列表
- 测试通过情况
- 注册到 app.py 的位置
- 下一步建议（调用 `tdd-red-green-refactor` 进入下一轮 TDD）
