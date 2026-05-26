"""场景管理服务"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.scenario import Scenario
from ..storage import Storage
from odap.biz.core.ontology.models.ontology import OntologyDocument


class ScenarioService:
    """场景管理服务"""
    
    def __init__(self):
        self.storage = Storage()
    
    def create_scenario(self, workspace_id: str, name: str, description: str = "", ontology_id: Optional[str] = None, status: str = "draft", tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """创建场景"""
        now = datetime.now().isoformat()
        scenario_id = f"scenario-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
        
        if not ontology_id:
            ontology_name = f"{name}_Ontology"
            ontology_description = f"自动创建的本体 for 场景: {name}"
            ontology_doc = OntologyDocument(name=ontology_name, description=ontology_description)
            ontology_id = ontology_doc.id
        
        scenario = {
            'scenario_id': scenario_id,
            'name': name,
            'description': description,
            'workspace_id': workspace_id,
            'status': status,
            'tags': tags or [],
            'ontology_id': ontology_id,
            'ontology_ids': [ontology_id],
            'doc_count': 0,
            'event_count': 0,
            'entity_count': 0,
            'created_at': now,
            'updated_at': now
        }
        
        self.storage.save_scenario(scenario)
        self.storage.bind_ontology_to_scenario(scenario_id, ontology_id, bound_by='system')
        self._ensure_initial_version(ontology_id, name)
        return scenario

    def _ensure_initial_version(self, ontology_id: str, scenario_name: str = "") -> None:
        """确保本体有初始版本"""
        try:
            from odap.biz.core.ontology.version_manager import OntologyVersionManager
            vm = OntologyVersionManager.get_instance()
            vm.ensure_initial_version(ontology_id, scenario_name)
        except Exception:
            pass
    
    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取场景"""
        return self.storage.get_scenario(scenario_id)
    
    def get_scenarios_by_workspace(self, workspace_id: str, page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """获取工作空间下的所有场景"""
        return self.storage.get_scenarios_by_workspace(workspace_id, page, page_size)
    
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
    
    def bind_ontology(self, scenario_id: str, ontology_id: str, bound_by: str = 'system') -> Dict[str, Any]:
        """绑定本体（追加式）"""
        scenario = self.storage.get_scenario(scenario_id)
        if not scenario:
            return {"status": "error", "message": f"场景 {scenario_id} 不存在"}
        
        result = self.storage.bind_ontology_to_scenario(scenario_id, ontology_id, bound_by)
        self._ensure_initial_version(ontology_id, scenario.get('name', ''))
        return result
    
    def unbind_ontology(self, scenario_id: str, ontology_id: str) -> Dict[str, Any]:
        """解绑本体"""
        scenario = self.storage.get_scenario(scenario_id)
        if not scenario:
            return {"status": "error", "message": f"场景 {scenario_id} 不存在"}
        
        bindings = self.storage.get_scenario_ontology_bindings(scenario_id)
        active_binding = None
        for b in bindings:
            if b.get('ontology_id') == ontology_id and b.get('binding_status') == 'active':
                active_binding = b
                break
        
        if not active_binding:
            return {"status": "error", "message": f"本体 {ontology_id} 未绑定到场景 {scenario_id}"}
        
        success = self.storage.unbind_ontology_from_scenario(scenario_id, ontology_id)
        if not success:
            return {"status": "error", "message": "解绑失败"}
        
        remaining = [oid for oid in scenario.get('ontology_ids', []) if oid != ontology_id]
        if scenario.get('ontology_id') == ontology_id:
            new_primary = remaining[0] if remaining else None
            self.storage.update_scenario(scenario_id, {'ontology_id': new_primary})
        
        return {"status": "success", "message": f"本体 {ontology_id} 已从场景 {scenario_id} 解绑"}
    
    def get_scenario_ontologies(self, scenario_id: str) -> Dict[str, Any]:
        """获取场景绑定的所有本体"""
        scenario = self.storage.get_scenario(scenario_id)
        if not scenario:
            return {"status": "error", "message": f"场景 {scenario_id} 不存在"}
        
        bindings = self.storage.get_scenario_ontology_bindings(scenario_id)
        return {"scenario_id": scenario_id, "bindings": bindings, "total": len(bindings)}
    
    def _extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中抽取实体（简单规则实现）"""
        import re
        entities = []
        
        # 抽取可能的人名（中文和简单英文）
        chinese_name_pattern = r'[张王李赵钱孙周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张][\u4e00-\u9fa5]{1,2}'
        chinese_names = re.findall(chinese_name_pattern, text)
        for name in chinese_names:
            entities.append({
                "id": f"person_{name}_{hash(name)}",
                "type": "Person",
                "name": name,
                "properties": {"source": "text_extraction"}
            })
        
        # 抽取组织名（简单匹配）
        org_keywords = ["公司", "集团", "科技", "有限", "股份", "大学", "学院", "医院", "银行", "政府"]
        for keyword in org_keywords:
            if keyword in text:
                # 简单抽取包含关键词的片段
                parts = text.split(keyword)
                for i in range(len(parts)-1):
                    before = parts[i][-5:] if len(parts[i])>5 else parts[i]
                    org_name = before + keyword
                    if len(org_name) >= 3:
                        entities.append({
                            "id": f"org_{org_name}_{hash(org_name)}",
                            "type": "Organization",
                            "name": org_name,
                            "properties": {"source": "text_extraction"}
                        })
        
        # 抽取地点名
        location_keywords = ["北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉", "西安", "重庆", "天津"]
        for city in location_keywords:
            if city in text:
                entities.append({
                    "id": f"loc_{city}_{hash(city)}",
                    "type": "Location",
                    "name": city,
                    "properties": {"source": "text_extraction"}
                })
        
        # 去重
        seen_ids = set()
        unique_entities = []
        for entity in entities:
            if entity["id"] not in seen_ids:
                seen_ids.add(entity["id"])
                unique_entities.append(entity)
        
        return unique_entities
    
    def build_graph_from_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """从场景数据构建图谱"""
        scenario = self.storage.get_scenario(scenario_id)
        if not scenario:
            return {"status": "error", "message": f"场景 {scenario_id} 不存在"}
        
        ontology_id = scenario.get("ontology_id")
        if not ontology_id:
            return {"status": "error", "message": "场景没有关联的本体"}
        
        documents = self.storage.get_scenario_documents(scenario_id)
        
        all_entities = []
        all_events = []
        
        for doc in documents:
            doc_type = doc.get("doc_type")
            data = doc.get("data", {})
            
            if doc_type == "news" or doc_type == "text":
                text = data.get("content", "") or data.get("text", "")
                if text:
                    extracted_entities = self._extract_entities_from_text(text)
                    all_entities.extend(extracted_entities)
                
                title = data.get("title", "")
                if title:
                    all_events.append({
                        "id": f"event_{datetime.now().strftime('%s')}_{doc.get('scenario_id')}",
                        "title": title,
                        "type": "News",
                        "timestamp": data.get("published_date", datetime.now().isoformat()),
                        "properties": {"source": doc_type}
                    })
        
        # 去重实体
        seen_ids = set()
        unique_entities = []
        for entity in all_entities:
            if entity["id"] not in seen_ids:
                seen_ids.add(entity["id"])
                unique_entities.append(entity)
        
        # 更新本体（简化实现）
        updates = {
            "entities": unique_entities,
            "events": all_events,
            "updated_at": datetime.now().isoformat()
        }
        
        # 简化处理：创建新的 OntologyDocument
        ontology_doc = OntologyDocument(
            id=ontology_id,
            name=f"Ontology_{scenario_id}",
            description=f"Ontology for scenario {scenario_id}",
            entities=unique_entities,
            relations=[]
        )
        
        # 更新场景统计
        scenario["entity_count"] = len(unique_entities)
        scenario["event_count"] = len(all_events)
        scenario["updated_at"] = datetime.now().isoformat()
        
        self.storage.update_scenario(scenario_id, scenario)
        
        return {
            "status": "success",
            "scenario_id": scenario_id,
            "ontology_id": ontology_id,
            "entity_count": len(unique_entities),
            "event_count": len(all_events),
            "entities": unique_entities[:10]  # 返回前10个实体作为预览
        }
