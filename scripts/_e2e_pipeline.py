"""端到端复现：完全按 pipeline_service._extract_with_llm 的调用方式。

验证两件事：
1. 用配置中的模型名（deepseek-ai/deepseek-v4-flash）→ 复现 410
2. 换成 openai/gpt-oss-20b 后：
   a. 在 pipeline 的 30s 硬超时下 → 超时失败（证明第二层根因）
   b. 放宽超时后 → 成功（证明模型可用）
"""
import asyncio
import sys
import time

sys.path.insert(0, "/app/apps/api")

from odap.infra.config_composer import get_config  # noqa: E402

TEXT = (
    "2026年5月18日凌晨，东海舰队派出驱逐舰编队，在东海海域执行代号「海燕」的巡航任务。"
    "编队由「南昌舰」担任旗舰，「杭州舰」协同护航。任务期间，编队与空军某部实施了联合演练。"
)

PROMPT = f"""从以下文本中提取实体、关系、事件和动作，并以JSON格式返回。

文本内容：
{TEXT}

请以以下JSON格式返回（只需返回JSON，不要其他内容）：
{{
    "entities": [{{"entity_id": "实体ID", "entity_type": "Unit|Location|Equipment|Event", "name": "名称"}}],
    "relations": [{{"relation_id": "关系ID", "relation_type": "located_at|attached_to", "source_entity": "源", "target_entity": "目标"}}],
    "events": [{{"event_id": "事件ID", "event_type": "contact|movement", "location": "地点", "description": "描述"}}],
    "actions": [{{"action_id": "动作ID", "action_type": "move|engage", "actor": "执行者ID", "target": "目标ID"}}]
}}
"""


def build_client(model_override=None):
    from graphiti_core.llm_client.config import LLMConfig
    from odap.infra.llm.llm_service import ZhipuAIClient

    api_key = get_config("llm.api_key", "")
    api_base = get_config("llm.api_base", "https://open.bigmodel.cn/api/paas/v4")
    model = model_override or get_config("llm.model", "glm-4")
    cfg = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.7)
    return ZhipuAIClient(config=cfg), model


async def attempt(model_override, timeout, label):
    from graphiti_core.prompts.models import Message

    client, model = build_client(model_override)
    messages = [Message(role="user", content=PROMPT)]
    t0 = time.time()
    try:
        result, _, _ = await asyncio.wait_for(
            client._generate_response(messages), timeout=timeout
        )
    except asyncio.TimeoutError:
        print(f"  [{label}] asyncio 超时 ({time.time()-t0:.1f}s > {timeout}s)  model={model}")
        return
    except Exception as e:
        msg = str(e)
        head = msg[:170].replace("\n", " ")
        print(f"  [{label}] 异常 ({time.time()-t0:.1f}s) {type(e).__name__}: {head}")
        return

    el = time.time() - t0
    if not result:
        print(f"  [{label}] 返回空 dict ({el:.1f}s)  model={model}")
        return
    ne = len(result.get("entities", []) or [])
    nr = len(result.get("relations", []) or [])
    nv = len(result.get("events", []) or [])
    na = len(result.get("actions", []) or [])
    print(f"  [{label}] PASS ({el:.1f}s) model={model} e={ne} r={nr} v={nv} a={na}")


async def main():
    print("=" * 78)
    print("A) 配置中的模型 + 30s（pipeline 真实超时）")
    print("=" * 78)
    await attempt(None, 30.0, "配置模型/30s")

    print()
    print("=" * 78)
    print("B) openai/gpt-oss-20b + 30s（pipeline 真实超时）")
    print("=" * 78)
    await attempt("openai/gpt-oss-20b", 30.0, "gpt-oss/30s")

    print()
    print("=" * 78)
    print("C) openai/gpt-oss-20b + 120s（放宽超时）")
    print("=" * 78)
    await attempt("openai/gpt-oss-20b", 120.0, "gpt-oss/120s")


asyncio.run(main())
