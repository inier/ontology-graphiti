"""西游记人物关系数据"""

RELATIONSHIPS = [
    # === 取经团队 ===
    {
        "rel_id": "rel_x001",
        "type": "师徒",
        "from": "唐僧",
        "to": "孙悟空",
        "description": "唐僧收孙悟空为大徒弟",
    },
    {
        "rel_id": "rel_x002",
        "type": "师徒",
        "from": "唐僧",
        "to": "猪八戒",
        "description": "唐僧收猪八戒为二徒弟",
    },
    {
        "rel_id": "rel_x003",
        "type": "师徒",
        "from": "唐僧",
        "to": "沙僧",
        "description": "唐僧收沙僧为三徒弟",
    },
    {
        "rel_id": "rel_x004",
        "type": "师徒",
        "from": "唐僧",
        "to": "白龙马",
        "description": "白龙化作白马为唐僧坐骑，暗为弟子",
    },

    # === 结拜关系 ===
    {
        "rel_id": "rel_x005",
        "type": "结拜",
        "from": "孙悟空",
        "to": "牛魔王",
        "description": "七大圣结拜，牛魔王为大哥，孙悟空排行老七",
    },

    # === 敌对关系 ===
    {
        "rel_id": "rel_x006",
        "type": "敌对",
        "from": "孙悟空",
        "to": "牛魔王",
        "description": "火焰山因借扇结仇，灵山围剿牛魔王",
    },
    {
        "rel_id": "rel_x007",
        "type": "敌对",
        "from": "孙悟空",
        "to": "白骨精",
        "description": "三打白骨精，除恶务尽",
    },
    {
        "rel_id": "rel_x008",
        "type": "敌对",
        "from": "孙悟空",
        "to": "红孩儿",
        "description": "红孩儿用三昧真火烧伤悟空，后被观音收服",
    },

    # === 降伏关系 ===
    {
        "rel_id": "rel_x009",
        "type": "降伏",
        "from": "如来佛祖",
        "to": "孙悟空",
        "description": "如来降伏大闹天宫的美猴王，压于五行山下",
    },
    {
        "rel_id": "rel_x010",
        "type": "降伏",
        "from": "观音菩萨",
        "to": "红孩儿",
        "description": "观音以净瓶收服红孩儿为善财童子",
    },
    {
        "rel_id": "rel_x011",
        "type": "降伏",
        "from": "弥勒佛",
        "to": "黄眉老佛",
        "description": "弥勒佛收服下凡为妖的座下童子",
    },
    {
        "rel_id": "rel_x012",
        "type": "降伏",
        "from": "观音菩萨",
        "to": "黑熊精",
        "description": "观音收服黑熊精为守山大神",
    },

    # === 隶属关系 ===
    {
        "rel_id": "rel_x013",
        "type": "隶属",
        "from": "玉皇大帝",
        "to": "天庭",
        "description": "玉帝为天庭之主",
    },
    {
        "rel_id": "rel_x014",
        "type": "隶属",
        "from": "如来佛祖",
        "to": "佛门",
        "description": "如来为西天佛祖",
    },
    {
        "rel_id": "rel_x015",
        "type": "隶属",
        "from": "观音菩萨",
        "to": "佛门",
        "description": "观音为佛门菩萨，奉如来之命",
    },
    {
        "rel_id": "rel_x016",
        "type": "隶属",
        "from": "哪吒",
        "to": "天庭",
        "description": "哪吒为天庭战将",
    },
    {
        "rel_id": "rel_x017",
        "type": "隶属",
        "from": "二郎神",
        "to": "天庭",
        "description": "二郎神为天庭战将",
    },
    {
        "rel_id": "rel_x018",
        "type": "隶属",
        "from": "牛魔王",
        "to": "妖界",
        "description": "牛魔王为七大圣之首，妖魔首领",
    },
    {
        "rel_id": "rel_x019",
        "type": "隶属",
        "from": "白骨精",
        "to": "妖界",
        "description": "白骨精为白虎岭尸妖",
    },

    # === 师徒（非取经团队）===
    {
        "rel_id": "rel_x020",
        "type": "师徒",
        "from": "菩提祖师",
        "to": "孙悟空",
        "description": "菩提祖师传授孙悟空七十二变和筋斗云",
    },
    {
        "rel_id": "rel_x021",
        "type": "师徒",
        "from": "太上老君",
        "to": "金角大王",
        "description": "金角大王原为太上老君看炉童子",
    },
    {
        "rel_id": "rel_x022",
        "type": "师徒",
        "from": "太上老君",
        "to": "银角大王",
        "description": "银角大王原为太上老君看炉童子",
    },

    # === 家庭关系 ===
    {
        "rel_id": "rel_x023",
        "type": "隶属",
        "from": "铁扇公主",
        "to": "妖界",
        "description": "牛魔王之妻，翠云山芭蕉洞之主",
    },
    {
        "rel_id": "rel_x024",
        "type": "隶属",
        "from": "红孩儿",
        "to": "妖界",
        "description": "牛魔王与铁扇公主之子",
    },

    # === 持有关系 ===
    {
        "rel_id": "rel_x025",
        "type": "持有",
        "from": "孙悟空",
        "to": "金箍棒",
        "description": "悟空从东海龙宫取得如意金箍棒",
    },
    {
        "rel_id": "rel_x026",
        "type": "持有",
        "from": "猪八戒",
        "to": "九齿钉耙",
        "description": "八戒随身的九齿钉耙",
    },
    {
        "rel_id": "rel_x027",
        "type": "持有",
        "from": "铁扇公主",
        "to": "芭蕉扇",
        "description": "铁扇公主的芭蕉扇",
    },
    {
        "rel_id": "rel_x028",
        "type": "持有",
        "from": "黄眉老佛",
        "to": "人种袋",
        "description": "从弥勒佛处盗得的人种袋",
    },
    {
        "rel_id": "rel_x029",
        "type": "持有",
        "from": "唐僧",
        "to": "紧箍咒",
        "description": "观音赐唐僧用于约束孙悟空的紧箍咒",
    },
    {
        "rel_id": "rel_x030",
        "type": "持有",
        "from": "沙僧",
        "to": "降妖宝杖",
        "description": "沙僧随身的降妖宝杖",
    },
]
