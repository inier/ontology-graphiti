"""Deprecated — ADR-067: biz/shared → infra/storage/

ScenarioStore 已迁移到 odap.infra.storage.scenario_store。
此模块仅保留向后兼容重定向，下个版本删除。
"""

import warnings


def __getattr__(name):
    if name in ("ScenarioStore", "scenario_store"):
        warnings.warn(
            f"odap.biz.shared.{name} is deprecated. "
            f"Use odap.infra.storage.scenario_store instead. (ADR-067)",
            DeprecationWarning,
            stacklevel=2,
        )
        from odap.infra.storage.scenario_store import ScenarioStore, scenario_store
        return {"ScenarioStore": ScenarioStore, "scenario_store": scenario_store}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
