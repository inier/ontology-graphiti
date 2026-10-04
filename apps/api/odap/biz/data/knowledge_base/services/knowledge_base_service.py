import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional

from ..storage.sqlite_kb_storage import SQLiteKnowledgeBaseStorage
from odap.infra.security.audit_helper import (
    audit as _audit_helper,
    storage_audit,
    graph_audit,
)

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    _instance = None

    @classmethod
    def get_instance(cls) -> "KnowledgeBaseService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        storage: SQLiteKnowledgeBaseStorage = None,
        candidate_storage: Any = None,
        usl_resolver: Any = None,
        usl_domain_id: str = "",
    ):
        self._storage = storage or SQLiteKnowledgeBaseStorage()
        self._graph_tasks: Dict[str, Dict[str, Any]] = {}
        # ADR-084 F1/F3：可选依赖注入（便于测试用真实 tmp_path 库装配）。
        #   candidate_storage —— open 层未治理类型实体转候选的落库（semantic_admin.candidate_store）
        #   usl_resolver      —— 写前 USL 归一器（canonical_of），None 时退化为 ASCII 启发式
        #   usl_domain_id     —— 归一所用领域；KB 车道当前无强绑定，默认空
        # 三者均为 None 时按需惰性构造（构造失败不缓存，遵 AGENTS.md 规则 14）。
        self._candidate_storage = candidate_storage
        self._usl_resolver = usl_resolver
        self._usl_domain_id = usl_domain_id

    def _create_llm_client(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None
        try:
            from odap.infra.llm.llm_service import ZhipuAIClient
            from graphiti_core.llm_client.config import LLMConfig
            api_base = os.getenv("OPENAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
            model = os.getenv("OPENAI_MODEL", "glm-4-flash")
            config = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.7)
            return ZhipuAIClient(config=config)
        except Exception as e:
            logger.warning(f"LLM client init failed: {e}")
            return None

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        llm = self._create_llm_client()
        if not llm:
            return None
        try:
            from graphiti_core.prompts.models import Message

            messages = [
                Message(role="system", content="你是一个知识图谱构建专家，擅长从文本中提取实体和关系。只返回JSON。"),
                Message(role="user", content=prompt),
            ]

            response, _, _ = await llm._generate_response(messages)
            return response
        except Exception as e:
            logger.warning(f"LLM call failed: {repr(e)}", exc_info=True)
            return None

    async def _call_he(self, text: str) -> Optional[Dict[str, Any]]:
        """调用 Hyper-Extract 进行 Schema 约束的知识提取。

        HE 使用 Pydantic AutoGraph 直接产出 {entities, relations} 结构，
        支持自动分块、并行处理、语义去重，质量远优于裸 LLM Prompt。
        """
        try:
            from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
            adapter = HEAdapter()
            if not adapter.is_available():
                logger.warning("HE adapter 不可用（hyperextract 未安装）")
                return None
            result = adapter.parse(text)
            if isinstance(result, dict) and result.get("status") == "error":
                logger.warning(f"HE 提取失败: {result.get('message')}")
                return None
            # HE adapter returns entities as dict with 'name' key,
            # and relations with 'source','target','relation_type' keys
            return result
        except ImportError:
            logger.warning("hyperextract 未安装")
            return None
        except Exception as e:
            logger.error(f"HE call failed: {e}")
            return None

    @staticmethod
    def _evaluate_quality(
        entities: List[Dict], relations: List[Dict], content_length: int
    ) -> Dict[str, Any]:
        """评估提取结果质量，返回指标报告和 0-100 分。

        指标：
          - entity_density: 每千字符实体数（5~25 为合理）
          - relation_density: 每千字符关系数
          - unique_entity_ratio: 实体去重率
          - avg_name_length: 实体名均长（>3.5 为健康）
          - relation_entity_ratio: 关系/实体比（0.2~1.0 为健康）
          - quality_score: 综合质量分 0-100
          - noise_risk: low/medium/high
        """
        chars_per_k = max(content_length / 1000.0, 1.0)
        e_count = len(entities)
        r_count = len(relations)

        # 实体密度（每千字符）
        entity_density = round(e_count / chars_per_k, 1)

        # 去重率
        unique_names = set(e.get("name", "") for e in entities if e.get("name"))
        unique_ratio = round(len(unique_names) / max(e_count, 1), 2)

        # 名均长度
        name_lengths = [len(e.get("name", "")) for e in entities if e.get("name")]
        avg_name_len = round(sum(name_lengths) / max(len(name_lengths), 1), 1) if name_lengths else 0

        # 关系密度和比率
        relation_density = round(r_count / chars_per_k, 1)
        rel_ent_ratio = round(r_count / max(e_count, 1), 2)

        # 噪声估算
        noise_score = 0
        if entity_density > 30:
            noise_score += 30
        elif entity_density > 20:
            noise_score += 15
        short_names_pct = sum(1 for l in name_lengths if l <= 2) / max(e_count, 1)
        if short_names_pct > 0.3:
            noise_score += 20
        if avg_name_len < 3:
            noise_score += 10
        if rel_ent_ratio < 0.05 and r_count == 0:
            noise_score += 25  # 完全无关系 = 高噪声

        # 综合质量分
        quality = 100
        # 密度惩罚
        if entity_density > 25:
            quality -= (entity_density - 25) * 1.2
        if entity_density < 3 and e_count > 0:
            quality -= 10  # 过于稀疏
        # 短名惩罚
        quality -= short_names_pct * 20
        # 无关系惩罚
        if r_count == 0 and e_count > 5:
            quality -= 25
        # 关系丰富度奖励
        if 0.2 <= rel_ent_ratio <= 2.0:
            quality += 5
        quality = max(0, min(100, round(quality)))

        return {
            "quality_score": quality,
            "entity_count": e_count,
            "relation_count": r_count,
            "entity_density": entity_density,
            "relation_density": relation_density,
            "unique_entity_ratio": unique_ratio,
            "avg_name_length": avg_name_len,
            "relation_entity_ratio": rel_ent_ratio,
            "noise_risk": "high" if quality < 40 else "medium" if quality < 70 else "low",
            "content_length": content_length,
        }

    def _extract_with_regex(self, content: str, entity_types: List[str] = None) -> Dict[str, Any]:
        entities = []
        relations = []

        # 通用领域实体模式（覆盖军事+电商+企业等领域）
        patterns = [
            # 军事/国防领域
            r'[\u4e00-\u9fff]{2,10}(?:编队|组织|部门|支队|分队|小组|团队)',
            r'[\u4e00-\u9fff]{2,8}(?:系统|设备|平台|载具|传感器|装置)',
            # 电商/企业领域
            r'[\u4e00-\u9fff]{2,10}(?:平台|会员|经销商|服务商|供应商|商家|用户|客户)',
            r'[\u4e00-\u9fff]{2,8}(?:订单|商品|产品|积分|权益|优惠券|发票|评价|活动|库存|结算)',
            r'[\u4e00-\u9fff]{2,8}(?:等级|账户|记录|车辆|档案|预约|营销|合同)',
            # 英文大写词
            r'\b[Bb]2[Bb]2[Cc]\b',
            r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
            # 中文关键词短语（2-6字常见实体）
            r'[\u4e00-\u9fff]{2,6}(?:管理体系|服务|系统|模型|流程|规则|策略)',
            # 数字+单位模式
            r'\d+(?:元|万元|亿元|分|次|项|级|类)',
        ]

        if entity_types:
            for etype in entity_types:
                if re.search(r'[\u4e00-\u9fff]', etype):
                    patterns.append(rf'[\u4e00-\u9fff]{{2,8}}{re.escape(etype)}')

        found = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            found.update(matches)

        # 构建 name → external_id 映射
        name_to_id = {}
        for name in found:
            entity_type = "extracted_entity"
            if any(kw in name for kw in ('会员', '用户', '客户', 'Member')):
                entity_type = "member"
            elif any(kw in name for kw in ('订单', 'Order')):
                entity_type = "order"
            elif any(kw in name for kw in ('商品', '产品', 'Product')):
                entity_type = "product"
            elif any(kw in name for kw in ('经销商', '服务商', '供应商', '商家', 'Dealer')):
                entity_type = "business_partner"
            elif any(kw in name for kw in ('积分', 'Points')):
                entity_type = "points"
            elif any(kw in name for kw in ('权益', '优惠券', 'Benefit', 'Coupon')):
                entity_type = "benefit"
            elif any(kw in name for kw in ('平台', 'Platform')):
                entity_type = "platform"
            elif any(kw in name for kw in ('车辆', 'Vehicle')):
                entity_type = "vehicle"
            entities.append({"name": name, "type": entity_type, "properties": {}})
            name_to_id[name] = name

        # 关系提取：基于中文关系模式（放宽字符范围 2-20 以匹配更长的实体名）
        RELATION_PATTERNS = [
            # 从属/属性
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})的([\u4e00-\u9fffA-Za-z0-9]{2,20})', "HAS_ATTRIBUTE"),
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})(?:属于|归属|隶属)([\u4e00-\u9fffA-Za-z0-9]{2,20})', "BELONGS_TO"),
            # 管理/运营
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})(?:管理|负责|运营|维护)([\u4e00-\u9fffA-Za-z0-9]{2,20})', "MANAGES"),
            # 提供/服务
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})(?:提供|供应|服务|支持)([\u4e00-\u9fffA-Za-z0-9]{2,20})', "PROVIDES"),
            # 包含/组成
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})(?:包含|包括|涵盖|含有)([\u4e00-\u9fffA-Za-z0-9]{2,20})', "CONTAINS"),
            # 使用/依赖
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})(?:使用|采用|利用|调用)([\u4e00-\u9fffA-Za-z0-9]{2,20})', "USES"),
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})(?:依赖|基于|依托)([\u4e00-\u9fffA-Za-z0-9]{2,20})', "DEPENDS_ON"),
            # 产生/生成
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})(?:产生|生成|创建|构建)([\u4e00-\u9fffA-Za-z0-9]{2,20})', "PRODUCES"),
            # 存储/记录
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})(?:存储|保存|记录|写入)([\u4e00-\u9fffA-Za-z0-9]{2,20})', "STORES"),
            # 通用关联（任意两实体相邻出现）
            (r'([\u4e00-\u9fffA-Za-z0-9]{2,20})[、和与及]([\u4e00-\u9fffA-Za-z0-9]{2,20})', "RELATED_TO"),
        ]

        rel_seen = set()
        for sentence in re.split(r'[。，；\n,;]', content):
            sentence = sentence.strip()
            if len(sentence) < 4:
                continue
            for pattern, rel_type in RELATION_PATTERNS:
                for match in re.finditer(pattern, sentence):
                    source, target = match.group(1), match.group(2)
                    rel_key = (source, target, rel_type)
                    if rel_key not in rel_seen:
                        rel_seen.add(rel_key)
                        relations.append({
                            "source": source,
                            "target": target,
                            "type": rel_type,
                        })

        # 实体名清理：去除噪声片段，提升与已有实体的匹配率
        _NOISE_PREFIX = re.compile(r'^[与和在为从下是](?=[\u4e00-\u9fff]{2})')
        _NOISE_SUFFIX = re.compile(r'(?<=[\u4e00-\u9fff]{2})[的之中]$')
        cleaned_entities = []
        for e in entities:
            name = e["name"].strip()
            # 跳过明显是噪声的实体
            if len(name) < 2:
                continue
            if re.match(r'^\d+[元万元亿分次项级类]', name) and len(name) <= 6:
                continue  # 纯数值单位，无语义
            # 去前后缀
            name = _NOISE_PREFIX.sub('', name)
            name = _NOISE_SUFFIX.sub('', name)
            name = name.strip()
            if len(name) < 2:
                continue
            e["name"] = name
            cleaned_entities.append(e)
        entities = cleaned_entities

        # 同步清理关系中的 source/target 名称
        for r in relations:
            r["source"] = _NOISE_PREFIX.sub('', r["source"].strip())
            r["source"] = _NOISE_SUFFIX.sub('', r["source"]).strip()
            r["target"] = _NOISE_PREFIX.sub('', r["target"].strip())
            r["target"] = _NOISE_SUFFIX.sub('', r["target"]).strip()

        return {"entities": entities, "relations": relations}

    # ==================================================================
    # ADR-084 F1/F3：open/typed 双层 + 写前 USL 归一
    # ==================================================================
    def _get_candidate_storage(self) -> Optional[Any]:
        """惰性获取 candidate_store 存储（open 层实体转候选的落库）。

        构造失败不缓存（AGENTS.md 规则 14：降级实例禁入长生命周期缓存），
        返回 None 由调用方显式处理，不静默吞。
        """
        if self._candidate_storage is not None:
            return self._candidate_storage
        try:
            from odap.biz.semantic_admin.candidate_store.storage import (
                SQLiteCandidateStorage,
            )
            self._candidate_storage = SQLiteCandidateStorage()
            return self._candidate_storage
        except Exception as e:
            logger.warning("candidate_store 初始化失败，open 层实体无法转候选: %r", e)
            return None

    def _get_usl_resolver(self):
        """返回 (resolver, domain_id)。resolver 可能为 None（无 USL 上下文）。

        惰性从 SQLite USL 存储构造（可脱离 Neo4j）。构造失败不缓存、返回 None，
        由 _partition_entities_by_type 退化为 ASCII 启发式（不静默假装归一成功）。
        """
        if self._usl_resolver is not None:
            return self._usl_resolver, self._usl_domain_id
        try:
            from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
                load_resolver_from_storage,
            )
            resolver = load_resolver_from_storage(self._usl_domain_id or "")
            self._usl_resolver = resolver
            return resolver, self._usl_domain_id
        except Exception as e:
            logger.warning(
                "UslTermResolver 构造失败，写前归一退化为 ASCII 启发式（不静默降级为已归一）: %r",
                e,
            )
            return None, self._usl_domain_id

    def _partition_entities_by_type(
        self,
        entities: List[Dict],
        resolver: Any = None,
        domain_id: str = "",
    ):
        """按类型治理状态二分实体（ADR-084 F1，纯逻辑，无副作用，不产生 zh_type）。

        typed 层：类型标识为非空 ASCII 安全串（可作图谱类型/受控标识符）。
        open 层：类型含中文、为空，或经 USL 归一明确未命中——不自由落 typed 图，
                 改由 _stage_open_layer_entities 转候选队列走治理车道。

        resolver 命中时用 canonical 作为类型基准；未命中（canonical_of 返回 None）
        打 unresolved_term=True。resolver 为 None 时退化为「ASCII=typed / CJK=open」。

        返回：(typed, open_layer)
          typed:      List[(entity, type_id)]
          open_layer: List[{"entity", "raw_type", "canonical", "unresolved_term"}]
        """
        typed: List[Any] = []
        open_layer: List[Dict[str, Any]] = []
        for entity in entities:
            raw_type = str(entity.get("type") or "").strip()
            canonical: Optional[str] = None
            if resolver is not None and raw_type:
                try:
                    canonical = resolver.canonical_of(raw_type, domain_id)
                except Exception as e:
                    # 归一器异常按「未归一」处理并显式告警，不静默当作命中（规则 14）
                    logger.warning("USL canonical_of 异常，按未归一处理: %r", e)
                    canonical = None
            unresolved_term = bool(resolver is not None and canonical is None)
            basis = canonical or raw_type
            type_id = basis.lower().replace(' ', '_')
            ascii_safe = bool(type_id) and not re.search(r'[\u4e00-\u9fff]', type_id)
            if ascii_safe:
                typed.append((entity, type_id))
            else:
                # open 层归置原因与「USL 是否识别」是两个正交维度：
                #   unresolved_term —— resolver 明确未命中（USL 不认识该类型）
                #   open_reason     —— 为何进 open 层（non_ascii_type / empty_type）
                open_layer.append({
                    "entity": entity,
                    "raw_type": raw_type,
                    "canonical": canonical,
                    "unresolved_term": unresolved_term,
                    "open_reason": "empty_type" if not raw_type else "non_ascii_type",
                })
        return typed, open_layer

    def _stage_open_layer_entities(
        self,
        open_items: List[Dict[str, Any]],
        kb_id: str,
        doc_id: str,
        workspace_id: str = "default",
    ) -> List[str]:
        """把 open 层（未治理类型）实体转 candidate_store 候选（ADR-084 F1）。

        不写 typed 图；建一条 source_type="ingest" 的 pipeline run 承载候选。
        返回新建候选 id 列表。任何失败均显式 warning 并返回已落库部分（不静默）。
        """
        if not open_items:
            return []
        storage = self._get_candidate_storage()
        if storage is None:
            logger.warning(
                "candidate_store 不可用，%d 个 open 层实体未转候选（kb=%s doc=%s）——"
                "typed 图不受影响，但这些未治理类型暂无法进入治理车道",
                len(open_items), kb_id, doc_id,
            )
            return []
        try:
            run = storage.create_pipeline_run(
                workspace_id=workspace_id,
                source_type="ingest",
                source_ref=f"kb:{kb_id}/doc:{doc_id}",
                triggered_by="kb_open_layer_stage",
            )
            run_id = run.get("id")
        except Exception as e:
            logger.warning("创建 ingest pipeline run 失败，open 层实体未落候选: %r", e)
            return []

        cands: List[Dict[str, Any]] = []
        for item in open_items:
            ent = item.get("entity") or {}
            name = str(ent.get("name") or "").strip()
            if not name:
                continue
            cands.append({
                "run_id": run_id,
                "canonical": name,
                "semantic_type": "对象类型",
                "origin": "llm",
                "domain_id": self._usl_domain_id or None,
                "source_text": name,
                "provenance": {
                    "source": "kb_ingest_open_layer",
                    "kb_id": kb_id,
                    "doc_id": doc_id,
                    "raw_type": item.get("raw_type"),
                    "usl_canonical": item.get("canonical"),
                    "unresolved_term": bool(item.get("unresolved_term")),
                    "open_reason": item.get("open_reason"),
                    "open_layer": True,
                },
            })
        if not cands:
            return []
        try:
            saved = storage.bulk_insert_candidates(cands)
        except Exception as e:
            logger.warning("open 层实体写候选失败: %r", e)
            return []
        logger.warning(
            "摄入车道 open 层：%d 个未治理类型实体已转候选（未落 typed 图），"
            "kb=%s doc=%s run=%s", len(saved), kb_id, doc_id, run_id,
        )
        return [c.get("id") for c in saved if isinstance(c, dict)]

    def _write_to_graph(
        self, kb_id: str, doc_id: str, entities: List[Dict], relations: List[Dict],
        workspace_id: str = "default",
    ) -> bool:
        """将抽取的实体和关系写入 Neo4j 图谱（ADR-084：open/typed 双层）。

        使用 GraphWriteProxy（架构规则：业务模块禁止直接使用 GraphManager 写操作）。
        实体 ID 格式: kb_{kb_id}_{entity_name}，确保跨文档去重。

        ADR-084 F1：类型含中文/未治理的实体不再塌缩成 zh_type 桶直写图谱，而是
        经 open 层转 candidate_store 候选，走治理车道；typed 图只含受治理事实。
        ADR-084 F3：写前经 UslTermResolver 归一类型，未命中打 unresolved_term。
        """
        try:
            from odap.infra.query.graph_write_proxy import get_graph_write_proxy
            write_proxy = get_graph_write_proxy()

            # 检查 GraphManager 是否可用
            gm = write_proxy._get_graph_manager()
            if gm is None or gm.mode == "unavailable":
                logger.warning("GraphManager 处于 unavailable 模式，无法写入图谱数据")
                return False

            # ADR-084 F1/F3：先按类型治理状态二分，open 层转候选（不落 typed 图）
            resolver, domain_id = self._get_usl_resolver()
            typed, open_layer = self._partition_entities_by_type(
                entities, resolver, domain_id,
            )
            staged_ids = self._stage_open_layer_entities(
                open_layer, kb_id, doc_id, workspace_id,
            )

            # 写入 typed 实体，建立 name→entity_id 映射供关系引用
            name_to_id: Dict[str, str] = {}
            success_count = 0

            # 先从 Neo4j 查询该 KB 已有实体名，提升正则/LLM 实体名匹配率
            try:
                if gm.neo4j_driver:
                    with gm.neo4j_driver.session() as session:
                        existing = session.run(
                            "MATCH (n:Entity) WHERE n.kb_id = $kb_id RETURN n.name AS name, n.id AS id",
                            kb_id=kb_id,
                        )
                        for rec in existing:
                            ename = rec["name"]
                            eid = rec["id"]
                            if ename and eid:
                                name_to_id[ename] = eid
                    logger.info(f"从 Neo4j 加载 KB {kb_id} 已有 {len(name_to_id)} 个实体名")
            except Exception as e:
                logger.debug(f"加载已有实体名失败（将仅使用本次抽取的名称）: {e}")

            for entity, entity_type_id in typed:
                name = entity.get("name", "")
                entity_id = f"kb_{kb_id}_{name}"
                if name not in name_to_id:
                    name_to_id[name] = entity_id

                props = {
                    **entity.get("properties", {}),
                    "source_doc": doc_id,
                    "kb_id": kb_id,
                    "name": name,
                    "entity_type_id": entity_type_id,
                }
                result = write_proxy.add_entity(entity_id, entity_type_id, props)
                if result.get("status") == "success":
                    success_count += 1

            # 写入关系：仅当 source/target 都能解析到 typed/已有实体时才写，
            # 触达 open 层（未治理）实体的关系被推迟（不合成幻影端点，规则 14）。
            relation_count = 0
            deferred_relations = 0

            def _resolve_entity_id(name: str) -> Optional[str]:
                if name in name_to_id:
                    return name_to_id[name]
                # 模糊匹配：关系中的名称可能是实体的子串或近似表达
                for entity_name, eid in name_to_id.items():
                    if name in entity_name or entity_name in name:
                        return eid
                return None

            for rel in relations:
                source_name = rel.get("source", "").strip()
                target_name = rel.get("target", "").strip()
                if not source_name or not target_name:
                    continue
                source_id = _resolve_entity_id(source_name)
                target_id = _resolve_entity_id(target_name)
                if source_id is None or target_id is None:
                    deferred_relations += 1
                    continue
                rel_type = rel.get("type", "related_to")
                props = {k: v for k, v in rel.items() if k not in ("source", "target", "type")}
                result = write_proxy.add_relationship(source_id, target_id, rel_type, props)
                if result.get("status") == "success":
                    relation_count += 1

            if open_layer:
                logger.warning(
                    "doc=%s: %d 个实体类型未治理→open 层转候选 %d 条；推迟关系 %d 条（触达 open 层端点）",
                    doc_id, len(open_layer), len(staged_ids), deferred_relations,
                )

            if not entities and not relations:
                logger.warning(f"No entities or relations to write for doc {doc_id}")
                return False
            return success_count > 0 or relation_count > 0 or bool(staged_ids)
        except Exception as e:
            logger.warning(f"GraphWriteProxy write failed: {repr(e)}", exc_info=True)
            return False

    def list_knowledge_bases(self) -> List[Dict[str, Any]]:
        return self._storage.list_knowledge_bases()

    def get_knowledge_base(self, kb_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_knowledge_base(kb_id)
        if not result:
            return {"status": "error", "message": "知识库不存在"}
        return result

    def create_knowledge_base(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_knowledge_base(data)

    def update_knowledge_base(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        result = self._storage.update_knowledge_base(kb_id, data)
        if not result:
            return {"status": "error", "message": "知识库不存在"}
        return result

    def delete_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        success = self._storage.delete_knowledge_base(kb_id)
        if not success:
            return {"status": "error", "message": "知识库不存在"}
        return {"status": "success", "message": "知识库删除成功"}

    def list_categories(self, kb_id: str) -> List[Dict[str, Any]]:
        return self._storage.list_categories(kb_id)

    def create_category(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_category(kb_id, data)

    def delete_category(self, kb_id: str, category_id: str) -> Dict[str, Any]:
        success = self._storage.delete_category(kb_id, category_id)
        if not success:
            return {"status": "error", "message": "分类不存在"}
        return {"status": "success", "message": "分类删除成功"}

    def list_documents(self, kb_id: str, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._storage.list_documents(kb_id, category_id)

    def create_document(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_document(kb_id, data)

    def get_document(self, kb_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_document(kb_id, doc_id)
        if not result:
            return {"status": "error", "message": "文档不存在"}
        return result

    def delete_document(self, kb_id: str, doc_id: str) -> Dict[str, Any]:
        success = self._storage.delete_document(kb_id, doc_id)
        if not success:
            return {"status": "error", "message": "文档不存在"}
        return {"status": "success", "message": "文档删除成功"}

    async def build_graph(
        self, doc_id: str, extraction_method: str = "auto", entity_types: List[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        doc = self._storage.find_document_by_id(doc_id)
        if not doc:
            return {"status": "error", "message": "文档不存在"}

        content = (doc.get("cleaned_content") or doc.get("content", "")) or ""
        if not content.strip():
            return {"status": "error", "message": "文档内容为空，无法构建图谱"}

        task_id = f"task_{doc_id}"
        kb_id_from_doc = doc.get("kb_id", "")
        # 任务开始审计
        _audit_helper(
            "kb_graph_build_start",
            user="system",
            result_status="success",
            service="kb_service",
            resource=doc_id,
            details={"kb_id": kb_id_from_doc, "method": extraction_method, "task_id": task_id},
        )
        self._graph_tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "method": extraction_method,
        }

        entities = []
        relations = []
        used_method = extraction_method
        quality = {}

        # ── HE (Hyper-Extract) 分支：LLM + Pydantic Schema 约束 ──
        if extraction_method in ("he", "auto"):
            he_result = await self._call_he(content)
            if he_result and isinstance(he_result, dict) and he_result.get("entities"):
                entities = he_result.get("entities", [])
                relations = he_result.get("relations", [])
                quality = self._evaluate_quality(entities, relations, len(content))
                used_method = "he"
                logger.info(
                    f"HE extraction: {len(entities)} entities, {len(relations)} relations, "
                    f"quality={quality.get('quality_score', '?')}"
                )
                # 保存中间结果到 DB，供后续审查编辑
                self._storage.save_extraction_result(
                    doc_id=doc_id,
                    entities=entities,
                    relations=relations,
                    quality=quality,
                    method="he",
                )
            elif extraction_method == "he":
                # HE 不可用而用户明确指定 → 报错
                duration_ms = int((time.time() - start_time) * 1000)
                self._graph_tasks[task_id] = {
                    "status": "failed", "progress": 0, "method": "he",
                    "error": "HE 提取不可用",
                }
                return {
                    "task_id": task_id, "status": "failed", "method": "he",
                    "entities_extracted": 0, "relations_extracted": 0,
                    "error": "Hyper-Extract 未安装或不可用，请先 pip install -e ./hyper-extract",
                }

        # ── LLM Prompt 分支（auto 模式下 HE 优先，失败才走这里） ──
        if (not entities and not relations) and extraction_method in ("llm", "auto"):
            prompt = f"""从以下文本中提取实体和关系。

实体：识别文中具体的人、组织、系统、产品、平台、概念等专有名词作为节点。
关系：识别实体之间明确的语义关联，包括但不限于：属于、包含、管理、提供、服务、依赖、调用、关联、产生、转换、存储等。

以JSON格式返回，确保每个关系中的 source 和 target 与实际提取到的实体 name 完全一致：
{{
  "entities": [{{"name": "实体名", "type": "类型", "properties": {{}}}}],
  "relations": [{{"source": "实体1", "target": "实体2", "type": "关系类型"}}]
}}

文本内容：
{content[:8000]}"""
            llm_result = await self._call_llm(prompt)
            if llm_result and isinstance(llm_result, dict):
                # 兼容多种 LLM 返回的键名变体
                entities = (
                    llm_result.get("entities")
                    or llm_result.get("实体")
                    or llm_result.get("entity")
                    or []
                )
                relations = (
                    llm_result.get("relations")
                    or llm_result.get("relationships")
                    or llm_result.get("关系")
                    or llm_result.get("relation")
                    or []
                )
                # 如果是列表但内层含不同键名，再尝试正规化
                if not relations and isinstance(llm_result.get("result"), dict):
                    sub = llm_result["result"]
                    relations = sub.get("relations") or sub.get("relationships") or sub.get("关系") or []
                    entities = entities or sub.get("entities") or sub.get("实体") or []
                used_method = "llm"
                logger.info(f"LLM extraction: {len(entities)} entities, {len(relations)} relations")
            elif extraction_method == "llm":
                duration_ms = int((time.time() - start_time) * 1000)
                _audit_helper(
                    "kb_graph_build_failed",
                    user="system",
                    result_status="failure",
                    result_message="LLM提取失败",
                    service="kb_service",
                    resource=doc_id,
                    details={"kb_id": kb_id_from_doc, "task_id": task_id, "method": "llm"},
                    duration_ms=duration_ms,
                )
                self._graph_tasks[task_id] = {
                    "status": "failed",
                    "progress": 0,
                    "method": "llm",
                    "error": "LLM提取失败",
                    "entities_extracted": 0,
                    "relations_extracted": 0,
                }
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "method": "llm",
                    "entities_extracted": 0,
                    "relations_extracted": 0,
                }

        # 核心修复：当LLM实体返回但关系为空时，仍尝试regex补充关系
        # 当LLM完全失败时，用regex做全量提取
        if (not entities or not relations) and extraction_method in ("regex", "auto"):
            regex_result = self._extract_with_regex(content, entity_types)
            regex_entities = regex_result.get("entities", [])
            regex_relations = regex_result.get("relations", [])
            if not entities:
                entities = regex_entities
                relations = regex_relations  # fix: 纯 regex 模式也需要补充关系
                used_method = "regex"
            else:
                # LLM已有实体但缺关系：只用regex的关系，实体名模糊匹配
                relations.extend(regex_relations)
                used_method = "llm+regex"
            logger.info(f"Regex supplement: {len(regex_entities)} entities, {len(regex_relations)} relations → method={used_method}")

        # LLM/Regex 抽取结束审计（无论哪个分支结束都记一次）
        _audit_helper(
            "kb_graph_extraction_done",
            user="system",
            result_status="success",
            service="kb_service",
            resource=doc_id,
            details={
                "doc_id": doc_id,
                "kb_id": kb_id_from_doc,
                "method": used_method,
                "entities_extracted": len(entities),
                "relations_extracted": len(relations),
            },
        )

        # 保存非 HE 方法的中间结果，供后续审查编辑
        if used_method != "he" and (entities or relations):
            quality = self._evaluate_quality(entities, relations, len(content))
            self._storage.save_extraction_result(
                doc_id=doc_id,
                entities=entities,
                relations=relations,
                quality=quality,
                method=used_method,
            )

        graph_ok = self._write_to_graph(kb_id_from_doc, doc_id, entities, relations)

        # GraphWriteProxy 写入结束审计
        graph_audit(
            "graph_write_proxy_write",
            result_status="success" if graph_ok else "failure",
            resource=doc_id,
            details={
                "kb_id": kb_id_from_doc,
                "entity_count": len(entities),
                "relation_count": len(relations),
            },
        )

        # 索引文档内容到 Graphiti（支持向量语义检索）
        try:
            from odap.infra.graph.graph_service import GraphManager
            from datetime import datetime, timezone
            graph_manager = GraphManager()
            if graph_manager.mode in ("graphiti", "neo4j_driver") and not graph_manager._use_fallback:
                cleaned_content = doc.get("cleaned_content") or content
                if cleaned_content and cleaned_content.strip():
                    episode_name = f"kb_doc_{doc_id}"
                    content_len = len(cleaned_content)
                    try:
                        ep_success = await graph_manager.add_episode(
                            name=episode_name,
                            content=cleaned_content[:50000],
                            source_description=f"KB:{kb_id_from_doc}",
                            reference_time=datetime.now(timezone.utc),
                        )
                        if ep_success:
                            logger.info(f"Document {doc_id} indexed to Graphiti as Episode {episode_name}")
                            graph_audit(
                                "graphiti_add_episode_success",
                                resource=episode_name,
                                details={
                                    "kb_id": kb_id_from_doc,
                                    "doc_id": doc_id,
                                    "content_length": content_len,
                                },
                            )
                        else:
                            graph_audit(
                                "graphiti_add_episode_failed",
                                result_status="failure",
                                result_message="add_episode returned False",
                                resource=episode_name,
                                details={"kb_id": kb_id_from_doc, "doc_id": doc_id},
                            )
                    except Exception as e:
                        graph_audit(
                            "graphiti_add_episode_failed",
                            result_status="failure",
                            result_message=str(e),
                            resource=episode_name,
                            details={"kb_id": kb_id_from_doc, "doc_id": doc_id},
                        )
                        raise
        except Exception as e:
            logger.warning(f"Graphiti Episode indexing skipped for doc {doc_id}: {e}")

        if not graph_ok or (not entities and not relations):
            fail_reason = "图数据库写入失败，请检查 Neo4j 连接" if not graph_ok else "未提取到任何实体或关系"
            duration_ms = int((time.time() - start_time) * 1000)
            _audit_helper(
                "kb_graph_build_failed",
                user="system",
                result_status="failure",
                result_message=fail_reason,
                service="kb_service",
                resource=doc_id,
                details={
                    "kb_id": kb_id_from_doc,
                    "task_id": task_id,
                    "method": used_method,
                },
                duration_ms=duration_ms,
            )
            self._graph_tasks[task_id] = {
                "status": "failed",
                "progress": 0,
                "method": used_method,
                "error": fail_reason,
                "entities_extracted": len(entities),
                "relations_extracted": len(relations),
            }
            return {
                "task_id": task_id,
                "status": "failed",
                "method": used_method,
                "entities_extracted": len(entities),
                "relations_extracted": len(relations),
                "error": fail_reason,
            }

        entities_extracted = len(entities)
        relations_extracted = len(relations)
        self._storage.update_document_graph_status(doc_id, True, entities_extracted)

        duration_ms = int((time.time() - start_time) * 1000)
        self._graph_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "method": used_method,
            "entities_extracted": entities_extracted,
            "relations_extracted": relations_extracted,
            "duration_ms": duration_ms,
        }

        # 整体任务结束审计
        _audit_helper(
            "kb_graph_build_completed",
            user="system",
            result_status="success",
            service="kb_service",
            resource=doc_id,
            details={
                "task_id": task_id,
                "kb_id": kb_id_from_doc,
                "method": used_method,
                "entities_extracted": entities_extracted,
                "relations_extracted": relations_extracted,
                "duration_ms": duration_ms,
            },
            duration_ms=duration_ms,
        )

        return {
            "task_id": task_id,
            "status": "completed",
            "entities_extracted": entities_extracted,
            "relations_extracted": relations_extracted,
            "method": used_method,
        }

    def get_graph_build_status(self, task_id: str) -> Dict[str, Any]:
        task = self._graph_tasks.get(task_id)
        if not task:
            return {"status": "error", "message": "任务不存在"}
        return task

    def get_kb_graph(self, kb_id: str) -> Dict[str, Any]:
        """查询指定知识库的图谱数据，返回 nodes + edges 供前端可视化。

        Neo4j 优先；Neo4j 不可用时降级为 SQLite entities_json 数据。
        """
        try:
            from odap.infra.graph.graph_service import GraphManager
            gm = GraphManager()
            if gm.mode != "unavailable" and gm.neo4j_driver:
                # 从 SQLite 收集该知识库的所有 doc_id，用于兼容旧数据（无 kb_id 属性）
                docs = self._storage.list_documents(kb_id)
                doc_ids = [d.get("doc_id", "") for d in docs if d.get("doc_id")]

                with gm.neo4j_driver.session() as session:
                    # 查询该知识库的所有实体节点（兼容新旧数据：kb_id 或 source_doc 匹配）
                    entity_result = session.run(
                        "MATCH (n) "
                        "WHERE n.kb_id = $kb_id OR n.source_doc IN $doc_ids "
                        "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props",
                        kb_id=kb_id, doc_ids=doc_ids
                    )
                    nodes = []
                    node_ids = set()
                    for record in entity_result:
                        node_id = record["id"]
                        labels = [lb for lb in (record["labels"] or []) if lb != "Entity"]
                        node_type = labels[0] if labels else "unknown"
                        props = record["props"] or {}
                        nodes.append({
                            "id": node_id,
                            "name": props.get("name", node_id),
                            "type": node_type,
                            "source_doc": props.get("source_doc", ""),
                            "properties": {k: v for k, v in props.items()
                                           if k not in ("id", "name", "source_doc", "kb_id")},
                        })
                        node_ids.add(node_id)

                    # 查询这些实体之间的关系
                    rel_result = session.run(
                        "MATCH (a)-[r]->(b) "
                        "WHERE (a.kb_id = $kb_id OR a.source_doc IN $doc_ids) "
                        "  AND (b.kb_id = $kb_id OR b.source_doc IN $doc_ids) "
                        "RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props",
                        kb_id=kb_id, doc_ids=doc_ids
                    )
                    edges = []
                    edge_idx = 0
                    for record in rel_result:
                        source = record["source"]
                        target = record["target"]
                        if source in node_ids and target in node_ids:
                            edges.append({
                                "id": f"e_{edge_idx}",
                                "source": source,
                                "target": target,
                                "type": record["type"] or "related_to",
                                "properties": record["props"] or {},
                            })
                            edge_idx += 1

                return {
                    "nodes": nodes,
                    "edges": edges,
                    "statistics": {
                        "total_entities": len(nodes),
                        "total_relationships": len(edges),
                    },
                }

            # Neo4j 不可用，降级为 SQLite entities_json 数据
            return self._get_kb_graph_from_sqlite(kb_id)

        except Exception as e:
            logger.warning(f"Failed to get KB graph from Neo4j, falling back to SQLite: {e}")
            return self._get_kb_graph_from_sqlite(kb_id)

    def _get_kb_graph_from_sqlite(self, kb_id: str) -> Dict[str, Any]:
        """从 SQLite 的 entities_json 字段构建图谱数据（Neo4j 不可用时的降级方案）。"""
        try:
            docs = self._storage.list_documents(kb_id)
            nodes = []
            node_ids = set()
            node_name_to_id = {}
            edges = []
            edge_idx = 0

            for doc in docs:
                doc_id = doc.get("doc_id", "")
                entities_data = doc.get("entities_json")
                if not entities_data:
                    continue
                if isinstance(entities_data, str):
                    try:
                        entities_data = json.loads(entities_data)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if not isinstance(entities_data, list):
                    continue

                for entity in entities_data:
                    if not isinstance(entity, dict):
                        continue
                    name = entity.get("name", "unknown")
                    entity_id = f"sqlite_{kb_id}_{name}"
                    if entity_id in node_ids:
                        continue
                    entity_type = entity.get("type", "extracted_entity")
                    node_ids.add(entity_id)
                    node_name_to_id[name] = entity_id
                    nodes.append({
                        "id": entity_id,
                        "name": name,
                        "type": entity_type,
                        "source_doc": doc_id,
                        "properties": entity.get("properties", {}),
                    })

                # 从文档的关系数据中提取 edges
                # entities_json 中的每个 entity 的 relations 字段
                for entity in entities_data:
                    if not isinstance(entity, dict):
                        continue
                    rels = entity.get("relations", [])
                    if not isinstance(rels, list):
                        continue
                    for rel in rels:
                        if not isinstance(rel, dict):
                            continue
                        source_name = rel.get("source", "")
                        target_name = rel.get("target", "")
                        if source_name in node_name_to_id and target_name in node_name_to_id:
                            edges.append({
                                "id": f"e_{edge_idx}",
                                "source": node_name_to_id[source_name],
                                "target": node_name_to_id[target_name],
                                "type": rel.get("type", "RELATED_TO"),
                                "properties": {},
                            })
                            edge_idx += 1

            return {
                "nodes": nodes,
                "edges": edges,
                "statistics": {
                    "total_entities": len(nodes),
                    "total_relationships": len(edges),
                },
            }
        except Exception as e:
            logger.warning(f"SQLite fallback graph failed: {e}")
            return {"nodes": [], "edges": [], "statistics": {"total_entities": 0, "total_relationships": 0}, "error": str(e)}

    async def rag_query(
        self, kb_id: str, query: str, top_k: int = 5, threshold: float = 0.1
    ) -> Dict[str, Any]:
        """RAG 语义检索：SQLite 关键词匹配 + Graphiti 向量检索 + LLM 回答。

        查询流程：
        1. SQLite 关键词匹配：直接从 SQLite 读取文档，用 re.search
           匹配中文关键词（含2-gram分词，避免跨平台编码问题）
        2. Graphiti 向量检索：如果 Graphiti 可用，补充语义检索结果
        3. 合并结果，调用 LLM 生成回答
        """
        kb = self._storage.get_knowledge_base(kb_id)
        if not kb:
            return {"status": "error", "message": "知识库不存在"}

        context_parts = []
        sources = []
        related_entities = []
        use_vector = False

        # ================================================================
        # Step 1: SQLite 关键词匹配（re.search + 2-gram中文分词）
        # ================================================================
        docs = self._storage.list_documents(kb_id)

        # 中文关键词匹配：优化分词策略
        #   1) 保留原始查询词（完整匹配）
        #   2) 按常用分隔符拆词
        #   3) 对中文查询做2-gram分词（增强短词召回）
        #   4) 剔除 ≤1 字符的短词
        #   5) 使用 re.search 替代 in 操作符（跨平台编码兼容）
        query_terms = set()
        query_clean = query.strip().lower()
        query_terms.add(query_clean)

        # 按中文标点和空格拆分短词
        for sep in ('的', '和', '与', '或', '，', '、', ' ', ',', ';', '；'):
            for part in query.split(sep):
                part = part.strip().lower()
                if len(part) >= 2:
                    query_terms.add(part)

        # 2-gram 中文分词（如"会员等级"→"会员","员等","等级"）
        query_no_punc = re.sub(r'[\s，,、。；;]', '', query.strip())
        for i in range(len(query_no_punc) - 1):
            bigram = query_no_punc[i:i+2]
            query_terms.add(bigram.lower())

        # 剔除太短的词（≤1字符），但保留原始查询
        query_terms = {t for t in query_terms if len(t) >= 2 or t == query_clean}

        logger.info(
            f"RAG query terms for '{query[:50]}': {len(query_terms)} terms → "
            f"{sorted(query_terms, key=len, reverse=True)[:10]}"
        )

        scored = []
        for doc in docs:
            # 优先使用清洗后的内容，做 UTF-8 安全编解码
            raw_content = doc.get("cleaned_content") or doc.get("content", "") or ""
            try:
                doc_content = raw_content.encode('utf-8').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                doc_content = raw_content
            if not doc_content.strip():
                continue
            content_lower = doc_content.lower()

            # 评分：使用 re.search 替代 in 操作符（更好的中文编码兼容性）
            match_count = 0
            total_term_score = 0
            for term in query_terms:
                if len(term) >= 2 and re.search(re.escape(term), content_lower, re.IGNORECASE):
                    occurrences = len(re.findall(re.escape(term), content_lower, re.IGNORECASE))
                    match_count += 1
                    total_term_score += min(occurrences, 10)  # 最多计数10次

            if match_count == 0:
                continue

            # 综合评分 = 匹配词比例 * 0.5 + 词频归一化 * 0.3 + 长度惩罚 * 0.2
            term_ratio = match_count / max(len(query_terms), 1)
            freq_score = min(total_term_score / 20.0, 1.0)  # 归一化
            # 长度惩罚：短文档优先（但不要太短）
            doc_len = max(len(doc_content), 1)
            length_score = min(10000.0 / max(doc_len, 100), 1.0)
            score = term_ratio * 0.5 + freq_score * 0.3 + length_score * 0.2

            if score >= threshold:
                scored.append((doc, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_docs = scored[:top_k]

        logger.info(
            f"RAG keyword match: {len(scored)} docs matched from {len(docs)} total docs, "
            f"returning top {len(top_docs)}"
        )

        for doc, score in top_docs:
            raw_content = doc.get("cleaned_content") or doc.get("content", "") or ""
            try:
                doc_content = raw_content.encode('utf-8').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                doc_content = raw_content
            context_parts.append(doc_content[:2000])
            sources.append({
                "doc_id": doc.get("doc_id"),
                "title": doc.get("title", ""),
                "score": round(score, 3),
                "source": "keyword",
            })

        # ================================================================
        # Step 2: Graphiti 向量语义检索（补充结果）
        # ================================================================
        try:
            from odap.infra.graph.graph_service import GraphManager
            graph_manager = GraphManager()

            if graph_manager.mode == "graphiti" and graph_manager.graph:
                try:
                    edges = await graph_manager.graph.search(
                        query=query, num_results=top_k * 2
                    )
                except Exception as ge:
                    logger.warning(f"Graphiti direct search failed: {ge}")
                    edges = []

                if edges:
                    use_vector = True
                    for edge in edges:
                        fact = getattr(edge, "fact", None)
                        if fact and fact.strip():
                            # 去重：避免和关键词结果重复
                            is_dup = False
                            for ex in context_parts:
                                if fact[:100] in ex or ex[:100] in fact:
                                    is_dup = True
                                    break
                            if not is_dup:
                                context_parts.append(fact)
                                edge_name = getattr(edge, "name", "") or ""
                                sources.append({
                                    "edge_id": str(getattr(edge, "uuid", edge_name)),
                                    "name": edge_name,
                                    "score": round(getattr(edge, "score", 0.7), 3),
                                    "source": "vector",
                                })
            elif graph_manager.mode in ("graphiti", "neo4j_driver"):
                try:
                    hybrid_results = graph_manager.search_hybrid(
                        query_text=query, top_k=top_k
                    )
                    if hybrid_results and isinstance(hybrid_results, list):
                        use_vector = True
                        for hr in hybrid_results:
                            if isinstance(hr, dict):
                                props = hr.get("properties", {})
                                fact = props.get("fact", "")
                                if fact:
                                    is_dup = False
                                    for ex in context_parts:
                                        if fact[:100] in ex or ex[:100] in fact:
                                            is_dup = True
                                            break
                                    if not is_dup:
                                        context_parts.append(fact)
                                        sources.append({
                                            "id": hr.get("id", ""),
                                            "type": hr.get("type", ""),
                                            "score": round(hr.get("score", 0.5), 3),
                                            "source": "hybrid",
                                        })
                except Exception as he:
                    logger.warning(f"Hybrid search failed: {he}")
        except Exception as e:
            logger.warning(f"Vector search unavailable, using keyword only: {e}")

        # ================================================================
        # Step 3: LLM 生成答案
        # ================================================================
        answer = ""
        if context_parts:
            context = "\n".join(context_parts[:top_k * 2])

            # 默认答案（LLM 不可用时的回退）
            answer = "相关文档片段：\n" + "\n---\n".join(
                [p[:500] for p in context_parts[:top_k]]
            )

            # 尝试 LLM 生成
            llm = self._create_llm_client()
            if llm:
                try:
                    from graphiti_core.prompts.models import Message

                    max_context = 8000
                    if len(context) > max_context:
                        context = context[:max_context] + "\n...(内容已截断)"

                    messages = [
                        Message(
                            role="system",
                            content="你是一个知识问答助手，基于提供的内容准确回答问题。"
                                    "如果内容不足以回答问题，请诚实说明。",
                        ),
                        Message(
                            role="user",
                            content=f"问题：{query}\n\n参考内容：\n{context}"
                                    f"\n\n请基于以上内容回答问题。",
                        ),
                    ]

                    llm_result, _, _ = await llm._generate_response(messages)

                    if isinstance(llm_result, dict) and "response" in llm_result:
                        answer = llm_result["response"]
                    elif isinstance(llm_result, dict):
                        answer = json.dumps(llm_result, ensure_ascii=False)
                    elif isinstance(llm_result, str):
                        answer = llm_result
                except Exception as e:
                    logger.warning(f"RAG LLM call failed: {repr(e)}", exc_info=True)
        else:
            answer = "未找到与查询相关的文档"

        logger.info(
            f"RAG result: answer={len(answer)} chars, sources={len(sources)}, "
            f"vector={use_vector}, context_parts={len(context_parts)}"
        )
        result_count = len(sources)
        _audit_helper(
            "kb_rag_query_service",
            user="system",
            result_status="success",
            service="kb_service",
            resource=kb_id,
            details={
                "kb_id": kb_id,
                "query": query[:500],
                "result_count": result_count,
                "use_vector": use_vector,
            },
        )
        return {"answer": answer, "sources": sources, "related_entities": related_entities}

    async def crawl_web(self, kb_id: str, urls: List[str], max_depth: int = 1) -> Dict[str, Any]:
        kb = self._storage.get_knowledge_base(kb_id)
        if not kb:
            return {"status": "error", "message": "知识库不存在"}

        results = []
        for url in urls:
            try:
                content = ""
                status_code = None
                try:
                    from odap.infra.utils.web_scraper import WebScraper
                    scraper = WebScraper()
                    content = scraper.fetch_url(url)
                    if content:
                        content = scraper.extract_text(content)
                        status_code = 200
                except Exception:
                    try:
                        import urllib.request
                        resp = urllib.request.urlopen(url, timeout=10)
                        status_code = getattr(resp, "status", 200)
                        html = resp.read().decode("utf-8", errors="replace")
                        content = re.sub(r"<[^>]+>", " ", html)
                        content = re.sub(r"\s+", " ", content).strip()
                    except Exception as e:
                        storage_audit(
                            "crawl_url_failed",
                            result_status="failure",
                            result_message=str(e),
                            service="crawl",
                            resource=url[:200],
                            details={"url": url[:500], "kb_id": kb_id},
                        )
                        results.append({"url": url, "status": "failed", "error": str(e)})
                        continue

                content_len = len(content) if isinstance(content, str) else 0
                # 每成功爬一个 URL 记 crawl_url_success
                storage_audit(
                    "crawl_url_success",
                    service="crawl",
                    resource=url[:200],
                    details={
                        "url": url[:500],
                        "status_code": status_code,
                        "content_len": content_len,
                        "kb_id": kb_id,
                    },
                )
                doc = self._storage.create_document(kb_id, {
                    "title": url,
                    "content_type": "web",
                    "content": content[:50000],
                })
                results.append({"url": url, "doc_id": doc.get("doc_id"), "status": "success"})
            except Exception as e:
                storage_audit(
                    "crawl_url_failed",
                    result_status="failure",
                    result_message=str(e),
                    service="crawl",
                    resource=url[:200],
                    details={"url": url[:500], "kb_id": kb_id},
                )
                results.append({"url": url, "status": "failed", "error": str(e)})

        return {"task_id": f"crawl_{kb_id}", "results": results}
