import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..interfaces import IKnowledgeServitizationEngine
from ..models import SkillTemplate, GeneratedService, ServiceDeployment, ServiceType, GenerationStatus
from ..storage import SQLiteServitizationStorage

logger = logging.getLogger("servitization_engine")


class KnowledgeServitizationEngine(IKnowledgeServitizationEngine):
    def __init__(self, storage: SQLiteServitizationStorage = None):
        self.storage = storage or SQLiteServitizationStorage()

    def create_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        template = SkillTemplate(**template_data)
        data = template.model_dump()
        data["service_type"] = template.service_type.value
        data["created_at"] = template.created_at.isoformat()
        self.storage.save_template(data)
        return data

    def list_templates(self, service_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.list_templates(service_type=service_type)

    def generate_service(self, template_id: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
        template_data = self.storage.get_template(template_id)
        if not template_data:
            raise ValueError(f"Template {template_id} not found")

        service = GeneratedService(
            name=overrides.get("name", template_data["name"]),
            description=overrides.get("description", template_data["description"]),
            service_type=ServiceType(template_data["service_type"]),
            source_ontology_id=overrides.get("source_ontology_id", ""),
            source_object_type=overrides.get("source_object_type", template_data["object_type"]),
            source_function_ids=overrides.get("source_function_ids", []),
            template_id=template_id,
            code=self._fill_template(template_data["code_template"], overrides),
            parameter_schema=overrides.get("parameter_schema", template_data["parameter_schema"]),
            output_schema=overrides.get("output_schema", template_data["output_schema"]),
            endpoint_path=overrides.get("endpoint_path"),
            status=GenerationStatus.COMPLETED,
        )

        data = service.model_dump()
        data["service_type"] = service.service_type.value
        data["status"] = service.status.value
        data["created_at"] = service.created_at.isoformat()
        data["updated_at"] = service.updated_at.isoformat()
        self.storage.save_service(data)
        return data

    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_service(service_id)

    def list_services(self, service_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.list_services(service_type=service_type, status=status)

    def deploy_service(self, service_id: str) -> Dict[str, Any]:
        service_data = self.storage.get_service(service_id)
        if not service_data:
            raise ValueError(f"Service {service_id} not found")

        existing = self.storage.get_deployment_by_service(service_id)
        if existing:
            return {"status": "error", "message": f"Service {service_id} already deployed"}

        service_type = service_data["service_type"]
        endpoint_url = self._build_endpoint_url(service_data)
        endpoint_path = f"/api/ontology/servitization/exec/{service_id}"

        deployment = ServiceDeployment(
            service_id=service_id,
            endpoint_url=endpoint_url,
            health_status="healthy",
        )

        deploy_data = deployment.model_dump()
        deploy_data["is_active"] = deployment.is_active
        self.storage.save_deployment(deploy_data)

        self.storage.update_service_status(service_id, GenerationStatus.DEPLOYED.value)

        service_data["status"] = GenerationStatus.DEPLOYED.value
        service_data["endpoint_path"] = endpoint_path
        self.storage.save_service(service_data)

        return deploy_data

    def undeploy_service(self, service_id: str) -> Dict[str, Any]:
        deployment = self.storage.get_deployment_by_service(service_id)
        if not deployment:
            raise ValueError(f"No active deployment found for service {service_id}")

        self.storage.update_deployment_status(
            deployment["deployment_id"], is_active=False, health_status="stopped")
        self.storage.update_service_status(service_id, GenerationStatus.COMPLETED.value)

        return {
            "deployment_id": deployment["deployment_id"],
            "service_id": service_id,
            "status": "undeployed",
        }

    def generate_from_ontology(self, ontology_id: str, service_type: str = "skill") -> Dict[str, Any]:
        generated_services = []

        try:
            from ..oms.storage.sqlite_oms_storage import SQLiteOMSStorage
            oms = SQLiteOMSStorage()
        except Exception:
            logger.warning("OMS storage not available, using empty data")
            return {"status": "error", "message": "OMS storage not available"}

        object_types = oms.list_object_types(active_only=True)
        action_types = oms.list_action_types()

        for obj_type in object_types:
            type_name = obj_type.get("name", obj_type.get("type_id", ""))
            query_service = self._generate_query_service(ontology_id, type_name, obj_type, service_type)
            if query_service:
                generated_services.append(query_service)

            stat_props = [p for p in obj_type.get("properties", []) if p.get("category") == "statistical_properties"]
            if stat_props:
                agg_service = self._generate_aggregate_service(ontology_id, type_name, stat_props, service_type)
                if agg_service:
                    generated_services.append(agg_service)

        for action in action_types:
            action_service = self._generate_action_service(ontology_id, action, service_type)
            if action_service:
                generated_services.append(action_service)

        return {
            "ontology_id": ontology_id,
            "service_type": service_type,
            "generated_count": len(generated_services),
            "services": generated_services,
        }

    def _generate_query_service(self, ontology_id: str, type_name: str, obj_type: Dict, service_type: str) -> Optional[Dict[str, Any]]:
        param_schema = self._infer_parameter_schema(obj_type)
        output_schema = self._infer_output_schema(obj_type)
        code = self._generate_query_skill_code(type_name, obj_type)

        service = GeneratedService(
            name=f"query_{type_name.lower()}",
            description=f"Query {type_name} objects from ontology",
            service_type=ServiceType(service_type),
            source_ontology_id=ontology_id,
            source_object_type=type_name,
            code=code,
            parameter_schema=param_schema,
            output_schema=output_schema,
            endpoint_path=f"/api/ontology/servitization/exec/query_{type_name.lower()}",
            status=GenerationStatus.COMPLETED,
        )

        data = service.model_dump()
        data["service_type"] = service.service_type.value
        data["status"] = service.status.value
        data["created_at"] = service.created_at.isoformat()
        data["updated_at"] = service.updated_at.isoformat()
        self.storage.save_service(data)
        return data

    def _generate_action_service(self, ontology_id: str, action: Dict, service_type: str) -> Optional[Dict[str, Any]]:
        action_name = action.get("name", action.get("action_type_id", ""))
        target_type = action.get("target_object_type", "")
        param_schema = self._infer_action_parameter_schema(action)
        output_schema = {"type": "object", "properties": {"success": {"type": "boolean"}, "message": {"type": "string"}}}
        code = self._generate_action_skill_code(action_name, action)

        service = GeneratedService(
            name=f"action_{action_name.lower()}",
            description=f"Execute {action_name} action on {target_type}",
            service_type=ServiceType(service_type),
            source_ontology_id=ontology_id,
            source_object_type=target_type,
            source_function_ids=[action.get("action_type_id", "")],
            code=code,
            parameter_schema=param_schema,
            output_schema=output_schema,
            endpoint_path=f"/api/ontology/servitization/exec/action_{action_name.lower()}",
            status=GenerationStatus.COMPLETED,
        )

        data = service.model_dump()
        data["service_type"] = service.service_type.value
        data["status"] = service.status.value
        data["created_at"] = service.created_at.isoformat()
        data["updated_at"] = service.updated_at.isoformat()
        self.storage.save_service(data)
        return data

    def _generate_aggregate_service(self, ontology_id: str, type_name: str, stat_props: List[Dict], service_type: str) -> Optional[Dict[str, Any]]:
        param_schema = {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["sum", "avg", "min", "max", "count"]},
                "property": {"type": "string", "enum": [p.get("name", "") for p in stat_props]},
                "filters": {"type": "object"},
            },
            "required": ["method", "property"],
        }
        output_schema = {
            "type": "object",
            "properties": {
                "result": {"type": "number"},
                "method": {"type": "string"},
                "property": {"type": "string"},
                "count": {"type": "integer"},
            },
        }
        code = self._generate_aggregate_skill_code(type_name, stat_props)

        service = GeneratedService(
            name=f"aggregate_{type_name.lower()}",
            description=f"Aggregate statistics for {type_name}",
            service_type=ServiceType(service_type),
            source_ontology_id=ontology_id,
            source_object_type=type_name,
            code=code,
            parameter_schema=param_schema,
            output_schema=output_schema,
            endpoint_path=f"/api/ontology/servitization/exec/aggregate_{type_name.lower()}",
            status=GenerationStatus.COMPLETED,
        )

        data = service.model_dump()
        data["service_type"] = service.service_type.value
        data["status"] = service.status.value
        data["created_at"] = service.created_at.isoformat()
        data["updated_at"] = service.updated_at.isoformat()
        self.storage.save_service(data)
        return data

    def _generate_query_skill_code(self, type_name: str, obj_type: Dict) -> str:
        properties = obj_type.get("properties", [])
        prop_names = [p.get("name", "") for p in properties]
        required_props = [p.get("name", "") for p in properties if p.get("required")]

        return (
            f'class Query{type_name}Skill(BaseSkill):\n'
            f'    """Auto-generated query skill for {type_name}"""\n'
            f'    name = "query_{type_name.lower()}"\n'
            f'    description = "Query {type_name} objects from ontology"\n'
            f'\n'
            f'    async def execute(self, params: dict) -> dict:\n'
            f'        from odap.infra.graph.graph_service import GraphManager\n'
            f'        gm = GraphManager()\n'
            f'        filters = {{k: v for k, v in params.items() if k in {prop_names}}}\n'
            f'        results = gm.query_nodes("{type_name}", filters)\n'
            f'        return {{"results": results, "count": len(results)}}\n'
        )

    def _generate_action_skill_code(self, action_name: str, action: Dict) -> str:
        parameters = action.get("parameters", [])
        param_names = [p.get("name", "") for p in parameters]
        target_type = action.get("target_object_type", "")

        return (
            f'class Action{action_name.capitalize()}Skill(BaseSkill):\n'
            f'    """Auto-generated action skill for {action_name}"""\n'
            f'    name = "action_{action_name.lower()}"\n'
            f'    description = "Execute {action_name} on {target_type}"\n'
            f'\n'
            f'    async def execute(self, params: dict) -> dict:\n'
            f'        required = {param_names}\n'
            f'        for r in required:\n'
            f'            if r not in params:\n'
            f'                return {{"success": False, "message": f"Missing required param: {{r}}"}}\n'
            f'        try:\n'
            f'            from ..runtime.services import import get_runtime_service\n'
            f'            service = get_runtime_service()\n'
            f'            result = service.record_mutation({{\n'
            f'                "action_type_id": "{action.get("action_type_id", action_name)}",\n'
            f'                "action_name": "{action_name}",\n'
            f'                "target_object_type": "{target_type}",\n'
            f'                **params\n'
            f'            }})\n'
            f'            return {{"success": True, "message": "{action_name} executed", "result": result}}\n'
            f'        except Exception as e:\n'
            f'            return {{"success": False, "message": str(e)}}\n'
        )

    def _generate_aggregate_skill_code(self, type_name: str, stat_props: List[Dict]) -> str:
        prop_names = [p.get("name", "") for p in stat_props]

        return (
            f'class Aggregate{type_name}Skill(BaseSkill):\n'
            f'    """Auto-generated aggregate skill for {type_name}"""\n'
            f'    name = "aggregate_{type_name.lower()}"\n'
            f'    description = "Aggregate statistics for {type_name}"\n'
            f'\n'
            f'    async def execute(self, params: dict) -> dict:\n'
            f'        method = params.get("method", "sum")\n'
            f'        prop = params.get("property")\n'
            f'        if prop not in {prop_names}:\n'
            f'            return {{"result": None, "error": f"Invalid property: {{prop}}"}}\n'
            f'        from odap.infra.graph.graph_service import GraphManager\n'
            f'        gm = GraphManager()\n'
            f'        nodes = gm.query_nodes("{type_name}", params.get("filters", {{}}))\n'
            f'        values = [n.get(prop, 0) for n in nodes if prop in n]\n'
            f'        if not values:\n'
            f'            return {{"result": 0, "method": method, "property": prop, "count": 0}}\n'
            f'        import statistics\n'
            f'        ops = {{"sum": sum, "avg": statistics.mean, "min": min, "max": max, "count": len}}\n'
            f'        result = ops.get(method, sum)(values)\n'
            f'        return {{"result": result, "method": method, "property": prop, "count": len(values)}}\n'
        )

    def _infer_parameter_schema(self, obj_type: Dict) -> Dict[str, Any]:
        properties = obj_type.get("properties", [])
        schema_props = {}
        required = []
        for prop in properties:
            prop_name = prop.get("name", "")
            prop_type = prop.get("property_type", "string")
            json_type = self._map_type_to_json(prop_type)
            prop_schema = {"type": json_type}
            if prop.get("enum_values"):
                prop_schema["enum"] = prop["enum_values"]
            schema_props[prop_name] = prop_schema
            if prop.get("required"):
                required.append(prop_name)

        schema = {"type": "object", "properties": schema_props}
        if required:
            schema["required"] = required
        return schema

    def _infer_output_schema(self, obj_type: Dict) -> Dict[str, Any]:
        properties = obj_type.get("properties", [])
        schema_props = {}
        for prop in properties:
            prop_name = prop.get("name", "")
            prop_type = prop.get("property_type", "string")
            json_type = self._map_type_to_json(prop_type)
            schema_props[prop_name] = {"type": json_type}

        return {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {"type": "object", "properties": schema_props},
                },
                "count": {"type": "integer"},
            },
        }

    def _infer_action_parameter_schema(self, action: Dict) -> Dict[str, Any]:
        parameters = action.get("parameters", [])
        schema_props = {}
        required = []
        for param in parameters:
            param_name = param.get("name", "")
            param_type = param.get("param_type", "string")
            json_type = self._map_type_to_json(param_type)
            prop_schema = {"type": json_type}
            if param.get("enum_values"):
                prop_schema["enum"] = param["enum_values"]
            schema_props[param_name] = prop_schema
            if param.get("required"):
                required.append(param_name)

        schema = {"type": "object", "properties": schema_props}
        if required:
            schema["required"] = required
        return schema

    def _fill_template(self, code_template: str, overrides: Dict[str, Any]) -> str:
        code = code_template
        for key, value in overrides.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in code:
                code = code.replace(placeholder, str(value))
        return code

    def _build_endpoint_url(self, service_data: Dict) -> str:
        service_id = service_data["service_id"]
        return f"http://localhost:8000/api/ontology/servitization/exec/{service_id}"

    @staticmethod
    def _map_type_to_json(prop_type: str) -> str:
        mapping = {
            "string": "string", "str": "string",
            "integer": "integer", "int": "integer",
            "float": "number", "number": "number",
            "boolean": "boolean", "bool": "boolean",
            "datetime": "string", "date": "string",
            "geopoint": "object", "tuple": "object",
            "list": "array", "json": "object",
        }
        return mapping.get(prop_type.lower(), "string")
