"""诊断：为何 LLM 归纳返回 0 实体。

假设：pipeline 提示词输出量大（entity_id + basic/statistical/capabilities/constraints + relations
     + events + actions），而 _generate_response 默认 max_tokens=4096，对推理模型 gpt-oss-20b
     来说思维链会用掉大部分配额 → 正式 JSON 被截断 → _extract_json 解析失败 → 空结果。

方法：用 pipeline 的真实提示词，在不同 max_tokens 下调用，观察 finish_reason 与产出。
"""
import asyncio
import sys
import time

sys.path.insert(0, "/app/apps/api")

from odap.biz.platform.config.impl.config_manager import ConfigManager  # noqa: E402

ConfigManager.get_instance()

from odap.infra.config_composer import get_config  # noqa: E402
from odap.infra.llm.llm_service import ZhipuAIClient  # noqa: E402
from graphiti_core.llm_client.config import LLMConfig  # noqa: E402
from graphiti_core.prompts.models import Message  # noqa: E402

TEXT = (
    "2026年5月18日凌晨，东海舰队派出驱逐舰编队，在东海海域执行代号「海燕」的巡航任务。"
    "编队由「南昌舰」担任旗舰，「杭州舰」协同护航。任务期间，编队与空军某部实施了联合演练。"
)

PROMPT = f"""从以下文本中提取实体、关系、事件和动作，并以JSON格式返回。

文本内容：
{TEXT}

请提取：
1. 实体（entities）：包括单位(Unit)、位置(Location)、装备(Equipment)、事件(Event)等，每个实体包含：
   - entity_id, entity_type, name
   - basic_properties: 基本属性（如side, status, location, coordinates）
   - statistical_properties: 统计属性（如capability_index, morale, supply_level, attrition_rate）
   - capabilities: 能力属性（如range, penetration_capacity, defense_capability）
   - constraints: 约束属性（如max_speed, min_supply）

2. 关系（relations）：实体之间的关系，包含 relation_id, relation_type, source_entity, target_entity

3. 事件（events）：发生的事情，包含 event_id, event_type, location, description, participants, outcome

4. 动作（actions）：文本中描述的或可推断的业务动作，包含 action_id, action_type, actor, target, parameters, opa_required

请以以下JSON格式返回（只需返回JSON，不要其他内容）：
{{
    "entities": [{{"entity_id": "ID", "entity_type": "Unit|Location|Equipment|Event", "name": "名称"}}],
    "relations": [{{"relation_id": "ID", "relation_type": "located_at", "source_entity": "源", "target_entity": "目标"}}],
    "events": [{{"event_id": "ID", "event_type": "contact", "location": "地点", "description": "描述"}}],
    "actions": [{{"action_id": "ID", "action_type": "move", "actor": "执行者", "target": "目标"}}]
}}
"""


def make_client():
    cfg = LLMConfig(
        model=get_config("llm.model", ""),
        api_key=get_config("llm.api_key", ""),
        base_url=get_config("llm.api_base", ""),
        temperature=0.7,
    )
    return ZhipuAIClient(config=cfg)


async def probe(api_key_direct, max_tokens, label):
    import httpx
    import json as _json

    client = make_client()
    if api_key_direct:
        client.api_key = api_key_direct  # 绕过解密，直接用 ENV 明文

    messages = [Message(role="user", content=PROMPT)]
    t0 = time.time()
    try:
        result, pt, ct = await asyncio.wait_for(
            client._generate_response(messages, max_tokens=max_tokens), timeout=180.0
        )
    except Exception as e:
        print(f"  [{label}] 异常 ({time.time()-t0:.1f}s) {type(e).__name__}: {str(e)[:150]}")
        return
    el = time.time() - t0
    ents = (result or {}).get("entities", []) or []
    rels = (result or {}).get("relations", []) or []
    evs = (result or {}).get("events", []) or []
    print(f"  [{label}] {el:.1f}s  tokens(in={pt}, out={ct})  entities={len(ents)} relations={len(rels)} events={len(evs)}")
    if ents:
        print(f"      实体: {[e.get('name') for e in ents][:6]}")


async def main():
    import os

    print("=" * 76)
    print("对照：客户端走 get_config（当前已修复）")
    print("=" * 76)
    await probe(None, 4096, "get_config/4096")

    print()
    print("=" * 76)
    print("直接观察 HTTP 层：不同 max_tokens 下的 finish_reason 与输出体量")
    print("=" * 76)
    import json as _json

    import httpx

    api_key = get_config("llm.api_key", "")
    base = get_config("llm.api_base", "").rstrip("/")
    model = get_config("llm.model", "")

    async with httpx.AsyncClient(timeout=180.0) as hc:
        for mt in (4096, 12000, 24000):
            t0 = time.time()
            r = await hc.post(
                base + "/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": PROMPT}],
                      "temperature": 0.7, "max_tokens": mt},
            )
            el = time.time() - t0
            d = r.json()
            ch = d.get("choices", [{}])[0]
            msg = ch.get("message", {})
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or ""
            u = d.get("usage", {})
            print(
                f"  max_tokens={mt:6d}  HTTP {r.status_code}  {el:5.1f}s  "
                f"finish={ch.get('finish_reason')}  in={u.get('prompt_tokens')} out={u.get('completion_tokens')}"
            )
            print(f"      content len={len(content)}  reasoning len={len(reasoning)}")
            print(f"      content 开头: {content[:100]!r}")


asyncio.run(main())
