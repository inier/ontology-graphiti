# ADR-057: 四大名著领域本体设计——统一语义层与中英映射

## 状态

提议

## 上下文

ODAP 平台需要为 X-1（三国演义）和 X-2（西游记）两个场景构建完整的领域本体。当前存在以下问题：

1. **语义层缺失**：现有 `Disambiguator` 只覆盖军事领域（雷达/目标/威胁），不覆盖文学领域
2. **英文命名问题**：现有三国类型 `SanguoFaction/Character/Location/Event/Relationship` 的 `name` 全为英文
3. **中英映射不完整**：`display_name` 虽有中文，但作为技术标识的 `name` 未提供中文映射
4. **两个领域本体需统一规范**：三国和西游记的建模方法、命名规范、语义定义应保持一致

## 决策

### 1. 语义层设计原则

- **type_id 使用英文（驼峰式）**：技术标识符保持英文，确保 API/代码兼容性
- **display_name 使用中文**：面向用户的显示名称使用中文
- **name 字段为中英双语**：`name` 格式为 `中文名/EnglishName`，如 `人物/Character`
- **语义层注册所有术语**：对象类型、关系类型、动作类型、属性名均注册到 Disambiguator

### 2. 三国演义本体（X-1）

#### 对象类型（Object Types）

| type_id | name | display_name | 说明 |
|---------|------|-------------|------|
| SanguoFaction | 势力/Faction | 三国势力 | 魏/蜀/吴/群雄/晋 |
| SanguoCharacter | 人物/Character | 三国人物 | 主要人物 |
| SanguoLocation | 地点/Location | 三国地点 | 重要地理 |
| SanguoEvent | 事件/Event | 三国事件 | 重大历史事件 |
| SanguoRelationship | 关系/Relationship | 三国关系 | 人物间关系 |
| SanguoArtifact | 物品/Artifact | 三国物品 | 兵器/坐骑/宝物 |
| SanguoStrategy | 谋略/Strategy | 三国谋略 | 计策/兵法/阵法 |

#### 关系类型（Link Types）

| link_name | display_name | source→target | cardinality |
|-----------|-------------|---------------|-------------|
| serves | 效力于 | SanguoCharacter→SanguoFaction | N:1 |
| sworn_brother | 结义 | SanguoCharacter→SanguoCharacter | N:N |
| married_to | 联姻 | SanguoCharacter→SanguoCharacter | N:N |
| rival_of | 对峙 | SanguoCharacter→SanguoCharacter | N:N |
| mentor_of | 师徒 | SanguoCharacter→SanguoCharacter | N:1 |
| stationed_at | 驻守于 | SanguoCharacter→SanguoLocation | N:1 |
| controls | 控制 | SanguoFaction→SanguoLocation | 1:N |
| participated_in | 参与 | SanguoCharacter→SanguoEvent | N:N |
| occurred_at | 发生于 | SanguoEvent→SanguoLocation | N:1 |
| wielded_by | 持有 | SanguoArtifact→SanguoCharacter | N:1 |
| devised_by | 设谋 | SanguoStrategy→SanguoCharacter | N:1 |

#### 动作类型（Action Types）

| action_type_id | display_name | target | 说明 |
|---------------|-------------|--------|------|
| sanguo.进军 | 进军 | SanguoCharacter | 移动军队至某地 |
| sanguo.交战 | 交战 | SanguoCharacter | 两军对垒 |
| sanguo.结盟 | 结盟 | SanguoFaction | 势力间结盟 |
| sanguo.施计 | 施计 | SanguoStrategy | 使用谋略 |
| sanguo.登基 | 登基 | SanguoCharacter | 称帝 |
| sanguo.投降 | 投降 | SanguoCharacter | 投降归顺 |

#### 业务规则

| 规则ID | 规则名 | 描述 |
|--------|--------|------|
| SG-R001 | 时间一致性 | 事件年份必须在人物生存期内 |
| SG-R002 | 势力排他 | 同一人物同一时期只能属于一个势力 |
| SG-R003 | 事件因果链 | 事件可构成因果链（前因→后果） |
| SG-R004 | 势力消长 | 势力疆域随事件推移变化 |

#### 指标

| 指标ID | 指标名 | 计算方式 |
|--------|--------|----------|
| SG-I001 | 势力人口 | 所属人物数×权重 |
| SG-I002 | 战役胜率 | 胜利事件/总交战事件 |
| SG-I003 | 人物活跃度 | 参与事件数 |
| SG-I004 | 势力扩张速度 | 疆域变化/时间 |

### 3. 西游记本体（X-2）

#### 对象类型（Object Types）

| type_id | name | display_name | 说明 |
|---------|------|-------------|------|
| XiyouCharacter | 人物/Character | 西游人物 | 取经团队/妖魔/神仙/凡人 |
| XiyouFaction | 势力/Faction | 西游势力 | 天庭/佛门/妖界/人间 |
| XiyouLocation | 地点/Location | 西游地点 | 仙山/洞府/国度/险境 |
| XiyouEvent | 事件/Event | 西游事件 | 八十一难等关键情节 |
| XiyouTreasure | 法宝/Treasure | 西游法宝 | 金箍棒/九齿钉耙等 |
| XiyouSpell | 法术/Spell | 西游法术 | 七十二变/筋斗云等 |
| XiyouRelationship | 关系/Relationship | 西游关系 | 人物间关系 |

#### 关系类型（Link Types）

