"""
规划编排技能模块单元测试

测试 odap/tools/planning/planning.py 中的所有函数：
- create_plan: 攻击/侦察/通用目标
- execute_workflow: attack_workflow / reconnaissance_workflow / 未知工作流
- validate_plan: 有效/无效/带警告的计划
- estimate_resources: 资源估算

Mock 策略：GraphManager 需 mock。

AGENTS.md Rule 9: 新增模块必须同步新增测试文件。
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# TestCreatePlan
# ---------------------------------------------------------------------------


class TestCreatePlan:
    """测试 create_plan 函数"""

    @patch("odap.tools.planning.planning.manager")
    def test_attack_goal(self, mock_manager):
        """攻击目标生成5步攻击计划"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 10,
            "entity_types": {"MilitaryUnit": 5},
            "mode": "networkx",
        }

        from odap.tools.planning.planning import create_plan

        result = create_plan("攻击敌方雷达站")

        assert result["status"] == "success"
        assert result["total_steps"] == 5
        assert result["data_source"] == "graph"
        assert result["graph_context"]["total_entities"] == 10
        steps = result["steps"]
        assert steps[0]["action"] == "reconnaissance"
        assert steps[-1]["action"] == "damage_assessment"

    @patch("odap.tools.planning.planning.manager")
    def test_reconnaissance_goal(self, mock_manager):
        """侦察目标生成3步侦察计划"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 0,
            "entity_types": {},
            "mode": "unknown",
        }

        from odap.tools.planning.planning import create_plan

        result = create_plan("侦察B区敌方活动")

        assert result["status"] == "success"
        assert result["total_steps"] == 3
        assert result["data_source"] == "simulation"
        steps = result["steps"]
        assert steps[0]["action"] == "area_scan"

    @patch("odap.tools.planning.planning.manager")
    def test_generic_goal(self, mock_manager):
        """通用目标生成2步通用计划"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 0,
            "entity_types": {},
            "mode": "unknown",
        }

        from odap.tools.planning.planning import create_plan

        result = create_plan("评估当前态势")

        assert result["status"] == "success"
        assert result["total_steps"] == 2
        steps = result["steps"]
        assert steps[0]["action"] == "information_gathering"
        assert steps[1]["action"] == "analysis"

    @patch("odap.tools.planning.planning.manager")
    def test_destroy_keyword_triggers_attack(self, mock_manager):
        """'摧毁'关键词也触发攻击计划"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 0,
            "entity_types": {},
            "mode": "unknown",
        }

        from odap.tools.planning.planning import create_plan

        result = create_plan("摧毁敌方指挥中心")

        assert result["status"] == "success"
        assert result["total_steps"] == 5

    @patch("odap.tools.planning.planning.manager")
    def test_monitor_keyword_triggers_recon(self, mock_manager):
        """'监控'关键词触发侦察计划"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 0,
            "entity_types": {},
            "mode": "unknown",
        }

        from odap.tools.planning.planning import create_plan

        result = create_plan("监控A区动态")

        assert result["status"] == "success"
        assert result["total_steps"] == 3

    @patch("odap.tools.planning.planning.manager")
    def test_constraints_passed_through(self, mock_manager):
        """约束条件正确传递"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 0,
            "entity_types": {},
            "mode": "unknown",
        }

        from odap.tools.planning.planning import create_plan

        constraints = ["避免附带损伤", "夜间执行"]
        result = create_plan("攻击目标", constraints=constraints)

        assert result["constraints"] == constraints

    @patch("odap.tools.planning.planning.manager")
    def test_graph_failure_falls_back(self, mock_manager):
        """图谱查询失败时降级到 simulation"""
        mock_manager.get_graph_statistics.side_effect = Exception("graph error")

        from odap.tools.planning.planning import create_plan

        result = create_plan("攻击目标")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert "graph_context" not in result


# ---------------------------------------------------------------------------
# TestExecuteWorkflow
# ---------------------------------------------------------------------------


class TestExecuteWorkflow:
    """测试 execute_workflow 函数"""

    @patch("odap.tools.planning.planning.manager")
    def test_attack_workflow(self, mock_manager):
        """attack_workflow 包含4个步骤"""
        mock_manager.get_entity.return_value = {
            "id": "target-1",
            "properties": {"status": "正常", "name": "Enemy Radar"},
        }
        mock_manager.query_entities.return_value = []

        from odap.tools.planning.planning import execute_workflow

        result = execute_workflow(
            "attack_workflow", {"target_id": "target-1", "area": "B"}
        )

        assert result["status"] == "success"
        assert result["total_steps"] == 4
        assert result["completed_steps"] == 4
        assert result["results"][0]["action"] == "reconnaissance"
        assert result["results"][0]["success"] is True

    @patch("odap.tools.planning.planning.manager")
    def test_attack_workflow_target_not_found(self, mock_manager):
        """attack_workflow 中目标未在图谱中找到"""
        mock_manager.get_entity.return_value = None
        mock_manager.query_entities.return_value = []

        from odap.tools.planning.planning import execute_workflow

        result = execute_workflow(
            "attack_workflow", {"target_id": "nonexistent", "area": "B"}
        )

        assert result["status"] == "success"
        # 侦察步骤应报告未找到
        recon_result = result["results"][0]["result"]
        assert "未在图谱中找到" in recon_result

    @patch("odap.tools.planning.planning.manager")
    def test_reconnaissance_workflow(self, mock_manager):
        """reconnaissance_workflow 包含2个步骤"""
        mock_manager.query_entities.return_value = [
            {"id": "e1", "type": "WeaponSystem"},
            {"id": "e2", "type": "MilitaryUnit"},
        ]

        from odap.tools.planning.planning import execute_workflow

        result = execute_workflow(
            "reconnaissance_workflow", {"area": "B"}
        )

        assert result["status"] == "success"
        assert result["total_steps"] == 2
        assert result["results"][0]["action"] == "area_scan"
        assert "2 个目标" in result["results"][0]["result"]

    @patch("odap.tools.planning.planning.manager")
    def test_unknown_workflow(self, mock_manager):
        """未知工作流返回错误"""
        from odap.tools.planning.planning import execute_workflow

        result = execute_workflow("unknown_workflow", {})

        assert result["status"] == "error"
        assert "未知工作流" in result["message"]


# ---------------------------------------------------------------------------
# TestValidatePlan
# ---------------------------------------------------------------------------


class TestValidatePlan:
    """测试 validate_plan 函数"""

    def test_valid_plan(self):
        """有效计划返回成功"""
        from odap.tools.planning.planning import validate_plan

        plan = {
            "steps": [
                {
                    "step": 1,
                    "action": "reconnaissance",
                    "skills_required": ["search_radar"],
                },
            ]
        }

        result = validate_plan(plan)

        assert result["status"] == "success"
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_invalid_plan_no_steps(self):
        """无效计划（无 steps）返回错误"""
        from odap.tools.planning.planning import validate_plan

        result = validate_plan({})

        assert result["status"] == "error"
        assert "无效的计划格式" in result["message"]

    def test_invalid_plan_none(self):
        """None 计划返回错误"""
        from odap.tools.planning.planning import validate_plan

        result = validate_plan(None)

        assert result["status"] == "error"

    def test_plan_with_unknown_skill_warning(self):
        """包含未知技能的计划产生警告"""
        from odap.tools.planning.planning import validate_plan

        plan = {
            "steps": [
                {
                    "step": 1,
                    "action": "custom",
                    "skills_required": ["nonexistent_skill"],
                },
            ]
        }

        result = validate_plan(plan)

        assert result["status"] == "success"
        assert len(result["warnings"]) > 0
        assert any("nonexistent_skill" in w for w in result["warnings"])

    def test_plan_with_too_many_steps(self):
        """步骤过多的计划产生问题"""
        from odap.tools.planning.planning import validate_plan

        plan = {
            "steps": [
                {"step": i, "skills_required": ["search_radar"]}
                for i in range(12)
            ]
        }

        result = validate_plan(plan)

        assert result["status"] == "warning"
        assert result["valid"] is False
        assert any("步骤过多" in issue for issue in result["issues"])


# ---------------------------------------------------------------------------
# TestEstimateResources
# ---------------------------------------------------------------------------


class TestEstimateResources:
    """测试 estimate_resources 函数"""

    def test_short_plan(self):
        """短计划（< 30分钟）需要1人，低成本"""
        from odap.tools.planning.planning import estimate_resources

        plan = {
            "steps": [
                {"estimated_time": "10分钟", "skills_required": ["search_radar"]},
                {"estimated_time": "5分钟", "skills_required": ["analyze_domain"]},
            ]
        }

        result = estimate_resources(plan)

        assert result["status"] == "success"
        assert result["total_time_minutes"] == 15
        assert result["estimated_personnel"] == 1
        assert result["estimated_cost"] == "low"

    def test_medium_plan(self):
        """中等计划（30-60分钟）需要2人，中等成本"""
        from odap.tools.planning.planning import estimate_resources

        plan = {
            "steps": [
                {"estimated_time": "20分钟", "skills_required": ["search_radar"]},
                {"estimated_time": "20分钟", "skills_required": ["analyze_domain"]},
            ]
        }

        result = estimate_resources(plan)

        assert result["total_time_minutes"] == 40
        assert result["estimated_personnel"] == 2
        assert result["estimated_cost"] == "medium"

    def test_long_plan(self):
        """长计划（> 60分钟）需要2人，高成本"""
        from odap.tools.planning.planning import estimate_resources

        plan = {
            "steps": [
                {"estimated_time": "40分钟", "skills_required": ["search_radar"]},
                {"estimated_time": "30分钟", "skills_required": ["analyze_domain"]},
            ]
        }

        result = estimate_resources(plan)

        assert result["total_time_minutes"] == 70
        assert result["estimated_cost"] == "high"

    def test_skill_usage_counted(self):
        """技能使用次数正确统计"""
        from odap.tools.planning.planning import estimate_resources

        plan = {
            "steps": [
                {
                    "estimated_time": "5分钟",
                    "skills_required": ["search_radar", "analyze_domain"],
                },
                {
                    "estimated_time": "5分钟",
                    "skills_required": ["search_radar"],
                },
            ]
        }

        result = estimate_resources(plan)

        assert result["skill_usage"]["search_radar"] == 2
        assert result["skill_usage"]["analyze_domain"] == 1

    def test_empty_plan(self):
        """空计划返回0时间和1人"""
        from odap.tools.planning.planning import estimate_resources

        result = estimate_resources({"steps": []})

        assert result["total_time_minutes"] == 0
        assert result["estimated_personnel"] == 1
        assert result["estimated_cost"] == "low"
