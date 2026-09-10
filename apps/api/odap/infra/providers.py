"""跨层依赖倒置 provider 注册表 —— C4 分层 seam。

背景（ADR-081 · Stage I）：
    分层架构 common(叶子) ← infra ← biz ← web(顶层)。C4 契约禁止 infra 直接 import biz。
    但部分 infra 组件（统一查询服务的 source 适配器）在运行期确实需要 biz 层的服务实例
    （OMS 服务、语义检索器、设计契约等）。历史上的做法是在 infra 里写「惰性 biz import」
    作为默认协作者——这构成 infra→biz 的直接依赖边，违反 C4。

机制（依赖倒置）：
    - infra 组件不再 import biz，改为向本注册表按名解析协作者：`resolve_provider("oms_service")`。
    - biz 在组合根启动时把「工厂函数」注册进本表（`odap.biz.providers_bootstrap`）。
      biz→infra 是合法的下行依赖，故注册方向不违反 C4。
    - 注册的是工厂（闭包，内部惰性 import biz），因此注册本身零开销、不触发 biz 重载。

失败语义（规则 14：失败必须显式，禁止静默兜底）：
    解析未注册的名字直接抛 RuntimeError，附明确修复指引；绝不返回 None 或占位对象。
    调用方（infra source）保持原有「注入了协作者就用注入的，否则解析默认」语义。
"""
from typing import Any, Callable, Dict

# name -> 无参工厂函数，调用后返回一个 provider 实例
_PROVIDER_FACTORIES: Dict[str, Callable[[], Any]] = {}


def register_provider(name: str, factory: Callable[[], Any]) -> None:
    """注册一个 provider 工厂。

    由 biz 侧（`odap.biz.providers_bootstrap`）在组合根导入时调用。
    重复注册同名 provider 以后者为准（允许测试覆盖）。
    """
    if not callable(factory):
        raise TypeError(f"provider '{name}' 的 factory 必须可调用，收到 {type(factory).__name__}")
    _PROVIDER_FACTORIES[name] = factory


def resolve_provider(name: str) -> Any:
    """解析并实例化一个已注册的 provider。

    未注册则显式抛 RuntimeError（规则 14：不做静默兜底）。
    """
    factory = _PROVIDER_FACTORIES.get(name)
    if factory is None:
        raise RuntimeError(
            f"Provider '{name}' 未注册。infra 组件依赖倒置解析失败。"
            f"请确保组合根已导入 biz provider 注册模块 "
            f"(`import odap.biz.providers_bootstrap`)，或向该 source 显式注入协作者。"
            f"（规则 14：显式失败，不静默兜底。）"
        )
    return factory()


def is_registered(name: str) -> bool:
    """查询某 provider 是否已注册（供诊断/测试用）。"""
    return name in _PROVIDER_FACTORIES


def registered_names() -> tuple:
    """返回已注册 provider 名字集合（供诊断/测试用）。"""
    return tuple(sorted(_PROVIDER_FACTORIES.keys()))


def clear_providers() -> None:
    """清空注册表（仅供测试隔离使用）。"""
    _PROVIDER_FACTORIES.clear()


__all__ = [
    "register_provider",
    "resolve_provider",
    "is_registered",
    "registered_names",
    "clear_providers",
]
