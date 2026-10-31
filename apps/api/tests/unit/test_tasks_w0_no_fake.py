"""W0-2 / W0-3 回归：任务层不得再有伪实现与静默吞异常。

这几条断言是「防倒退」门禁：
- 源码里不得出现 `time.sleep(...)` 假等待；
- 不得出现硬编码的 `entities_generated: 100 / relations_generated: 150`；
- 能力缺失时必须显式 `NotImplementedError`（供路由层翻译 501），而不是返回假成功；
- 文件上传必须真实落库，落库失败/缺场景必须显式失败。
"""

from __future__ import annotations

import ast
import inspect

import pytest

import odap.infra.providers as providers
import odap.tasks as tasks


class TestNoFakeImplementation:
    def test_source_has_no_fake_sleep_or_hardcoded_counts(self):
        tree = ast.parse(inspect.getsource(tasks))

        sleeps = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
        ]
        assert not sleeps, "任务层不得用 sleep 模拟耗时（AST 级检查，docstring 提及不算）"

        fake_counts = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant)
                        and key.value in ("entities_generated", "relations_generated")
                        and isinstance(value, ast.Constant) and isinstance(value.value, int)):
                    fake_counts.append((key.value, value.value))
        assert not fake_counts, f"检测到硬编码假计数：{fake_counts}"

    def test_capability_reports_unavailable_with_actionable_reason(self):
        capability = tasks.graph_generation_capability()
        assert capability["available"] is False
        assert capability["error_code"] == tasks.ERR_GRAPH_NOT_IMPLEMENTED
        assert "extract(" in capability["reason"]  # 写明真实实现要求，不是模糊文案

    def test_graph_task_raises_not_implemented(self):
        with pytest.raises(NotImplementedError) as excinfo:
            tasks.generate_graph_task.run("task-001", "scn-return-rate", None)
        assert tasks.ERR_GRAPH_NOT_IMPLEMENTED in str(excinfo.value)

    def test_graph_task_returns_real_provider_counts(self, monkeypatch):
        class _Extractor:
            def extract(self, scenario_id, config):
                assert scenario_id == "scn-return-rate"
                return {"entities_generated": 3, "relations_generated": 2,
                        "component_version": "stub-0.1"}

        monkeypatch.setitem(providers._PROVIDER_FACTORIES,
                            tasks.GRAPH_EXTRACTOR_PROVIDER, lambda: _Extractor())
        result = tasks.generate_graph_task.run("task-002", "scn-return-rate", {"model": "x"})
        assert result["status"] == "completed"
        assert result["entities_generated"] == 3
        assert result["relations_generated"] == 2
        assert result["component_version"] == "stub-0.1"


class TestFileParse:
    def test_json_payload(self):
        parsed = tasks.parse_uploaded_file(b'{"entity": "Order", "metric": "order_return_rate"}',
                                            ".json")
        assert parsed["format"] == "json"
        assert parsed["item_count"] == 1
        assert "metric" in parsed["json_keys"]

    def test_csv_counts_real_rows(self):
        parsed = tasks.parse_uploaded_file("品类,退货率\n家电,0.184\n服饰,0.211\n".encode(),
                                            ".csv")
        assert parsed["csv_rows"] == 2
        assert parsed["item_count"] == 2
        assert "退货率" in parsed["csv_columns"]

    def test_txt_counts_lines(self):
        parsed = tasks.parse_uploaded_file("第一行\n第二行\n".encode(), ".txt")
        assert parsed["format"] == "txt"
        assert parsed["item_count"] == 2

    def test_unsupported_extension_raises_with_name(self):
        with pytest.raises(ValueError) as excinfo:
            tasks.parse_uploaded_file(b"x", ".xlsx")
        assert ".xlsx" in str(excinfo.value)


class TestFileUploadTask:
    def test_missing_scenario_fails_explicitly(self):
        result = tasks.process_file_upload_task.run("task-010", "退货明细.csv", b"a,b\n1,2\n",
                                                    ".csv", None)
        assert result["status"] == "failed"
        assert result["error_code"] == tasks.ERR_SCENARIO_REQUIRED
        assert "scenario_id" in result["error"]

    def test_unsupported_file_type_returns_code(self):
        result = tasks.process_file_upload_task.run("task-011", "退货明细.xlsx", b"x", ".xlsx",
                                                    "scn-1")
        assert result["status"] == "failed"
        assert result["error_code"] == "UNSUPPORTED_FILE_TYPE"

    def test_success_returns_persisted_row_id(self, monkeypatch):
        monkeypatch.setattr(tasks, "_persist_scenario_document", lambda sid, doc: 42)
        result = tasks.process_file_upload_task.run("task-012", "退货明细.csv",
                                                    b"a,b\n1,2\n", ".csv", "scn-1")
        assert result["status"] == "completed"
        assert result["doc_row_id"] == 42
        assert result["scenario_id"] == "scn-1"
        assert result["csv_rows"] == 1

    def test_missing_scenario_row_fails_with_not_found(self, monkeypatch):
        def _raise(scenario_id, doc):
            raise LookupError("scenario scn-ghost 不存在")

        monkeypatch.setattr(tasks, "_persist_scenario_document", _raise)
        result = tasks.process_file_upload_task.run("task-013", "退货明细.csv",
                                                    b"a,b\n1,2\n", ".csv", "scn-ghost")
        assert result["status"] == "failed"
        assert result["error_code"] == tasks.ERR_SCENARIO_NOT_FOUND

    def test_persist_crash_is_not_swallowed(self, monkeypatch):
        def _boom(scenario_id, doc):
            raise RuntimeError("SQLite disk I/O error")

        monkeypatch.setattr(tasks, "_persist_scenario_document", _boom)
        result = tasks.process_file_upload_task.run("task-014", "退货明细.csv",
                                                    b"a,b\n1,2\n", ".csv", "scn-1")
        assert result["status"] == "failed"
        assert result["error_code"] == tasks.ERR_PERSIST_FAILED
        assert "SQLite disk I/O error" in result["error"]
