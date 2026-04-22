"""场景管理服务"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.scenario import Scenario
from ..storage import Storage
from odap.biz.ontology.services.build_service import OntologyBuildService


class ScenarioService:
    """场景管理服务"""
    
    def __init__(self):
        self.storage = Storage()
        self.ontology_service = OntologyBuildService()
    
    def create_scenario(self, workspace_id: str, name: str, description: str = "", ontology_id: Optional[str] = None) -> Dict[str, Any]:
        """创建场景"""
        now = datetime.now().isoformat()
        scenario_id = f"scenario-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
        
        # 如果没有提供本体ID，自动创建一个新本体
        if not ontology_id:
            ontology_name = f"{name}_Ontology"
            ontology_description = f"自动创建的本体 for 场景: {name}"
            ontology_doc = self.ontology_service.create_ontology(ontology_name, ontology_description)
            ontology_id = ontology_doc.id
        
        scenario = {
            'scenario_id': scenario_id,
            'name': name,
            'description': description,
            'workspace_id': workspace_id,
            'ontology_id': ontology_id,
            'doc_count': 0,
            'event_count': 0,
            'entity_count': 0,
            'created_at': now,
            'updated_at': now
        }
        
        self.storage.save_scenario(scenario)
        return scenario
    
    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取场景"""
        return self.storage.get_scenario(scenario_id)
    
    def get_scenarios_by_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        """获取工作空间下的所有场景"""
        return self.storage.get_scenarios_by_workspace(workspace_id)
    
    def update_scenario(self, scenario_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新场景"""
        self.storage.update_scenario(scenario_id, updates)
        scenario = self.storage.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        return scenario
    
    def delete_scenario(self, scenario_id: str) -> bool:
        """删除场景"""
        scenario = self.storage.get_scenario(scenario_id)
        if not scenario:
            return False
        
        self.storage.delete_scenario(scenario_id)
        return True
    
    def bind_ontology(self, scenario_id: str, ontology_id: str) -> Dict[str, Any]:
        """绑定本体"""
        return self.update_scenario(scenario_id, {'ontology_id': ontology_id})
