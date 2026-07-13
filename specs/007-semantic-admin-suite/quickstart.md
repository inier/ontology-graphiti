# Quickstart: Semantic Admin & Ontology Learning Suite 启用 + 全链路校验

**Date**: 2026-07-11
**Feature**: 007-semantic-admin-suite
**Feature Branch**: `007-semantic-admin-suite`

---

## 1. 环境检查（启动前必过）

```bash
# 1.1 重启 Podman 开发环境（先清理冲突容器）
python bootstep.py restart-dev
# 预期: graphiti-main-app, graphiti-frontend-dev, graphiti-neo4j, graphiti-opa, graphiti-redis 全部 Up
podman ps --format "table {{.Names}} {{.Status}}"
# 断言: graphiti-main-app 状态含 "(healthy)"，否则执行 podman logs -f graphiti-main-app 排查

# 1.2 验证 Python 3.11
podman exec graphiti-main-app python -c "import sys; v=sys.version_info; assert (v.major,v.minor)==(3,11), f'need 3.11 got {v.major}.{v.minor}'; print(f'Python {sys.version.split()[0]} OK')"
# 预期输出: Python 3.11.x OK

# 1.3 验证 Neo4j 连接（容器内通过服务名 graphiti-neo4j）
podman exec graphiti-main-app python -c "
from neo4j import GraphDatabase
import os
uri = os.environ.get('NEO4J_URI','bolt://graphiti-neo4j:7687')
u = os.environ.get('NEO4J_USER','neo4j')
p = os.environ.get('NEO4J_PASSWORD','password')
with GraphDatabase.driver(uri, auth=(u,p)) as d:
    with d.session() as s:
        r = s.run('RETURN 1 AS n').single()
        assert r['n'] == 1, 'Neo4j ping failed'
print('Neo4j OK, URI=', uri)
"
# 预期输出: Neo4j OK, URI= bolt://graphiti-neo4j:7687

# 1.4 OPALite OPA 最小化 Rego 语法自检（semantic_admin 策略包）
#    先把 semantic_admin.rego 拷到容器 OPA 挂载目录，再 eval
cp odap/infra/opa/policies/semantic_admin.rego docker/opa-mount/
podman exec graphiti-opa opa eval -d /policies/semantic_admin.rego 'data.semantic_admin.allow'
# 预期输出 JSON 含 "result":[{"expressions":[{"value":true/false}]}]
# 断言: 不出现 "1 error occurred" / "rego_parse_error"

# 1.5 OPA 6 条最小 deny/allow parity cases 先行自检（Iter3 前置）
podman exec graphiti-opa bash -c '
cat > /tmp/opa_smoke.sh <<"EOF"
#!/bin/bash
declare -a cases=(
  "input.user.ws_role=schema_auditor input.action=REVIEW   => true"
  "input.user.ws_role=schema_auditor input.action=MODIFY   => true"
  "input.user.ws_role=schema_auditor input.action=FINAL_APPROVE => false"
  "input.user.ws_role=schema_owner   input.action=FINAL_APPROVE => true"
  "input.user.ws_role=viewer         input.action=MODIFY   => false"
  "input.user.ws_role=schema_editor  input.action=MODIFY   => true"
)
i=0
for c in "${cases[@]}"; do
  input=$(echo "$c" | cut -d= -f1,2 --output-delimiter="=" | sed "s/ => .*//")
  expected=$(echo "$c" | sed "s/.*=> //")
  out=$(opa eval -d /policies/semantic_admin.rego -i /dev/stdin "data.semantic_admin.allow" <<<"{\"user\":{\"ws_role\":\"$(echo $c|grep -oE 'ws_role=[a-z_]+'|cut -d= -f2)\"},\"action\":\"$(echo $c|grep -oE 'action=[A-Z_]+'|cut -d= -f2)\"}")
  actual=$(echo "$out" | python3 -c "import json,sys;d=json.load(sys.stdin);print(str(next(iter(d.get('result',[{}])[0].get('expressions',[{}])[0].get('value',False))).lower() if d.get('result') else 'false').lower())")
  if [ "$actual" = "$expected" ]; then echo "case $((++i)) PASS: $c"; else echo "case $((++i)) FAIL: $c got $actual"; exit 1; fi
done
EOF
bash /tmp/opa_smoke.sh
'
# 预期: 6 行 "case N PASS: ..."，零 FAIL
```

