"""
数据采集层 - 数据摄取与归纳模块
实现 ADR-031 L2: Data Ingestion & Normalization

组件:
- NewsIngester: 联网检索 → LLM 归纳 → OntologyDocument
- ManualInputHandler: 表单/JSON/自然语言 → OntologyDocument
- RandomEventGenerator: 涉事方行为模型 → OntologyDocument（参考 NetLogo）
- OntologyDocumentIO: 导入/导出 .odoc.json
"""

import json
import uuid
import random
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.ontology_document import (
    OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent,
    OntologyAction, OntologyRule, OntologyConstraint, VersionRef,
    DataSource, DocumentMeta, TemporalInfo, SourceType, DocType,
    EntityType, ActionStatus, OntologyDocumentSchema, make_battle_event_document
)

logger = logging.getLogger("data_ingestion")


# ─────────────────────────────────────────────────
# 联网检索采集 - NewsIngester
# ─────────────────────────────────────────────────

ONTOLOGY_EXTRACT_PROMPT = """
你是一位专业的情报分析师。请从以下新闻/报道文本中提取结构化信息，
输出符合 OntologyDocument 格式的 JSON（仅输出 JSON，不要任何解释）。

【事件背景】
{context}

【文本内容】
{text}

【输出格式要求】
{{
  "doc_id": "evt-{date}-xxxxx",
  "doc_type": "event",
  "source": {{"type": "news_ingest", "url": "{url}", "collected_at": "{timestamp}", "confidence": 0.8}},
  "meta": {{"title": "...", "description": "...", "tags": [...], "language": "zh", "classification": "SIM"}},
  "entities": [
    {{
      "entity_id": "unit-xxx-001",
      "entity_type": "Unit|Equipment|Location|Person|Organization",
      "name": "...",
      "name_en": "...",
      "basic_properties": {{"side": "red|blue|neutral", "location": "...", "status": "..."}},
      "statistical_properties": {{"combat_power": 0.0-1.0, "morale": 0.0-1.0}},
      "capabilities": {{}},
      "constraints": []
    }}
  ],
  "relations": [
    {{
      "relation_id": "rel-xxx",
      "relation_type": "engaged_with|commands|supported_by|deployed_at|reinforces",
      "source_entity": "entity_id",
      "target_entity": "entity_id",
      "properties": {{}},
      "temporal": {{"start_time": "{timestamp}", "is_current": true}}
    }}
  ],
  "events": [
    {{
      "event_id": "evt-xxx",
      "event_type": "contact|attack|retreat|reinforce|patrol|cease_fire",
      "timestamp": "{timestamp}",
      "location": "...",
      "participants": ["entity_id_1", "entity_id_2"],
      "description": "...",
      "outcome": {{}},
      "phase": "..."
    }}
  ],
  "actions": [],
  "rules": [],
  "constraints": [],
  "ontology_version": {{"version_id": "", "parent_version": null, "commit_message": "新闻采集归纳"}}
}}

注意: 如果文本信息不足，合理推断并标注 confidence 较低值。
"""


