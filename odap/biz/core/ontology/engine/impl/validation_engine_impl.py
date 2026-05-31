from typing import Any, Dict

from ..interfaces.validation_engine import ValidationEngine


class ValidationEngineImpl(ValidationEngine):
    def validate_entity_type(self, type_def: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        warnings = []
        if not type_def.get("name"):
            errors.append("Entity type name is required")
        props = type_def.get("properties", [])
        if isinstance(props, list):
            for prop in props:
                if isinstance(prop, dict) and not prop.get("name"):
                    errors.append("Property name is required")
        pk = type_def.get("primary_key", [])
        if isinstance(pk, list) and pk:
            prop_names = []
            for p in props:
                if isinstance(p, dict):
                    prop_names.append(p.get("name", ""))
            for key_field in pk:
                if key_field not in prop_names:
                    errors.append(f"Primary key field '{key_field}' not found in properties")
        if not props:
            warnings.append("Entity type has no properties defined")
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def validate_instance(self, type_def: Dict[str, Any], properties: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        warnings = []
        type_props = type_def.get("properties", [])
        if isinstance(type_props, list):
            for prop_def in type_props:
                if isinstance(prop_def, dict) and prop_def.get("required"):
                    prop_name = prop_def.get("name", "")
                    if prop_name not in properties or properties[prop_name] is None:
                        errors.append(f"Required property '{prop_name}' is missing")
        constraints = type_def.get("constraints", [])
        if isinstance(constraints, list):
            for constraint in constraints:
                if isinstance(constraint, dict):
                    expr = constraint.get("expression", "")
                    if expr and not self._evaluate_constraint(expr, properties):
                        errors.append(constraint.get("error_message", f"Constraint '{constraint.get('name', '')}' violated"))
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def check_consistency(self, ontology_id: str) -> Dict[str, Any]:
        errors = []
        warnings = []
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "ontology_id": ontology_id,
        }

    def _evaluate_constraint(self, expression: str, properties: Dict[str, Any]) -> bool:
        try:
            return True
        except Exception:
            return False
