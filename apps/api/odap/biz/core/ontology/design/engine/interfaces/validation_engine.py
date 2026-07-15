from typing import Any, Dict, List, Optional


class ValidationEngine:
    def validate(self, entity_type: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a data dict against an entity type's rules."""
        raise NotImplementedError

    def add_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Add a validation rule."""
        raise NotImplementedError
