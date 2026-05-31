import logging
import uuid
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class QueryPlanner:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._task_templates = {
            "query": [
                {"step": 1, "task_type": "intent_recognition", "description": "识别查询意图"},
                {"step": 2, "task_type": "entity_extraction", "description": "提取实体"},
                {"step": 3, "task_type": "knowledge_retrieval", "description": "知识检索"},
                {"step": 4, "task_type": "result_formatting", "description": "结果格式化"},
            ],
            "action": [
                {"step": 1, "task_type": "intent_recognition", "description": "识别操作意图"},
                {"step": 2, "task_type": "permission_check", "description": "权限检查"},
                {"step": 3, "task_type": "action_execution", "description": "执行操作"},
                {"step": 4, "task_type": "result_validation", "description": "结果验证"},
            ],
            "explain": [
                {"step": 1, "task_type": "intent_recognition", "description": "识别解释意图"},
                {"step": 2, "task_type": "context_gathering", "description": "收集上下文"},
                {"step": 3, "task_type": "reasoning_chain", "description": "构建推理链"},
                {"step": 4, "task_type": "explanation_generation", "description": "生成解释"},
            ],
            "recommend": [
                {"step": 1, "task_type": "intent_recognition", "description": "识别推荐意图"},
                {"step": 2, "task_type": "context_analysis", "description": "上下文分析"},
                {"step": 3, "task_type": "candidate_generation", "description": "候选生成"},
                {"step": 4, "task_type": "ranking", "description": "排序推荐"},
            ],
            "analyze": [
                {"step": 1, "task_type": "intent_recognition", "description": "识别分析意图"},
                {"step": 2, "task_type": "data_collection", "description": "数据收集"},
                {"step": 3, "task_type": "pattern_analysis", "description": "模式分析"},
                {"step": 4, "task_type": "report_generation", "description": "报告生成"},
            ],
            "compare": [
                {"step": 1, "task_type": "intent_recognition", "description": "识别对比意图"},
                {"step": 2, "task_type": "entity_identification", "description": "实体识别"},
                {"step": 3, "task_type": "feature_extraction", "description": "特征提取"},
                {"step": 4, "task_type": "comparison_generation", "description": "对比生成"},
            ],
        }
        self._initialized = True

    def plan(self, structured_query: Dict[str, Any]) -> Dict[str, Any]:
        intent = structured_query.get("intent", "query")
        template = self._task_templates.get(intent, self._task_templates["query"])
        tasks = []
        for step in template:
            task = {
                "task_id": str(uuid.uuid4()),
                "step": step["step"],
                "task_type": step["task_type"],
                "description": step["description"],
                "status": "pending",
                "input": {},
                "output": {},
            }
            if step["step"] == 1:
                task["input"] = {
                    "intent": structured_query.get("intent"),
                    "entities": structured_query.get("entities", []),
                    "filters": structured_query.get("filters", {}),
                }
            tasks.append(task)

        return {
            "plan_id": str(uuid.uuid4()),
            "intent": intent,
            "tasks": tasks,
            "total_steps": len(tasks),
        }