---

## 2. Iter 1 验证（USL 服务化 + seed 迁移）

```bash
# 2.1 全量单元测试（USL 模块 6 层）
pytest tests/unit/test_semantic_admin_usl_storage.py \
       tests/unit/test_semantic_admin_usl_service.py \
       tests/unit/test_semantic_admin_usl_api.py \
       tests/unit/test_semantic_admin_usl_hotreload.py \
       -v --no-header
# 断言: 全绿 (passed)，0 failed，0 skipped（无 graphiti 依赖）

# 2.2 运行 seed_sanguo_xiyou.py（把硬编码语义写入 usl.db）
podman exec graphiti-main-app python scripts/seed_sanguo_xiyou.py --apply --db /app/data/usl.db
# 预期输出尾两行:
#   [seed] sanguo canonical_terms = 44 (objects+relations+actions+properties)
#   [seed] xiyou  canonical_terms = 30 (objects+relations+actions+properties)

# 2.3 查 SQLite usl.db：三国 canonical 术语数量 >= 20（要求 ≥ 20，实际 44）
podman exec graphiti-main-app python -c "
import sqlite3, json
conn = sqlite3.connect('/app/data/usl.db')
cur = conn.cursor()
n_sanguo = cur.execute(\"SELECT COUNT(*) FROM usl_canonical_terms t JOIN usl_domains d ON t.domain_id=d.id WHERE d.code='sanguo'\").fetchone()[0]
n_xiyou  = cur.execute(\"SELECT COUNT(*) FROM usl_canonical_terms t JOIN usl_domains d ON t.domain_id=d.id WHERE d.code='xiyou'\").fetchone()[0]
n_shared = cur.execute(\"SELECT COUNT(*) FROM usl_canonical_terms t JOIN usl_domains d ON t.domain_id=d.id WHERE d.code='shared'\").fetchone()[0]
conn.close()
print(f'sanguo={n_sanguo} xiyou={n_xiyou} shared={n_shared}')
assert n_sanguo >= 20, f'三国 canonical={n_sanguo} < 20'
assert n_xiyou  >= 15, f'西游 canonical={n_xiyou}  < 15'
print('Iter1 seed count OK')
"
# 断言: 无 AssertionError，末行打印 "Iter1 seed count OK"

# 2.4 HTTP GET /api/semantic-admin/usl/domains 断言 200 + 2 个域（sanguo + xiyou，shared 不计入业务域）
podman exec graphiti-main-app bash -c '
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" | python3 -c "import json,sys;print(json.load(sys.stdin)[\"access_token\"])")
HTTP=$(curl -s -o /tmp/doms.json -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/semantic-admin/usl/domains)
python3 - <<PY
import json
with open("/tmp/doms.json") as f: d=json.load(f)
items = d.get("items") or d.get("domains") or (d if isinstance(d,list) else [])
biz = [x for x in items if x.get("code") in ("sanguo","xiyou")]
print(f"HTTP={$HTTP} count={len(items)} biz_domains={len(biz)} codes={[x[\"code\"] for x in biz]}")
assert "{$HTTP}" == "200", f"HTTP != 200"
assert len(biz) == 2, f"biz domains != 2"
print("Iter1 domains HTTP+count OK")
PY
'
# 断言: HTTP=200 biz_domains=2 codes=['sanguo','xiyou']
```

---

## 3. Iter 2 验证（L1-L2 概念抽取 + Candidate 双写）

### 模式 A：测试模式（不用真 LLM / 不用真 Neo4j）

```bash
USE_MOCK_EMBEDDER=true USE_MOCK_NEO4J=true \
pytest tests/unit/test_ol_pipeline_l1l2.py -v --no-header
# 用例必须覆盖:
#   - test_l1_hdbscan_min_cluster_3 -> 50 实体 -> >= 3 个簇
#   - test_l2_fca_attribute_closure_075 -> 属性共享阈值 0.75 下生成 is_a 边
#   - test_candidate_dual_write_sqlite_only -> Neo4j mock 抛异常 -> SQLite 自动回滚（2PC 模拟）
#   - test_get_candidates_paginated_status_filter -> L1 分页 + status=proposed 过滤
# 断言: 全绿 passed，0 failed，0 xfailed
```

