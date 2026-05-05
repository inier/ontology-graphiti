"""
数据采集层 - 商业事件随机生成器
实现 ADR-031 L2: Data Ingestion & Normalization

BusinessEventGenerator: 商业事件生成器
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


class BusinessEventGenerator(BaseRandomGenerator):
    """商业事件生成器 - 生成商业场景下的各种事件"""

    GENERATOR_TYPE = "business"
    GENERATOR_NAME = "商业事件生成器"
    GENERATOR_DESCRIPTION = "生成商业场景下的各种事件，包括投资、并购、产品发布、市场变化等"

    # 商业事件类型
    BUSINESS_ACTIONS = [
        "investment", "acquisition", "merger", "product_launch",
        "market_expansion", "restructuring", "ipo", "partnership",
        "regulatory_change", "market_volatility", "partnership_dissolution",
        "market_entry", "market_exit"
    ]

    # 公司库
    COMPANIES = {
        "tech": [
            "科技创新集团", "数字先锋公司", "智能科技股份", "网络创新企业",
            "数据智能公司", "云端科技集团", "人工智能实验室", "软件巨头科技",
        ],
        "finance": [
            "华夏银行", "全球投资集团", "财富管理公司", "证券金融公司",
            "保险集团", "资产管理公司", "信托投资公司", "私募股权基金",
        ],
        "retail": [
            "零售巨头集团", "连锁超市股份", "电商平台公司", "购物中心集团",
            "品牌运营公司", "供应链管理企业", "物流配送公司", "跨境贸易集团",
        ],
        "manufacturing": [
            "重工业集团", "装备制造公司", "汽车制造企业", "电子产业集团",
            "新能源公司", "新材料科技", "化工产业股份", "精密制造企业",
        ],
    }

    # 地点库
    LOCATIONS = [
        "北京CBD", "上海陆家嘴", "深圳南山", "杭州西湖",
        "广州天河", "成都高新区", "武汉光谷", "西安高新区",
        "南京河西", "苏州工业园", "天津滨海", "重庆两江",
    ]

    # 事件描述模板
    EVENT_TEMPLATES = {
        "investment": [
            "{company}获得{amount}投资，用于{purpose}",
            "{company}完成{amount}融资，由{investor}领投",
            "{investor}向{company}投资{amount}",
        ],
        "acquisition": [
            "{company}收购{target}，交易金额{amount}",
            "{company}完成对{target}的收购，进军{industry}行业",
            "{target}被{company}以{amount}收购",
        ],
        "merger": [
            "{company}与{partner}合并，组建{new_company}",
            "{company}和{partner}宣布合并，市值达{amount}",
        ],
        "product_launch": [
            "{company}发布新产品{product}，定位{position}",
            "{company}推出{purpose}产品{product}",
            "{company}的新产品{product}正式上市",
        ],
        "market_expansion": [
            "{company}宣布进入{region}市场",
            "{company}在{region}开设首家门店",
            "{company}完成{region}市场的战略布局",
        ],
        "restructuring": [
            "{company}宣布重大战略重组",
            "{company}进行业务调整，聚焦{focus}",
            "{company}优化组织架构，提升效率",
        ],
        "ipo": [
            "{company}在{stock_market}上市，发行价{price}",
            "{company}IPO申请获批，即将登陆{stock_market}",
            "{company}成功上市，融资{amount}",
        ],
        "partnership": [
            "{company}与{partner}建立战略合作",
            "{company}和{partner}签署合作协议",
            "{company}与{partner}联合开发{product}",
        ],
        "partnership_dissolution": [
            "{company}与{partner}终止合作",
            "{company}和{partner}宣布解除合作关系",
            "{company}与{partner}的战略合作到期",
        ],
        "market_entry": [
            "{company}正式进入{industry}行业",
            "{company}在{location}成立新公司，布局{industry}",
            "{company}宣布进入{region}市场",
        ],
        "market_exit": [
            "{company}退出{region}市场",
            "{company}宣布战略收缩，退出{industry}业务",
            "{company}决定剥离{industry}板块",
        ],
        "regulatory_change": [
            "{industry}行业迎来新政策，{company}积极响应",
            "{region}出台{industry}监管新规",
            "监管变化影响{industry}，{company}调整策略",
        ],
        "market_volatility": [
            "{stock_market}波动，{company}股价{change}",
            "市场不确定性增加，{company}调整投资策略",
            "{stock_market}指数{change}，{industry}板块承压",
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
        """生成商业事件"""
        docs = []
        for _ in range(count):
            doc = await self._build_document(scenario_context, scenario_id)
            docs.append(doc)
        return docs

    async def _build_document(self, context: dict, scenario_id: str) -> OntologyDocument:
        """构建商业事件文档"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        action_type = random.choice(self.BUSINESS_ACTIONS)
        sector = random.choice(list(self.COMPANIES.keys()))
        company = random.choice(self.COMPANIES[sector])
        location = random.choice(self.LOCATIONS)

        company_id = f"company-{uuid.uuid4().hex[:6]}"

        amounts = ["1亿元", "5亿元", "10亿元", "50亿元", "100亿元", "500亿元"]
        amount = random.choice(amounts)

        other_sectors = [s for s in self.COMPANIES.keys() if s != sector]
        if other_sectors:
            target_sector = random.choice(other_sectors)
        else:
            target_sector = sector
        target = random.choice(self.COMPANIES[target_sector])
        partner = random.choice(self.COMPANIES[random.choice(list(self.COMPANIES.keys()))])

        investor = random.choice(self.COMPANIES[random.choice(list(self.COMPANIES.keys()))])

        products = ["智能平台", "解决方案", "创新产品", "生态系统", "服务平台"]
        product = random.choice(products)

        purposes = ["技术研发", "市场拓展", "产品创新", "团队建设", "产业升级"]
        purpose = random.choice(purposes)

        positions = ["高端市场", "中端市场", "大众市场", "细分市场"]
        position = random.choice(positions)

        focuses = ["核心业务", "技术创新", "数字化转型", "绿色发展"]
        focus = random.choice(focuses)

        regions = ["华东地区", "华南地区", "华北地区", "西部地区", "海外市场"]
        region = random.choice(regions)

        industries = ["科技", "金融", "制造", "零售", "医疗"]
        industry = random.choice(industries)

        stock_markets = ["上交所", "深交所", "港交所", "纽交所", "纳斯达克"]
        stock_market = random.choice(stock_markets)

        prices = ["10元", "20元", "50元", "100元", "200元"]
        price = random.choice(prices)

        changes = ["大幅上涨5%", "上涨3%", "小幅上涨1%", "下跌2%", "大幅下跌5%", "波动加剧"]
        change = random.choice(changes)

        new_companies = ["创新集团", "联合企业", "控股公司", "产业集团"]
        new_company = random.choice(new_companies)

        template = random.choice(self.EVENT_TEMPLATES.get(action_type, ["{company}完成{action_type}"]))
        description = template.format(
            company=company,
            target=target,
            partner=partner,
            investor=investor,
            amount=amount,
            product=product,
            purpose=purpose,
            position=position,
            region=region,
            industry=industry,
            stock_market=stock_market,
            price=price,
            change=change,
            new_company=new_company,
            focus=focus,
            location=location
        )

        title = f"[商业] {company} - {action_type}"

        doc = OntologyDocument(
            doc_id=f"biz-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=DataSource(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=[sector, action_type, location],
            ),
            entities=[
                OntologyEntity(
                    entity_id=company_id,
                    entity_type="Company",
                    name=company,
                    basic_properties={
                        "sector": sector,
                        "location": location,
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
                    outcome={"amount": amount, "status": "announced"},
                ),
            ],
            ontology_version=VersionRef(commit_message=f"商业事件: {company} {action_type}"),
            scenario_id=scenario_id,
        )
        return doc
