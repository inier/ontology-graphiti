"""决策流程状态机（ADR-091 §5.1）

手写 dict，零新增依赖（不引 `transitions` / `python-statemachine`）。

三个派生点必须**单点实现**，前端不自行推断：
- `derive_group`：台账/队列的分组条件
- `available_operations`：队列与详情页共用的"当前可做动作"
- `GROUP_STATUSES`：待办域三态与分组的一一映射（counts 与 group 同源）
"""

from typing import Dict, List, Optional, Tuple

from odap.infra.middleware.exception_handler import ConflictError

# status -> 允许的下一跳（内部驱动，非用户动作）
ALLOWED_TRANSITIONS: Dict[str, set] = {
    "pending": {"decided", "rejected"},   # 裁决：采纳 / 驳回
    "decided": {"executing"},             # 派发执行（无"撤回采纳"）
    "executing": {"executed", "failed"},  # 执行结果回写
    "failed": {"executing"},              # 重试执行
    "executed": set(),                    # 终态
    "rejected": set(),                    # 终态
}

# 待办域：pending | decided | executing（不是单一 status！）
# group 与 counts 均由本常量派生，禁止在别处再写一遍条件
GROUP_STATUSES: Dict[str, Tuple[str, ...]] = {
    "to_resolve": ("pending",),
    "to_execute": ("decided", "executing"),
}

_GROUP_BY_STATUS = {
    status: group for group, statuses in GROUP_STATUSES.items() for status in statuses
}

_OPERATIONS_BY_STATUS: Dict[str, List[str]] = {
    "pending": ["approve", "reject"],
    "decided": ["execute"],
    "failed": ["retry"],
    "executing": [],
    "executed": [],
    "rejected": [],
}


def derive_group(status: str) -> Optional[str]:
    """status -> 队列分组；不在待办域（executed/failed/rejected）返回 None。"""
    return _GROUP_BY_STATUS.get(status)


def available_operations(status: str) -> List[str]:
    """当前可执行的操作（未知状态返回空，宁可不给按钮也不给错按钮）。"""
    return list(_OPERATIONS_BY_STATUS.get(status, []))


def queue_domain_statuses() -> Tuple[str, ...]:
    """待办域三态（服务端硬编码注入，客户端无法用 status 绕过队列语义）。"""
    return tuple(status for statuses in GROUP_STATUSES.values() for status in statuses)


def assert_transition(current: str, target: str) -> None:
    """非法迁移抛 `ConflictError`（409 + `error.code=illegal_transition`）。

    这是**可预期的客户端错误**（状态被别人抢先改了，或界面按钮给错了），
    所以必须是 409 而不是 500。也不能抛 `ValueError`：中间件会把它压成
    400 + 纯字符串 `detail`，前端拿不到 `code`，只能读会随人改的文案。
    """
    allowed = ALLOWED_TRANSITIONS.get(current)
    if allowed is None:
        raise ConflictError(f"未知的当前状态: {current}", code="illegal_transition",
                            details={"current_status": current, "target_status": target})
    if target not in allowed:
        raise ConflictError(
            f"非法状态迁移: {current} -> {target}；允许的下一跳为 {sorted(allowed) or '无（终态）'}",
            code="illegal_transition",
            details={"current_status": current, "target_status": target},
        )
