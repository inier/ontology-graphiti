"""P0-3 溯源完整性测试：规范化指纹 / 长度前缀链 / 追加式封存 / 篡改可见。

关键负例来自 Semantica #2136：用 ``"|".join`` 拼接字段再哈希，``("a|b", "c")``
与 ``("a", "b|c")`` 会得到同一个摘要，篡改因此不可见。本文件显式复现该碰撞，
并证明新编码不会碰撞。
"""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from datetime import datetime, timezone

import pytest

from odap.infra.security.provenance.integrity import (
    GENESIS_DIGEST,
    canonical_bytes,
    chain_digest,
    collection_digest,
    event_digest,
    event_key,
)
from odap.infra.security.provenance.chain_store import ProvenanceChainStore
from odap.infra.security.provenance.audit_exporter import AuditExporter


def _event(eid: str, action: str = "run", ts: str = "2026-10-30T10:00:00+00:00",
           workspace: str = "ws1") -> dict:
    return {
        "id": eid,
        "event_type": "agent.decision",
        "action": action,
        "timestamp": ts,
        "actor": {"actor_id": "agent-1", "actor_name": "决策智能体"},
        "resource": {"resource_type": "decision", "resource_id": "dec-1"},
        "workspace_id": workspace,
    }


# ---------------------------------------------------------------------------
# 规范化与指纹
# ---------------------------------------------------------------------------

class TestCanonicalBytes:
    def test_key_order_does_not_change_bytes(self):
        assert canonical_bytes({"b": 1, "a": 2}) == canonical_bytes({"a": 2, "b": 1})

    def test_unicode_is_not_escaped(self):
        assert canonical_bytes({"n": "红方"}).decode("utf-8") == '{"n":"红方"}'

    def test_datetime_becomes_isoformat(self):
        payload = {"t": datetime(2026, 10, 30, tzinfo=timezone.utc)}
        assert b"2026-10-30T00:00:00+00:00" in canonical_bytes(payload)


class TestEventDigest:
    def test_field_order_irrelevant(self):
        a = {"id": "e1", "action": "x"}
        b = {"action": "x", "id": "e1"}
        assert event_digest(a) == event_digest(b)

    def test_any_field_change_changes_digest(self):
        assert event_digest(_event("e1")) != event_digest(_event("e1", action="other"))

    def test_derived_fields_are_excluded(self):
        base = _event("e1")
        with_derived = dict(base, checksum="x", chain_hash="y", prev_digest="z",
                            event_digest="w", sealed_at="t")
        assert event_digest(base) == event_digest(with_derived)

    def test_event_key_accepts_both_id_forms(self):
        assert event_key({"id": "a"}) == "a"
        assert event_key({"event_id": "b"}) == "b"
        with pytest.raises(ValueError):
            event_key({})


class TestSeparatorCollisionRegression:
    """Semantica #2136 反面教材：分隔符拼接可碰撞，长度前缀不可。"""

    def test_legacy_separator_concatenation_collides(self):
        left = hashlib.sha256(f"{'a|b'}|{'c'}".encode()).hexdigest()
        right = hashlib.sha256(f"{'a'}|{'b|c'}".encode()).hexdigest()
        assert left == right  # 旧编码确实碰撞

    def test_event_digest_does_not_collide(self):
        a = event_digest({"id": "a|b", "timestamp": "c"})
        b = event_digest({"id": "a", "timestamp": "b|c"})
        assert a != b

    def test_chain_digest_does_not_collide(self):
        assert chain_digest("a|b", "c") != chain_digest("a", "b|c")

    def test_collection_digest_is_order_sensitive(self):
        d1, d2 = event_digest(_event("e1")), event_digest(_event("e2"))
        assert collection_digest([d1, d2]) != collection_digest([d2, d1])

    def test_chain_digest_depends_on_prev(self):
        d = event_digest(_event("e1"))
        assert chain_digest(GENESIS_DIGEST, d) != chain_digest("f" * 64, d)


