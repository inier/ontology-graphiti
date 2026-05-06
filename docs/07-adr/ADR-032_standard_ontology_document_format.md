# ADR-032: 标准化本体文档格式（OntologyDocument）

## 状态
已接受

## 上下文

系统中存在多个数据来源产生的模拟/情报数据：
- 联网采集并经 LLM 归纳的新闻纪实
- 用户手动输入的动态信息
- 随机生成的涉事方行为数据
- 从外部系统导入的历史场景

这些数据需要满足：
1. **可沉淀**：格式标准，可长期存档和复用
2. **可扩展本体**：能驱动 Graphiti 自动构建和扩展知识图谱
3. **结构对齐**：与 Palantir AIP 本体结构、OWL/RDF 语义层对齐，便于生态集成
4. **人机可读**：人工审核友好，也能直接被 LLM 解析

参考：Palantir Ontology（Object Type / Property / Action / Rule）、Schema.org、军用 STANAG 5500 交换格式、OpenCog AtomSpace。

---

## 决策

### 统一格式：OntologyDocument JSON

每一条可沉淀的数据单元称为 **OntologyDocument**，是系统内数据流通的原子格式。

```json
{
  "$schema": "https://odap.local/schemas/ontology-document/v1.json",
  "$version": "1.0.0",
  "doc_id": "evt-20260414-001",
  "doc_type": "event",
  "source": {
    "type": "news_ingest",
    "url": "https://example.com/news/xyz",
    "collected_at": "2026-04-14T10:00:00Z",
    "confidence": 0.85
  },
  "meta": {
    "title": "B区遭遇战事件",
    "description": "红方装甲营在 B 区遭遇蓝方机械化步兵，发生遭遇战",
    "tags": ["战斗", "遭遇战", "B区"],
    "language": "zh",
    "classification": "SIM"
  },

  "entities": [
    {
      "entity_id": "unit-red-armor-001",
      "entity_type": "Unit",
      "name": "红方装甲营",
      "name_en": "Red Armor Battalion",
      "basic_properties": {
        "side": "red",
        "unit_type": "armor",
        "strength": 320,
        "location": "B区北侧",
        "coordinates": [39.9, 116.4],
        "status": "engaged"
      },
      "statistical_properties": {
        "combat_power": 0.78,
        "morale": 0.85,
        "supply_level": 0.6,
        "casualty_rate": 0.05,
        "advance_speed_kmh": 12.0
      },
      "capabilities": {
        "fire_range_km": 8,
        "armor_penetration": "high",
        "air_defense": false
      }
    },
    {
      "entity_id": "unit-blue-mech-001",
      "entity_type": "Unit",
      "name": "蓝方机械化步兵营",
      "name_en": "Blue Mechanized Infantry Battalion",
      "basic_properties": {
        "side": "blue",
        "unit_type": "mechanized_infantry",
        "strength": 450,
        "location": "B区南侧",
        "coordinates": [39.85, 116.42],
        "status": "engaged"
      },
      "statistical_properties": {
        "combat_power": 0.65,
        "morale": 0.72,
        "supply_level": 0.8,
        "casualty_rate": 0.08,
        "advance_speed_kmh": 8.0
      },
      "capabilities": {
        "fire_range_km": 3,
        "armor_penetration": "medium",
        "air_defense": true
      }
    }
  ],

  "relations": [
    {
      "relation_id": "rel-001",
      "relation_type": "engaged_with",
      "source_entity": "unit-red-armor-001",
      "target_entity": "unit-blue-mech-001",
      "properties": {
        "engagement_type": "direct_fire",
        "distance_km": 2.5,
        "initiated_by": "red"
      },
      "temporal": {
        "start_time": "2026-04-14T08:30:00Z",
        "end_time": null,
        "is_current": true
      }
    }
  ],

  "events": [
    {
      "event_id": "evt-001",
      "event_type": "contact",
      "timestamp": "2026-04-14T08:30:00Z",
      "location": "B区",
      "coordinates": [39.875, 116.41],
      "participants": ["unit-red-armor-001", "unit-blue-mech-001"],
      "description": "红方装甲营与蓝方机械化步兵营在B区发生接触",
      "outcome": {
        "red_casualties": 15,
        "blue_casualties": 22,
        "terrain_control_change": "contested"
      },
      "phase": "initial_contact"
    }
  ],

  "actions": [
    {
      "action_id": "act-001",
      "action_type": "attack",
      "actor": "unit-red-armor-001",
      "target": "unit-blue-mech-001",
      "timestamp": "2026-04-14T08:35:00Z",
      "parameters": {
        "fire_mode": "direct",
        "munition_type": "APFSDS",
        "rounds_fired": 24
      },
      "opa_required": true,
      "status": "executed"
    }
  ],

  "rules": [
    {
      "rule_id": "rule-roe-001",
      "rule_type": "engagement_rule",
      "description": "装甲单位接触后须在 30 分钟内请求炮兵支援",
      "condition": "unit_type == 'armor' AND engaged == true AND duration_min >= 30",
      "consequence": "request_artillery_support",
      "priority": "high",
      "source": "ROE-2026-v2"
    }
  ],

  "constraints": [
    {
      "constraint_id": "cst-001",
      "constraint_type": "geographic",
      "description": "禁止炮击 B 区平民聚居点",
      "scope": {
        "entity_types": ["Artillery", "MLRS"],
        "area": "civilian_zone_B",
        "coordinates_polygon": [[39.86, 116.40], [39.88, 116.40], [39.88, 116.43], [39.86, 116.43]]
      },
      "violation_consequence": "mission_abort",
      "legal_basis": "ROE-LOAC-2026"
    }
  ],

  "ontology_version": {
    "version_id": "v20260414-001",
    "parent_version": "v20260413-012",
    "commit_message": "B区遭遇战事件 - 新闻采集归纳",
    "schema_version": "1.0.0"
  }
}
```

