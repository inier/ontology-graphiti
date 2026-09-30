#!/usr/bin/env python
"""ODAP LLM 链路一体诊断工具（容器内运行）。

用途：一次性定位「LLM归纳失败 / 抽取为空 / 401 / 410 / 超时」这类问题的真实原因。
背景见 .workbuddy/memory/2026-09-28.md（三层根因：模型EOL、硬超时、密钥未持久化）。

用法:
    podman cp scripts/diagnose_llm_stack.py graphiti-dev-app:/tmp/
    podman exec graphiti-dev-app python -u /tmp/diagnose_llm_stack.py            # 基础检查
    podman exec graphiti-dev-app python -u /tmp/diagnose_llm_stack.py --screen   # + 候选模型批量筛选
    podman exec graphiti-dev-app python -u /tmp/diagnose_llm_stack.py --e2e      # + 真实 LLM归纳端到端

注意:
    - 容器重建后 /tmp 会清空，需重新 podman cp
    - Windows 下中文输出经 PowerShell 管道会乱码，建议 `| Out-File -Encoding utf8` 落盘再读
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/app/apps/api")

TEXT = (
    "2026年5月18日凌晨，东海舰队派出驱逐舰编队，在东海海域执行代号「海燕」的巡航任务。"
    "编队由「南昌舰」担任旗舰，「杭州舰」协同护航。任务期间，编队与空军某部实施了联合演练。"
)

SENSITIVE_KEYS = (
    "llm.api_key",
    "graph_db.password",
    "object_storage.access_key",
    "object_storage.secret_key",
    "auth.jwt_secret",
    "search.tavily_api_key",
)


def hdr(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------- 1. 配置
def check_config():
    hdr("1. 配置解析（复现 app 进程视角：先实例化 ConfigManager 注入 DB 层）")
    from odap.biz.platform.config.impl.config_manager import ConfigManager

    mgr = ConfigManager.get_instance()
    from odap.infra.config_composer import get_config

    print(f"  get_config llm.model    = {get_config('llm.model')!r}")
    print(f"  get_config llm.api_base = {get_config('llm.api_base')!r}")
    print(f"  get_config llm.api_key  = {get_config('llm.api_key')!r}"[:110])
    print(f"  ENV OPENAI_MODEL        = {os.getenv('OPENAI_MODEL')!r}")
    print(f"  ENV OPENAI_API_BASE     = {os.getenv('OPENAI_API_BASE')!r}")
    print(f"  ENV OPENAI_API_KEY      = {os.getenv('OPENAI_API_KEY', '')[:8]!r}...")
    print(f"  ENV CONFIG_ENCRYPTION_KEY len = {len(os.getenv('CONFIG_ENCRYPTION_KEY', ''))}")

    # 解密自检：密文形态（base64 且长）说明 CONFIG_ENCRYPTION_KEY 不匹配
    api_key = get_config("llm.api_key", "") or ""
    looks_cipher = bool(re.fullmatch(r"[A-Za-z0-9+/=]{40,}", api_key)) and "-" not in api_key
    print()
    if looks_cipher:
        print("  ❌ 严重：llm.api_key 看起来是**密文**，说明 CONFIG_ENCRYPTION_KEY 无法解密 DB 值。")
        print("     后果：密文被当作 API Key 发出 → 401 Unauthorized")
        print("     修复：持久化 CONFIG_ENCRYPTION_KEY 到 .env.docker/.env，并用它重新加密敏感项")
    else:
        print("  ✅ llm.api_key 已正确解密（非密文形态）")

    return mgr


# ---------------------------------------------------------------- 2. 端点
def check_endpoint():
    hdr("2. 端点可达性 + 模型清单")
    from odap.infra.config_composer import get_config

    api_key = get_config("llm.api_key", "")
    base = (get_config("llm.api_base", "") or "").rstrip("/")
    model = get_config("llm.model", "")
    models = []
    try:
        req = urllib.request.Request(
            base + "/models", headers={"Authorization": "Bearer " + api_key}
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            models = sorted(m["id"] for m in json.load(r)["data"])
        print(f"  /models -> HTTP 200，共 {len(models)} 个模型")
        print(f"  配置模型是否在列表中: {model in models}  ({model})")
        if model not in models:
            print("  ⚠️  不在列表中通常意味着：已 EOL / 未对本账号开通 / 名称拼写有误")
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        print(f"  /models 失败: {type(e).__name__}: {e} {body}")
    return models


# ---------------------------------------------------------------- 3. 真实调用
def chat_probe(model, prompt="回复两个字：可用", max_tokens=32, timeout=120):
    from odap.infra.config_composer import get_config

    api_key = get_config("llm.api_key", "")
    base = (get_config("llm.api_base", "") or "").rstrip("/")
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    ).encode()
    req = urllib.request.Request(
        base + "/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            b = e.read().decode()[:220]
        except Exception:
            b = ""
        return f"HTTP {e.code} ({time.time()-t0:.1f}s) | {b}"
    except Exception as e:
        return f"FAIL ({time.time()-t0:.1f}s) {type(e).__name__}: {e}"

    ch = d.get("choices", [{}])[0]
    msg = ch.get("message", {})
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or "").strip()
    u = d.get("usage", {})
    flag = "content" if content else ("仅reasoning(本项目不可用)" if reasoning else "EMPTY")
    return (
        f"HTTP 200 ({time.time()-t0:.1f}s) finish={ch.get('finish_reason')} "
        f"out={u.get('completion_tokens')} [{flag}] {content[:30]!r}"
    )


def check_configured_model():
    hdr("3. 配置模型真实 chat 探测")
    from odap.infra.config_composer import get_config

    model = get_config("llm.model", "")
    print(f"  model = {model!r}")
    print(f"    -> {chat_probe(model)}")


# ---------------------------------------------------------------- 4. 抽取验收
EXTRACT_PROMPT = f"""你是本体抽取引擎。从下面的文本中抽取实体、关系、事件，并严格以 JSON 输出。

