"""
数据采集层 - 冲突事件随机生成器
实现 ADR-031 L2: Data Ingestion & Normalization

ConflictEventGenerator: 冲突事件生成器
参考 NetLogo 多智能体行为概率模型
"""

import json
import uuid
import random
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_generator import BaseRandomGenerator
from ..schema.document import (
    OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent,
    OntologyAction, VersionRef, SourceInfo, DocumentMeta, TemporalInfo,
    SourceType, DocType, EntityType, ActionStatus,
)

logger = logging.getLogger("data_ingestion")


class ConflictEventGenerator(BaseRandomGenerator):
    """
    按涉事方和事件模板自动随机生成动态信息
    参考 NetLogo 多智能体随机行为模型:
    - 每个涉事方有行为概率表（patrol/engage/withdraw/support）
    - 基于当前状态（readiness/supply/capability_index）权重调整
    - 事件输出符合 OntologyDocument 格式
    """

    # 生成器类型标识
    GENERATOR_TYPE = "conflict"
    GENERATOR_NAME = "冲突事件生成器"
    GENERATOR_DESCRIPTION = "生成冲突场景下的各种事件，包括交锋、巡查、支援、撤出、侦查等行动"

    def get_generator_name(self) -> str:
        return self.GENERATOR_NAME

    def get_generator_description(self) -> str:
        return self.GENERATOR_DESCRIPTION

    # 涉事方行为概率表（参考 NetLogo）
    PARTY_BEHAVIOR_PROFILES = {
        "party_a": {
            "engage": 0.40,
            "patrol": 0.25,
            "support": 0.20,
            "withdraw": 0.10,
            "scout": 0.05,
        },
        "party_b": {
            "engage": 0.30,
            "patrol": 0.30,
            "support": 0.25,
            "withdraw": 0.10,
            "scout": 0.05,
        },
        "neutral": {
            "patrol": 0.55,
            "evacuate": 0.25,
            "report": 0.15,
            "cease_operation": 0.05,
        },
    }

    # 单位名称库
    UNIT_NAMES = {
        "party_a": [
            "A方第1分队", "A方第2机动组", "A方第3支援队", "A方特勤组", "A方工程队", "A方防护组",
            "A方第4巡查队", "A方航空组", "A方信息组", "A方资源保障队", "A方调查组", "A方第5编队",
            "A方空投组", "A方第6合成队", "A方综合队", "A方信息行动单元",
        ],
        "party_b": [
            "B方第1机动组", "B方第2编队", "B方第3支援队", "B方海上行动组", "B方工程组", "B方防护组",
            "B方特勤组", "B方空中突击队", "B方第4编队", "B方后勤支援组", "B方信息组", "B方第5支援队",
            "B方第6机动队", "B方快速反应组", "B方两栖行动组", "B方空中支援组",
        ],
        "neutral": [
            "第三方观察团", "中立方协调员", "民众撤离队", "国际协调组织", "人道主义救援组织",
            "国际组织代表", "当地志愿者", "记者团",
        ],
    }

    # 地点库
    LOCATIONS = [
        "A区北部区域", "B区接触地带", "C区渡口", "D区城镇",
        "E区山地走廊", "F区海岸线", "G区平原", "H区丛林",
        "K区桥梁枢纽", "L区铁路交叉点", "M区机场", "N区港口设施",
        "O区山区据点", "P区沙漠地带", "Q区沼泽地带", "R区城市郊区",
        "北部区域", "东部据点", "莲花湖地区", "青河渡口", "龙山山口",
        "中央节点", "白云机场", "南方港", "友谊桥", "中央平原",
    ]

    # 装备库
    EQUIPMENT_TYPES = [
        "重型载具A", "重型载具B", "轻型载具",
        "装甲运输车A", "装甲运输车B", "通用运输车",
        "自行投射装置A", "自行投射装置B", "牵引投射装置",
        "突击型旋翼机A", "突击型旋翼机B", "武装旋翼机",
        "远程投射系统-11", "战术投射系统-15", "防护系统-9",
        "无人载具A", "无人载具B", "观测无人设备",
        "移动防护系统", "综合防护系统", "轮式运输车",
    ]

    # 天气条件
    WEATHER_CONDITIONS = [
        "晴朗", "多云", "阴天", "小雨", "中雨", "大雨",
        "大雾", "小雪", "中雪", "大风", "沙尘暴", "夜间",
    ]

    # 时间段
    TIME_PERIODS = [
        "凌晨", "拂晓", "上午", "中午", "下午", "傍晚", "黄昏", "夜间", "深夜",
    ]

    # 地形类型
    TERRAIN_TYPES = [
        "山地", "丘陵", "平原", "丛林", "沙漠", "沼泽", "城市", "海岸", "高原", "草原",
    ]

    # 事件类型对应关系
    ACTION_TO_EVENT = {
        "engage": "contact",
        "patrol": "patrol",
        "support": "support",
        "withdraw": "withdraw",
        "scout": "scout",
        "evacuate": "evacuate",
        "report": "report",
        "cease_operation": "cease_operation",
    }

    # 行动描述模板
    ACTION_DESCRIPTIONS = {
        "engage": [
            "对{opponent}发起行动，",
            "在{location}地区与{eqp}协同对{opponent}行动，",
            "使用无人设备监测后，对{opponent}实施精确操作，",
            "在{terrain}地形对{opponent}实施包围行动，",
        ],
        "patrol": [
            "在{location}附近进行例行巡查，",
            "对{terrain}地带进行搜索排查，",
            "在{eqp}掩护下对{location}实施巡查，",
            "针对可疑目标进行定点巡查，",
        ],
        "support": [
            "增派{eqp}前往{location}支援，",
            "从后方调集预备队支援{location}，",
            "空中投送{eqp}至{location}，",
            "通过公路机动向{location}输送支援力量，",
        ],
        "withdraw": [
            "因战略调整主动撤离{location}，",
            "在{eqp}掩护下有序撤出，",
            "受恶劣天气{weather}影响暂时后撤，",
            "完成阻击任务后主动撤出{location}，",
        ],
        "scout": [
            "派遣调查组前往{location}收集信息，",
            "使用无人设备对{terrain}地带实施抵近观测，",
            "调查人员潜入{location}获取信息，",
            "电子监测{location}区域的对方通讯，",
        ],
        "evacuate": [
            "组织平民从{location}安全撤离，",
            "在{weather}条件下紧急疏散当地居民，",
            "开辟安全走廊协助民众撤离危险区域，",
            "医疗队前往{location}执行撤离任务，",
        ],
        "report": [
            "向上级汇报{location}区域态势，",
            "观察员报告{terrain}地带的最新情况，",
            "信息部门汇总并上报{location}调查结果，",
            "多方信息汇总后形成态势报告，",
        ],
        "cease_operation": [
            "根据协议在{location}停止行动，",
            "双方协商后在{terrain}地带实现停止行动，",
            "国际调停后在{location}实施停止行动，",
            "暂时在{location}地区实行临时停止行动，",
        ],
    }

    # 结果描述
    OUTCOME_DESCRIPTIONS = {
        "engage": [
            "达成{count}个目标",
            "对对方造成重大影响",
            "成功突破对方防线",
            "占据关键位置",
            "击退对方交锋",
        ],
        "patrol": [
            "未发现异常情况",
            "发现可疑目标并标记",
            "确认区域安全",
            "搜集到有价值信息",
            "排除{count}处安全隐患",
        ],
        "support": [
            "有效增强了守卫力量",
            "及时补充了行动人员",
            "提升了整体能力",
            "巩固了防线",
            "扭转了不利局面",
        ],
        "withdraw": [
            "成功保存了有生力量",
            "避免了更大损失",
            "撤至安全区域",
            "完成战略调整",
            "重新部署完毕",
        ],
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def generate(
        self,
        parties: List[str] = None,
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
        use_llm_for_description: bool = False,
    ) -> List[OntologyDocument]:
        """
        按涉事方生成随机事件

        Args:
            parties: 参与方列表（如 ["party_a", "party_b"]）
            scenario_context: 当前场景状态（影响行为概率权重）
            count: 生成事件数量
            scenario_id: 归属场景
            use_llm_for_description: 是否用 LLM 生成丰富描述

        Returns:
            List[OntologyDocument]
        """
        context = scenario_context or {}
        docs = []

        if not parties:
            parties = ["party_a", "party_b"]

        for _ in range(count):
            party = random.choice(parties)
            behavior_profile = self.PARTY_BEHAVIOR_PROFILES.get(party, self.PARTY_BEHAVIOR_PROFILES["party_a"])

            # 根据场景状态调整权重
            adjusted_profile = self._adjust_weights(behavior_profile, context, party)

            # 随机选择行为
            action_type = self._weighted_choice(adjusted_profile)

            # 生成对手（仅交锋/撤出时有对手）
            opponent = None
            if action_type in ["engage", "withdraw", "support"]:
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
        readiness = context.get(f"{party}_readiness", 0.7)
        supply = context.get(f"{party}_supply", 0.7)
        capability_index = context.get(f"{party}_capability_index", 0.7)

        # 准备度低 -> 增加撤出概率
        if readiness < 0.4 and "withdraw" in adjusted:
            adjusted["withdraw"] = adjusted.get("withdraw", 0) * 2
        # 供给不足 -> 减少交锋概率
        if supply < 0.3 and "engage" in adjusted:
            adjusted["engage"] = adjusted.get("engage", 0) * 0.5
        # 能力强 -> 增加交锋概率
        if capability_index > 0.8 and "engage" in adjusted:
            adjusted["engage"] = adjusted.get("engage", 0) * 1.5

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
        weather = random.choice(self.WEATHER_CONDITIONS)
        time_period = random.choice(self.TIME_PERIODS)
        terrain = random.choice(self.TERRAIN_TYPES)
        equipment = random.choice(self.EQUIPMENT_TYPES)

        actor_names = self.UNIT_NAMES.get(actor_party, ["未知队伍"])
        actor_name = random.choice(actor_names)
        actor_id = f"unit-{actor_party}-{uuid.uuid4().hex[:6]}"

        # 随机生成单位属性
        unit_types = ["heavy_unit", "light_unit", "support_unit", "scout", "mobile", "air_unit", "armored_unit"]
        capability_index = round(random.uniform(0.4, 0.95), 2)
        readiness = round(random.uniform(0.5, 0.95), 2)
        resource_level = round(random.uniform(0.3, 0.90), 2)

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
                    "unit_type": random.choice(unit_types),
                    "equipment": equipment,
                    "time_period": time_period,
                    "weather": weather,
                },
                statistical_properties={
                    "capability_index": capability_index,
                    "readiness": readiness,
                    "resource_level": resource_level,
                    "attrition_rate": round(random.uniform(0.0, 0.15), 3),
                },
            )
        ]

        relations = []
        events = []
        actions = []

        event_type = self.ACTION_TO_EVENT.get(action_type, "generic")

        # 生成丰富的描述
        description_template = random.choice(self.ACTION_DESCRIPTIONS.get(action_type, ["执行{action_type}任务"]))
        outcome_template = random.choice(self.OUTCOME_DESCRIPTIONS.get(action_type, ["任务完成"]))
        target_count = random.randint(1, 5)

        if opponent_party:
            opp_names = self.UNIT_NAMES.get(opponent_party, ["未知队伍"])
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
                    "capability_index": round(random.uniform(0.4, 0.90), 2),
                    "readiness": round(random.uniform(0.5, 0.90), 2),
                    "resource_level": round(random.uniform(0.4, 0.90), 2),
                },
            ))

            rel_type_map = {
                "engage": "engaged_with",
                "support": "supports",
                "withdraw": "withdraws_from",
            }
            relations.append(OntologyRelation(
                relation_type=rel_type_map.get(action_type, "related_to"),
                source_entity=actor_id,
                target_entity=opp_id,
                temporal=TemporalInfo(start_time=now, is_current=True),
            ))

            # 使用模板生成描述
            description = description_template.format(
                opponent=opp_name,
                location=location,
                eqp=equipment,
                terrain=terrain,
                weather=weather
            ) + outcome_template.format(count=target_count)

            events.append(OntologyEvent(
                event_type=event_type,
                timestamp=now,
                location=location,
                participants=[actor_id, opp_id],
                description=description,
                outcome={
                    "terrain_control": random.choice(["disputed", "held", "lost"]),
                    "weather": weather,
                    "time_period": time_period,
                    "terrain": terrain,
                    "target_count": target_count,
                },
                phase=random.choice(["initial", "main", "final"]),
            ))
            actions.append(OntologyAction(
                action_type=action_type,
                actor=actor_id,
                target=opp_id,
                timestamp=now,
                parameters={
                    "mode": random.choice(["proactive", "cautious", "protective"]),
                    "equipment": equipment,
                    "weather": weather,
                },
                status=ActionStatus.EXECUTED.value,
            ))
        else:
            # 使用模板生成描述
            description = description_template.format(
                opponent="",
                location=location,
                eqp=equipment,
                terrain=terrain,
                weather=weather
            ) + outcome_template.format(count=target_count)

            events.append(OntologyEvent(
                event_type=event_type,
                timestamp=now,
                location=location,
                participants=[actor_id],
                description=description,
                outcome={
                    "weather": weather,
                    "time_period": time_period,
                    "terrain": terrain,
                },
                phase="active",
            ))

        title = f"[随机] {actor_name} - {action_type}"
        if use_llm and self.llm:
            description = await self._enrich_description(description)

        doc = OntologyDocument(
            doc_id=f"rand-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=SourceInfo(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=[actor_party, action_type, location, terrain, weather],
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
            prompt = f"请将以下事件描述扩展为1-2句更生动的叙述（保持事实）：{basic_desc}"
            if hasattr(self.llm, 'complete'):
                return await self.llm.complete(prompt)
        except Exception:
            pass
        return basic_desc