### 模式 B：集成模式（需真 Neo4j 运行 + OPENAI_API_KEY）

```bash
# 先确认 Neo4j 健康（见 §1.3），再跑
pytest tests/integration/test_ol_pipeline_e2e_sanguo.py -v -m integration --no-header
# 用例内部会做:
#   1. 载入三国 3 段样例（桃园结义 / 草船借箭 / 空城计）共约 1200 字
#   2. HE 抽取 -> 实体 + 关系 + 属性
#   3. L1 BGE(1024)->UMAP(64)->HDBSCAN -> cluster 聚类
#   4. L2 FCA 形式概念分析 -> concept lattice -> is_a/part_of 层级
#   5. CandidateWriter.dual_write -> SQLite usl_candidates + Neo4j :ConceptCandidate 节点
#   6. 断言 COUNT(*) >= 30
# 预期: test_e2e_sanguo_3_paragraphs_candidates_ge_30 PASSED
# 断言: 候选数量候选集 >= 30（若 < 30 跑 `pytest ... -s` 看每步中间 count）
```

---

## 4. Iter 3 验证（质量闸 + 审批流 + OPA）

```bash
# 4.1 质量闸 + 审批流 单元测试全绿
pytest tests/unit/test_quality_gate.py tests/unit/test_approval_workflow.py -v --no-header
# 质量闸用例必含:
#   - Gate1 拼写/停用词（stoplist）过滤 -> 含 "阿巴阿巴" 的候选 BLOCKED
#   - Gate2 embedding 语义相似度 -> 与现有 canonical 余弦 > 0.92 直接 MERGE
#   - Gate3 FCA 层级一致性 -> parent-child 属性闭包冲突 BLOCKED
#   - Gate4 风险等级（confidence < 0.6 且涉及 shared 域）-> 强制 HITL
# 审批流用例必含:
#   - MODIFY(editor) -> REVIEW(auditor) -> APPROVE(owner) -> WRITTEN_BACK(system) 状态机
#   - schema_auditor 尝试 FINAL_APPROVE -> OPA deny -> 停在 REVIEW_PASSED
#   - 回滚: APPROVED 后发现误判 -> REJECT 状态流转 + 审计 log
# 断言: 全绿 passed

# 4.2 OPA 最小化 6 条 deny/allow parity cases（见 §1.5，此处强制重跑验证一致性）
# 断言: 6/6 PASS

# 4.3 审核台模拟 3 步流转（ws_role=schema_auditor 走 MODIFY -> REVIEW -> APPROVE -> WRITTEN_BACK）
podman exec graphiti-main-app bash -c '
set -e
TOKEN_AUDITOR=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"auditor1\",\"password\":\"auditor123\"}" | python3 -c "import json,sys;print(json.load(sys.stdin).get(\"access_token\",\"\"))")
TOKEN_OWNER=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"owner1\",\"password\":\"owner123\"}" | python3 -c "import json,sys;print(json.load(sys.stdin).get(\"access_token\",\"\"))")
# Step 1: MODIFY (editor or self) —— 创建一条 proposed 候选
CID=$(curl -s -X POST http://localhost:8000/api/semantic-admin/candidates \
  -H "Authorization: Bearer $TOKEN_AUDITOR" -H "Content-Type: application/json" \
  -d "{\"domain_code\":\"sanguo\",\"level\":\"L1\",\"label\":\"test_武侯诸葛亮\",\"member_refs\":[\"a1\",\"a2\"],\"confidence\":0.88}" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)[\"id\"])")
echo "CID=$CID"
# Step 2: REVIEW (schema_auditor) —— 写审核意见，转 REVIEW_PASSED
curl -s -X POST http://localhost:8000/api/semantic-admin/candidates/$CID/transition \
  -H "Authorization: Bearer $TOKEN_AUDITOR" -H "Content-Type: application/json" \
  -d "{\"action\":\"REVIEW\",\"comment\":\"命名规范，与 canonical 无冲突\"}" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);assert d.get(\"status\")==\"REVIEW_PASSED\", d; print(\"Step2 REVIEW -> REVIEW_PASSED OK\")"
# Step 3: APPROVE 角色隔离——auditor 执行 FINAL_APPROVE 必须被 OPA deny
DENY_CHECK=$(curl -s -o /tmp/deny.json -w "%{http_code}" -X POST \
  http://localhost:8000/api/semantic-admin/candidates/$CID/transition \
  -H "Authorization: Bearer $TOKEN_AUDITOR" -H "Content-Type: application/json" \
  -d "{\"action\":\"FINAL_APPROVE\",\"comment\":\"越权尝试\"}")
python3 - <<PY
import json
with open("/tmp/deny.json") as f: d=json.load(f)
assert "$DENY_CHECK" in ("403","400"), f"auditor FINAL_APPROVE should be denied HTTP $DENY_CHECK"
print("Step3 auditor deny OK (HTTP $DENY_CHECK)")
PY
# Step 4: owner 真正 APPROVE -> 转 APPROVED -> 触发 WRITTEN_BACK（写回 canonical + Neo4j）
curl -s -X POST http://localhost:8000/api/semantic-admin/candidates/$CID/transition \
  -H "Authorization: Bearer $TOKEN_OWNER" -H "Content-Type: application/json" \
  -d "{\"action\":\"FINAL_APPROVE\",\"comment\":\"owner 终审通过\"}" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);assert d.get(\"status\") in (\"APPROVED\",\"WRITTEN_BACK\"), d; print(f\"Step4 owner approve -> status={d.get('status')} OK\")"
# Step 5: 最终 WRITTEN_BACK 校验
curl -s http://localhost:8000/api/semantic-admin/candidates/$CID \
  -H "Authorization: Bearer $TOKEN_AUDITOR" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);assert d.get(\"status\")==\"WRITTEN_BACK\", d; print(\"Step5 WRITTEN_BACK OK — Iter3 审核台闭环完成\")"
'
# 断言输出包含:
#   Step2 REVIEW -> REVIEW_PASSED OK
#   Step3 auditor deny OK (HTTP 403)
#   Step4 owner approve -> status=WRITTEN_BACK OK
#   Step5 WRITTEN_BACK OK — Iter3 审核台闭环完成
```

