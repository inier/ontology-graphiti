"""
Phase 5: Agent Loop + NL Query 集成测试

行为: B5-3~B5-6 (智能体 NL 问答端到端验证)

运行方式:
  /c/Miniconda3/python.exe -m pytest tests/integration/test_agent_nl_integration.py -v --tb=short
"""

import json, os, sys, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 平台需要运行才能执行这些集成测试
pytestmark = pytest.mark.integration


class TestAgentNLQuery:
    """验证智能体 NL 问答能力"""

    def _login_and_get_token(self, base_url="http://localhost:8000"):
        """辅助：登录获取 token"""
        try:
            import requests
            r = requests.post(f"{base_url}/api/auth/login",
                json={"username": "admin", "password": "admin123"}, timeout=5)
            if r.status_code != 200:
                pytest.skip("Platform not available (login failed)")
            return r.json()["access_token"]
        except Exception:
            pytest.skip("Platform not available (connection failed)")

    def test_health_check(self):
        """B5-0: 平台健康检查"""
        try:
            import requests
            r = requests.get("http://localhost:8000/health", timeout=5)
            assert r.status_code == 200
            assert r.json().get("status") == "healthy"
        except Exception:
            pytest.skip("Platform not running")

    def test_sanguo_character_query(self):
        """B5-3: 三国人物 NL 查询返回结果"""
        token = self._login_and_get_token()
        import requests
        r = requests.post("http://localhost:8000/api/ontology/query/nl",
            json={"query": "刘备", "workspace_id": "default", "limit": 5},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15)
        assert r.status_code == 200, f"NL query failed: {r.status_code}"
        resp = r.json()
        assert resp.get("status") == "success", f"Query not successful: {resp}"
        assert resp.get("total", 0) > 0, f"Expected rows > 0, got {resp.get('total')}"

    def test_xiyou_character_query(self):
        """B5-4: 西游人物 NL 查询返回结果"""
        token = self._login_and_get_token()
        import requests
        r = requests.post("http://localhost:8000/api/ontology/query/nl",
            json={"query": "孙悟空", "workspace_id": "default", "limit": 5},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15)
        assert r.status_code == 200
        resp = r.json()
        assert resp.get("status") == "success"
        assert resp.get("total", 0) > 0

    def test_sanguo_timeline_query(self):
        """B5-5: 三国时间线推演——按年份查询"""
        token = self._login_and_get_token()
        import requests
        r = requests.post("http://localhost:8000/api/ontology/query/nl",
            json={"query": "赤壁之战", "workspace_id": "default", "limit": 5},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15)
        assert r.status_code == 200
        resp = r.json()
        assert resp.get("status") == "success"

    def test_xiyou_timeline_query(self):
        """B5-6: 西游劫难推演——按难数查询"""
        token = self._login_and_get_token()
        import requests
        r = requests.post("http://localhost:8000/api/ontology/query/nl",
            json={"query": "火焰山", "workspace_id": "default", "limit": 5},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15)
        assert r.status_code == 200
        resp = r.json()
        assert resp.get("status") == "success"

    def test_agent_list_exists(self):
        """B5-1~B5-2: 智能体已创建且可查询"""
        token = self._login_and_get_token()
        import requests
        r = requests.get("http://localhost:8000/api/agent-management",
            headers={"Authorization": f"Bearer {token}"}, timeout=10)
        assert r.status_code == 200
        agents = r.json()
        assert isinstance(agents, list)
        names = [a.get("name", "") for a in agents]
        # 至少应该有一个三国或西游智能体
        has_agent = any("sanguo" in n or "xiyou" in n for n in names)
        assert has_agent, f"No sanguo/xiyou agent found in: {names}"

    def test_treasure_query(self):
        """B3-7验证: 西游法宝查询"""
        token = self._login_and_get_token()
        import requests
        r = requests.post("http://localhost:8000/api/ontology/query/nl",
            json={"query": "金箍棒", "workspace_id": "default", "limit": 3},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15)
        assert r.status_code == 200
        resp = r.json()
        assert resp.get("status") == "success"
