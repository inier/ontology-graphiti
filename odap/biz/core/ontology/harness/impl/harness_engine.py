import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..storage import SQLiteHarnessStorage
from ..models import (
    HarnessSession, HarnessStage, StageStatus, StageResult,
    HITLConfirmation, HITLRiskLevel, AgentTask,
    OntologyBlueprint, BlueprintNode, BlueprintEdge,
    AgentRole, AgentMessage, SubTask,
    RequirementAnalysis, OntologySuggestion,
)

logger = logging.getLogger("harness_engine")

STAGE_ORDER = [
    HarnessStage.DATA_SELECTION,
    HarnessStage.DATA_PROCESSING,
    HarnessStage.ONTOLOGY_MODELING,
    HarnessStage.QUERY_DESIGN,
    HarnessStage.API_SKILL_EXPORT,
    HarnessStage.VALIDATION,
]

HIGH_RISK_OPERATIONS = {"delete", "remove", "bulk_update", "schema_change"}

NOUN_PATTERNS = re.compile(r"[\u4e00-\u9fff]{2,6}|[A-Za-z]+")
RELATION_VERBS = ["管理", "分析", "处理", "关联", "映射", "匹配", "同步", "依赖", "包含", "属于", "引用", "触发", "订阅", "推送", "调用", "访问", "监控", "校验", "转换", "聚合"]
ACTION_VERBS = ["创建", "删除", "更新", "查询", "导入", "导出", "审批", "部署", "执行", "配置", "启动", "停止", "重启", "备份", "恢复", "迁移", "发布", "订阅", "通知", "告警"]

WORKFLOW_STAGES = [
    {"stage": "requirement_analysis", "label": "需求分析", "description": "解析自然语言需求，提取业务对象与关系"},
    {"stage": "business_validation", "label": "业务校验", "description": "校验需求完整性与一致性"},
    {"stage": "etl", "label": "ETL", "description": "数据抽取、转换、加载"},
    {"stage": "graph_mapping", "label": "数据图谱映射", "description": "将业务数据映射到图谱结构"},
    {"stage": "graph_construction", "label": "图谱构建", "description": "构建知识图谱"},
    {"stage": "ontology_modeling", "label": "本体建模", "description": "基于图谱数据构建本体模型"},
    {"stage": "business_interface", "label": "业务接口", "description": "生成业务API与Skill接口"},
]


