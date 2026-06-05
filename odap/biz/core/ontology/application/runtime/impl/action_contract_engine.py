import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..interfaces import IActionContractEngine
from ..storage import SQLiteRuntimeStorage
from ..models import ActionContract

logger = logging.getLogger("action_contract_engine")


class ActionContractEngine(IActionContractEngine):
    def __init__(self, storage: SQLiteRuntimeStorage = None):
        self.storage = storage or SQLiteRuntimeStorage()

    def create_contract(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        contract = ActionContract(**contract_data)
        if not contract.action_type_id:
            raise ValueError("action_type_id is required")
        existing = self.storage.get_contract_by_action(contract.action_type_id)
        if existing:
            raise ValueError(f"Contract already exists for action_type_id={contract.action_type_id}")
        result = self.storage.save_contract(contract.model_dump())
        return result

    def get_contract(self, contract_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_contract(contract_id)

    def get_contract_by_action(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_contract_by_action(action_type_id)

    def list_contracts(self) -> List[Dict[str, Any]]:
        return self.storage.list_contracts()

    def verify_contract(self, contract_id: str, mutation_log: List[Dict[str, Any]]) -> Dict[str, Any]:
        contract_data = self.storage.get_contract(contract_id)
        if not contract_data:
            return {"status": "error", "message": f"Contract {contract_id} not found"}
        write_set = contract_data.get("write_set", [])
        side_effect_set = contract_data.get("side_effect_set", [])
        declared_targets = set()
        for entry in write_set + side_effect_set:
            key = entry.get("object_type", "")
            if entry.get("property_name"):
                key += f".{entry['property_name']}"
            declared_targets.add(key)
        observed_targets = set()
        violations = []
        for mut in mutation_log:
            obj_type = mut.get("target_object_type", "")
            prop = mut.get("property_name", "")
            key = f"{obj_type}.{prop}" if prop else obj_type
            observed_targets.add(key)
            if key not in declared_targets:
                violations.append({
                    "mutation_id": mut.get("mutation_id", ""),
                    "observed_target": key,
                    "message": f"Undeclared mutation: {key}",
                })
        is_verified = len(violations) == 0
        contract_data["is_verified"] = is_verified
        contract_data["verified_at"] = datetime.now().isoformat()
        self.storage.save_contract(contract_data)
        return {
            "status": "success",
            "contract_id": contract_id,
            "is_verified": is_verified,
            "declared_targets": list(declared_targets),
            "observed_targets": list(observed_targets),
            "violations": violations,
        }

    def update_contract(self, contract_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        contract_data = self.storage.get_contract(contract_id)
        if not contract_data:
            return None
        for k, v in updates.items():
            if k in contract_data and k != "contract_id":
                contract_data[k] = v
        return self.storage.save_contract(contract_data)

    def delete_contract(self, contract_id: str) -> bool:
        return self.storage.delete_contract(contract_id)
