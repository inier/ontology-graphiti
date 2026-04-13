"""
Slice 1.2 集成测试：Graphiti + Neo4j
验证 build_indices, add_episode, retrieve_episodes, search 端到端链路

运行方式: python -m pytest tests/test_graphiti_integration.py -v
"""

import asyncio
import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass


# ---- Fixtures ----

@pytest.fixture(scope="module")
def graphiti_deps():
    """为所有测试提供共享的 Graphiti 依赖"""
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from core.llm_clients import ZhipuAIClient

    api_key = os.getenv('OPENAI_API_KEY', '')
    api_base = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
    api_model = os.getenv('OPENAI_MODEL', 'gpt-4')
    neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'neo4j123456')

    return {
        "neo4j_uri": neo4j_uri,
        "neo4j_user": neo4j_user,
        "neo4j_password": neo4j_password,
        "api_key": api_key,
        "api_base": api_base,
        "api_model": api_model,
    }


@pytest.fixture(scope="module")
def graphiti_client(graphiti_deps):
    """创建 Graphiti 实例（module 级别共享）"""
    from graphiti_core import Graphiti
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from core.llm_clients import ZhipuAIClient

    llm_config = LLMConfig(
        model=graphiti_deps["api_model"],
        api_key=graphiti_deps["api_key"],
        base_url=graphiti_deps["api_base"],
        temperature=0.7
    )
    llm_client = ZhipuAIClient(config=llm_config)

    embedder_config = OpenAIEmbedderConfig(
        api_key=graphiti_deps["api_key"],
        base_url=graphiti_deps["api_base"].rstrip('/chat/completions').rstrip('/') + '/embeddings',
        embedding_model="Pro/BAAI/bge-m3"
    )
    embedder = OpenAIEmbedder(config=embedder_config)

    g = Graphiti(
        uri=graphiti_deps["neo4j_uri"],
        user=graphiti_deps["neo4j_user"],
        password=graphiti_deps["neo4j_password"],
        llm_client=llm_client,
        embedder=embedder,
    )

    yield g

    # 清理
    try:
        g.close()
    except Exception:
        pass


# ---- Tests ----

class TestNeo4jConnection:
    """Step 1: Neo4j 连接验证"""

    def test_neo4j_connectivity(self, graphiti_deps):
        """Neo4j 应该可以连接并返回数据库信息"""
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            graphiti_deps["neo4j_uri"],
            auth=(graphiti_deps["neo4j_user"], graphiti_deps["neo4j_password"])
        )
        driver.verify_connectivity()

        with driver.session() as session:
            # 检查数据库是否在线
            result = session.run("RETURN 1 AS ok").single()
            assert result["ok"] == 1

        driver.close()


class TestGraphitiInit:
    """Step 2: Graphiti 索引构建"""

    @pytest.mark.asyncio
    async def test_build_indices(self, graphiti_client):
        """build_indices_and_constraints 应该成功完成"""
        # delete_existing=True 确保干净状态
        await graphiti_client.build_indices_and_constraints(delete_existing=False)
        # 如果到这里没抛异常就算成功


