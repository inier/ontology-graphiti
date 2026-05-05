"""
数据采集层 - 科技事件随机生成器
实现 ADR-031 L2: Data Ingestion & Normalization

TechEventGenerator: 科技事件生成器
"""

import random
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.biz.ontology.ingestion_split.base_generator import BaseRandomGenerator
from odap.biz.ontology.schema.document import (
    OntologyDocument, OntologyEntity, OntologyEvent,
    VersionRef, DataSource, DocumentMeta, SourceType, DocType,
)

logger = logging.getLogger("data_ingestion")


class TechEventGenerator(BaseRandomGenerator):
    """科技事件生成器 - 生成科技领域的事件"""

    GENERATOR_TYPE = "tech"
    GENERATOR_NAME = "科技事件生成器"
    GENERATOR_DESCRIPTION = "生成科技领域的事件，包括技术突破、产品发布、融资、学术成果等"

    TECH_ACTIONS = [
        "breakthrough", "product_launch", "research", "patent",
        "launch", "collaboration", "award", "funding",
        "expansion", "launch_failure", "data_breach", "partnership"
    ]

    TECH_COMPANIES = [
        "未来科技", "智能创新", "量子实验室", "生物科技公司",
        "新能源技术", "量子计算中心", "AI研究院", "机器人公司",
        "元宇宙科技", "区块链实验室", "云计算中心", "大数据公司",
        "5G创新中心", "芯片设计公司", "自动驾驶研究院", "无人机技术公司",
    ]

    RESEARCH_AREAS = [
        "人工智能", "量子计算", "生物医药", "新能源", "材料科学",
        "航空航天", "深海探测", "脑科学", "基因编辑", "机器人",
    ]

    LOCATIONS = [
        "北京中关村", "上海张江", "深圳南山", "杭州云栖",
        "武汉光谷", "成都天府", "西安高新", "苏州工业园",
    ]

    EVENT_TEMPLATES = {
        "breakthrough": [
            "{company}在{area}领域取得重大突破",
            "{company}宣布{area}研究获得突破性进展",
            "{area}领域传来好消息，{company}实现技术跨越",
        ],
        "product_launch": [
            "{company}发布新一代{product}",
            "{company}的{product}正式亮相",
            "{company}推出革命性产品{product}",
        ],
        "research": [
            "{company}启动{area}研究计划",
            "{company}与高校合作开展{area}研究",
            "{company}在{area}领域发表重要论文",
        ],
        "patent": [
            "{company}获得{area}技术专利",
            "{company}申请的新专利获批",
            "{company}在{area}领域专利布局加速",
        ],
        "award": [
            "{company}荣获{award}奖项",
            "{company}的{product}获得国际认可",
            "{company}团队因{area}研究获奖",
        ],
        "funding": [
            "{company}完成{amount}融资",
            "{company}获得{amount}投资",
            "{company}估值达{amount}",
        ],
        "expansion": [
            "{company}成立海外研发中心",
            "{company}在{location}建立研究基地",
            "{company}业务扩展至{area}",
        ],
        "partnership": [
            "{company}与{partner}建立战略合作",
            "{company}与{partner}联合开发{product}",
            "{company}与科研机构合作研究{area}",
        ],
        "launch": [
            "{company}推出全新{product}",
            "{company}在{location}发布{product}",
            "{company}的新产品{product}正式上线",
        ],
        "collaboration": [
            "{company}与{partner}开展深度合作",
            "{company}联合{partner}共同研发{product}",
            "{company}与{partner}在{area}领域达成合作",
        ],
        "launch_failure": [
            "{company}的{product}遭遇挫折",
            "{company}发布的{product}面临技术挑战",
            "{company}在{product}研发中遇到问题",
        ],
        "data_breach": [
            "{company}发生数据安全事件",
            "{company}加强数据安全措施",
            "{company}在{area}领域完善数据保护",
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
        """生成科技事件"""
        docs = []
        for _ in range(count):
            doc = await self._build_document(scenario_context, scenario_id)
            docs.append(doc)
        return docs

    async def _build_document(self, context: dict, scenario_id: str) -> OntologyDocument:
        """构建科技事件文档"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        action_type = random.choice(self.TECH_ACTIONS)
        company = random.choice(self.TECH_COMPANIES)
        location = random.choice(self.LOCATIONS)
        area = random.choice(self.RESEARCH_AREAS)

        company_id = f"tech-{uuid.uuid4().hex[:6]}"

        amounts = ["1000万元", "5000万元", "1亿元", "5亿元", "10亿元", "20亿元"]
        amount = random.choice(amounts)

        partners = ["清华大学", "北京大学", "中科院", "华为", "阿里达摩院", "腾讯AI Lab"]
        partner = random.choice(partners)

        products = ["智能平台", "AI芯片", "量子计算机", "机器人", "无人机", "操作系统"]
        product = random.choice(products)

        awards = ["科技进步一等奖", "最佳创新奖", "国际设计大奖", "技术突破奖"]
        award = random.choice(awards)

        template = random.choice(self.EVENT_TEMPLATES.get(action_type, ["{company}完成{action_type}"]))
        description = template.format(
            company=company,
            partner=partner,
            amount=amount,
            area=area,
            product=product,
            award=award,
            location=location,
        )

        title = f"[科技] {company} - {action_type}"

        doc = OntologyDocument(
            doc_id=f"tech-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=DataSource(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=["科技", action_type, area],
            ),
            entities=[
                OntologyEntity(
                    entity_id=company_id,
                    entity_type="TechCompany",
                    name=company,
                    basic_properties={
                        "sector": "technology",
                        "location": location,
                        "research_area": area,
                    },
                ),
            ],
            events=[
                OntologyEvent(
                    event_type=action_type,
                    timestamp=now,
                    location=location,
                    participants=[company_id],
                    description=description,
                    outcome={"research_area": area, "status": "announced"},
                ),
            ],
            ontology_version=VersionRef(commit_message=f"科技事件: {company} {action_type}"),
            scenario_id=scenario_id,
        )
        return doc
