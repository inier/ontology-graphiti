---
id: odap.l7.adr-077-shacl-owl本体治理
status: active
owner: architect
version: ''
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

# ADR-077: SHACL/OWL 本体治理（双轨制）

## 状态

**Accepted**（2026-08-20，经 grilling 四轮裁决）

> **Superseded in part by [ADR-085](ADR-085_SHACL形状持久化与写路径校验不变量.md)（2026-10-04，提议）**：本 ADR 裁决 1「派生不持久化」的边界被 ADR-085 扩展——形状改为落「带 Schema 版本号失效键的派生缓存表 `sa_shacl_shape`」（裁决 1 本就允许带版本失效键的缓存，故为操作化而非推翻；单一事实源仍是类型定义 + usl 约束 + L6 公理）。裁决 3「校验输入显式传入、不读 Neo4j」保持不变，ADR-085 的写路径校验点把「即将写入的实例」显式递给校验器。其余决策（双轨制、模块布局、OWL 导入 HITL、依赖 pin）不受影响。

## 上下文

ODAP 使用自定义 Schema 格式（ADR-032 `OntologyDocument` JSON）作为本体内部主格式，但存在两个缺口：

1. **无 SHACL 约束**：本体定义的属性/关系约束（必填、类型、基数、范围）仅存在于自定义 Schema 中，无标准约束校验层，实例数据合规检查依赖应用层手工实现。
2. **无 OWL 互操作**：无法与标准本体生态（Protégé、RDF 工具链、外部知识图谱）互操作，导入/导出困难。

参考行业实践：W3C SHACL（Shapes Constraint Language）是 RDF 图数据的约束校验标准；OWL（Web Ontology Language）是本体语义表达与推理标准。Palantir AIP 本体通过本体元数据映射到 SHACL/OWL 实现治理与互操作。

## 决策

### 1. 双轨制原则

**自定义 Schema 是单一事实源（single source of truth）**，SHACL 与 OWL 均由它**自动派生**，禁止人工双写：

```
自定义 Schema (ADR-032, 内部主格式)
        │ 自动派生（单向）
        ├──→ SHACL Shapes（约束校验用）
        └──→ OWL/Turtle（互操作用）
```

派生是**单向**的（Schema → SHACL/OWL），反向导入（OWL → Schema）作为**互操作入口**单独处理（见 §4）。

### 2. 模块落位

```
biz/core/ontology/design/engine/
├── shacl/                        # ★新增
│   ├── shape_generator.py        #   自定义 Schema → SHACL Shape 自动生成
│   ├── validator.py              #   pySHACL 验证（实例数据合规检查）
│   └── api 暴露: POST /api/ontology/{id}/shacl/validate
├── owl/                          # ★新增
│   ├── owl_exporter.py           #   owlready2: Schema → OWL/Turtle 导出
│   └── owl_importer.py           #   标准本体导入（互操作）
└── (现有 schema 引擎不动 —— 内部主格式)
```

### 3. Schema → SHACL Shape 映射规则

自定义 Schema 的约束映射为 SHACL shape：

| 自定义 Schema 约束 | SHACL 约束组件 | 说明 |
|---|---|---|
| `properties[].required = true` | `sh:minCount 1` | 必填属性 |
| `properties[].data_type` | `sh:datatype` | 数据类型（string/integer/float/boolean/date/datetime） |
| `relations[].cardinality` | `sh:minCount` / `sh:maxCount` | 1:1→[1,1]、1:N→[1,∞]、N:1→[1,1]、N:N→[0,∞] |
| `relations[].link_type = composition` | `sh:nodeKind sh:IRI` | 组合关系目标必须是 IRI 节点（避免目标实例需额外声明 rdf:type） |
| `classification_level` | **不映射**（密级元数据） | 密级是属性元数据非值约束，属数据分类模块职责（ADR-077 §5 边界） |
| 主键 `primary_key` | `sh:minCount 1`（降级） | 唯一性约束；跳过已在 properties 定义的字段避免 path 重复 |

Shape 生成**确定性、可测试**：同一 Schema 输入 → 相同 Shape 输出。

### 4. OWL 导出/导入

- **导出**：`owlready2` 将自定义 Schema 实体类型/关系/属性导出为 OWL 类/对象属性/数据属性，序列化为 Turtle（`.ttl`）。
- **导入**：`owl_importer` 解析标准 OWL 本体，映射回自定义 Schema（作为互操作入口），导入结果进质量闸人工确认（HITL），不直接覆盖内部主格式。

### 5. 质量闸联动

