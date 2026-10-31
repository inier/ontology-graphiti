"""F7 意图评测集的业务词表与句式模板（数据部分，不含构建逻辑）。

词表取自真实零售 / 仓储 / 供应商协同语义；跨域用例刻意使用 USL 未覆盖的邻域术语，
使「泛化缺口」（AC-34）可度量。
"""

from __future__ import annotations

from typing import Dict, Iterable, List

# ── 业务词表（真实语义：零售 / 仓储 / 供应商协同）─────────────────────────────
#: (canonical, [surface…], 期望意图)
METRICS: List[tuple[str, List[str], str]] = [
    ("退货率", ["退货率", "退货比例", "退货占比"], "metric_query"),
    ("库存周转率", ["库存周转率", "存货周转率", "周转次数"], "metric_query"),
    ("履约率", ["履约率", "按时交付率", "交付达成率"], "metric_query"),
    ("客单价", ["客单价", "平均订单金额", "单均金额"], "metric_query"),
    ("缺货率", ["缺货率", "断货率"], "metric_query"),
    ("毛利率", ["毛利率", "毛利水平"], "metric_query"),
    ("销售额", ["销售额", "营收额"], "metric_query"),
]

OBJECTS: List[tuple[str, List[str]]] = [
    ("订单", ["订单", "交易单"]),
    ("供应商", ["供应商", "供货商", "厂商"]),
    ("品类", ["品类", "类目", "商品类别"]),
    ("仓库", ["仓库", "库房"]),
    ("门店", ["门店", "实体店"]),
]

ACTIONS: List[tuple[str, List[str]]] = [
    ("删除订单", ["删除订单", "清除订单"]),
    ("导出报表", ["导出报表", "导出数据"]),
    ("冻结供应商", ["冻结供应商"]),
    ("调整安全库存", ["调整安全库存"]),
    ("下发补货单", ["下发补货单", "生成补货单"]),
]

PROPERTIES: List[tuple[str, List[str]]] = [
    ("单价", ["单价", "商品单价"]),
    ("安全库存", ["安全库存"]),
    ("供应商等级", ["供应商等级"]),
    ("订单状态", ["订单状态"]),
]

PROCESSES: List[tuple[str, List[str]]] = [
    ("退货审批", ["退货审批", "退货审核"]),
    ("入库上架", ["入库上架"]),
    ("出库拣货", ["出库拣货", "拣货"]),
    ("结算对账", ["结算对账", "对账"]),
]

RULES: List[tuple[str, List[str]]] = [
    ("退货时限规则", ["退货时限规则"]),
    ("供应商准入规则", ["供应商准入规则"]),
    ("库存预警规则", ["库存预警规则"]),
]

TIMES = ["上季度", "本季度", "上个月", "本周", "2026Q3", "2026年9月", "近7天", "去年同期"]
REGIONS = ["华东区", "华南区", "华北区", "西南区"]
CHANNELS = ["线上", "线下", "自营店", "加盟店"]
DOMAINS = ["电商业务", "门店零售", "供应商协同", "仓储物流"]

METRIC_SURFACES = [(canonical, surf, intent)
                   for canonical, surfaces, intent in METRICS for surf in surfaces]

#: USL 未覆盖的"邻域词"—— 正确系统应理解其意图，L1 词典必然未命中
UNSEEN_DOMAIN_TERMS: List[tuple[str, str]] = [
    ("动销率", "metric_query"),
    ("售罄率", "metric_query"),
    ("滞销率", "metric_query"),
    ("存销比", "metric_query"),
    ("库销比", "metric_query"),
    ("资金周转率", "metric_query"),
    ("坪效", "metric_query"),
    ("人效", "metric_query"),
    ("退货处理时长", "metric_query"),
    ("供应商协同评分", "metric_query"),
    ("订单履约成本", "metric_query"),
    ("仓容利用率", "metric_query"),
    ("二次销售率", "metric_query"),
    ("缺货天数", "metric_query"),
    ("安全库存水位", "property_lookup"),
    ("供应商结算账期", "property_lookup"),
    ("拣货路径", "process_lookup"),
    ("退货质检环节", "process_lookup"),
    ("供应商淘汰机制", "rule_lookup"),
    ("补货触发条件", "rule_lookup"),
]