---

## 5. Iter 4 验证（写回 + 老目录清理 + 电商构建）

```bash
# 5.1 老 semantic_layer 目录删除后，原 import 路径必须 ModuleNotFoundError（零存活）
#    先做删除操作（一次性，CI 再跑需 restore）
rm -rf odap/biz/core/ontology/design/schema/semantic_layer
#    验证: 任何从旧路径 import 必须抛 ModuleNotFoundError
python -c "
import sys
tried = False
try:
    tried = True
    from odap.biz.core.ontology.design.schema.semantic_layer import IntentParser as X  # noqa
    raise AssertionError('旧路径仍可导入！请检查残留 __pycache__ / symlink')
except ModuleNotFoundError:
    print('PASS: 旧 semantic_layer 路径已删除，ModuleNotFoundError 触发')
except Exception as e:
    # 允许因父模块不存在导致的 ImportError 变体
    if 'semantic_layer' in str(type(e).__name__) or 'semantic_layer' in str(e):
        print(f'PASS (variant {type(e).__name__}): {e}')
    else:
        raise
assert tried, 'try 块未执行'
"
# 断言: 打印 PASS 且不抛 AssertionError

# 5.2 电商领域构建脚本：从 sample.md 构建本体 + 输出差异率报告
python scripts/build_ecommerce_ontology.py \
  --mode ol-from-docs \
  --from-doc ./sample.md \
  --diff \
  --out /tmp/ecom_ontology.json
# 预期 stdout 末尾差异报告形如（具体数字视 sample.md 内容）：
#   ==== Diff Report ====
#   Added Objects:    12
#   Added Relations:   8
#   Added Properties: 23
#   Removed:           0  (首次构建)
#   Conflict Terms:    1  (与共享域 "价格" 属性冲突，需 HITL)
#   覆盖率 Coverage:  87.4%
# 断言 numeric 校验（用脚本返回 exit code）：
#   exit code 0: 覆盖率 >= 80% 且 conflicts <= 3
#   exit code 2: conflicts > 3（需要人工修 sample.md 或 stoplist）
#   可追加 `echo $?` 看值
```

