"""HEAdapter — Hyper-Extract API adapter.

Wraps the hyperextract Python API with correct kwargs and normalized output.
Key API alignments (from research.md):
- Template.create(source, language, llm_client=, embedder=) — NOT llm=/emb=
- BaseAutoType.feed_text(text) — NOT evolve()
- .nodes/.edges access — NOT dump_dict()
- No native graph merge API — merge_results is manual dedup
- AutoGraph(node_schema=, edge_schema=) expects Pydantic BaseModel *classes*,
  not strings — requires __name__ attribute for dynamic GraphSchema creation.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

from odap.infra.config_composer import get_config

logger = logging.getLogger("he_adapter")


# ------------------------------------------------------------------
# Pydantic schemas for AutoGraph (must be classes with __name__, not strings)
# ------------------------------------------------------------------

class _ExtractionNode(BaseModel):
    """Node schema for AutoGraph — represents an extracted entity."""

    name: str = ""
    type: str = ""
    description: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)

    # Allow HE to populate extra fields during extraction
    model_config = {"extra": "allow"}

    @classmethod
    def _coerce_field(cls, v: Any) -> str:
        """Coerce field value to string; join lists to keep AutoGraph hashable."""
        return _coerce_str(v)

    _name_validator = field_validator("name", mode="before")(_coerce_field)
    _type_validator = field_validator("type", mode="before")(_coerce_field)
    _description_validator = field_validator("description", mode="before")(_coerce_field)


class _ExtractionEdge(BaseModel):
    """Edge schema for AutoGraph — represents an extracted relation."""

    source: str = ""
    target: str = ""
    relation_type: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    _src_validator = field_validator("source", mode="before")(_ExtractionNode._coerce_field)
    _tgt_validator = field_validator("target", mode="before")(_ExtractionNode._coerce_field)
    _rel_validator = field_validator("relation_type", mode="before")(_ExtractionNode._coerce_field)


def _coerce_str(value: Any) -> str:
    """Coerce a value to string; join lists with ',' to keep them hashable.

    Some HE templates return `type`/`name` as lists, which breaks downstream
    set operations (unhashable type: 'list'). This helper normalizes them.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value if v is not None)
    return str(value)


def _node_key_extractor(node: _ExtractionNode) -> str:
    """Extract unique key from a node (by name)."""
    return getattr(node, "name", "") or ""


def _edge_key_extractor(edge: _ExtractionEdge) -> str:
    """Extract unique key from an edge (source-relation_type-target)."""
    src = getattr(edge, "source", "") or ""
    rel = getattr(edge, "relation_type", "") or ""
    tgt = getattr(edge, "target", "") or ""
    return f"{src}-{rel}-{tgt}"


def _nodes_in_edge_extractor(edge: _ExtractionEdge) -> Tuple[str, str]:
    """Extract (source_key, target_key) from an edge for validation."""
    src = getattr(edge, "source", "") or ""
    tgt = getattr(edge, "target", "") or ""
    return (src, tgt)