质量闸（ADR-061 16 子指标）新增 **"SHACL 合规率"** 指标：实例数据经 pySHACL 验证的通过率，纳入语义管理台质量闸看板。

### 6. 技术选型

| 能力 | 选型 | 版本约束 | 理由 |
|---|---|---|---|
| SHACL 验证 | `pySHACL` | ≥0.25 | 标准实现、活跃维护、支持 SHACL Core |
| OWL 操作 | `owlready2` | ≥0.46 | Python 原生 OWL、与 RDFLib 集成 |
| RDF 序列化 | `rdflib` | ≥7.0 | SHACL/OWL 底层三元组存储与序列化 |

依赖治理：进 `apps/api/pyproject.toml` + `uv.lock`，镜像需 `rebuild main`。

### 7. 与现有能力边界

- **与 ADR-075 推理引擎正交**：SHACL 是**约束校验**（数据合规），Datalog 是**规则演绎**（业务推理），职责不重叠。
- **与 ADR-061 质量闸协同**：SHACL 合规率作为质量闸新指标，校验失败进质量闸 HITL 飞轮。

## 后果

### 正面
- 实例数据合规检查标准化，替代手工应用层校验
- 本体可导入/导出标准 OWL，与外部生态互操作
- 双轨制保证内部主格式不变，无迁移成本

### 负面与缓解
- 新增 3 个依赖（pySHACL/owlready2/rdflib），镜像体积增加 → 缓解：均为纯 Python 包，按需加载
- SHACL/OWL 派生需覆盖全部 Schema 约束类型，工作量 → 缓解：映射规则确定性可测试，TDD 驱动

## 可逆性

**高**。双轨制单向派生，SHACL/OWL 为旁路产物，移除不影响内部主格式与写入路径。

## Grilling 裁决（2026-08-20）

### 裁决 1：派生一致性防漂移（§1 双轨制）

**问题**：Schema → SHACL/OWL 单向派生，若 Schema 变更后派生产物未同步，会导致校验/互操作漂移。

**裁决**：派生**不持久化**——SHACL Shape 与 OWL 每次按需（validate/export 请求时）从当前 Schema 实时生成，杜绝陈旧副本。任何缓存（如有）必须带 Schema 版本号失效键。单一事实源原则由此得到硬保证。

### 裁决 2：OWL 导入反向映射的安全与 HITL（§4）

**问题**：`owl_importer` 将外部 OWL 映射回自定义 Schema，可能引入恶意/冲突定义。

**裁决**：导入结果**不直接入库**——产出 Schema 候选（草稿），经质量闸（ADR-061）与 HITL 人工确认后方可写回内部主格式。导入器仅做**结构映射**（类→实体类型、对象属性→关系、数据属性→属性），语义约束（OWL 公理）降级为 `semantic_hints` 元数据，不自动转约束。导入过程全程审计（ADR-074）。

### 裁决 3：SHACL 校验的实例数据来源（§3）

**问题**：pySHACL 校验需要 RDF 化的实例数据，但 ABox 存储在 Neo4j。

**裁决**：校验输入为**显式传入的实例数据**（JSON 或已 RDF 化的图），由 `validator.py` 负责将实例 JSON → RDF 临时图（rdflib）→ 套用生成的 SHACL shape 校验。**不直接读 Neo4j**（避免跨层耦合与性能风险）。API 接受 `instances` 数组或 `data_graph` 引用。校验结果（符合/违反+具体 shape 定位）返回结构化报告，供质量闸"HITL 飞轮"消费。

### 裁决 4：owlready2 依赖兼容性

**问题**：owlready2 依赖较重，且对 Python 3.10-3.13 兼容性需确认。

**裁决**：OWL 导出/导入**按需延迟加载**（lazy import），owlready2 不可用时降级为 rdflib 纯 RDF 序列化（Turtle 文本输出仍可用）。owlready2 仅用于需要 OWL 语义操作的场景（类层次推理），纯序列化需求走 rdflib。依赖版本 pin：pySHACL≥0.25、owlready2≥0.46、rdflib≥7.0。

## 关联

- ADR-032（本体格式，内部主格式）
- ADR-061（质量闸，新增 SHACL 合规率指标）
- ADR-068（L1 Design 层，SHACL/OWL 落位）
- ADR-075（推理引擎，正交边界）

## References

- [SHACL W3C 规范](https://www.w3.org/TR/shacl/)
- [OWL 2 W3C 规范](https://www.w3.org/TR/owl2-overview/)
- [pySHACL](https://github.com/RDFLib/pySHACL)
- [owlready2](https://owlready2.readthedocs.io/)
