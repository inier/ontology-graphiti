import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from .storage import ServiceCatalogStorage
from ..models import CatalogEntryStatus


class ServiceCatalogService:
    _instance = None

    @classmethod
    def get_instance(cls, storage=None):
        if cls._instance is None:
            cls._instance = cls(storage)
        return cls._instance

    def __init__(self, storage=None):
        self.storage = storage or ServiceCatalogStorage()

    def register_service(self, service_id: str, service_name: str, service_type: str,
                         source_ontology_id: str = None, source_object_type: str = None,
                         source_ontology_version: str = "", capabilities: list = None,
                         endpoint_path: str = "", description: str = "",
                         metadata: dict = None) -> Dict[str, Any]:
        existing = self.storage.get_by_service_id(service_id)
        if existing:
            return {"status": "success", "catalog_id": existing["catalog_id"],
                    "message": "Service already registered"}
        now = datetime.now().isoformat()
        catalog_id = f"cat-{uuid.uuid4().hex[:8]}"
        entry = {
            "catalog_id": catalog_id, "service_id": service_id,
            "service_name": service_name, "service_type": service_type,
            "source_ontology_id": source_ontology_id,
            "source_object_type": source_object_type,
            "source_ontology_version": source_ontology_version,
            "current_version": 1, "status": "active",
            "capabilities": capabilities or [],
            "endpoint_path": endpoint_path, "description": description,
            "registered_at": now, "last_updated_at": now,
            "metadata": metadata or {},
        }
        self.storage.register(entry)
        if source_ontology_id:
            self._auto_link_version(catalog_id, source_ontology_id, source_ontology_version)
        return {"status": "success", "catalog_id": catalog_id, "service_id": service_id}

    def get_entry(self, catalog_id: str) -> Dict[str, Any]:
        data = self.storage.get(catalog_id)
        if not data:
            return {"status": "error", "message": "Catalog entry not found"}
        data["entry_status"] = data.pop("status")
        return {"status": "success", **data}

    def list_services(self, service_type: str = None, source_ontology_id: str = None,
                      status: str = None, source_object_type: str = None,
                      limit: int = 100) -> Dict[str, Any]:
        entries = self.storage.list_entries(service_type, source_ontology_id,
                                            status, source_object_type, limit)
        return {"status": "success", "count": len(entries),
                "services": [{"catalog_id": e["catalog_id"], "service_id": e["service_id"],
                              "service_name": e["service_name"], "service_type": e["service_type"],
                              "status": e["status"],
                              "source_object_type": e.get("source_object_type", "")}
                             for e in entries]}

    def discover_services(self, capability: str = None, object_type: str = None,
                          scenario_id: str = None) -> Dict[str, Any]:
        entries = self.storage.list_entries(status="active")
        results = entries
        if object_type:
            results = [e for e in results if e.get("source_object_type") == object_type]
        if capability:
            results = [e for e in results
                       if capability in e.get("capabilities", [])]
        return {"status": "success", "count": len(results),
                "services": [{"catalog_id": e["catalog_id"], "service_name": e["service_name"],
                              "service_type": e["service_type"],
                              "endpoint_path": e.get("endpoint_path", "")}
                             for e in results]}

    def deprecate_service(self, catalog_id: str) -> Dict[str, Any]:
        result = self.storage.update_status(catalog_id, "deprecated")
        if not result:
            return {"status": "error", "message": "Catalog entry not found"}
        return {"status": "success", "catalog_id": catalog_id, "new_status": "deprecated"}

    def retire_service(self, catalog_id: str) -> Dict[str, Any]:
        result = self.storage.update_status(catalog_id, "retired")
        if not result:
            return {"status": "error", "message": "Catalog entry not found"}
        return {"status": "success", "catalog_id": catalog_id, "new_status": "retired"}

    def delete_entry(self, catalog_id: str) -> Dict[str, Any]:
        result = self.storage.delete(catalog_id)
        if not result:
            return {"status": "error", "message": "Catalog entry not found"}
        return {"status": "success", "catalog_id": catalog_id}

    def on_ontology_version_changed(self, ontology_id: str,
                                     new_version_id: str) -> Dict[str, Any]:
        entries = self.storage.list_entries(source_ontology_id=ontology_id, status="active")
        updated = []
        for entry in entries:
            self.storage.update_status(entry["catalog_id"], "needs_update")
            link_id = f"vl-{uuid.uuid4().hex[:8]}"
            self.storage.add_version_link({
                "link_id": link_id, "catalog_id": entry["catalog_id"],
                "ontology_version_id": new_version_id,
                "service_version": entry.get("current_version", 1) + 1,
                "is_compatible": False,
                "notes": "Auto-flagged: ontology version changed",
                "created_at": datetime.now().isoformat(),
            })
            updated.append(entry["catalog_id"])
        return {"status": "success", "ontology_id": ontology_id,
                "new_version_id": new_version_id,
                "services_flagged": len(updated), "catalog_ids": updated}

    def get_version_links(self, catalog_id: str) -> Dict[str, Any]:
        links = self.storage.get_version_links(catalog_id)
        return {"status": "success", "catalog_id": catalog_id, "links": links}

    def health_check(self, catalog_id: str) -> Dict[str, Any]:
        data = self.storage.get(catalog_id)
        if not data:
            return {"status": "error", "message": "Catalog entry not found"}
        return {"status": "success", "catalog_id": catalog_id,
                "service_status": data.get("status", "unknown"),
                "last_updated": data.get("last_updated_at", "")}

    def _auto_link_version(self, catalog_id: str, ontology_id: str,
                           ontology_version: str):
        if not ontology_version:
            return
        link_id = f"vl-{uuid.uuid4().hex[:8]}"
        self.storage.add_version_link({
            "link_id": link_id, "catalog_id": catalog_id,
            "ontology_version_id": ontology_version,
            "service_version": 1, "is_compatible": True,
            "notes": "Auto-linked on registration",
            "created_at": datetime.now().isoformat(),
        })


get_service_catalog = ServiceCatalogService.get_instance