---

### Schema 说明

#### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `$schema` | string | ✅ | Schema URL，版本化 |
| `doc_id` | string | ✅ | 全局唯一 ID，建议前缀：`evt-`, `unit-`, `scenario-` |
| `doc_type` | enum | ✅ | `event` / `entity` / `scenario` / `batch` |
| `source` | object | ✅ | 数据来源（`news_ingest` / `manual` / `random_gen` / `import`） |
| `meta` | object | ✅ | 标题、描述、标签、分类级别 |
| `entities` | array | ✅ | 实体列表（本体对象类型） |
| `relations` | array | ✅ | 关系列表（边） |
| `events` | array | ✅ | 事件序列（时序） |
| `actions` | array | ⬜ | 行动列表（可选） |
| `rules` | array | ⬜ | 规则集合（交战规则等） |
| `constraints` | array | ⬜ | 约束集合（禁区、ROE 限制等） |
| `ontology_version` | object | ✅ | 版本信息，写入图谱时追踪 |

#### 实体 (Entity) 四类属性对照

| 属性组 | 说明 | 参考 |
|--------|------|------|
| `basic_properties` | 标识性属性：名称、位置、状态、类型 | Palantir Object Properties |
| `statistical_properties` | 数值性指标：战力、士气、损耗率 | Palantir Computed Properties |
| `capabilities` | 能力维度：射程、穿甲、防空 | STANAG 5500 |
| `constraints` | 实体级约束（独立于全局约束集） | OWL Restriction |

---

### 版本化与沉淀规则

```
每个 OntologyDocument 写入后：
  1. 赋予 version_id（`v{YYYYMMDD}-{seq:03d}`）
  2. 指向 parent_version（形成版本链）
  3. 不可变存储（write-once，只允许新版本覆盖）
  4. 写入 Graphiti Episode（`content` = JSON 文本）
  5. 触发 Hook `ontology.document.ingested`
```

---

## 后果

### 变得更容易
- ✅ 所有数据来源（新闻采集/手动/随机）统一格式，一次学习即可使用
- ✅ Graphiti Episode 内容即为 JSON 文本，天然支持 LLM 语义搜索
- ✅ 版本链完整，支持差异对比、回溯、审计
- ✅ `rules` 和 `constraints` 字段可直接驱动 OPA 策略生成

### 变得更难
- ❌ 所有数据写入前都需要通过 Schema 验证，增加一步处理
- ❌ 历史数据（如现有 56 条 Episode）需要迁移到新格式

## 可逆性
**中**。格式本身可迭代（通过 `$version` 字段实现向后兼容）。历史数据迁移脚本可生成。

## 相关 ADR
- ADR-036: Palantir AIP Ontology 参考架构（基础实体类型来源）
- ADR-031: 模拟器 Web 可视化与实时本体热写入（消费本格式）
- ADR-002: Graphiti 双时态知识图谱（写入目标）
