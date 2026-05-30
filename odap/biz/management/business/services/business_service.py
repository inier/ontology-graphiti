from typing import Dict, Any, List, Optional

from ..storage.sqlite_storage import BusinessStorage


class BusinessService:
    _instance = None

    @classmethod
    def get_instance(cls) -> "BusinessService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, storage: BusinessStorage = None):
        self._storage = storage or BusinessStorage()

    def list_processes(self, ontology_id: str = None, version_id: str = None) -> List[Dict[str, Any]]:
        return self._storage.list_processes(ontology_id=ontology_id, version_id=version_id)

    def get_process(self, process_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_process(process_id)
        if not result:
            return {"status": "error", "message": "业务过程不存在"}
        return result

    def create_process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_process(data)

    def update_process(self, process_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        result = self._storage.update_process(process_id, data)
        if not result:
            return {"status": "error", "message": "业务过程不存在"}
        return result

    def delete_process(self, process_id: str) -> Dict[str, Any]:
        success = self._storage.delete_process(process_id)
        if not success:
            return {"status": "error", "message": "业务过程不存在"}
        return {"status": "success", "message": "业务过程删除成功"}

    def list_rules(self, ontology_id: str = None, version_id: str = None) -> List[Dict[str, Any]]:
        return self._storage.list_rules(ontology_id=ontology_id, version_id=version_id)

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_rule(rule_id)
        if not result:
            return {"status": "error", "message": "业务规则不存在"}
        return result

    def create_rule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_rule(data)

    def update_rule(self, rule_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        result = self._storage.update_rule(rule_id, data)
        if not result:
            return {"status": "error", "message": "业务规则不存在"}
        return result

    def delete_rule(self, rule_id: str) -> Dict[str, Any]:
        success = self._storage.delete_rule(rule_id)
        if not success:
            return {"status": "error", "message": "业务规则不存在"}
        return {"status": "success", "message": "业务规则删除成功"}

    def list_logics(self, ontology_id: str = None, version_id: str = None) -> List[Dict[str, Any]]:
        return self._storage.list_logics(ontology_id=ontology_id, version_id=version_id)

    def get_logic(self, logic_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_logic(logic_id)
        if not result:
            return {"status": "error", "message": "业务逻辑不存在"}
        return result

    def create_logic(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_logic(data)

    def update_logic(self, logic_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        result = self._storage.update_logic(logic_id, data)
        if not result:
            return {"status": "error", "message": "业务逻辑不存在"}
        return result

    def delete_logic(self, logic_id: str) -> Dict[str, Any]:
        success = self._storage.delete_logic(logic_id)
        if not success:
            return {"status": "error", "message": "业务逻辑不存在"}
        return {"status": "success", "message": "业务逻辑删除成功"}

    def list_indicators(self, ontology_id: str = None, version_id: str = None) -> List[Dict[str, Any]]:
        return self._storage.list_indicators(ontology_id=ontology_id, version_id=version_id)

    def get_indicator(self, indicator_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_indicator(indicator_id)
        if not result:
            return {"status": "error", "message": "业务指标不存在"}
        return result

    def create_indicator(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_indicator(data)

    def update_indicator(self, indicator_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        result = self._storage.update_indicator(indicator_id, data)
        if not result:
            return {"status": "error", "message": "业务指标不存在"}
        return result

    def delete_indicator(self, indicator_id: str) -> Dict[str, Any]:
        success = self._storage.delete_indicator(indicator_id)
        if not success:
            return {"status": "error", "message": "业务指标不存在"}
        return {"status": "success", "message": "业务指标删除成功"}
