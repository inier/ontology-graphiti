"""最终验收：调用项目真实的 LLM归纳阶段处理器（LLMExtractionStageHandler）。

这是「LLM归纳失败」问题的直接对照测试：
  - 修复前：410 Gone / asyncio 30s 超时 → success=False
  - 修复后：应 success=True，且 entities/relations/events 有值
"""
import asyncio
import sys

sys.path.insert(0, "/app/apps/api")

# 关键：先实例化 ConfigManager，使其把 DB 层注入 ConfigurationComposer，
# 以复现 app 进程内的配置解析结果（独立进程默认只有 ENV 层）。
from odap.biz.platform.config.impl.config_manager import ConfigManager  # noqa: E402

mgr = ConfigManager.get_instance()
from odap.infra.config_composer import get_config  # noqa: E402

print("=" * 74)
print("配置解析结果（模拟 app 进程：DB 层已注入）")
print("=" * 74)
print(f"  llm.model    = {get_config('llm.model')!r}")
print(f"  llm.api_base = {get_config('llm.api_base')!r}")
key = get_config("llm.api_key", "") or ""
print(f"  llm.api_key  = {(key[:6] + '...' + key[-4:]) if len(key) > 12 else repr(key)} (len={len(key)})")
import os  # noqa: E402

print(f"  ENV OPENAI_MODEL = {os.getenv('OPENAI_MODEL')!r}")

TEXT = (
    "2026年5月18日凌晨，东海舰队派出驱逐舰编队，在东海海域执行代号「海燕」的巡航任务。"
    "编队由「南昌舰」担任旗舰，「杭州舰」协同护航。任务期间，编队与空军某部实施了联合演练。"
)

print()
print("=" * 74)
print("执行 LLMExtractionStageHandler.execute()  —— 即界面上的「LLM归纳」")
print("=" * 74)

from odap.biz.core.ontology.design.services.pipeline_service import (  # noqa: E402
    LLMExtractionStageHandler,
    PipelineContext,
)


async def main():
    ctx = PipelineContext(
        ingest_id="verify-llm-induction",
        scenario_id="verify-scenario",
        source="manual",
        original_content=TEXT,
    )
    handler = LLMExtractionStageHandler()
    t0 = asyncio.get_event_loop().time()
    ok = await handler.execute(ctx)
    el = asyncio.get_event_loop().time() - t0

    print(f"  耗时      : {el:.1f}s")
    print(f"  success   : {ok}")
    print(f"  context.err: {ctx.error}")

    res = ctx.stage_results.get("llm", {})
    print(f"  entities  : {res.get('entities_count')}")
    print(f"  relations : {res.get('relations_count')}")
    print(f"  events    : {res.get('events_count')}")

    ents = res.get("entities") or []
    if ents:
        print(f"  实体样例  : {[e.get('name') for e in ents][:6]}")

    print()
    print("=" * 74)
    print("本阶段写入的 process_logs")
    print("=" * 74)
    for lg in ctx.logs:
        stage = getattr(lg.stage, "value", lg.stage)
        status = getattr(lg.status, "value", lg.status)
        print(f"  [{stage}] {lg.operation} -> {status}  err={lg.error_message}")

    print()
    print("结论:", "✅ LLM归纳成功" if ok else "❌ LLM归纳仍然失败")


asyncio.run(main())
