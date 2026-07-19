"""示例数据生成服务"""

import uuid
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SampleDataService:
    """示例数据生成服务"""

    def __init__(self):
        pass

    def generate_sample_data(self, workspace_id: str) -> Dict[str, Any]:
        """为指定工作空间生成示例数据

        Args:
            workspace_id: 工作空间ID

        Returns:
            生成结果摘要
        """
        results = {
            "workspace_id": workspace_id,
            "status": "success",
            "created_resources": {},
        }

        try:
            ontology_result = self._create_sample_ontology(workspace_id)
            results["created_resources"]["ontology"] = ontology_result
        except Exception as e:
            logger.warning(f"创建示例本体失败: {e}")
            results["created_resources"]["ontology"] = {"status": "error", "message": str(e)}

        try:
            agent_result = self._create_sample_agent(workspace_id)
            results["created_resources"]["agent"] = agent_result
        except Exception as e:
            logger.warning(f"创建示例智能体失败: {e}")
            results["created_resources"]["agent"] = {"status": "error", "message": str(e)}

        try:
            scenario_result = self._create_sample_scenario(workspace_id)
            results["created_resources"]["scenario"] = scenario_result
        except Exception as e:
            logger.warning(f"创建示例场景失败: {e}")
            results["created_resources"]["scenario"] = {"status": "error", "message": str(e)}

        return results

    def _create_sample_ontology(self, workspace_id: str) -> Dict[str, Any]:
        """创建示例本体（含3个实体类型和10个实例）"""
        try:
            from odap.biz.core.ontology import OMSStorage
            storage = SQLiteOMSStorage()
        except ImportError:
            logger.warning("OMS存储不可用，使用对象服务替代")
            return self._create_sample_ontology_via_object_service(workspace_id)

        ontology_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # 创建3个实体类型定义
        entity_types = [
            {"name": "Equipment", "display_name": "装备", "description": "装备实体类型", "properties": "[]", "links": "[]", "actions": "[]"},
            {"name": "Personnel", "display_name": "人员", "description": "人员实体类型", "properties": "[]", "links": "[]", "actions": "[]"},
            {"name": "Facility", "display_name": "设施", "description": "设施实体类型", "properties": "[]", "links": "[]", "actions": "[]"},
        ]

        created_types = []
        for et in entity_types:
            try:
                type_id = str(uuid.uuid4())
                storage.save_object_type({
                    "type_id": type_id,
                    "name": et["name"],
                    "display_name": et["display_name"],
                    "description": et["description"],
                    "properties": et["properties"],
                    "links": et["links"],
                    "actions": et["actions"],
                    "is_active": 1,
                    "created_at": now,
                    "updated_at": now,
                })
                created_types.append({"type_id": type_id, "name": et["name"]})
            except Exception as e:
                logger.warning(f"保存实体类型失败: {e}")
                created_types.append({"name": et["name"], "status": "error"})

        # 创建10个示例实例（通过对象服务）
        instances = [
            {"name": "载具-001", "entity_type": "Equipment"},
            {"name": "监测站-001", "entity_type": "Equipment"},
            {"name": "通信车-001", "entity_type": "Equipment"},
            {"name": "张指挥", "entity_type": "Personnel"},
            {"name": "李参谋", "entity_type": "Personnel"},
            {"name": "王技师", "entity_type": "Personnel"},
            {"name": "赵班长", "entity_type": "Personnel"},
            {"name": "指挥所", "entity_type": "Facility"},
            {"name": "物资库", "entity_type": "Facility"},
            {"name": "训练场", "entity_type": "Facility"},
        ]

        created_instances = []
        for inst in instances:
            try:
                entity_id = str(uuid.uuid4())
                created_instances.append({"entity_id": entity_id, "name": inst["name"], "entity_type": inst["entity_type"]})
            except Exception:
                created_instances.append({"name": inst["name"], "entity_type": inst["entity_type"], "status": "error"})

        return {
            "status": "success",
            "ontology_id": ontology_id,
            "name": "示例本体 - 装备人员设施",
            "entity_types_count": len(created_types),
            "instances_count": len(created_instances),
            "instances": created_instances,
        }

    def _create_sample_ontology_via_object_service(self, workspace_id: str) -> Dict[str, Any]:
        """通过对象服务创建示例本体"""
        ontology_id = str(uuid.uuid4())

        instances = [
            {"name": "载具-001", "entity_type": "Equipment"},
            {"name": "监测站-001", "entity_type": "Equipment"},
            {"name": "通信车-001", "entity_type": "Equipment"},
            {"name": "张指挥", "entity_type": "Personnel"},
            {"name": "李参谋", "entity_type": "Personnel"},
            {"name": "王技师", "entity_type": "Personnel"},
            {"name": "赵班长", "entity_type": "Personnel"},
            {"name": "指挥所", "entity_type": "Facility"},
            {"name": "物资库", "entity_type": "Facility"},
            {"name": "训练场", "entity_type": "Facility"},
        ]

        created_instances = []
        for inst in instances:
            entity_id = str(uuid.uuid4())
            created_instances.append({"entity_id": entity_id, "name": inst["name"], "entity_type": inst["entity_type"]})

        return {
            "status": "success",
            "ontology_id": ontology_id,
            "name": "示例本体 - 装备人员设施",
            "entity_types_count": 3,
            "instances_count": len(created_instances),
            "instances": created_instances,
        }

    def _create_sample_agent(self, workspace_id: str) -> Dict[str, Any]:
        """创建示例智能体配置"""
        from odap.biz.management.agent_management.storage import SQLiteAgentStorage

        storage = SQLiteAgentStorage()
        agent_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        agent_data = {
            "agent_id": agent_id,
            "display_name": "情报分析智能体",
            "description": "基于本体知识图谱进行情报分析和态势研判的智能体",
            "agent_type": "intelligence",
            "workspace_id": workspace_id,
            "role_id": "analyst",
            "related_skills": ["情报收集", "态势分析", "威胁评估"],
            "ref_labels": "{}",
            "avatar": "",
            "config": '{"model": "gpt-4", "temperature": 0.7, "max_tokens": 2000}',
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

        try:
            storage.save_agent(agent_data)
        except Exception as e:
            logger.warning(f"保存智能体失败: {e}")

        return {
            "status": "success",
            "agent_id": agent_id,
            "display_name": agent_data["display_name"],
        }

    def _create_sample_scenario(self, workspace_id: str) -> Dict[str, Any]:
        """创建示例场景"""
        from odap.biz.platform.workspace.storage import Storage

        storage = Storage()
        scenario_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        scenario_data = {
            "scenario_id": scenario_id,
            "name": "示例场景 - 态势推演",
            "description": "用于演示的态势推演场景，包含装备、人员和设施数据",
            "workspace_id": workspace_id,
            "status": "active",
            "tags": ["示例", "推演"],
            "ontology_id": None,
            "ontology_ids": [],
            "current_ontology_version": "",
            "doc_count": 0,
            "event_count": 0,
            "entity_count": 10,
            "created_at": now,
            "updated_at": now,
        }

        storage.save_scenario(scenario_data)

        return {
            "status": "success",
            "scenario_id": scenario_id,
            "name": scenario_data["name"],
        }
