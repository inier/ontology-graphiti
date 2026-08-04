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
import os
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

from odap.infra.config_composer import get_config

logger = logging.getLogger("he_adapter")

_DEFAULT_TEMPLATE_YAML = os.path.join(
    os.path.dirname(__file__), "..", "templates", "chinese_ontology_graph.yaml"
)


def get_kb_path(workspace_id: str, ontology_id: str) -> str:
    """Iter 2.1: Resolve the HE Knowledge Abstract persistence path.

    Convention (plan 009 §2.1):
        data/he_kb/{workspace_id}/{ontology_id}/

    The base path can be overridden via config key ``he.kb_base_path``
    (relative paths resolve against the API working directory).

    Args:
        workspace_id: Workspace identifier (defaults to "default" upstream).
        ontology_id: Ontology identifier.

    Returns:
        Absolute-or-relative directory path for the KA. The directory may
        not exist yet — callers create it via ``HEAdapter.feed_to_kb``.
    """
    base = get_config("he.kb_base_path", "data/he_kb")
    ws = workspace_id or "default"
    ont = ontology_id or "default"
    return os.path.join(base, ws, ont)


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


def _clean_json_response(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace >= first_brace:
        return text[first_brace : last_brace + 1]
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket >= first_bracket:
        return text[first_bracket : last_bracket + 1]
    return text


_CUSTOM_NODE_PROMPT = (
    "你是一位专业的中文本体与知识图谱抽取专家。请从以下文本中精确抽取所有相关的实体、概念或节点。\n\n"
    "【严格抽取规则】\n"
    "1. 实体必须是完整的名词性短语，不得残缺或截断\n"
    "2. 实体不得以介词开头（与、在、对、为、从、向、把、被、让、给、通过、根据、关于、对于、将、使）\n"
    "3. 实体不得以连词开头（和、及、或、并、以及）\n"
    "4. 实体不得是动词短语（如：构建、执行、进行、完成、实现 + 名词）\n"
    "5. 实体必须是文本中实际出现的完整名称，不得截取片段\n"
    "6. 每个实体应有独立指代意义，排除纯代词、泛称\n"
    "7. 同一实体在全文中保持命名一致\n\n"
    "【实体类型白名单 — 从以下分类中选择最匹配的类型】\n"
    "- 系统: 软件系统、信息系统、计算系统\n"
    "- 平台: 服务平台、管理平台、交易平台\n"
    "- 模块: 功能模块、业务模块、子系统\n"
    "- 概念: 抽象概念、理论、模型、标准\n"
    "- 流程: 业务流程、工作流程、操作流程\n"
    "- 规则: 业务规则、计算规则、约束条件\n"
    "- 数据: 数据集合、数据模型、数据库\n"
    "- 服务: 服务接口、API、微服务\n"
    "- 人员: 角色、用户、参与者\n"
    "- 组织: 机构、部门、团队\n"
    "- 产品: 商品、产品、应用\n"
    "- 技术: 技术方法、算法、框架\n\n"
    "【错误示例 — 以下均为不合格实体，严禁输出】\n"
    "- ❌ '与个性化推荐系统' — 以介词'与'开头\n"
    "- ❌ '在平台统一规则' — 以介词'在'开头\n"
    "- ❌ '构建会员' — 动词短语，'构建'是动词\n"
    "- ❌ '员注册与成长流程' — 残缺片段，缺少'会'字\n"
    "- ❌ '能分账与结算系统' — 残缺片段，缺少前半部分\n"
    "- ❌ '执行操作' — 动词短语\n"
    "- ❌ '进行处理' — 动词短语\n\n"
    "【正确示例】\n"
    "- ✅ '个性化推荐系统' — 完整名词短语，类型：系统\n"
    "- ✅ '平台统一规则' — 完整名词短语，类型：规则\n"
    "- ✅ '会员注册与成长流程' — 完整流程名称，类型：流程\n"
    "- ✅ '分账与结算系统' — 完整系统名称，类型：系统\n"
    "- ✅ '会员体系' — 完整概念名称，类型：概念\n"
    "- ✅ '对账与清算服务' — 完整服务名称，类型：服务\n\n"
    "【输出格式】\n"
    "仅输出有效的 JSON 对象，包含 items 字段，值为实体对象数组。\n"
    "每个实体对象必须包含：name（实体名称）、type（实体类型，从白名单中选择）、description（简要描述）。\n"
    "不要在 JSON 前后添加任何解释性文字。\n\n"
    "源文本：\n"
    "{source_text}"
)

_CUSTOM_EDGE_PROMPT = (
    "你是一位专业的中文关系抽取专家。请从以下文本中抽取已提供实体之间的关系（边）。\n\n"
    "【严格规则】\n"
    "1. 只能连接下方已知实体列表中的实体，不得臆造新实体\n"
    "2. 如果文本中的实体不在已知列表中，不要创建涉及它的关系\n"
    "3. 关系的 source 和 target 必须与已知实体列表中的 name 完全一致\n"
    "4. 仅在文本明确表达语义联系时创建关系，不要凭常识补充隐含关系\n"
    "5. 关系方向必须与文本描述一致\n"
    "6. 不得为不存在的实体创建关系\n\n"
    "【关系类型白名单 — 从以下分类中选择最匹配的类型】\n"
    "- 包含: 整体与组成部分（系统包含模块）\n"
    "- 属于: 从属、归属（模块属于系统）\n"
    "- 使用: 工具、方法、资源的利用（模块使用数据）\n"
    "- 依赖: 必要条件、前置关系（流程依赖规则）\n"
    "- 关联: 相关但非直接的联系（系统关联平台）\n"
    "- 提供: 服务、功能、资源的交付（服务提供接口）\n"
    "- 调用: 接口、方法的使用（模块调用服务）\n"
    "- 基于: 基础、根据（实现基于技术）\n"
    "- 通过: 途径、手段（流程通过规则实现）\n"
    "- 实现: 目标与手段（模块实现功能）\n"
    "- 管理: 管控、治理（平台管理模块）\n"
    "- 涉及: 牵涉、关联（数据涉及流程）\n\n"
    "【输出格式】\n"
    "仅输出有效的 JSON 对象，包含 items 字段，值为关系对象数组。\n"
    "每个关系对象必须包含：source（源实体名称）、target（目标实体名称）、relation_type（关系类型，从白名单中选择）。\n"
    "不要在 JSON 前后添加任何解释性文字。\n\n"
    "已知实体列表：\n"
    "{known_nodes}\n\n"
    "源文本：\n"
    "{source_text}"
)


class _JsonCleaningLLM:
    """LLM wrapper that cleans JSON responses before returning.

    Some LLMs (especially Chinese models) may return non-pure JSON responses
    with prefixes like "我们{...}" or suffixes. This wrapper strips those
    and returns only the JSON part.
    """

    def __init__(self, llm_client):
        self._llm = llm_client

    def invoke(self, input_data, **kwargs):
        if hasattr(input_data, 'to_messages'):
            messages = input_data.to_messages()
        elif isinstance(input_data, dict) and 'messages' in input_data:
            messages = input_data['messages']
        else:
            messages = input_data
        response = self._llm.invoke(messages, **kwargs)
        if hasattr(response, 'content') and response.content:
            cleaned = _clean_json_response(response.content)
            response.content = cleaned
        return response

    def batch(self, messages_list, **kwargs):
        responses = self._llm.batch(messages_list, **kwargs)
        for response in responses:
            if hasattr(response, 'content') and response.content:
                cleaned = _clean_json_response(response.content)
                response.content = cleaned
        return responses

    def with_structured_output(self, schema):
        from langchain_core.runnables import RunnableLambda
        structured_chain = self._llm.with_structured_output(schema)

        def _clean_and_parse(input_data):
            try:
                result = structured_chain.invoke(input_data)
                return result
            except Exception:
                if hasattr(input_data, 'to_messages'):
                    messages = input_data.to_messages()
                elif isinstance(input_data, dict) and 'messages' in input_data:
                    messages = input_data['messages']
                else:
                    messages = input_data
                raw_response = self._llm.invoke(messages)
                text = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
                cleaned = _clean_json_response(text)
                try:
                    import json
                    data = json.loads(cleaned)
                    return schema(**data) if hasattr(schema, '__call__') else schema.model_validate(data)
                except Exception:
                    try:
                        return schema.model_validate_json(cleaned)
                    except Exception:
                        return schema()

        return RunnableLambda(_clean_and_parse)


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

        Optimization: Defaults to the Chinese ontology YAML template which
        provides entity type whitelists, proper chunk_size (4096), and
        one_stage extraction mode for better quality. Falls back to the
        hardcoded AutoGraph if template loading fails.

        Args:
            text: Input text to extract from.
            template: Template config dict with 'template_path' or full
                      template config for AutoGraph. If None, uses the
                      default Chinese ontology YAML template.

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

        auto_type = None
        template_to_use = template or self._resolve_default_template(template)

        if template_to_use and template_to_use.get("template_path"):
            try:
                auto_type = self._Template.create(
                    source=template_to_use["template_path"],
                    language=template_to_use.get("language", "zh"),
                    llm_client=llm_client,
                    embedder=embedder,
                )
                logger.info("Using YAML template: %s", template_to_use["template_path"])
            except Exception as template_err:
                logger.warning(
                    "YAML template load failed (%s), falling back to hardcoded AutoGraph",
                    template_err,
                )
                auto_type = None

        if auto_type is None:
            auto_type = self._build_auto_graph(
                template_to_use or {}, llm_client, embedder
            )
            logger.info("Using hardcoded AutoGraph fallback")

        try:
            result = auto_type.parse(text)
            normalized = self._normalize_result(result)
            if normalized.get("entities"):
                normalized = self._post_validate_entities(normalized, text)
            return normalized
        except Exception as parse_err:
            logger.warning("Template parse failed, trying AutoGraph fallback: %s", parse_err)
            try:
                auto_graph = self._build_auto_graph(
                    {"language": template_to_use.get("language", "zh")} if template_to_use else {},
                    llm_client,
                    embedder,
                )
                result = auto_graph.parse(text)
                return self._normalize_result(result)
            except Exception as fallback_err:
                logger.error("AutoGraph fallback also failed: %s", fallback_err)
                return None

    def _resolve_default_template(self, template: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve the default template when none is explicitly provided.

        Priority:
        1. Explicit template with template_path → use as-is
        2. Custom template without template_path → use as kwargs for _build_auto_graph
        3. No template at all → use Chinese ontology YAML template if available
        """
        if template and template.get("template_path"):
            return template

        if template:
            return template

        if os.path.isfile(_DEFAULT_TEMPLATE_YAML):
            return {
                "template_path": _DEFAULT_TEMPLATE_YAML,
                "language": "zh",
            }

        logger.warning("Default template not found at %s", _DEFAULT_TEMPLATE_YAML)
        return {}

    @staticmethod
    def _normalize_text_for_comparison(text: str) -> str:
        """Normalize text for entity validation comparison.

        Removes whitespace, common punctuation, and normalizes to lowercase
        for robust Chinese/English mixed text comparison.
        """
        import re
        normalized = text.lower()
        normalized = re.sub(r'[\s\u3000]+', '', normalized)
        normalized = re.sub(r'[，。！？、；：""''（）【】《》,.;:!?\[\]()""\']+', '', normalized)
        return normalized

    @staticmethod
    def _post_validate_entities(
        normalized: Dict[str, Any], source_text: str
    ) -> Dict[str, Any]:
        """Post-validate entities against source text.

        Uses lenient validation:
        1. Hard filter: entities shorter than 2 characters
        2. Soft check: normalize whitespace/punctuation before substring match
           - If entity name is found in normalized source → keep
           - If NOT found → add 'possible_hallucination' quality flag instead
             of hard filtering (LLM may have slightly rephrased the name)
        3. Filter relations whose endpoints are not in valid entity set

        Args:
            normalized: Normalized result with entities and relations
            source_text: Original source text for substring validation

        Returns:
            Validated result with quality flags
        """
        entities = normalized.get("entities", [])
        relations = normalized.get("relations", [])
        normalized_source = HEAdapter._normalize_text_for_comparison(source_text)
        valid_names = set()
        filtered_entities = []

        for entity in entities:
            name = entity.get("name", "")
            if not name or len(name.strip()) < 2:
                logger.debug("Filtered entity (too short/empty): '%s'", name)
                continue

            normalized_name = HEAdapter._normalize_text_for_comparison(name)
            found_in_source = (
                normalized_name in normalized_source
                or name in source_text
            )

            if not found_in_source:
                logger.info(
                    "Entity not found in source (soft flag): '%s' "
                    "(normalized: '%s')",
                    name, normalized_name,
                )
                entity = {**entity, "possible_hallucination": True}

            filtered_entities.append(entity)
            valid_names.add(name)

        filtered_relations = []
        for rel in relations:
            src = rel.get("source", "")
            tgt = rel.get("target", "")
            if src in valid_names and tgt in valid_names:
                filtered_relations.append(rel)
            else:
                logger.debug(
                    "Filtered relation (endpoint not in valid entities): %s->%s",
                    src,
                    tgt,
                )

        hallucination_count = sum(
            1 for e in filtered_entities if e.get("possible_hallucination")
        )
        if hallucination_count > 0:
            logger.info(
                "Post-validation: %d entities flagged as possible hallucination",
                hallucination_count,
            )

        return {
            "entities": filtered_entities,
            "relations": filtered_relations,
        }

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
    # Iter 2.1: Persistent Knowledge Abstract (kb) — continuous engine
    # ------------------------------------------------------------------

    def feed_to_kb(
        self,
        kb_path: str,
        text: str,
        template: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Iter 2.1: Incrementally feed text to a persistent Knowledge Abstract.

        Uses HE's native Template.create() + ka.load() + ka.feed_text() +
        ka.dump() to persist evolving knowledge to disk.

        Workflow:
            1. Resolve template (explicit > default Chinese ontology YAML).
            2. Create KA instance via Template.create().
            3. If kb_path/metadata.json exists → ka.load(kb_path) (accumulate).
               Else → mkdir parents (new KA).
            4. ka.feed_text(text) — HE handles extraction + incremental merge.
            5. ka.dump(kb_path) — persist updated KA to disk.

        Args:
            kb_path: Directory path for the Knowledge Abstract.
                Convention: data/he_kb/{workspace_id}/{ontology_id}/
            text: New text to extract and merge into the KA.
            template: Optional template config with 'template_path' and
                'language'. If None, uses the default Chinese ontology YAML.

        Returns:
            True if the feed succeeded, False on failure.
        """
        if not self._available:
            raise RuntimeError("hyperextract 未安装或不可用")
        if not text or not text.strip():
            logger.warning("feed_to_kb: empty text, skipping")
            return False

        llm_client = self._create_llm_client()
        try:
            embedder = self._create_embedder()
        except Exception as embed_err:
            logger.warning("Embedder creation failed, using LLM-only mode: %s", embed_err)
            embedder = None

        template_to_use = self._resolve_default_template(template)
        source = template_to_use.get("template_path") or "general/graph"
        language = template_to_use.get("language", "zh")

        import json
        from pathlib import Path

        kb_dir = Path(kb_path)
        metadata_file = kb_dir / "metadata.json"

        try:
            ka = self._Template.create(
                source, language,
                llm_client=llm_client, embedder=embedder,
            )

            if metadata_file.exists():
                # Existing KA: load accumulated state, then feed
                ka.load(str(kb_dir))
                logger.info("Loaded existing KA from %s", kb_path)
            else:
                # New KA: ensure directory exists before dump
                kb_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Creating new KA at %s", kb_path)

            ka.feed_text(text)
            ka.dump(str(kb_dir))
            logger.info("Fed %d chars to KA at %s", len(text), kb_path)
            return True
        except Exception as e:
            logger.error("feed_to_kb failed for %s: %s", kb_path, e)
            return False

    def load_from_kb(self, kb_path: str) -> Optional[Dict[str, Any]]:
        """Iter 2.1: Load accumulated knowledge from a persistent KA.

        Reads the KA from disk and returns its current state as a normalized
        dict. Used by extract_from_document to read accumulated knowledge
        instead of re-parsing from scratch.

        Args:
            kb_path: Directory path for the Knowledge Abstract.

        Returns:
            Normalized dict {"entities": [...], "relations": [...]} or None
            if the KA does not exist or cannot be loaded.
        """
        if not self._available:
            raise RuntimeError("hyperextract 未安装或不可用")

        import json
        from pathlib import Path

        kb_dir = Path(kb_path)
        metadata_file = kb_dir / "metadata.json"
        if not metadata_file.exists():
            logger.info("KA not found at %s, returning None", kb_path)
            return None

        # Read template info from metadata to recreate KA instance
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            logger.warning("Failed to read KA metadata: %s", e)
            metadata = {}

        source = metadata.get("template", "general/graph")
        language = metadata.get("lang", "zh")

        llm_client = self._create_llm_client()
        try:
            embedder = self._create_embedder()
        except Exception as embed_err:
            logger.warning("Embedder creation failed, using LLM-only mode: %s", embed_err)
            embedder = None

        try:
            ka = self._Template.create(
                source, language,
                llm_client=llm_client, embedder=embedder,
            )
            ka.load(str(kb_dir))
            return self._normalize_result(ka)
        except Exception as e:
            logger.error("load_from_kb failed for %s: %s", kb_path, e)
            return None

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

        Critical configuration overrides (for Chinese text quality):
        - chunk_size: 4096 chars (default 2048 is too small for Chinese, causes
          entity truncation at word boundaries)
        - chunk_overlap: 512 chars (provides context continuity across chunks)
        - extraction_mode: "one_stage" (default; two_stage wastes context
          by injecting full node list into edge extraction prompt)
        """
        node_key_extractor = template.get("node_key_extractor") or _node_key_extractor
        edge_key_extractor = template.get("edge_key_extractor") or _edge_key_extractor
        nodes_in_edge_extractor = (
            template.get("nodes_in_edge_extractor") or _nodes_in_edge_extractor
        )
        extraction_mode = template.get("extraction_mode", "one_stage")
        chunk_size = template.get("chunk_size", 4096)
        chunk_overlap = template.get("chunk_overlap", 512)

        return self._AutoGraph(
            node_schema=_ExtractionNode,
            edge_schema=_ExtractionEdge,
            node_key_extractor=node_key_extractor,
            edge_key_extractor=edge_key_extractor,
            nodes_in_edge_extractor=nodes_in_edge_extractor,
            llm_client=llm_client,
            embedder=embedder,
            extraction_mode=extraction_mode,
            prompt_for_node_extraction=_CUSTOM_NODE_PROMPT,
            prompt_for_edge_extraction=_CUSTOM_EDGE_PROMPT,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
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
        llm = ChatOpenAI(
            model=config["model"],
            api_key=config["api_key"] or os.environ.get("OPENAI_API_KEY", ""),
            base_url=config.get("base_url") or None,
            temperature=config.get("temperature", 0),
        )
        return _JsonCleaningLLM(llm)

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
                name = _coerce_str(getattr(node, "name", getattr(node, "key", "")))
                entities.append({
                    "name": name,
                    "display_name": _coerce_str(getattr(node, "display_name", name)),
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
