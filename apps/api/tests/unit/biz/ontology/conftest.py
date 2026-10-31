"""本体约束编排测试夹具：真实实现 + 边界假件（TBox / USL / OPA / 检索）。

原则：管线、对齐、守卫、检索、合成、契约门全部用**真实实现**；
只在外部系统边界注入假件（SQLite TBox 后端、OPA HTTP、检索引擎），
这样测的是真实编排逻辑，而不是自造的替身逻辑。
"""

from __future__ import annotations

import pytest

WORKSPACE = "ws-supply"
ORDER_REF = "doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A"


class FakeOntologyService:
    """TBox 真相源的替身（接口与 OntologyService 一致）。"""

    def list_ontologies(self, workspace_id=None):
        return {"ontologies": [{"ontology_id": "onto-supply"}]}

    def list_object_types(self, ontology_id):
        return {"object_types": [
            {"id": "Order", "name": "订单"},
            {"id": "Supplier", "name": "供应商"},
        ]}

    def list_link_types(self, ontology_id):
        return {"link_types": [{"id": "placedBy", "name": "下单方"}]}

    def list_indicator_types(self, ontology_id):
        return {"indicator_types": [
            {"id": "order_return_rate", "name": "退货率"},
            {"id": "supplier_fulfillment_rate", "name": "履约率"},
        ]}


#: 真实业务词条（USL 术语表结构）
USL_TERMS = [
    {"canonical": "退货率", "semantic_type": "对象类型",
     "synonyms": ["退货比例"], "domain_id": "dom-sales"},
    {"canonical": "订单", "semantic_type": "对象类型", "synonyms": [], "domain_id": "dom-sales"},
    {"canonical": "删除订单", "semantic_type": "动作类型", "synonyms": [], "domain_id": "dom-sales"},
    {"canonical": "已停用词", "semantic_type": "对象类型", "stoplist_flag": True},
]


class FakeOpaManager:
    """OPA HTTP 客户端替身：allow / deny / 不可用三种行为。"""

    def __init__(self, allow: bool = True, reason: str = "", fail: bool = False):
        self.allow = allow
        self.reason = reason
        self.fail = fail

    def check_permission_abac(self, user, action, resource, environment):
        if self.fail:
            raise ConnectionError("OPA 服务不可达（10.0.0.1:8181 连接被拒绝）")
        return {"allow": self.allow, "reason": self.reason}


class FakeEngine:
    """检索引擎替身（接口与 semantic_retrieval 引擎一致）。"""

    def __init__(self, rows=None, fail: bool = False):
        self.rows = rows or []
        self.fail = fail

    async def search(self, workspace_id, query, limit=20):
        if self.fail:
            raise RuntimeError("Neo4j 连接失败（graph engine）")
        return {"rows": list(self.rows), "total": len(self.rows)}


def evidence_rows(value: float = 0.184):
    return [{"doc_id": ORDER_REF, "metric_value": value, "asof": "2026-09-30"}]


class FakeOpaClient:
    """OPA HTTP 客户端替身（审批门用）：put_policy / check_package_permission。"""

    def __init__(self, allow: bool = True, fail: bool = False,
                 fail_put: bool = False):
        self.allow = allow
        self.fail = fail
        self.fail_put = fail_put
        self.put_calls: list[tuple[str, str]] = []
        self.eval_calls: list[tuple[str, dict]] = []

    def put_policy(self, policy_id: str, rego_content: str) -> bool:
        if self.fail_put:
            raise ConnectionError("OPA 策略装载失败（8181 连接被拒绝）")
        self.put_calls.append((policy_id, rego_content))
        return True

    def check_package_permission(self, package: str, opa_input: dict) -> bool:
        if self.fail:
            raise ConnectionError("OPA 包级检查失败（8181 连接被拒绝）")
        self.eval_calls.append((package, opa_input))
        return self.allow


class FakeApprovalManager:
    """审批门依赖的 OPAManager 替身（只用到 opa_client）。"""

    def __init__(self, client: FakeOpaClient):
        self.opa_client = client


class FakeGapService:
    """gap_pool 写入替身：记录调用，按配置决定成功/失败。"""

    def __init__(self, ok: bool = True):
        self.ok = ok
        self.calls: list[dict] = []

    def record_signal(self, source, expression: str, **kwargs):
        self.calls.append({"source": str(source), "expression": expression, **kwargs})
        if not self.ok:
            return {"status": "error", "message": "gap store unavailable"}
        return {"status": "ok", "gap": {"gap_id": f"gap-{len(self.calls):03d}"}}


@pytest.fixture
def fake_opa_client():
    return FakeOpaClient


@pytest.fixture
def fake_gap_service():
    return FakeGapService


