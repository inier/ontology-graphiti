#!/usr/bin/env python3
"""补写失败 Episode + 查询验证（快速版）"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from core.llm_clients import ZhipuAIClient

# --- 配置 ---
api_key = os.getenv('OPENAI_API_KEY', '')
api_base = os.getenv('OPENAI_API_BASE', '')
api_model = os.getenv('OPENAI_MODEL', '')
neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
neo4j_password = os.getenv('NEO4J_PASSWORD', '')

raw_base = api_base.rstrip('/')
if '/chat/completions' in raw_base:
    embed_base = raw_base.split('/chat/completions')[0]
else:
    embed_base = raw_base.rstrip('/')

# 之前失败的 4 个 Episode
FAILED_EPISODES = [
    {
        'name': 'C区地点1',
        'body': 'C区地点1是一个城市地形区域，位于C区，坐标为(71.8, 1.2)。'
    },
    {
        'name': 'D区地点1',
        'body': 'D区地点1是一个山地地形区域，位于D区，坐标为(91.8, 28.0)。'
    },
    {
        'name': 'D区学校2',
        'body': 'D区学校2是一个学校类民用基础设施，当前状态为正常，位于B区地点1。'
    },
    {
        'name': '任务_MISSION_5',
        'body': '任务MISSION_5：攻击任务，优先级高，截止时间2026-04-11T22:14:09，当前状态为完成。任务分配给Red Force 步兵部队1，目标包括Blue Force 导弹2，任务区域在A区地点2附近。'
    },
]

QUERIES = [
    "蓝方部队部署位置",
    "红方装甲力量",
    "D区地形",
    "受损的武器系统",
    "失败的补给任务",
]


async def main():
    llm_config = LLMConfig(
        model=api_model, api_key=api_key, base_url=api_base, temperature=0.7
    )
    llm_client = ZhipuAIClient(config=llm_config)

    embedder_config = OpenAIEmbedderConfig(
        api_key=api_key, base_url=embed_base, embedding_model="Pro/BAAI/bge-m3"
    )
    embedder = OpenAIEmbedder(config=embedder_config)

    g = Graphiti(
        uri=neo4j_uri, user=neo4j_user, password=neo4j_password,
        llm_client=llm_client, embedder=embedder,
    )
    print("✅ Graphiti connected")

    # 补写失败的 Episode
    print(f"\n🔄 Re-trying {len(FAILED_EPISODES)} failed episodes...")
    success = 0
    for ep in FAILED_EPISODES:
        try:
            print(f"  Writing '{ep['name']}'...", end=' ', flush=True)
            await g.add_episode(
                name=ep['name'],
                episode_body=ep['body'],
                source_description='simulation_data/retry',
                reference_time=datetime.now(timezone.utc),
                update_communities=False
            )
            print("✅")
            success += 1
        except Exception as e:
            print(f"❌ {e}")

    print(f"  Result: {success}/{len(FAILED_EPISODES)} success")

    # 查询验证
    print(f"\n🔍 Search queries:")
    for q in QUERIES:
        try:
            results = await g.search(query=q, num_results=3)
            print(f"  '{q}' → {len(results)} results")
            for r in results[:2]:
                name = getattr(r, 'name', '?')
                fact = getattr(r, 'fact', '')[:80]
                print(f"    - {name}: {fact}...")
        except Exception as e:
            print(f"  '{q}' → ❌ {e}")

    # retrieve_episodes 验证
    print("\n📖 retrieve_episodes test:")
    try:
        eps = await g.retrieve_episodes(query="蓝方部队", num_results=5)
        print(f"  Retrieved {len(eps)} episodes")
        for ep in eps[:3]:
            print(f"    - {ep.name}: {ep.episode_body[:60]}...")
    except Exception as e:
        print(f"  ❌ {e}")

    await g.close()
    print("\n🎉 Done!")


if __name__ == "__main__":
    asyncio.run(main())