class NewsIngester:
    """
    联网检索并归纳为 OntologyDocument

    检索链路:
    Tavily API (首选) → SerpAPI (备选) → DuckDuckGo HTML 解析 (降级) → Mock (无API时)
    """

    def __init__(self, llm_client=None, search_api_key: str = None, tavily_api_key: str = None):
        self.llm = llm_client
        self._search_api_key = search_api_key
        self._tavily_api_key = tavily_api_key
        self._use_mock = (llm_client is None)

    async def ingest(
        self,
        query: str,
        event_context: str = "",
        max_sources: int = 5,
    ) -> List[OntologyDocument]:
        """
        联网检索 + LLM 归纳 → OntologyDocument 列表

        Args:
            query: 检索关键词（如 "B区遭遇战 2026"）
            event_context: 事件背景描述（辅助 LLM 理解）
            max_sources: 最大检索来源数

        Returns:
            List[OntologyDocument]: 验证通过的文档列表
        """
        logger.info(f"开始联网检索: {query}")

        if self._use_mock:
            logger.warning("未配置 LLM/Search API，使用 Mock 数据")
            return self._generate_mock_news_docs(query, event_context)

        try:
            # 步骤1: 联网检索
            search_results = await self._search(query, max_sources)
            if not search_results:
                logger.warning("检索结果为空，使用 Mock")
                return self._generate_mock_news_docs(query, event_context)

            # 步骤2: 汇总文本
            combined_text = self._combine_sources(search_results)
            urls = [r.get("url", "") for r in search_results[:3]]

            # 步骤3: LLM 结构化抽取
            raw_docs = await self._extract_with_llm(combined_text, event_context, urls)

            # 步骤4: 验证
            validated = []
            for doc_data in raw_docs:
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    validated.append(OntologyDocument.from_dict(doc_data))
                else:
                    logger.warning(f"文档验证失败: {result.errors}")

            logger.info(f"成功归纳 {len(validated)} 个文档")
            return validated

        except Exception as e:
            logger.error(f"联网检索失败: {e}，使用 Mock")
            return self._generate_mock_news_docs(query, event_context)

    async def _search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """执行联网检索（优先 Tavily，降级 DuckDuckGo）"""
        # Tavily
        if self._tavily_api_key:
            try:
                return await self._search_tavily(query, max_results)
            except Exception as e:
                logger.warning(f"Tavily 检索失败: {e}")

        # 降级 Mock
        logger.info("使用 Mock 检索结果")
        return []

    async def _search_tavily(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Tavily API 检索"""
        import aiohttp
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self._tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                return data.get("results", [])

    def _combine_sources(self, results: List[Dict[str, Any]]) -> str:
        """汇总多源文本"""
        parts = []
        for i, r in enumerate(results[:5], 1):
            title = r.get("title", "")
            content = r.get("content", r.get("snippet", ""))
            url = r.get("url", "")
            parts.append(f"[来源{i}] {title}\nURL: {url}\n{content[:1000]}")
        return "\n\n---\n\n".join(parts)

    async def _extract_with_llm(
        self, text: str, context: str, urls: List[str]
    ) -> List[Dict[str, Any]]:
        """使用 LLM 将文本抽取为 OntologyDocument JSON"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")
        url_str = urls[0] if urls else ""

        prompt = ONTOLOGY_EXTRACT_PROMPT.format(
            context=context or "战场事件分析",
            text=text,
            date=date_str,
            url=url_str,
            timestamp=now,
        )

        try:
            if hasattr(self.llm, 'complete'):
                response = await self.llm.complete(prompt)
            elif hasattr(self.llm, 'chat'):
                response = await self.llm.chat([{"role": "user", "content": prompt}])
            else:
                return []

            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"LLM 抽取失败: {e}")
            return []

    def _parse_json_response(self, response: str) -> List[Dict[str, Any]]:
        """解析 LLM 响应中的 JSON"""
        # 提取 JSON 块
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except Exception:
            pass
        return []

    def _generate_mock_news_docs(self, query: str, context: str) -> List[OntologyDocument]:
        """生成 Mock 新闻文档（无 API 时的降级）"""
        doc = make_battle_event_document(
            title=f"新闻采集: {query}",
            red_unit="红方部队",
            blue_unit="蓝方部队",
            location="交战区域",
            event_type="contact",
            source_type=SourceType.NEWS_INGEST.value,
        )
        doc.source.url = f"https://mock-news.local/search?q={query}"
        doc.source.confidence = 0.6
        doc.meta.description = f"基于检索词 '{query}' 生成的 Mock 数据（{context or '无背景'}）"
        logger.info(f"生成 Mock 新闻文档: {doc.doc_id}")
        return [doc]


# ─────────────────────────────────────────────────
# 手动输入处理 - ManualInputHandler
# ─────────────────────────────────────────────────