输出格式（不要输出任何解释，不要用 Markdown 代码块）：
{{
  "entities": [{{"name": "实体名", "entity_type": "类型"}}],
  "relations": [{{"source": "源实体", "target": "实体", "relation_type": "关系类型"}}],
  "events": [{{"name": "事件名", "event_type": "类型", "time": "时间"}}]
}}

文本：
{TEXT}
"""


def check_extraction(model=None):
    hdr("4. 本体抽取 JSON 验收（结构化输出能力）")
    from odap.infra.config_composer import get_config

    model = model or get_config("llm.model", "")
    r = chat_probe(model, prompt=EXTRACT_PROMPT, max_tokens=4096, timeout=200)
    print(f"  model = {model!r}")
    print(f"    -> {r}")


def screen_models(models):
    hdr("5. 候选模型批量筛选（阶段1 探活 → 阶段2 抽取）")
    skip = ("embed", "embedqa", "rerank", "retriever", "nemoguard", "safety", "reward",
            "content-safety", "clip", "vila", "deplot", "fuyu", "kosmos", "video-detector",
            "parse", "nm", "synthetic")
    pool = [m for m in models if not any(s in m.lower() for s in skip)]
    print(f"  候选 {len(pool)} 个（已排除嵌入/安全/多模态类）")
    for m in pool:
        r = chat_probe(m, timeout=45)
        ok = r.startswith("HTTP 200") and "[content]" in r
        mark = "✅" if ok else "  "
        print(f"  {mark} {m:52s} {r}")


# ---------------------------------------------------------------- 6. 端到端
def check_e2e():
    hdr("6. 端到端：真实 LLM归纳阶段处理器")
    from odap.biz.platform.config.impl.config_manager import ConfigManager

    ConfigManager.get_instance()
    from odap.biz.core.ontology.design.services.pipeline_service import (
        LLMExtractionStageHandler,
        PipelineContext,
    )

    async def run():
        ctx = PipelineContext(
            ingest_id="diagnose-llm-induction",
            scenario_id="diagnose",
            source="manual",
            original_content=TEXT,
        )
        t0 = time.time()
        ok = await LLMExtractionStageHandler().execute(ctx)
        res = ctx.stage_results.get("llm", {})
        print(f"  耗时       : {time.time()-t0:.1f}s")
        print(f"  success    : {ok}")
        print(f"  context.err: {ctx.error}")
        print(f"  entities   : {res.get('entities_count')}")
        print(f"  relations  : {res.get('relations_count')}")
        print(f"  events     : {res.get('events_count')}")
        print()
        print("  结论:", "✅ LLM归纳成功" if ok else "❌ LLM归纳失败")
        if ok and not res.get("entities_count"):
            print("  ⚠️  成功但 0 实体：多为 max_tokens 被思维链打满导致 JSON 截断，"
                  "查日志中的「LLM 输出被 max_tokens 截断」告警")

    asyncio.run(run())


def main():
    ap = argparse.ArgumentParser(description="ODAP LLM 链路一体诊断")
    ap.add_argument("--screen", action="store_true", help="批量筛选候选模型（耗时较长）")
    ap.add_argument("--e2e", action="store_true", help="跑真实 LLM归纳阶段处理器")
    ap.add_argument("--all", action="store_true", help="等价于 --screen --e2e")
    a = ap.parse_args()

    check_config()
    models = check_endpoint()
    check_configured_model()
    check_extraction()
    if a.screen or a.all:
        screen_models(models)
    if a.e2e or a.all:
        check_e2e()

    hdr("诊断完成")
    print("  失败原因速查 → .workbuddy/memory/2026-09-28.md")


if __name__ == "__main__":
    main()