# ---------------------------------------------------------------------------
# 追加式封存
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    return ProvenanceChainStore(db_path=str(tmp_path / "chain.db"))


@pytest.fixture
def events():
    return [_event("e1"), _event("e2", ts="2026-10-30T11:00:00+00:00"),
            _event("e3", ts="2026-10-30T12:00:00+00:00")]


class TestSeal:
    def test_seal_appends_and_links(self, store, events):
        result = store.seal(events)
        assert result["status"] == "ok"
        assert result["sealed"] == 3
        assert result["skipped"] == 0
        links = store.links()
        assert [link.event_id for link in links] == ["e1", "e2", "e3"]
        assert links[0].prev_digest == GENESIS_DIGEST
        assert links[1].prev_digest == links[0].chain_hash
        assert links[2].prev_digest == links[1].chain_hash
        assert result["head"]["chain_hash"] == links[-1].chain_hash

    def test_reseal_skips_existing_without_overwrite(self, store, events):
        store.seal(events)
        first_head = store.head().chain_hash
        result = store.seal(events)
        assert result["sealed"] == 0
        assert result["skipped"] == 3
        assert store.count() == 3
        assert store.head().chain_hash == first_head

    def test_seal_order_is_timestamp_ascending(self, store):
        unordered = [_event("late", ts="2026-10-30T20:00:00+00:00"),
                     _event("early", ts="2026-10-30T01:00:00+00:00")]
        store.seal(unordered)
        assert [link.event_id for link in store.links()] == ["early", "late"]

    def test_event_without_id_is_rejected(self, store):
        with pytest.raises(ValueError, match="neither 'id' nor 'event_id'"):
            store.seal([{"timestamp": "2026-10-30T00:00:00+00:00"}])


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

class TestVerify:
    def test_valid_after_seal(self, store, events):
        store.seal(events)
        result = store.verify(events)
        assert result["valid"] is True
        assert result["reason"] is None
        assert result["checked"] == 3
        assert result["unsealed_event_ids"] == []

    def test_tampered_event_is_detected(self, store, events):
        store.seal(events)
        tampered = [dict(events[0], action="deleted"), events[1], events[2]]
        result = store.verify(tampered)
        assert result["valid"] is False
        assert result["reason"] == "tampered"
        assert result["tampered"][0]["event_id"] == "e1"
        assert result["tampered"][0]["sealed_digest"] != result["tampered"][0]["actual_digest"]

    def test_unsealed_event_reported(self, store, events):
        store.seal(events[:2])
        result = store.verify(events)
        assert result["valid"] is False
        assert result["reason"] == "unsealed"
        assert result["unsealed_event_ids"] == ["e3"]

    def test_empty_window_is_not_a_pass(self, store):
        result = store.verify([])
        assert result["valid"] is False
        assert result["reason"] == "empty_window"

    def test_corrupted_link_detected(self, store, events):
        store.seal(events)
        conn = sqlite3.connect(store.db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE provenance_chain SET event_digest = ? WHERE event_id = 'e2'",
                    ("0" * 64,),
                )
        finally:
            conn.close()

        result = store.verify(events)
        assert result["valid"] is False
        # 改内容指纹会同时触发「内容不一致」与「链哈希对不上」，按 tampered 归类
        assert result["reason"] == "tampered"
        assert [item["event_id"] for item in result["tampered"]] == ["e2"]
        assert any(
            item["reason"] == "chain_hash_mismatch" for item in result["broken_links"]
        )

    def test_rewritten_chain_hash_breaks_linkage(self, store, events):
        store.seal(events)
        conn = sqlite3.connect(store.db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE provenance_chain SET chain_hash = ? WHERE event_id = 'e2'",
                    ("f" * 64,),
                )
        finally:
            conn.close()

        result = store.verify(events)
        assert result["valid"] is False
        assert result["reason"] == "broken_chain"
        # e3 的 prev_digest 不再等于 e2 的（被改写的）链哈希
        assert any(item["reason"] == "prev_mismatch" for item in result["broken_links"])

    def test_redelete_of_sealed_row_is_exposed_as_unsealed(self, store, events):
        store.seal(events)
        conn = sqlite3.connect(store.db_path)
        try:
            with conn:
                conn.execute("DELETE FROM provenance_chain WHERE event_id = 'e2'")
        finally:
            conn.close()

        result = store.verify(events)
        # 删掉中段链节既是「未封存」也破坏了前后链接，broken_chain 优先归类
        assert result["valid"] is False
        assert result["reason"] == "broken_chain"
        assert result["unsealed_event_ids"] == ["e2"]
        assert result["broken_links"]