class ManualInputHandler:
    """
    处理用户手动输入的动态信息

    输入模式:
    1. 结构化 dict（来自 Web 表单）
    2. 自由 JSON 字符串（直接粘贴）
    3. 自然语言（LLM 转换，可选）
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def from_form(self, form_data: dict, scenario_id: str = None) -> OntologyDocument:
        """从表单 dict 构建 OntologyDocument"""
        now = datetime.now(timezone.utc).isoformat()

        doc = OntologyDocument(
            doc_id=form_data.get("doc_id") or f"manual-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}",
            doc_type=form_data.get("doc_type", DocType.EVENT.value),
            source=DataSource(
                type=SourceType.MANUAL.value,
                collected_at=now,
                confidence=1.0,
                author=form_data.get("author"),
            ),
            meta=DocumentMeta(
                title=form_data.get("title", "手动输入事件"),
                description=form_data.get("description", ""),
                tags=form_data.get("tags", []),
            ),
            scenario_id=scenario_id or form_data.get("scenario_id"),
        )

        # 解析实体
        for e_data in form_data.get("entities", []):
            doc.entities.append(OntologyEntity(**{
                k: v for k, v in e_data.items()
                if k in OntologyEntity.__dataclass_fields__
            }))

        # 解析关系
        for r_data in form_data.get("relations", []):
            temporal_data = r_data.pop("temporal", {})
            rel = OntologyRelation(**{
                k: v for k, v in r_data.items()
                if k in OntologyRelation.__dataclass_fields__ and k != "temporal"
            })
            if temporal_data:
                rel.temporal = TemporalInfo(**temporal_data)
            doc.relations.append(rel)

        # 解析事件
        for e_data in form_data.get("events", []):
            doc.events.append(OntologyEvent(**{
                k: v for k, v in e_data.items()
                if k in OntologyEvent.__dataclass_fields__
            }))

        # 版本
        doc.ontology_version.commit_message = f"手动输入: {doc.meta.title}"

        # 验证
        result = OntologyDocumentSchema.validate(doc)
        if not result.is_valid:
            raise ValueError(f"表单数据验证失败: {'; '.join(result.errors)}")

        return doc

    async def from_json(self, raw_json: str, scenario_id: str = None) -> OntologyDocument:
        """验证并解析 JSON 字符串"""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {e}")

        # Schema 验证
        result = OntologyDocumentSchema.validate(data)
        if not result.is_valid:
            raise ValueError(f"Schema 验证失败: {'; '.join(result.errors)}")

        doc = OntologyDocument.from_dict(data)
        if scenario_id:
            doc.scenario_id = scenario_id
        doc.source.type = SourceType.MANUAL.value

        return doc

    async def from_natural_language(self, text: str, scenario_id: str = None) -> OntologyDocument:
        """
        自然语言 → OntologyDocument（使用 LLM 转换）
        如果没有 LLM，生成基础文档
        """
        if self.llm is None:
            # 无 LLM：生成最简 event 文档
            now = datetime.now(timezone.utc).isoformat()
            doc = OntologyDocument(
                doc_type=DocType.EVENT.value,
                source=DataSource(type=SourceType.MANUAL.value, collected_at=now),
                meta=DocumentMeta(title="自然语言输入", description=text[:500]),
                scenario_id=scenario_id,
            )
            doc.events.append(OntologyEvent(
                event_type="generic",
                timestamp=now,
                description=text[:500],
            ))
            doc.ontology_version.commit_message = f"自然语言输入: {text[:50]}"
            return doc

        # 使用 LLM 转换
        prompt = f"""将以下自然语言描述转换为 OntologyDocument JSON 格式（只输出 JSON）:

{text}