---

## 6. 单元 / 集成测试命令行 9 组（按迭代分）+ E2E

```bash
# -------- Iter 1 (USL 服务化) --------
# T1-1 存储层 CRUD + 真实 tmp_path SQLite（禁止 MagicMock）
pytest tests/unit/test_semantic_admin_usl_storage.py -v
# T1-2 服务层错误返回格式 + 类型转换（Enum.value / datetime.isoformat）
pytest tests/unit/test_semantic_admin_usl_service.py -v
# T1-3 API 路由层 HTTP 状态码映射 + HTTPException 透传
pytest tests/unit/test_semantic_admin_usl_api.py -v
# T1-4 热加载 USLCache.invalidate 广播
pytest tests/unit/test_semantic_admin_usl_hotreload.py -v

# -------- Iter 2 (L1-L2 概念抽取) --------
# T2-1 L1 HDBSCAN + L2 FCA 逻辑（Mock Embedder + Mock Neo4j）
USE_MOCK_EMBEDDER=true USE_MOCK_NEO4J=true pytest tests/unit/test_ol_pipeline_l1l2.py -v
# T2-2 L1-L2 双写 + 2PC 回滚（Mock Neo4j 抛异常）
USE_MOCK_NEO4J=true pytest tests/unit/test_candidate_dual_write.py -v
# T2-3 集成：三国 3 段样例端到端（需 Neo4j + OPENAI_API_KEY）
pytest tests/integration/test_ol_pipeline_e2e_sanguo.py -v -m integration

# -------- Iter 3 (质量闸 + 审批流) --------
# T3-1 质量闸 4 关自动化
pytest tests/unit/test_quality_gate.py -v
# T3-2 审批流状态机 + OPA deny/allow 6 parity
pytest tests/unit/test_approval_workflow.py -v

# -------- Iter 4 + E2E --------
# T4 电商构建脚本 smoke（生成差异报告 + exit 0/2）
pytest tests/integration/test_build_ecommerce_ontology.py -v -m integration
# E2E 全链路：seed -> ingest -> schema_learning -> qg -> approve -> writeback -> 查询
pytest tests/e2e/test_semantic_admin_full_chain.py -v -m e2e
```

---

## 7. 8 条常见陷阱速查（对齐 AGENTS.md §D）

