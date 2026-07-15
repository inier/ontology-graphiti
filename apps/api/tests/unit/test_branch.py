"""
Branch & Merge 单元测试 (T360, TDD)

按 AGENTS.md 规则 9 必测：
- SQLite 存储层用 `tmp_path` 真实 DB
- 服务层/路由层走真实 SQLite + 真实 ThreeWayMergeEngine
- 至少 35+ 用例

覆盖：
- TestBranchModel: UUID/Enum/默认值
- TestMergeRequestModel: 同上
- TestConflictModel: 三方值 / resolution
- TestSQLiteBranchStorage: 3 表 CRUD / JSON / 级联
- TestBranchRepository: 全部方法
- TestThreeWayMergeEngine: 6 种合并场景
- TestBranchService: 编排 / MR / 冲突 / 解决 / 执行
- TestBranchRoutes: HTTP 状态码 / 404/400/500
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI


# =====================================================================
# Helpers
# =====================================================================

def _make_branch(**overrides) -> Any:
    """工厂函数构造测试用 Branch"""
    from odap.biz.core.ontology.branch.models import Branch, BranchStatus
    defaults = dict(
        name="feature-x",
        ontology_id="ont-1",
        base_version_id="v1",
        head_version_id="v1",
    )
    defaults.update(overrides)
    return Branch(**defaults)


def _make_mr(**overrides) -> Any:
    from odap.biz.core.ontology.branch.models import MergeRequest, MergeRequestStatus
    defaults = dict(
        source_branch_id="br-src",
        target_branch_id="br-tgt",
        title="merge feature-x",
    )
    defaults.update(overrides)
    return MergeRequest(**defaults)


def _make_conflict(**overrides) -> Any:
    from odap.biz.core.ontology.branch.models import Conflict, ConflictResolution
    defaults = dict(
        merge_request_id="mr-1",
        path="/a/b",
        base_value=1,
        ours_value=2,
        theirs_value=3,
    )
    defaults.update(overrides)
    return Conflict(**defaults)


# =====================================================================
# TestBranchModel
# =====================================================================

class TestBranchModel:
    """Branch Pydantic 模型 (T348)"""

    def test_required_fields(self):
        b = _make_branch()
        assert b.name == "feature-x"
        assert b.ontology_id == "ont-1"
        assert b.base_version_id == "v1"
        assert b.head_version_id == "v1"

    def test_uuid_auto_generated(self):
        b1 = _make_branch()
        b2 = _make_branch()
        assert b1.id != b2.id
        # UUID 格式校验
        uuid.UUID(b1.id)

    def test_status_default_active(self):
        from odap.biz.core.ontology.branch.models import BranchStatus
        b = _make_branch()
        assert b.status == BranchStatus.ACTIVE
        assert b.status.value == "active"

    def test_status_enum_values(self):
        from odap.biz.core.ontology.branch.models import BranchStatus
        assert BranchStatus.ACTIVE.value == "active"
        assert BranchStatus.MERGED.value == "merged"
        assert BranchStatus.ABANDONED.value == "abandoned"

    def test_status_is_str_enum(self):
        """(str, Enum) 双继承：可直接当字符串比较"""
        from odap.biz.core.ontology.branch.models import BranchStatus
        assert BranchStatus.ACTIVE == "active"

    def test_default_description_empty(self):
        b = _make_branch()
        assert b.description == ""

    def test_default_created_by_system(self):
        b = _make_branch()
        assert b.created_by == "system"

    def test_created_at_default(self):
        b = _make_branch()
        assert isinstance(b.created_at, datetime)

    def test_merged_at_default_none(self):
        b = _make_branch()
        assert b.merged_at is None

    def test_independent_merged_at(self):
        """Pydantic 规则 5：默认 None 不可被实例间共享"""
        b1 = _make_branch()
        b2 = _make_branch()
        b1.merged_at = datetime.now()
        assert b2.merged_at is None


# =====================================================================
# TestMergeRequestModel
# =====================================================================

class TestMergeRequestModel:
    """MergeRequest Pydantic 模型 (T349)"""

    def test_required_fields(self):
        mr = _make_mr()
        assert mr.source_branch_id == "br-src"
        assert mr.target_branch_id == "br-tgt"
        assert mr.title == "merge feature-x"

    def test_default_empty_containers(self):
        mr = _make_mr()
        assert mr.conflicts == []
        assert mr.base_snapshot == {}
        assert mr.ours_snapshot == {}
        assert mr.theirs_snapshot == {}

    def test_container_field_isolation(self):
        """容器字段必须 default_factory，实例间独立"""
        mr1 = _make_mr()
        mr2 = _make_mr()
        mr1.conflicts.append({"p": 1})
        mr1.base_snapshot["x"] = 1
        assert mr2.conflicts == []
        assert mr2.base_snapshot == {}

    def test_status_default_open(self):
        from odap.biz.core.ontology.branch.models import MergeRequestStatus
        mr = _make_mr()
        assert mr.status == MergeRequestStatus.OPEN

    def test_status_enum_all_values(self):
        from odap.biz.core.ontology.branch.models import MergeRequestStatus
        expected = {"open", "approved", "merged", "conflict", "closed"}
        actual = {s.value for s in MergeRequestStatus}
        assert actual == expected

    def test_merged_at_default_none(self):
        mr = _make_mr()
        assert mr.merged_at is None

    def test_uuid_auto_generated(self):
        mr1 = _make_mr()
        mr2 = _make_mr()
        assert mr1.id != mr2.id
        uuid.UUID(mr1.id)


# =====================================================================
# TestConflictModel
# =====================================================================

class TestConflictModel:
    """Conflict Pydantic 模型 (T350)"""

    def test_three_way_values(self):
        c = _make_conflict(base_value=10, ours_value=20, theirs_value=30)
        assert c.base_value == 10
        assert c.ours_value == 20
        assert c.theirs_value == 30

    def test_resolution_default_unresolved(self):
        from odap.biz.core.ontology.branch.models import ConflictResolution
        c = _make_conflict()
        assert c.resolution == ConflictResolution.UNRESOLVED

    def test_resolution_enum_values(self):
        from odap.biz.core.ontology.branch.models import ConflictResolution
        assert ConflictResolution.UNRESOLVED.value == "unresolved"
        assert ConflictResolution.USE_OURS.value == "use_ours"
        assert ConflictResolution.USE_THEIRS.value == "use_theirs"
        assert ConflictResolution.USE_BASE.value == "use_base"
        assert ConflictResolution.MANUAL.value == "manual"

    def test_path_is_json_pointer(self):
        c = _make_conflict(path="/objectTypes/0/properties/2/name")
        assert c.path == "/objectTypes/0/properties/2/name"

    def test_resolved_value_default_none(self):
        c = _make_conflict()
        assert c.resolved_value is None

    def test_resolved_by_default_empty(self):
        c = _make_conflict()
        assert c.resolved_by == ""

    def test_resolved_at_default_none(self):
        c = _make_conflict()
        assert c.resolved_at is None


# =====================================================================
# TestSQLiteBranchStorage
# =====================================================================

class TestSQLiteBranchStorage:
    """SQLite 3 表 CRUD + JSON 序列化 (T353)"""

    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.core.ontology.branch.storage import SQLiteBranchStorage
        return SQLiteBranchStorage(db_path=str(tmp_path / "branch_test.db"))

    def test_save_and_get_branch(self, storage):
        b = _make_branch()
        storage.save_branch(b)
        got = storage.get_branch(b.id)
        assert got is not None
        assert got.id == b.id
        assert got.name == b.name

    def test_get_branch_not_found(self, storage):
        assert storage.get_branch("nonexistent") is None

    def test_list_branches_empty(self, storage):
        assert storage.list_branches() == []

    def test_list_branches_returns_all(self, storage):
        for _ in range(3):
            storage.save_branch(_make_branch())
        assert len(storage.list_branches()) == 3

    def test_list_branches_by_ontology(self, storage):
        storage.save_branch(_make_branch(ontology_id="o1"))
        storage.save_branch(_make_branch(ontology_id="o1"))
        storage.save_branch(_make_branch(ontology_id="o2"))
        assert len(storage.list_branches_by_ontology("o1")) == 2

    def test_get_active_branch(self, storage):
        from odap.biz.core.ontology.branch.models import BranchStatus
        b1 = _make_branch(ontology_id="o1")
        b2 = _make_branch(ontology_id="o1")
        b2.status = BranchStatus.MERGED
        storage.save_branch(b1)
        storage.save_branch(b2)
        active = storage.get_active_branch("o1")
        assert active is not None
        assert active.status == BranchStatus.ACTIVE

    def test_delete_branch_cascades_mr(self, storage):
        b = _make_branch()
        storage.save_branch(b)
        mr = _make_mr(source_branch_id=b.id)
        storage.save_merge_request(mr)
        # 在 mr 下插入冲突
        c = _make_conflict(merge_request_id=mr.id)
        storage.save_conflicts(mr.id, [c])
        assert storage.delete_branch(b.id) is True
        assert storage.get_branch(b.id) is None
        # MR 已被级联删除
        assert storage.get_merge_request(mr.id) is None

    def test_delete_branch_not_found(self, storage):
        assert storage.delete_branch("nonexistent") is False

    def test_save_and_get_merge_request(self, storage):
        mr = _make_mr(base_snapshot={"a": 1}, ours_snapshot={"a": 2})
        storage.save_merge_request(mr)
        got = storage.get_merge_request(mr.id)
        assert got is not None
        assert got.base_snapshot == {"a": 1}
        assert got.ours_snapshot == {"a": 2}

    def test_merge_request_json_field_roundtrip(self, storage):
        """JSON 字段：dict/list 往返一致性"""
        snapshots = {
            "base_snapshot": {"x": [1, 2, 3], "y": {"nested": True}},
            "ours_snapshot": {"x": [4, 5], "y": {"nested": False}},
            "theirs_snapshot": {"x": [], "y": {}},
        }
        mr = _make_mr(**snapshots)
        storage.save_merge_request(mr)
        got = storage.get_merge_request(mr.id)
        assert got.base_snapshot == snapshots["base_snapshot"]
        assert got.ours_snapshot == snapshots["ours_snapshot"]
        assert got.theirs_snapshot == snapshots["theirs_snapshot"]

    def test_list_merge_requests_by_branch(self, storage):
        storage.save_merge_request(_make_mr(source_branch_id="br-A"))
        storage.save_merge_request(_make_mr(source_branch_id="br-B"))
        storage.save_merge_request(_make_mr(target_branch_id="br-A"))
        # br-A 涉及 2 个
        assert len(storage.list_merge_requests(branch_id="br-A")) == 2

    def test_list_merge_requests_by_status(self, storage):
        from odap.biz.core.ontology.branch.models import MergeRequestStatus
        mr1 = _make_mr()
        mr2 = _make_mr()
        mr2.status = MergeRequestStatus.MERGED
        storage.save_merge_request(mr1)
        storage.save_merge_request(mr2)
        assert len(storage.list_merge_requests(status="open")) == 1
        assert len(storage.list_merge_requests(status="merged")) == 1

    def test_save_conflicts_replaces(self, storage):
        """save_conflicts 应当先删旧冲突"""
        mr = _make_mr()
        storage.save_merge_request(mr)
        c1 = _make_conflict(merge_request_id=mr.id, path="/a")
        c2 = _make_conflict(merge_request_id=mr.id, path="/b")
        storage.save_conflicts(mr.id, [c1])
        assert len(storage.list_conflicts(mr.id)) == 1
        # 第二次保存替换
        storage.save_conflicts(mr.id, [c2])
        listed = storage.list_conflicts(mr.id)
        assert len(listed) == 1
        assert listed[0].path == "/b"

    def test_list_conflicts_empty(self, storage):
        assert storage.list_conflicts("nonexistent-mr") == []

    def test_update_conflict_resolution(self, storage):
        from odap.biz.core.ontology.branch.models import ConflictResolution
        mr = _make_mr()
        storage.save_merge_request(mr)
        c = _make_conflict(merge_request_id=mr.id)
        storage.save_conflicts(mr.id, [c])
        updated = storage.update_conflict_resolution(
            c.id, ConflictResolution.USE_OURS, "v-ours", "alice"
        )
        assert updated.resolution == ConflictResolution.USE_OURS
        assert updated.resolved_value == "v-ours"
        assert updated.resolved_by == "alice"
        assert updated.resolved_at is not None

    def test_update_conflict_not_found_raises(self, storage):
        from odap.biz.core.ontology.branch.models import ConflictResolution
        with pytest.raises(ValueError, match="not found"):
            storage.update_conflict_resolution(
                "nonexistent", ConflictResolution.USE_OURS, None, "x"
            )


# =====================================================================
# TestBranchRepository
# =====================================================================

class TestBranchRepository:
    """BranchRepositoryImpl ABC 全部方法 (T354)"""

    @pytest.fixture
    def repo(self, tmp_path):
        from odap.biz.core.ontology.branch.impl import BranchRepositoryImpl
        from odap.biz.core.ontology.branch.storage import SQLiteBranchStorage
        return BranchRepositoryImpl(storage=SQLiteBranchStorage(
            db_path=str(tmp_path / "repo_test.db")
        ))

    def test_save_and_get_branch(self, repo):
        b = _make_branch()
        repo.save(b)
        got = repo.get(b.id)
        assert got is not None
        assert got.id == b.id

    def test_list_branches(self, repo):
        for _ in range(3):
            repo.save(_make_branch())
        assert len(repo.list()) == 3

    def test_list_by_ontology(self, repo):
        repo.save(_make_branch(ontology_id="o1"))
        repo.save(_make_branch(ontology_id="o1"))
        repo.save(_make_branch(ontology_id="o2"))
        assert len(repo.list_by_ontology("o1")) == 2

    def test_get_active(self, repo):
        repo.save(_make_branch(ontology_id="o1"))
        active = repo.get_active("o1")
        assert active is not None
        assert active.status.value == "active"

    def test_delete_branch(self, repo):
        b = _make_branch()
        repo.save(b)
        assert repo.delete(b.id) is True
        assert repo.get(b.id) is None

    def test_save_and_get_merge_request(self, repo):
        mr = _make_mr()
        repo.save_merge_request(mr)
        got = repo.get_merge_request(mr.id)
        assert got is not None

    def test_list_merge_requests(self, repo):
        repo.save_merge_request(_make_mr(source_branch_id="b1"))
        repo.save_merge_request(_make_mr(source_branch_id="b2"))
        assert len(repo.list_merge_requests()) == 2

    def test_save_and_list_conflicts(self, repo):
        mr = _make_mr()
        repo.save_merge_request(mr)
        c = _make_conflict(merge_request_id=mr.id)
        repo.save_conflicts(mr.id, [c])
        assert len(repo.list_conflicts(mr.id)) == 1

    def test_update_conflict_resolution(self, repo):
        from odap.biz.core.ontology.branch.models import ConflictResolution
        mr = _make_mr()
        repo.save_merge_request(mr)
        c = _make_conflict(merge_request_id=mr.id)
        repo.save_conflicts(mr.id, [c])
        updated = repo.update_conflict_resolution(
            c.id, ConflictResolution.USE_THEIRS, "v-theirs", "bob"
        )
        assert updated.resolution == ConflictResolution.USE_THEIRS
        assert updated.resolved_value == "v-theirs"


# =====================================================================
# TestThreeWayMergeEngine
# =====================================================================

class TestThreeWayMergeEngine:
    """3-way merge 引擎 (T355)"""

    @pytest.fixture
    def engine(self):
        from odap.biz.core.ontology.branch.impl import ThreeWayMergeEngine
        return ThreeWayMergeEngine()

    def test_no_conflict_disjoint_changes(self, engine):
        base = {"a": 1, "b": 2}
        ours = {"a": 10, "b": 2}   # 改 a
        theirs = {"a": 1, "b": 20}  # 改 b
        result = engine.merge(base, ours, theirs)
        assert result.conflicts == []
        assert result.merged == {"a": 10, "b": 20}

    def test_ours_only_change_preserved(self, engine):
        base = {"x": "old"}
        ours = {"x": "new-ours"}
        theirs = {"x": "old"}
        result = engine.merge(base, ours, theirs)
        assert result.conflicts == []
        assert result.merged["x"] == "new-ours"

    def test_theirs_only_change_preserved(self, engine):
        base = {"x": "old"}
        ours = {"x": "old"}
        theirs = {"x": "new-theirs"}
        result = engine.merge(base, ours, theirs)
        assert result.conflicts == []
        assert result.merged["x"] == "new-theirs"

    def test_both_change_same_field_different_value_conflicts(self, engine):
        base = {"x": "old"}
        ours = {"x": "ours-val"}
        theirs = {"x": "theirs-val"}
        conflicts = engine.detect_conflicts(base, ours, theirs)
        assert len(conflicts) == 1
        assert conflicts[0].path == "/x"
        assert conflicts[0].base_value == "old"
        assert conflicts[0].ours_value == "ours-val"
        assert conflicts[0].theirs_value == "theirs-val"

    def test_nested_dict_modification(self, engine):
        base = {"meta": {"version": 1, "author": "alice"}}
        ours = {"meta": {"version": 2, "author": "alice"}}
        theirs = {"meta": {"version": 1, "author": "bob"}}
        conflicts = engine.detect_conflicts(base, ours, theirs)
        # 不同字段：ours 改 version, theirs 改 author → 不冲突
        assert conflicts == []
        result = engine.merge(base, ours, theirs)
        assert result.merged["meta"]["version"] == 2
        assert result.merged["meta"]["author"] == "bob"

    def test_nested_dict_conflict(self, engine):
        base = {"meta": {"version": 1}}
        ours = {"meta": {"version": 2}}
        theirs = {"meta": {"version": 3}}
        conflicts = engine.detect_conflicts(base, ours, theirs)
        assert len(conflicts) == 1
        assert conflicts[0].path == "/meta/version"

    def test_list_modification(self, engine):
        base = {"items": [1, 2, 3]}
        ours = {"items": [1, 2, 30]}     # 改 index 2
        theirs = {"items": [1, 20, 3]}   # 改 index 1
        result = engine.merge(base, ours, theirs)
        # 不冲突
        assert result.conflicts == []
        assert result.merged["items"] == [1, 20, 30]

    def test_json_pointer_path_correct(self, engine):
        base = {"a": {"b": {"c": 1}}}
        ours = {"a": {"b": {"c": 2}}}
        theirs = {"a": {"b": {"c": 3}}}
        conflicts = engine.detect_conflicts(base, ours, theirs)
        assert len(conflicts) == 1
        assert conflicts[0].path == "/a/b/c"

    def test_added_key_only_one_side(self, engine):
        """只在 ours 添加 theirs 不动的 key → 不冲突"""
        base = {"a": 1}
        ours = {"a": 1, "b": 2}
        theirs = {"a": 1}
        result = engine.merge(base, ours, theirs)
        assert result.conflicts == []
        assert result.merged == {"a": 1, "b": 2}

    def test_same_change_no_conflict(self, engine):
        base = {"a": 1}
        ours = {"a": 2}
        theirs = {"a": 2}
        conflicts = engine.detect_conflicts(base, ours, theirs)
        assert conflicts == []

    def test_auto_resolved_count(self, engine):
        base = {"a": 1, "b": 2, "c": 3}
        ours = {"a": 10, "b": 2, "c": 3}    # 改 a
        theirs = {"a": 1, "b": 20, "c": 3}  # 改 b
        result = engine.merge(base, ours, theirs)
        assert result.auto_resolved_count == 2  # a + b
        assert result.conflicts == []

    def test_merge_with_meta_params(self, engine):
        """传入 source_meta / target_meta 不会破坏合并逻辑"""
        base = {"a": 1}
        ours = {"a": 2}
        theirs = {"a": 1}
        result = engine.merge(
            base, ours, theirs,
            source_meta={"branch": "feat"},
            target_meta={"branch": "main"},
        )
        assert result.conflicts == []


# =====================================================================
# TestBranchService
# =====================================================================

class TestBranchService:
    """BranchService 编排 (T356)"""

    @pytest.fixture
    def service(self, tmp_path):
        from odap.biz.core.ontology.branch.impl import (
            BranchRepositoryImpl, ThreeWayMergeEngine,
        )
        from odap.biz.core.ontology.branch.services import BranchService
        from odap.biz.core.ontology.branch.storage import SQLiteBranchStorage
        return BranchService(
            repository=BranchRepositoryImpl(storage=SQLiteBranchStorage(
                db_path=str(tmp_path / "svc_test.db")
            )),
            engine=ThreeWayMergeEngine(),
        )

    def test_create_branch_success(self, service):
        result = service.create_branch("feat-a", "ont-1", "v1", "test")
        assert result.get("status") != "error"
        assert result["name"] == "feat-a"
        assert result["status"] == "active"

    def test_create_branch_missing_field(self, service):
        result = service.create_branch("", "ont-1", "v1")
        assert result.get("status") == "error"

    def test_get_branch_found(self, service):
        b = service.create_branch("feat", "o1", "v1")
        got = service.get_branch(b["id"])
        assert got["id"] == b["id"]

    def test_get_branch_not_found(self, service):
        got = service.get_branch("nonexistent")
        assert got.get("status") == "error"

    def test_list_branches(self, service):
        service.create_branch("f1", "o1", "v1")
        service.create_branch("f2", "o1", "v1")
        result = service.list_branches(ontology_id="o1")
        assert result["count"] == 2

    def test_list_branches_global(self, service):
        service.create_branch("f1", "o1", "v1")
        service.create_branch("f2", "o2", "v1")
        result = service.list_branches()
        assert result["count"] == 2

    def test_delete_branch(self, service):
        b = service.create_branch("f1", "o1", "v1")
        result = service.delete_branch(b["id"])
        assert result.get("deleted") is True

    def test_delete_branch_not_found(self, service):
        result = service.delete_branch("nonexistent")
        assert result.get("status") == "error"

    def test_get_lineage_single(self, service):
        b = service.create_branch("f1", "o1", "v1")
        lineage = service.get_lineage(b["id"])
        assert lineage["count"] >= 1
        assert lineage["lineage"][0]["id"] == b["id"]

    def test_create_merge_request(self, service):
        b1 = service.create_branch("src", "o1", "v1")
        b2 = service.create_branch("tgt", "o1", "v1")
        mr = service.create_merge_request(
            source_branch_id=b1["id"],
            target_branch_id=b2["id"],
            title="merge",
        )
        assert mr.get("status") != "error"
        assert mr["status"] == "open"

    def test_create_merge_request_same_branch(self, service):
        b = service.create_branch("f", "o1", "v1")
        result = service.create_merge_request(
            source_branch_id=b["id"],
            target_branch_id=b["id"],
            title="self-merge",
        )
        assert result.get("status") == "error"

    def test_create_merge_request_missing_field(self, service):
        result = service.create_merge_request("", "tgt", "title")
        assert result.get("status") == "error"

    def test_list_merge_requests(self, service):
        b1 = service.create_branch("s", "o1", "v1")
        b2 = service.create_branch("t", "o1", "v1")
        service.create_merge_request(b1["id"], b2["id"], "m1")
        result = service.list_merge_requests(branch_id=b1["id"])
        assert result["count"] == 1

    def test_get_merge_request(self, service):
        b1 = service.create_branch("s", "o1", "v1")
        b2 = service.create_branch("t", "o1", "v1")
        mr = service.create_merge_request(b1["id"], b2["id"], "m1")
        got = service.get_merge_request(mr["id"])
        assert got["id"] == mr["id"]

    def test_detect_conflicts_no_conflict(self, service):
        b1 = service.create_branch("s", "o1", "v1")
        b2 = service.create_branch("t", "o1", "v1")
        mr = service.create_merge_request(
            source_branch_id=b1["id"],
            target_branch_id=b2["id"],
            title="m",
            base_snapshot={"a": 1, "b": 2},
            ours_snapshot={"a": 10, "b": 2},
            theirs_snapshot={"a": 1, "b": 20},
        )
        result = service.detect_conflicts(mr["id"])
        assert result["count"] == 0
        assert result["status"] == "approved"

    def test_detect_conflicts_with_conflict(self, service):
        b1 = service.create_branch("s", "o1", "v1")
        b2 = service.create_branch("t", "o1", "v1")
        mr = service.create_merge_request(
            source_branch_id=b1["id"],
            target_branch_id=b2["id"],
            title="m",
            base_snapshot={"x": "old"},
            ours_snapshot={"x": "ours"},
            theirs_snapshot={"x": "theirs"},
        )
        result = service.detect_conflicts(mr["id"])
        assert result["count"] == 1
        assert result["status"] == "conflict"
        assert result["conflicts"][0]["path"] == "/x"

    def test_detect_conflicts_mr_not_found(self, service):
        result = service.detect_conflicts("nonexistent")
        assert result.get("status") == "error"

    def test_resolve_conflict_use_ours(self, service):
        b1 = service.create_branch("s", "o1", "v1")
        b2 = service.create_branch("t", "o1", "v1")
        mr = service.create_merge_request(
            source_branch_id=b1["id"],
            target_branch_id=b2["id"],
            title="m",
            base_snapshot={"x": "old"},
            ours_snapshot={"x": "ours"},
            theirs_snapshot={"x": "theirs"},
        )
        detected = service.detect_conflicts(mr["id"])
        cid = detected["conflicts"][0]["id"]
        result = service.resolve_conflict(cid, "use_ours")
        assert result["conflict"]["resolution"] == "use_ours"
        assert result["conflict"]["resolved_value"] == "ours"
        assert result["merge_request_status"] == "approved"

    def test_resolve_conflict_invalid_resolution(self, service):
        result = service.resolve_conflict("xxx", "bogus")
        assert result.get("status") == "error"

    def test_resolve_conflict_unresolved_forbidden(self, service):
        result = service.resolve_conflict("xxx", "unresolved")
        assert result.get("status") == "error"

    def test_execute_merge_unresolved_blocks(self, service):
        b1 = service.create_branch("s", "o1", "v1")
        b2 = service.create_branch("t", "o1", "v1")
        mr = service.create_merge_request(
            source_branch_id=b1["id"],
            target_branch_id=b2["id"],
            title="m",
            base_snapshot={"x": "old"},
            ours_snapshot={"x": "ours"},
            theirs_snapshot={"x": "theirs"},
        )
        service.detect_conflicts(mr["id"])
        result = service.execute_merge(mr["id"])
        assert result.get("status") == "error"
        assert "unresolved" in result.get("message", "")

    def test_execute_merge_success(self, service):
        b1 = service.create_branch("s", "o1", "v1")
        b2 = service.create_branch("t", "o1", "v1")
        mr = service.create_merge_request(
            source_branch_id=b1["id"],
            target_branch_id=b2["id"],
            title="m",
            base_snapshot={"a": 1, "b": 2},
            ours_snapshot={"a": 10, "b": 2},
            theirs_snapshot={"a": 1, "b": 20},
        )
        # 无冲突，直接执行
        result = service.execute_merge(mr["id"])
        assert result["status"] == "merged"
        assert result["merged"]["a"] == 10
        assert result["merged"]["b"] == 20

    def test_execute_merge_marks_source_merged(self, service):
        b1 = service.create_branch("s", "o1", "v1")
        b2 = service.create_branch("t", "o1", "v1")
        mr = service.create_merge_request(
            source_branch_id=b1["id"],
            target_branch_id=b2["id"],
            title="m",
            base_snapshot={"x": 1},
            ours_snapshot={"x": 2},
            theirs_snapshot={"x": 1},
        )
        service.execute_merge(mr["id"])
        got = service.get_branch(b1["id"])
        assert got["status"] == "merged"
        assert got["merged_at"] is not None

    def test_execute_merge_mr_not_found(self, service):
        result = service.execute_merge("nonexistent")
        assert result.get("status") == "error"


# =====================================================================
# TestBranchRoutes
# =====================================================================

class TestBranchRoutes:
    """HTTP 路由测试 (T357)"""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        """FastAPI TestClient + 注入 tmp storage"""
        from fastapi.testclient import TestClient
        from odap.biz.core.ontology.branch.impl import BranchRepositoryImpl
        from odap.biz.core.ontology.branch.services import BranchService
        from odap.biz.core.ontology.branch.storage import SQLiteBranchStorage
        from odap.biz.core.ontology.branch.api import routes as routes_module

        test_storage = SQLiteBranchStorage(
            db_path=str(tmp_path / "route_test.db")
        )
        # 替换模块级单例，避免污染全局
        routes_module.branch_service = BranchService(
            repository=BranchRepositoryImpl(storage=test_storage),
        )
        app = FastAPI()
        app.include_router(routes_module.router)
        return TestClient(app)

    def _create_branch_payload(self, **overrides) -> Dict[str, Any]:
        payload = {
            "name": "test-branch",
            "ontology_id": "ont-1",
            "base_version_id": "v1",
        }
        payload.update(overrides)
        return payload

    def test_create_branch_endpoint(self, client):
        resp = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-branch"
        assert data["status"] == "active"

    def test_create_branch_missing_field_returns_422(self, client):
        """Pydantic 必填字段缺失返回 422（FastAPI 标准行为）"""
        resp = client.post(
            "/api/ontology/branches",
            json={"name": "x"},  # 缺 ontology_id / base_version_id
        )
        assert resp.status_code == 422

    def test_list_branches_endpoint(self, client):
        client.post("/api/ontology/branches", json=self._create_branch_payload())
        resp = client.get("/api/ontology/branches")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_list_branches_by_ontology(self, client):
        client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(ontology_id="o-A"),
        )
        resp = client.get("/api/ontology/branches?ontology_id=o-A")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_get_branch_found(self, client):
        created = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(),
        ).json()
        resp = client.get(f"/api/ontology/branches/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_branch_not_found_returns_404(self, client):
        resp = client.get("/api/ontology/branches/nonexistent")
        assert resp.status_code == 404

    def test_delete_branch_endpoint(self, client):
        created = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(),
        ).json()
        resp = client.delete(f"/api/ontology/branches/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_branch_not_found_returns_404(self, client):
        resp = client.delete("/api/ontology/branches/nonexistent")
        assert resp.status_code == 404

    def test_create_merge_request_endpoint(self, client):
        b1 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="src"),
        ).json()
        b2 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="tgt"),
        ).json()
        resp = client.post(
            f"/api/ontology/branches/{b1['id']}/merge-requests",
            json={
                "source_branch_id": b1["id"],
                "target_branch_id": b2["id"],
                "title": "merge",
                "base_snapshot": {"a": 1},
                "ours_snapshot": {"a": 2},
                "theirs_snapshot": {"a": 3},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"

    def test_create_merge_request_same_branch_returns_400(self, client):
        b = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(),
        ).json()
        resp = client.post(
            f"/api/ontology/branches/{b['id']}/merge-requests",
            json={
                "source_branch_id": b["id"],
                "target_branch_id": b["id"],
                "title": "self-merge",
            },
        )
        assert resp.status_code == 400

    def test_list_merge_requests(self, client):
        resp = client.get("/api/ontology/branches/merge-requests")
        assert resp.status_code == 200
        assert "merge_requests" in resp.json()

    def test_get_merge_request_not_found_returns_404(self, client):
        resp = client.get("/api/ontology/branches/merge-requests/nonexistent")
        assert resp.status_code == 404

    def test_detect_conflicts_endpoint(self, client):
        b1 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="src"),
        ).json()
        b2 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="tgt"),
        ).json()
        mr = client.post(
            f"/api/ontology/branches/{b1['id']}/merge-requests",
            json={
                "source_branch_id": b1["id"],
                "target_branch_id": b2["id"],
                "title": "m",
                "base_snapshot": {"x": 1},
                "ours_snapshot": {"x": 2},
                "theirs_snapshot": {"x": 3},
            },
        ).json()
        resp = client.post(
            f"/api/ontology/branches/merge-requests/{mr['id']}/detect-conflicts"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["status"] == "conflict"

    def test_detect_conflicts_mr_not_found_returns_404(self, client):
        resp = client.post(
            "/api/ontology/branches/merge-requests/nonexistent/detect-conflicts"
        )
        assert resp.status_code == 404

    def test_resolve_conflict_endpoint(self, client):
        b1 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="src"),
        ).json()
        b2 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="tgt"),
        ).json()
        mr = client.post(
            f"/api/ontology/branches/{b1['id']}/merge-requests",
            json={
                "source_branch_id": b1["id"],
                "target_branch_id": b2["id"],
                "title": "m",
                "base_snapshot": {"x": 1},
                "ours_snapshot": {"x": 2},
                "theirs_snapshot": {"x": 3},
            },
        ).json()
        detected = client.post(
            f"/api/ontology/branches/merge-requests/{mr['id']}/detect-conflicts"
        ).json()
        cid = detected["conflicts"][0]["id"]
        resp = client.post(
            f"/api/ontology/branches/merge-requests/{mr['id']}/resolve",
            json={
                "conflict_id": cid,
                "resolution": "use_ours",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["conflict"]["resolution"] == "use_ours"

    def test_execute_merge_endpoint_success(self, client):
        b1 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="src"),
        ).json()
        b2 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="tgt"),
        ).json()
        mr = client.post(
            f"/api/ontology/branches/{b1['id']}/merge-requests",
            json={
                "source_branch_id": b1["id"],
                "target_branch_id": b2["id"],
                "title": "m",
                "base_snapshot": {"a": 1, "b": 2},
                "ours_snapshot": {"a": 10, "b": 2},
                "theirs_snapshot": {"a": 1, "b": 20},
            },
        ).json()
        resp = client.post(
            f"/api/ontology/branches/merge-requests/{mr['id']}/execute"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "merged"

    def test_execute_merge_with_unresolved_returns_400(self, client):
        b1 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="src"),
        ).json()
        b2 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="tgt"),
        ).json()
        mr = client.post(
            f"/api/ontology/branches/{b1['id']}/merge-requests",
            json={
                "source_branch_id": b1["id"],
                "target_branch_id": b2["id"],
                "title": "m",
                "base_snapshot": {"x": 1},
                "ours_snapshot": {"x": 2},
                "theirs_snapshot": {"x": 3},
            },
        ).json()
        client.post(
            f"/api/ontology/branches/merge-requests/{mr['id']}/detect-conflicts"
        )
        resp = client.post(
            f"/api/ontology/branches/merge-requests/{mr['id']}/execute"
        )
        assert resp.status_code == 400

    def test_list_conflicts_endpoint(self, client):
        b1 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="src"),
        ).json()
        b2 = client.post(
            "/api/ontology/branches",
            json=self._create_branch_payload(name="tgt"),
        ).json()
        mr = client.post(
            f"/api/ontology/branches/{b1['id']}/merge-requests",
            json={
                "source_branch_id": b1["id"],
                "target_branch_id": b2["id"],
                "title": "m",
                "base_snapshot": {"x": 1},
                "ours_snapshot": {"x": 2},
                "theirs_snapshot": {"x": 3},
            },
        ).json()
        client.post(
            f"/api/ontology/branches/merge-requests/{mr['id']}/detect-conflicts"
        )
        resp = client.get(
            f"/api/ontology/branches/merge-requests/{mr['id']}/conflicts"
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_route_exception_passthrough_404(self, client):
        """except HTTPException: raise 必须透传（404 而非 500）"""
        resp = client.get("/api/ontology/branches/missing-id")
        assert resp.status_code == 404
        assert resp.status_code != 500

    def test_route_exception_passthrough_422(self, client):
        """Pydantic 校验失败返回 422（FastAPI 标准）"""
        resp = client.post(
            "/api/ontology/branches",
            json={"name": "x"},  # 缺字段 → 422
        )
        assert resp.status_code == 422
        assert resp.status_code != 500
