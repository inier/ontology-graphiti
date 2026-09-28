"""execution_tool delete_entity 分支经 GraphWriteProxy 软删（真实函数体，下游边界打桩）。

裁定 A：真实类名为 ExecutionStrategyTool（execution_tool.py 无 ExecutionTool）。
裁定 B：_perform_action 的 try 块在抵达任何 action 分支前会真实构造
get_query_service() 与 GraphManager()，离线环境会抛错/挂起并被宽 except 吞为
status="failed"，导致 delete_entity 分支不可达。故同时 patch 这两个下游依赖 +
get_graph_write_proxy，SUT（delete_entity 分支）仍走真实代码（规则 14 #6）。
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
    with patch("odap.infra.query.get_query_service", return_value=MagicMock()), \
         patch("odap.infra.graph.graph_service.GraphManager", return_value=MagicMock()), \
         patch("odap.infra.query.get_graph_write_proxy", return_value=fake_proxy):
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
    with patch("odap.infra.query.get_query_service", return_value=MagicMock()), \
         patch("odap.infra.graph.graph_service.GraphManager", return_value=MagicMock()), \
         patch("odap.infra.query.get_graph_write_proxy", return_value=fake_proxy):
        result = tool._perform_action(_make_input())
    assert result["status"] == "error"
    assert "entity not found" in result["message"]
    fake_proxy.delete_entity.assert_called_once()
