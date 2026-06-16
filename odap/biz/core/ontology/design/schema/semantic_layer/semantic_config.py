"""
统一语义层配置

为三国演义和西游记两个领域提供：
1. 中英文映射表
2. 规范术语（canonical terms）
3. 同义词/近义词/别名
4. 扩展规则

所有后续本体建模均基于此语义层，避免歧义。
"""

# ============================================================
# 三国演义语义层
# ============================================================

SANGUO_SEMANTIC = {
    "domain": "sanguo",
    "display_name": "三国演义",
    "description": "基于罗贯中《三国演义》的领域语义定义",

    # --- 中英文映射 ---
    "en_mapping": {
        # 对象类型
        "势力": "Faction",
        "人物": "Character",
        "地点": "Location",
        "事件": "Event",
        "关系": "Relationship",
        "物品": "Artifact",
        "谋略": "Strategy",
        # 关系类型
        "效力于": "Serves",
        "结义": "SwornBrother",
        "联姻": "MarriedTo",
        "对峙": "RivalOf",
        "师徒": "MentorOf",
        "驻守于": "StationedAt",
        "控制": "Controls",
        "参与": "ParticipatedIn",
        "发生于": "OccurredAt",
        "持有": "WieldedBy",
        "设谋": "DevisedBy",
        # 动作类型
        "进军": "March",
        "交战": "Confrontation",
        "结盟": "Alliance",
        "施计": "UseStrategy",
        "登基": "Enthrone",
        "投降": "Surrender",
        # 属性
        "姓名": "Name",
        "字": "StyleName",
        "阵营": "Camp",
        "称号": "Title",
        "角色": "Role",
        "出生年": "BirthYear",
        "逝世年": "DeathYear",
        "籍贯": "Origin",
        "描述": "Description",
        "建立年": "EstablishedYear",
        "灭亡年": "EndedYear",
        "都城": "Capital",
        "建立者": "Founder",
        "年份": "Year",
        "月份": "Month",
        "类别": "Category",
        "区域": "Region",
        "今址": "ModernLocation",
        "类型": "Type",
    },

    # --- 规范术语 + 同义词/近义词/别名 ---
    "canonical_terms": {
        # 对象类型术语
        "势力": {
            "synonyms": ["阵营", "国家", "方", "朝", "国", "邦"],
            "near_synonyms": ["军团", "集团", "诸侯"],
            "aliases": ["三国势力", "阵营"],
        },
        "人物": {
            "synonyms": ["角色", "将军", "谋士", "君主", "人", "英雄"],
            "near_synonyms": ["将领", "武将", "文臣", "军师", "主公"],
            "aliases": ["三国人物", "英雄"],
        },
        "地点": {
            "synonyms": ["城池", "关隘", "州", "郡", "城", "关"],
            "near_synonyms": ["要塞", "险地", "重镇", "关口"],
            "aliases": ["三国地点", "地理"],
        },
        "事件": {
            "synonyms": ["冲突", "事件", "事变", "之变"],
            "near_synonyms": ["会战", "交锋", "交兵", "用兵"],
            "aliases": ["三国事件", "历史事件"],
        },
        "物品": {
            "synonyms": ["器具", "坐骑", "宝物"],
            "near_synonyms": ["设备", "名马", "神器"],
            "aliases": ["三国物品", "器具"],
        },
        "谋略": {
            "synonyms": ["计策", "兵法", "计谋", "奇谋", "妙计"],
            "near_synonyms": ["策略", "战法", "阵法", "韬略"],
            "aliases": ["三国谋略", "计策"],
        },
        # 关系类型术语
        "结义": {
            "synonyms": ["桃园结义", "义兄弟", "结拜"],
            "near_synonyms": ["兄弟", "义气"],
            "aliases": ["结义兄弟"],
        },
        "效力于": {
            "synonyms": ["归属", "投靠", "追随", "从属", "效力于"],
            "near_synonyms": ["归顺", "依附", "效忠"],
            "aliases": ["效力"],
        },
        "交战": {
            "synonyms": ["对垒", "交锋", "对峙", "大战"],
            "near_synonyms": ["攻伐", "征讨", "讨伐"],
            "aliases": ["交锋", "冲突"],
        },
        "进军": {
            "synonyms": ["出兵", "进军", "起兵", "挥军"],
            "near_synonyms": ["征伐", "讨伐", "攻伐"],
            "aliases": ["出征"],
        },
    },

    # --- 扩展规则 ---
    "expansion_rules": [
        {"pattern": "人物", "expansion": ["三国人物", "蜀汉人物", "曹魏人物", "东吴人物"]},
        {"pattern": "势力", "expansion": ["魏", "蜀", "吴", "群雄", "晋"]},
        {"pattern": "冲突", "expansion": ["官渡之战", "赤壁之战", "夷陵之战", "五丈原之战"]},
        {"pattern": "谋略", "expansion": ["空城计", "连环计", "苦肉计", "草船借箭"]},
    ],
}


# ============================================================
# 西游记语义层
# ============================================================

