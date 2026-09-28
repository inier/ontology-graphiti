"""execution_tool delete_entity 分支经 GraphWriteProxy 软删（真实函数体，下游边界打桩）。

裁定 A：真实类名为 ExecutionStrategyTool（execution_tool.py 无 ExecutionTool）。
裁定 B：delete_entity 分支已短路提为 _perform_action try 块首个 if，先于无关的
get_query_service()/GraphManager() 构造，故仅需 patch 下游边界 get_graph_write_proxy；
SUT（delete_entity 分支）走真实代码（规则 14 #6）。若短路被回退（delete 分支移回构造之后），
离线环境下未打桩的 get_query_service()/GraphManager() 会抛错被宽 except 吞为 status="failed"，
本测试即转红——因此不再 patch 这两个依赖，使其成为短路的回归护栏。
"""
from unittest.mock import patch, MagicMock


def _make_input(**over):
    from odap.biz.core.ontology.application.chat.tools.execution_tool import ExecutionInput
    base = dict(action="delete_entity", target="e1", params={},
                ontology_id="ont1", workspace_id="ws1")
    base.update(over)
    return ExecutionInput(**base)


def test_delete_entity_routes_through_proxy():
    """成功路径：经 proxy 软删并透传 status/invalid_at/relations_invalidated。"""
    from odap.biz.core.ontology.application.chat.tools import execution_tool as et
    tool = et.ExecutionStrategyTool()
    fake_proxy = MagicMock()
    fake_proxy.delete_entity.return_value = {
        "status": "success", "entity_id": "e1",
        "entities_invalidated": 1, "relations_invalidated": 0,
        "invalid_at": "2026-09-28T10:00:00+00:00",
    }
    with patch("odap.infra.query.get_graph_write_proxy", return_value=fake_proxy):
        result = tool._perform_action(_make_input())
    assert result["action"] == "delete_entity"
    assert result["status"] == "success"
    assert result["invalid_at"] == "2026-09-28T10:00:00+00:00"
    fake_proxy.delete_entity.assert_called_once()


def test_delete_entity_propagates_error():
    """失败路径：proxy 返回 error 必须透传，不得假成功（规则 14）。"""
    from odap.biz.core.ontology.application.chat.tools import execution_tool as et
    tool = et.ExecutionStrategyTool()
    fake_proxy = MagicMock()
    fake_proxy.delete_entity.return_value = {"status": "error", "message": "entity not found: e1"}
    with patch("odap.infra.query.get_graph_write_proxy", return_value=fake_proxy):
        result = tool._perform_action(_make_input())
    assert result["status"] == "error"
    assert "entity not found" in result["message"]
    fake_proxy.delete_entity.assert_called_once()
