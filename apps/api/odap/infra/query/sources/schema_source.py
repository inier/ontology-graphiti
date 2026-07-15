from typing import Any, Dict, List, Optional


class SchemaSourceImpl:
    def __init__(self, oms_storage=None):
        self._oms = oms_storage

    def _get_oms(self):
        if self._oms is None:
            from odap.biz.core.ontology.application.oms.services import get_oms_service
            self._oms = get_oms_service()
        return self._oms

    def query_object_types(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        oms = self._get_oms()
        all_types = oms.list_object_types()
        if not filters:
            return all_types
        result = []
        for ot in all_types:
            match = True
            if "type_id" in filters and ot.get("type_id") != filters["type_id"]:
                match = False
            if "name" in filters and filters["name"].lower() not in ot.get("name", "").lower():
                match = False
            if "is_active" in filters and ot.get("is_active") != filters["is_active"]:
                match = False
            if match:
                result.append(ot)
        return result

    def query_link_definitions(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        oms = self._get_oms()
        all_types = oms.list_object_types()
        all_links = []
        for ot in all_types:
            for link in ot.get("links", []):
                if not filters:
                    all_links.append(link)
                else:
                    match = True
                    if "source_type" in filters and link.get("source_type") != filters["source_type"]:
                        match = False
                    if "target_type" in filters and link.get("target_type") != filters["target_type"]:
                        match = False
                    if "name" in filters and filters["name"].lower() not in link.get("name", "").lower():
                        match = False
                    if match:
                        all_links.append(link)
        return all_links

    def query_action_types(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        oms = self._get_oms()
        all_actions = oms.list_action_types()
        if not filters:
            return all_actions
        result = []
        for at in all_actions:
            match = True
            if "action_type_id" in filters and at.get("action_type_id") != filters["action_type_id"]:
                match = False
            if "target_object_type" in filters and at.get("target_object_type") != filters["target_object_type"]:
                match = False
            if "name" in filters and filters["name"].lower() not in at.get("name", "").lower():
                match = False
            if match:
                result.append(at)
        return result

    def validate_entity_type(self, entity_type: str) -> bool:
        """
        校验实体类型是否在 OMS 中注册

        Args:
            entity_type: 实体类型名称

        Returns:
            True 如果类型已注册
        """
        oms = self._get_oms()
        type_def = oms.get_object_type(entity_type)
        return type_def is not None

    def validate_properties(
        self, entity_type: str, properties: Dict[str, Any]
    ) -> List[str]:
        """
        校验属性值是否符合 OMS 类型定义

        Args:
            entity_type: 实体类型名称
            properties: 属性字典

        Returns:
            校验错误列表（空列表表示通过）
        """
        oms = self._get_oms()
        type_def = oms.get_object_type(entity_type)
        if not type_def:
            return [f"Unknown entity type: {entity_type}"]

        errors = []
        prop_defs = {p["name"]: p for p in type_def.get("properties", [])}

        for prop_name, prop_def in prop_defs.items():
            if prop_def.get("required") and prop_name not in properties:
                errors.append(f"Missing required property: {prop_name}")

        for key, value in properties.items():
            if key not in prop_defs:
                continue
            prop_def = prop_defs[key]
            expected_type = prop_def.get("property_type", "string")
            type_errors = self._check_value_type(key, value, expected_type)
            errors.extend(type_errors)

        return errors

    def validate_cardinality(
        self,
        source_type: str,
        link_name: str,
        current_count: int,
    ) -> bool:
        """
        校验关系基数是否合规

        Args:
            source_type: 源实体类型
            link_name: 关系名称
            current_count: 当前已存在的关系数量

        Returns:
            True 如果基数合规
        """
        oms = self._get_oms()
        type_def = oms.get_object_type(source_type)
        if not type_def:
            return True

        for link in type_def.get("links", []):
            if link.get("name") == link_name:
                cardinality = link.get("cardinality", "many_to_many")
                if cardinality in ("one_to_one", "ONE_TO_ONE") and current_count >= 1:
                    return False
                if cardinality in ("one_to_many", "ONE_TO_MANY") and current_count >= 1:
                    pass
                break

        return True

    @staticmethod
    def _check_value_type(key: str, value: Any, expected_type: str) -> List[str]:
        """检查值类型是否匹配"""
        errors = []
        type_map = {
            "string": (str,),
            "integer": (int,),
            "float": (int, float),
            "boolean": (bool,),
            "datetime": (str,),
            "geopoint": (str, dict, list),
            "json": (dict, list, str),
            "reference": (str,),
        }
        allowed = type_map.get(expected_type.lower(), (str,))
        if not isinstance(value, allowed):
            errors.append(
                f"Property '{key}' expected type '{expected_type}', got '{type(value).__name__}'"
            )
        return errors
