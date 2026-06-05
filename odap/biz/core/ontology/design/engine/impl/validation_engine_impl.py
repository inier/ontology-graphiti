from typing import Any, Dict
import re

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

    def validate(self, entity_type: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a data dict against an entity type's rules (ABC implementation)."""
        type_result = self.validate_entity_type(entity_type)
        instance_result = self.validate_instance(entity_type, data)
        return {
            "is_valid": type_result.get("is_valid", False) and instance_result.get("is_valid", False),
            "errors": type_result.get("errors", []) + instance_result.get("errors", []),
            "warnings": type_result.get("warnings", []) + instance_result.get("warnings", []),
        }

    def add_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Add a validation rule (ABC implementation)."""
        return {"status": "success", "message": "Rule added (no-op)"}

    def _evaluate_constraint(self, expression: str, properties: Dict[str, Any]) -> bool:
        try:
            parts = expression.split(":", 1)
            constraint_type = parts[0].strip().lower()
            constraint_expr = parts[1].strip() if len(parts) > 1 else ""

            if constraint_type == "not_null":
                for prop_name in constraint_expr.split(","):
                    val = properties.get(prop_name.strip())
                    if val is None or val == "":
                        return False
                return True

            if constraint_type == "unique":
                return True

            if constraint_type == "range":
                range_parts = constraint_expr.split(":")
                if len(range_parts) == 2:
                    min_val = float(range_parts[0]) if range_parts[0] else None
                    max_val = float(range_parts[1]) if range_parts[1] else None
                    for prop_name, val in properties.items():
                        try:
                            num_val = float(val)
                            if min_val is not None and num_val < min_val:
                                return False
                            if max_val is not None and num_val > max_val:
                                return False
                        except (ValueError, TypeError):
                            continue
                return True

            if constraint_type == "regex":
                pattern = constraint_expr
                for prop_name, val in properties.items():
                    if isinstance(val, str) and not re.search(pattern, val):
                        return False
                return True

            if constraint_type == "enum":
                allowed = [v.strip() for v in constraint_expr.split(",")]
                for prop_name, val in properties.items():
                    if val is not None and str(val) not in allowed:
                        return False
                return True

            return True
        except Exception:
            return True
