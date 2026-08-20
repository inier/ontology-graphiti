#!/usr/bin/env python3
"""P1-04/06: OpenHarness OPA 守卫 + .env 敏感路径测试"""

import pytest
from unittest.mock import MagicMock, patch
from odap.infra.opa.pep import EnforcementResult
from odap.biz.integration.openharness_agent.opa_guard import OpenHarnessOPAGuard


class TestOpenHarnessOPAGuard:
    """守卫桥接 PEP"""

    def test_guard_allow_passes_through(self):
        mock_pep = MagicMock()
        mock_pep.evaluate.return_value = EnforcementResult(
            allowed=True, reason="granted", stage="executed"
        )
        guard = OpenHarnessOPAGuard(pep=mock_pep)

        result = guard.check_tool_execution(
            agent_id="agent-1",
            tool_name="read_file",
            tool_input={"path": "/data/doc.txt"},
            subject={"id": "user1", "roles": ["analyst"]},
            environment={"time": "2026-08-14"},
            trace_id="trace-1",
        )

        assert result["allowed"] is True
        assert result["stage"] == "executed"
        mock_pep.evaluate.assert_called_once()

    def test_guard_deny_passes_through(self):
        mock_pep = MagicMock()
        mock_pep.evaluate.return_value = EnforcementResult(
            allowed=False, reason="not in allow-list",
            stage="whitelist", blocked_at="whitelist"
        )
        guard = OpenHarnessOPAGuard(pep=mock_pep)

        result = guard.check_tool_execution(
            agent_id="agent-1",
            tool_name="evil_tool",
            tool_input={},
            subject={"id": "user1", "roles": ["analyst"]},
        )

        assert result["allowed"] is False
        assert result["blocked_at"] == "whitelist"

    def test_guard_pep_not_configured_fail_close(self):
        guard = OpenHarnessOPAGuard(pep=None)

        result = guard.check_tool_execution(
            agent_id="agent-1",
            tool_name="read_file",
            tool_input={},
            subject={"id": "user1", "roles": ["analyst"]},
        )

        assert result["allowed"] is False
        assert "PEP not configured" in result["reason"]
        assert result["blocked_at"] == "guard"

    def test_guard_passes_tool_input_as_resource(self):
        """验证 tool_input 被正确传入 resource.input"""
        mock_pep = MagicMock()
        mock_pep.evaluate.return_value = EnforcementResult(
            allowed=True, reason="ok", stage="executed"
        )
        guard = OpenHarnessOPAGuard(pep=mock_pep)

        guard.check_tool_execution(
            agent_id="a1",
            tool_name="write_file",
            tool_input={"path": "/out.txt", "content": "hello"},
            subject={"id": "u1", "roles": ["admin"]},
        )

        call_args = mock_pep.evaluate.call_args[0][0]
        assert call_args.tool_name == "write_file"
        assert call_args.resource["input"]["path"] == "/out.txt"
        assert call_args.input_context["content"] == "hello"


class TestEnvSensitivePath:
    """白皮书 §2.2: .env 文件被 OpenHarness 拦截

    直接测试 SENSITIVE_PATH_PATTERNS 匹配逻辑，
    不依赖完整 openharness 包安装。
    """

    def _get_env_patterns(self):
        """直接从源文件提取 .env 相关的 glob 模式字符串"""
        import os
        project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        checker_path = os.path.join(
            project_root, "packages", "openharness", "src", "openharness", "permissions", "checker.py"
        )
        with open(checker_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 提取 .env 相关的字符串行
        env_patterns = []
        for line in content.splitlines():
            stripped = line.strip()
            if ".env" in stripped and stripped.startswith('"'):
                # 提取引号内的 pattern
                pattern = stripped.split('"')[1]
                env_patterns.append(pattern)
        return env_patterns

    def test_env_in_patterns(self):
        patterns = self._get_env_patterns()
        import fnmatch
        assert any(fnmatch.fnmatch("/project/.env", p) for p in patterns)

    def test_env_local_in_patterns(self):
        patterns = self._get_env_patterns()
        import fnmatch
        assert any(fnmatch.fnmatch("/project/.env.local", p) for p in patterns)

    def test_envrc_in_patterns(self):
        patterns = self._get_env_patterns()
        import fnmatch
        assert any(fnmatch.fnmatch("/project/.envrc", p) for p in patterns)

    def test_normal_file_not_matched_by_env_rule(self):
        patterns = self._get_env_patterns()
        import fnmatch
        assert not any(fnmatch.fnmatch("/project/data.txt", p) for p in patterns)
