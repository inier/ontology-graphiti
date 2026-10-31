"""知识域（Wiki + 文档治理）测试夹具。

纪律：
- 每个用例独立 SQLite 文件（`tmp_path`），不污染 `DATA_DIR/odap_main.db`。
- 测试数据用真实业务语义（订单退货率 / 供应商履约），不用 foo/bar。
"""

from __future__ import annotations

import pytest

#: 固定"今天"，使陈旧判定（AC-13）可复算，不受运行日期影响
TODAY = "2026-10-17"


@pytest.fixture
def kb_db(tmp_path):
    """独立的知识域数据库路径（已建 v2 schema）。"""
    from odap.infra.storage.schema_v2 import ensure_v2_schema

    path = str(tmp_path / "odap_main.db")
    ensure_v2_schema(path)
    return path


@pytest.fixture
def entry_service(kb_db):
    from odap.biz.knowledge.wiki.services.entry_service import WikiEntryService

    return WikiEntryService(db_path=kb_db)


@pytest.fixture
def version_service(kb_db):
    from odap.biz.knowledge.wiki.services.version_service import VersionService

    return VersionService(db_path=kb_db)


@pytest.fixture
def citation_service(kb_db):
    from odap.biz.knowledge.wiki.services.citation_service import CitationService

    return CitationService(db_path=kb_db)


@pytest.fixture
def dedupe_service(kb_db):
    from odap.biz.knowledge.wiki.services.dedupe_service import DedupeService

    return DedupeService(db_path=kb_db)


@pytest.fixture
def doc_repo(kb_db):
    from odap.biz.knowledge.governance.repositories.doc_repo import GovernedDocRepository

    return GovernedDocRepository(db_path=kb_db)


@pytest.fixture
def doc_service(kb_db):
    from odap.biz.knowledge.governance.services.doc_service import DocService

    return DocService(db_path=kb_db, today=TODAY)


@pytest.fixture
def verify_service(kb_db):
    from odap.biz.knowledge.governance.services.verify_service import VerifyService

    return VerifyService(db_path=kb_db, today=TODAY)


@pytest.fixture
def supersede_service(kb_db):
    from odap.biz.knowledge.governance.services.supersede_service import SupersedeService

    return SupersedeService(db_path=kb_db)


@pytest.fixture
def sync_service(kb_db):
    from odap.biz.knowledge.governance.services.sync_service import SyncService

    return SyncService(db_path=kb_db, approval_checker=lambda approval_id: True)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    """伪装仓库根（含 docs/ 与 apps/），使同步服务不触达真实仓库文件。"""
    root = tmp_path / "fake-repo"
    (root / "docs" / "02-architecture").mkdir(parents=True)
    (root / "apps").mkdir(parents=True)
    monkeypatch.setenv("ODAP_REPO_ROOT", str(root))
    return root


@pytest.fixture
def make_entry(entry_service):
    """创建一个已发布条目（供引用图/去重用例复用）。"""

    def _make(title: str, content: str, owner: str = "u-owner", publish: bool = True, **kwargs):
        entry = entry_service.create(title=title, content=content, owner=owner, **kwargs)
        return entry_service.publish(entry.id, actor_id=owner) if publish else entry

    return _make
