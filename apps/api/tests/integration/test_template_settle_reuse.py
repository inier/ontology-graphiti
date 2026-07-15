"""Integration tests: HE template settlement and reuse logic.

Requires: Neo4j reachable + OPENAI_API_KEY set + hyperextract installed.
Tests verify REAL template settlement, reuse (usage_count increment), and
the lightweight validation path that skips full trial extraction.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.integration

# --- Neo4j reachability check (follows test_ontology_graphiti.py pattern) ---
NEO4J_AVAILABLE = False
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    pass

_neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_neo4j_user = os.getenv("NEO4J_USER", "neo4j")
_neo4j_password = os.getenv("NEO4J_PASSWORD", "password")


def _neo4j_reachable() -> bool:
    if not NEO4J_AVAILABLE:
        return False
    try:
        driver = GraphDatabase.driver(_neo4j_uri, auth=(_neo4j_user, _neo4j_password))
        with driver.session() as s:
            s.run("RETURN 1")
        driver.close()
        return True
    except Exception:
        return False


_has_openai_key = bool(os.getenv("OPENAI_API_KEY"))

_skip_if_no_env = pytest.mark.skipif(
    not (_neo4j_reachable() and _has_openai_key),
    reason="Requires Neo4j + OPENAI_API_KEY + hyperextract",
)

# Full valid HE YAML template for settle tests (TemplateCfg compliant)
# Includes ALL required fields: tags, output.description, entities.description,
# relations.description, guideline (target + rules), display.
_TEST_YAML = """\
language: [zh, en]
name: custom_settle_test
type: graph
tags: [test, integration, graph]
description:
  zh: 集成测试沉淀模板 - 从文本中提取实体和关系。
  en: Integration test settled template - extracts entities and relations from text.
output:
  description:
    zh: 由实体节点和关系边组成的知识图谱结果。
    en: Knowledge graph result consisting of entity nodes and relation edges.
  entities:
    description:
      zh: 文本中可独立识别、可参与关系连接的实体节点。
      en: Entity nodes that can be independently identified and participate in relation connections.
    fields:
      - name: name
        type: str
        description:
          zh: 实体名称，使用文本中最明确的称呼。
          en: Entity name, using the most explicit designation in the text.
      - name: type
        type: str
        description:
          zh: 实体类型，如人物/地点/组织/概念等。
          en: Entity type, e.g. person/location/organization/concept.
      - name: description
        type: str
        description:
          zh: 对实体身份或含义的简要说明。
          en: Brief description of the entity identity or meaning.
        required: false
  relations:
    description:
      zh: 实体之间的显式语义关系边。
      en: Explicit semantic relation edges between entities.
    fields:
      - name: source
        type: str
        description:
          zh: 关系起点实体名称。
          en: Source entity name of the relation.
      - name: target
        type: str
        description:
          zh: 关系终点实体名称。
          en: Target entity name of the relation.
      - name: type
        type: str
        description:
          zh: 关系类型，如属于/创建/位于/相关等。
          en: Relation type, e.g. belongs_to/created/located_at/related_to.
      - name: description
        type: str
        description:
          zh: 对关系依据或上下文含义的简要说明。
          en: Brief description of the relation basis or contextual meaning.
        required: false
guideline:
  target:
    zh: 你是一位知识抽取与知识图谱构建专家。请从文本中识别关键实体，并构建这些实体之间的二元关系。
    en: You are an expert in knowledge extraction and knowledge graph construction. Identify key entities from the text and construct binary relations between them.
  rules_for_entities:
    zh:
      - 提取对理解文本事实、结构或逻辑有价值的实体。
      - 同一实体在全文中保持命名一致。
      - 不要提取纯代词、泛称或无独立指代意义的词语。
    en:
      - Extract entities that are valuable for understanding text facts, structure, or logic.
      - Maintain consistent naming for the same entity throughout the text.
      - Do not extract pure pronouns, generic terms, or phrases without independent referential meaning.
  rules_for_relations:
    zh:
      - 仅在文本明确表达两个实体之间存在语义联系时创建关系。
      - 避免重复关系；同一对实体存在多种不同关系可分别记录。
      - 优先使用文本中明确出现的关系词。
    en:
      - Create relation edges only when the text explicitly expresses a semantic connection between two entities.
      - Avoid duplicate relations; multiple different relations for the same pair may be recorded separately.
      - Prefer relation words that explicitly appear in the text.
