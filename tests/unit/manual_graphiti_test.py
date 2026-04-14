#!/usr/bin/env python3
"""Graphiti 集成测试 - 手动验证脚本"""
import asyncio
import os
import sys

sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from core.llm_clients import ZhipuAIClient

api_key = os.getenv('OPENAI_API_KEY', '')
api_base = os.getenv('OPENAI_API_BASE', '')
api_model = os.getenv('OPENAI_MODEL', '')
neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
neo4j_password = os.getenv('NEO4J_PASSWORD', '')

print(f'API Base: {api_base}')
print(f'Model: {api_model}')
print(f'Neo4j: {neo4j_uri}')

# 智能构造 embedder base_url：从 api_base 提取到 /v1 级别
# OpenAI SDK 的 embeddings.create() 会自动拼接 /embeddings，所以 base_url 不应包含它
raw_base = api_base.rstrip('/')
if '/chat/completions' in raw_base:
    embed_base = raw_base.split('/chat/completions')[0]
else:
    embed_base = raw_base.rstrip('/')
print(f'Embedder Base: {embed_base}')

llm_config = LLMConfig(
    model=api_model,
    api_key=api_key,
    base_url=api_base,
    temperature=0.7
)
llm_client = ZhipuAIClient(config=llm_config)

embedder_config = OpenAIEmbedderConfig(
    api_key=api_key,
    base_url=embed_base,
    embedding_model="Pro/BAAI/bge-m3"
)
embedder = OpenAIEmbedder(config=embedder_config)

async def test():
    g = Graphiti(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
    )
    print("✅ Graphiti instance created")

    print("🔨 Building indices...")
    await g.build_indices_and_constraints(delete_existing=False)
    print("✅ Indices built!")

    # 写入一个测试 Episode
    from datetime import datetime, timezone
    print("📝 Adding test episode...")
    result = await g.add_episode(
        name="TEST_EPISODE_001",
        episode_body="TEST_EPISODE_001 是一个测试步兵单位，隶属于蓝方阵营，驻扎在A区，兵力120人。",
        source_description="测试数据",
        reference_time=datetime.now(timezone.utc),
        update_communities=False
    )
    print(f"✅ Episode added: {result}")

    # 关闭并重新打开，确保索引刷新
    g.close()
    print("🔄 Reopening connection...")
    g = Graphiti(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
    )

    # 查询
    print("🔍 Retrieving episodes...")
    episodes = await g.retrieve_episodes(reference_time=datetime.now(timezone.utc))
    print(f"✅ Retrieved {len(episodes)} episodes")
    for ep in episodes[:3]:
        print(f"  - {getattr(ep, 'name', '?')}: {getattr(ep, 'episode_body', '')[:60]}...")

    # 搜索
    print("🔎 Searching for '蓝方 步兵'...")
    results = await g.search(query="蓝方 步兵", num_results=3)
    print(f"✅ Search returned {len(results)} results")

    g.close()
    print("\n🎉 All checks passed!")

if __name__ == "__main__":
    asyncio.run(test())
