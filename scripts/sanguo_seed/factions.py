"""三国演义势力数据 — 魏/蜀/吴 + 群雄 + 晋"""

FACTIONS = [
    {
        "faction_id": "faction_wei",
        "name": "魏",
        "full_name": "曹魏",
        "founder": "cao_cao",
        "capital": "xuchang",
        "established_year": 220,
        "ended_year": 265,
        "color": "#4A90D9",
        "description": "曹操奠基，曹丕代汉称帝，占据中原九州，国力最强。推行屯田制，唯才是举，文治武功兼备。",
    },
    {
        "faction_id": "faction_shu",
        "name": "蜀",
        "full_name": "蜀汉",
        "founder": "liu_bei",
        "capital": "chengdu",
        "established_year": 221,
        "ended_year": 263,
        "color": "#5CB85C",
        "description": "刘备以汉室宗亲自居，续汉正统。据益州险要，以仁义立国，诸葛亮治蜀有方，然国力最弱。",
    },
    {
        "faction_id": "faction_wu",
        "name": "吴",
        "full_name": "东吴",
        "founder": "sun_jian",
        "capital": "jianye",
        "established_year": 229,
        "ended_year": 280,
        "color": "#D9534F",
        "description": "孙氏三代经营江东，依长江天险，水军天下无双。孙权称帝后偏安江南，国祚最久。",
    },
    {
        "faction_id": "faction_qunxiong",
        "name": "群雄",
        "full_name": "汉末群雄",
        "founder": None,
        "capital": None,
        "established_year": 184,
        "ended_year": 200,
        "color": "#F0AD4E",
        "description": "黄巾之乱后各路诸侯割据一方，包括董卓、袁绍、袁术、吕布、刘表、公孙瓒等，最终被曹操等逐一消灭。",
    },
    {
        "faction_id": "faction_jin",
        "name": "晋",
        "full_name": "西晋",
        "founder": "sima_zhao",
        "capital": "luoyang",
        "established_year": 265,
        "ended_year": 316,
        "color": "#9B59B6",
        "description": "司马氏经高平陵之变夺取曹魏大权，司马炎代魏建晋，先后灭蜀灭吴，统一天下。",
    },
]


def get_faction(faction_id: str) -> dict | None:
    """根据 faction_id 获取势力信息"""
    for faction in FACTIONS:
        if faction["faction_id"] == faction_id:
            return faction
    return None
