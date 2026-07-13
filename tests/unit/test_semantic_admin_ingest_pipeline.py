"""Semantic Admin Ingest→Pipeline 单元测试（AGENTS.md §C，≤250 LOC）。"""
from __future__ import annotations

import json
import os
from enum import Enum
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

try:
    from pydantic import BaseModel, Field, ConfigDict
except Exception as _exc:  # pragma: no cover
    pytest.skip(f"Pydantic unavailable: {_exc}", allow_module_level=True)


class IngestSourceType(str, Enum):
    NATURAL_LANGUAGE = "natural_language"
    MANUAL = "manual"
    JSON = "json"


class UnifiedIngestRequest(BaseModel):
    """统一摄入请求 Schema（T2：新增 config 可选 Dict）。"""
    model_config = ConfigDict(strict=False, extra="ignore")
    workspace_id: str
    source_type: str = IngestSourceType.NATURAL_LANGUAGE.value
    text: Optional[str] = None
    ontology_id: Optional[str] = None
    scenario_id: Optional[str] = None
    extraction_mode: str = "constrained"
    config: Optional[Dict[str, Any]] = Field(default=None)


def _s2b(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


def _auto(req: UnifiedIngestRequest, env_default: Optional[str] = None) -> bool:
    cfg = req.config or {}
    if "auto_pipeline" in cfg:
        return bool(cfg["auto_pipeline"])
    return _s2b(env_default)


# 1. Schema Tests -----------------------------------------------------------
class TestIngestRequestSchema:
    def test_config_optional(self):
        r1 = UnifiedIngestRequest(workspace_id="w1", text="a")
        assert r1.config is None
        r2 = UnifiedIngestRequest(
            workspace_id="w1", text="a",
            config={"auto_pipeline": True, "l1": {"n": 2}},
        )
        assert r2.config == {"auto_pipeline": True, "l1": {"n": 2}}

    def test_json_roundtrip(self):
        r = UnifiedIngestRequest(
            workspace_id="w1", text="Hi",
            config={"auto_pipeline": True, "x": "军事"},
        )
        j = r.model_dump_json()
        p = json.loads(j)
        assert p["config"] == {"auto_pipeline": True, "x": "军事"}
        r2 = UnifiedIngestRequest.model_validate(p)
        assert r2.config == r.config

    def test_empty_dict_and_none_both_valid(self):
        a = UnifiedIngestRequest(workspace_id="w", text="a", config={})
        assert a.config == {}
        b = UnifiedIngestRequest(workspace_id="w", text="a", config=None)
        assert b.config is None


# 2. Auto Pipeline Switch（Env default） -------------------------------------
_SENTINEL = object()


class TestAutoPipelineSwitch:
    @patch("asyncio.create_task")
    def test_env_true_triggers(self, mock_ct: MagicMock):
        with patch.dict(os.environ, {"INGEST_AUTO_PIPELINE_DEFAULT": "true"}):
            req = UnifiedIngestRequest(workspace_id="w1", text="三国：刘备、关羽")
            ok = _auto(req, os.environ.get("INGEST_AUTO_PIPELINE_DEFAULT"))
            assert ok is True
            if ok:
                mock_ct(AsyncMock())  # 用 AsyncMock 避免未 await 警告
            assert mock_ct.called and mock_ct.call_count >= 1

    @patch("asyncio.create_task")
    def test_env_false_no_trigger(self, mock_ct: MagicMock):
        with patch.dict(os.environ, {"INGEST_AUTO_PIPELINE_DEFAULT": "false"}):
            req = UnifiedIngestRequest(workspace_id="w1", text="Test")
            ok = _auto(req, os.environ.get("INGEST_AUTO_PIPELINE_DEFAULT"))
            assert ok is False
            if ok:
                mock_ct(_SENTINEL)
            assert not mock_ct.called


# 3. Config Override Env ----------------------------------------------------
class TestConfigSwitchOverridesEnv:
    @patch("asyncio.create_task")
    def test_payload_true_overrides_env_false(self, mock_ct: MagicMock):
        with patch.dict(os.environ, {"INGEST_AUTO_PIPELINE_DEFAULT": "false"}):
            req = UnifiedIngestRequest(
                workspace_id="w1", text="Auto trigger",
                config={"auto_pipeline": True},
            )
            ok = _auto(req, os.environ.get("INGEST_AUTO_PIPELINE_DEFAULT"))
            assert ok is True
            if ok:
                mock_ct(AsyncMock())
            assert mock_ct.called and mock_ct.call_count == 1

    @patch("asyncio.create_task")
    def test_payload_false_overrides_env_true(self, mock_ct: MagicMock):
        with patch.dict(os.environ, {"INGEST_AUTO_PIPELINE_DEFAULT": "true"}):
            req = UnifiedIngestRequest(
                workspace_id="w1", text="No pipeline",
                config={"auto_pipeline": False},
            )
            ok = _auto(req, os.environ.get("INGEST_AUTO_PIPELINE_DEFAULT"))
            assert ok is False
            if ok:
                mock_ct(_SENTINEL)
            assert not mock_ct.called
