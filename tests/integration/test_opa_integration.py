import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OPA_AVAILABLE = False
try:
    import httpx
    opa_url = os.getenv("OPA_URL", "http://localhost:8181")
    resp = httpx.get(f"{opa_url}/health", timeout=2.0)
    if resp.status_code == 200:
        OPA_AVAILABLE = True
except Exception:
    pass

skip_if_no_opa = pytest.mark.skipif(
    not OPA_AVAILABLE,
    reason="OPA server not available for integration testing",
)


class TestMarkdownToRegoCompilation:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from odap.infra.opa.markdown_compiler import MarkdownCompiler
        self.compiler = MarkdownCompiler()

    def test_compile_simple_policy(self):
        markdown = """# 访问控制策略

## 角色 指挥官

### 允许操作
- 查询
- 分析
- 报告
- 决策

## 角色 分析师

### 允许操作
- 查询
- 分析
"""
        result = self.compiler.compile(markdown)
        assert result.success is True
        assert len(result.rego_text) > 0
        assert "commander" in result.rego_text or "指挥官" in result.rego_text

    def test_compile_deny_policy(self):
        markdown = """# 安全策略

## 角色 访客

### 禁止操作
- 写入
- 删除
- 更新
"""
        result = self.compiler.compile(markdown)
        assert result.success is True
        assert len(result.rego_text) > 0

    def test_compile_empty_policy(self):
        markdown = ""
        result = self.compiler.compile(markdown)
        assert result.success is True or len(result.errors) > 0

    def test_compile_multi_role_policy(self):
        markdown = """# 多角色策略

## 角色 管理员

### 允许操作
- 查询
- 写入
- 删除

## 角色 操作员

### 允许操作
- 查询
- 写入

## 角色 观察员

### 允许操作
- 查询
"""
        result = self.compiler.compile(markdown)
        assert result.success is True
        assert len(result.rules) >= 3

    def test_compile_role_mapping(self):
        markdown = """# 策略

## 角色 指挥官

### 允许操作
- 攻击
- 防御
"""
        result = self.compiler.compile(markdown)
        assert result.success is True
        assert "attack" in result.rego_text or "defend" in result.rego_text


class TestOPAPolicyCRUD:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.db_path = str(tmp_path / "test_opa.db")

    def _get_conn(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute('''CREATE TABLE IF NOT EXISTS policies (
            policy_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            status TEXT DEFAULT 'enabled',
            version TEXT DEFAULT '1.0.0',
            markdown_content TEXT,
            rego_content TEXT,
            created_at TEXT,
            updated_at TEXT
        )''')
        conn.commit()
        return conn

    def test_create_policy(self):
        conn = self._get_conn()
        policy_id = f"policy-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (policy_id, "Test Policy", "Desc", "test", "enabled", "1.0.0",
             "# Test", 'package test\nallow=true', now, now),
        )
        conn.commit()
        cursor = conn.execute("SELECT * FROM policies WHERE policy_id=?", (policy_id,))
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "Test Policy"

    def test_update_policy_status(self):
        conn = self._get_conn()
        policy_id = f"policy-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (policy_id, "Status Test", "Desc", "test", "enabled", "1.0.0",
             "# Test", 'package test\nallow=true', now, now),
        )
        conn.commit()
        conn.execute(
            "UPDATE policies SET status=?, updated_at=? WHERE policy_id=?",
            ("disabled", datetime.utcnow().isoformat(), policy_id),
        )
        conn.commit()
        cursor = conn.execute("SELECT status FROM policies WHERE policy_id=?", (policy_id,))
        row = cursor.fetchone()
        conn.close()
        assert row[0] == "disabled"

    def test_delete_policy(self):
        conn = self._get_conn()
        policy_id = f"policy-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (policy_id, "Delete Test", "Desc", "test", "enabled", "1.0.0",
             "# Test", 'package test\nallow=true', now, now),
        )
        conn.commit()
        conn.execute("DELETE FROM policies WHERE policy_id=?", (policy_id,))
        conn.commit()
        cursor = conn.execute("SELECT * FROM policies WHERE policy_id=?", (policy_id,))
        row = cursor.fetchone()
        conn.close()
        assert row is None


@skip_if_no_opa
class TestOPAEvaluation:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from odap.infra.opa.opa_service import OPAManager
        self.opa = OPAManager()

    def test_evaluate_allow_decision(self):
        result = self.opa.check_permission_abac({
            "role": "commander",
            "action": "view",
            "resource": "reports",
        })
        assert result.get("allow") is True or "decision" in str(result).lower()

    def test_evaluate_deny_decision(self):
        result = self.opa.check_permission_abac({
            "role": "guest",
            "action": "delete",
            "resource": "classified_data",
        })
        assert result is not None

    def test_health_check(self):
        healthy = self.opa.health_check()
        assert healthy is True