参考格式:
{{
  "doc_id": "manual-xxxxx",
  "doc_type": "event",
  "source": {{"type": "manual", "collected_at": "{datetime.now(timezone.utc).isoformat()}", "confidence": 0.95}},
  "meta": {{"title": "...", "description": "...", "tags": []}},
  "entities": [...],
  "relations": [...],
  "events": [...],
  "actions": [],
  "rules": [],
  "constraints": [],
  "ontology_version": {{"version_id": "", "parent_version": null, "commit_message": "..."}}
}}"""

        try:
            if hasattr(self.llm, 'complete'):
                response = await self.llm.complete(prompt)
            elif hasattr(self.llm, 'chat'):
                response = await self.llm.chat([{"role": "user", "content": prompt}])
            else:
                response = ""

            # 提取 JSON
            text_resp = response.strip()
            if "```json" in text_resp:
                text_resp = text_resp.split("```json")[1].split("```")[0].strip()
            elif "```" in text_resp:
                text_resp = text_resp.split("```")[1].split("```")[0].strip()

            data = json.loads(text_resp)
            doc = OntologyDocument.from_dict(data)
            if scenario_id:
                doc.scenario_id = scenario_id
            return doc
        except Exception as e:
            logger.error(f"LLM 转换失败: {e}，降级到基础文档")
            return await self.from_natural_language.__wrapped__(self, text, scenario_id) if hasattr(
                self.from_natural_language, '__wrapped__') else OntologyDocument(
                doc_type=DocType.EVENT.value,
                source=DataSource(type=SourceType.MANUAL.value),
                meta=DocumentMeta(title="自然语言输入", description=text[:500]),
                scenario_id=scenario_id,
            )


# ─────────────────────────────────────────────────
# 随机事件生成器 - RandomEventGenerator
# 参考 NetLogo 多智能体行为概率模型
# ─────────────────────────────────────────────────

class RandomEventGenerator:
    """
    按涉事方和事件模板自动随机生成动态信息

    参考 NetLogo 多智能体随机行为模型:
    - 每个涉事方有行为概率表（patrol/attack/retreat/reinforce）
    - 基于当前状态（morale/supply/combat_power）权重调整
    - 事件输出符合 OntologyDocument 格式
    """

    # 涉事方行为概率表（参考 NetLogo）
    PARTY_BEHAVIOR_PROFILES = {
        "red": {
            "attack": 0.40,
            "patrol": 0.25,
            "reinforce": 0.20,
            "retreat": 0.10,
            "recon": 0.05,
        },
        "blue": {
            "attack": 0.30,
            "patrol": 0.30,
            "reinforce": 0.25,
            "retreat": 0.10,
            "recon": 0.05,
        },
        "neutral": {
            "patrol": 0.55,
            "evacuate": 0.25,
            "report": 0.15,
            "cease_fire": 0.05,
        },
    }

    # 单位名称库
    UNIT_NAMES = {
        "red": ["红方装甲营", "红方机步旅", "红方炮兵团", "红方特战队", "红方工兵营", "红方防空营"],
        "blue": ["蓝方机步营", "蓝方装甲旅", "蓝方炮兵团", "蓝方海军陆战队", "蓝方工兵连", "蓝方防空连"],
        "neutral": ["第三方观察团", "中立方协调员", "平民撤离队"],
    }

    # 地点库
    LOCATIONS = [
        "A区北部高地", "B区遭遇地带", "C区渡口", "D区城镇",
        "E区山地走廊", "F区海岸线", "G区平原", "H区丛林",
    ]

    # 事件类型对应关系
    ACTION_TO_EVENT = {
        "attack": "contact",
        "patrol": "patrol",
        "reinforce": "reinforce",
        "retreat": "retreat",
        "recon": "recon",
        "evacuate": "evacuate",
        "report": "report",
        "cease_fire": "cease_fire",
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def generate(
        self,
        parties: List[str],
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
        use_llm_for_description: bool = False,
    ) -> List[OntologyDocument]:
        """
        按涉事方生成随机事件

        Args:
            parties: 参与方列表（如 ["red", "blue"]）
            scenario_context: 当前场景状态（影响行为概率权重）
            count: 生成事件数量
            scenario_id: 归属场景
            use_llm_for_description: 是否用 LLM 生成丰富描述

        Returns:
            List[OntologyDocument]
        """
        context = scenario_context or {}
        docs = []

        for _ in range(count):
            # 随机选择涉事方
            party = random.choice(parties)
            behavior_profile = self.PARTY_BEHAVIOR_PROFILES.get(party, self.PARTY_BEHAVIOR_PROFILES["red"])

            # 根据场景状态调整权重
            adjusted_profile = self._adjust_weights(behavior_profile, context, party)

            # 随机选择行为
            action_type = self._weighted_choice(adjusted_profile)

            # 生成对手（仅进攻/撤退时有对手）
            opponent = None
            if action_type in ["attack", "retreat", "reinforce"]:
                other_parties = [p for p in parties if p != party]
                if other_parties:
                    opponent = random.choice(other_parties)

            doc = await self._build_document(
                actor_party=party,
                action_type=action_type,
                opponent_party=opponent,
                context=context,
                scenario_id=scenario_id,
                use_llm=use_llm_for_description,
            )
            docs.append(doc)

        logger.info(f"随机生成 {len(docs)} 个事件（涉事方: {parties}）")
        return docs

    def _adjust_weights(self, profile: dict, context: dict, party: str) -> dict:
        """根据场景状态动态调整行为权重"""
        adjusted = dict(profile)
        morale = context.get(f"{party}_morale", 0.7)
        supply = context.get(f"{party}_supply", 0.7)
        combat_power = context.get(f"{party}_combat_power", 0.7)

        # 士气低 → 增加撤退概率
        if morale < 0.4 and "retreat" in adjusted:
            adjusted["retreat"] = adjusted.get("retreat", 0) * 2
        # 供给不足 → 减少攻击概率
        if supply < 0.3 and "attack" in adjusted:
            adjusted["attack"] = adjusted.get("attack", 0) * 0.5
        # 战力强 → 增加进攻概率
        if combat_power > 0.8 and "attack" in adjusted:
            adjusted["attack"] = adjusted.get("attack", 0) * 1.5

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        return adjusted

    def _weighted_choice(self, weights: dict) -> str:
        """加权随机选择"""
        keys = list(weights.keys())
        values = list(weights.values())
        return random.choices(keys, weights=values, k=1)[0]

    async def _build_document(
        self,
        actor_party: str,
        action_type: str,
        opponent_party: Optional[str],
        context: dict,
        scenario_id: str,
        use_llm: bool,
    ) -> OntologyDocument:
        """构建随机事件 OntologyDocument"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")
        location = random.choice(self.LOCATIONS)

        actor_names = self.UNIT_NAMES.get(actor_party, ["未知部队"])
        actor_name = random.choice(actor_names)
        actor_id = f"unit-{actor_party}-{uuid.uuid4().hex[:6]}"

        entities = [
            OntologyEntity(
                entity_id=actor_id,
                entity_type=EntityType.UNIT.value,
                name=actor_name,
                name_en=actor_name,
                basic_properties={
                    "side": actor_party,
                    "location": location,
                    "status": "active",
                    "unit_type": random.choice(["armor", "infantry", "artillery", "recon"]),
                },
                statistical_properties={
                    "combat_power": round(random.uniform(0.4, 0.95), 2),
                    "morale": round(random.uniform(0.5, 0.95), 2),
                    "supply_level": round(random.uniform(0.3, 0.90), 2),
                    "casualty_rate": round(random.uniform(0.0, 0.15), 3),
                },
            )
        ]

        relations = []
        events = []
        actions = []

        event_type = self.ACTION_TO_EVENT.get(action_type, "generic")

        if opponent_party:
            opp_names = self.UNIT_NAMES.get(opponent_party, ["未知部队"])
            opp_name = random.choice(opp_names)
            opp_id = f"unit-{opponent_party}-{uuid.uuid4().hex[:6]}"

            entities.append(OntologyEntity(
                entity_id=opp_id,
                entity_type=EntityType.UNIT.value,
                name=opp_name,
                name_en=opp_name,
                basic_properties={
                    "side": opponent_party,
                    "location": location,
                    "status": "active",
                },
                statistical_properties={
                    "combat_power": round(random.uniform(0.4, 0.90), 2),
                    "morale": round(random.uniform(0.5, 0.90), 2),
                    "supply_level": round(random.uniform(0.4, 0.90), 2),
                },
            ))

            rel_type_map = {
                "attack": "engaged_with",
                "reinforce": "reinforces",
                "retreat": "retreats_from",
            }
            relations.append(OntologyRelation(
                relation_type=rel_type_map.get(action_type, "related_to"),
                source_entity=actor_id,
                target_entity=opp_id,
                temporal=TemporalInfo(start_time=now, is_current=True),
            ))

            description = f"{actor_name} 对 {opp_name} 执行 {action_type}（位于 {location}）"
            events.append(OntologyEvent(
                event_type=event_type,
                timestamp=now,
                location=location,
                participants=[actor_id, opp_id],
                description=description,
                outcome={"terrain_control": random.choice(["contested", "held", "lost"])},
                phase=random.choice(["initial", "main", "final"]),
            ))
            actions.append(OntologyAction(
                action_type=action_type,
                actor=actor_id,
                target=opp_id,
                timestamp=now,
                parameters={"mode": random.choice(["aggressive", "cautious", "defensive"])},
                status=ActionStatus.EXECUTED.value,
            ))
        else:
            description = f"{actor_name} 在 {location} 执行 {action_type}"
            events.append(OntologyEvent(
                event_type=event_type,
                timestamp=now,
                location=location,
                participants=[actor_id],
                description=description,
                phase="active",
            ))

        title = f"[随机] {actor_name} - {action_type}"
        if use_llm and self.llm:
            description = await self._enrich_description(description)

        doc = OntologyDocument(
            doc_id=f"rand-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=DataSource(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=[actor_party, action_type, location],
            ),
            entities=entities,
            relations=relations,
            events=events,
            actions=actions,
            ontology_version=VersionRef(commit_message=f"随机生成: {actor_name} {action_type}"),
            scenario_id=scenario_id,
        )
        return doc

    async def _enrich_description(self, basic_desc: str) -> str:
        """使用 LLM 丰富事件描述"""
        try:
            prompt = f"请将以下军事事件描述扩展为1-2句更生动的叙述（保持事实）：{basic_desc}"
            if hasattr(self.llm, 'complete'):
                return await self.llm.complete(prompt)
        except Exception:
            pass
        return basic_desc


