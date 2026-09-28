"""_soft_delete 共享软删工具单元测试。"""
from odap.infra.graph import _soft_delete as sd


def test_active_predicates_are_stable_strings():
    assert sd.ACTIVE_NODE_PREDICATE == "n.invalid_at IS NULL"
    assert sd.ACTIVE_REL_PREDICATE == "r.invalid_at IS NULL"


def test_is_active_true_when_missing_or_empty():
    assert sd.is_active({}) is True
    assert sd.is_active(None) is True
    assert sd.is_active({"invalid_at": ""}) is True
    assert sd.is_active({"invalid_at": None}) is True


def test_is_active_false_when_marked():
    assert sd.is_active({"invalid_at": "2026-09-28T10:00:00+00:00"}) is False


def test_now_iso_is_utc_offset_string():
    ts = sd.now_iso()
    assert isinstance(ts, str)
    assert ts.endswith("+00:00")
    # 可被 datetime 解析
    from datetime import datetime
    datetime.fromisoformat(ts)
