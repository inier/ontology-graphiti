"""两阶段模型筛选。

阶段1（快速探活）：小 prompt，40s 超时。判定 model 是否可用 + 答案是否落在 content 字段。
阶段2（抽取验收）：仅对阶段1通过者，做本体抽取 JSON 验收。

背景：项目客户端 odap/infra/llm/llm_service.py 只读
      result['choices'][0]['message']['content']，不处理 reasoning_content，
      因此「答案只在 reasoning_content」的模型对本项目不可用。
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

POOL = [
    # instruct 类（非推理）—— 最可能有干净的 content
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/nemotron-4-340b-instruct",
    "nvidia/llama3-chatqa-1.5-70b",
    "ai21labs/jamba-1.5-large-instruct",
    "ibm/granite-3.0-8b-instruct",
    "mistralai/mixtral-8x22b-v0.1",
    "mistralai/mistral-nemotron",
    "meta/muse-glimmer-30b",
    # 推理类 —— 复测（可能瞬时 503）
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-super-120b-a12b",
    "z-ai/glm-5.3-flash",
    "openai/gpt-oss-20b",
]

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


def call(model, prompt, max_tokens=64, timeout=40):
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
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
            return json.load(r), time.time() - t0, None
    except urllib.error.HTTPError as e:
        try:
            b = e.read().decode()[:160]
        except Exception:
            b = ""
        return None, time.time() - t0, f"HTTP {e.code} {b}"
    except Exception as e:
        return None, time.time() - t0, f"{type(e).__name__}: {e}"


print("=" * 80)
print("阶段 1：快速探活（40s 超时，prompt=回复两个字：可用）")
print("=" * 80)
survivors = []
for m in POOL:
    d, el, err = call(m, "回复两个字：可用")
    if d is None:
        print(f"  {m:48s} X  {el:5.1f}s  {err}")
        continue
    msg = d.get("choices", [{}])[0].get("message", {})
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or "").strip()
    if content:
        print(f"  {m:48s} OK {el:5.1f}s  content={content[:24]!r}")
        survivors.append(m)
    elif reasoning:
        print(f"  {m:48s} ~  {el:5.1f}s  仅 reasoning_content（本项目不可用）")
    else:
        print(f"  {m:48s} ?  {el:5.1f}s  空响应 finish={d.get('choices',[{}])[0].get('finish_reason')}")

print()
print("=" * 80)
print(f"阶段 2：本体抽取 JSON 验收（存活 {len(survivors)} 个）")
print("=" * 80)
for m in survivors:
    d, el, err = call(m, EXTRACT_PROMPT, max_tokens=1200, timeout=120)
    if d is None:
        print(f"  {m:48s} X  {el:5.1f}s  {err}")
        continue
    msg = d.get("choices", [{}])[0].get("message", {})
    content = (msg.get("content") or "").strip()
    tok = d.get("usage", {}).get("completion_tokens")
    if not content:
        print(f"  {m:48s} X  空 content ({el:.1f}s, {tok} tok)")
        continue
    raw = content
    mm = re.search(r"```(?:ja|json)?\s*(.*?)```", content, re.S)
    if mm:
        raw = mm.group(1).strip()
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"  {m:48s} !  JSON 非法 ({el:.1f}s, {tok} tok) {e} | {content[:110]!r}")
        continue
    ne = len(data.get("entities", []))
    nr = len(data.get("relations", []))
    nv = len(data.get("events", []))
    print(f"  {m:48s} PASS ({el:.1f}s, {tok} tok) e={ne} r={nr} v={nv}")