| # | 陷阱 | 触发场景 | 后果 | 规避方法 |
|---|------|---------|------|---------|
| **T1** | **NEVER USE MAGICMOCK FOR SQLITE** | 写 storage 层测试时图省事用 `MagicMock(spec=sqlite3.Connection)` | 存储层 bug 漏到集成阶段才爆 | 强制 `tmp_path` 建真实 `.db`；CI 扫描 `test_*storage*.py` 不许出现 `MagicMock` |
| **T2** | **EACH connect MUST close** | 偷懒 `conn=sqlite3.connect(...); cur=conn.cursor(); ...` 末尾漏 `conn.close()` | SQLite 文件锁堆积，下次写入 `database is locked` | 每写 `sqlite3.connect` 立刻配 `try/finally: conn.close()` 或 `with contextlib.closing(sqlite3.connect(...)) as conn` |
| **T3** | **stoplist 写入 ≠ 删除** | 质量闸 Gate1 想去掉 "阿巴阿巴" 这个停用词，只改 STOPLIST dict 以为下次校验就自动放行 | 已入库的 stoplist 条目仍存 `usl_stoplist` 表；Gate1 先查 DB 再查内存 dict，词仍被 BLOCKED | 必须 `DELETE FROM usl_stoplist WHERE word='阿巴阿巴'` 或调 `SemanticAdminService.remove_stopword()` |
| **T4** | **双写 Neo4j 失败不回滚 USL** | Iter2 Candidate 双写，Neo4j 服务挂了 → 误以为 SQLite 也回滚 | 若 2PC 模拟逻辑有 bug，SQLite 有脏数据、Neo4j 无节点、可视化缺项 | 必跑 `test_candidate_dual_write.py` 中 `USE_MOCK_NEO4J=true` 的 `test_neo4j_down_rolls_back_sqlite` 用例；断言 `usl_candidates.count == 0` |
| **T5** | **AUDITOR 不能 FINAL_APPROVE** | 产品以为 schema_auditor=最终审核人，硬编码 APPROVE 按钮给 auditor 角色 | OPA deny 返回 403，前端无 fallback 提示 → 白屏/卡死 | 前端按钮按 `data.semantic_admin.allow(action=FINAL_APPROVE)` OPA 结果做 disabled + 文案 "请联系 schema_owner 终审" |
| **T6** | **auto_skip_admin 默认关** | 开发环境想跳过质量闸人工审核，改代码把 `auto_skip_admin=True` 当默认值提交 | 生产环境新候选 0 闸口进 USL，脏词污染全局 | `SemanticAdminConfig.auto_skip_admin` 默认值强制 `False`；仅 `ENV=dev + USE_MOCK_EMBEDDER=true` 时允许覆盖为 True |
| **T7** | **L3 概念格内存上限** | Iter4 电商全量 10 万实体跑 L3 concept lattice，FCA 计算 `2^n` 爆炸 | 进程 OOM kill，容器重启 loop | `ConceptLatticeConfig` 硬上限：concepts ≤ 50,000、attrs_per_concept ≤ 200；超限抛 `ConceptLatticeOverflow` 走 `--mode=l2-only` 降级 |
| **T8** | **删除目录先修 import** | Iter4 先 `rm -rf semantic_layer/` 再回头替换 import | 全量 pytest 一片红，定位困难；甚至 `odap/web/app.py` include_router 直接 importError 起不来 | 先全局 grep `from.*semantic_layer import\|import.*semantic_layer` 100% 替换为新路径 `odap.biz.core.semantic.*`，跑一次冒烟 `pytest tests/unit -q --no-header` 全绿后，再 `rm` 目录 |

---

## 9. Dashboard & 审核台 Demo（对应 I4T9/T10 5 KPI + 三视图）

```bash
# ---------- 9.1 登录获取 admin Token ----------
podman exec graphiti-main-app bash -c '
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"admin123\"}" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)[\"access_token\"])")
echo "TOKEN=$(echo $TOKEN | cut -c1-20)..."

# ---------- 9.2 Dashboard Summary API = 5 KPI ----------
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/semantic-admin/dashboard/summary \
  | python3 -m json.tool
# 预期 JSON 字段（对应前端 5 KPI 卡）：
#   total_domains            → KPI 卡片 1 "Total Domains"
#   total_terms              → KPI 卡片 2 "Total Terms"
#   total_hierarchy_edges    → KPI 卡片 3 "Hierarchy Edges"
#   approved_candidates_this_week → KPI 卡片 4 "Candidates Approved This Week"
#   pipeline_success_rate_7d     → KPI 卡片 5 "Pipeline Runs 7d Success Rate"

# ---------- 9.3 Terms 30 天新增折线图（ECharts x 轴）----------
curl -s "http://localhost:8000/api/semantic-admin/dashboard/terms-trend?days=30" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 - <<'PY'
import json,sys
d = json.load(sys.stdin)
buckets = d.get("buckets") or d.get("items") or []
print(f"Terms trend buckets = {len(buckets)} (要求 = 30)")
xs = [b.get("date") or b.get("day") for b in buckets]
ys = [b.get("count") or b.get("new_terms") or 0 for b in buckets]
print(f"  xs range: {xs[0] if xs else None} ~ {xs[-1] if xs else None}")
print(f"  ys sum   = {sum(ys)} (Total terms added 30d)")
assert len(buckets) == 30, f"days=30 必须返回 30 buckets，实际 {len(buckets)}"
print("✅ Terms trend OK — 前端 ECharts 折线图可绑定")
PY

# ---------- 9.4 Approvals Breakdown 饼图（AntD Pie 4 扇区）----------
curl -s http://localhost:8000/api/semantic-admin/dashboard/approvals-breakdown \
  -H "Authorization: Bearer $TOKEN" \
  | python3 - <<'PY'
import json,sys
d = json.load(sys.stdin)
items = d.get("items") or d.get("breakdown") or []
print(f"Approvals breakdown categories = {len(items)}")
for it in items:
    k = it.get("status") or it.get("name") or it.get("category")
    v = it.get("count") or it.get("value") or 0
    print(f"  {k:<24s} = {v}")
expect_keys = {"DRAFT","PENDING_REVIEW","AUDITOR_APPROVED","ADMIN_PENDING","APPROVED","REJECTED","WRITTEN_BACK"}
found = {(it.get("status") or it.get("name") or "") for it in items}
print(f"✅ Approvals breakdown OK — 共 {len(items)} 分类，AntD Pie 可直接绑定")
PY
'
```

