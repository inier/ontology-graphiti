"""
规划与编排Skill模块
实现任务规划和执行流程管理
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import register_skill
from odap.infra.graph import GraphManager
from odap.biz.simulator.data_generator import load_simulation_data

manager = GraphManager()

def create_plan(goal, constraints=None):
    """
    创建执行计划

    Args:
        goal: 目标描述
        constraints: 约束条件

    Returns:
        执行计划
    """
    data = load_simulation_data()

    plan_steps = []

    if "攻击" in goal or "摧毁" in goal:
        plan_steps.append({
            "step": 1,
            "action": "reconnaissance",
            "description": "情报侦察 - 确认目标位置和状态",
            "estimated_time": "5分钟",
            "skills_required": ["search_radar", "analyze_entity_status"]
        })
        plan_steps.append({
            "step": 2,
            "action": "threat_analysis",
            "description": "威胁分析 - 评估打击风险和附带损伤",
            "estimated_time": "3分钟",
            "skills_required": ["analyze_threat_level", "check_strike_risk"]
        })
        plan_steps.append({
            "step": 3,
            "action": "authorization",
            "description": "授权确认 - 检查权限和策略",
            "estimated_time": "1分钟",
            "skills_required": ["check_permission", "simulate_policy_execution"]
        })
        plan_steps.append({
            "step": 4,
            "action": "strike_execution",
            "description": "执行打击 - 下达攻击指令",
            "estimated_time": "2分钟",
            "skills_required": ["attack_target"]
        })
        plan_steps.append({
            "step": 5,
            "action": "damage_assessment",
            "description": "毁伤评估 - 确认打击效果",
            "estimated_time": "10分钟",
            "skills_required": ["calculate_strike_damage", "analyze_entity_status"]
        })

    elif "侦察" in goal or "监控" in goal:
        plan_steps.append({
            "step": 1,
            "action": "area_scan",
            "description": "区域扫描 - 搜索目标区域",
            "estimated_time": "10分钟",
            "skills_required": ["search_radar", "analyze_domain"]
        })
        plan_steps.append({
            "step": 2,
            "action": "data_collection",
            "description": "数据收集 - 记录目标信息",
            "estimated_time": "5分钟",
            "skills_required": ["analyze_entity_status"]
        })
        plan_steps.append({
            "step": 3,
            "action": "threat_assessment",
            "description": "威胁评估 - 分析领域态势",
            "estimated_time": "5分钟",
            "skills_required": ["analyze_threat_level", "generate_domain_report"]
        })

    else:
        plan_steps.append({
            "step": 1,
            "action": "information_gathering",
            "description": "信息收集 - 查询相关实体",
            "estimated_time": "5分钟",
            "skills_required": ["analyze_domain"]
        })
        plan_steps.append({
            "step": 2,
            "action": "analysis",
            "description": "分析研判 - 生成建议",
            "estimated_time": "3分钟",
            "skills_required": ["analyze_force_comparison"]
        })

    plan = {
        "status": "success",
        "goal": goal,
        "total_steps": len(plan_steps),
        "estimated_total_time": f"{sum([int(s['estimated_time'].split('分钟')[0]) for s in plan_steps])}分钟",
        "steps": plan_steps,
        "constraints": constraints or [],
        "created_at": datetime.now().isoformat()
    }

    return plan

def execute_workflow(workflow_id, context):
    """
    执行工作流

    Args:
        workflow_id: 工作流ID
        context: 执行上下文

    Returns:
        执行结果
    """
    workflow_results = []

    if workflow_id == "attack_workflow":
        step_results = []

        step_results.append({
            "step": 1,
            "action": "reconnaissance",
            "result": "RADAR_01 位置确认，状态活跃",
            "success": True
        })

        step_results.append({
            "step": 2,
            "action": "threat_analysis",
            "result": "威胁等级: 中",
            "success": True
        })

        step_results.append({
            "step": 3,
            "action": "authorization",
            "result": "OPA检查通过",
            "success": True
        })

        step_results.append({
            "step": 4,
            "action": "strike_execution",
            "result": "打击指令已下发",
            "success": True
        })

        workflow_results = step_results

    elif workflow_id == "reconnaissance_workflow":
        step_results = []

        step_results.append({
            "step": 1,
            "action": "area_scan",
            "result": "扫描完成，发现3个目标",
            "success": True
        })

        step_results.append({
            "step": 2,
            "action": "data_collection",
            "result": "数据已记录",
            "success": True
        })

        workflow_results = step_results

    else:
        return {"status": "error", "message": f"未知工作流: {workflow_id}"}

    return {
        "status": "success",
        "workflow_id": workflow_id,
        "total_steps": len(workflow_results),
        "completed_steps": len([r for r in workflow_results if r.get("success")]),
        "results": workflow_results,
        "context": context
    }

def validate_plan(plan):
    """
    验证计划可行性

    Args:
        plan: 执行计划

    Returns:
        验证结果
    """
    if not plan or "steps" not in plan:
        return {"status": "error", "message": "无效的计划格式"}

    issues = []
    warnings = []

    for step in plan.get("steps", []):
        if "skills_required" in step:
            for skill in step["skills_required"]:
                if skill not in ["search_radar", "analyze_domain", "analyze_threat_level",
                                "check_strike_risk", "check_permission", "simulate_policy_execution",
                                "attack_target", "calculate_strike_damage", "analyze_entity_status",
                                "analyze_force_comparison"]:
                    warnings.append(f"技能 {skill} 可能不可用")

    if len(plan.get("steps", [])) > 10:
        issues.append("计划步骤过多，可能影响执行效率")

    return {
        "status": "success" if not issues else "warning",
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "recommendation": "计划可行" if not issues else "请修正计划后重试"
    }

def estimate_resources(plan):
    """
    估算资源需求

    Args:
        plan: 执行计划

    Returns:
        资源估算
    """
    total_time = 0
    skill_usage = {}

    for step in plan.get("steps", []):
        time_str = step.get("estimated_time", "0分钟")
        time_minutes = int(time_str.split("分钟")[0])
        total_time += time_minutes

        for skill in step.get("skills_required", []):
            skill_usage[skill] = skill_usage.get(skill, 0) + 1

    return {
        "status": "success",
        "total_time_minutes": total_time,
        "skill_usage": skill_usage,
        "estimated_personnel": 1 if total_time < 30 else 2,
        "estimated_cost": "low" if total_time < 30 else "medium" if total_time < 60 else "high"
    }

register_skill(
    name="create_plan",
    description="创建执行计划",
    handler=create_plan,
    category="planning")


register_skill(
    name="execute_workflow",
    description="执行工作流",
    handler=execute_workflow,
    category="planning")


register_skill(
    name="validate_plan",
    description="验证计划可行性",
    handler=validate_plan,
    category="planning")


register_skill(
    name="estimate_resources",
    description="估算资源需求",
    handler=estimate_resources,
    category="planning")