# ── 句式模板 ────────────────────────────────────────────────────────────────
SYN_TEMPLATES = [
    "{t}{r}{s}是多少",
    "帮我查一下{r}{t}的{s}",
    "{t}{s}怎么样",
    "看一下{t}{s}的变化趋势",
    "{c}渠道{t}{s}如何",
    "{t}{r}{s}同比情况",
    "{s}在{t}的表现如何",
    "统计{t}{r}的{s}",
    "我要看{t}{s}",
    "{t}{r}{s}环比上升了吗",
    "帮我算下{t}{s}",
    "{t}{c}{s}排名前十的是哪些",
    "{s}最近怎么样",
    "{r}的{s}是多少",
]

CROSS_TEMPLATES = [
    "{d}里{s}怎么算",
    "{d}关注的{s}最近怎么样",
    "{d}看板上的{s}是多少",
    "{t}{d}的{s}",
    "{d}这块{s}有没有变化",
    "{d}场景下{t}{s}大概多少",
]

#: 已覆盖词在"别的域"里使用（应正常命中）
COVERED_CROSS_TEMPLATES = [
    "{d}的{c}{s}{t}是多少",
    "{d}里供应商的{s}{t}怎么样",
    "{d}场景下{t}{c}{s}排名",
]

#: (连接词, 附加诉求模板, 附加诉求是否为动作)
COMPOSITE_TAILS: List[tuple[str, str, bool]] = [
    ("然后", "{a}", True),
    ("并且", "{a}", True),
    ("同时", "{a}", True),
    ("顺便", "{a}", True),
    ("还要看", "{o}的{p}", False),
    ("并且对比", "{o}的{p}", False),
    ("同时关注", "{pr}", False),
    ("再确认", "{ru}", False),
]

#: 域外问题（任何业务域都不该接）
OUT_OF_SCOPE = [
    "今天食堂有什么菜",
    "帮我订一张去上海的机票",
    "这个月的社保基数调整了吗",
    "员工报销流程怎么走",
    "公司停车位怎么申请",
    "明天团建几点集合",
    "帮我把这份简历投递到招聘网站",
    "服务器机房的温度是不是太高了",
    "这个季度的团建预算还剩多少",
    "怎么修改登录密码",
]

#: 域内近似但无术语可命中（应澄清，不应强行给数）
NEAR_MISS = [
    "单据怎么打印",
    "那张纸质凭证放哪了",
    "这批货的物流单号是多少",
    "合作的第三方联系人电话是多少",
    "地下储物间的门禁卡在哪领",
    "电子发票怎么开",
    "结算清单什么时候寄出",
    "货架上的标签谁负责换",
    "茶水间的咖啡机坏了找谁修",
    "这份合同的法务审核到哪一步了",
    "下周的值班表排好了吗",
    "新同事的门禁权限开通了吗",
    "打印机卡纸了怎么处理",
    "年度体检什么时候安排",
    "这个月的团建活动去哪",
]


def make_case(cid: str, category: str, query: str, intent: str,
              terms: Iterable[str]) -> Dict[str, object]:
    """统一的用例结构（`expected_terms` 记录构造时真实使用的表面形式）。"""
    return {
        "id": cid,
        "category": category,
        "query": query,
        "expected_intent": intent,
        "expected_terms": list(terms),
    }


__all__ = [
    "ACTIONS",
    "CHANNELS",
    "COMPOSITE_TAILS",
    "COVERED_CROSS_TEMPLATES",
    "CROSS_TEMPLATES",
    "DOMAINS",
    "METRICS",
    "METRIC_SURFACES",
    "NEAR_MISS",
    "OBJECTS",
    "OUT_OF_SCOPE",
    "PROCESSES",
    "PROPERTIES",
    "REGIONS",
    "RULES",
    "SYN_TEMPLATES",
    "TIMES",
    "UNSEEN_DOMAIN_TERMS",
    "make_case",
]
