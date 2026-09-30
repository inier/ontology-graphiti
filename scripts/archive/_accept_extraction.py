"""验收测试：候选模型能否完成本体抽取（结构化 JSON 输出）。

本体归纳阶段要求模型从文本中抽取 实体/关系/事件，并返回严格 JSON。
这里用中文军事文本模拟真实场景。
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/app/apps/api")
from odap.infra.config_composer import get_config  # noqa: E402

api_key = get_config("llm.api_key", "")
api_base = get_config("llm.api_base", "").rstrip("/")

TEXT = (
    "2026年5月18日凌晨，东海舰队派出驱逐舰编队，在东海海域执行代号「海燕」的巡航任务。"
    "编队由「南昌舰」担任旗舰，「杭州舰」协同护航。任务期间，编队与空军某部实施了联合演练。"
)

PROMPT = f"""你是本体抽取引擎。从下面的文本中抽取实体、关系、事件，并严格以 JSON 输出。

输出格式（不要输出任何解释或 Markdown 代码块标记）：
{{
  "entities": [{{"name": "实体名", "entity_type": "类型"}}],
  "relations": [{{"source": "源实体", "target": "目标实体", "relation_type": "关系类型"}}],
  "events": [{{"name": "事件名", "event_type": "类型", "time": "时间"}}]
}}

文本：
{TEXT}
"""

CANDIDATES = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-super-120b-a12b",
]


def extract(model, timeout=150):
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 1200,
            "temperature": 0.1,
        }
    ).encode()
    req = urllib.request.Request(
        api_base + "/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        b = ""
        try:
            b = e.read().decode()[:200]
        except Exception:
            pass
        return f"HTTP {e.code} | {b}"
    except Exception as e:
        return f"FAIL {type(e).__name__}: {e}"

    elapsed = time.time() - t0
    msg = d.get("choices", [{}])[0].get("message", {})
    content = (msg.get("content") or "").strip()
    usage = d.get("usage", {})

    if not content:
        return f"EMPTY content ({elapsed:.1f}s)"

    # 去掉可能的 ```json ``` 包裹
    raw = content
    m = re.search(r"```(?:json)?\s*(.*?)```", content, re.S)
    if m:
        raw = m.group(1).strip()

    try:
        data = json.loads(raw)
    except Exception as e:
        return (
            f"JSON 解析失败 ({elapsed:.1f}s, {usage.get('completion_tokens')} tok): {e}\n"
            f"      原文前 260 字: {content[:260]!r}"
        )

    ne = len(data.get("entities", []))
    nr = len(data.get("relations", []))
    nv = len(data.get("events", []))
    sample = [e.get("name") for e in data.get("entities", [])][:5]
    return (
        f"✅ JSON 合法 ({elapsed:.1f}s, {usage.get('completion_tokens')} tok) "
        f"entities={ne} relations={nr} events={nv} | {sample}"
    )


for m in CANDIDATES:
    print(f"{m}")
    print(f"  -> {extract(m)}")
    print()
