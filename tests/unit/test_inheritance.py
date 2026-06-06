"""
Inheritance 模块单元测试 (T372)

覆盖：
- TestInheritanceEdgeModel: 领域模型
- TestMixinModel: 领域模型
- TestSQLiteInheritanceStorage: SQLite 真实 DB (tmp_path)
- TestInheritanceRepository: 存储实现
- TestInheritanceValidator: 循环/深度/Mixin 冲突
- TestInheritanceResolver: 单/多继承/Mixin 优先级/跨层级
- TestInheritanceService: 编排层
- TestInheritanceRoutes: HTTP API

≥25 用例。
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List

import pytest


# ============== TestInheritanceEdgeModel ==============

class TestInheritanceEdgeModel:
    def test_create_inheritance_edge_defaults(self):
        from odap.biz.core.ontology.inheritance.models.inheritance import (
            InheritanceEdge,
        )
        edge = InheritanceEdge(
            child_type_id="A", parent_type_id="B"
        )
        assert edge.id  # 自动生成 uuid
        assert edge.child_type_id == "A"
        assert edge.parent_type_id == "B"
        assert edge.depth == 1
        assert edge.discriminator == {}
        assert edge.created_at is not None

    def test_inheritance_edge_with_discriminator(self):
        from odap.biz.core.ontology.inheritance.models.inheritance import (
            InheritanceEdge,
        )
        edge = InheritanceEdge(
            child_type_id="Car",
            parent_type_id="Vehicle",
            discriminator={"kind": "car"},
        )
        assert edge.discriminator == {"kind": "car"}

    def test_inheritance_edge_with_depth(self):
        from odap.biz.core.ontology.inheritance.models.inheritance import (
            InheritanceEdge,
        )
        edge = InheritanceEdge(
            child_type_id="A", parent_type_id="B", depth=3
        )
        assert edge.depth == 3

    def test_inheritance_edge_unique_ids(self):
        from odap.biz.core.ontology.inheritance.models.inheritance import (
            InheritanceEdge,
        )
        e1 = InheritanceEdge(child_type_id="A", parent_type_id="B")
        e2 = InheritanceEdge(child_type_id="A", parent_type_id="B")
        assert e1.id != e2.id


# ============== TestMixinModel ==============

class TestMixinModel:
    def test_create_mixin_defaults(self):
        from odap.biz.core.ontology.inheritance.models.mixin import Mixin
        m = Mixin(name="TimestampMixin")
        assert m.id
        assert m.name == "TimestampMixin"
        assert m.description == ""
        assert m.properties == []
        assert m.target_type_ids == []
        assert m.created_at is not None

    def test_mixin_with_properties(self):
        from odap.biz.core.ontology.inheritance.models.mixin import Mixin
        m = Mixin(
            name="AuditMixin",
            description="adds audit fields",
            properties=["created_at", "updated_at", "created_by"],
            target_type_ids=["A", "B"],
        )
        assert "created_at" in m.properties
        assert "A" in m.target_type_ids

    def test_mixin_mutable_defaults_isolated(self):
        from odap.biz.core.ontology.inheritance.models.mixin import Mixin
        m1 = Mixin(name="A")
        m2 = Mixin(name="B")
        m1.properties.append("foo")
        assert m2.properties == []  # default_factory 隔离


# ============== TestSQLiteInheritanceStorage ==============

class TestSQLiteInheritanceStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.core.ontology.inheritance.storage.sqlite_inheritance_storage import (
            SQLiteInheritanceStorage,
        )
        return SQLiteInheritanceStorage(db_path=str(tmp_path / "inh_test.db"))

    def test_init_creates_tables(self, storage, tmp_path):
        db = tmp_path / "inh_test.db"
        conn = sqlite3.connect(str(db))
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        assert "inheritance_edges" in tables
        assert "mixins" in tables

    def test_save_and_get_edge(self, storage):
        edge = {
            "id": "e-1",
            "child_type_id": "A",
            "parent_type_id": "B",
            "depth": 1,
            "discriminator": {"k": "v"},
        }
        storage.save_edge(edge)
        got = storage.get_edge("e-1")
        assert got is not None
        assert got["child_type_id"] == "A"
        assert got["parent_type_id"] == "B"
        assert got["discriminator"] == {"k": "v"}

    def test_get_edge_not_found(self, storage):
        assert storage.get_edge("nonexistent") is None

    def test_delete_edge(self, storage):
        storage.save_edge({"id": "e-1", "child_type_id": "A", "parent_type_id": "B"})
        assert storage.delete_edge("e-1") is True
        assert storage.get_edge("e-1") is None

    def test_delete_edge_by_pair(self, storage):
        storage.save_edge({"id": "e-1", "child_type_id": "A", "parent_type_id": "B"})
        assert storage.delete_edge_by_pair("A", "B") is True
        assert storage.get_edge("e-1") is None

    def test_delete_edge_by_pair_not_found(self, storage):
        assert storage.delete_edge_by_pair("A", "B") is False

    def test_list_edges_by_child(self, storage):
        storage.save_edge({"id": "e-1", "child_type_id": "A", "parent_type_id": "B"})
        storage.save_edge({"id": "e-2", "child_type_id": "A", "parent_type_id": "C"})
        storage.save_edge({"id": "e-3", "child_type_id": "D", "parent_type_id": "B"})
        result = storage.list_edges(child_id="A")
        assert len(result) == 2

    def test_list_edges_by_parent(self, storage):
        storage.save_edge({"id": "e-1", "child_type_id": "A", "parent_type_id": "B"})
        storage.save_edge({"id": "e-2", "child_type_id": "C", "parent_type_id": "B"})
        result = storage.list_edges(parent_id="B")
        assert len(result) == 2

    def test_save_and_get_mixin(self, storage):
        m = {
            "id": "m-1",
            "name": "AuditMixin",
            "description": "audit fields",
            "properties": ["created_at", "updated_at"],
            "target_type_ids": ["A"],
        }
        storage.save_mixin(m)
        got = storage.get_mixin("m-1")
        assert got["name"] == "AuditMixin"
        assert got["properties"] == ["created_at", "updated_at"]
        assert got["target_type_ids"] == ["A"]

    def test_get_mixin_not_found(self, storage):
        assert storage.get_mixin("nonexistent") is None

    def test_delete_mixin(self, storage):
        storage.save_mixin({"id": "m-1", "name": "X", "properties": []})
        assert storage.delete_mixin("m-1") is True
        assert storage.delete_mixin("m-1") is False  # 第二次

    def test_list_mixins(self, storage):
        storage.save_mixin({"id": "m-1", "name": "A", "properties": []})
        storage.save_mixin({"id": "m-2", "name": "B", "properties": []})
        result = storage.list_mixins()
        assert len(result) == 2
        names = {m["name"] for m in result}
        assert names == {"A", "B"}

    def test_attach_mixin_to_type(self, storage):
        storage.save_mixin({
            "id": "m-1", "name": "Audit", "properties": ["created_at"],
        })
        assert storage.attach_mixin_to_type("m-1", "A") is True
        assert storage.attach_mixin_to_type("m-1", "A") is True  # idempotent
        ms = storage.list_mixins_for_type("A")
        assert len(ms) == 1
        assert "A" in ms[0]["target_type_ids"]

    def test_attach_mixin_not_found(self, storage):
        assert storage.attach_mixin_to_type("nonexistent", "A") is False

    def test_detach_mixin_from_type(self, storage):
        storage.save_mixin({"id": "m-1", "name": "X", "properties": []})
        storage.attach_mixin_to_type("m-1", "A")
        assert storage.detach_mixin_from_type("m-1", "A") is True
        assert storage.list_mixins_for_type("A") == []

    def test_list_mixins_for_type_filters(self, storage):
        storage.save_mixin({
            "id": "m-1", "name": "A", "properties": [], "target_type_ids": ["X"]
        })
        storage.save_mixin({
            "id": "m-2", "name": "B", "properties": [], "target_type_ids": ["Y"]
        })
        assert len(storage.list_mixins_for_type("X")) == 1
        assert len(storage.list_mixins_for_type("Y")) == 1
        assert storage.list_mixins_for_type("Z") == []


# ============== TestInheritanceRepository ==============

class TestInheritanceRepository:
    @pytest.fixture
    def repo(self, tmp_path):
        from odap.biz.core.ontology.inheritance.impl.inheritance_repository_impl import (
            InheritanceRepositoryImpl,
        )
        from odap.biz.core.ontology.inheritance.storage.sqlite_inheritance_storage import (
            SQLiteInheritanceStorage,
        )
        storage = SQLiteInheritanceStorage(db_path=str(tmp_path / "inh_repo.db"))
        return InheritanceRepositoryImpl(storage=storage)

    def test_save_and_list_edges(self, repo):
        repo.save_edge({"id": "e1", "child_type_id": "A", "parent_type_id": "B"})
        edges = repo.list_edges()
        assert len(edges) == 1
        assert edges[0]["child_type_id"] == "A"

    def test_delete_edge_by_pair(self, repo):
        repo.save_edge({"id": "e1", "child_type_id": "A", "parent_type_id": "B"})
        assert repo.delete_edge_by_pair("A", "B") is True

    def test_save_mixin_and_list_for_type(self, repo):
        repo.save_mixin({"id": "m1", "name": "M", "properties": []})
        repo.attach_mixin_to_type("m1", "T1")
        ms = repo.list_mixins_for_type("T1")
        assert len(ms) == 1


# ============== TestInheritanceValidator ==============

class TestInheritanceValidator:
    def test_simple_chain_a_b_c_passes(self):
        from odap.biz.core.ontology.inheritance.impl.validator import (
            validate_inheritance_chain,
        )
        from odap.biz.core.ontology.inheritance.models.inheritance import (
            InheritanceEdge,
        )
        edges = [
            InheritanceEdge(child_type_id="A", parent_type_id="B"),
            InheritanceEdge(child_type_id="B", parent_type_id="C"),
        ]
        result = validate_inheritance_chain(edges)
        assert result.is_valid is True
        assert result.errors == []

    def test_cycle_a_b_c_a_detected(self):
        from odap.biz.core.ontology.inheritance.impl.validator import (
            validate_inheritance_chain,
        )
        from odap.biz.core.ontology.inheritance.models.inheritance import (
            InheritanceEdge,
        )
        edges = [
            InheritanceEdge(child_type_id="A", parent_type_id="B"),
            InheritanceEdge(child_type_id="B", parent_type_id="C"),
            InheritanceEdge(child_type_id="C", parent_type_id="A"),
        ]
        result = validate_inheritance_chain(edges)
        assert result.is_valid is False
        assert any("Cycle" in e for e in result.errors)

    def test_depth_exceeds_5_detected(self):
        from odap.biz.core.ontology.inheritance.impl.validator import (
            validate_inheritance_chain,
        )
        from odap.biz.core.ontology.inheritance.models.inheritance import (
            InheritanceEdge,
        )
        edges = [
            InheritanceEdge(child_type_id=f"L{i}", parent_type_id=f"L{i + 1}")
            for i in range(7)
        ]
        result = validate_inheritance_chain(edges)
        assert result.is_valid is False
        assert any("depth" in e.lower() for e in result.errors)

    def test_mixin_conflict_with_parent_property(self):
        from odap.biz.core.ontology.inheritance.impl.validator import (
            validate_mixin_conflicts,
        )
        from odap.biz.core.ontology.inheritance.models.mixin import Mixin
        mixin = Mixin(name="AuditMixin", properties=["created_at"])
        result = validate_mixin_conflicts(
            type_id="Child",
            mixins=[mixin],
            type_properties=[],
            parent_property_names=["created_at"],
        )
        # 冲突在 warnings（不阻断）
        assert any("created_at" in w for w in result.warnings)

    def test_mixin_no_conflict(self):
        from odap.biz.core.ontology.inheritance.impl.validator import (
            validate_mixin_conflicts,
        )
        from odap.biz.core.ontology.inheritance.models.mixin import Mixin
        mixin = Mixin(name="TagMixin", properties=["tags"])
        result = validate_mixin_conflicts(
            type_id="Child", mixins=[mixin], type_properties=[], parent_property_names=[]
        )
        assert result.warnings == []
        assert result.is_valid is True

    def test_empty_chain_passes(self):
        from odap.biz.core.ontology.inheritance.impl.validator import (
            validate_inheritance_chain,
        )
        result = validate_inheritance_chain([])
        assert result.is_valid is True

    def test_validator_oop_class(self):
        from odap.biz.core.ontology.inheritance.impl.validator import (
            InheritanceValidator,
        )
        from odap.biz.core.ontology.inheritance.models.mixin import Mixin
        v = InheritanceValidator()
        result = v.validate_mixins(
            type_id="T",
            mixins=[Mixin(name="M", properties=["x"])],
            type_properties=["x"],
        )
        assert any("shadows" in w for w in result.warnings)


# ============== TestInheritanceResolver ==============

class TestInheritanceResolver:
    @pytest.fixture
    def setup(self, tmp_path):
        from odap.biz.core.ontology.inheritance.impl import (
            DictTypePropertyProvider,
            InheritanceRepositoryImpl,
        )
        from odap.biz.core.ontology.inheritance.impl.resolver import (
            InheritanceResolver,
        )
        from odap.biz.core.ontology.inheritance.storage.sqlite_inheritance_storage import (
            SQLiteInheritanceStorage,
        )
        storage = SQLiteInheritanceStorage(db_path=str(tmp_path / "inh_res.db"))
        repo = InheritanceRepositoryImpl(storage=storage)
        # 链 A ← B ← C
        repo.save_edge({"id": "e1", "child_type_id": "B", "parent_type_id": "A"})
        repo.save_edge({"id": "e2", "child_type_id": "C", "parent_type_id": "B"})
        provider = DictTypePropertyProvider(
            type_properties={
                "A": ["name", "code"],
                "B": ["code", "desc"],
                "C": ["desc", "extra"],
            },
            type_values={
                "A": {"name": "A_val", "code": "A_code"},
                "B": {"code": "B_code", "desc": "B_desc"},
                "C": {"desc": "C_desc", "extra": "C_extra"},
            },
        )
        resolver = InheritanceResolver(repo, provider)
        return resolver, repo, provider

    def test_single_inheritance_property(self, setup):
        resolver, _, _ = setup
        chain = resolver.resolve_property_chain("B", "code")
        # self (B) + parent (A)
        assert len(chain) == 2
        assert chain[0].source == "self"
        assert chain[1].source == "parent:A"
        assert chain[1].depth == 1

    def test_multi_level_inheritance(self, setup):
        resolver, _, _ = setup
        chain = resolver.resolve_property_chain("C", "name")
        # C 没有 self.name → 父类链 B → A
        assert len(chain) == 1
        assert chain[0].source == "parent:A"
        assert chain[0].depth == 2  # C → B → A

    def test_resolve_all_properties(self, setup):
        resolver, _, _ = setup
        all_props = resolver.resolve_all_properties("C")
        # C 自有: desc, extra; 父类链 B(→B 自有 code, desc 已去重), A(→name, code)
        assert "name" in all_props
        assert "code" in all_props
        assert "desc" in all_props
        assert "extra" in all_props
        # desc: self + parent:B
        desc_chain = all_props["desc"]
        assert desc_chain[0].source == "self"
        assert any(c.source == "parent:B" for c in desc_chain)

    def test_mixin_priority_below_parent(self, setup):
        resolver, repo, _ = setup
        # 给 C 附加一个 Mixin，提供 "tag" 属性
        repo.save_mixin({
            "id": "m-1", "name": "TagMixin", "properties": ["tag"],
            "target_type_ids": ["C"],
        })
        chain = resolver.resolve_property_chain("C", "tag")
        assert len(chain) == 1
        assert chain[0].source == "mixin:m-1"
        # depth 应大于父类链深度
        assert chain[0].depth >= 2

    def test_resolve_all_includes_mixin(self, setup):
        resolver, repo, _ = setup
        repo.save_mixin({
            "id": "m-1", "name": "TagMixin", "properties": ["tag"],
            "target_type_ids": ["C"],
        })
        all_props = resolver.resolve_all_properties("C")
        assert "tag" in all_props
        assert all_props["tag"][0].source == "mixin:m-1"

    def test_resolve_property_not_found(self, setup):
        resolver, _, _ = setup
        chain = resolver.resolve_property_chain("C", "nonexistent")
        assert chain == []


# ============== TestInheritanceService ==============

class TestInheritanceService:
    @pytest.fixture
    def service(self, tmp_path):
        from odap.biz.core.ontology.inheritance.impl import (
            DictTypePropertyProvider,
            InheritanceRepositoryImpl,
        )
        from odap.biz.core.ontology.inheritance.services.inheritance_service import (
            InheritanceService,
        )
        from odap.biz.core.ontology.inheritance.storage.sqlite_inheritance_storage import (
            SQLiteInheritanceStorage,
        )
        storage = SQLiteInheritanceStorage(db_path=str(tmp_path / "inh_svc.db"))
        repo = InheritanceRepositoryImpl(storage=storage)
        provider = DictTypePropertyProvider(
            type_properties={"A": ["name"], "B": ["code"], "C": ["desc"]},
        )
        return InheritanceService(repository=repo, property_provider=provider)

    def test_add_edge_success(self, service):
        result = service.add_edge("B", "A")
        assert result.get("status") != "error"
        assert result["child_type_id"] == "B"
        assert result["parent_type_id"] == "A"

    def test_add_edge_self_loop_rejected(self, service):
        result = service.add_edge("A", "A")
        assert result.get("status") == "error"

    def test_add_edge_cycle_rejected(self, service):
        service.add_edge("A", "B")
        service.add_edge("B", "C")
        # 试图添加 C → A 应当触发环
        result = service.add_edge("C", "A")
        assert result.get("status") == "error"

    def test_remove_edge_success(self, service):
        service.add_edge("B", "A")
        result = service.remove_edge("B", "A")
        assert result["status"] == "ok"

    def test_remove_edge_not_found(self, service):
        result = service.remove_edge("X", "Y")
        assert result.get("status") == "error"

    def test_list_edges_filter(self, service):
        service.add_edge("B", "A")
        service.add_edge("C", "A")
        result = service.list_by_parent("A")
        assert result["count"] == 2

    def test_add_mixin_and_attach(self, service):
        m = service.add_mixin({"name": "Audit", "properties": ["created_at"]})
        assert m.get("status") != "error"
        result = service.attach_mixin_to_type(m["id"], "A")
        assert result["status"] == "ok"
        assert "A" in service.get_mixin(m["id"])["target_type_ids"]

    def test_add_mixin_no_name_rejected(self, service):
        result = service.add_mixin({"properties": []})
        assert result.get("status") == "error"

    def test_update_mixin(self, service):
        m = service.add_mixin({"name": "M", "properties": ["x"]})
        result = service.update_mixin(m["id"], {"description": "updated"})
        assert result["description"] == "updated"
        assert result["name"] == "M"  # 未覆盖字段保留

    def test_remove_mixin(self, service):
        m = service.add_mixin({"name": "M"})
        result = service.remove_mixin(m["id"])
        assert result["status"] == "ok"

    def test_attach_mixin_not_found(self, service):
        result = service.attach_mixin_to_type("nonexistent", "A")
        assert result.get("status") == "error"

    def test_resolve_type(self, service):
        service.add_edge("B", "A")
        result = service.resolve_type("B")
        assert result["type_id"] == "B"
        assert "name" in result["properties"]  # 来自父类 A
        assert "code" in result["properties"]  # B 自身

    def test_validate_type_clean(self, service):
        service.add_edge("B", "A")
        result = service.validate_type("B")
        assert result["is_valid"] is True


# ============== TestInheritanceRoutes ==============

class TestInheritanceRoutes:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from odap.biz.core.ontology.inheritance.api.routes import router
        from odap.biz.core.ontology.inheritance.impl import (
            DictTypePropertyProvider,
            InheritanceRepositoryImpl,
        )
        from odap.biz.core.ontology.inheritance.services.inheritance_service import (
            InheritanceService,
        )
        from odap.biz.core.ontology.inheritance.storage.sqlite_inheritance_storage import (
            SQLiteInheritanceStorage,
        )
        storage = SQLiteInheritanceStorage(db_path=str(tmp_path / "inh_routes.db"))
        repo = InheritanceRepositoryImpl(storage=storage)
        provider = DictTypePropertyProvider(
            type_properties={"A": ["name"], "B": ["code"]},
        )
        # 替换模块级单例
        import odap.biz.core.ontology.inheritance.api.routes as routes_mod
        routes_mod.inheritance_service = InheritanceService(
            repository=repo, property_provider=provider
        )
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_post_edge_endpoint(self, client):
        resp = client.post(
            "/api/ontology/inheritance/edges",
            json={"child_type_id": "B", "parent_type_id": "A"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["child_type_id"] == "B"

    def test_post_edge_self_loop_returns_400(self, client):
        resp = client.post(
            "/api/ontology/inheritance/edges",
            json={"child_type_id": "A", "parent_type_id": "A"},
        )
        assert resp.status_code == 400

    def test_list_edges_endpoint(self, client):
        client.post(
            "/api/ontology/inheritance/edges",
            json={"child_type_id": "B", "parent_type_id": "A"},
        )
        resp = client.get("/api/ontology/inheritance/edges")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_delete_edge_endpoint(self, client):
        client.post(
            "/api/ontology/inheritance/edges",
            json={"child_type_id": "B", "parent_type_id": "A"},
        )
        resp = client.delete("/api/ontology/inheritance/edges/B/A")
        assert resp.status_code == 200

    def test_delete_edge_not_found_404(self, client):
        resp = client.delete("/api/ontology/inheritance/edges/X/Y")
        assert resp.status_code == 404

    def test_resolve_endpoint(self, client):
        client.post(
            "/api/ontology/inheritance/edges",
            json={"child_type_id": "B", "parent_type_id": "A"},
        )
        resp = client.get("/api/ontology/inheritance/resolve/B")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type_id"] == "B"
        assert "name" in data["properties"]

    def test_create_mixin_endpoint(self, client):
        resp = client.post(
            "/api/ontology/inheritance/mixins",
            json={"name": "AuditMixin", "properties": ["created_at"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "AuditMixin"

    def test_list_mixins_endpoint(self, client):
        client.post(
            "/api/ontology/inheritance/mixins",
            json={"name": "M1", "properties": []},
        )
        resp = client.get("/api/ontology/inheritance/mixins")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_get_mixin_404(self, client):
        resp = client.get("/api/ontology/inheritance/mixins/nonexistent")
        assert resp.status_code == 404

    def test_attach_mixin_endpoint(self, client):
        m = client.post(
            "/api/ontology/inheritance/mixins",
            json={"name": "M", "properties": ["p"]},
        ).json()
        resp = client.post(
            f"/api/ontology/inheritance/mixins/{m['id']}/attach/A"
        )
        assert resp.status_code == 200

    def test_detach_mixin_endpoint(self, client):
        m = client.post(
            "/api/ontology/inheritance/mixins",
            json={"name": "M", "properties": ["p"]},
        ).json()
        client.post(f"/api/ontology/inheritance/mixins/{m['id']}/attach/A")
        resp = client.post(f"/api/ontology/inheritance/mixins/{m['id']}/detach/A")
        assert resp.status_code == 200

    def test_validate_endpoint(self, client):
        client.post(
            "/api/ontology/inheritance/edges",
            json={"child_type_id": "B", "parent_type_id": "A"},
        )
        resp = client.post(
            "/api/ontology/inheritance/validate", json={"type_id": "B"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "is_valid" in data