| link_name | display_name | source→target | cardinality |
|-----------|-------------|---------------|-------------|
| mentor_disciple | 师徒 | XiyouCharacter→XiyouCharacter | 1:N |
| sworn_brother | 结拜 | XiyouCharacter→XiyouCharacter | N:N |
| enemy_of | 敌对 | XiyouCharacter→XiyouCharacter | N:N |
| subdued_by | 降伏 | XiyouCharacter→XiyouCharacter | N:N |
| belongs_to | 隶属 | XiyouCharacter→XiyouFaction | N:1 |
| dwells_at | 栖居于 | XiyouCharacter→XiyouLocation | N:1 |
| holds | 持有 | XiyouCharacter→XiyouTreasure | N:N |
| masters | 掌握 | XiyouCharacter→XiyouSpell | N:N |
| occurred_at | 发生于 | XiyouEvent→XiyouLocation | N:1 |
| participated_in | 参与 | XiyouEvent→XiyouCharacter | N:N |
| controls | 掌管 | XiyouFaction→XiyouLocation | 1:N |

#### 动作类型（Action Types）

| action_type_id | display_name | target | 说明 |
|---------------|-------------|--------|------|
| xiyou.降妖 | 降妖除魔 | XiyouCharacter | 取经人降伏妖魔 |
| xiyou.斗法 | 斗法 | XiyouCharacter | 法术对决 |
| xiyou.变化 | 变化遁形 | XiyouCharacter | 使用变化之术 |
| xiyou.求援 | 搬请救兵 | XiyouCharacter | 请外援相助 |
| xiyou.渡劫 | 渡过劫难 | XiyouEvent | 克服八十一难 |
| xiyou.使用法宝 | 使用法宝 | XiyouTreasure | 激活法宝 |

#### 业务规则

| 规则ID | 规则名 | 描述 |
|--------|--------|------|
| XY-R001 | 劫难序号 | 八十一难按序号1-81递增 |
| XY-R002 | 法宝归属 | 法宝同一时刻只能被一人持有 |
| XY-R003 | 势力克制 | 天庭>妖界，佛门>天庭（观音受如来派遣） |
| XY-R004 | 取经路线 | 事件按地理路线推进（长安→灵山） |

#### 指标

| 指标ID | 指标名 | 计算方式 |
|--------|--------|----------|
| XY-I001 | 劫难进度 | 已渡劫数/81 |
| XY-I002 | 人物战力 | 法宝数+法术数+势力加成 |
| XY-I003 | 妖魔危险度 | 妖魔迫使求援次数 |
| XY-I004 | 取经团队协作度 | 协同降妖事件/总事件 |

### 4. 统一语义层（Semantic Layer）

需要将 Disambiguator 从纯军事领域扩展为可配置的多领域语义层：

```python
# 语义层配置结构
SEMANTIC_LAYERS = {
    "sanguo": {
        "canonical_terms": {
            "人物": ["角色", "人", "将军", "谋士", "君主"],
            "势力": ["阵营", "国家", "方", "朝"],
            "事件": ["战役", "战斗", "事变", "之变"],
            "地点": ["城池", "关隘", "州", "郡"],
            "谋略": ["计策", "兵法", "计谋", "奇谋"],
            "结义": ["桃园结义", "义兄弟", "结拜"],
            "效力于": ["归属", "投靠", "追随", "从属"],
        },
        "en_mapping": {
            "人物": "Character", "势力": "Faction", "事件": "Event",
            "地点": "Location", "谋略": "Strategy", "物品": "Artifact",
            "结义": "SwornBrother", "效力于": "Serves",
            "驻守于": "StationedAt", "发生于": "OccurredAt",
            "交战": "Battle", "进军": "March", "结盟": "Alliance",
        }
    },
    "xiyou": {
        "canonical_terms": {
            "人物": ["角色", "行者", "长老", "妖怪", "神仙", "菩萨"],
            "势力": ["阵营", "天庭", "佛门", "妖界"],
            "法宝": ["兵器", "宝贝", "神器", "宝物"],
            "法术": ["神通", "变化", "遁术", "法力"],
            "劫难": ["难", "磨难", "灾", "险"],
            "师徒": ["师徒关系", "取经团队"],
            "降妖": ["除魔", "收妖", "降伏"],
        },
        "en_mapping": {
            "人物": "Character", "势力": "Faction", "事件": "Event",
            "地点": "Location", "法宝": "Treasure", "法术": "Spell",
            "师徒": "MentorDisciple", "降妖": "SubdueDemon",
            "斗法": "SpellDuel", "渡劫": "OvercomeTrial",
        }
    }
}
```

## 后果

**正面**：
- 两个领域的本体有一致的设计规范
- 语义层支持中英映射和同义词消歧
- Agent 查询时可以用中文自然语言，系统自动映射到技术标识

**负面**：
- 需要扩展 Disambiguator 为多领域可配置
- 种子数据需要提供中英双语的 name
- OMS 中需要同时存储 `name`（双语言）和 `display_name`（纯中文）

## 可逆性

可逆。语义层配置为数据驱动，新增/修改领域只需更新 `SEMANTIC_LAYERS` 配置和对应的类型定义，不影响已有本体数据。

## 关联 ADR

- ADR-036：领域实体标准本体库（Palantir 参考）
- ADR-050：OADP 业务语义体系架构
- ADR-056：语义层修正（类型校验执行与模型统一）
