#!/usr/bin/env python3
"""将 simulation_data.json 写入 Graphiti 知识图谱。

将每个战场实体（地点、部队、武器、基础设施、事件、任务）
转换为自然语言 Episode 写入 Graphiti，让 LLM 自动抽取实体和关系。
"""
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

# 智能构造 embedder base_url
raw_base = api_base.rstrip('/')
if '/chat/completions' in raw_base:
    embed_base = raw_base.split('/chat/completions')[0]
else:
    embed_base = raw_base.rstrip('/')

# 加载数据
with open('data/simulation_data.json', 'r') as f:
    data = json.load(f)

# 构建查找表：ID -> 完整对象
id_lookup = {}
for category in ['locations', 'military_units', 'weapon_systems',
                 'civilian_infrastructures', 'battle_events', 'missions']:
    for item in data.get(category, []):
        id_lookup[item['id']] = item

def resolve_name(ref_id: str) -> str:
    """通过 ID 查找实体名称。"""
    entity = id_lookup.get(ref_id)
    if entity:
        return entity['properties'].get('name', ref_id)
    return ref_id

def build_episode_text(item: dict, category: str) -> tuple[str, str]:
    """将结构化实体转为自然语言 Episode 文本。返回 (name, body)。"""
    props = item['properties']
    rels = item.get('relationships', {})
    item_id = item['id']

    if category == 'locations':
        name = props['name']
        body = (
            f"{name}是一个{props['terrain']}地形区域，位于{props['area']}区，"
            f"坐标为({props['coordinates'][0]:.1f}, {props['coordinates'][1]:.1f})。"
        )

    elif category == 'military_units':
        name = props['name']
        loc_name = resolve_name(rels.get('located_at', ''))
        body = (
            f"{name}是一支{props['affiliation']}的{props['type']}部队，"
            f"兵力{props['strength']}人，装备包括{'、'.join(props['equipment'])}，"
            f"当前状态为{props['status']}，驻扎在{loc_name}。"
        )

    elif category == 'weapon_systems':
        name = props['name']
        loc_name = resolve_name(rels.get('located_at', ''))
        operator_name = resolve_name(rels.get('operated_by', ''))
        body = (
            f"{name}是一个{props['affiliation']}的{props['type']}武器系统，"
            f"有效射程{props['range']:.1f}公里，当前状态为{props['status']}，"
            f"部署在{loc_name}，由{operator_name}操作。"
        )

    elif category == 'civilian_infrastructures':
        name = props['name']
        loc_name = resolve_name(rels.get('located_at', ''))
        body = (
            f"{name}是一个{props['type']}类民用基础设施，"
            f"当前状态为{props['status']}，位于{loc_name}。"
        )

    elif category == 'battle_events':
        event_type = props['type']
        timestamp = props['timestamp']
        outcome = props['outcome']
        involves = [resolve_name(uid) for uid in rels.get('involves', [])]
        loc_name = resolve_name(rels.get('occurs_at', ''))
        body = (
            f"于{timestamp}在{loc_name}发生了一次{event_type}行动，"
            f"参战单位包括{'、'.join(involves)}，"
            f"行动结果为{outcome}。"
        )
        name = f"战场事件_{item_id}"

    elif category == 'missions':
        mission_type = props['type']
        status = props['status']
        priority = props['priority']
        deadline = props['deadline']
        assigned = resolve_name(rels.get('assigned_to', ''))
        targets = [resolve_name(tid) for tid in rels.get('targets', [])]
        loc_name = resolve_name(rels.get('located_at', ''))
        body = (
            f"任务{item_id}：{mission_type}任务，优先级{priority}，"
            f"截止时间{deadline}，当前状态为{status}。"
            f"任务分配给{assigned}，目标包括{'、'.join(set(targets))}，"
            f"任务区域在{loc_name}附近。"
        )
        name = f"任务_{item_id}"

    else:
        name = item_id
        body = json.dumps(props, ensure_ascii=False)

    return name, body


async def main():
    # 构建 LLM 和 Embedder
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

    # 连接 Graphiti
    g = Graphiti(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
    )
    print("✅ Graphiti connected")

    # 构建索引
    print("🔨 Building indices...")
    await g.build_indices_and_constraints(delete_existing=False)
    print("✅ Indices built")

    # 收集所有 Episode
    episodes_to_add = []
    categories = [
        ('locations', 'locations'),
        ('military_units', 'military_units'),
        ('weapon_systems', 'weapon_systems'),
        ('civilian_infrastructures', 'civilian_infrastructures'),
        ('battle_events', 'battle_events'),
        ('missions', 'missions'),
    ]

    for category, key in categories:
        for item in data.get(key, []):
            name, body = build_episode_text(item, category)
            episodes_to_add.append({
                'name': name,
                'body': body,
                'source': f'simulation_data/{category}',
                'category': category,
                'item_id': item['id']
            })

    print(f"\n📋 Prepared {len(episodes_to_add)} episodes to add:")
    for ep in episodes_to_add:
        print(f"  [{ep['category']:30s}] {ep['name']}")

    # 写入
    print(f"\n🚀 Writing {len(episodes_to_add)} episodes to Graphiti...")
    success_count = 0
    fail_count = 0
    for i, ep in enumerate(episodes_to_add):
        try:
            print(f"  [{i+1:2d}/{len(episodes_to_add)}] {ep['name']}...", end=' ', flush=True)
            await g.add_episode(
                name=ep['name'],
                episode_body=ep['body'],
                source_description=ep['source'],
                reference_time=datetime.now(timezone.utc),
                update_communities=False
            )
            print("✅")
            success_count += 1
        except Exception as e:
            print(f"❌ {e}")
            fail_count += 1

    print(f"\n📊 Results: {success_count} success, {fail_count} failed")

    # 搜索验证
    test_queries = [
        "蓝方部队部署位置",
        "红方装甲力量",
        "D区地形",
        "受损的武器系统",
        "失败的补给任务",
    ]
    print(f"\n🔍 Running {len(test_queries)} search queries:")
    for query in test_queries:
        try:
            results = await g.search(query=query, num_results=3)
            print(f"  '{query}' → {len(results)} results")
            for r in results[:2]:
                print(f"    - {getattr(r, 'name', '?')}: {getattr(r, 'fact', '')[:80]}...")
        except Exception as e:
            print(f"  '{query}' → ❌ {e}")

    await g.close()
    print("\n🎉 Done!")


if __name__ == "__main__":
    asyncio.run(main())
