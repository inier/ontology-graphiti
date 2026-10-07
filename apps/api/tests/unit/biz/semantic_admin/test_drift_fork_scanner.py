from odap.biz.semantic_admin.usl_manager.models.usl_term import UslTerm, SemanticType
from odap.biz.semantic_admin.drift_scan.services.scanners import fork_scan


def _term(id, canonical, dom="d1", **kw):
    return UslTerm(id=id, domain_id=dom, canonical=canonical,
                   semantic_type=SemanticType.OBJECT_TYPE, **kw).model_dump()


def test_fork_detected_when_expression_maps_to_two_terms():
    terms = [
        _term("t1", "势力", synonyms=["阵营"]),
        _term("t2", "军团", synonyms=["阵营"]),   # “阵营” 同时挂 t1/t2
    ]
    findings = fork_scan(terms, scope={"domain_id": "d1"})
    assert len(findings) == 1
    f = findings[0]
    assert f["kind"] == "fork"
    assert f["subject"] == "阵营"
    sides = {s["term_id"] for s in f["sides_json"]}
    assert sides == {"t1", "t2"}


def test_stoplist_excluded():
    terms = [
        _term("t1", "势力", synonyms=["的"]),
        _term("t2", "军团", synonyms=["的"], stoplist_flag=True),
    ]
    # t2 停用词整体不参与；“的” 只挂 t1 → 无 fork
    assert fork_scan(terms, scope={}) == []


def test_empty_and_whitespace_excluded():
    terms = [_term("t1", "势力", synonyms=["", "  "]), _term("t2", "军团", aliases=[""])]
    assert fork_scan(terms, scope={}) == []


def test_single_term_expression_no_false_positive():
    terms = [_term("t1", "势力", synonyms=["阵营"]), _term("t2", "人物")]
    assert fork_scan(terms, scope={}) == []


def test_canonical_collision_is_fork():
    terms = [_term("t1", "势力", dom="d1"), _term("t2", "势力", dom="d2")]
    findings = fork_scan(terms, scope={})
    assert len(findings) == 1
    assert findings[0]["subject"] == "势力"
