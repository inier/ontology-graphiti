import hashlib
import logging
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger("ontology_mapper")

# ODAP 5 output categories for entity classification
_ACTION_ENTITY_KEYWORDS = ("action", "act", "buy", "sell", "execute", "transfer", "perform")
_RULE_ENTITY_KEYWORDS = ("rule", "constraint", "policy", "regulation", "law")
_PROCESS_ENTITY_KEYWORDS = ("process", "workflow", "procedure", "flow", "step")

# Chinese prepositions that should be stripped from entity name beginnings
_CN_PREPOSITIONS = (
    "与", "在", "从", "向", "把", "被", "让", "给",
    "通过", "根据", "关于", "对于", "由于", "基于", "针对", "按照",
    "凭借", "沿着", "顺着", "往", "朝",
)

# Chinese conjunctions that should be stripped from entity name beginnings
_CN_CONJUNCTIONS = ("和", "与", "及", "或", "并", "以及", "或是", "或者")

# Chinese verbs that indicate verb phrases (not valid entity names)
# These are STRIPPED from entity names during cleaning
_CN_VERB_PREFIXES = (
    "构建", "创建", "执行", "进行", "实现", "完成", "开展", "组织",
    "管理", "提供", "支持", "配置", "部署", "安装", "集成", "对接",
    "开发", "设计", "规划", "分析", "评估", "监控", "检测", "验证",
    "注册", "登录", "提交", "发送", "接收", "处理", "转换",
    "计算", "存储", "查询", "更新", "删除", "新增", "审核", "审批",
    "分配", "调度", "同步", "异步", "触发", "响应", "操作", "维护",
    "生成", "建立", "制定", "编制", "发布", "上线", "下线", "接入",
    "输出", "输入", "读取", "写入", "加载", "卸载", "启动", "停止",
    "使能", "禁用", "启用", "开启", "关闭", "连接", "断开",
    "登记", "记录", "追踪", "日志", "报告", "通知", "告警", "预警",
    "支付", "结算", "对账",
    "推荐", "匹配", "推送", "分发", "路由", "转发", "代理",
)

# Single Chinese characters that are likely fragments when they appear at
# the start of an entity name (second half of a 2-character word that was
# truncated during text chunking).
# E.g., "员" from "会员", "理" from "管理", "能" from "智能"
_CN_TRUNCATION_FRAGMENT_CHARS = set(
    "员理能识合"
)

# Minimum entity name length (Chinese characters)
_MIN_ENTITY_NAME_LEN = 2


def clean_entity_name(raw_name: str) -> Tuple[str, List[str]]:
    """Clean an extracted entity name by removing Chinese function words.

    Strips prepositions, conjunctions, and verb prefixes from entity names.
    Returns (cleaned_name, list_of_issues).

    Issues:
    - "preposition_stripped": a preposition was removed from the beginning
    - "conjunction_stripped": a conjunction was removed from the beginning
    - "verb_phrase": entity name started with a verb prefix (now stripped)
    - "too_short": entity name is too short to be a valid entity
    - "fragment": entity name looks like a truncated fragment
    - "truncated_prefix": name starts with a character that looks like
      the second half of a truncated word (e.g., "员" from "会员")
    """
    if not raw_name or not raw_name.strip():
        return (raw_name, ["empty"])

    name = raw_name.strip()
    issues: List[str] = []

    if len(name) < _MIN_ENTITY_NAME_LEN:
        issues.append("too_short")

    changed = True
    while changed:
        changed = False
        for prep in _CN_PREPOSITIONS:
            if name.startswith(prep) and len(name) > len(prep):
                name = name[len(prep):]
                issues.append("preposition_stripped")
                changed = True
                break
        if changed:
            continue
        for conj in _CN_CONJUNCTIONS:
            if name.startswith(conj) and len(name) > len(conj):
                name = name[len(conj):]
                issues.append("conjunction_stripped")
                changed = True
                break

    _CN_VERB_FOLLOWING_CONJUNCTIONS = ("与", "和", "及", "并", "或")

    for verb in _CN_VERB_PREFIXES:
        if name.startswith(verb):
            rest = name[len(verb):]
            if rest and rest.startswith(_CN_VERB_FOLLOWING_CONJUNCTIONS):
                break
            if rest and len(rest) >= _MIN_ENTITY_NAME_LEN:
                name = rest
                issues.append("verb_phrase_stripped")
                changed = True
            elif rest:
                issues.append("verb_phrase")
            break

    if changed:
        for verb in _CN_VERB_PREFIXES:
            if name.startswith(verb):
                rest = name[len(verb):]
                if rest and rest.startswith(_CN_VERB_FOLLOWING_CONJUNCTIONS):
                    break
                if rest and len(rest) >= _MIN_ENTITY_NAME_LEN:
                    name = rest
                    issues.append("verb_phrase_stripped")
                break

    if name and len(name) >= 2 and name[0] in _CN_TRUNCATION_FRAGMENT_CHARS:
        issues.append("truncated_prefix")

    if len(name) < _MIN_ENTITY_NAME_LEN and len(raw_name) >= _MIN_ENTITY_NAME_LEN:
        issues.append("fragment")

    return (name, issues)