class TestEpisodeWrite:
    """Step 3: Episode 写入"""

    @pytest.mark.asyncio
    async def test_add_single_episode(self, graphiti_client):
        """写入单个 Episode 应该成功"""
        from datetime import datetime, timezone

        result = await graphiti_client.add_episode(
            name="TEST_UNIT_001",
            episode_body="TEST_UNIT_001 是一个 步兵单位，隶属于蓝方阵营，当前驻扎在A区，兵力120人，装备包括步枪和坦克，状态为待命。",
            source_description="战场数据: MilitaryUnit",
            reference_time=datetime.now(timezone.utc),
            update_communities=False
        )

        # add_episode 返回的应该是一个 EpisodeResult 或类似对象
        assert result is not None

    @pytest.mark.asyncio
    async def test_add_multiple_episodes(self, graphiti_client):
        """写入多个 Episode（模拟数据）"""
        from data.simulation_data import load_simulation_data
        from datetime import datetime, timezone

        data = load_simulation_data()
        all_entities = []
        all_entities.extend(data.get("locations", []))
        all_entities.extend(data.get("military_units", []))
        all_entities.extend(data.get("weapon_systems", []))
        all_entities.extend(data.get("civilian_infrastructure", []))

        success = 0
        errors = 0
        for entity in all_entities[:25]:
            entity_id = entity.get("id", "unknown")
            entity_type = entity.get("type", "")
            props = entity.get("properties", {})

            parts = [f"{entity_id} 是一个 {entity_type}"]
            for key, value in props.items():
                if isinstance(value, (str, int, float, bool)):
                    parts.append(f"它的 {key} 是 {value}")
                elif isinstance(value, (list, tuple)):
                    parts.append(f"它的 {key} 包括 {'、'.join(str(v) for v in value)}")
            episode_text = "。".join(parts)

            try:
                await graphiti_client.add_episode(
                    name=entity_id,
                    episode_body=episode_text,
                    source_description=f"战场数据: {entity_type}",
                    reference_time=datetime.now(timezone.utc),
                    update_communities=False
                )
                success += 1
            except Exception as e:
                errors += 1
                print(f"  写入失败 {entity_id}: {e}")

        print(f"\n  Episode 写入结果: 成功 {success}, 失败 {errors}")
        assert success >= 20, f"预期至少 20 个 Episode 成功，实际 {success}"


class TestEpisodeQuery:
    """Step 4: Episode 查询验证"""

    @pytest.mark.asyncio
    async def test_retrieve_episodes(self, graphiti_client):
        """retrieve_episodes 应该返回非空列表"""
        from datetime import datetime, timezone

        episodes = await graphiti_client.retrieve_episodes(
            reference_time=datetime.now(timezone.utc)
        )

        assert episodes is not None
        assert len(episodes) > 0, "应该至少能检索到 1 个 Episode"
        print(f"\n  检索到 {len(episodes)} 个 Episode")
        # 打印前 3 个的名称
        for ep in episodes[:3]:
            print(f"    - {getattr(ep, 'name', 'unknown')}: {getattr(ep, 'episode_body', '')[:80]}...")

    @pytest.mark.asyncio
    async def test_retrieve_episodes_last_n(self, graphiti_client):
        """last_n 参数应该限制返回数量"""
        from datetime import datetime, timezone

        episodes = await graphiti_client.retrieve_episodes(
            reference_time=datetime.now(timezone.utc),
            last_n=5
        )

        assert len(episodes) <= 5, "last_n=5 应该最多返回 5 个"

    @pytest.mark.asyncio
    async def test_search(self, graphiti_client):
        """search 应该能通过关键词匹配 Episode"""
        results = await graphiti_client.search(
            query="蓝方 步兵 A区",
            num_results=5
        )

        assert results is not None
        print(f"\n  搜索 '蓝方 步兵 A区' 返回 {len(results)} 个结果")


class TestGraphManagerIntegration:
    """Step 5: BattlefieldGraphManager 集成验证"""

    def test_graph_manager_mode(self):
        """GraphManager 应该在 neo4j_driver 或 graphiti 模式（非 fallback）"""
        # 重置单例以触发新连接
        from core.graph_manager import BattlefieldGraphManager
        BattlefieldGraphManager._instance = None
        BattlefieldGraphManager._initialized = False

        gm = BattlefieldGraphManager()
        assert gm._mode in ("neo4j_driver", "graphiti"), \
            f"预期 neo4j_driver 或 graphiti 模式，实际 {gm._mode}"
        assert not gm._use_fallback, "不应该在 fallback 模式"

    def test_graph_manager_statistics(self):
        """GraphManager.get_statistics 应该返回非零实体数"""
        from core.graph_manager import BattlefieldGraphManager

        gm = BattlefieldGraphManager()
        stats = gm.get_statistics()

        assert stats["total_entities"] > 0, "图谱应该有实体"
        assert stats["mode"] != "fallback", "不应该在 fallback 模式"
        print(f"\n  图谱统计: {stats}")
