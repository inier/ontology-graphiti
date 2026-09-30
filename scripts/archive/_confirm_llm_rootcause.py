"""确认 LLM 归纳失败的根因：配置模型名无效。

在容器内运行：
    podman cp scripts/_confirm_llm_rootcause.py graphiti-dev-app:/tmp/
    podman exec graphiti-dev-app python /tmp/_confirm_llm_rootcause.py
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
model_env = get_config("llm.model", "")

print("=" * 68)
print("1. 独立进程（只加载 ENV 层）解析出的配置")
print("=" * 68)
print(f"  api_base : {api_base}")
print(f"  llm.model: {model_env}")
print(f"  api_key  : {(api_key[:6] + '...' + api_key[-4:]) if len(api_key) > 10 else repr(api_key)} (len={len(api_key)})")

# 端点可达性与模型清单
models = []
try:
    req = urllib.request.Request(api_base + "/models", headers={"Authorization": "Bearer " + api_key})
    with urllib.request.urlopen(req, timeout=25) as r:
        models = sorted(m["id"] for m in json.load(r)["data"])
    print(f"  /models  : HTTP 200，共 {len(models)} 个模型")
except Exception as e:
    print(f"  /models  : 失败 {type(e).__name__}: {e}")

print()
print("=" * 68)
print("2. 用配置中的模型名发起真实 chat 请求")
print("=" * 68)


def chat(model, timeout=90):
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 8}
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
            txt = d["choices"][0]["message"]["content"]
            return f"OK   ({time.time()-t0:5.1f}s) -> {str(txt)[:40]}"
    except urllib.error.HTTPError as e:
        body_txt = ""
        try:
            body_txt = e.read().decode()[:300]
        except Exception:
            pass
        return f"HTTP {e.code} ({time.time()-t0:5.1f}s) | {body_txt}"
    except Exception as e:
        return f"FAIL ({time.time()-t0:5.1f}s) {type(e).__name__}: {e}"


print(f"  配置值 {model_env!r}")
print(f"    -> {chat(model_env)}")
print(f"  是否在端点模型清单中: {model_env in models}")
print()

# 候选模型
candidates = [m for m in models if any(k in m for k in ("deepseek", "glm", "kimi", "gpt-oss"))]
print("=" * 68)
print("3. 候选替代模型实测")
print("=" * 68)
for m in candidates:
    print(f"  {m:34s} -> {chat(m, timeout=60)}")

print()
print("=" * 68)
print("4. ENV 变量（容器运行时真实来源）")
print("=" * 68)
import os  # noqa: E402

for k in ("OPENAI_API_BASE", "OPENAI_MODEL", "EMBEDDER_MODEL"):
    print(f"  {k:18s} = {os.getenv(k)}")
