import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..interfaces import IFunctionEngine
from ..storage import SQLiteRuntimeStorage
from ..models import OntologyFunction, FunctionType, FunctionStatus

logger = logging.getLogger("function_engine")


class FunctionEngine(IFunctionEngine):
    def __init__(self, storage: SQLiteRuntimeStorage = None):
        self.storage = storage or SQLiteRuntimeStorage()

    def register_function(self, function_data: Dict[str, Any]) -> Dict[str, Any]:
        func = OntologyFunction(**function_data)
        if not func.name:
            raise ValueError("function name is required")
        if not func.target_object_type:
            raise ValueError("target_object_type is required")
        if func.implementation and func.status == FunctionStatus.DRAFT:
            func.status = FunctionStatus.ACTIVE
        func.updated_at = datetime.now().isoformat()
        result = self.storage.save_function(func.model_dump())
        return result

    def get_function(self, function_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_function(function_id)

    def list_functions(self, function_type: Optional[str] = None, target_object_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.list_functions(function_type=function_type, target_object_type=target_object_type)

    def execute_function(self, function_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        func_data = self.storage.get_function(function_id)
        if not func_data:
            return {"status": "error", "message": f"Function {function_id} not found"}
        if func_data.get("status") != FunctionStatus.ACTIVE.value:
            return {"status": "error", "message": f"Function {function_id} is not active (status={func_data.get('status')})"}
        impl = func_data.get("implementation", "")
        if not impl:
            return {"status": "error", "message": f"Function {function_id} has no implementation"}
        try:
            local_vars: Dict[str, Any] = {"context": context, "result": None}
            exec(impl, {"__builtins__": __builtins__}, local_vars)
            result = local_vars.get("result")
            return {"status": "success", "function_id": function_id, "result": result}
        except Exception as e:
            logger.error(f"Function execution failed: {function_id} - {e}")
            return {"status": "error", "message": str(e)}

    def update_function(self, function_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        func_data = self.storage.get_function(function_id)
        if not func_data:
            return None
        for k, v in updates.items():
            if k in func_data and k != "function_id":
                func_data[k] = v
        func_data["updated_at"] = datetime.now().isoformat()
        return self.storage.save_function(func_data)

    def delete_function(self, function_id: str) -> bool:
        return self.storage.delete_function(function_id)
