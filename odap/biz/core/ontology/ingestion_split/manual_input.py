"""
数据采集层 - 手动输入处理模块
实现 ADR-031 L2: Data Ingestion & Normalization

ManualInputHandler: 表单/JSON/自然语言 → OntologyDocument
"""

import asyncio
import json
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from odap.biz.core.ontology.schema.document import (
    OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent,
    OntologyAction, OntologyRule, OntologyConstraint, VersionRef,
    SourceInfo, DocumentMeta, TemporalInfo, SourceType, DocType,
    EntityType, ActionStatus, OntologyDocumentSchema,
)

logger = logging.getLogger("data_ingestion")

_EXTRACT_PROMPT = """从以下文本中提取实体、关系和事件，并以JSON格式返回。

文本内容：
{text}

请提取：
1. 实体（entities）：包括人物(Person)、组织(Organization)、地点(Location)、物品(Item)等，每个实体包含：
   - entity_id: 唯一标识，格式如 "person-0", "org-0", "location-0"
   - entity_type: 实体类型（Person/Organization/Location/Item/Event）
   - name: 实体名称
   - basic_properties: 基本属性字典

2. 关系（relations）：实体之间的关系，包含：
   - relation_id: 唯一标识，格式如 "rel-0"
   - relation_type: 关系类型（如 member_of, married_to, child_of, located_at, manages, associated_with, owns, created_by 等）
   - source_entity: 源实体ID
   - target_entity: 目标实体ID
   - properties: 关系属性字典

3. 事件（events）：发生的事情，包含：
   - event_id: 唯一标识
   - event_type: 事件类型
   - timestamp: 时间戳（ISO格式）
   - description: 事件描述
   - participants: 参与者实体ID列表

请以以下JSON格式返回（只需返回JSON，不要其他内容）：
{{
    "entities": [
        {{"entity_id": "person-0", "entity_type": "Person", "name": "名称", "basic_properties": {{}}}}
    ],
    "relations": [
        {{"relation_id": "rel-0", "relation_type": "关系类型", "source_entity": "源实体ID", "target_entity": "目标实体ID", "properties": {{}}}}
    ],
    "events": [
        {{"event_id": "event-0", "event_type": "事件类型", "timestamp": "", "description": "描述", "participants": []}}
    ]
}}"""


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
            source=SourceInfo(
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

        for e_data in form_data.get("entities", []):
            doc.entities.append(OntologyEntity(**{
                k: v for k, v in e_data.items()
                if k in OntologyEntity.__dataclass_fields__
            }))

        for r_data in form_data.get("relations", []):
            temporal_data = r_data.pop("temporal", {})
            rel = OntologyRelation(**{
                k: v for k, v in r_data.items()
                if k in OntologyRelation.__dataclass_fields__ and k != "temporal"
            })
            if temporal_data:
                rel.temporal = TemporalInfo(**temporal_data)
            doc.relations.append(rel)

        for e_data in form_data.get("events", []):
            doc.events.append(OntologyEvent(**{
                k: v for k, v in e_data.items()
                if k in OntologyEvent.__dataclass_fields__
            }))

        doc.ontology_version.commit_message = f"手动输入: {doc.meta.title}"

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
        自然语言转 OntologyDocument（使用 LLM 转换）
        如果没有 LLM，使用规则提取降级方案
        """
        if self.llm is None:
            return self._extract_with_rules(text, scenario_id)

        prompt = _EXTRACT_PROMPT.format(text=text)

        try:
            result_dict = await self._call_llm(prompt)

            if result_dict and isinstance(result_dict, dict):
                doc = self._build_doc_from_llm_result(result_dict, text, scenario_id)
                if doc.entities or doc.relations:
                    logger.info(f"LLM 提取完成: {len(doc.entities)} 个实体, {len(doc.relations)} 个关系")
                    return doc
                logger.warning("LLM 返回空结果，降级到规则提取")

            return self._extract_with_rules(text, scenario_id)
        except Exception as e:
            logger.error(f"LLM 转换失败: {e}，降级到规则提取")
            return self._extract_with_rules(text, scenario_id)

    async def _call_llm(self, prompt: str) -> Optional[dict]:
        """统一调用 LLM 客户端，返回解析后的 dict"""
        if hasattr(self.llm, '_generate_response'):
            return await self._call_graphiti_llm(prompt)
        elif hasattr(self.llm, 'complete'):
            response = await self.llm.complete(prompt)
            return self._parse_json_response(response)
        elif hasattr(self.llm, 'chat'):
            response = await self.llm.chat([{"role": "user", "content": prompt}])
            return self._parse_json_response(response)
        else:
            logger.warning("LLM 客户端无可用接口，降级到规则提取")
            return None

    async def _call_graphiti_llm(self, prompt: str) -> Optional[dict]:
        """调用 graphiti-core 风格的 LLM 客户端（ZhipuAIClient）"""
        try:
            from graphiti_core.prompts.models import Message
            messages = [Message(role="user", content=prompt)]
            result, _, _ = await asyncio.wait_for(
                self.llm._generate_response(messages),
                timeout=30.0
            )
            return result
        except asyncio.TimeoutError:
            logger.error("LLM 调用超时（30s）")
            return None
        except Exception as e:
            logger.error(f"graphiti LLM 调用失败: {e}")
            return None

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """从 LLM 文本响应中解析 JSON"""
        if not response or not response.strip():
            return None
        text_resp = response.strip()
        if "```json" in text_resp:
            text_resp = text_resp.split("```json")[1].split("```")[0].strip()
        elif "```" in text_resp:
            text_resp = text_resp.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text_resp)
        except json.JSONDecodeError:
            return None

    def _build_doc_from_llm_result(self, result: dict, original_text: str, scenario_id: str = None) -> OntologyDocument:
        """从 LLM 返回的 dict 构建 OntologyDocument"""
        now = datetime.now(timezone.utc).isoformat()
        doc = OntologyDocument(
            doc_type=DocType.EVENT.value,
            source=SourceInfo(type=SourceType.MANUAL.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(title="自然语言输入", description=original_text[:500]),
            scenario_id=scenario_id,
        )

        for ent_data in result.get("entities", []):
            if isinstance(ent_data, dict) and ent_data.get("name"):
                doc.entities.append(OntologyEntity(
                    entity_id=ent_data.get("entity_id", f"entity-{len(doc.entities)}"),
                    entity_type=ent_data.get("entity_type", "Entity"),
                    name=ent_data["name"],
                    basic_properties=ent_data.get("basic_properties", {}),
                ))

        for rel_data in result.get("relations", []):
            if isinstance(rel_data, dict) and rel_data.get("source_entity") and rel_data.get("target_entity"):
                doc.relations.append(OntologyRelation(
                    relation_id=rel_data.get("relation_id", f"rel-{len(doc.relations)}"),
                    relation_type=rel_data.get("relation_type", "related_to"),
                    source_entity=rel_data["source_entity"],
                    target_entity=rel_data["target_entity"],
                    properties=rel_data.get("properties", {}),
                ))

        for evt_data in result.get("events", []):
            if isinstance(evt_data, dict):
                doc.events.append(OntologyEvent(
                    event_id=evt_data.get("event_id", f"event-{len(doc.events)}"),
                    event_type=evt_data.get("event_type", "narrative"),
                    timestamp=evt_data.get("timestamp", now),
                    description=evt_data.get("description", ""),
                ))

        if not doc.events:
            doc.events.append(OntologyEvent(
                event_type="narrative",
                timestamp=now,
                description=original_text[:500],
            ))

        doc.ontology_version.commit_message = f"LLM提取: {original_text[:50]}"
        return doc

    def _extract_with_rules(self, text: str, scenario_id: str = None) -> OntologyDocument:
        """基于规则的实体/关系提取（LLM 不可用时的降级方案）"""
        now = datetime.now(timezone.utc).isoformat()
        doc = OntologyDocument(
            doc_type=DocType.EVENT.value,
            source=SourceInfo(type=SourceType.MANUAL.value, collected_at=now),
            meta=DocumentMeta(title="自然语言输入", description=text[:500]),
            scenario_id=scenario_id,
        )

        entities, relations = self._rule_extract_entities_relations(text)

        for ent in entities:
            doc.entities.append(OntologyEntity(
                entity_id=ent["entity_id"],
                entity_type=ent["entity_type"],
                name=ent["name"],
                basic_properties=ent.get("basic_properties", {}),
            ))

        for rel in relations:
            doc.relations.append(OntologyRelation(
                relation_id=rel["relation_id"],
                relation_type=rel["relation_type"],
                source_entity=rel["source_entity"],
                target_entity=rel["target_entity"],
                properties=rel.get("properties", {}),
            ))

        doc.events.append(OntologyEvent(
            event_type="narrative",
            timestamp=now,
            description=text[:500],
        ))
        doc.ontology_version.commit_message = f"规则提取: {text[:50]}"
        return doc

    _SURNAME_CHARS = frozenset('赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴鬱胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍卻璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公')

    _NOT_IN_PERSON_NAME = frozenset({
        '的', '了', '在', '是', '有', '被', '把', '让', '给', '到', '从',
        '向', '为', '而', '但', '却', '又', '也', '都', '就', '才', '已',
        '将', '会', '能', '要', '和', '与', '跟', '或', '及', '之', '其',
        '这', '那', '此', '某', '各', '每', '该', '本', '上', '下', '中',
        '内', '外', '前', '后', '左', '右', '东', '西', '南', '北',
        '府', '国', '庄', '门', '派', '帮', '族', '院', '寺', '观',
        '宫', '殿', '营', '寨', '城', '村', '镇', '州', '省', '县',
        '市', '区', '街', '路', '山', '河', '湖', '海', '岛', '湾',
        '港', '关', '桥', '楼', '阁', '公司', '集团', '部门', '部队',
        '很', '非', '最', '更', '太', '真', '也', '还', '再', '又',
        '已', '曾', '正', '将', '要', '能', '会', '可', '应', '须',
        '得', '着', '过', '地', '里', '个', '些', '种', '样', '件',
        '条', '块', '片', '段', '份', '批', '群', '队', '组', '双',
        '两', '三', '四', '五', '六', '七', '八', '九', '十', '百',
        '千', '万', '亿', '数', '几', '多', '少', '半',
    })

    _STOP_WORDS = frozenset({
        '是', '的', '了', '在', '有', '和', '与', '被', '把', '让', '给',
        '到', '从', '向', '为', '而', '但', '却', '又', '也', '都', '就',
        '才', '已', '将', '会', '能', '要', '可以', '后来', '于是', '因为',
        '所以', '虽然', '不过', '非常', '两个', '两人', '他们', '她们',
        '我们', '你们', '自己', '这个', '那个', '什么', '怎么', '为什么',
        '不是', '没有', '已经', '正在', '曾经', '应该', '必须', '可能',
        '大概', '也许', '确实', '其实', '然后', '接着', '最后', '首先',
        '如果', '只要', '只有', '除了', '尽管', '无论', '不管', '即使',
        '后来', '还有', '只是', '只有', '还是', '但是', '而且', '或者',
        '并且', '以及', '由于', '通过', '根据', '按照', '关于', '对于',
        '其中', '之间', '之后', '之前', '以上', '以下', '以内', '以外',
    })

    def _is_likely_person_name(self, name: str, relax_surname: bool = False) -> bool:
        if not name or len(name) < 2 or len(name) > 4:
            return False
        if name in self._STOP_WORDS:
            return False
        for ch in name:
            if ch in self._NOT_IN_PERSON_NAME:
                return False
        if name[0] in self._SURNAME_CHARS:
            return True
        if len(name) == 2 and name[-1] in '哥姐叔伯婶嫂':
            return True
        if relax_surname and len(name) >= 2:
            return True
        return False

    def _rule_extract_entities_relations(self, text: str) -> Tuple[List[Dict], List[Dict]]:
        entities = []
        relations = []
        entity_map = {}

        self._extract_person_entities(text, entities, entity_map)
        self._extract_organization_entities(text, entities, entity_map)
        self._extract_location_entities(text, entities, entity_map)
        self._extract_item_entities(text, entities, entity_map)
        self._extract_relations(text, entities, relations, entity_map)
        self._infer_relations_from_context(text, entities, relations, entity_map)

        logger.info(f"规则提取完成: {len(entities)} 个实体, {len(relations)} 个关系")
        return entities, relations

    def _add_entity(self, name: str, entity_type: str, entities: list, entity_map: dict) -> Optional[str]:
        name = name.strip()
        if not name or len(name) < 2 or name in entity_map or name in self._STOP_WORDS:
            return entity_map.get(name)
        type_prefix = {
            "Person": "person", "Organization": "org",
            "Location": "location", "Item": "item"
        }.get(entity_type, "entity")
        eid = f"{type_prefix}-{len(entities)}"
        entity_map[name] = eid
        entities.append({
            "entity_id": eid,
            "entity_type": entity_type,
            "name": name,
            "basic_properties": {},
        })
        return eid

    def _extract_person_entities(self, text: str, entities: list, entity_map: dict):
        is_pattern = re.compile(r'([\u4e00-\u9fff]{2,4})是')
        for m in is_pattern.finditer(text):
            name = m.group(1)
            if self._is_likely_person_name(name):
                self._add_entity(name, "Person", entities, entity_map)

        title_patterns = [
            re.compile(r'([\u4e00-\u9fff]{2,4})(?:先生|女士|教授|博士|主任|经理|总监|总裁|部长|司令|将军|老爷|太太|奶奶|小姐|公子|嫂|婶|伯|叔)'),
        ]
        for pattern in title_patterns:
            for m in pattern.finditer(text):
                name = m.group(1)
                if self._is_likely_person_name(name):
                    self._add_entity(name, "Person", entities, entity_map)

        special_titles = [
            re.compile(r'(贾母|贾政|贾赦|王夫人|邢夫人|史太君|老祖宗|老太太|老太君|太君)'),
        ]
        for pattern in special_titles:
            for m in pattern.finditer(text):
                name = m.group(1)
                if name not in entity_map:
                    self._add_entity(name, "Person", entities, entity_map)

        kinship_suffix_patterns = [
            (re.compile(r'([\u4e00-\u9fff]{2,3}?)的(?:妻子|丈夫|外孙女|孙女|女儿|儿子|侄女|侄子|孙子|媳妇|老祖宗)'), "kinship"),
            (re.compile(r'([\u4e00-\u9fff]{2,3})(?:之妻|之夫|之子|之女|之外孙女|之孙女|之媳妇)'), "kinship"),
        ]
        for pattern, _ in kinship_suffix_patterns:
            for m in pattern.finditer(text):
                raw = m.group(0)
                name = m.group(1)
                while name and name[0] in '了是在有被把让给到从':
                    name = name[1:]
                if name and self._is_likely_person_name(name, relax_surname=True):
                    self._add_entity(name, "Person", entities, entity_map)

        verb_patterns = [
            re.compile(r'([\u4e00-\u9fff]{2,4})(?:很|非常|十分|极其|特别|格外)?(?:嫁给|娶了|疼爱|掌管|管理|负责|命令|指挥|帮助|救助|杀害|攻击|防御|喜欢|讨厌|认识|拜访|告诉|请教|邀请|陪同|送别|收留|收养|抚养|教导|陷害|背叛|追随|投靠)([\u4e00-\u9fff]{2,4})'),
        ]
        for pattern in verb_patterns:
            for m in pattern.finditer(text):
                for i in (1, 2):
                    name = m.group(i)
                    if self._is_likely_person_name(name):
                        self._add_entity(name, "Person", entities, entity_map)

        pair_patterns = [
            re.compile(r'([\u4e00-\u9fff]{2,4})(?:与|和|跟)([\u4e00-\u9fff]{2,4}?)(?:自幼相识|相识|相恋|相爱|情投意合|结为|成婚|成亲|是朋友|是同事|合作|一起|青梅竹马)'),
        ]
        for pattern in pair_patterns:
            for m in pattern.finditer(text):
                for i in (1, 2):
                    name = m.group(i)
                    if self._is_likely_person_name(name):
                        self._add_entity(name, "Person", entities, entity_map)

    def _extract_organization_entities(self, text: str, entities: list, entity_map: dict):
        org_patterns = [
            re.compile(r'([\u4e00-\u9fff]{1,3}(?:府|国|庄|门|派|帮|族|院|寺|观|宫|殿|营|寨))(?![\u4e00-\u9fff])'),
            re.compile(r'([\u4e00-\u9fff]{2,6}(?:公司|集团|部门|部队|军团|企业|银行|医院|学校|大学|研究所|委员会|政府|法院|检察院))'),
        ]

        _verb_prefixes = frozenset('进出到去来往回在从被把让给')

        for pattern in org_patterns:
            for m in pattern.finditer(text):
                name = m.group(1)
                if name not in entity_map and name not in self._STOP_WORDS and len(name) >= 2:
                    if name[0] not in '了是在有被把让给到从' and name[0] not in _verb_prefixes:
                        self._add_entity(name, "Organization", entities, entity_map)

    def _extract_location_entities(self, text: str, entities: list, entity_map: dict):
        loc_patterns = [
            re.compile(r'([\u4e00-\u9fff]{1,3}(?:山|城|村|镇|州|省|岛|湾|港|关|隘|桥|楼|阁|河|湖|海))(?![\u4e00-\u9fff])'),
            re.compile(r'([\u4e00-\u9fff]{2,5}(?:市|区|县|乡|街|路|巷|广场|公园|花园|庄园|城堡))'),
        ]

        for pattern in loc_patterns:
            for m in pattern.finditer(text):
                name = m.group(1)
                if name not in entity_map and name not in self._STOP_WORDS and len(name) >= 2:
                    self._add_entity(name, "Location", entities, entity_map)

    def _extract_item_entities(self, text: str, entities: list, entity_map: dict):
        item_patterns = [
            re.compile(r'(《[^》]+》)'),
            re.compile(r'([\u4e00-\u9fff]{1,3}(?:剑|刀|枪|弓|盾|杖|鞭|锤|斧|戟))(?![\u4e00-\u9fff])'),
        ]

        for pattern in item_patterns:
            for m in pattern.finditer(text):
                name = m.group(1)
                if name not in entity_map and name not in self._STOP_WORDS and len(name) >= 2:
                    self._add_entity(name, "Item", entities, entity_map)

    def _extract_relations(self, text: str, entities: list, relations: list, entity_map: dict):
        rel_idx = 0

        for person_name, person_eid in list(entity_map.items()):
            if not person_eid.startswith("person-"):
                continue

            for m in re.finditer(re.escape(person_name) + r'(?:与|和|跟)([\u4e00-\u9fff]{2,3})', text):
                other_name = m.group(1)
                if self._is_likely_person_name(other_name):
                    other_id = entity_map.get(other_name)
                    if not other_id:
                        other_id = self._add_entity(other_name, "Person", entities, entity_map)
                    if other_id and person_eid != other_id:
                        relations.append({"relation_id": f"rel-{rel_idx}", "relation_type": "associated_with", "source_entity": person_eid, "target_entity": other_id, "properties": {"extracted_from": "rule"}})
                        rel_idx += 1

            for m in re.finditer(re.escape(person_name) + r'的(?:妻子|丈夫)', text):
                for other_name, other_eid in entity_map.items():
                    if other_eid.startswith("person-") and other_eid != person_eid:
                        if f"是{other_name}的妻" in text or f"是{other_name}的丈夫" in text:
                            relations.append({"relation_id": f"rel-{rel_idx}", "relation_type": "married_to", "source_entity": person_eid, "target_entity": other_eid, "properties": {"extracted_from": "rule"}})
                            rel_idx += 1

            for m in re.finditer(re.escape(person_name) + r'(?:嫁给了?|娶了?)([\u4e00-\u9fff]{2,4})', text):
                target_name = m.group(1)
                if self._is_likely_person_name(target_name):
                    target_id = entity_map.get(target_name)
                    if not target_id:
                        target_id = self._add_entity(target_name, "Person", entities, entity_map)
                    if target_id and person_eid != target_id:
                        relations.append({"relation_id": f"rel-{rel_idx}", "relation_type": "married_to", "source_entity": person_eid, "target_entity": target_id, "properties": {"extracted_from": "rule"}})
                        rel_idx += 1

            for m in re.finditer(re.escape(person_name) + r'的(?:外孙女|孙女|女儿|儿子|孙子)', text):
                kinship_type = m.group(0).replace(person_name, '').replace('的', '')
                for other_name, other_eid in entity_map.items():
                    if other_eid.startswith("person-") and other_eid != person_eid:
                        pattern_check = f"是{other_name}的{kinship_type}"
                        if pattern_check in text or f"是{person_name}的{kinship_type}" in text.replace(person_name + "的", ""):
                            pass
                child_pattern = re.compile(r'([\u4e00-\u9fff]{2,4})是' + re.escape(person_name) + r'的(?:外孙女|孙女|女儿|儿子|孙子)')
                for cm in child_pattern.finditer(text):
                    child_name = cm.group(1)
                    if self._is_likely_person_name(child_name):
                        child_id = entity_map.get(child_name)
                        if not child_id:
                            child_id = self._add_entity(child_name, "Person", entities, entity_map)
                        if child_id and child_id != person_eid:
                            relations.append({"relation_id": f"rel-{rel_idx}", "relation_type": "child_of", "source_entity": child_id, "target_entity": person_eid, "properties": {"extracted_from": "rule"}})
                            rel_idx += 1

            for m in re.finditer(re.escape(person_name) + r'(?:很|非常|十分|极其|特别|格外)?(?:疼爱|掌管|管理|负责|命令|指挥|帮助|救助|杀害|攻击|防御|喜欢|讨厌|认识|拜访|告诉|请教|邀请|陪同|送别|收留|收养|抚养|教导|陷害|背叛|追随|投靠)([\u4e00-\u9fff]{2,4})', text):
                target_name = m.group(1)
                if self._is_likely_person_name(target_name):
                    target_id = entity_map.get(target_name)
                    if not target_id:
                        target_id = self._add_entity(target_name, "Person", entities, entity_map)
                    if target_id and person_eid != target_id:
                        relations.append({"relation_id": f"rel-{rel_idx}", "relation_type": "cares_for", "source_entity": person_eid, "target_entity": target_id, "properties": {"extracted_from": "rule"}})
                        rel_idx += 1

        member_of_patterns = [
            re.compile(r'([\u4e00-\u9fff]{2,4})是([\u4e00-\u9fff]{1,3}(?:府|国|庄|门|派|帮|族|院))的'),
            re.compile(r'([\u4e00-\u9fff]{2,4})(?:管理|掌管|负责|领导|统帅|指挥)([\u4e00-\u9fff]{1,3}(?:府|国|庄|门|派|帮|族|家|院|部队))'),
        ]
        for pattern in member_of_patterns:
            for m in pattern.finditer(text):
                source_name = m.group(1)
                target_name = m.group(2)
                if self._is_likely_person_name(source_name):
                    source_id = entity_map.get(source_name)
                    if not source_id:
                        source_id = self._add_entity(source_name, "Person", entities, entity_map)
                    target_id = entity_map.get(target_name)
                    if not target_id:
                        target_id = self._add_entity(target_name, "Organization", entities, entity_map)
                    if source_id and target_id and source_id != target_id:
                        relations.append({"relation_id": f"rel-{rel_idx}", "relation_type": "member_of", "source_entity": source_id, "target_entity": target_id, "properties": {"extracted_from": "rule"}})
                        rel_idx += 1

        located_at_pattern = re.compile(r'([\u4e00-\u9fff]{2,4})(?:住在|居住在|搬到|来到|前往|到达|住进)([\u4e00-\u9fff]{1,3}(?:府|国|庄|院|楼|宫|山|城|村|镇))')
        for m in located_at_pattern.finditer(text):
            source_name = m.group(1)
            target_name = m.group(2)
            if self._is_likely_person_name(source_name) and source_name[0] not in '了是在有被把让给到从':
                source_id = entity_map.get(source_name)
                if not source_id:
                    source_id = self._add_entity(source_name, "Person", entities, entity_map)
                target_id = entity_map.get(target_name)
                if not target_id:
                    target_id = self._add_entity(target_name, "Organization", entities, entity_map)
                if source_id and target_id and source_id != target_id:
                    relations.append({"relation_id": f"rel-{rel_idx}", "relation_type": "located_at", "source_entity": source_id, "target_entity": target_id, "properties": {"extracted_from": "rule"}})
                    rel_idx += 1

    def _infer_relations_from_context(self, text: str, entities: list, relations: list, entity_map: dict):
        existing_pairs = set()
        for r in relations:
            existing_pairs.add((r["source_entity"], r["target_entity"]))

        rel_idx = len(relations)
        person_ids = [(name, eid) for name, eid in entity_map.items()
                      if eid.startswith("person-")]
        org_ids = [(name, eid) for name, eid in entity_map.items()
                   if eid.startswith("org-")]

        for person_name, person_eid in person_ids:
            for org_name, org_eid in org_ids:
                if f"{person_name}是{org_name}" in text or f"{person_name}在{org_name}" in text:
                    pair = (person_eid, org_eid)
                    if pair not in existing_pairs:
                        relations.append({
                            "relation_id": f"rel-{rel_idx}",
                            "relation_type": "member_of",
                            "source_entity": person_eid,
                            "target_entity": org_eid,
                            "properties": {"extracted_from": "context_inference"},
                        })
                        existing_pairs.add(pair)
                        rel_idx += 1