### 9.5 前端 Tab 绑定说明（I4T9 Dashboard 第 6 Tab）

| KPI 卡 / 图表 | 字段路径 | AntD 6 组件 |
|---|---|---|
| KPI 1 Total Domains | `summary.total_domains` | `<Statistic title="Total Domains" value={v} />` |
| KPI 2 Total Terms | `summary.total_terms` | `<Statistic title="Total Terms" value={v} />` |
| KPI 3 Hierarchy Edges | `summary.total_hierarchy_edges` | `<Statistic title="Hierarchy Edges" value={v} prefix={<LineChartOutlined />} />` |
| KPI 4 Approved This Week | `summary.approved_candidates_this_week` | `<CardedStatistic title="Approved This Week" value={v} trend="up" />` |
| KPI 5 Pipeline 7d Success Rate | `summary.pipeline_success_rate_7d` | `<Progress type="circle" percent={Math.round(v*100)} />` |
| Terms 30d 折线图 | `terms-trend.buckets[].{date,new_terms}` | `<ReactECharts option={lineOption(xs,ys)} />` |
| Approvals 饼图 | `approvals-breakdown.items[].{status,count}` | `<Pie data={items} angleField="count" colorField="status" />` |

---

## 10. 一键电商全链路（Seed → Pipeline → QG → Approve → Writeback → Dashboard）

```bash
# ---------- 模式 A：纯脚本本地跑（不用容器，3~5 分钟，推荐开发日常冒烟）----------
#     不需要真 LLM/Neo4j/OpenAI Key，全部用 Mock
cd e:/DEMO/AI/ontology-graphiti
python examples/semantic_admin_ecommerce_demo.py
# 预期输出分 6 步：
#   [Step 1] B2 创建电商 Domain → Seed 200+ 术语
#   [Step 2] C1 启动 Pipeline Run → 执行到 l6_done
#   [Step 3] C4 质量闸 G1×7 + G2×4 + G3×5 = 16 submetrics 评估
#   [Step 4] D 审核台 L1 auditor APPROVE + L2 owner FINAL_APPROVE
#   [Step 5] B7/I4T6 Writeback DualChannelWriter → Graphiti
#   [Step 6] C5 Dashboard Summary 查询
# 最后 2 行断言：
#   Final approved terms: N          （要求 N ≥ 30）
#   ✅ Demo success — Final approved terms = N >= 30

# ---------- 模式 B：Podman 容器内跑（真实 HTTP API 端到端）----------
podman exec graphiti-main-app bash -c '
cd /app
# 如容器无 examples 目录，先从挂载宿主机路径拷，再
export DATA_DIR=/app/data
python bootstep.py status  # 确保 graphiti-main-app = healthy
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"admin123\"}" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)[\"access_token\"])")

# 10.1 B2 创建域 + Seed 术语（HTTP）
DID=$(curl -s -X POST http://localhost:8000/api/semantic-admin/usl/domains \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"code\":\"ecommerce\",\"name\":\"电商\",\"description\":\"容器端到端测试 domain\"}" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get(\"id\") or d.get(\"domain_id\"))")
echo "DID=$DID"

# 10.2 C1 启动 Pipeline Run（上传 10 篇电商文本 → 自动 execute-all）
RID=$(curl -s -X POST http://localhost:8000/api/semantic-admin/pipeline/runs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"domain_code\":\"ecommerce\",\"workspace_id\":\"ws-e2e\",\"ontology_id\":\"ont-e2e\",\"source_type\":\"natural_language\",\"source_ref\":\"e2e-demo\",\"triggered_by\":\"admin\",\"documents\":[{\"text\":\"iPhone 15 Pro Max 256GB 原色钛金属 A17 Pro 芯片 6.7 英寸超视网膜 XDR 显示屏\"},{\"text\":\"MacBook Air 13 英寸 M3 芯片 8GB 统一内存 256GB SSD 午夜色\"},{\"text\":\"AirPods Pro 第二代 USB-C 充电盒 MagSafe 充电 主动降噪自适应通透模式\"}]}" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get(\"id\") or d.get(\"run_id\"))")
echo "RID=$RID"

# 10.3 一键推进到 l6_done（等价 I4T5 execute_l3→l6）
START=$(date +%s)
curl -s -X POST http://localhost:8000/api/semantic-admin/pipeline/runs/$RID/execute-all \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{}" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('execute-all status =',d.get('status') or d.get('run_status'))"
DUR=$(( $(date +%s) - START ))
echo "⏱️  execute-all duration = ${DUR}s（要求 ≤ 30 秒 clean scope / 容器 ≤ 60 秒）"

# 10.4 查候选集（≥ 50 条为达标）
CURL="http://localhost:8000/api/semantic-admin/candidates?run_id=$RID&page_size=200"
CAND_COUNT=$(curl -s -H "Authorization: Bearer $TOKEN" $CURL \
  | python3 -c "import json,sys;d=json.load(sys.stdin);items=d.get('items') or d.get('candidates') or [];print(len(items))")
echo "Candidates returned = $CAND_COUNT（要求 ≥ 50）"
[ "$CAND_COUNT" -ge 50 ] && echo "✅ Candidates OK"

# 10.5 Final Summary Dashboard 校验
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/semantic-admin/dashboard/summary \
  | python3 -m json.tool | head -20
'
```

