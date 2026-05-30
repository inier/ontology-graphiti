"""
数据采集层 - 军事事件随机生成器
实现 ADR-031 L2: Data Ingestion & Normalization

RandomEventGenerator: 军事战争事件生成器
参考 NetLogo 多智能体行为概率模型
"""

import json
import uuid
import random
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.ingestion_split.base_generator import BaseRandomGenerator
from odap.biz.core.ontology.schema.document import (
    OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent,
    OntologyAction, VersionRef, SourceInfo, DocumentMeta, TemporalInfo,
    SourceType, DocType, EntityType, ActionStatus,
)

logger = logging.getLogger("data_ingestion")


class RandomEventGenerator(BaseRandomGenerator):
    """
    按涉事方和事件模板自动随机生成动态信息
    参考 NetLogo 多智能体随机行为模型:
    - 每个涉事方有行为概率表（patrol/attack/retreat/reinforce）
    - 基于当前状态（morale/supply/combat_power）权重调整
    - 事件输出符合 OntologyDocument 格式
    """

    # 生成器类型标识
    GENERATOR_TYPE = "military"
    GENERATOR_NAME = "军事战争事件生成器"
    GENERATOR_DESCRIPTION = "生成军事战争场景下的各种事件，包括进攻、巡逻、增援、撤退、侦察等行动"

    def get_generator_name(self) -> str:
        return self.GENERATOR_NAME

    def get_generator_description(self) -> str:
        return self.GENERATOR_DESCRIPTION

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
        "red": [
            "红方装甲营", "红方机步旅", "红方炮兵团", "红方特战队", "红方工兵营", "红方防空营",
            "红方摩步连", "红方陆航旅", "红方电子对抗营", "红方后勤保障团", "红方侦察营", "红方装甲团",
            "红方空降营", "红方装甲旅88旅", "红方合成营", "红方信息化作战单元",
        ],
        "blue": [
            "蓝方机步营", "蓝方装甲旅", "蓝方炮兵团", "蓝方海军陆战队", "蓝方工兵连", "蓝方防空连",
            "蓝方特种作战群", "蓝方空中突击营", "蓝方装甲骑兵团", "蓝方后勤支援旅", "蓝方电子战营", "蓝方炮兵旅",
            "蓝方机械化步兵师", "蓝方快速反应部队", "蓝方两栖作战营", "蓝方空中支援联队",
        ],
        "neutral": [
            "第三方观察团", "中立方协调员", "平民撤离队", "联合国维和部队", "人道主义救援组织",
            "国际红十字会代表", "当地平民志愿者", "记者团",
        ],
    }

    # 地点库
    LOCATIONS = [
        "A区北部高地", "B区遭遇地带", "C区渡口", "D区城镇",
        "E区山地走廊", "F区海岸线", "G区平原", "H区丛林",
        "K区桥梁枢纽", "L区铁路交叉点", "M区机场", "N区港口设施",
        "O区山区要塞", "P区沙漠地带", "Q区沼泽地带", "R区城市郊区",
        "108高地", "203号阵地", "莲花湖地区", "青河渡口", "龙山山口",
        "虎头山阵地", "白云机场", "红星港", "友谊桥", "中央平原",
    ]

    # 装备库
    EQUIPMENT_TYPES = [
        "99A式主战坦克", "96A式主战坦克", "15式轻型坦克",
        "04A式步战车", "86A式步战车", "08式步战车",
        "PLZ-05自行榴弹炮", "PLZ-07自行榴弹炮", "122毫米牵引炮",
        "AH-64阿帕奇", "Mi-28浩劫", "直-10武装直升机",
        "东风-11弹道导弹", "东风-15战术导弹", "红旗-9防空系统",
        "翼龙无人机", "彩虹无人机", "侦察无人机",
        "99式自行高炮", "04式弹炮合一系统", "09式轮式步战车",
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
        "attack": "contact",
        "patrol": "patrol",
        "reinforce": "reinforce",
        "retreat": "retreat",
        "recon": "recon",
        "evacuate": "evacuate",
        "report": "report",
        "cease_fire": "cease_fire",
    }

    # 行动描述模板
    ACTION_DESCRIPTIONS = {
        "attack": [
            "对{opponent}发起突然袭击，",
            "在{location}地区与{eqp}协同进攻{opponent}，",
            "使用无人机侦察后，对{opponent}发动精确打击，",
            "在{terrain}地形对{opponent}实施包围进攻，",
        ],
        "patrol": [
            "在{location}附近进行例行巡逻，",
            "对{terrain}地带进行搜索排查，",
            "在{eqp}掩护下对{location}实施巡逻，",
            "针对可疑目标进行定点巡逻，",
        ],
        "reinforce": [
            "增派{eqp}前往{location}支援，",
            "从后方调集预备队增援{location}，",
            "空中投送{eqp}至{location}，",
            "通过公路机动向{location}输送增援力量，",
        ],
        "retreat": [
            "因战略调整主动撤离{location}，",
            "在{eqp}掩护下有序撤退，",
            "受恶劣天气{weather}影响暂时后撤，",
            "完成阻击任务后主动撤出{location}，",
        ],
        "recon": [
            "派遣侦察分队前往{location}搜集情报，",
            "使用无人机对{terrain}地带实施抵近侦察，",
            "化装侦察员潜入{location}获取情报，",
            "电子侦察{location}区域的敌方通讯，",
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
            "情报部门汇总并上报{location}侦察结果，",
            "多方信息汇总后形成态势报告，",
        ],
        "cease_fire": [
            "根据停火协议在{location}停止军事行动，",
            "双方协商后在{terrain}地带实现停火，",
            "联合国调停后在{location}实施停火，",
            "暂时在{location}地区实行临时停火，",
        ],
    }

    # 结果描述
    OUTCOME_DESCRIPTIONS = {
        "attack": [
            "摧毁敌方{count}个目标",
            "造成敌方重大伤亡",
            "成功突破敌方防线",
            "占领关键阵地",
            "击退敌方进攻",
        ],
        "patrol": [
            "未发现异常情况",
            "发现可疑目标并标记",
            "确认区域安全",
            "搜集到有价值情报",
            "排除{count}处安全隐患",
        ],
        "reinforce": [
            "有效增强了防御力量",
            "及时补充了作战人员",
            "提升了整体战斗力",
            "巩固了防线",
            "扭转了不利局面",
        ],
        "retreat": [
            "成功保存了有生力量",
            "避免了更大损失",
            "撤至安全区域",
            "完成战略转移",
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

        if not parties:
            parties = ["red", "blue"]

        for _ in range(count):
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
        weather = random.choice(self.WEATHER_CONDITIONS)
        time_period = random.choice(self.TIME_PERIODS)
        terrain = random.choice(self.TERRAIN_TYPES)
        equipment = random.choice(self.EQUIPMENT_TYPES)

        actor_names = self.UNIT_NAMES.get(actor_party, ["未知部队"])
        actor_name = random.choice(actor_names)
        actor_id = f"unit-{actor_party}-{uuid.uuid4().hex[:6]}"

        # 随机生成单位属性
        unit_types = ["armor", "infantry", "artillery", "recon", "mechanized", "airborne", "armored"]
        combat_power = round(random.uniform(0.4, 0.95), 2)
        morale = round(random.uniform(0.5, 0.95), 2)
        supply_level = round(random.uniform(0.3, 0.90), 2)

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
                    "combat_power": combat_power,
                    "morale": morale,
                    "supply_level": supply_level,
                    "casualty_rate": round(random.uniform(0.0, 0.15), 3),
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
                    "terrain_control": random.choice(["contested", "held", "lost"]),
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
                    "mode": random.choice(["aggressive", "cautious", "defensive"]),
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
            prompt = f"请将以下军事事件描述扩展为1-2句更生动的叙述（保持事实）：{basic_desc}"
            if hasattr(self.llm, 'complete'):
                return await self.llm.complete(prompt)
        except Exception:
            pass
        return basic_desc
