"""决定性诊断：用 pipeline_service._extract_with_llm 的【逐字】提示词，导出原始响应。

已知：精简提示词 → entities=8；真实长提示词（经 LLMExtractionStageHandler）→ entities=0。
本脚本用逐字复刻的真实提示词，打印 finish_reason / content / reasoning，定位差异。
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, "/app/apps/api")

from odap.biz.platform.config.impl.config_manager import ConfigManager  # noqa: E402

ConfigManager.get_instance()

import httpx  # noqa: E402
from odap.infra.config_composer import get_config  # noqa: E402

TEXT = (
    "2026年5月18日凌晨，东海舰队派出驱逐舰编队，在东海海域执行代号「海燕」的巡航任务。"
    "编队由「南昌舰」担任旗舰，「杭州舰」协同护航。任务期间，编队与空军某部实施了联合演练。"
)

# 逐字复制自 pipeline_service.py:_extract_with_llm 的 prompt 构造
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
   关系类型参考：located_at, attached_to, engaged_with, adjacent_to, contains, assigned_to, participants, occurs_at

3. 事件（events）：发生的事情，包含 event_id, event_type, location, description, participants, outcome

4. 动作（actions）：文本中描述的或可推断的业务动作，包含：
   - action_id, action_type（move/engage/hold/support/withdraw/observe/communicate）
   - actor: 执行者实体ID
   - target: 目标实体ID
   - parameters: 动作参数（如destination, target_id, hold_type等）
   - opa_required: 是否需要策略审批（engage/support/withdraw为true）

请以以下JSON格式返回（只需返回JSON，不要其他内容）：
{{
    "entities": [
        {{"entity_id": "实体ID", "entity_type": "Unit|Location|Equipment|Event", "name": "名称",
          "basic_properties": {{"side": "party_a|party_b|neutral", "status": "active|deployed|destroyed", "location": "位置"}},
          "statistical_properties": {{"capability_index": 0.8, "morale": 0.7}},
          "capabilities": {{"range": 100.0}},
          "constraints": {{}}}}
    ],
    "relations": [
        {{"relation_id": "关系ID", "relation_type": "located_at|engaged_with|..", "source_entity": "源实体ID", "target_entity": "目标实体ID"}}
    ],
    "events": [
        {{"event_id": "事件ID", "event_type": "contact|engage|movement|..", "location": "地点", "description": "描述", "participants": ["实体ID"], "outcome": {{}}}}
    ],
    "actions": [
        {{"action_id": "动作ID", "action_type": "move|engage|hold|support|withdraw|observe|communicate",
          "actor": "执行者实体ID", "target": "目标实体ID",
          "parameters": {{"destination": "目标位置", "target_id": "交锋目标ID"}},
          "opa_required": false}}
    ]
}}
"""

API_KEY = get_config("llm.api_key", "")
BASE = get_config("llm.api_base", "").rstrip("/")
MODEL = get_config("llm.model", "")


def count(content):
    """按客户端的 _extract_json 逻辑解析，统计数量"""
    from odap.infra.llm.llm_service import ZhipuAIClient

    c = ZhipuAIClient(config=None)
    obj = c._extract_json(content)
    if not isinstance(obj, dict):
        return f"非 dict: {type(obj).__name__}", obj
    return (
        f"keys={sorted(obj.keys())} e={len(obj.get('entities') or [])} "
        f"r={len(obj.get('relations') or [])} v={len(obj.get('events') or [])} "
        f"a={len(obj.get('actions') or [])}",
        obj,
    )


async def run(max_tokens, temperature):
    async with httpx.AsyncClient(timeout=240.0) as hc:
        t0 = time.time()
        r = await hc.post(
            BASE + "/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": PROMPT}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        el = time.time() - t0
    d = r.json()
    ch = d.get("choices", [{}])[0]
    msg = ch.get("message", {})
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or ""
    u = d.get("usage", {})
    summary, obj = count(content)
    print(f"max_tokens={max_tokens:6d} temp={temperature}  HTTP {r.status_code}  {el:5.1f}s")
    print(f"  finish={ch.get('finish_reason')}  in={u.get('prompt_tokens')} out={u.get('completion_tokens')}")
    print(f"  content len={len(content)}  reasoning len={len(reasoning)}")
    print(f"  解析: {summary}")
    print(f"  content 前 200: {content[:200]!r}")
    if reasoning:
        print(f"  reasoning 前 200: {reasoning[:200]!r}")
    print()


async def main():
    print(f"model={MODEL}  base={BASE}")
    print("=" * 74)
    for mt, temp in ((4096, 0.7), (4096, 0.1), (16000, 0.7)):
        await run(mt, temp)


asyncio.run(main())
