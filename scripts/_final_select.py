"""定向复测：确定最终可用模型。

关注点：
- mistral-nemotron 抽取耗时 109s，而客户端 httpx 超时是 120s → 擦边，需复测确认
- nano-omni 之前 503（Worker limit 16/16）→ 单发复测，判断是瞬时负载还是长期限流
- gpt-oss-20b 之前 content 为空、1200 tok 全被 reasoning 吃掉 → 用 max_tokens=4000 复测
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/app/apps/api")
from odap.infra.config_composer import get_config  # noqa: E402

API_KEY = get_config("llm.api_key", "")
API_BASE = get_config("llm.api_base", "").rstrip("/")

TEXT = (
    "2026年5月18日凌晨，东海舰队派出驱逐舰编队，在东海海域执行代号「海燕」的巡航任务。"
    "编队由「南昌舰」担任旗舰，「杭州舰」协同护航。任务期间，编队与空军某部实施了联合演练。"
)

EXTRACT_PROMPT = f"""你是本体抽取引擎。从下面的文本中抽取实体、关系、事件，并严格以 JSON 输出。

输出格式（不要输出任何解释，不要用 Markdown 代码块）：
{{
  "entities": [{{"name": "实体名", "entity_type": "类型"}}],
  "relations": [{{"source": "源实体", "target": "目标实体", "relation_type": "关系类型"}}],
  "events": [{{"name": "事件名", "event_type": "类型", "time": "时间"}}]
}}

文本：
{TEXT}
"""

CLIENT_TIMEOUT = 120.0  # 与 odap/infra/llm/llm_service.py 保持一致


def run(label, model, max_tokens=4000, timeout=200):
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": EXTRACT_PROMPT}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }
    ).encode()
    req = urllib.request.Request(
        API_BASE + "/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            b = e.read().decode()[:180]
        except Exception:
            b = ""
        print(f"  [{label}] HTTP {e.code} ({time.time()-t0:.1f}s) {b}")
        return
    except Exception as e:
        print(f"  [{label}] FAIL ({time.time()-t0:.1f}s) {type(e).__name__}: {e}")
        return

    el = time.time() - t0
    msg = d.get("choices", [{}])[0].get("message", {})
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or "").strip()
    usage = d.get("usage", {})
    finish = d.get("choices", [{}])[0].get("finish_reason")

    risk = "  <== 超出客户端 120s 超时!" if el > CLIENT_TIMEOUT else ""
    if not content:
        print(
            f"  [{label}] 空 content ({el:.1f}s, tok={usage.get('completion_tokens')}, "
            f"finish={finish}, reasoning_len={len(reasoning)})"
        )
        return

    raw = content
    mm = re.search(r"```(?:json)?\s*(.*?)```", content, re.S)
    if mm:
        raw = mm.group(1).strip()
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"  [{label}] JSON 非法 ({el:.1f}s) {e} | {content[:120]!r}")
        return
    ne, nr, nv = (
        len(data.get("entities", [])),
        len(data.get("relations", [])),
        len(data.get("events", [])),
    )
    print(f"  [{label}] PASS ({el:.1f}s, tok={usage.get('completion_tokens')}) e={ne} r={nr} v={nv}{risk}")


print("=== mistralai/mistral-nemotron 可复现性（连续 2 次）===")
run("nemotron #1", "mistralai/mistral-nemotron")
run("nemotron #2", "mistralai/mistral-nemotron")

print()
print("=== nvidia/nemotron-3-nano-omni-30b-a3b-reasoning 单发复测 ===")
run("nano-omni", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")

print()
print("=== openai/gpt-oss-20b（max_tokens=4000）===")
run("gpt-oss", "openai/gpt-oss-20b")
