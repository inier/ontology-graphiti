"""T058 ConstraintSuggester — local rule engine for validation constraint suggestions.

Suggests constraints (format, pattern, minimum, maximum) based on
property name and data type. No LLM dependency.
"""
import re
from typing import Any, Dict, List, Optional

_NAME_PATTERNS: List[tuple] = [
    (re.compile(r"email", re.IGNORECASE), {"format": "email", "pattern": r"^[\w.-]+@[\w.-]+\.\w+$"}),
    (re.compile(r"phone|mobile|telephone", re.IGNORECASE), {"pattern": r"^1[3-9]\d{9}$"}),
    (re.compile(r"url|website|homepage", re.IGNORECASE), {"format": "uri"}),
    (re.compile(r"percentage|percent|ratio", re.IGNORECASE), {"minimum": 0, "maximum": 100}),
    (re.compile(r"price|amount|cost|fee|salary", re.IGNORECASE), {"minimum": 0}),
    (re.compile(r"\bage\b", re.IGNORECASE), {"minimum": 0, "maximum": 150}),
    (re.compile(r"lat(itude)?$", re.IGNORECASE), {"minimum": -90, "maximum": 90}),
    (re.compile(r"lon(gitude|g)?$|^lng$", re.IGNORECASE), {"minimum": -180, "maximum": 180}),
    (re.compile(r"color|colour", re.IGNORECASE), {"pattern": r"^#[0-9a-fA-F]{6}$"}),
    (re.compile(r"^ip|ip_address", re.IGNORECASE), {"pattern": r"^(\d{1,3}\.){3}\d{1,3}$"}),
]


class ConstraintSuggester:
    """Local rule engine for validation constraint suggestions."""

    def suggest(self, property_name: str, data_type: str) -> Dict[str, Any]:
        name = property_name or ""
        constraints: Dict[str, Any] = {}
        for pattern, rule_constraints in _NAME_PATTERNS:
            if pattern.search(name):
                constraints.update(rule_constraints)
                break
        return {
            "property_name": property_name,
            "data_type": data_type,
            "constraints": constraints,
            "source": "rule_engine",
        }

    def suggest_batch(
        self, items: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        return [
            self.suggest(item["property_name"], item["data_type"])
            for item in items
        ]
