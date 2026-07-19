# ADR-072: ReasoningServiceContract —— +AI Reasoning 层推理服务契约

## Status
Proposed

## Context

ADR-068 将本体模块重组为 3+1 分层架构，新增 +AI Reasoning 技术能力层。该层定位为**技术能力层**（Technical Capability Layer）而非领域层——它不引入新的领域概念，只操作已有领域对象，通过 `ReasoningServiceContract` 统一暴露推理入口。

当前 AI 增强能力散落在 4 个模块中，无统一契约：
- `assistant/rules/` — 类型推断（TypeInferenceRule）
- `cognition/` — 意图识别、知识导航
- `health/` — 跨层一致性校验
- `design/services/validation/` — Schema 校验

这导致上层模块（L1 Design、L3 Application）需要分别导入不同模块的实现类，无法统一调用，也无法替换推理引擎（规则引擎 vs LLM-based vs 混合）。定义统一契约后，所有推理能力通过 `ReasoningServiceContract` 统一暴露，tool-calling 智能体可通过 `get_reasoning_capabilities()` 动态发现可用能力。

## Decision

### 1. Frozen Dataclass Views

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass(frozen=True)
class TypeInferenceResult:
    """类型推断结果。"""
    suggestions: List[Dict[str, Any]]    # 建议的新类型定义列表
    confidence: float                    # 整体置信度 0.0-1.0
    explanation: str                     # 推理过程说明

@dataclass(frozen=True)
class ConstraintSuggestion:
    """属性约束建议。"""
    property_name: str                   # 目标属性名
    suggested_constraint: str            # 建议约束类型 (e.g. "not_null", "range", "unique", "enum")
    rationale: str                       # 建议依据
    confidence: float                    # 置信度 0.0-1.0

@dataclass(frozen=True)
class ConsistencyReport:
    """一致性校验报告。"""
    pass_count: int                      # 通过项数
    fail_count: int                      # 失败项数
    anomalies: List[Dict[str, Any]]      # 异常项列表 [{type, message, location, severity}]
    severity_distribution: Dict[str, int]  # 严重程度分布 {"error": N, "warning": M}
```

### 2. ReasoningServiceContract 抽象合约

```python
from typing import List

class ReasoningServiceContract:
    """
    +AI Reasoning 层统一推理入口（技术层契约）。

    聚合类型推断、约束建议、一致性校验等 AI 增强能力。
    所有方法返回 Frozen Dataclass Views，禁止直接引用内部实现。
    实现可替换：规则引擎 / LLM-based / 混合模式。
    """

    # ---------- 推理组：服务 L1 Design ----------
    def infer_types(self, data_sample: dict, workspace_id: str) -> TypeInferenceResult:
        """分析数据样本，建议新的实体类型。"""
        raise NotImplementedError

    def suggest_constraints(
        self, entity_type_id: str
    ) -> List[ConstraintSuggestion]:
        """分析已有实例，建议属性约束。"""
        raise NotImplementedError

    # ---------- 一致性组：服务 L2 Construction ----------
    def check_schema_consistency(self, ontology_id: str) -> ConsistencyReport:
        """Schema 级一致性校验（类型层次、约束冲突）。"""
        raise NotImplementedError

    def check_instance_consistency(
        self, entity_type_id: str, instance_ids: List[str]
    ) -> ConsistencyReport:
        """实例级一致性校验（缺失必填字段、值域违规）。"""
        raise NotImplementedError

    # ---------- 分析组：服务 L3 Application ----------
    def get_reasoning_capabilities(self) -> List[str]:
        """返回可用推理能力列表（供 tool-calling Agent 动态注册工具）。"""
        raise NotImplementedError
```

### 3. 契约矩阵中的位置

依据 ADR-068 的 3+1 契约矩阵：

```
                  L1 Design         L2 Construction    +AI Reasoning
L2 Construction  DesignContract           —                 —
+AI Reasoning    DesignContract    BuildResultContract       —
L3 Application   DesignContract    BuildResultContract   ReasoningSvcContract  ← 本 ADR
```

`ReasoningServiceContract` 的消费者是 L3 Application（AI 助手、智能体工具注册），生产者是 +AI Reasoning 层的 `UnifiedReasoningService`。

## Consequences

### 变得更容易
- AI 能力有统一契约，不再需要在 4 个模块间手动协调调用
- 推理引擎可替换：从规则引擎切换到 LLM-based 仅需更换 `UnifiedReasoningService` 实现
- `get_reasoning_capabilities()` 使 tool-calling 智能体可动态发现可用推理工具
- 新增推理能力（如关系推断、异常模式发现）只需扩展合约方法，不影响消费者

### 变得困难/需注意
- 需要适配器桥接旧代码（`assistant/rules/`、`health/`、`cognition/`）到新合约
- `TypeInferenceResult.suggestions` 和 `ConsistencyReport.anomalies` 使用 `List[Dict]` 保持灵活性，但缺失编译期类型检查
- 方法签名与 L1/L2 的 `DesignContract`、`BuildResultContract` 必须联动设计（如 `check_schema_consistency` 需要读取 DesignContract 的 Schema 定义）

### 风险与缓解
| 风险 | 等级 | 缓解 |
|------|------|------|
| 4 模块适配器桥接遗漏能力 | 中 | 逐模块迁移时编写能力清单映射测试 |
| `anomalies` 结构不稳定引起上层解析错误 | 低 | 约定 severity/type/code 为必填字段，扩展字段自由 |
| LLM-based 实现不确定性 | 中 | 保留规则引擎兜底路径，置信度 <0.5 降级为规则引擎结果 |

---
> **父决策**: [ADR-068 本体模块四层分层架构](ADR-068_本体模块四层分层架构.md) | **关联**: [ADR-071 BuildResultContract](ADR-071_BuildResultContract_构建产物契约.md)
