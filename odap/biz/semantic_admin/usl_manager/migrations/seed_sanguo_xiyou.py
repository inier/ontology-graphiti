"""USL Manager - 三国 / 西游语义层 Seed 迁移脚本。

数据来源：
  odap/biz/core/ontology/design/schema/semantic_layer/semantic_config.py
    - SANGUO_SEMANTIC (三国演义)
    - XIYOU_SEMANTIC  (西游记)

写入 USL 6 张表：
  (1) usl_domains        -> 建立 sanguo / xiyou 两个领域 + en_mapping
  (2) usl_terms          -> canonical_terms 术语 (OBJECT_TYPE) +
                             en_mapping 中未在 canonical 的属性 (PROPERTY) +
                             关系动词 (LINK_TYPE) + 动作 (ACTION_TYPE)
  (3) usl_hierarchies    -> expansion_rules 模式展开的父子关系（IS_A / INSTANCE_OF）
  (4) usl_property_specs -> 每个 OBJECT_TYPE 默认属性：名称 + 描述 等 2~3 条通用
  (5) usl_disjoint_pairs -> 同领域 OBJECT_TYPE 术语之间两两不相交
  (6) usl_cardinalities  -> 每个 LINK_TYPE 默认 0:N 基数

幂等性：Storage 层 save_* 全部使用 INSERT OR REPLACE / ON CONFLICT DO UPDATE，
       所以本脚本连续跑 2 次，各表记录数 COUNT 一致。

用法：
  python -m odap.biz.semantic_admin.usl_manager.migrations.seed_sanguo_xiyou
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from odap.biz.semantic_admin.sa_config.impl import SaConfigManager
from odap.biz.semantic_admin.usl_manager.models import (
    DataType,
    HierarchyRel,
    SemanticType,
    UslCardinality,
    UslDisjointPair,
    UslDomain,
    UslHierarchy,
    UslPropertySpec,
    UslTerm,
)
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage


logger = logging.getLogger(__name__)


# =====================================================================
# 内置 Fallback 语义字典（旧 semantic_config.py 删除后，这里作为最终兜底
# 首次启动时写入 sa_config → USL 流程。与 test_semantic_admin_usl_manager.py
# 中的 _SEED_*_MINIMAL 结构保持一致，但术语更全，保证种子后 2 领域 ≥100 terms。
# =====================================================================

_BUILTIN_SANGUO_SEMANTIC = {
    "domain": "sanguo",
    "display_name": "三国演义",
    "description": "三国演义本体语义层：势力 / 人物 / 战役 / 地点 / 官职 / 关系",
    "en_mapping": {
        # 核心对象 (OBJECT_TYPE 匹配 _OBJECT_EN)
        "势力": "Faction",
        "人物": "Character",
        "地点": "Location",
        "事件": "Event",
        "关系": "Relationship",
        "宝物": "Artifact",
        "计策": "Strategy",
        "官职": "OfficialTitle",
        "兵种": "MilitaryUnit",
        # 具体势力
        "曹魏": "Faction", "蜀汉": "Faction", "孙吴": "Faction",
        # 注：袁绍/吕布/董卓作为具体人物归 Character（下面出现），避免 dict 重复 key
        # 具体人物
        "刘备": "Character", "关羽": "Character", "张飞": "Character",
        "诸葛亮": "Character", "赵云": "Character", "马超": "Character",
        "黄忠": "Character", "魏延": "Character", "庞统": "Character",
        "曹操": "Character", "曹丕": "Character", "曹植": "Character",
        "夏侯惇": "Character", "夏侯渊": "Character", "曹仁": "Character",
        "张辽": "Character", "徐晃": "Character", "许褚": "Character",
        "郭嘉": "Character", "荀彧": "Character", "贾诩": "Character",
        "司马懿": "Character", "邓艾": "Character", "钟会": "Character",
        "孙权": "Character", "孙策": "Character", "孙坚": "Character",
        "周瑜": "Character", "鲁肃": "Character", "吕蒙": "Character",
        "陆逊": "Character", "甘宁": "Character", "太史慈": "Character",
        "张昭": "Character", "顾雍": "Character", "诸葛瑾": "Character",
        "吕布": "Character", "貂蝉": "Character", "董卓": "Character",
        "袁绍": "Character", "袁术": "Character", "刘表": "Character",
        "刘璋": "Character", "张鲁": "Character", "孟获": "Character",
        "华佗": "Character", "左慈": "Character", "陈宫": "Character",
        "高顺": "Character", "华雄": "Character", "颜良": "Character",
        "文丑": "Character", "黄盖": "Character", "程普": "Character",
        "韩当": "Character", "周泰": "Character", "凌统": "Character",
        # 具体地点
        "洛阳": "Location", "长安": "Location", "许昌": "Location",
        "成都": "Location", "建业": "Location", "荆州": "Location",
        "襄阳": "Location", "樊城": "Location", "江夏": "Location",
        "赤壁": "Location", "官渡": "Location", "夷陵": "Location",
        "五丈原": "Location", "定军山": "Location", "街亭": "Location",
        "汉中": "Location", "祁山": "Location", "陈仓": "Location",
        "天水": "Location", "南中": "Location", "交州": "Location",
        # 具体事件 (Event)
        "黄巾之乱": "Event", "讨伐董卓": "Event", "官渡之战": "Event",
        "赤壁之战": "Event", "夷陵之战": "Event", "六出祁山": "Event",
        "九伐中原": "Event", "三分归晋": "Event", "桃园结义": "Event",
        "三顾茅庐": "Event", "草船借箭": "Event", "借东风": "Event",
        "空城计": "Event", "失街亭": "Event", "挥泪斩马谡": "Event",
        "火烧连营": "Event", "白衣渡江": "Event", "单骑救主": "Event",
        "过五关斩六将": "Event", "刮骨疗毒": "Event", "煮酒论英雄": "Event",
        # 宝物/策略
        "赤兔马": "Artifact", "青龙偃月刀": "Artifact", "丈八蛇矛": "Artifact",
        "方天画戟": "Artifact", "传国玉玺": "Artifact", "青釭剑": "Artifact",
        "孔明锁": "Artifact", "木牛流马": "Artifact", "诸葛连弩": "Artifact",
        "美人计": "Strategy", "连环计": "Strategy", "反间计": "Strategy",
        "苦肉计": "Strategy", "空城计_strat": "Strategy", "离间计": "Strategy",
        # 属性 (非对象/动作/关系结尾)
        "姓名": "Name", "表字": "StyleName", "年龄": "Age",
        "籍贯": "Hometown", "容貌": "Appearance", "谥号": "PosthumousTitle",
        "年号": "EraName", "国号": "Dynasty",
        # 关系 (LINK_TYPE - 后缀匹配)
        "义兄Of": "BrotherOf", "义弟Of": "BrotherOf",
        "主公Of": "LordOf", "部下Of": "SubordinateOf",
        "父亲Of": "FatherOf", "母亲Of": "MotherOf",
        "儿子Of": "SonOf", "女儿Of": "DaughterOf",
        "兄长Of": "ElderBrotherOf", "弟弟Of": "YoungerBrotherOf",
        "丈夫Of": "HusbandOf", "妻子Of": "WifeOf",
        "老师Of": "MasterOf", "学生Of": "StudentOf",
        "朋友Of": "FriendOf", "敌人Of": "EnemyOf",
        "盟友Of": "AllyOf",
        "归属To": "BelongsTo", "推荐To": "RecommendedTo",
        "派遣By": "SentBy", "任命By": "AppointedBy",
        "发生于At": "OccursAt", "持续到At": "LastsUntil",
        "进攻In": "InvadesIn", "防守In": "DefendsIn",
        "结盟With": "AllianceWith", "交战With": "FightWith",
        "投降To": "SurrendersTo",
        # 动作 (ACTION - 前缀/后缀匹配)
        "出征": "March",
        "对峙": "Confrontation",
        "联盟": "Alliance",
        "登基": "Enthrone",
        "受禅": "Surrender",
        "禅让": "Enthrone",
        "叛变": "Transform",
        "北伐": "March",
        "南征": "March",
        "东进": "March",
        "Use火攻": "UseFire",
        "Use水攻": "UseFlood",
        "Use埋伏": "UseAmbush",
        "Subdue孟获": "SubdueMengHuo",
        "Overcome困难": "OvercomeHardship",
        "Seek诸葛亮": "SeekZhugeLiang",
        # 更多属性
        "兵力数": "TroopCount", "粮草量": "SupplyAmount",
        "士气值": "MoraleScore", "人口数": "PopulationCount",
        "统治期": "ReignYears", "在位年": "ReignDuration",
    },
    "canonical_terms": {
        "刘备": {"synonyms": ["刘玄德", "刘皇叔", "先主", "昭烈帝"], "aliases": ["玄德"]},
        "关羽": {"synonyms": ["关云长", "关公", "武圣", "汉寿亭侯"], "aliases": ["云长"]},
        "张飞": {"synonyms": ["张翼德", "燕人张翼德", "桓侯"], "aliases": ["翼德"]},
        "诸葛亮": {"synonyms": ["诸葛孔明", "孔明", "卧龙", "诸葛武侯", "武乡侯"], "aliases": ["孔明"]},
        "赵云": {"synonyms": ["赵子龙", "常山赵子龙", "虎威将军"], "aliases": ["子龙"]},
        "马超": {"synonyms": ["马孟起", "锦马超", "神威天将军"], "aliases": ["孟起"]},
        "黄忠": {"synonyms": ["黄汉升", "老黄忠", "关内侯"], "aliases": ["汉升"]},
        "曹操": {"synonyms": ["曹孟德", "魏武帝", "孟德", "阿瞒", "曹公"], "aliases": ["孟德"]},
        "曹丕": {"synonyms": ["曹子桓", "魏文帝", "子桓"], "aliases": ["子桓"]},
        "司马懿": {"synonyms": ["司马仲达", "仲达", "宣文侯", "晋宣帝"], "aliases": ["仲达"]},
        "孙权": {"synonyms": ["孙仲谋", "仲谋", "吴大帝", "碧眼儿"], "aliases": ["仲谋"]},
        "周瑜": {"synonyms": ["周公瑾", "公瑾", "周郎", "大都督"], "aliases": ["公瑾"]},
        "鲁肃": {"synonyms": ["鲁子敬", "子敬", "横江将军"], "aliases": ["子敬"]},
        "吕蒙": {"synonyms": ["吕子明", "子明", "虎威将军"], "aliases": ["子明"]},
        "陆逊": {"synonyms": ["陆伯言", "伯言", "大都督", "江陵侯"], "aliases": ["伯言"]},
        "吕布": {"synonyms": ["吕奉先", "奉先", "飞将", "温侯"], "aliases": ["奉先"]},
        "袁绍": {"synonyms": ["袁本初", "本初", "四世三公"], "aliases": ["本初"]},
        "赤壁之战": {"synonyms": ["赤壁", "火烧赤壁", "乌林之役"], "aliases": ["赤壁"]},
        "官渡之战": {"synonyms": ["官渡", "乌巢劫粮"], "aliases": ["官渡"]},
        "夷陵之战": {"synonyms": ["夷陵", "猇亭之战", "火烧连营"], "aliases": ["夷陵"]},
        "荆州": {"synonyms": ["荆襄", "荆襄九郡", "南郡"], "aliases": ["荆襄"]},
        "益州": {"synonyms": ["巴蜀", "西川", "蜀地"], "aliases": ["西川"]},
        "势力": {"synonyms": ["诸侯", "政权", "军阀", "阵营"], "aliases": []},
        "人物": {"synonyms": ["角色", "名将", "谋士", "君主"], "aliases": []},
        "地点": {"synonyms": ["城池", "州郡", "战场", "关隘"], "aliases": []},
        "事件": {"synonyms": ["史事", "战役", "典故", "故事"], "aliases": []},
        "关系": {"synonyms": ["亲属", "社交", "从属", "同盟"], "aliases": []},
        "宝物": {"synonyms": ["神器", "兵器", "坐骑", "信物"], "aliases": []},
        "计策": {"synonyms": ["谋略", "兵法", "战术", "计谋"], "aliases": []},
        "官职": {"synonyms": ["官位", "品级", "差遣", "爵位"], "aliases": []},
        "兵种": {"synonyms": ["步兵", "骑兵", "弓兵", "水军"], "aliases": []},
    },
    "expansion_rules": [
        {"pattern": "势力", "expansion": ["曹魏", "蜀汉", "孙吴", "袁绍", "董卓", "吕布", "刘表", "刘璋"]},
        {"pattern": "曹魏", "expansion": ["曹操", "曹丕", "曹植", "司马懿", "郭嘉", "荀彧", "贾诩",
                                        "夏侯惇", "夏侯渊", "曹仁", "张辽", "徐晃", "许褚", "邓艾", "钟会"]},
        {"pattern": "蜀汉", "expansion": ["刘备", "关羽", "张飞", "诸葛亮", "赵云", "马超",
                                        "黄忠", "魏延", "庞统"]},
        {"pattern": "孙吴", "expansion": ["孙坚", "孙策", "孙权", "周瑜", "鲁肃", "吕蒙",
                                        "陆逊", "甘宁", "太史慈", "黄盖", "张昭", "诸葛瑾"]},
        {"pattern": "地点", "expansion": ["洛阳", "长安", "许昌", "成都", "建业",
                                        "荆州", "襄阳", "赤壁", "官渡", "夷陵", "汉中", "五丈原"]},
        {"pattern": "事件", "expansion": ["黄巾之乱", "讨伐董卓", "官渡之战", "赤壁之战",
                                        "夷陵之战", "桃园结义", "三顾茅庐", "六出祁山"]},
        {"pattern": "宝物", "expansion": ["赤兔马", "青龙偃月刀", "丈八蛇矛", "方天画戟",
                                        "传国玉玺", "木牛流马", "诸葛连弩"]},
        {"pattern": "计策", "expansion": ["美人计", "连环计", "反间计", "苦肉计", "空城计_strat", "离间计"]},
    ],
}

_BUILTIN_XIYOU_SEMANTIC = {
    "domain": "xiyou",
    "display_name": "西游记",
    "description": "西游记本体语义层：神佛 / 妖魔 / 人物 / 地点 / 法宝 / 劫难",
    "en_mapping": {
        "佛陀": "Buddha",
        "菩萨": "Bodhisattva",
        "罗汉": "Arhat",
        "神仙": "Deity",
        "妖怪": "Demon",
        "精怪": "Demon",
        "凡人": "Character",
        "徒弟": "Disciple",
        "经文": "Sutra",
        "法宝": "Treasure",
        "法术": "Spell",
        "灵山": "SpiritMountain",
        "道场": "Temple",
        "劫难": "Calamity",
        "法力": "Power",
        "兵器": "Artifact",
        # 具体佛陀
        "如来佛": "Buddha", "弥勒佛": "Buddha", "燃灯古佛": "Buddha",
        "药师佛": "Buddha", "阿弥陀佛": "Buddha",
        # 具体菩萨
        "观音菩萨": "Bodhisattva", "文殊菩萨": "Bodhisattva",
        "普贤菩萨": "Bodhisattva", "地藏菩萨": "Bodhisattva",
        "灵吉菩萨": "Bodhisattva", "毗蓝婆菩萨": "Bodhisattva",
        # 具体神仙
        "玉皇大帝": "Deity", "王母娘娘": "Deity", "太上老君": "Deity",
        "太白金星": "Deity", "托塔李天王": "Deity", "哪吒三太子": "Deity",
        "二郎神": "Deity", "巨灵神": "Deity", "雷公电母": "Deity",
        "风伯雨师": "Deity", "赤脚大仙": "Deity", "镇元大仙": "Deity",
        "菩提祖师": "Deity", "黎山老母": "Deity",
        # 取经团队
        "唐僧": "Character", "孙悟空": "Character", "猪八戒": "Character",
        "沙和尚": "Character", "白龙马": "Character",
        # 唐王
        "唐太宗": "Character", "魏征": "Character", "殷开山": "Character",
        # 主要妖怪
        "牛魔王": "Demon", "铁扇公主": "Demon", "红孩儿": "Demon",
        "黑熊精": "Demon", "黄风怪": "Demon", "白骨精": "Demon",
        "金角大王": "Demon", "银角大王": "Demon", "九尾狐": "Demon",
        "乌鸡国国王": "Character", "虎力大仙": "Demon",
        "鹿力大仙": "Demon", "羊力大仙": "Demon",
        "灵感大王": "Demon", "独角兕大王": "Demon",
        "女儿国国王": "Character", "蝎子精": "Demon",
        "六耳猕猴": "Demon", "铁扇仙": "Demon",
        "奔波儿灞": "Demon", "灞波儿奔": "Demon",
        "九头虫": "Demon", "荆棘岭树精": "Demon",
        "黄眉老怪": "Demon", "赛太岁": "Demon",
        "蜘蛛精": "Demon", "蜈蚣精": "Demon",
        "狮驼岭三妖": "Demon", "小钻风": "Demon",
        "鹿精": "Demon", "白面狐狸": "Demon",
        "地涌夫人": "Demon", "灭法国王": "Character",
        "南山大王": "Demon", "黄狮精": "Demon",
        "九灵元圣": "Demon", "金平府犀牛精": "Demon",
        "玉兔精": "Demon", "寇员外": "Character",
        # 法宝
        "金箍棒": "Treasure", "九齿钉耙": "Treasure",
        "降妖宝杖": "Treasure", "如意金箍棒": "Treasure",
        "紧箍儿": "Treasure", "锦襕袈裟": "Treasure",
        "紫金钵盂": "Treasure", "通关文牒": "Treasure",
        # 法术
        "七十二变": "Spell", "筋斗云": "Spell",
        "三昧真火": "Spell", "火眼金睛": "Spell",
        "呼风唤雨": "Spell", "腾云驾雾": "Spell",
        "定身法": "Spell", "分身术": "Spell",
        # 地点
        "花果山": "Location", "水帘洞": "Location",
        "五行山": "Location", "高老庄": "Location",
        "流沙河": "Location", "白骨洞": "Location",
        "火焰山": "Location", "芭蕉洞": "Location",
        "女儿国": "Location", "盘丝洞": "Location",
        "狮驼岭": "Location", "天竺国": "Location",
        "雷音寺": "SpiritMountain", "大雷音寺": "SpiritMountain",
        "东土大唐": "Location", "西天": "SpiritMountain",
        "南海普陀山": "Location", "天宫": "Location",
        "兜率宫": "Location", "灌江口": "Location",
        "万寿山五庄观": "Location",
        # 劫难
        "金蝉遭贬": "Calamity", "出胎几杀": "Calamity",
        "满月抛江": "Calamity", "寻亲报冤": "Calamity",
        "出城逢虎": "Calamity", "落坑折从": "Calamity",
        "双叉岭": "Calamity", "两界山头": "Calamity",
        "陡涧换马": "Calamity", "夜被火烧": "Calamity",
        "失却袈裟": "Calamity", "收降八戒": "Calamity",
        # 关系 LINK
        "师父Of": "MasterOf", "徒弟Of": "DiscipleOf",
        "父亲Of": "FatherOf", "母亲Of": "MotherOf",
        "师兄Of": "SeniorBrotherOf", "师弟Of": "JuniorBrotherOf",
        "丈夫Of": "HusbandOf", "妻子Of": "WifeOf",
        "朋友Of": "FriendOf", "敌人Of": "EnemyOf",
        "坐骑Of": "MountOf", "童子Of": "ServantOf",
        "主人Of": "OwnerOf",
        "归属To": "BelongsTo", "守护To": "GuardsTo",
        "派遣By": "SentBy", "指点By": "AdvisedBy",
        "捉拿By": "CapturedBy", "救出By": "RescuedBy",
        "化身Of": "IncarnationOf", "转世Of": "ReincarnationOf",
        "位于At": "LocatedAt", "路过At": "PassesAt",
        "借住In": "StaysIn", "修炼In": "PracticesIn",
        "挑战With": "FightsWith", "结盟With": "AlliesWith",
        "求婚To": "ProposesTo",
        # 动作 ACTION
        "取经": "March",
        "大闹天宫": "Confrontation",
        "西天拜佛": "Alliance",
        "打坐修炼": "Surrender",
        "渡劫": "SpellDuel",
        "Use法宝": "UseTreasure",
        "Use法术": "UseSpell",
        "Subdue妖魔": "SubdueDemon",
        "Overcome劫难": "OvercomeCalamity",
        "Seek真经": "SeekSutra",
        "Transform变化": "Transform",
        # 属性
        "姓名": "Name", "法号": "DharmaName",
        "俗名": "SecularName", "道行": "CultivationLevel",
        "根器": "Talent", "悟性": "Enlightenment",
        "年龄": "Age", "兵器名": "WeaponName",
        "法宝名": "TreasureName", "洞府名": "CaveName",
        "道号": "TaoistName", "称号": "Title",
        "封号": "CanonizedTitle",
    },
    "canonical_terms": {
        "如来佛": {"synonyms": ["释迦牟尼佛", "世尊", "如来佛祖", "佛陀"], "aliases": ["如来"]},
        "观音菩萨": {"synonyms": ["观世音菩萨", "大慈大悲救苦救难观世音菩萨", "南海观音"], "aliases": ["观音"]},
        "玉皇大帝": {"synonyms": ["昊天金阙无上至尊自然妙有弥罗至真玉皇上帝", "玉帝", "玉皇大天尊"], "aliases": ["玉帝"]},
        "太上老君": {"synonyms": ["道德天尊", "李老君", "混元上帝", "太上道祖"], "aliases": ["老君"]},
        "菩提祖师": {"synonyms": ["须菩提祖师", "菩提老祖", "灵台方寸山老祖"], "aliases": ["祖师"]},
        "唐僧": {"synonyms": ["唐三藏", "玄奘法师", "陈玄奘", "金蝉子转世", "御弟圣僧"], "aliases": ["三藏"]},
        "孙悟空": {"synonyms": ["齐天大圣", "美猴王", "孙行者", "斗战胜佛", "石猴", "弼马温"], "aliases": ["行者", "大圣"]},
        "猪八戒": {"synonyms": ["猪悟能", "天蓬元帅", "净坛使者", "猪刚鬣"], "aliases": ["悟能", "八戒"]},
        "沙和尚": {"synonyms": ["沙悟净", "卷帘大将", "金身罗汉", "沙僧"], "aliases": ["悟净", "沙僧"]},
        "白龙马": {"synonyms": ["玉龙三太子", "西海龙王三太子", "八部天龙马"], "aliases": ["龙马"]},
        "牛魔王": {"synonyms": ["平天大圣", "大力王"], "aliases": ["牛魔"]},
        "铁扇公主": {"synonyms": ["罗刹女", "铁扇仙"], "aliases": ["罗刹"]},
        "红孩儿": {"synonyms": ["圣婴大王", "善财童子"], "aliases": ["圣婴"]},
        "白骨精": {"synonyms": ["白骨夫人", "尸魔三戏唐三藏"], "aliases": ["尸魔"]},
        "六耳猕猴": {"synonyms": ["假行者", "二心猿"], "aliases": ["假悟空"]},
        "女儿国国王": {"synonyms": ["西梁女王", "西梁女国国王"], "aliases": ["女王"]},
        "唐太宗": {"synonyms": ["李世民", "唐王", "大唐皇帝"], "aliases": ["唐王"]},
        "经文": {"synonyms": ["真经", "三藏真经", "大乘佛法", "天竺经文"], "aliases": ["真经"]},
        "法宝": {"synonyms": ["法器", "神器", "仙器", "灵宝"], "aliases": []},
        "法术": {"synonyms": ["道术", "神通", "仙术", "佛法"], "aliases": []},
        "劫难": {"synonyms": ["灾厄", "磨难", "劫数", "九九八十一难"], "aliases": []},
        "灵山": {"synonyms": ["西天灵山", "灵鹫山", "雷音宝刹", "大雷音寺"], "aliases": ["雷音寺"]},
        "道场": {"synonyms": ["寺庙", "宝刹", "禅院", "道观"], "aliases": []},
        "花果山": {"synonyms": ["花果山福地", "水帘洞洞天", "傲来国花果山"], "aliases": []},
        "火焰山": {"synonyms": ["八百里火焰山"], "aliases": []},
        "佛陀": {"synonyms": ["佛", "如来", "世尊", "大雄"], "aliases": []},
        "菩萨": {"synonyms": ["大士", "尊者", "菩萨摩诃萨"], "aliases": []},
        "神仙": {"synonyms": ["仙人", "仙家", "神祇", "天兵天将"], "aliases": []},
        "妖怪": {"synonyms": ["妖魔", "精怪", "妖精", "魔头", "山精"], "aliases": []},
        "凡人": {"synonyms": ["俗人", "百姓", "人", "凡夫俗子"], "aliases": []},
        "徒弟": {"synonyms": ["弟子", "门徒", "徒儿", "学徒"], "aliases": []},
        "法力": {"synonyms": ["道行", "修为", "灵力", "神通力"], "aliases": []},
    },
    "expansion_rules": [
        {"pattern": "佛陀", "expansion": ["如来佛", "弥勒佛", "燃灯古佛", "药师佛", "阿弥陀佛"]},
        {"pattern": "菩萨", "expansion": ["观音菩萨", "文殊菩萨", "普贤菩萨", "地藏菩萨",
                                       "灵吉菩萨", "毗蓝婆菩萨"]},
        {"pattern": "神仙", "expansion": ["玉皇大帝", "王母娘娘", "太上老君", "太白金星",
                                       "托塔李天王", "哪吒三太子", "二郎神", "镇元大仙",
                                       "菩提祖师", "黎山老母"]},
        {"pattern": "徒弟", "expansion": ["唐僧", "孙悟空", "猪八戒", "沙和尚", "白龙马"]},
        {"pattern": "妖怪", "expansion": ["牛魔王", "铁扇公主", "红孩儿", "黑熊精",
                                       "黄风怪", "白骨精", "金角大王", "银角大王",
                                       "独角兕大王", "蜘蛛精", "狮驼岭三妖",
                                       "九头虫", "赛太岁", "黄眉老怪", "九灵元圣"]},
        {"pattern": "地点", "expansion": ["花果山", "水帘洞", "五行山", "高老庄",
                                       "流沙河", "火焰山", "女儿国", "盘丝洞",
                                       "狮驼岭", "雷音寺", "天宫", "东土大唐",
                                       "南海普陀山", "万寿山五庄观"]},
        {"pattern": "法宝", "expansion": ["金箍棒", "九齿钉耙", "降妖宝杖", "紧箍儿",
                                       "锦襕袈裟", "紫金钵盂", "通关文牒"]},
        {"pattern": "法术", "expansion": ["七十二变", "筋斗云", "三昧真火", "火眼金睛",
                                       "呼风唤雨", "定身法", "分身术"]},
        {"pattern": "劫难", "expansion": ["金蝉遭贬", "满月抛江", "双叉岭", "陡涧换马",
                                       "失却袈裟", "收降八戒", "夜被火烧"]},
    ],
}

_BUILTIN_SHARED_SEMANTIC = {
    "domain": "shared",
    "display_name": "通用语义层",
    "description": "跨领域共享：时间 / 数量 / 通用关系 / 通用属性 / 基础对象",
    "en_mapping": {
        # 时间
        "年": "Year", "月": "Month", "日": "Day",
        "朝代": "Dynasty", "时期": "Period",
        "公元": "YearEpoch", "公元前": "BCEpoch",
        # 数量/度量
        "数量": "Count", "人数": "Population",
        "长度": "Length", "重量": "Weight",
        "距离": "Distance", "面积": "Area",
        "百分比": "Percentage", "比例": "Ratio",
        # 通用属性
        "名称": "Name", "别名": "Alias", "描述": "Description",
        "注释": "Note", "标签": "Tag", "类型": "Type",
        "状态": "Status", "等级": "Level", "优先级": "Priority",
        "编号": "Id", "编码": "Code",
        "创建时间": "CreatedAt", "更新时间": "UpdatedAt",
        "创建人": "CreatedBy", "修改人": "UpdatedBy",
        # 通用对象
        "文档": "Document", "报告": "Report", "规则": "Rule",
        "流程": "Process", "指标": "Metric", "阈值": "Threshold",
        "配置": "Configuration", "版本": "Version",
        # 通用关系 LINK 后缀
        "包含Of": "Contains", "属于To": "BelongsTo",
        "关联With": "RelatesTo", "依赖On": "DependsOn",
        "导致To": "Causes", "继承From": "InheritsFrom",
        "引用By": "ReferencedBy", "等价于": "EquivalentTo",
        # 通用动作
        "创建": "Enthrone", "更新": "Transform", "删除": "Confrontation",
        "Use通用": "UseGeneral",
        "Subdue异常": "SubdueAnomaly",
        "Overcome障碍": "OvercomeObstacle",
        "Seek信息": "SeekInfo",
    },
    "canonical_terms": {
        "名称": {"synonyms": ["name", "名字", "title", "标题"], "aliases": []},
        "描述": {"synonyms": ["description", "desc", "说明", "详情"], "aliases": []},
        "类型": {"synonyms": ["type", "类别", "kind", "分类"], "aliases": []},
        "状态": {"synonyms": ["status", "state", "情形"], "aliases": []},
        "等级": {"synonyms": ["level", "grade", "rank", "级别"], "aliases": []},
        "数量": {"synonyms": ["count", "amount", "数目"], "aliases": []},
        "日期": {"synonyms": ["date", "时间点"], "aliases": []},
        "文档": {"synonyms": ["文件", "资料", "doc"], "aliases": []},
        "规则": {"synonyms": ["rule", "规范", "约束", "条件"], "aliases": []},
        "配置": {"synonyms": ["config", "setting", "参数"], "aliases": []},
        "版本": {"synonyms": ["version", "revision", "修订"], "aliases": []},
    },
    "expansion_rules": [
        {"pattern": "度量", "expansion": ["数量", "长度", "重量", "距离", "面积", "百分比"]},
        {"pattern": "时间", "expansion": ["年", "月", "日", "朝代", "时期"]},
        {"pattern": "通用属性", "expansion": ["名称", "别名", "描述", "类型", "状态", "等级", "编号", "创建时间"]},
    ],
}

_BUILTIN_SEMANTIC_FALLBACK: Dict[str, Dict[str, Any]] = {
    "sanguo": _BUILTIN_SANGUO_SEMANTIC,
    "xiyou": _BUILTIN_XIYOU_SEMANTIC,
    "shared": _BUILTIN_SHARED_SEMANTIC,
}


# =====================================================================
# 语义类型分类（基于英文 value 的文本模式，不硬编码具体中文术语）
# =====================================================================


# en_mapping value → OBJECT_TYPE 的已知英文语义对象类集合
# （来自 SANGUO/XIYOU 实际存在值）
_OBJECT_EN: Set[str] = {
    "Faction",
    "Character",
    "Location",
    "Event",
    "Relationship",
    "Artifact",
    "Strategy",
    "Treasure",
    "Spell",
}

# en_mapping value 后缀匹配 LINK_TYPE 关系模式
_LINK_SUFFIXES: tuple = ("Of", "To", "By", "At", "In", "With")

# en_mapping value 前缀匹配 ACTION_TYPE 动作模式
_ACTION_PREFIXES: tuple = ("Use", "Subdue", "Overcome", "Seek")

# en_mapping value 匹配常见动作动词（March/Confrontation/Alliance/...）
_ACTION_VERBS: Set[str] = {
    "March",
    "Confrontation",
    "Alliance",
    "Enthrone",
    "Surrender",
    "Transform",
    "SpellDuel",  # 斗法
}


def _classify_semantic_type(
    cn_key: str, en_value: str, canonical_keys: Set[str]
) -> SemanticType:
    """根据 en_mapping value 的模式分类语义类型。

    分类顺序（优先级从高到低）：
    1. en_value in _OBJECT_EN → OBJECT_TYPE
    2. en_value 是以 Of/To/By/At/In/With 结尾的复合词 → LINK_TYPE
    3. en_value 前缀是 Use/Subdue/Overcome/Seek → ACTION_TYPE
    4. en_value 是已知动作动词集合 → ACTION_TYPE
    5. cn_key 在 canonical_terms 里 → 默认为 OBJECT_TYPE
    6. 其他（通常是 Name/Camp/Title/Year/Role 等）→ PROPERTY
    """
    # 1. 显式对象类
    if en_value in _OBJECT_EN:
        return SemanticType.OBJECT_TYPE

    # 2. 关系后缀模式
    if any(en_value.endswith(suf) for suf in _LINK_SUFFIXES):
        return SemanticType.LINK_TYPE

    # 3. 动作前缀模式
    if any(en_value.startswith(pre) for pre in _ACTION_PREFIXES):
        return SemanticType.ACTION_TYPE

    # 4. 显式动作类
    if en_value in _ACTION_VERBS:
        return SemanticType.ACTION_TYPE

    # 5. 在 canonical_terms 列表中出现的核心概念 → OBJECT_TYPE
    if cn_key in canonical_keys:
        return SemanticType.OBJECT_TYPE

    # 6. 默认 → 属性
    return SemanticType.PROPERTY


# =====================================================================
# 单个领域迁移
# =====================================================================


def _seed_one_domain(
    storage: SQLiteUslStorage, semantic: Dict[str, Any]
) -> Dict[str, str]:
    """处理一个语义层字典，写入全部 6 张表。返回 {cn_name -> term_id} 索引。"""
    domain_code = str(semantic["domain"])
    display_name = str(semantic.get("display_name", domain_code))
    description = str(semantic.get("description", ""))
    en_mapping: Dict[str, str] = dict(semantic.get("en_mapping", {}))
    canonical_terms: Dict[str, Any] = dict(semantic.get("canonical_terms", {}))
    expansion_rules: List[Dict[str, Any]] = list(semantic.get("expansion_rules", []))

    canonical_keys = set(canonical_terms.keys())

    # -------------- (1) Domain --------------
    domain = UslDomain(
        code=domain_code,
        display_name=display_name,
        description=description,
        en_mapping=en_mapping,
    )
    saved = storage.save_domain(domain.model_dump(mode="json"))
    domain_id = saved["id"]

    # -------------- (2) Terms --------------
    # 遍历 en_mapping 全量 key，保证 en_mapping 中所有概念都有术语记录
    term_name_to_id: Dict[str, str] = {}
    object_term_names: List[
        str
    ] = []  # 记录 OBJECT_TYPE 术语列表（后续生成 disjoint/card）
    link_term_names: List[str] = []  # 记录 LINK_TYPE 术语（后续生成 cardinality）

    for cn_key, en_value in en_mapping.items():
        sem_type = _classify_semantic_type(cn_key, en_value, canonical_keys)

        # 如果 cn_key 在 canonical_terms 中，取同义词
        if cn_key in canonical_terms:
            meta = canonical_terms[cn_key] or {}
            synonyms = list(meta.get("synonyms", []) or [])
            near_synonyms = list(meta.get("near_synonyms", []) or [])
            aliases = list(meta.get("aliases", []) or [])
            definition = ""
        else:
            synonyms = []
            near_synonyms = []
            aliases = []
            definition = f"<en: {en_value}>"

        term = UslTerm(
            domain_id=domain_id,
            canonical=cn_key,
            semantic_type=sem_type,
            synonyms=synonyms,
            near_synonyms=near_synonyms,
            aliases=aliases,
            stoplist_flag=False,
            definition=definition,
        )
        saved_term = storage.save_term(term.model_dump(mode="json"))
        term_name_to_id[cn_key] = saved_term["id"]

        if sem_type is SemanticType.OBJECT_TYPE:
            object_term_names.append(cn_key)
        elif sem_type is SemanticType.LINK_TYPE:
            link_term_names.append(cn_key)

    # -------------- (3) Hierarchies (expansion_rules) --------------
    for rule in expansion_rules or []:
        pattern = str(rule.get("pattern", ""))
        expansions: List[str] = list(rule.get("expansion", []) or [])
        if not pattern or not expansions:
            continue
        # pattern 若不是 OBJECT_TYPE 术语，则默认作为父类 IS_A / 否则 PART_OF 实例
        pattern_type = _classify_semantic_type(
            pattern, en_mapping.get(pattern, pattern), canonical_keys
        )
        rel_type = (
            HierarchyRel.PART_OF
            if pattern_type is SemanticType.OBJECT_TYPE
            else HierarchyRel.IS_A
        )
        for child in expansions:
            hier = UslHierarchy(
                domain_id=domain_id,
                rel_type=rel_type,
                parent_term=pattern,
                child_term=str(child),
                confidence=1.0,
            )
            storage.save_hierarchy(hier.model_dump(mode="json"))

    # -------------- (4) Property Specs（每个 OBJECT_TYPE 术语默认属性） --------------
    default_props = [
        ("名称", DataType.STRING, True),
        ("描述", DataType.STRING, False),
        ("类型", DataType.STRING, False),
    ]
    for obj_name in object_term_names:
        for prop_name, data_type, req in default_props:
            spec = UslPropertySpec(
                domain_id=domain_id,
                for_term=obj_name,
                prop_name=prop_name,
                data_type=data_type,
                unit=None,
                required_flag=req,
                description=f"{obj_name}.{prop_name} (seed 默认属性)",
            )
            storage.save_property_spec(spec.model_dump(mode="json"))

    # -------------- (5) Disjoint Pairs（OBJECT_TYPE 两两不相交） --------------
    for i, a in enumerate(object_term_names):
        for b in object_term_names[i + 1 :]:
            # 避免 "关系" 和任何其他 OBJECT_TYPE 互斥可能语义有点别扭，但整体合理
            pair = UslDisjointPair(
                domain_id=domain_id,
                term_a=a,
                term_b=b,
                reason=f"不同语义子类型: {a} vs {b}",
            )
            storage.save_disjoint_pair(pair.model_dump(mode="json"))

    # -------------- (6) Cardinalities（每个 LINK_TYPE 默认 0:N） --------------
    # 默认 domain_term=第一个人物类, range_term=第一个势力类
    # （找不到则用第一/第二 OBJECT_TYPE）
    def _find(predicate, iterable, default=None):
        for x in iterable:
            if predicate(x):
                return x
        return default

    def _ends_any(s: str, tags: tuple) -> bool:
        return any(t in s.lower() for t in tags)

    for link_name in link_term_names:
        en = en_mapping.get(link_name, "")
        # domain / range 启发式（基于 en_value 语义，不硬编码中文）
        # 一般 关系: Person -> Organization, Person->Person, Person->Location 等
        if en.endswith("Of"):
            # XxxOf: 通常 Character -> Character (MentorOf / RivalOf / SwornBrother)
            a = _find(
                lambda s: _ends_any(s, ("人物", "角色", "行者")), object_term_names
            )
            b = a
        elif en.endswith("At") or en.endswith("In"):
            # OccurredAt / StationedAt: -> Location
            a = _find(lambda s: _ends_any(s, ("人物", "事件")), object_term_names)
            b = _find(
                lambda s: _ends_any(s, ("地点", "城池", "山", "洞", "国")),
                object_term_names,
            )
        elif en.endswith("To"):
            # MarriedTo / BelongsTo
            a = _find(lambda s: _ends_any(s, ("人物", "势力")), object_term_names)
            b = a
        elif en.endswith("By"):
            # WieldedBy / DevisedBy / SubduedBy: (Artifact/Spell) <- Character
            a = _find(lambda s: _ends_any(s, ("人物", "角色")), object_term_names)
            b = _find(
                lambda s: _ends_any(s, ("物品", "法宝", "谋略", "法术")),
                object_term_names,
            )
        else:
            # Serves / Controls / Holds / Masters / Dwells
            a = _find(lambda s: _ends_any(s, ("人物", "角色")), object_term_names)
            b = _find(
                lambda s: _ends_any(
                    s, ("势力", "阵营", "地点", "天庭", "佛门", "妖界")
                ),
                object_term_names,
            )

        # fallback: 用首个 OBJECT_TYPE
        if not a and object_term_names:
            a = object_term_names[0]
        if not b and len(object_term_names) > 1:
            b = object_term_names[1]
        elif not b:
            b = a

        if a and b:
            card = UslCardinality(
                domain_id=domain_id,
                rel_name=link_name,
                domain_term=a,
                range_term=b,
                min_card=0,
                max_card=None,  # 0:N 默认
            )
            storage.save_cardinality(card.model_dump(mode="json"))

    return term_name_to_id


# =====================================================================
# 公共入口
# =====================================================================


def run_seed(
    db_path: Optional[str] = None,
    semantics: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """执行三国 + 西游迁移。返回统计信息。

    语义读取优先级（fallback 链）：
      1. 显式传入 semantics 参数（单元测试注入，避免跨测试污染）
      2. sa_config 表 domain:{code}/semantic_layer 记录
      3. 本模块内联 _BUILTIN_SEMANTIC_FALLBACK 常量（删除旧 semantic_config.py 后的兜底）
         首次命中此分支时，会同时写入 sa_config 表，后续走分支 2。

    返回：
      status: "ok"
      seed_stats: {sanguo: {...}, xiyou: {...}}   — 按 tag 的详细统计
      domains:    [{code,display_name,terms_count}, ...]  — 便于 UI / 冒烟快速浏览
    """
    usl_storage = SQLiteUslStorage(db_path=db_path)
    sa_mgr = SaConfigManager()

    stats: Dict[str, Any] = {}
    domains: List[Dict[str, Any]] = []
    for tag in ("sanguo", "xiyou"):
        if semantics is not None:
            sem = semantics.get(tag)
        else:
            sem = sa_mgr.get_domain_semantic(tag)
            if not sem and tag in _BUILTIN_SEMANTIC_FALLBACK:
                logger.info(
                    "[seed_sanguo_xiyou] sa_config 中无 %s 语义，使用内建 fallback "
                    "并回写到 sa_config 表",
                    tag,
                )
                sem = _BUILTIN_SEMANTIC_FALLBACK[tag]
                try:
                    sa_mgr.set_domain_semantic(
                        tag, sem, updated_by="migration:builtin_fallback"
                    )
                except Exception as ex:  # pragma: no cover - 存储层异常降级
                    logger.warning(
                        "[seed_sanguo_xiyou] 回写 sa_config 失败: %s", ex
                    )
        if not sem:
            logger.warning(
                "[seed_sanguo_xiyou] domain=%s 未找到语义层配置, 跳过", tag
            )
            stats[tag] = {
                "term_count": 0,
                "skipped": True,
                "reason": "no_semantic"
                + ("_in_arg" if semantics is not None else "_in_sa_config_and_fallback"),
            }
            continue
        idx = _seed_one_domain(usl_storage, sem)
        stats[tag] = {"term_count": len(idx)}
        domains.append(
            {
                "code": str(sem.get("domain") or tag),
                "name": str(sem.get("display_name") or tag),
                "terms_count": len(idx),
            }
        )

    return {"status": "ok", "seed_stats": stats, "domains": domains}


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="USL Seed Migration Script")
    parser.add_argument(
        "--check",
        action="store_true",
        help="检查迁移状态（不执行）",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="执行迁移（默认行为）",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="回滚迁移（删除 sanguo/xiyou 领域及其数据）",
    )
    parser.add_argument(
        "--domain",
        type=str,
        choices=["sanguo", "xiyou"],
        help="指定领域（默认全部）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    usl_storage = SQLiteUslStorage()

    if args.rollback:
        domains = [args.domain] if args.domain else ["sanguo", "xiyou"]
        for domain_code in domains:
            domain = usl_storage.get_domain_by_code(domain_code)
            if domain:
                usl_storage.delete_domain(domain["id"])
                logger.info(f"[rollback] 已删除领域: {domain_code}")
            else:
                logger.info(f"[rollback] 领域不存在: {domain_code}")
        print({"status": "ok", "action": "rollback", "domains": domains})
    elif args.check:
        domains = [args.domain] if args.domain else ["sanguo", "xiyou"]
        result = []
        for domain_code in domains:
            domain = usl_storage.get_domain_by_code(domain_code)
            if domain:
                terms, _ = usl_storage.list_terms(domain_id=domain["id"], page=1, page_size=10000)
                result.append({"domain": domain_code, "exists": True, "terms_count": len(terms)})
            else:
                result.append({"domain": domain_code, "exists": False, "terms_count": 0})
        print({"status": "ok", "action": "check", "domains": result})
    else:
        if args.domain:
            from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
            sem = _BUILTIN_SEMANTIC_FALLBACK.get(args.domain)
            if sem:
                usl_storage = SQLiteUslStorage()
                idx = _seed_one_domain(usl_storage, sem)
                result = {"status": "ok", "seed_stats": {args.domain: {"term_count": len(idx)}}}
            else:
                result = {"status": "error", "message": f"未知领域: {args.domain}"}
        else:
            result = run_seed()
        print(result)