class HarnessEngine:
    def __init__(self, storage: SQLiteHarnessStorage = None):
        self.storage = storage or SQLiteHarnessStorage()

    def create_session(self, name: str, description: str = "", scenario_id: Optional[str] = None, workspace_id: Optional[str] = None, requirement: str = "") -> Dict[str, Any]:
        session = HarnessSession(
            name=name,
            description=description,
            scenario_id=scenario_id,
            workspace_id=workspace_id,
            requirement=requirement,
            stage_results=[StageResult(stage=s) for s in STAGE_ORDER],
        )
        now = datetime.now().isoformat()
        session.created_at = now
        session.updated_at = now
        return self.storage.save_session(session.model_dump())

    def get_session(self, session_id: str) -> Dict[str, Any]:
        result = self.storage.get_session(session_id)
        if not result:
            return {"status": "error", "message": f"Session {session_id} not found"}
        return result

    def list_sessions(self, status: Optional[str] = None, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        sessions = self.storage.list_sessions(status=status, scenario_id=scenario_id)
        return {"sessions": sessions, "count": len(sessions)}

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        if self.storage.delete_session(session_id):
            return {"status": "success", "message": f"Session {session_id} deleted"}
        return {"status": "error", "message": f"Session {session_id} not found"}

    def advance_stage(self, session_id: str, stage_output: Dict[str, Any] = None) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        current = session_data.get("current_stage", HarnessStage.DATA_SELECTION.value)
        stage_results = session_data.get("stage_results", [])
        current_idx = -1
        for i, sr in enumerate(stage_results):
            if sr.get("stage") == current and sr.get("status") != StageStatus.COMPLETED.value:
                sr["status"] = StageStatus.COMPLETED.value
                sr["completed_at"] = datetime.now().isoformat()
                if stage_output:
                    sr["output"] = stage_output
                current_idx = i
                break
        if current_idx < 0:
            return {"status": "error", "message": f"Cannot advance: current stage {current} not found or already completed"}
        if current_idx + 1 < len(stage_results):
            next_stage = stage_results[current_idx + 1]
            session_data["current_stage"] = next_stage["stage"]
            next_stage["status"] = StageStatus.RUNNING.value
            next_stage["started_at"] = datetime.now().isoformat()
        else:
            session_data["status"] = StageStatus.COMPLETED.value
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return session_data

    def fail_stage(self, session_id: str, error: str) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        current = session_data.get("current_stage")
        for sr in session_data.get("stage_results", []):
            if sr.get("stage") == current:
                sr["status"] = StageStatus.FAILED.value
                sr["errors"].append(error)
                break
        session_data["status"] = StageStatus.FAILED.value
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return session_data

    def create_hitl_confirmation(self, session_id: str, stage: str, risk_level: str, title: str, description: str, affected_objects: List[str] = None) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        confirmation = HITLConfirmation(
            stage=stage,
            risk_level=risk_level,
            title=title,
            description=description,
            affected_objects=affected_objects or [],
        )
        session_data["hitl_confirmations"].append(confirmation.model_dump())
        for sr in session_data.get("stage_results", []):
            if sr.get("stage") == stage:
                sr["status"] = StageStatus.HITL_PENDING.value
                break
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return confirmation.model_dump()

    def resolve_hitl(self, session_id: str, confirmation_id: str, resolution: str, resolved_by: str) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        for conf in session_data.get("hitl_confirmations", []):
            if conf.get("confirmation_id") == confirmation_id:
                conf["is_resolved"] = True
                conf["resolution"] = resolution
                conf["resolved_by"] = resolved_by
                conf["resolved_at"] = datetime.now().isoformat()
                break
        for sr in session_data.get("stage_results", []):
            if sr.get("status") == StageStatus.HITL_PENDING.value:
                sr["status"] = StageStatus.APPROVED.value
                break
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return {"status": "success", "confirmation_id": confirmation_id, "resolution": resolution}

    def add_agent_task(self, session_id: str, agent_type: str, stage: str, description: str, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        task = AgentTask(
            agent_type=agent_type,
            stage=stage,
            description=description,
            input_data=input_data or {},
        )
        session_data["agent_tasks"].append(task.model_dump())
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return task.model_dump()

    def update_agent_task(self, session_id: str, task_id: str, output_data: Dict[str, Any] = None, status: str = None, error: str = None) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        for task in session_data.get("agent_tasks", []):
            if task.get("task_id") == task_id:
                if output_data:
                    task["output_data"] = output_data
                if status:
                    task["status"] = status
                if error:
                    task["error"] = error
                break
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return {"status": "success", "task_id": task_id}

    def run_planning(self, session_id: str) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        requirement = session_data.get("requirement", "")
        if not requirement:
            return {"status": "error", "message": "Requirement is empty"}

        analysis = self._parse_requirement(requirement)
        sub_task = SubTask(
            agent_role=AgentRole.PLANNING,
            description="Planning agent: parse requirement and extract business objects/relationships",
            input_data={"requirement": requirement},
            output_data=analysis,
            status=StageStatus.COMPLETED,
            completed_at=datetime.now().isoformat(),
        )
        session_data["sub_tasks"] = session_data.get("sub_tasks", [])
        session_data["sub_tasks"].append(sub_task.model_dump())
        session_data["planning_output"] = analysis
        session_data["context_memory"]["planning"] = analysis
        msg = AgentMessage(
            from_agent="planning_agent",
            to_agent="ontology_agent",
            message_type="planning_result",
            content=analysis,
        )
        session_data["messages"] = session_data.get("messages", [])
        session_data["messages"].append(msg.model_dump())
        session_data["status"] = StageStatus.RUNNING.value
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return session_data

    def run_ontology_modeling(self, session_id: str) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        planning_output = session_data.get("planning_output", {})
        if not planning_output:
            return {"status": "error", "message": "Planning output is empty, run planning first"}

        suggestions = self._generate_ontology_suggestions(planning_output)
        sub_task = SubTask(
            agent_role=AgentRole.ONTOLOGY,
            description="Ontology agent: generate ontology modeling suggestions",
            input_data={"planning_output": planning_output},
            output_data=suggestions,
            status=StageStatus.COMPLETED,
            completed_at=datetime.now().isoformat(),
        )
        session_data["sub_tasks"] = session_data.get("sub_tasks", [])
        session_data["sub_tasks"].append(sub_task.model_dump())
        session_data["ontology_output"] = suggestions
        session_data["context_memory"]["ontology"] = suggestions
        msg = AgentMessage(
            from_agent="ontology_agent",
            to_agent="executor_agent",
            message_type="ontology_result",
            content=suggestions,
        )
        session_data["messages"] = session_data.get("messages", [])
        session_data["messages"].append(msg.model_dump())
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return session_data

    def run_execution(self, session_id: str) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        ontology_output = session_data.get("ontology_output", {})
        if not ontology_output:
            return {"status": "error", "message": "Ontology output is empty, run ontology modeling first"}

        workflow = self._generate_workflow_nodes(ontology_output)
        execution_result = {
            "workflow": workflow,
            "blueprint": {
                "nodes": workflow,
                "edges": self._generate_workflow_edges(workflow),
            },
        }
        sub_task = SubTask(
            agent_role=AgentRole.EXECUTOR,
            description="Executor agent: generate workflow blueprint and executable code",
            input_data={"ontology_output": ontology_output},
            output_data=execution_result,
            status=StageStatus.COMPLETED,
            completed_at=datetime.now().isoformat(),
        )
        session_data["sub_tasks"] = session_data.get("sub_tasks", [])
        session_data["sub_tasks"].append(sub_task.model_dump())
        session_data["execution_output"] = execution_result
        session_data["context_memory"]["execution"] = execution_result
        msg = AgentMessage(
            from_agent="executor_agent",
            to_agent="validator_agent",
            message_type="execution_result",
            content=execution_result,
        )
        session_data["messages"] = session_data.get("messages", [])
        session_data["messages"].append(msg.model_dump())
        session_data["status"] = StageStatus.HITL_PENDING.value
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return session_data

    def run_full_pipeline(self, session_id: str) -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}

        planning_result = self.run_planning(session_id)
        if planning_result.get("status") == "error":
            return planning_result

        session_data = self.storage.get_session(session_id)
        ontology_result = self.run_ontology_modeling(session_id)
        if ontology_result.get("status") == "error":
            return ontology_result

        session_data = self.storage.get_session(session_id)
        execution_result = self.run_execution(session_id)
        if execution_result.get("status") == "error":
            return execution_result

        final_session = self.storage.get_session(session_id)
        final_session["status"] = StageStatus.HITL_PENDING.value
        final_session["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(final_session)
        return final_session

    def approve_step(self, session_id: str, stage: str, approved_by: str = "") -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        msg = AgentMessage(
            from_agent="human",
            to_agent="system",
            message_type="approval",
            content={"step": stage, "action": "approve", "approved_by": approved_by},
        )
        session_data["messages"] = session_data.get("messages", [])
        session_data["messages"].append(msg.model_dump())
        session_data["context_memory"]["approvals"] = session_data["context_memory"].get("approvals", [])
        session_data["context_memory"]["approvals"].append({"step": stage, "action": "approved", "approved_by": approved_by})
        if stage == "execution" and session_data.get("status") == StageStatus.HITL_PENDING.value:
            session_data["status"] = StageStatus.COMPLETED.value
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return session_data

    def reject_step(self, session_id: str, stage: str, reason: str = "") -> Dict[str, Any]:
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        msg = AgentMessage(
            from_agent="human",
            to_agent="system",
            message_type="rejection",
            content={"step": stage, "action": "reject", "reason": reason},
        )
        session_data["messages"] = session_data.get("messages", [])
        session_data["messages"].append(msg.model_dump())
        session_data["context_memory"]["rejections"] = session_data["context_memory"].get("rejections", [])
        session_data["context_memory"]["rejections"].append({"step": stage, "action": "rejected", "reason": reason})
        session_data["status"] = StageStatus.FAILED.value
        session_data["updated_at"] = datetime.now().isoformat()
        self.storage.save_session(session_data)
        return session_data

    def create_blueprint(self, name: str, description: str = "", session_id: Optional[str] = None) -> Dict[str, Any]:
        default_nodes = [
            BlueprintNode(node_type="data_source", label="数据源", stage=HarnessStage.DATA_SELECTION, position_x=100, position_y=100),
            BlueprintNode(node_type="data_process", label="数据处理", stage=HarnessStage.DATA_PROCESSING, position_x=300, position_y=100),
            BlueprintNode(node_type="ontology_model", label="本体建模", stage=HarnessStage.ONTOLOGY_MODELING, position_x=500, position_y=100),
            BlueprintNode(node_type="query_design", label="查询设计", stage=HarnessStage.QUERY_DESIGN, position_x=700, position_y=100),
            BlueprintNode(node_type="skill_export", label="Skill/API导出", stage=HarnessStage.API_SKILL_EXPORT, position_x=900, position_y=100),
            BlueprintNode(node_type="validation", label="验证", stage=HarnessStage.VALIDATION, position_x=1100, position_y=100),
        ]
        default_edges = []
        for i in range(len(default_nodes) - 1):
            default_edges.append(BlueprintEdge(
                source_node_id=default_nodes[i].node_id,
                target_node_id=default_nodes[i + 1].node_id,
            ))
        bp = OntologyBlueprint(
            name=name,
            description=description,
            session_id=session_id,
            nodes=default_nodes,
            edges=default_edges,
        )
        return self.storage.save_blueprint(bp.model_dump())

    def get_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        result = self.storage.get_blueprint(blueprint_id)
        if not result:
            return {"status": "error", "message": f"Blueprint {blueprint_id} not found"}
        return result

    def list_blueprints(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        blueprints = self.storage.list_blueprints(session_id=session_id)
        return {"blueprints": blueprints, "count": len(blueprints)}

    def _parse_requirement(self, requirement: str) -> Dict[str, Any]:
        nouns = list(set(NOUN_PATTERNS.findall(requirement)))
        business_objects = []
        for noun in nouns[:20]:
            obj = {"name": noun, "type": "entity", "properties": [], "description": noun}
            for verb in RELATION_VERBS:
                if verb in requirement and noun in requirement:
                    obj["type"] = "core_entity"
                    break
            business_objects.append(obj)

        relationships = []
        for verb in RELATION_VERBS:
            if verb in requirement:
                related = [n for n in nouns if n in requirement]
                if len(related) >= 2:
                    relationships.append({
                        "name": verb,
                        "source": related[0],
                        "target": related[1],
                        "type": "relation",
                    })

        actions = []
        for verb in ACTION_VERBS:
            if verb in requirement:
                targets = [n for n in nouns if n in requirement]
                actions.append({
                    "name": f"{verb}{targets[0]}" if targets else verb,
                    "verb": verb,
                    "target": targets[0] if targets else "",
                    "type": "action",
                })

        processing_needs = []
        if any(w in requirement for w in ["实时", "实时性", "流式"]):
            processing_needs.append({"type": "realtime", "description": "实时处理需求"})
        if any(w in requirement for w in ["批量", "离线", "定时"]):
            processing_needs.append({"type": "batch", "description": "批量处理需求"})
        if any(w in requirement for w in ["分析", "统计", "报表"]):
            processing_needs.append({"type": "analytics", "description": "分析统计需求"})

        risks = []
        if len(business_objects) > 10:
            risks.append({"type": "complexity", "description": "业务对象过多，建议分阶段建模"})
        if not relationships:
            risks.append({"type": "missing_relation", "description": "未识别到明确的关系，需人工确认"})

        missing_info = []
        if not business_objects:
            missing_info.append("未识别到业务对象，请补充需求描述")
        if not relationships:
            missing_info.append("未识别到业务关系，请明确对象间关系")

        analysis = RequirementAnalysis(
            business_objects=business_objects,
            relationships=relationships,
            processing_needs=processing_needs,
            risks=risks,
            missing_info=missing_info,
        )
        return analysis.model_dump()

    def _generate_ontology_suggestions(self, planning_output: Dict[str, Any]) -> Dict[str, Any]:
        business_objects = planning_output.get("business_objects", [])
        relationships = planning_output.get("relationships", [])
        actions = planning_output.get("actions", [])

        object_types = []
        for obj in business_objects:
            object_types.append({
                "name": obj.get("name", ""),
                "category": "T" if obj.get("type") == "core_entity" else "P",
                "properties": obj.get("properties", []),
                "description": obj.get("description", ""),
            })

        link_types = []
        for rel in relationships:
            link_types.append({
                "name": rel.get("name", ""),
                "source_type": rel.get("source", ""),
                "target_type": rel.get("target", ""),
                "category": "L",
                "cardinality": "1:N",
            })

        functions = []
        for obj in business_objects[:5]:
            if obj.get("type") == "core_entity":
                functions.append({
                    "name": f"calculate_{obj.get('name', '')}_metric",
                    "category": "F",
                    "input_type": obj.get("name", ""),
                    "output_type": "metric",
                    "description": f"计算{obj.get('name', '')}相关指标",
                })

        action_list = []
        for act in actions:
            action_list.append({
                "name": act.get("name", ""),
                "category": "A",
                "verb": act.get("verb", ""),
                "target": act.get("target", ""),
                "trigger": "manual",
            })

        constraints = []
        if len(object_types) > 0:
            constraints.append({
                "name": "naming_convention",
                "type": "naming",
                "rule": "对象类型名称使用PascalCase",
            })
        if len(link_types) > 0:
            constraints.append({
                "name": "relation_cardinality",
                "type": "cardinality",
                "rule": "关系必须明确基数约束",
            })

        suggestion = OntologySuggestion(
            object_types=object_types,
            link_types=link_types,
            functions=functions,
            actions=action_list,
            constraints=constraints,
        )
        return suggestion.model_dump()

    def _generate_workflow_nodes(self, ontology_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        object_types = ontology_output.get("object_types", [])
        link_types = ontology_output.get("link_types", [])
        functions = ontology_output.get("functions", [])
        actions = ontology_output.get("actions", [])

        nodes = []
        for i, stage_info in enumerate(WORKFLOW_STAGES):
            config = {}
            if stage_info["stage"] == "requirement_analysis":
                config = {"extract_objects": True, "extract_relations": True}
            elif stage_info["stage"] == "business_validation":
                config = {"check_completeness": True, "check_consistency": True}
            elif stage_info["stage"] == "etl":
                config = {"sources": [ot["name"] for ot in object_types[:5]]}
            elif stage_info["stage"] == "graph_mapping":
                config = {"entity_types": [ot["name"] for ot in object_types],
                          "relation_types": [lt["name"] for lt in link_types]}
            elif stage_info["stage"] == "graph_construction":
                config = {"build_method": "incremental"}
            elif stage_info["stage"] == "ontology_modeling":
                config = {"object_types": len(object_types),
                          "link_types": len(link_types),
                          "functions": len(functions),
                          "actions": len(actions)}
            elif stage_info["stage"] == "business_interface":
                config = {"api_endpoints": [a["name"] for a in actions],
                          "skill_exports": [f["name"] for f in functions]}

            nodes.append({
                "node_id": f"wf-{stage_info['stage']}",
                "node_type": stage_info["stage"],
                "label": stage_info["label"],
                "description": stage_info["description"],
                "position_x": i * 200,
                "position_y": 100,
                "config": config,
            })
        return nodes

    def _generate_workflow_edges(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        edges = []
        for i in range(len(nodes) - 1):
            edges.append({
                "edge_id": f"edge-{nodes[i]['node_id']}-{nodes[i + 1]['node_id']}",
                "source_node_id": nodes[i]["node_id"],
                "target_node_id": nodes[i + 1]["node_id"],
                "label": "",
                "data_mapping": {},
            })
        return edges