identifiers:
  entity_id: name
  relation_id: '{source}|{type}|{target}'
  relation_members:
    source: source
    target: target
options:
  extraction_mode: one_stage
display:
  entity_label: '{name} ({type})'
  relation_label: '{type}'
"""


@_skip_if_no_env
class TestTemplateSettleReuse:
    """Template settlement and reuse integration tests."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        # Redirect DATA_DIR so YAML files go to tmp_path (not production data dir)
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        self.tmp_path = tmp_path

        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        from odap.biz.data.hyper_extract.storage.sqlite_template_storage import (
            SqliteTemplateStorage,
        )

        self.adapter = HEAdapter()
        if not self.adapter.is_available():
            pytest.skip("hyperextract not installed")

        self.storage = SqliteTemplateStorage(
            db_path=str(tmp_path / "templates.db")
        )
        self.engine = TemplateEngine(self.adapter, self.storage)

    def test_settle_template_persists_to_sqlite_and_disk(self):
        """settle_template() must write YAML to disk and metadata to SQLite."""
        ontology_id = f"test-settle-{uuid.uuid4().hex[:8]}"
        template_id = self.engine.settle_template(
            ontology_id=ontology_id,
            name="custom_settle_test",
            yaml_content=_TEST_YAML,
            score=0.75,
            coverage=["object", "relation"],
        )
        assert template_id, "settle_template must return a non-empty template_id"

        # Verify metadata in SQLite
        record = self.storage.get_by_ontology(ontology_id)
        assert record is not None, "Settled template not found in SQLite"
        assert record["name"] == "custom_settle_test"
        assert record["score"] == 0.75
        assert record["source"] == "custom"

        # Verify YAML file exists on disk
        yaml_path = record["yaml_path"]
        assert yaml_path and os.path.exists(yaml_path), (
            f"YAML file not written to disk: {yaml_path}"
        )

    def test_assess_reuses_settled_and_increments_usage_count(self):
        """assess() with settled template must return source='settled' and
        increment usage_count on each reuse."""
        ontology_id = f"test-reuse-{uuid.uuid4().hex[:8]}"
        self.engine.settle_template(
            ontology_id=ontology_id,
            name="custom_settle_test",
            yaml_content=_TEST_YAML,
            score=0.75,
            coverage=["object", "relation"],
        )

        text = "张三是ABC公司的CEO。李四是XYZ公司的CTO。"

        # First assess — should find settled template and validate it
        result1 = self.engine.assess(text, ontology_id)
        assert result1["settled_used"] is True, "First assess should use settled template"
        candidates1 = result1.get("candidates", [])
        assert len(candidates1) >= 1
        assert candidates1[0]["source"] == "settled"

        usage_after_1 = self.storage.get_by_ontology(ontology_id)["usage_count"]

        # Second assess — should reuse settled again, incrementing usage_count
        result2 = self.engine.assess(text, ontology_id)
        assert result2["settled_used"] is True

        usage_after_2 = self.storage.get_by_ontology(ontology_id)["usage_count"]
        assert usage_after_2 > usage_after_1, (
            f"usage_count should increment on reuse: {usage_after_1} → {usage_after_2}"
        )

    def test_settled_template_skips_full_assessment_path(self):
        """When settled template passes validation, assess() must NOT call
        list_presets (the full trial extraction path is skipped)."""
        ontology_id = f"test-skip-{uuid.uuid4().hex[:8]}"
        self.engine.settle_template(
            ontology_id=ontology_id,
            name="custom_settle_test",
            yaml_content=_TEST_YAML,
            score=0.75,
            coverage=["object", "relation"],
        )

        # Track list_presets calls — should be 0 when settled is used
        call_count = [0]
        original_list_presets = self.engine.list_presets

        def counting_list_presets():
            call_count[0] += 1
            return original_list_presets()

        self.engine.list_presets = counting_list_presets

        text = "张三是ABC公司的CEO。"
        result = self.engine.assess(text, ontology_id)

        assert result["settled_used"] is True, "Settled template should be used"
        assert call_count[0] == 0, (
            f"list_presets should NOT be called when settled is used, "
            f"but was called {call_count[0]} times"
        )
