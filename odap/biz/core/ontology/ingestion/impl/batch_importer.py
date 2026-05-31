import csv
import io
import json
import logging
import uuid
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BatchImporter:
    def import_csv(self, entity_type_id: str, data: str, workspace_id: str) -> Dict[str, Any]:
        success_count = 0
        fail_count = 0
        errors = []

        try:
            reader = csv.DictReader(io.StringIO(data))
            for row_idx, row in enumerate(reader):
                try:
                    row["entity_type_id"] = entity_type_id
                    row["workspace_id"] = workspace_id
                    if "id" not in row or not row["id"]:
                        row["id"] = str(uuid.uuid4())
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    errors.append({"row": row_idx + 1, "error": str(e)})

            return {
                "status": "success",
                "success_count": success_count,
                "fail_count": fail_count,
                "errors": errors,
                "format": "csv",
                "entity_type_id": entity_type_id,
                "workspace_id": workspace_id,
            }
        except Exception as e:
            logger.warning("CSV import failed: %s", e)
            return {
                "status": "error",
                "success_count": 0,
                "fail_count": 0,
                "errors": [{"row": 0, "error": str(e)}],
                "format": "csv",
                "entity_type_id": entity_type_id,
                "workspace_id": workspace_id,
            }

    def import_json(self, entity_type_id: str, data: Any, workspace_id: str) -> Dict[str, Any]:
        success_count = 0
        fail_count = 0
        errors = []

        try:
            if isinstance(data, str):
                parsed = json.loads(data)
            else:
                parsed = data

            items = parsed if isinstance(parsed, list) else [parsed]

            for idx, item in enumerate(items):
                try:
                    if not isinstance(item, dict):
                        fail_count += 1
                        errors.append({"index": idx, "error": "Item is not a dict"})
                        continue
                    item["entity_type_id"] = entity_type_id
                    item["workspace_id"] = workspace_id
                    if "id" not in item or not item["id"]:
                        item["id"] = str(uuid.uuid4())
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    errors.append({"index": idx, "error": str(e)})

            return {
                "status": "success",
                "success_count": success_count,
                "fail_count": fail_count,
                "errors": errors,
                "format": "json",
                "entity_type_id": entity_type_id,
                "workspace_id": workspace_id,
            }
        except Exception as e:
            logger.warning("JSON import failed: %s", e)
            return {
                "status": "error",
                "success_count": 0,
                "fail_count": 0,
                "errors": [{"index": 0, "error": str(e)}],
                "format": "json",
                "entity_type_id": entity_type_id,
                "workspace_id": workspace_id,
            }
