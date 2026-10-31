"""L2 形态学召回：从「未见过的领域名词」推断意图类别（无向量方案的核心）。

为什么需要它：USL 词典只能覆盖已登记术语。跨域迁移时用户会用词典里没有的说法
（动销率 / 仓容利用率 / 补货触发条件 …）。中文业务名词的**构词后缀**携带稳定的
语义类别信号——`率/额/比/成本/天数` 属指标，`水位/账期/等级` 属属性，
`路径/环节/流程` 属过程，`机制/条件/规则` 属规则。

判定纪律（防误报，比召回更重要）：
1. 后缀必须**紧邻**名词右边界（`动销率` 命中，`基数调整了吗` 不命中）；
2. 名词左侧遇到边界字（的/里/上/和/，…）即截断，保证槽位边界不吞掉修饰语；
3. 问句形态门槛：后缀之后必须是空串或**明确的指标/属性问法**（是多少/怎么算/怎么样/
   有没有变化…）。`社保基数调整了吗` 这类「含后缀词但不是数据问句」的域外问题必须
   保持不命中——干扰项识别比多捞一条更重要。

本模块只做形态判断，不查词典、不发网络请求。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

#: 指标类后缀（长后缀在前，匹配时优先取最长）
METRIC_CUES: Tuple[str, ...] = (
    "利用率", "周转率", "达成率", "完成率", "覆盖率", "退货率",
    "时长", "成本", "评分", "天数", "指数", "系数", "均值", "占比", "总额",
    "率", "额", "比", "量", "价", "效", "数",
)

#: 弱后缀：在行政/HR/IT 语境里同样常见（年假天数、社保基数、文件数量），
#: 必须同时出现业务域词才认作业务指标，否则会把域外问题当数据问句。
WEAK_CUES: Tuple[str, ...] = ("数", "量", "天数")

#: 业务域词（出现即说明该名词属于本体覆盖的业务域）
BUSINESS_TOKENS: Tuple[str, ...] = (
    "订单", "退货", "退款", "库存", "供应商", "品类", "仓库", "库房", "门店",
    "采购", "促销", "销售", "毛利", "净利", "履约", "交付", "周转", "补货",
    "拣货", "出库", "入库", "对账", "结算", "账期", "客户", "商品", "货物",
    "仓容", "动销", "售罄", "滞销", "存销", "库销", "资金", "调拨", "渠道",
    "平台", "电商", "供应链", "物流", "售后", "质检", "会员", "积分", "优惠券",
    "成本", "价格", "报价", "折扣", "达成", "缺货", "断货", "进销", "毛利",
)

#: 属性类后缀
PROPERTY_CUES: Tuple[str, ...] = ("水位", "账期", "等级", "状态", "口径")

#: 过程类后缀
PROCESS_CUES: Tuple[str, ...] = ("路径", "环节", "流程", "工序", "步骤", "动作")

#: 规则类后缀
RULE_CUES: Tuple[str, ...] = ("机制", "条件", "规则", "阈值", "红线")

_CUE_TABLE: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("metric_query", METRIC_CUES),
    ("property_lookup", PROPERTY_CUES),
    ("process_lookup", PROCESS_CUES),
    ("rule_lookup", RULE_CUES),
)

#: 名词左边界（遇到即截断，避免把「华东区本季度」并进名词）
BOUNDARY_CHARS = set(
    "的了是在和与及跟对把让被给从向于这那个些们你我他她它们"
    "里上下中内外前后间到去来都也还很更最不没要会能可请帮"
    "块侧端面"
    "，。！？；：、（）()【】[]{}· 　\t\n0123456789"
)

#: 出现在后缀位置但其实是**比较修饰语**的组合（同比/环比），不能当作术语后缀
_MODIFIER_PREFIXES = ("同", "环")

#: 问法前允许出现的时间副词（「最近怎么样」「目前如何」）
TEMPORAL_PREFIXES: Tuple[str, ...] = (
    "最近", "近期", "目前", "现在", "当前", "近来", "这段时间", "这周", "本周", "上周",
    "这个月", "本月", "上个月", "今年", "去年",
)

#: 后缀之后允许的问法（显式白名单：宁可漏召回，不可把陈述/域外问题当数据问句）
#: 只收「要数据/要口径」的形态，不放裸「怎么」——否则「报销流程怎么走」这类域外问题
#: 会被误判成过程查询。命中位置不要求在紧邻处：`利用率还有多少空间` 也要算。
QUESTION_MARKERS: Tuple[str, ...] = (
    "是多少", "有多少", "多少", "怎么样", "怎么算", "怎么看", "如何",
    "有没有", "有变化", "什么趋势", "趋势", "走势", "情况", "排名", "排行", "同比", "环比",
    "大概", "几何", "是什么", "表现", "变化", "对比", "水平", "超过", "低于", "高于",
    "大于", "小于", "达到", "分别是", "有哪些", "几成", "几天", "几次", "最高", "最低",
    "占比", "空间", "多久", "多长", "以内", "以上", "以下", "几个", "几人",
)

#: 宽松问法：只在**名词本身含业务域词**时才认（`拣货路径怎么优化` 要召回，
#: `报销流程怎么走` 不召回）。这条是「跨域召回」与「干扰项不误报」的分界线。
LENIENT_MARKERS: Tuple[str, ...] = ("怎么", "如何做", "该怎么做")

#: 「比」出现在这些字前面时是介词（比去年/比上周），不是名词后缀
_PREPOSITION_FOLLOWERS = ("去", "上", "同", "前", "本", "今", "之", "环")

#: 名词最大长度（中文业务名词极少超过 8 字）
MAX_TERM_CHARS = 8
#: 名词最小长度（含后缀）：单字后缀至少要有 1 个前缀字，双字后缀同理
MIN_PREFIX_CHARS = 1


@dataclass(frozen=True)
class CueSpan:
    """形态召回结果（槽位级别的名词短语）。"""

    surface: str
    intent: str
    cue: str
    start: int
    end: int

    @property
    def score(self) -> float:
        """形态证据的置信分（低于词典精确匹配，高于模糊匹配）。"""
        return 0.91 if self.intent == "metric_query" else 0.88


def _rest_is_question(rest: str, surface: str = "") -> bool:
    text = rest.strip()
    if not text:
        return True  # 裸名词短语问句（「电商业务的动销率」）
    for prefix in TEMPORAL_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    if not text:
        return False
    if any(marker in text for marker in QUESTION_MARKERS):
        return True
    return _has_business_token(surface) and any(m in text for m in LENIENT_MARKERS)


def _left_boundary(text: str, cue_start: int) -> int:
    index = cue_start
    while index > 0 and (cue_start - (index - 1)) <= MAX_TERM_CHARS:
        char = text[index - 1]
        if char in BOUNDARY_CHARS:
            break
        index -= 1
    return index


def _has_business_token(surface: str) -> bool:
    return any(token in surface for token in BUSINESS_TOKENS)


def _is_business_noun(surface: str, cue: str) -> bool:
    """弱后缀必须带业务域词才算业务指标（挡住「年假天数」「社保基数」这类域外问句）。"""
    if cue not in WEAK_CUES:
        return True
    return _has_business_token(surface)


def extract_cue_spans(text: str) -> List[CueSpan]:
    """扫出所有「后缀名词 + 问法」的槽位（同一 span 只保留最具体的一个）。"""
    source = text or ""
    found: List[CueSpan] = []
    occupied: List[Tuple[int, int]] = []
    for intent, cues in _CUE_TABLE:
        for cue in cues:
            start_at = 0
            while True:
                hit = source.find(cue, start_at)
                if hit < 0:
                    break
                start_at = hit + len(cue)
                end = hit + len(cue)
                if cue == "比" and hit > 0 and source[hit - 1] in _MODIFIER_PREFIXES:
                    continue  # 同比 / 环比：修饰语，不是术语后缀
                if cue == "比" and end < len(source) and source[end] in _PREPOSITION_FOLLOWERS:
                    continue  # 比去年 / 比上周：介词，不是后缀
                left = _left_boundary(source, hit)
                if hit - left < MIN_PREFIX_CHARS:
                    continue
                surface = source[left:end]
                if not _rest_is_question(source[end:], surface):
                    continue
                if not _is_business_noun(surface, cue):
                    continue
                span = (left, end)
                if any(span[0] >= s and span[1] <= e for s, e in occupied):
                    continue
                occupied.append(span)
                found.append(CueSpan(surface=surface, intent=intent, cue=cue,
                                     start=left, end=end))
    found.sort(key=lambda c: (c.start, -(c.end - c.start)))
    return found


__all__ = [
    "BOUNDARY_CHARS",
    "CueSpan",
    "METRIC_CUES",
    "PROCESS_CUES",
    "PROPERTY_CUES",
    "QUESTION_MARKERS",
    "RULE_CUES",
    "extract_cue_spans",
]
