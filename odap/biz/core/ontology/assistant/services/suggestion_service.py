"""T060 SuggestionService — AI suggestion lifecycle management.

Manages pending → accepted/rejected transitions with audit log integration.
Returns Dict[str, Any] (AGENTS.md rule 2: services don't raise HTTPException).
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.assistant.storage import Storage

logger = logging.getLogger(__name__)

_RESERVED_WORDS = frozenset({
    "class", "def", "if", "else", "elif", "for", "while", "return",
    "import", "from", "as", "try", "except", "finally", "with",
    "lambda", "yield", "global", "nonlocal", "pass", "break",
    "continue", "in", "is", "not", "and", "or", "True", "False",
    "None", "self", "cls", "type", "id", "name", "value",
})

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class SuggestionService:
    """Manages AI suggestion lifecycle and naming convention validation."""

    def __init__(self, db_path: str = None):
        self.storage = Storage(db_path=db_path) if db_path else Storage()

    def create_suggestion(self, data: Dict[str, Any]) -> Dict[str, Any]:
        required = ["ontology_id", "target_type", "suggestion_category", "source"]
        for field in required:
            if not data.get(field):
                return {"status": "error", "message": f"missing required field: {field}"}
        try:
            now = datetime.now(timezone.utc).isoformat()
            suggestion = {
                "ontology_id": data["ontology_id"],
                "target_type": data["target_type"],
                "target_id": data.get("target_id"),
                "suggestion_category": data["suggestion_category"],
                "content": data.get("content", {}),
                "source": data["source"],
                "confidence": data.get("confidence", 0.0),
                "status": "pending",
                "session_id": data.get("session_id"),
                "created_at": now,
            }
            return self.storage.save_suggestion(suggestion)
        except Exception as exc:
            logger.exception("create_suggestion failed")
            return {"status": "error", "message": f"create_suggestion failed: {exc}"}

    def get_suggestion(self, suggestion_id: str) -> Dict[str, Any]:
        suggestion = self.storage.get_suggestion(suggestion_id)
        if not suggestion:
            return {"status": "error", "message": f"suggestion not found: {suggestion_id}"}
        return suggestion

    def list_suggestions(
        self,
        ontology_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        suggestions = self.storage.list_suggestions(
            ontology_id=ontology_id, status=status
        )
        return {"suggestions": suggestions, "count": len(suggestions)}

    def accept_suggestion(self, suggestion_id: str, user_id: str = "anonymous") -> Dict[str, Any]:
        suggestion = self.storage.get_suggestion(suggestion_id)
        if not suggestion:
            return {"status": "error", "message": f"suggestion not found: {suggestion_id}"}
        if suggestion.get("status") == "accepted":
            return {"status": "error", "message": "suggestion already accepted"}

        # T089: Validate naming convention for property/link/action suggestions
        validation = self._validate_suggestion_content(suggestion)
        if validation.get("status") == "error":
            self._log_audit(
                action="ai_suggestion_accept_validation_failed",
                user_id=user_id,
                result_status="failure",
                suggestion_id=suggestion_id,
                ontology_id=suggestion.get("ontology_id"),
                details=validation,
            )
            return validation

        updated = self.storage.update_suggestion_status(suggestion_id, "accepted")
        if not updated:
            return {"status": "error", "message": "failed to update suggestion status"}
        self._log_audit(
            action="ai_suggestion_accept",
            user_id=user_id,
            result_status="success",
            suggestion_id=suggestion_id,
            ontology_id=suggestion.get("ontology_id"),
            details={
                "target_type": suggestion.get("target_type"),
                "suggestion_category": suggestion.get("suggestion_category"),
                "content_summary": self._summarize_content(suggestion.get("content", {})),
            },
        )
        return {
            "suggestion_id": suggestion_id,
            "status": "accepted",
            "applied": True,
            "message": "suggestion accepted",
        }

    def reject_suggestion(
        self,
        suggestion_id: str,
        user_id: str = "anonymous",
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        suggestion = self.storage.get_suggestion(suggestion_id)
        if not suggestion:
            return {"status": "error", "message": f"suggestion not found: {suggestion_id}"}
        updated = self.storage.update_suggestion_status(
            suggestion_id, "rejected", rejection_reason=reason
        )
        if not updated:
            return {"status": "error", "message": "failed to update suggestion status"}
        self._log_audit(
            action="ai_suggestion_reject",
            user_id=user_id,
            result_status="success",
            suggestion_id=suggestion_id,
            ontology_id=suggestion.get("ontology_id"),
            details={
                "target_type": suggestion.get("target_type"),
                "suggestion_category": suggestion.get("suggestion_category"),
                "rejection_reason": reason,
                "content_summary": self._summarize_content(suggestion.get("content", {})),
            },
        )
        return {
            "suggestion_id": suggestion_id,
            "status": "rejected",
            "rejection_reason": reason,
            "message": "suggestion rejected",
        }

    def delete_suggestion(self, suggestion_id: str) -> Dict[str, Any]:
        deleted = self.storage.delete_suggestion(suggestion_id)
        if not deleted:
            return {"status": "error", "message": f"suggestion not found: {suggestion_id}"}
        return {"suggestion_id": suggestion_id, "status": "deleted"}

    def validate_property_name(self, name: str) -> Dict[str, Any]:
        if not name or not name.strip():
            return {"valid": False, "reason": "name is empty"}
        if not _SNAKE_CASE_RE.match(name):
            return {"valid": False, "reason": "name must be snake_case (lowercase, underscores)"}
        if name in _RESERVED_WORDS:
            return {"valid": False, "reason": f"'{name}' is a reserved word"}
        return {"valid": True}

    def _validate_suggestion_content(self, suggestion: Dict[str, Any]) -> Dict[str, Any]:
        """T089: Validate naming convention for suggestion content before acceptance.

        Checks property/link/action names against snake_case + reserved-word rules.
        Returns ``{"status": "ok"}`` when valid, or
        ``{"status": "error", "message": ..., "invalid_names": [...]}`` on failure.
        """
        content = suggestion.get("content") or {}
        if not isinstance(content, dict):
            return {"status": "ok"}

        target_type = suggestion.get("target_type", "")
        category = suggestion.get("suggestion_category", "")

        # Only validate name-bearing suggestion categories
        name_bearing_categories = {"add_property", "add_link_type", "add_action_type",
                                   "property", "link", "action"}
        if category and category not in name_bearing_categories:
            return {"status": "ok"}

        names_to_check: List[str] = []

        # Single property suggestion: content may have "name" or "property_name"
        for key in ("name", "property_name", "link_name", "action_name"):
            value = content.get(key)
            if isinstance(value, str) and value:
                names_to_check.append(value)

        # Batch property suggestion: content may have "properties" list
        properties = content.get("properties")
        if isinstance(properties, list):
            for prop in properties:
                if isinstance(prop, dict):
                    prop_name = prop.get("name") or prop.get("property_name")
                    if isinstance(prop_name, str) and prop_name:
                        names_to_check.append(prop_name)

        # Link/action batch suggestions
        for batch_key in ("links", "actions", "suggestions"):
            batch = content.get(batch_key)
            if isinstance(batch, list):
                for item in batch:
                    if isinstance(item, dict):
                        item_name = item.get("name")
                        if isinstance(item_name, str) and item_name:
                            names_to_check.append(item_name)

        invalid: List[Dict[str, str]] = []
        for name in names_to_check:
            result = self.validate_property_name(name)
            if not result.get("valid"):
                invalid.append({"name": name, "reason": result.get("reason", "invalid")})

        if invalid:
            return {
                "status": "error",
                "message": f"suggestion contains {len(invalid)} invalid name(s); "
                           f"first: '{invalid[0]['name']}' — {invalid[0]['reason']}",
                "invalid_names": invalid,
            }
        return {"status": "ok"}

    @staticmethod
    def _summarize_content(content: Dict[str, Any]) -> Dict[str, Any]:
        """T091: Build a compact summary of suggestion content for audit log."""
        if not isinstance(content, dict):
            return {}
        summary: Dict[str, Any] = {}
        for key in ("name", "property_name", "data_type", "target_object_type",
                    "source_type", "target_type", "cardinality", "link_type"):
            if key in content:
                summary[key] = content[key]
        for batch_key in ("properties", "links", "actions", "suggestions"):
            batch = content.get(batch_key)
            if isinstance(batch, list):
                summary[f"{batch_key}_count"] = len(batch)
        return summary

    @staticmethod
    def _log_audit(
        action: str,
        user_id: str,
        result_status: str,
        suggestion_id: str,
        ontology_id: str = None,
        details: Dict = None,
    ):
        try:
            from odap.infra.security.unified_audit import log_audit

            log_audit(
                action=action,
                resource="ai_suggestion",
                user=user_id,
                service="ontology_assistant",
                result_status=result_status,
                result_message=f"{action}: {suggestion_id}",
                details=details or {"suggestion_id": suggestion_id, "ontology_id": ontology_id or ""},
                workspace_id="default",
            )
        except Exception:
            pass
