"""Schema-level extractor using LLM for natural language input.

Uses ZhipuAIClient (OpenAI-compatible) to call LLM and extract
structured ontology type definitions from natural language descriptions.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict

from odap.infra.config_composer import get_config

logger = logging.getLogger(__name__)

ONTOLOGY_SCHEMA_EXTRACT_PROMPT = """You are an ontology design expert. Extract structured type definitions from the following natural language description.

Return a JSON object with these keys:
- "object_types": List of object type definitions, each with:
  - "name": English identifier (snake_case)
  - "display_name": Chinese display name
  - "description": Brief description
  - "properties": List of property definitions, each with:
    - "name": Property name (snake_case)
    - "property_type": One of "string", "integer", "float", "boolean", "datetime", "json"
    - "required": true or false
  - "classification_level": One of "TS", "S", "C", "U" (default "U")

- "link_types": List of relationship definitions, each with:
  - "name": Relationship name (snake_case)
  - "source_type": Source object type name
  - "target_type": Target object type name
  - "cardinality": One of "1:1", "1:N", "N:1", "N:N"
  - "link_type": One of "ASSOCIATION", "COMPOSITION", "DEPENDENCY", "INHERITANCE"
  - "description": Brief description

- "action_types": List of action definitions, each with:
  - "name": Action name (snake_case)
  - "target_object_type": Target object type name
  - "description": Brief description
  - "parameters": List of parameter objects with "name", "param_type", "required"

- "rule_types": List of rule definitions, each with:
  - "name": Rule name (snake_case)
  - "condition": Condition description
  - "consequence": Consequence description
  - "priority": One of "low", "medium", "high"

- "process_types": List of business process definitions, each with:
  - "name": Process name (snake_case)
  - "display_name": Chinese display name
  - "description": Brief description
  - "related_objects": List of related object type names

- "indicator_types": List of indicator definitions, each with:
  - "name": Indicator name (snake_case)
  - "indicator_type": One of "kpi", "metric", "dimension"
  - "formula": Calculation formula description
  - "unit": Measurement unit

IMPORTANT: Return ONLY valid JSON. No markdown, no explanation, no code blocks.

Natural language description:
{text}
"""


class SchemaLevelExtractor:
    """Extracts schema-level type definitions from natural language using LLM."""

    def __init__(self):
        self._llm_client = None

    def _get_llm_client(self):
        """Get or create LLM client (ZhipuAIClient with LLMConfig)."""
        if self._llm_client is None:
            from odap.infra.llm.llm_service import ZhipuAIClient
            from graphiti_core.llm_client.config import LLMConfig

            api_key = get_config("llm.api_key", "")
            api_base = get_config(
                "llm.api_base", "https://open.bigmodel.cn/api/paas/v4"
            )
            model = get_config("llm.model", "glm-4")

            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY not configured; cannot call LLM for NL extraction"
                )

            config = LLMConfig(
                model=model,
                api_key=api_key,
                base_url=api_base,
                temperature=0.7,
            )
            self._llm_client = ZhipuAIClient(config=config)
        return self._llm_client

    async def extract_from_text(
        self, text: str, auto_search: bool = False
    ) -> Dict[str, Any]:
        """Extract schema definitions from natural language text.

        Args:
            text: Natural language description of the domain.
            auto_search: Whether to supplement with web search results.

        Returns:
            Dict with status and extracted type definitions.
        """
        try:
            # Optional web search for supplementary information
            search_context = ""
            if auto_search:
                search_context = await self._web_search(text)

            # Build prompt
            prompt_text = text
            if search_context:
                prompt_text = (
                    f"{text}\n\nSupplementary domain knowledge:\n{search_context}"
                )

            prompt = ONTOLOGY_SCHEMA_EXTRACT_PROMPT.format(text=prompt_text)

            # Call LLM
            llm = self._get_llm_client()
            from graphiti_core.prompts.models import Message

            messages = [Message(role="user", content=prompt)]
            result_dict, _, _ = await asyncio.wait_for(
                llm._generate_response(messages),
                timeout=120.0,
            )

            # _generate_response already returns a parsed dict
            # but we also handle raw string responses for robustness
            if isinstance(result_dict, dict):
                return self._normalize_result(result_dict)

            # Fallback: if result_dict is a string, parse it
            if isinstance(result_dict, str):
                return self._parse_llm_response(result_dict)

            return {
                "status": "error",
                "message": "Unexpected LLM response type",
            }

        except asyncio.TimeoutError:
            logger.error("NL schema extraction timed out (120s)")
            return {
                "status": "error",
                "message": "Extraction timed out; please try again with shorter input",
            }
        except RuntimeError as e:
            # Re-raise configuration errors (e.g. missing API key)
            logger.error(f"NL schema extraction config error: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"NL schema extraction failed: {e}")
            return {
                "status": "error",
                "message": f"Extraction failed: {str(e)}",
            }

    async def _web_search(self, query: str) -> str:
        """Search web for supplementary domain knowledge."""
        try:
            from odap.biz.data.knowledge_base.ingestion.news_ingester import (
                NewsIngester,
            )

            ingester = NewsIngester()
            results = ingester.search(query, max_results=3)
            if results:
                return "\n".join(
                    [r.get("content", r.get("title", "")) for r in results[:3]]
                )
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
        return ""

    def _normalize_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate the LLM result dict.

        The ZhipuAIClient._generate_response already parses JSON and
        returns a dict, so we just validate/normalize the structure.
        """
        result = {
            "status": "ok",
            "object_types": data.get("object_types", []),
            "link_types": data.get("link_types", []),
            "action_types": data.get("action_types", []),
            "rule_types": data.get("rule_types", []),
            "process_types": data.get("process_types", []),
            "function_types": data.get("function_types", []),
            "indicator_types": data.get("indicator_types", []),
            "summary": {
                "object_types": len(data.get("object_types", [])),
                "link_types": len(data.get("link_types", [])),
                "action_types": len(data.get("action_types", [])),
                "rule_types": len(data.get("rule_types", [])),
                "process_types": len(data.get("process_types", [])),
                "indicator_types": len(data.get("indicator_types", [])),
            },
        }
        return result

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse raw LLM response string into structured result.

        Used as fallback when _generate_response returns a string
        instead of a parsed dict.
        """
        json_str = response.strip()

        # Remove markdown code blocks if present
        if json_str.startswith("```"):
            json_str = re.sub(r"^```\w*\n?", "", json_str)
            json_str = re.sub(r"\n?```$", "", json_str)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            match = re.search(r"\{[\s\S]*\}", json_str)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return {
                        "status": "error",
                        "message": "Failed to parse LLM response as JSON",
                    }
            else:
                return {
                    "status": "error",
                    "message": "No JSON found in LLM response",
                }

        return self._normalize_result(data)
