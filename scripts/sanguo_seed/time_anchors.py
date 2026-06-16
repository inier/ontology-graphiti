"""三国演义时间锚点定义 — 6个关键时间节点"""

TIME_ANCHORS = [
    {
        "anchor_id": "anchor_184",
        "year": 184,
        "title": "黄巾之乱",
        "phase": "乱世开端",
        "summary": "张角率黄巾军起事，天下大乱，群雄并起。刘关张桃园结义，曹操起兵讨贼，三国故事由此拉开序幕。",
        "key_events": ["event_huangjin_qiyi", "event_taoyuan_jieyi"],
        "characters_introduced": ["liu_bei", "guan_yu", "zhang_fei", "zhang_jiao", "cao_cao"],
    },
    {
        "anchor_id": "anchor_190",
        "year": 190,
        "title": "讨董联盟",
        "phase": "群雄割据",
        "summary": "董卓入京把持朝政，十八路诸侯联合讨董。虎牢关三英战吕布，各路英雄崭露头角，割据之势已成。",
        "key_events": ["event_taodong_lianmeng", "event_hulao_guan_zhizhan"],
        "characters_introduced": ["dong_zhuo", "lu_bu", "yuan_shao"],
    },
    {
        "anchor_id": "anchor_200",
        "year": 200,
        "title": "官渡之战",
        "phase": "北方统一",
        "summary": "曹操以少胜多击败袁绍，统一北方。郭嘉遗计定辽东，奠定曹魏基业。",
        "key_events": ["event_guandu_zhizhan"],
        "characters_introduced": ["yuan_shao"],
    },
    {
        "anchor_id": "anchor_208",
        "year": 208,
        "title": "赤壁之战",
        "phase": "三分天下",
        "summary": "诸葛亮隆中对规划天下三分，孙刘联军赤壁大败曹操，三分格局初成。",
        "key_events": ["event_chibi_zhizhan", "event_longzhong_dui"],
        "characters_introduced": ["zhou_yu", "zhuge_liang", "sun_quan"],
    },
    {
        "anchor_id": "anchor_220",
        "year": 220,
        "title": "三国鼎立",
        "phase": "三国鼎立",
        "summary": "曹丕代汉称帝，刘备续汉称帝，孙权称帝，三国正式鼎立。",
        "key_events": ["event_caopi_daihan", "event_liu_bei_chengdi", "event_sun_quan_chengdi"],
        "characters_introduced": ["cao_pi"],
    },
    {
        "anchor_id": "anchor_263",
        "year": 263,
        "title": "三分归晋",
        "phase": "统一归晋",
        "summary": "司马氏代魏，蜀汉灭亡，最终西晋灭吴，天下归一。",
        "key_events": ["event_shu_han_miewang"],
        "characters_introduced": ["jiang_wei", "sima_zhao"],
    },
]


def get_time_anchor(anchor_id: str) -> dict | None:
    """根据 anchor_id 获取时间锚点"""
    for anchor in TIME_ANCHORS:
        if anchor["anchor_id"] == anchor_id:
            return anchor
    return None


def get_time_anchor_by_year(year: int) -> dict | None:
    """根据年份获取最近的时间锚点"""
    for anchor in TIME_ANCHORS:
        if anchor["year"] == year:
            return anchor
    return None