@pytest.fixture
def make_approval_gate():
    """构造真实 OpaApprovalGate + 假 OPA 客户端（验证输入映射与 fail-closed）。"""
    from odap.biz.core.ontology.orchestration.actions.approval import OpaApprovalGate

    def _make(allow: bool = True, fail: bool = False, fail_put: bool = False):
        client = FakeOpaClient(allow=allow, fail=fail, fail_put=fail_put)
        gate = OpaApprovalGate(manager_factory=lambda: FakeApprovalManager(client))
        return gate, client

    return _make


@pytest.fixture
def action_repo(kb_db):
    from odap.biz.core.ontology.orchestration.actions.repository import QaActionRepository

    return QaActionRepository(db_path=kb_db)


@pytest.fixture
def action_service(action_repo, trace_repo, make_approval_gate):
    """真实 ActionService（仓储 + 执行器真实；审批门用假 OPA 客户端）。"""
    from odap.biz.core.ontology.orchestration.actions.executor import ActionExecutor
    from odap.biz.core.ontology.orchestration.actions.service import ActionService

    gate, _client = make_approval_gate(allow=True)
    return ActionService(
        repo=action_repo,
        executor=ActionExecutor(trace_repo=trace_repo),
        approval_gate=gate,
        trace_repo=trace_repo,
    )


@pytest.fixture
def tbox_catalog():
    from odap.biz.core.ontology.orchestration.tbox import TBoxCatalog

    return TBoxCatalog(ontology_service_factory=lambda: FakeOntologyService())


@pytest.fixture
def intent_router():
    from odap.biz.core.ontology.orchestration.impl.intent_router import (
        L1IntentRouter,
        UslDictionary,
    )

    return L1IntentRouter(dictionary=UslDictionary(loader=lambda: list(USL_TERMS)))


@pytest.fixture
def resolver(tbox_catalog):
    """证据解析器：外部系统（USL 表 / 文档库）用边界替身，其余走真实解析。"""
    from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

    return DefaultEvidenceResolver(
        catalog=tbox_catalog,
        doc_verifier=lambda ref: (True, "") if ref == ORDER_REF else (False, "文档不存在"),
        usl_verifier=lambda ref: (True, ""),
    )


@pytest.fixture
def kb_db(tmp_path):
    """独立 SQLite（qa_traces / qa_provenance 落在这里）。"""
    from odap.infra.storage.schema_v2 import ensure_v2_schema

    path = str(tmp_path / "odap_main.db")
    ensure_v2_schema(path)
    return path


@pytest.fixture
def trace_repo(kb_db):
    from odap.biz.core.ontology.orchestration.repositories.trace_repo import QaTraceRepository

    return QaTraceRepository(db_path=kb_db)


@pytest.fixture
def fake_ontology_service():
    return FakeOntologyService


@pytest.fixture
def fake_engine():
    return FakeEngine


@pytest.fixture
def fake_opa():
    return FakeOpaManager


@pytest.fixture
def evidence_rows_factory():
    return evidence_rows


@pytest.fixture
def build_pipeline(tbox_catalog, intent_router, resolver, trace_repo, action_service):
    """按需装配管线（OPA / 检索引擎 / TBox / 动作服务可逐个用例替换）。"""
    from odap.biz.core.ontology.orchestration.impl.answer_composer import (
        EvidenceOnlyAnswerComposer,
    )
    from odap.biz.core.ontology.orchestration.impl.ontology_aligner import TBoxOntologyAligner
    from odap.biz.core.ontology.orchestration.impl.output_contract_gate import (
        StrictOutputContractGate,
    )
    from odap.biz.core.ontology.orchestration.impl.retrieval_executor import (
        MultiEngineRetrievalExecutor,
    )
    from odap.biz.core.ontology.orchestration.impl.rule_guard import OPARuleGuard
    from odap.biz.core.ontology.orchestration.pipeline import QaPipeline

    def _build(*, opa: FakeOpaManager | None = None, engines: dict | None = None,
               catalog=None, router=None, actions=None):
        active_catalog = catalog or tbox_catalog
        return QaPipeline(
            intent_router=router or intent_router,
            aligner=TBoxOntologyAligner(active_catalog),
            guard=OPARuleGuard(opa_manager_factory=lambda: opa or FakeOpaManager()),
            retriever=MultiEngineRetrievalExecutor(
                engine_factories=engines or {
                    "graph": lambda: FakeEngine(evidence_rows()),
                },
                timeout_seconds=2.0,
            ),
            composer=EvidenceOnlyAnswerComposer(),
            gate=StrictOutputContractGate(),
            trace_repo=trace_repo,
            catalog=active_catalog,
            resolver=resolver,
            action_service=actions or action_service,
        )

    return _build
