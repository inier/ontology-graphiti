"""L3 受限 LLM 消歧：只在 L2 候选置信不足时介入。

三条硬约束（缺一条就算不上"受限"）：
1. **候选封闭**：prompt 只给 L2 产出的 top-k 候选，要求模型返回候选下标；
   返回下标越界/非法 JSON/空理由 → 视为不可用，不做「就近解释」；
2. **不可用即澄清**：端点不可达、无模型配置、超时、响应不合 schema，一律抛
   `LLMUnavailable`，由路由层降级为 `clarify_required` 并带 `INTENT_LLM_UNAVAILABLE`；
   **禁止**猜测作答、**禁止**假装调用过 L3；
3. **可观测**：每次调用把 model / endpoint / 耗时 / 原始理由写进 provenance 槽位。

客户端用 OpenAI 兼容 /chat/completions（项目既有 `llm.api_base` 配置），
只依赖 httpx，不引新库。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Sequence

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8.0
MAX_CANDIDATES = 5
INTENT_LLM_UNAVAILABLE = "INTENT_LLM_UNAVAILABLE"

_SYSTEM_PROMPT = (
    "你是意图消歧器。只能从给定候选中选择一个，或用 choice=-1 表示无法判定。"
    "禁止引入候选之外的意图。只输出 JSON，不要解释性前后缀。"
)
_SCHEMA_HINT = '{"choice": <候选下标整数，无法判定填 -1>, "confidence": <0~1>, "reason": "<=40字"}'


class LLMUnavailable(RuntimeError):
    """LLM 侧不可用/不合规响应（调用方必须降级为澄清）。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Candidate:
    """L3 只能看见这些候选。"""

    index: int
    surface: str
    intent: str
    score: float


@dataclass(frozen=True)
class LLMChoice:
    """受限消歧结果（choice_index=-1 表示模型自认无法判定）。"""

    choice_index: int
    confidence: float
    reason: str
    elapsed_ms: int
    model: str
    endpoint: str


class OpenAICompatClient:
    """最小 OpenAI 兼容客户端（JSON 对象输出）。"""

    def __init__(self, base_url: str, model: str, api_key: str = "",
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.model = model or ""
        self.api_key = api_key or ""
        self.timeout = timeout

    @property
    def endpoint(self) -> str:
        base = self.base_url
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def complete_json(self, system: str, user: str) -> Dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - httpx 是既有依赖
            raise LLMUnavailable(f"httpx 不可用: {exc}") from exc
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            response = httpx.post(self.endpoint, json=payload, headers=headers,
                                  timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 - 网络异常必须显式不可用
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if response.status_code >= 400:
            raise LLMUnavailable(f"HTTP {response.status_code}: {response.text[:160]}")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001 - 响应结构不合约定
            raise LLMUnavailable(f"响应结构异常: {type(exc).__name__}") from exc
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"非 JSON 输出: {content[:120]!r}") from exc
        if not isinstance(parsed, dict):
            raise LLMUnavailable(f"JSON 不是对象: {type(parsed).__name__}")
        return parsed


class RestrictedLLMDisambiguator:
    """受限消歧器（client 注入即可测；默认按 llm.* 配置构造）。"""

    name = "IntentLLM"
    version = "v1.0"

    def __init__(self, client=None, max_candidates: int = MAX_CANDIDATES) -> None:
        self._client = client
        self.max_candidates = max_candidates

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def endpoint(self) -> str:
        return getattr(self._client, "endpoint", "")

    @property
    def model(self) -> str:
        return getattr(self._client, "model", "")

    def disambiguate(self, query: str, candidates: Sequence[Candidate]) -> LLMChoice:
        if not candidates:
            raise LLMUnavailable("无候选，无法消歧")
        client = self._client
        if client is None:
            raise LLMUnavailable("LLM 端点未配置（需同时设置 llm.api_base / llm.model / llm.api_key）")
        visible = list(candidates)[: self.max_candidates]
        started = time.monotonic()
        try:
            raw = client.complete_json(_SYSTEM_PROMPT, self._user_prompt(query, visible))
        except LLMUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - 客户端任何异常都按不可用处理
            # 换客户端实现（非 OpenAI 兼容）时也可能抛原生异常，
            # 这里统一收敛到 LLMUnavailable，保证路由层一定走「降级澄清」而不是 500。
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        choice = raw.get("choice")
        if not isinstance(choice, int) or isinstance(choice, bool):
            raise LLMUnavailable(f"choice 非法: {choice!r}")
        if choice >= len(visible) or choice < -1:
            raise LLMUnavailable(f"choice 越界: {choice}（候选 {len(visible)} 个）")
        reason = str(raw.get("reason") or "").strip()
        if not reason:
            raise LLMUnavailable("空理由（不可审计，按不可用处理）")
        confidence = raw.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = 0.9 if choice >= 0 else 0.0
        return LLMChoice(choice_index=int(choice), confidence=float(confidence),
                         reason=reason, elapsed_ms=elapsed_ms,
                         model=self.model, endpoint=self.endpoint)

    @staticmethod
    def _user_prompt(query: str, visible: Sequence[Candidate]) -> str:
        lines = [f"问题：{query}", "候选："]
        for candidate in visible:
            lines.append(
                f"{candidate.index}. 表面形式={candidate.surface} 意图={candidate.intent} "
                f"召回分={candidate.score:.2f}"
            )
        lines.append(f"输出 JSON（schema）：{_SCHEMA_HINT}")
        return "\n".join(lines)


def build_default_disambiguator(timeout: float = DEFAULT_TIMEOUT) -> RestrictedLLMDisambiguator:
    """按项目既有 `llm.*` 配置装配（无配置 → 不可用，路由层会降级澄清）。

    可用性判定**必须包含 api_key**：`llm.api_base` / `llm.model` 在配置层都有内置默认值
    （`https://api.openai.com/v1` / `gpt-4`），只看这两项永远"已配置"，
    会让每次低置信查询都真的去连外网（8 秒超时后再降级），把澄清路径变成延迟炸弹。
    """
    try:
        from odap.infra.config_composer import get_config
    except Exception as exc:  # noqa: BLE001 - 配置层不可用即不可用
        logger.warning("L3 配置读取失败: %s", exc)
        return RestrictedLLMDisambiguator(client=None)
    base_url = str(get_config("llm.api_base", "") or "")
    model = str(get_config("llm.model", "") or "")
    api_key = str(get_config("llm.api_key", "") or "")
    if not (base_url and model and api_key):
        return RestrictedLLMDisambiguator(client=None)
    client = OpenAICompatClient(base_url=base_url, model=model, api_key=api_key,
                                timeout=timeout)
    return RestrictedLLMDisambiguator(client=client)


__all__ = [
    "Candidate",
    "INTENT_LLM_UNAVAILABLE",
    "LLMChoice",
    "LLMUnavailable",
    "OpenAICompatClient",
    "RestrictedLLMDisambiguator",
    "build_default_disambiguator",
]
