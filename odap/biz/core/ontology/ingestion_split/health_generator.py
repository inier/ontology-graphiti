"""
数据采集层 - 医疗健康事件随机生成器
实现 ADR-031 L2: Data Ingestion & Normalization

HealthEventGenerator: 医疗健康事件生成器
"""

import random
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.ingestion_split.base_generator import BaseRandomGenerator
from odap.biz.core.ontology.schema.document import (
    OntologyDocument, OntologyEntity, OntologyEvent,
    VersionRef, SourceInfo, DocumentMeta, SourceType, DocType,
)


logger = logging.getLogger("data_ingestion")


class HealthEventGenerator(BaseRandomGenerator):
    """医疗健康事件生成器 - 生成医疗健康领域的事件"""

    GENERATOR_TYPE = "healthcare"
    GENERATOR_NAME = "医疗健康事件生成器"
    GENERATOR_DESCRIPTION = "生成医疗健康领域的事件，包括新药研发、临床试验、医疗突破等"

    HEALTH_ACTIONS = [
        "drug_approval", "clinical_trial", "breakthrough", "research",
        "device_approval", "outbreak", "vaccination", "treatment",
        "partnership", "funding", "merger", "recall"
    ]

    MEDICAL_INSTITUTIONS = [
        "仁和医院", "第一人民医院", "中心医院", "医药研究院",
        "生物制药公司", "医疗器械集团", "基因科技公司", "疫苗研发中心",
        "中医研究院", "专科医院集团", "体检中心", "康复医院",
    ]

    LOCATIONS = [
        "北京协和医院", "上海华山医院", "广州中山医院", "成都华西医院",
        "武汉同济医院", "南京鼓楼医院", "西安西京医院", "杭州浙一医院",
    ]

    DISEASES = [
        "癌症", "糖尿病", "心血管疾病", "阿尔茨海默症", "帕金森症",
        "艾滋病", "流感", "新冠肺炎", "肝炎", "肺炎",
    ]

    DRUGS = [
        "创新靶向药", "新型疫苗", "生物制剂", "基因疗法",
        "免疫治疗药物", "中药新药", "医疗器械", "诊断试剂",
    ]

    EVENT_TEMPLATES = {
        "drug_approval": [
            "{institution}的{drug}获得药监局批准上市",
            "{institution}研发的新药{drug}获批",
            "{drug}正式上市，用于治疗{disease}",
        ],
        "clinical_trial": [
            "{institution}启动{drug}临床试验",
            "{institution}开展{disease}新疗法临床试验",
            "{drug}的III期临床试验取得积极结果",
        ],
        "breakthrough": [
            "{institution}在{disease}治疗领域取得突破",
            "{institution}的{drug}显示显著疗效",
            "研究人员发现治疗{disease}的新方法",
        ],
        "research": [
            "{institution}开展{disease}研究",
            "{institution}发表{disease}研究论文",
            "{institution}在{research}领域取得进展",
        ],
        "device_approval": [
            "{institution}的医疗器械获批",
            "{institution}研发的新设备上市",
            "新型{therapy}设备获得认证",
        ],
        "outbreak": [
            "{location}爆发{disease}疫情",
            "{disease}疫情在{location}扩散",
            "{institution}报告{disease}病例增加",
        ],
        "vaccination": [
            "{institution}开展新疫苗接种工作",
            "{location}启动大规模疫苗接种",
            "{drug}疫苗接种率达标",
        ],
        "treatment": [
            "{institution}采用新疗法治疗{disease}",
            "{institution}成功实施{technique}手术",
            "新型{therapy}疗法在{disease}治疗中应用",
        ],
        "partnership": [
            "{institution}与{partner}合作研发新药",
            "{institution}与科研机构合作研究{disease}",
            "{institution}与{partner}建立医疗联盟",
        ],
        "funding": [
            "{institution}获得{amount}医疗研发资金",
            "{institution}的{research}项目获批资助",
            "{drug}研发项目融资{amount}",
        ],
        "merger": [
            "{institution}与{partner}合并",
            "医疗行业并购案：{institution}收购{partner}",
            "{institution}与{partner}达成战略合作",
        ],
        "recall": [
            "{institution}召回{drug}",
            "{institution}发布医疗器械召回公告",
            "{drug}因安全问题被召回",
        ],
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def get_generator_name(self) -> str:
        return self.GENERATOR_NAME

    def get_generator_description(self) -> str:
        return self.GENERATOR_DESCRIPTION

    async def generate(
        self,
        parties: List[str] = None,
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
    ) -> List[OntologyDocument]:
        """生成医疗健康事件"""
        docs = []
        for _ in range(count):
            doc = await self._build_document(scenario_context, scenario_id)
            docs.append(doc)
        return docs

    async def _build_document(self, context: dict, scenario_id: str) -> OntologyDocument:
        """构建医疗健康事件文档"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        action_type = random.choice(self.HEALTH_ACTIONS)
        institution = random.choice(self.MEDICAL_INSTITUTIONS)
        location = random.choice(self.LOCATIONS)
        disease = random.choice(self.DISEASES)
        drug = random.choice(self.DRUGS)

        institution_id = f"medical-{uuid.uuid4().hex[:6]}"

        amounts = ["1000万元", "5000万元", "1亿元", "5亿元", "10亿元"]
        amount = random.choice(amounts)

        partners = ["医学院", "研究所", "制药公司", "医疗器械厂", "疾控中心"]
        partner = random.choice(partners)

        techniques = ["机器人", "微创", "介入", "定向", "无创"]
        technique = random.choice(techniques)

        therapies = ["免疫治疗", "基因治疗", "细胞治疗", "靶向治疗"]
        therapy = random.choice(therapies)

        researches = ["新药研发", "临床试验", "精准医疗", "医疗器械"]
        research = random.choice(researches)

        template = random.choice(self.EVENT_TEMPLATES.get(action_type, ["{institution}完成{action_type}"]))
        description = template.format(
            institution=institution,
            partner=partner,
            amount=amount,
            disease=disease,
            drug=drug,
            location=location,
            technique=technique,
            therapy=therapy,
            research=research,
        )

        title = f"[医疗] {institution} - {action_type}"

        doc = OntologyDocument(
            doc_id=f"health-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=SourceInfo(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=["医疗", action_type, disease],
            ),
            entities=[
                OntologyEntity(
                    entity_id=institution_id,
                    entity_type="MedicalInstitution",
                    name=institution,
                    basic_properties={
                        "type": "hospital" if "医院" in institution else "research",
                        "location": location,
                    },
                ),
            ],
            events=[
                OntologyEvent(
                    event_type=action_type,
                    timestamp=now,
                    location=location,
                    participants=[institution_id],
                    description=description,
                    outcome={"disease": disease, "status": "announced"},
                ),
            ],
            ontology_version=VersionRef(commit_message=f"医疗事件: {institution} {action_type}"),
            scenario_id=scenario_id,
        )
        return doc
