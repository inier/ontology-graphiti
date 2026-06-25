"""T057 TypeInferenceEngine — local rule engine for property name → type inference.

Uses exact match + prefix/suffix/contains pattern matching. No LLM dependency.
Response time < 100ms. 40+ property name groups covering 90+ variants.
"""
import re
from typing import Any, Dict, List, Optional

_EXACT_MATCH_TABLE: Dict[str, Dict[str, Any]] = {
    "id": {"type": "STRING", "constraints": None},
    "name": {"type": "STRING", "constraints": None},
    "title": {"type": "STRING", "constraints": None},
    "description": {"type": "STRING", "constraints": None},
    "email": {"type": "STRING", "constraints": {"format": "email", "pattern": r"^[\w.-]+@[\w.-]+\.\w+$"}},
    "phone": {"type": "STRING", "constraints": {"pattern": r"^1[3-9]\d{9}$"}},
    "mobile": {"type": "STRING", "constraints": {"pattern": r"^1[3-9]\d{9}$"}},
    "telephone": {"type": "STRING", "constraints": {"pattern": r"^1[3-9]\d{9}$"}},
    "address": {"type": "STRING", "constraints": None},
    "age": {"type": "INTEGER", "constraints": {"minimum": 0, "maximum": 150}},
    "price": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "cost": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "fee": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "salary": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "amount": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "total": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "sum": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "quantity": {"type": "INTEGER", "constraints": {"minimum": 0}},
    "count": {"type": "INTEGER", "constraints": {"minimum": 0}},
    "stock": {"type": "INTEGER", "constraints": {"minimum": 0}},
    "weight": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "height": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "width": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "length": {"type": "FLOAT", "constraints": {"minimum": 0}},
    "status": {"type": "STRING", "constraints": None},
    "type": {"type": "STRING", "constraints": None},
    "category": {"type": "STRING", "constraints": None},
    "created_at": {"type": "DATETIME", "constraints": None},
    "created_time": {"type": "DATETIME", "constraints": None},
    "updated_at": {"type": "DATETIME", "constraints": None},
    "modified_at": {"type": "DATETIME", "constraints": None},
    "deleted_at": {"type": "DATETIME", "constraints": None},
    "is_active": {"type": "BOOLEAN", "constraints": None},
    "is_enabled": {"type": "BOOLEAN", "constraints": None},
    "is_deleted": {"type": "BOOLEAN", "constraints": None},
    "is_valid": {"type": "BOOLEAN", "constraints": None},
    "is_verified": {"type": "BOOLEAN", "constraints": None},
    "is_locked": {"type": "BOOLEAN", "constraints": None},
    "has_permission": {"type": "BOOLEAN", "constraints": None},
    "has_access": {"type": "BOOLEAN", "constraints": None},
    "password": {"type": "STRING", "constraints": None},
    "secret": {"type": "STRING", "constraints": None},
    "token": {"type": "STRING", "constraints": None},
    "avatar": {"type": "STRING", "constraints": {"format": "url"}},
    "image": {"type": "STRING", "constraints": {"format": "url"}},
    "photo": {"type": "STRING", "constraints": {"format": "url"}},
    "icon": {"type": "STRING", "constraints": {"format": "url"}},
    "url": {"type": "STRING", "constraints": {"format": "url"}},
    "website": {"type": "STRING", "constraints": {"format": "url"}},
    "homepage": {"type": "STRING", "constraints": {"format": "url"}},
    "latitude": {"type": "FLOAT", "constraints": {"minimum": -90, "maximum": 90}},
    "lat": {"type": "FLOAT", "constraints": {"minimum": -90, "maximum": 90}},
    "longitude": {"type": "FLOAT", "constraints": {"minimum": -180, "maximum": 180}},
    "lng": {"type": "FLOAT", "constraints": {"minimum": -180, "maximum": 180}},
    "lon": {"type": "FLOAT", "constraints": {"minimum": -180, "maximum": 180}},
    "score": {"type": "FLOAT", "constraints": {"minimum": 0, "maximum": 100}},
    "rating": {"type": "FLOAT", "constraints": {"minimum": 0, "maximum": 100}},
    "priority": {"type": "INTEGER", "constraints": None},
    "level": {"type": "INTEGER", "constraints": None},
    "order": {"type": "INTEGER", "constraints": None},
    "code": {"type": "STRING", "constraints": None},
    "code_name": {"type": "STRING", "constraints": None},
    "version": {"type": "STRING", "constraints": None},
    "duration": {"type": "INTEGER", "constraints": {"minimum": 0}},
    "timeout": {"type": "INTEGER", "constraints": {"minimum": 0}},
    "percentage": {"type": "FLOAT", "constraints": {"minimum": 0, "maximum": 100}},
    "percent": {"type": "FLOAT", "constraints": {"minimum": 0, "maximum": 100}},
    "ratio": {"type": "FLOAT", "constraints": {"minimum": 0, "maximum": 100}},
    "ip": {"type": "STRING", "constraints": {"pattern": r"^(\d{1,3}\.){3}\d{1,3}$"}},
    "ip_address": {"type": "STRING", "constraints": {"pattern": r"^(\d{1,3}\.){3}\d{1,3}$"}},
    "color": {"type": "STRING", "constraints": {"pattern": r"^#[0-9a-fA-F]{6}$"}},
    "colour": {"type": "STRING", "constraints": {"pattern": r"^#[0-9a-fA-F]{6}$"}},
    "locale": {"type": "STRING", "constraints": None},
    "language": {"type": "STRING", "constraints": None},
    "timezone": {"type": "STRING", "constraints": None},
    "currency": {"type": "STRING", "constraints": None},
    "gender": {"type": "STRING", "constraints": None},
    "sex": {"type": "STRING", "constraints": None},
    "birthday": {"type": "DATETIME", "constraints": None},
    "birth_date": {"type": "DATETIME", "constraints": None},
    "start_date": {"type": "DATETIME", "constraints": None},
    "end_date": {"type": "DATETIME", "constraints": None},
    "parent_id": {"type": "REFERENCE", "constraints": None},
    "owner_id": {"type": "REFERENCE", "constraints": None},
    "creator_id": {"type": "REFERENCE", "constraints": None},
    "metadata": {"type": "JSON", "constraints": None},
    "extra_data": {"type": "JSON", "constraints": None},
    "tags": {"type": "JSON", "constraints": None},
    "labels": {"type": "JSON", "constraints": None},
    "coordinates": {"type": "JSON", "constraints": None},
    "geo_point": {"type": "GEOPOINT", "constraints": None},
    "location": {"type": "GEOPOINT", "constraints": None},
}

