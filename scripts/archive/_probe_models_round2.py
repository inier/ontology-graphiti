"""第二轮探针：在 NVIDIA 端点找出「账号已开通且可用」的模型。

关键点：
- /models 返回的是目录，不代表账号已开通（部分返回 404 Function not found for account）
- 冷启动可能很慢，超时放宽到 180s
- 需要区分 content / reasoning_content（推理模型）
"""
import json
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/app/apps/api")
from odap.infra.config_composer import get_config  # noqa: E402

api_key = get_config("llm.api_key", "")
api_base = get_config("llm.api_base", "").rstrip("/")

CANDIDATES = [
    "z-ai/glm-5.3-flash",
    "z-ai/glm-5.3",
    "deepseek-ai/deepseek-v4.1-flash",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "mistralai/mistral-large-2-instruct",
    "meta/muse-glimmer-30b",
    "poolside/laguna-xs-2.1",
]


def chat(model, timeout=180, prompt="用一句话说明什么是知识图谱。", max_tokens=80):
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
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
            msg = d.get("choices", [{}])[0].get("message", {})
            content = (msg.get("content") or "").strip()
            reasoning = (msg.get("reasoning_content") or "").strip()
            usage = d.get("usage", {})
            preview = (content or reasoning)[:70].replace("\n", " ")
            flag = "content" if content else ("reasoning" if reasoning else "EMPTY")
            return (
                f"OK   {time.time()-t0:6.1f}s  [{flag}] "
                f"tok={usage.get('completion_tokens')} | {preview}"
            )
    except urllib.error.HTTPError as e:
        body_txt = ""
        try:
            body_txt = e.read().decode()[:200]
        except Exception:
            pass
        return f"HTTP {e.code} {time.time()-t0:6.1f}s | {body_txt}"
    except Exception as e:
        return f"FAIL {time.time()-t0:6.1f}s {type(e).__name__}: {e}"


print("=" * 78)
print("第一轮（冷启动，timeout=180s）")
print("=" * 78)
works = []
for m in CANDIDATES:
    r = chat(m)
    print(f"  {m:46s} {r}")
    if r.startswith("OK"):
        works.append(m)

print()
print("=" * 78)
print("第二轮（热态复测，验证稳定性与真实延迟）")
print("=" * 78)
for m in works:
    r = chat(m, timeout=120)
    print(f"  {m:46s} {r}")