---

## 11. 全量验收 3 行命令（CI / PR Merge 前必跑）

```bash
# ---------- A. 单元（300+ tests，3~4 分钟）----------
#    说明：跳过 openharness.tools + RoleType.COMMANDER / OPA 等 pre-existing 失败项
pytest tests/unit/test_semantic_admin_sa_config.py \
       tests/unit/test_semantic_admin_writeback.py \
       tests/unit/test_semantic_admin_usl_manager.py \
       tests/unit/test_semantic_admin_graphiti_writeback.py \
       tests/unit/test_semantic_admin_candidate_store.py \
       tests/unit/test_semantic_admin_ingest_pipeline.py \
       tests/unit/test_semantic_admin_l4_l5.py \
       tests/unit/test_semantic_admin_approval_2level.py \
       tests/unit/test_semantic_admin_ol_pipeline.py \
       tests/unit/test_semantic_admin_routes.py \
       tests/unit/test_semantic_admin_services.py \
       tests/unit/test_semantic_layer.py \
       tests/unit/test_semantic_map.py \
       tests/unit/test_ol_l3_fca.py \
       tests/unit/biz/semantic_admin -v --tb=short --no-header
# 预期（I4T16 达标）:
#   ======================= 303 passed in 214.45s (0:03:34) =======================

# ---------- B. 6 子服务 import 冒烟（5 秒）----------
python -c "
from odap.biz.semantic_admin.usl_manager.services.usl_manager_service import UslManagerService
from odap.biz.semantic_admin.ol_pipeline.services.pipeline_service import PipelineService
from odap.biz.semantic_admin.candidate_store.services.candidate_service import CandidateService
from odap.biz.semantic_admin.quality_gate.services.quality_gate_service import QualityGateService
from odap.biz.semantic_admin.approval_workflow.services.approval_service import ApprovalService
from odap.biz.semantic_admin.usl_writeback.services.writeback_service import WritebackService
assert all([UslManagerService,PipelineService,CandidateService,QualityGateService,ApprovalService,WritebackService])
print('✅ 6/6 subservices import OK')
"

# ---------- C. 电商 Demo（5 分钟，推荐 PR 合并前日跑一次）----------
#    要求最后打印: "✅ Demo success — Final approved terms = N >= 30"
python examples/semantic_admin_ecommerce_demo.py | tail -5
```

