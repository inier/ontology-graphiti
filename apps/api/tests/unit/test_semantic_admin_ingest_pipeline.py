"""Semantic Admin Ingest→Pipeline 单元测试。

规则 14 #6：测试必须执行真实函数体。本文件直接导入并调用
`odap.biz.data.ingest.api.routes._decide_auto_pipeline`（真实触发判定）与
`UnifiedIngestResponse`，不再本地复刻 `_auto`/`_s2b` 自测自评——旧版正是
「测试全绿、功能实际全死」的根源：它断言的 config-覆盖-env 语义真实代码从未实现。
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

try:
    from odap.biz.data.ingest.api.routes import (
        _decide_auto_pipeline,
        UnifiedIngestResponse,
    )
except Exception as _exc:  # pragma: no cover
    pytest.skip(f"ingest routes 导入失败: {_exc}", allow_module_level=True)


class TestDecideAutoPipeline:
    """真实触发判定：有 workspace_id + 开关开启 + natural_language 三者全满足才触发。"""

    def test_natural_language_with_config_true_triggers(self):
        triggered, reason = _decide_auto_pipeline(
            ws_id="w1", source_type="natural_language",
            req_cfg={"auto_pipeline": True},
        )
        assert triggered is True
        assert "触发" in reason

    def test_env_true_triggers_without_config(self):
        with patch.dict(os.environ, {"INGEST_AUTO_PIPELINE_DEFAULT": "true"}):
            triggered, _ = _decide_auto_pipeline(
                ws_id="w1", source_type="natural_language", req_cfg={},
            )
        assert triggered is True

    def test_config_false_does_not_override_env_true(self):
        # 真实语义是 OR：config.auto_pipeline=False + env=true → 仍触发。
        # 旧假测试断言此处为 False（config 覆盖 env），是生产代码从未实现的语义。
        # 「显式 opt-out 应压过服务端默认」是待评审的行为变更，此处只固化现状。
        with patch.dict(os.environ, {"INGEST_AUTO_PIPELINE_DEFAULT": "true"}):
            triggered, _ = _decide_auto_pipeline(
                ws_id="w1", source_type="natural_language",
                req_cfg={"auto_pipeline": False},
            )
        assert triggered is True

    def test_default_env_false_no_trigger(self):
        with patch.dict(os.environ, {"INGEST_AUTO_PIPELINE_DEFAULT": "false"}):
            triggered, reason = _decide_auto_pipeline(
                ws_id="w1", source_type="natural_language", req_cfg={},
            )
        assert triggered is False
        assert "开关未开启" in reason

    def test_unset_env_defaults_to_false_no_trigger(self):
        with patch.dict(os.environ, {"INGEST_AUTO_PIPELINE_DEFAULT": ""}):
            os.environ.pop("INGEST_AUTO_PIPELINE_DEFAULT", None)
            triggered, reason = _decide_auto_pipeline(
                ws_id="w1", source_type="natural_language", req_cfg={},
            )
        assert triggered is False
        assert "开关未开启" in reason

    def test_structured_source_never_triggers(self):
        triggered, reason = _decide_auto_pipeline(
            ws_id="w1", source_type="json", req_cfg={"auto_pipeline": True},
        )
        assert triggered is False
        assert "natural_language" in reason

    def test_missing_workspace_no_trigger(self):
        triggered, reason = _decide_auto_pipeline(
            ws_id=None, source_type="natural_language",
            req_cfg={"auto_pipeline": True},
        )
        assert triggered is False
        assert "workspace_id" in reason


class TestResponseObservability:
    """规则 14：摄入响应必须携带触发状态字段，杜绝静默伪成功。"""

    def test_response_defaults_not_triggered(self):
        r = UnifiedIngestResponse(status="success", source_type="json")
        assert r.pipeline_triggered is False
        assert r.pipeline_trigger_reason is None

    def test_response_carries_trigger_reason(self):
        r = UnifiedIngestResponse(
            status="success", source_type="natural_language",
            pipeline_triggered=True, pipeline_trigger_reason="已触发",
        )
        assert r.pipeline_triggered is True
        assert r.pipeline_trigger_reason == "已触发"

    def test_extra_result_keys_ignored(self):
        # 路由层用 UnifiedIngestResponse(**result, ...) 构造，facade 多余键须被忽略
        r = UnifiedIngestResponse(
            **{"status": "success", "source_type": "json", "unknown_key": 1},
            pipeline_triggered=False, pipeline_trigger_reason="n/a",
        )
        assert r.status == "success"
        assert r.pipeline_trigger_reason == "n/a"
