import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..interfaces import IAggregateEngine
from ..storage import SQLiteRuntimeStorage
from ..models import AggregateDefinition, AggregateMethod

logger = logging.getLogger("aggregate_engine")


class AggregateEngine(IAggregateEngine):
    def __init__(self, storage: SQLiteRuntimeStorage = None):
        self.storage = storage or SQLiteRuntimeStorage()

    def register_aggregate(self, aggregate_data: Dict[str, Any]) -> Dict[str, Any]:
        agg = AggregateDefinition(**aggregate_data)
        if not agg.name:
            raise ValueError("aggregate name is required")
        if not agg.target_object_type:
            raise ValueError("target_object_type is required")
        if not agg.target_property:
            raise ValueError("target_property is required")
        return self.storage.save_aggregate(agg.model_dump())

    def get_aggregate(self, agg_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_aggregate(agg_id)

    def list_aggregates(self, target_object_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.list_aggregates(target_object_type=target_object_type)

    def compute_aggregate(self, agg_id: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        agg_data = self.storage.get_aggregate(agg_id)
        if not agg_data:
            return {"status": "error", "message": f"Aggregate {agg_id} not found"}
        method = agg_data.get("method", AggregateMethod.SUM.value)
        target_property = agg_data.get("target_property", "")
        values = []
        for item in data:
            val = item.get(target_property)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    continue
        if not values:
            return {"status": "success", "agg_id": agg_id, "result": None, "count": 0}
        if method == AggregateMethod.SUM.value:
            result = sum(values)
        elif method == AggregateMethod.MIN.value:
            result = min(values)
        elif method == AggregateMethod.MAX.value:
            result = max(values)
        elif method == AggregateMethod.AVG.value:
            result = sum(values) / len(values)
        elif method == AggregateMethod.COUNT.value:
            result = len(values)
        elif method == AggregateMethod.FIRST.value:
            result = values[0]
        elif method == AggregateMethod.LAST.value:
            result = values[-1]
        else:
            result = sum(values)
        return {
            "status": "success",
            "agg_id": agg_id,
            "method": method,
            "target_property": target_property,
            "result": result,
            "count": len(values),
        }

    def delete_aggregate(self, agg_id: str) -> bool:
        return self.storage.delete_aggregate(agg_id)