def is_valid_entity_name(name: str) -> bool:
    """Check if an entity name is valid after cleaning.

    Returns True if the name should be kept, False if it should be filtered out.
    """
    if not name or not name.strip():
        return False
    cleaned, issues = clean_entity_name(name)
    if "too_short" in issues or "fragment" in issues:
        return False
    if "truncated_prefix" in issues:
        return False
    if "verb_phrase" in issues:
        return False
    if not cleaned or len(cleaned) < _MIN_ENTITY_NAME_LEN:
        return False
    return True


class OntologyMapper:
    """将 HE 抽取结果映射到 ODAP 本体结构

    根据 ontology_id 从 OntologyService 加载合法的类型名称集合，
    在 map 阶段对实体类型和关系类型进行校验与映射。
    """

    def __init__(self, ontology_id: str = "", strict: bool = True):
        self._ontology_id = ontology_id
        self._strict = strict
        self._object_type_names: Set[str] = set()
        self._link_type_names: Set[str] = set()

        if ontology_id:
            self._load_ontology_types()

    def _load_ontology_types(self) -> None:
        """从 OntologyService 加载合法的对象类型和关系类型名称"""
        try:
            from odap.biz.core.ontology.public import OntologyService

            svc = OntologyService()

            obj_result = svc.list_object_types(self._ontology_id)
            if obj_result.get("status") == "error":
                logger.warning(
                    "加载对象类型失败: %s", obj_result.get("message", "unknown")
                )
            else:
                for obj in obj_result.get("object_types", []):
                    name = obj.get("name")
                    if name:
                        self._object_type_names.add(name)

            link_result = svc.list_link_types(self._ontology_id)
            if link_result.get("status") == "error":
                logger.warning(
                    "加载关系类型失败: %s", link_result.get("message", "unknown")
                )
            else:
                for link in link_result.get("link_types", []):
                    name = link.get("name")
                    if name:
                        self._link_type_names.add(name)

            logger.info(
                "本体类型加载完成: ontology_id=%s, object_types=%d, link_types=%d",
                self._ontology_id,
                len(self._object_type_names),
                len(self._link_type_names),
            )
        except Exception as exc:
            logger.warning("加载本体类型异常: %s", exc)

    def map(self, ka: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """将 HE 抽取结果映射到 ODAP 本体结构

        Args:
            ka: 抽取结果，包含 "entities" 和 "relations" 列表

        Returns:
            映射后的结构，包含 "entities" 和 "relations"；
            输入无效时返回 {"status": "error", "message": "..."}
        """
        if not ka:
            return {"status": "error", "message": "抽取结果为空"}

        raw_entities = ka.get("entities")
        raw_relations = ka.get("relations")
        if raw_entities is None and raw_relations is None:
            return {"status": "error", "message": "抽取结果缺少 entities 和 relations"}

        mapped_entities = []
        for ent in (raw_entities or []):
            mapped = self._map_entity(ent)
            if mapped is not None:
                mapped_entities.append(mapped)

        mapped_relations = []
        for rel in (raw_relations or []):
            mapped = self._map_relation(rel)
            if mapped is not None:
                mapped_relations.append(mapped)

        logger.info(
            "本体映射完成: entities=%d→%d, relations=%d→%d",
            len(raw_entities or []),
            len(mapped_entities),
            len(raw_relations or []),
            len(mapped_relations),
        )

        return {
            "entities": mapped_entities,
            "relations": mapped_relations,
        }

    # ------------------------------------------------------------------
    # Multi-template merge (US2 / T056)
    # ------------------------------------------------------------------

    def merge_and_map(
        self,
        multi_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge multi-template extraction results and map to ODAP 5 classes.

        Steps:
            1. Collect entities and relations from all template results.
            2. Deduplicate entities by name (keep first, mark conflicts).
            3. Deduplicate relations by (source, relation_type, target).
            4. Classify entities into ODAP 5 classes:
               object_types, link_types, action_types, rule_types, process_types.
            5. Preserve source_template provenance per entity.

        Args:
            multi_results: List of {"entities": [...], "relations": [...],
                           "source_template": str}

        Returns:
            {
                "entities": [...],       # merged, deduplicated
                "relations": [...],      # merged, deduplicated
                "object_types": [...],
                "link_types": [...],
                "action_types": [...],
                "rule_types": [...],
                "process_types": [...],
                "conflicts": [...],      # name collisions with differing props
            }
        """
        if not multi_results:
            return {
                "entities": [],
                "relations": [],
                "object_types": [],
                "link_types": [],
                "action_types": [],
                "rule_types": [],
                "process_types": [],
                "conflicts": [],
            }

        merged_entities: List[Dict[str, Any]] = []
        seen_entity_names: Dict[str, Dict[str, Any]] = {}
        conflicts: List[Dict[str, Any]] = []

        merged_relations: List[Dict[str, Any]] = []
        seen_rel_keys: Set[Tuple[str, str, str]] = set()
        name_mapping: Dict[str, str] = {}

        for result in multi_results:
            source_template = result.get("source_template", "unknown")

            # Merge entities
            for ent in result.get("entities", []):
                raw_name = ent.get("name", "")
                original_type = ent.get("type", "")
                if not raw_name or not original_type:
                    continue

                cleaned_name, issues = clean_entity_name(raw_name)

                if "too_short" in issues or "fragment" in issues:
                    logger.info(
                        "实体名称质量过滤: 跳过 '%s' → '%s' (issues=%s)",
                        raw_name, cleaned_name, issues,
                    )
                    continue

                if "truncated_prefix" in issues:
                    logger.info(
                        "实体名称质量过滤: 跳过截断片段 '%s' → '%s' (issues=%s)",
                        raw_name, cleaned_name, issues,
                    )
                    continue

                if "verb_phrase" in issues:
                    logger.info(
                        "实体名称质量过滤: 跳过动词短语 '%s' → '%s' (issues=%s)",
                        raw_name, cleaned_name, issues,
                    )
                    continue

                if not cleaned_name or len(cleaned_name) < _MIN_ENTITY_NAME_LEN:
                    logger.info(
                        "实体名称质量过滤: 清洗后名称过短 '%s' → '%s'",
                        raw_name, cleaned_name,
                    )
                    continue

                if cleaned_name != raw_name:
                    logger.info(
                        "实体名称清洗: '%s' → '%s' (issues=%s)",
                        raw_name, cleaned_name, issues,
                    )
                    name_mapping[raw_name] = cleaned_name
                    ent = {**ent, "name": cleaned_name}

                name = cleaned_name

                # Classify by original type BEFORE mapping (which may change type)
                category = self._classify_entity_category(original_type)

                if category == "object":
                    # Object entities go through full type validation
                    mapped = self._map_entity(ent)
                    if mapped is None:
                        continue
                else:
                    # Action/Rule/Process entities skip object_type validation
                    mapped = {
                        "entity_id": self._deterministic_entity_id(original_type, name),
                        "name": name,
                        "display_name": ent.get("display_name", name),
                        "type": original_type,
                        "description": ent.get("description", ""),
                    }
                    raw_props = ent.get("properties", {})
                    if isinstance(raw_props, dict):
                        mapped.update(self._map_properties(raw_props))

                # Add source_template provenance
                mapped["source_template"] = source_template

                if name in seen_entity_names:
                    # Check for conflicts (different properties)
                    existing = seen_entity_names[name]
                    if self._entities_conflict(existing, mapped):
                        conflicts.append({
                            "name": name,
                            "source_template_1": existing.get("source_template", ""),
                            "source_template_2": source_template,
                            "field": "properties",
                        })
                    # Keep first occurrence, skip duplicate
                    continue

                seen_entity_names[name] = mapped
                merged_entities.append(mapped)

            # Merge relations
            for rel in result.get("relations", []):
                source = rel.get("source", "")
                target = rel.get("target", "")
                rel_type = rel.get("relation_type", "")

                if source in name_mapping:
                    source = name_mapping[source]
                if target in name_mapping:
                    target = name_mapping[target]

                cleaned_rel = {**rel, "source": source, "target": target}
                key = (source, rel_type, target)

                if key in seen_rel_keys:
                    continue

                mapped_rel = self._map_relation(cleaned_rel)
                if mapped_rel is not None:
                    mapped_rel["source_template"] = source_template
                    seen_rel_keys.add(key)
                    merged_relations.append(mapped_rel)

        # Classify entities into ODAP 5 classes
        object_types: List[Dict[str, Any]] = []
        action_types: List[Dict[str, Any]] = []
        rule_types: List[Dict[str, Any]] = []
        process_types: List[Dict[str, Any]] = []
        link_types: List[Dict[str, Any]] = []

        for ent in merged_entities:
            category = self._classify_entity_category(ent.get("type", ""))
            type_entry = {
                "name": ent.get("name", ""),
                "display_name": ent.get("display_name", ent.get("name", "")),
                "type": ent.get("type", ""),
                "description": ent.get("description", ""),
                "source_template": ent.get("source_template", ""),
            }
            if category == "action":
                action_types.append(type_entry)
            elif category == "rule":
                rule_types.append(type_entry)
            elif category == "process":
                process_types.append(type_entry)
            else:
                object_types.append(type_entry)

        # Relations → link_types
        for rel in merged_relations:
            rel_type = rel.get("relation_type", "")
            link_types.append({
                "name": rel_type,
                "display_name": rel.get("display_name", rel_type),
                "source": rel.get("source", ""),
                "target": rel.get("target", ""),
                "source_template": rel.get("source_template", ""),
            })

        logger.info(
            "merge_and_map 完成: entities=%d, relations=%d, conflicts=%d, "
            "object_types=%d, action_types=%d, rule_types=%d, process_types=%d",
            len(merged_entities),
            len(merged_relations),
            len(conflicts),
            len(object_types),
            len(action_types),
            len(rule_types),
            len(process_types),
        )

        return {
            "entities": merged_entities,
            "relations": merged_relations,
            "object_types": object_types,
            "link_types": link_types,
            "action_types": action_types,
            "rule_types": rule_types,
            "process_types": process_types,
            "conflicts": conflicts,
        }

    @staticmethod
    def _entities_conflict(e1: Dict[str, Any], e2: Dict[str, Any]) -> bool:
        """Check if two entities with same name have conflicting properties."""
        # Compare description and properties
        desc1 = e1.get("description", "")
        desc2 = e2.get("description", "")
        if desc1 != desc2:
            return True
        # Compare basic_properties if present
        props1 = e1.get("basic_properties", e1.get("properties", {}))
        props2 = e2.get("basic_properties", e2.get("properties", {}))
        if props1 != props2:
            return True
        return False

    @staticmethod
    def _classify_entity_category(entity_type: str) -> str:
        """Classify an entity type into an ODAP category.

        Returns one of: "object", "action", "rule", "process".
        """
        t_lower = entity_type.lower()
        if any(kw in t_lower for kw in _ACTION_ENTITY_KEYWORDS):
            return "action"
        if any(kw in t_lower for kw in _RULE_ENTITY_KEYWORDS):
            return "rule"
        if any(kw in t_lower for kw in _PROCESS_ENTITY_KEYWORDS):
            return "process"
        return "object"

    def _map_entity(self, ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """映射单个实体"""
        entity_type = ent.get("type", "")
        entity_name = ent.get("name", "")

        if not entity_type or not entity_name:
            logger.warning("实体缺少 type 或 name，跳过: %s", ent)
            return None

        if self._object_type_names and entity_type not in self._object_type_names:
            if self._strict:
                logger.warning(
                    "实体类型 '%s' 不在本体定义中，strict 模式跳过: %s",
                    entity_type,
                    entity_name,
                )
                return None
            else:
                logger.info(
                    "实体类型 '%s' 不在本体定义中，标记为 unclassified: %s",
                    entity_type,
                    entity_name,
                )
                entity_type = "unclassified"

        entity_id = self._deterministic_entity_id(entity_type, entity_name)
        raw_props = ent.get("properties", {})
        if not isinstance(raw_props, dict):
            raw_props = {}

        mapped_props = self._map_properties(raw_props)

        return {
            "entity_id": entity_id,
            "name": entity_name,
            "display_name": ent.get("display_name", entity_name),
            "type": entity_type,
            "description": ent.get("description", ""),
            **mapped_props,
        }

    def _map_relation(self, rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """映射单个关系"""
        source = rel.get("source", "")
        target = rel.get("target", "")
        relation_type = rel.get("relation_type", "")

        if not source or not target or not relation_type:
            logger.warning("关系缺少 source/target/relation_type，跳过: %s", rel)
            return None

        if self._link_type_names and relation_type not in self._link_type_names:
            if self._strict:
                logger.warning(
                    "关系类型 '%s' 不在本体定义中，strict 模式跳过: %s→%s",
                    relation_type,
                    source,
                    target,
                )
                return None
            else:
                logger.info(
                    "关系类型 '%s' 不在本体定义中，标记为 unclassified: %s→%s",
                    relation_type,
                    source,
                    target,
                )
                relation_type = "unclassified"

        raw_props = rel.get("properties", {})
        if not isinstance(raw_props, dict):
            raw_props = {}

        return {
            "source": source,
            "target": target,
            "relation_type": relation_type,
            "display_name": rel.get("display_name", relation_type),
            "properties": raw_props,
        }

    @staticmethod
    def _deterministic_entity_id(entity_type: str, entity_name: str) -> str:
        """基于 entity_type:entity_name 生成确定性 ID"""
        return hashlib.sha256(f"{entity_type}:{entity_name}".encode()).hexdigest()[:16]

    @staticmethod
    def _map_properties(raw_props: Dict[str, Any]) -> Dict[str, Any]:
        """将原始属性拆分为四层结构

        - basic_properties: 名称、描述、类型及简单字符串/数值字段
        - statistical_properties: 含 count/rate/ratio/avg/sum/total 的字段
        - capabilities: 含 can_/supports_/enabled 的字段
        - constraints: 含 max_/min_/limit/constraint 的字段
        """
        basic: Dict[str, Any] = {}
        statistical: Dict[str, Any] = {}
        capabilities: Dict[str, Any] = {}
        constraints: Dict[str, Any] = {}

        stat_keywords = ("count", "rate", "ratio", "avg", "sum", "total")
        cap_keywords = ("can_", "supports_", "enabled")
        constraint_keywords = ("max_", "min_", "limit", "constraint")

        for key, value in raw_props.items():
            key_lower = key.lower()

            if key_lower in ("name", "description", "type"):
                basic[key] = value
            elif any(kw in key_lower for kw in stat_keywords):
                statistical[key] = value
            elif any(kw in key_lower for kw in cap_keywords):
                capabilities[key] = value
            elif any(kw in key_lower for kw in constraint_keywords):
                constraints[key] = value
            else:
                basic[key] = value

        return {
            "basic_properties": basic,
            "statistical_properties": statistical,
            "capabilities": capabilities,
            "constraints": constraints,
        }