# ---------------------------------------------------------------------------
# 导出清单
# ---------------------------------------------------------------------------

class TestExporterDigests:
    def test_jsonld_carries_digest_and_manifest(self, events):
        from rdflib import Graph, Literal, Namespace, RDF, URIRef

        ODAP = Namespace("https://odap.local/prov/")
        PROV = Namespace("http://www.w3.org/ns/prov#")

        content = AuditExporter().export(events, "json-ld")
        g = Graph().parse(data=content, format="json-ld")

        activity = URIRef(f"{ODAP}activity/e1")
        assert (activity, URIRef(f"{ODAP}sha256"), Literal(event_digest(events[0]))) in g

        manifests = list(g.subjects(URIRef(f"{ODAP}memberCount"), None))
        assert len(manifests) == 1
        assert (manifests[0], RDF.type, URIRef(f"{PROV}Collection")) in g
        # 每条 Activity 都挂在清单下
        members = set(g.subjects(URIRef(f"{ODAP}partOfExport"), manifests[0]))
        assert {str(m) for m in members} == {f"{ODAP}activity/{e['id']}" for e in events}

    def test_csv_carries_digest_column(self, events):
        out = AuditExporter().export(events, "csv")
        header = out.splitlines()[0]
        assert "event_digest" in header
        assert event_digest(events[0]) in out


# ---------------------------------------------------------------------------
# 路由层
# ---------------------------------------------------------------------------

class TestProvenanceRoutes:
    def test_verify_endpoint_passthrough(self, monkeypatch, store, events):
        from odap.infra.security.provenance import provenance_routes as routes

        store.seal(events)
        monkeypatch.setattr(routes, "_load_workspace_events", lambda ws, limit: events)
        monkeypatch.setattr(routes, "_get_store", lambda: store)

        result = asyncio.run(routes.verify_provenance(workspace_id="ws1", limit=1000,
                                                     user={"sub": "u1"}))
        assert result["valid"] is True
        assert result["workspace_id"] == "ws1"

    def test_seal_endpoint_rejects_empty_window(self, monkeypatch):
        from odap.infra.security.provenance import provenance_routes as routes

        monkeypatch.setattr(routes, "_load_workspace_events", lambda ws, limit: [])
        result = asyncio.run(routes.seal_provenance(workspace_id="ws1", limit=1000,
                                                    user={"sub": "u1"}))
        assert result["status"] == "error"
        assert "审计窗口为空" in result["message"]

    def test_seal_endpoint_seals_and_reports_head(self, monkeypatch, store, events):
        from odap.infra.security.provenance import provenance_routes as routes

        monkeypatch.setattr(routes, "_load_workspace_events", lambda ws, limit: events)
        monkeypatch.setattr(routes, "_get_store", lambda: store)
        # 避免写真实审计库
        import odap.infra.security.unified_audit as ua
        monkeypatch.setattr(ua, "log_audit", lambda **kwargs: None)

        result = asyncio.run(routes.seal_provenance(workspace_id="ws1", limit=1000,
                                                    user={"sub": "u1"}))
        assert result["status"] == "ok"
        assert result["sealed"] == 3
        assert result["head"]["chain_hash"]
