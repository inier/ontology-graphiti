"""决策领域枚举（ADR-076 §3 + ADR-091）

单独成文件的原因：`DecisionRecord` 模型已逼近 300 行硬上限，把值域定义
抽出来既便于 `status × outcome` 矩阵独立引用，也避免模型文件继续膨胀。
"""

from enum import Enum


class DecisionOutcome(str, Enum):
    """决策执行结果（ADR-076 §3：五态，ADR-091 零变更）"""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    PENDING = "pending"
    REJECTED = "rejected"


class CausalLinkType(str, Enum):
    """决策间因果边类型（ADR-076 §4.5）"""

    CAUSED_BY = "CAUSED_BY"          # 直接导致（父决策语义）
    INFLUENCED_BY = "INFLUENCED_BY"  # 弱影响（上下文参考但未直接采纳）
    PRECEDENT_FOR = "PRECEDENT_FOR"  # 先例引用留痕（旧决策 -> 新决策）


class DecisionStatus(str, Enum):
    """决策流程位置（ADR-091 §5.1）

    与 `DecisionOutcome` 职责分离：`outcome` 是执行结果，`status` 是流程位置。
    服务端产生，客户端不可写；界面 6 态不直接暴露（收敛为 5 类标签）。
    """

    PENDING = "pending"      # 待裁决（进队列）
    DECIDED = "decided"      # 已裁决，待执行
    EXECUTING = "executing"  # 执行中
    EXECUTED = "executed"    # 已执行完毕
    FAILED = "failed"        # 执行失败（可重试）
    REJECTED = "rejected"    # 已否决（终态）


class DecisionEntrySource(str, Enum):
    """决策入口来源（ADR-091 A3）

    `LEGACY` 表示迁移前就存在的记录，来源不可考——不伪装成 `manual`。
    """

    MANUAL = "manual"
    PIPELINE = "pipeline"
    RECOMMENDATION = "recommendation"
    QA = "qa"
    AGENT = "agent"
    IMPORT = "import"
    LEGACY = "legacy"