XIYOU_SEMANTIC = {
    "domain": "xiyou",
    "display_name": "西游记",
    "description": "基于吴承恩《西游记》的领域语义定义",

    # --- 中英文映射 ---
    "en_mapping": {
        # 对象类型
        "势力": "Faction",
        "人物": "Character",
        "地点": "Location",
        "事件": "Event",
        "关系": "Relationship",
        "法宝": "Treasure",
        "法术": "Spell",
        # 关系类型
        "师徒": "MentorDisciple",
        "结拜": "SwornBrother",
        "敌对": "EnemyOf",
        "降伏": "SubduedBy",
        "隶属": "BelongsTo",
        "栖居于": "DwellsAt",
        "持有": "Holds",
        "掌握": "Masters",
        "发生于": "OccurredAt",
        "参与": "ParticipatedIn",
        "掌管": "Controls",
        # 动作类型
        "降妖": "SubdueDemon",
        "斗法": "SpellDuel",
        "变化": "Transform",
        "求援": "SeekHelp",
        "渡劫": "OvercomeTrial",
        "使用法宝": "UseTreasure",
        # 属性
        "法名": "DharmaName",
        "称号": "Title",
        "种族": "Race",
        "修为": "Cultivation",
        "势力归属": "FactionAffiliation",
        "回目": "Chapter",
        "难数": "TrialNumber",
        "危险等级": "DangerLevel",
        "威力": "Power",
    },

    # --- 规范术语 + 同义词/近义词/别名 ---
    "canonical_terms": {
        # 对象类型术语
        "势力": {
            "synonyms": ["阵营", "天庭", "佛门", "妖界", "人间"],
            "near_synonyms": ["门派", "宗族", "部族"],
            "aliases": ["西游势力"],
        },
        "人物": {
            "synonyms": ["角色", "行者", "长老", "妖怪", "神仙", "菩萨", "妖魔"],
            "near_synonyms": ["精怪", "魔王", "罗汉", "天神", "真人"],
            "aliases": ["西游人物"],
        },
        "地点": {
            "synonyms": ["仙山", "洞府", "国度", "险境", "山", "洞", "国"],
            "near_synonyms": ["福地", "灵山", "天宫", "龙宫"],
            "aliases": ["西游地点"],
        },
        "事件": {
            "synonyms": ["劫难", "磨难", "难", "灾", "险", "八十一难"],
            "near_synonyms": ["考验", "历练", "关卡"],
            "aliases": ["西游事件", "八十一难"],
        },
        "法宝": {
            "synonyms": ["器具", "宝贝", "神器", "宝物"],
            "near_synonyms": ["法器", "灵宝", "仙器"],
            "aliases": ["西游法宝"],
        },
        "法术": {
            "synonyms": ["神通", "变化", "遁术", "法力"],
            "near_synonyms": ["仙术", "妖术", "道术", "佛法"],
            "aliases": ["西游法术"],
        },
        # 关系类型术语
        "师徒": {
            "synonyms": ["师徒关系", "取经团队", "师尊", "弟子"],
            "near_synonyms": ["传授", "教诲"],
            "aliases": ["取经师徒"],
        },
        "降妖": {
            "synonyms": ["除魔", "收妖", "降伏", "收服"],
            "near_synonyms": ["镇妖", "伏魔", "降服"],
            "aliases": ["降妖除魔"],
        },
        "斗法": {
            "synonyms": ["比拼", "斗法", "斗术", "较量"],
            "near_synonyms": ["对决", "比试"],
            "aliases": ["法术对决"],
        },
    },

    # --- 扩展规则 ---
    "expansion_rules": [
        {"pattern": "人物", "expansion": ["取经人", "妖魔", "神仙", "凡人"]},
        {"pattern": "势力", "expansion": ["天庭", "佛门", "妖界", "人间"]},
        {"pattern": "法宝", "expansion": ["金箍棒", "九齿钉耙", "紫金铃", "芭蕉扇"]},
        {"pattern": "法术", "expansion": ["七十二变", "筋斗云", "火眼金睛", "定身法"]},
        {"pattern": "劫难", "expansion": ["第一难", "第十难", "第五十难", "第八十一难"]},
    ],
}


# ============================================================
# 跨领域共享术语
# ============================================================

SHARED_SEMANTIC = {
    "domain": "shared",
    "display_name": "共享术语",
    "canonical_terms": {
        "人物": {
            "synonyms": ["角色", "人"],
            "near_synonyms": [],
            "aliases": [],
        },
        "势力": {
            "synonyms": ["阵营", "组织"],
            "near_synonyms": [],
            "aliases": [],
        },
        "地点": {
            "synonyms": ["位置", "场所"],
            "near_synonyms": [],
            "aliases": [],
        },
        "事件": {
            "synonyms": ["事情", "经过"],
            "near_synonyms": [],
            "aliases": [],
        },
        "关系": {
            "synonyms": ["关联", "联系"],
            "near_synonyms": [],
            "aliases": [],
        },
    },
    "en_mapping": {
        "人物": "Character",
        "势力": "Faction",
        "地点": "Location",
        "事件": "Event",
        "关系": "Relationship",
        "发生于": "OccurredAt",
        "参与": "ParticipatedIn",
        "控制": "Controls",
    },
}