class HEAdapter:
    """Hyper-Extract adapter — sole entry point to HE API.

    All HE API calls MUST go through this adapter to ensure consistent
    kwarg names and result normalization.
    """

    def __init__(self):
        self._available = False
        self._Template = None
        self._AutoGraph = None
        self._create_llm_fn = None
        self._create_embedder_fn = None
        self._embedder_cache = None  # Cache: None=not tried, False=failed, obj=embedder

        try:
            from hyperextract import Template, AutoGraph
            from hyperextract.utils.client import create_llm, create_embedder, _parse_client_spec

            self._Template = Template
            self._AutoGraph = AutoGraph
            self._create_llm_fn = create_llm
            self._create_embedder_fn = create_embedder
            self._parse_client_spec = _parse_client_spec
            self._available = True
            logger.info("hyperextract 已加载")
        except ImportError:
            logger.warning("hyperextract 未安装，HE 适配器不可用")

    def is_available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def parse(
        self,
        text: str,
        template: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extract structured data from text using a HE template.

        Args:
            text: Input text to extract from.
            template: Template config dict with 'template_path' or full
                      template config for AutoGraph.

        Returns:
            Normalized dict {"entities": [...], "relations": [...]} or None.
        """
        if not text:
            return None
        if not self._available:
            raise RuntimeError("hyperextract 未安装或不可用")

        llm_client = self._create_llm_client()
        try:
            embedder = self._create_embedder()
        except Exception as embed_err:
            logger.warning("Embedder creation failed, using LLM-only mode: %s", embed_err)
            embedder = None

        if template and template.get("template_path"):
            auto_type = self._Template.create(
                source=template["template_path"],
                language=template.get("language", "zh"),
                llm_client=llm_client,
                embedder=embedder,
            )
        else:
            auto_type = self._build_auto_graph(template or {}, llm_client, embedder)

        try:
            result = auto_type.parse(text)
            return self._normalize_result(result)
        except Exception as parse_err:
            logger.warning("Template parse failed, trying AutoGraph fallback: %s", parse_err)
            try:
                auto_graph = self._build_auto_graph(
                    {"language": template.get("language", "zh")} if template else {},
                    llm_client,
                    embedder,
                )
                result = auto_graph.parse(text)
                return self._normalize_result(result)
            except Exception as fallback_err:
                logger.error("AutoGraph fallback also failed: %s", fallback_err)
                return None

    def parse_batch(
        self,
        texts: List[str],
        template: Optional[Dict[str, Any]] = None,
    ) -> List[Optional[Dict[str, Any]]]:
        """Batch extraction with per-text error isolation.

        Each text is parsed independently. If one fails, it returns None
        for that text without affecting others.

        Args:
            texts: List of input texts.
            template: Template config dict.

        Returns:
            List of results (or None for failed texts), same length as texts.
        """
        if not self._available:
            raise RuntimeError("hyperextract 未安装或不可用")

        results: List[Optional[Dict[str, Any]]] = []
        for text in texts:
            try:
                result = self.parse(text, template=template)
                results.append(result)
            except Exception as e:
                logger.error(f"parse_batch: text extraction failed: {e}")
                results.append(None)
        return results

    def feed_text(
        self,
        existing_result: Any,
        new_text: str,
    ) -> Optional[Dict[str, Any]]:
        """Incremental extraction — append new text to existing result.

        Uses BaseAutoType.feed_text() (NOT evolve) per real HE API.

        Args:
            existing_result: A BaseAutoType instance from a previous parse().
            new_text: New text to extract and merge.

        Returns:
            Normalized dict {"entities": [...], "relations": [...]} or None.
        """
        if not self._available:
            raise RuntimeError("hyperextract 未安装或不可用")
        if not new_text:
            return None

        try:
            updated = existing_result.feed_text(new_text)
            return self._normalize_result(updated)
        except Exception as e:
            logger.error(f"feed_text failed: {e}")
            raise

    # ------------------------------------------------------------------
    # Merge (manual — HE has no native graph merge API)
    # ------------------------------------------------------------------

    def merge_results(
        self,
        results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge multiple extraction results with deduplication.

        HE has no native graph merge API. This method deduplicates:
        - Entities by name (keep first occurrence)
        - Relations by (source, type, target) triplet

        Args:
            results: List of normalized result dicts.

        Returns:
            Merged dict {"entities": [...], "relations": [...]}.
        """
        merged_entities: List[Dict[str, Any]] = []
        merged_relations: List[Dict[str, Any]] = []
        seen_entity_names: set = set()
        seen_relation_keys: set = set()

        for result in results:
            if not result:
                continue

            for entity in result.get("entities", []):
                name = entity.get("name", "")
                if name and name not in seen_entity_names:
                    seen_entity_names.add(name)
                    merged_entities.append(entity)

            for relation in result.get("relations", []):
                source = relation.get("source", "")
                target = relation.get("target", "")
                rtype = relation.get("relation_type", relation.get("type", ""))
                key = (source, rtype, target)
                if key not in seen_relation_keys:
                    seen_relation_keys.add(key)
                    merged_relations.append(relation)

        return {"entities": merged_entities, "relations": merged_relations}

    # ------------------------------------------------------------------
    # Trial Extraction (for template assessment)
    # ------------------------------------------------------------------

    def trial_extract(
        self,
        text: str,
        template: Optional[Dict[str, Any]] = None,
        sample_size: int = 1500,
    ) -> Dict[str, Any]:
        """Trial extraction for template scoring.

        Truncates text to sample_size, parses, and returns metrics
        for template assessment scoring.

        Args:
            text: Input text (will be truncated).
            template: Template config dict.
            sample_size: Max chars to extract from (default 1500).

        Returns:
            Dict with entity_count, relation_count, field_coverage,
            type_diversity, types_found.
        """
        if not self._available:
            raise RuntimeError("hyperextract 未安装或不可用")

        sampled = text[:sample_size]
        result = self.parse(sampled, template=template)

        if not result:
            return {
                "entity_count": 0,
                "relation_count": 0,
                "field_coverage": 0.0,
                "type_diversity": 0.0,
                "types_found": [],
            }

        entities = result.get("entities", [])
        relations = result.get("relations", [])
        # Build types_found defensively — `type` may be a list for some HE
        # templates, so coerce each to string before adding to the set.
        types_set: set = set()
        for e in entities:
            t = e.get("type", "")
            if isinstance(t, (list, tuple)):
                for t_item in t:
                    if t_item:
                        types_set.add(str(t_item))
            elif t:
                types_set.add(str(t))
        types_found = list(types_set)

        # field_coverage: fraction of entities with non-empty description
        entities_with_desc = sum(1 for e in entities if e.get("description"))
        field_coverage = entities_with_desc / len(entities) if entities else 0.0

        # type_diversity: unique types / total entities (0-1)
        type_diversity = len(types_found) / len(entities) if entities else 0.0

        return {
            "entity_count": len(entities),
            "relation_count": len(relations),
            "field_coverage": round(field_coverage, 4),
            "type_diversity": round(type_diversity, 4),
            "types_found": types_found,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_auto_graph(self, template: Dict[str, Any], llm_client, embedder):
        """Build AutoGraph instance from template dict.

        AutoGraph requires Pydantic BaseModel *classes* (with __name__) for
        node_schema/edge_schema, plus callable key extractors. The template
        dict may carry string hints (node_schema/edge_schema/entity_types/
        relation_types) but those are NOT used as schema classes — we use
        _ExtractionNode/_ExtractionEdge which align with _normalize_result().

        The template dict may override:
        - extraction_mode: "one_stage" (default) or "two_stage"
        - node_key_extractor / edge_key_extractor / nodes_in_edge_extractor:
          callable overrides (rarely needed; defaults follow the schema)
        """
        node_key_extractor = template.get("node_key_extractor") or _node_key_extractor
        edge_key_extractor = template.get("edge_key_extractor") or _edge_key_extractor
        nodes_in_edge_extractor = (
            template.get("nodes_in_edge_extractor") or _nodes_in_edge_extractor
        )
        extraction_mode = template.get("extraction_mode", "one_stage")

        return self._AutoGraph(
            node_schema=_ExtractionNode,
            edge_schema=_ExtractionEdge,
            node_key_extractor=node_key_extractor,
            edge_key_extractor=edge_key_extractor,
            nodes_in_edge_extractor=nodes_in_edge_extractor,
            llm_client=llm_client,
            embedder=embedder,
            extraction_mode=extraction_mode,
        )

    def _create_llm_client(self):
        """Create LLM client from ODAP config using HE create_llm()."""
        api_key = get_config("llm.api_key", "")
        api_base = get_config("llm.api_base", "")
        model = get_config("llm.model", "gpt-4o")

        if api_base:
            spec = f"openai:{model}@{api_base}"
        else:
            spec = f"openai:{model}"

        config = self._parse_client_spec(spec, api_key=api_key, default_kind="llm")

        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config["model"],
            api_key=config["api_key"] or os.environ.get("OPENAI_API_KEY", ""),
            base_url=config.get("base_url") or None,
            temperature=config.get("temperature", 0),
            response_format={"type": "json_object"},
        )

    def _create_embedder(self):
        """Create embedder from ODAP config (cached — only attempted once).

        Strategy (provider=auto):
        1. Try SaaS API embedder (OpenAI/NVIDIA compatible /embeddings endpoint).
        2. If API fails (404/500/timeout), try local HuggingFace embedder.
        3. If local also fails (missing sentence-transformers), return None (LLM-only mode).

        provider=api:  Only try SaaS API.
        provider=local: Only try local HuggingFace.

        Embedder creation is expensive (API round-trips) and rarely succeeds
        with non-OpenAI endpoints. We cache the result per HEAdapter instance.
        """
        if self._embedder_cache is not None:
            return self._embedder_cache if self._embedder_cache is not False else None

        provider = get_config("llm.embedder_provider", "auto")

        result = None
        if provider == "local":
            result = self._create_local_embedder()
            if result is None:
                logger.warning("Local embedder unavailable, trying SaaS API as fallback")
                result = self._create_api_embedder()
        elif provider == "api":
            result = self._create_api_embedder()
            if result is None:
                logger.warning("API embedder unavailable, trying local as fallback")
                result = self._create_local_embedder()
        else:
            # provider == "auto": try API first, then local
            result = self._create_api_embedder()
            if result is None:
                logger.info("API embedder unavailable, trying local HuggingFace")
                result = self._create_local_embedder()

        if result is None:
            logger.warning("All embedder strategies failed, using LLM-only mode")
        self._embedder_cache = result if result is not None else False
        return result

    def _create_api_embedder(self):
        """Create SaaS API embedder using OpenAI-compatible /embeddings endpoint.

        Uses langchain_openai.OpenAIEmbeddings with the configured API key/base.
        NVIDIA NIM supports baai/bge-m3; OpenAI supports text-embedding-3-small.
        """
        try:
            api_key = get_config("llm.api_key", "") or os.environ.get("OPENAI_API_KEY", "")
            api_base = get_config("llm.api_base", "") or os.environ.get("OPENAI_API_BASE", "")
            model = get_config("llm.embedder_model", "text-embedding-3-small")

            from langchain_openai import OpenAIEmbeddings

            kwargs = {
                "model": model,
                "api_key": api_key,
            }
            if api_base:
                kwargs["base_url"] = api_base

            embedder = OpenAIEmbeddings(**kwargs)

            # Smoke test — some APIs don't support /embeddings
            embedder.embed_query("test")
            logger.info(f"SaaS API embedder OK (model={model}, base={api_base})")
            return embedder
        except Exception as e:
            logger.warning(f"SaaS API embedder failed: {e}")
            return None

    @staticmethod
    def _create_local_embedder():
        """Create a local HuggingFace embedder (no API required).

        Uses BAAI/bge-small-zh-v1.5 — a lightweight (95MB) Chinese/English
        embedding model with 512-dim vectors. Downloaded once and cached.

        Returns None if sentence-transformers is not installed (graceful degradation).
        """
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        except ImportError:
            logger.warning(
                "HuggingFaceEmbeddings unavailable (sentence-transformers not installed)"
            )
            return None

        model_name = get_config(
            "llm.embedder_local_model", "BAAI/bge-small-zh-v1.5"
        )
        logger.info(f"Using local HuggingFace embedder: {model_name}")
        try:
            return HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except Exception as e:
            logger.warning(f"Local HuggingFace embedder init failed: {e}")
            return None

    @staticmethod
    def _normalize_result(result) -> Dict[str, Any]:
        """Normalize HE result to {"entities": [...], "relations": [...]}.

        Accesses .nodes and .edges directly (NOT dump_dict()).
        Coerces `type` to string — some HE templates return a list of types
        per node, which would break downstream set operations.
        """
        entities: list = []
        relations: list = []

        nodes = getattr(result, "nodes", None)
        edges = getattr(result, "edges", None)

        if nodes:
            for node in nodes:
                entities.append({
                    "name": _coerce_str(getattr(node, "name", getattr(node, "key", ""))),
                    "type": _coerce_str(getattr(node, "type", "")),
                    "description": _coerce_str(getattr(node, "description", "")),
                    "properties": getattr(node, "properties", {}),
                })

        if edges:
            for edge in edges:
                relations.append({
                    "source": _coerce_str(getattr(edge, "source", getattr(edge, "source_node", ""))),
                    "target": _coerce_str(getattr(edge, "target", getattr(edge, "target_node", ""))),
                    "relation_type": _coerce_str(getattr(edge, "relation_type", getattr(edge, "type", ""))),
                    "properties": getattr(edge, "properties", {}),
                })

        if not entities and not relations and isinstance(result, dict):
            entities = result.get("entities") or result.get("nodes") or []
            relations = result.get("relations") or result.get("edges") or []

        return {
            "entities": entities,
            "relations": relations,
        }