_PREFIX_RULES: List[tuple] = [
    ("is_", "BOOLEAN"),
    ("has_", "BOOLEAN"),
    ("can_", "BOOLEAN"),
]

_SUFFIX_RULES: List[tuple] = [
    ("_at", "DATETIME"),
    ("_date", "DATETIME"),
    ("_time", "DATETIME"),
    ("_id", "REFERENCE"),
    ("_count", "INTEGER"),
    ("_num", "INTEGER"),
    ("_number", "INTEGER"),
    ("_price", "FLOAT"),
    ("_amount", "FLOAT"),
    ("_rate", "FLOAT"),
    ("_ratio", "FLOAT"),
    ("_name", "STRING"),
    ("_title", "STRING"),
    ("_label", "STRING"),
    ("_desc", "STRING"),
    ("_description", "STRING"),
    ("_url", "STRING"),
    ("_uri", "STRING"),
    ("_link", "STRING"),
    ("_path", "STRING"),
    ("_json", "JSON"),
    ("_meta", "JSON"),
    ("_config", "JSON"),
    ("_data", "JSON"),
    ("_lat", "FLOAT"),
    ("_lng", "FLOAT"),
    ("_lon", "FLOAT"),
]

_CONTAINS_RULES: List[tuple] = [
    ("email", "STRING"),
    ("phone", "STRING"),
    ("address", "STRING"),
    ("url", "STRING"),
    ("price", "FLOAT"),
    ("amount", "FLOAT"),
    ("cost", "FLOAT"),
    ("fee", "FLOAT"),
    ("salary", "FLOAT"),
    ("age", "INTEGER"),
    ("count", "INTEGER"),
    ("quantity", "INTEGER"),
    ("total", "INTEGER"),
    ("size", "INTEGER"),
    ("length", "INTEGER"),
    ("date", "DATETIME"),
    ("time", "DATETIME"),
    ("timestamp", "DATETIME"),
    ("flag", "BOOLEAN"),
    ("enabled", "BOOLEAN"),
    ("active", "BOOLEAN"),
    ("visible", "BOOLEAN"),
    ("deleted", "BOOLEAN"),
]


class TypeInferenceEngine:
    """Local rule engine for property name → data type inference."""

    def infer_type(self, property_name: str) -> Dict[str, Any]:
        name = (property_name or "").strip().lower()
        if not name:
            return {
                "property_name": property_name,
                "inferred_type": "STRING",
                "confidence": 0.3,
                "source": "rule_engine",
                "match_rule": "fallback",
                "suggested_constraints": None,
            }

        entry = _EXACT_MATCH_TABLE.get(name)
        if entry:
            return {
                "property_name": property_name,
                "inferred_type": entry["type"],
                "confidence": 1.0,
                "source": "rule_engine",
                "match_rule": "exact_match",
                "suggested_constraints": entry.get("constraints"),
            }

        for prefix, inferred in _PREFIX_RULES:
            if name.startswith(prefix):
                return {
                    "property_name": property_name,
                    "inferred_type": inferred,
                    "confidence": 0.9,
                    "source": "rule_engine",
                    "match_rule": "prefix_match",
                    "suggested_constraints": None,
                }

        for suffix, inferred in _SUFFIX_RULES:
            if name.endswith(suffix):
                return {
                    "property_name": property_name,
                    "inferred_type": inferred,
                    "confidence": 0.85,
                    "source": "rule_engine",
                    "match_rule": "suffix_match",
                    "suggested_constraints": None,
                }

        for keyword, inferred in _CONTAINS_RULES:
            if keyword in name:
                return {
                    "property_name": property_name,
                    "inferred_type": inferred,
                    "confidence": 0.8,
                    "source": "rule_engine",
                    "match_rule": "contains_match",
                    "suggested_constraints": None,
                }

        return {
            "property_name": property_name,
            "inferred_type": "STRING",
            "confidence": 0.3,
            "source": "rule_engine",
            "match_rule": "fallback",
            "suggested_constraints": None,
        }

    def infer_batch(self, property_names: List[str]) -> List[Dict[str, Any]]:
        return [self.infer_type(n) for n in property_names]