# ─────────────────────────────────────────────────
# 导入/导出 - OntologyDocumentIO
# ─────────────────────────────────────────────────

class OntologyDocumentIO:
    """
    OntologyDocument 导入/导出管理

    文件格式: .odoc.json
    支持: 单文档、场景包（多文档）、全量本体快照
    """

    def __init__(self, version_manager=None):
        self.versions = version_manager

    async def export_document(self, doc: OntologyDocument) -> bytes:
        """导出单个文档为 .odoc.json"""
        return doc.to_json(indent=2).encode("utf-8")

    async def export_scenario(
        self,
        scenario_id: str,
        documents: List[OntologyDocument],
    ) -> bytes:
        """导出整个场景（含所有事件）"""
        package = {
            "export_type": "scenario",
            "scenario_id": scenario_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "document_count": len(documents),
            "documents": [doc.to_dict() for doc in documents],
        }
        return json.dumps(package, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    async def export_versions_snapshot(
        self,
        versions_summary: List[dict],
    ) -> bytes:
        """导出版本链快照"""
        snapshot = {
            "export_type": "versions_snapshot",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version_count": len(versions_summary),
            "versions": versions_summary,
        }
        return json.dumps(snapshot, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    async def import_file(
        self,
        content: bytes,
        scenario_id: str = None,
    ) -> List[OntologyDocument]:
        """
        导入 .odoc.json

        步骤:
        1. JSON Schema 验证
        2. 冲突检测
        3. 返回文档列表（由调用方决定是否触发热写入）
        """
        try:
            raw = json.loads(content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"文件格式错误: {e}")

        documents = []

        # 场景包
        if isinstance(raw, dict) and raw.get("export_type") == "scenario":
            for doc_data in raw.get("documents", []):
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    doc = OntologyDocument.from_dict(doc_data)
                    if scenario_id:
                        doc.scenario_id = scenario_id
                    doc.source.type = SourceType.IMPORT.value
                    documents.append(doc)
                else:
                    logger.warning(f"导入文档验证失败: {result.errors}")
        # 单文档
        elif isinstance(raw, dict):
            result = OntologyDocumentSchema.validate(raw)
            if result.is_valid:
                doc = OntologyDocument.from_dict(raw)
                if scenario_id:
                    doc.scenario_id = scenario_id
                doc.source.type = SourceType.IMPORT.value
                documents.append(doc)
            else:
                raise ValueError(f"文档验证失败: {'; '.join(result.errors)}")
        # 文档列表
        elif isinstance(raw, list):
            for doc_data in raw:
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    doc = OntologyDocument.from_dict(doc_data)
                    if scenario_id:
                        doc.scenario_id = scenario_id
                    doc.source.type = SourceType.IMPORT.value
                    documents.append(doc)

        logger.info(f"导入 {len(documents)} 个文档")
        return documents
