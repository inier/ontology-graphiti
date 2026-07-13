# Contract: API Contracts — 21 个 HTTP 接口完整契约

**分组**:
- **A 组**: `/usl/*` — 9 个 CRUD 接口（domains / terms / hierarchy / property-specs / disjoint-pairs / cardinality）
- **B 组**: `/pipeline/*` + `/candidates/*` — 7 个 Pipeline + Candidate 接口
- **C 组**: `/quality-gate/*` + `/approval/*` + `/dashboard/*` — 5 个质量门 + 审批 + 仪表盘接口

**全局前缀**: 所有 API 路径默认挂载于 `/api/semantic-admin/` 下（如 `/api/semantic-admin/usl/domains`、`/api/semantic-admin/pipeline/runs`、`/api/semantic-admin/candidates`、`/api/semantic-admin/quality-gate/reports`、`/api/semantic-admin/approval/tasks`、`/api/semantic-admin/dashboard/summary`）。
**全局 Content-Type**: `application/json`。
**全局鉴权**: `Authorization: Bearer <JWT>`；无 Token → 401；角色不满足 → 403。
**全局分页**: 列表接口支持 `?page=1&page_size=50`（page_size max=500）。
**全局时间格式**: ISO-8601 UTC（`2026-07-11T15:30:00Z`）。

---

## Group A: `/usl/*` — 9 个 CRUD 接口

### A1. `GET /usl/domains` — Domain 列表

| 项 | 内容 |
|----|------|
| **Method** | GET |
| **权限** | `user/guest`（全局，JWT ws_role 域内含 viewer 语义）及以上 |
| **Depends** | `require_role(["user", "guest", "editor", "schema_auditor", "director", "analyst", "admin"])`（JWT `ws_role` claim 域内角色：viewer/term_editor/domain_editor/reviewer/super_admin） |
| **Query** | `page: int = 1`；`page_size: int = 50`；`q: str | None = None`（按 display_name 模糊搜索） |
| **Request Pydantic** | `DomainListQuery(page: int=Field(ge=1), page_size:int=Field(ge=1,le=500), q:str\|None)` |
| **成功响应 200** | `{"total": int, "items": [DomainResponse]}` |
| **DomainResponse 字段** | `id: str`；`display_name: str`；`description: str \| None`；`en_mapping_count: int`；`term_count: int`；`created_at: datetime`；`updated_at: datetime` |
| **4xx/5xx** | 401 `AUTH_REQUIRED`；403 `ROLE_DENIED`；500 `DB_ERROR` |

### A2. `POST /usl/domains` — 创建 Domain

| 项 | 内容 |
|----|------|
| **Method** | POST |
| **权限** | `editor`（全局，JWT ws_role 域内含 domain_editor 语义） + `admin`（全局L2终审，JWT ws_role 域内含 super_admin 语义） |
| **Request Pydantic** | `DomainCreate(domain_id: str=Field(min_length=2,max_length=64,pattern="^[a-z0-9_]+$"), display_name: str=Field(min_length=1,max_length=128), description: str \| None = None, en_mapping: dict[str,str] \| None = {})` |
| **成功响应 201** | `DomainResponse` + `Location: /api/semantic-admin/usl/domains/{id}` |
| **4xx/5xx** | 400 `INVALID_DOMAIN_ID`（正则不匹配）；409 `DOMAIN_ID_EXISTS`；401/403/500 同上 |

### A3. `PATCH /usl/domains/{domain_id}` / `DELETE /usl/domains/{domain_id}` — 更新/删除 Domain

| 项 | 内容（合并 PATCH + DELETE） |
|----|------|
| **Method** | PATCH / DELETE |
| **权限** | PATCH: `editor+`（全局，JWT ws_role 域内含 domain_editor 语义）；DELETE: `admin only`（全局L2终审，JWT ws_role 域内含 super_admin 语义） |
| **PATCH Request** | `DomainUpdate(display_name: str\|None, description: str\|None, en_mapping: dict\|None)` — 全字段 optional |
| **成功响应** | PATCH 200: `DomainResponse`；DELETE 204: Empty |
| **4xx/5xx** | 404 `DOMAIN_NOT_FOUND`；400 `DELETE_WITH_CHILDREN`（仍有 terms 时）；401/403/500 |

### A4. `GET /usl/domains/{domain_id}/terms` — Term 列表（按 domain）

| 项 | 内容 |
|----|------|
| **Method** | GET |
| **权限** | `user/guest`（全局，JWT ws_role 域内含 viewer 语义）及以上 |
| **Query** | `page`；`page_size`；`q: str\|None`（按 canonical + synonym LIKE）；`include_synonyms: bool = True`；`parent_id: str\|None`（层级筛选） |
| **Request Pydantic** | `TermListQuery(...)` |
| **成功响应 200** | `{"total": int, "items": [TermResponse]}` |
| **TermResponse 字段** | `id: str`；`domain_id: str`；`canonical: str`；`synonyms: list[str]`；`near_synonyms: list[str]`；`aliases: list[str]`；`hint_parents: list[str]`；`en: str\|None`；`term_rank: float`（0-1）；`created_at/updated_at` |
| **4xx/5xx** | 404 `DOMAIN_NOT_FOUND`；401/403/500 |

### A5. `POST /usl/domains/{domain_id}/terms` — 创建 Term

| 项 | 内容 |
|----|------|
| **Method** | POST |
| **权限** | `editor`（全局，JWT ws_role 域内含 term_editor 语义） + |
| **Request Pydantic** | `TermCreate(canonical: str=Field(min_length=1), synonyms: list[str]=[], near_synonyms: list[str]=[], aliases: list[str]=[], hint_parents: list[str]=[], en: str\|None=None, term_rank: float=Field(ge=0,le=1,default=0.5))` |
| **成功响应 201** | `TermResponse` |
| **4xx/5xx** | 400 `EMPTY_CANONICAL`；409 `TERM_DUPLICATE`（同 domain 同 canonical）；404 `DOMAIN_NOT_FOUND`；401/403/500 |

### A6. `PATCH /usl/terms/{term_id}` / `DELETE /usl/terms/{term_id}` — 更新/删除 Term（与 A3 同模式）

| 项 | 内容 |
|----|------|
| **Method** | PATCH / DELETE |
| **权限** | PATCH: `editor+`（全局，JWT ws_role 域内含 term_editor 语义）；DELETE: `editor+`（全局，JWT ws_role 域内含 domain_editor 语义） |
| **PATCH Request** | `TermUpdate(canonical?, synonyms?, near_synonyms?, aliases?, hint_parents?, en?, term_rank?)` |
| **成功响应** | PATCH 200 `TermResponse`；DELETE 204 |
| **4xx/5xx** | 404 `TERM_NOT_FOUND`；400 `TERM_IN_USE`（仍被 hierarchy 引用时）；401/403/500 |

### A7. `POST /usl/hierarchy` + `GET /usl/hierarchy` + `DELETE /usl/hierarchy/{edge_id}` — 层级边 CRUD

| 项 | 内容（合并 3 个接口） |
|----|------|
| **Method** | POST / GET / DELETE |
| **权限** | POST/DELETE: `editor+`（全局，JWT ws_role 域内含 term_editor 语义）；GET: `user/guest+`（全局，JWT ws_role 域内含 viewer 语义） |
| **POST Request** | `HierarchyCreate(domain_id: str, parent_term_id: str, child_term_id: str, edge_type: Literal["is_a","part_of","instance_of"] = "is_a", weight: float=Field(ge=0,le=1,default=1.0))` |
| **GET Query** | `domain_id: str`；`root_id: str\|None`（以 root 为根返回整个子树，默认返回全量）；`depth: int=Field(ge=1,le=10,default=5)` |
| **HierarchyResponse** | `id: str`；`domain_id`；`parent_term_id/canonical_parent`；`child_term_id/canonical_child`；`edge_type`；`weight`；`depth_from_root`；`created_at` |
| **成功响应** | POST 201；GET 200 `{"edges": [HierarchyResponse], "tree": NestedTree }`；DELETE 204 |
| **4xx/5xx** | 400 `CYCLE_DETECTED`；404 `TERM_NOT_FOUND`（parent/child 任一不存在）；409 `EDGE_DUPLICATE`；401/403/500 |

### A8. `POST /usl/property-specs` + `GET /usl/property-specs` + `PATCH /DELETE` — PropertySpec CRUD

| 项 | 内容（合并） |
|----|------|
| **Method** | POST / GET / PATCH / DELETE |
| **权限** | `editor+`（全局，JWT ws_role 域内含 domain_editor 语义）写；`user/guest+`（全局，JWT ws_role 域内含 viewer 语义）读 |
| **Spec 核心字段** | `domain_id: str`；`target_term_id: str\|None`（None=domain 全局）；`prop_name: str`；`data_type: Literal["STRING","INTEGER","FLOAT","BOOLEAN","DATETIME","ENUM","JSON"]`；`required: bool=False`；`default_value: Any\|None`；`enum_values: list[str]\|None`；`min_val/max_val: float\|None`；`description: str\|None` |
| **Request Pydantic** | `PropertySpecCreate`/`PropertySpecUpdate`（与字段对齐，必填校验） |
| **成功响应** | POST 201 `PropertySpecResponse`；GET 200 列表 + total；PATCH 200；DELETE 204 |
| **4xx/5xx** | 400 `INVALID_DATATYPE_DEFAULT`（default 类型不匹配）；400 `ENUM_VALUES_REQUIRED`（ENUM 型未填 enum_values）；404；401/403；500 |

### A9. `POST /usl/disjoint-pairs` + `GET /usl/disjoint-pairs` + `DELETE`；`POST /usl/cardinality` + `GET` + `DELETE` — 不相交对 + 基数约束（双资源合并）

| 项 | 内容 |
|----|------|
| **DisjointPair 接口** | `POST /usl/disjoint-pairs`；`GET /usl/disjoint-pairs?domain_id=`；`DELETE /usl/disjoint-pairs/{id}` |
| **DisjointPair 字段** | `domain_id`；`term_a_id`；`term_b_id`；`strict: bool=True`（True=严格互斥 False=弱互斥） |
| **DisjointPair 4xx** | 400 `PAIR_SAME_TERM`（A=B）；409 `PAIR_DUPLICATE`；404 |
| **Cardinality 接口** | `POST /usl/cardinality`；`GET /usl/cardinality?domain_id=&term_id=`；`DELETE /usl/cardinality/{id}` |
| **Cardinality 字段** | `domain_id`；`source_term_id`；`relation_name: str`；`target_term_id: str\|None`；`min_card: int=Field(ge=0,default=0)`；`max_card: int\|None=Field(ge=0,default=None)`（None=无限） |
| **Cardinality 4xx** | 400 `MIN_GT_MAX`；400 `NEGATIVE_CARDINALITY`；409 `CARD_DUPLICATE`；404；401/403；500 |

---

## Group B: `/pipeline/*` 3 + `/candidates/*` 4 = 7 接口

### B1. `POST /pipeline/runs` — 启动新 Pipeline Run

| 项 | 内容 |
|----|------|
| **Method** | POST |
| **权限** | `editor`（全局，JWT ws_role 域内含 term_editor 语义） + |
| **Request Pydantic** | `PipelineRunCreate(domain_id: str, name: str=Field(min_length=1,max_length=128), text_sources: list[TextSource] = Field(min_length=1), auto_execute_until: Literal["l1","l2","l3","l4","l5","l6","manual"] = "manual")`；嵌套 `TextSource(source_type: Literal["raw_text","file_id","url"], content: str)` |
| **成功响应 201** | `PipelineRunResponse` + Location 头 |
| **PipelineRunResponse 字段** | `run_id: str`；`name`；`domain_id`；`status: str in PENDING_ENUM`；`current_step: Literal["l1","l2","l3","l4","l5","l6","done","failed"]`；`metrics_json: dict`；`text_sources: list[TextSource]`；`started_at/finished_at: datetime\|None`；`error_message: str\|None` |
| **4xx/5xx** | 400 `NO_TEXT_SOURCES`（空列表）；400 `EMPTY_CONTENT`；404 `DOMAIN_NOT_FOUND`；401/403/500 |

### B2. `GET /pipeline/runs/{run_id}` — 查询 Run 状态 + 指标

| 项 | 内容 |
|----|------|
| **Method** | GET |
| **权限** | `user/guest+`（全局，JWT ws_role 域内含 viewer 语义） |
| **Query** | `include_metrics: bool=True`；`include_step_details: bool=False` |
| **成功响应 200** | `PipelineRunResponse` + `step_details: list[StepDetail]`（当后者 true） |
| **StepDetail 字段** | `step_name: Literal["l1","l2","l3","l4","l5","l6"]`；`status: Literal["pending","running","done","failed","skipped"]`；`started_at/finished_at`；`elapsed_ms: int`；`record_count: int`；`confidence_distribution: {"0-0.2": int, "0.2-0.4": int, ..., "0.8-1.0": int}`；`error_message: str\|None` |
| **4xx/5xx** | 404 `RUN_NOT_FOUND`；401/403/500 |

### B3. `POST /pipeline/runs/{run_id}/advance` + `POST /pipeline/runs/{run_id}/execute-all` — 推进/全自动

| 项 | 内容（合并） |
|----|------|
| **advance** | Body 可选 `target_step: Literal["l1","l2","l3","l4","l5","l6"]`（默认=下一步）；幂等：已完成状态直接返回原 Response |
| **execute-all** | Body 可选 `fail_fast: bool=True`；无 target_step 参数 |
| **成功响应** | 200 `PipelineRunResponse`（含更新后 status + step_details） |
| **4xx/5xx** | 404 `RUN_NOT_FOUND`；409 `RUN_ALREADY_FINISHED`（对于 advance 且已 approved/rejected）；400 `STEP_OUT_OF_ORDER`；500 `STEP_EXECUTION_ERROR`（error_message 填 traceback 摘要） |

### B4. `GET /candidates` — Candidate 列表（按 Run / Status / Term 过滤）

| 项 | 内容 |
|----|------|
| **Method** | GET |
| **权限** | `user/guest+`（全局，JWT ws_role 域内含 viewer 语义） |
| **Query** | `run_id: str\|None`；`status: Literal["pending","audited","modified","rejected","final_approved","auto_skipped_admin","promoted","deleted"] \| None`（可多值 `status=X&status=Y`）；`canonical_q: str\|None`；`confidence_ge: float=0.0`；`source_step: Literal["l1","l2","l3","l4","l5"] \| None`；`page/page_size` |
| **Request Pydantic** | `CandidateListQuery(...)` |
| **成功响应 200** | `{"total": int, "items": [CandidateResponse]}` |
| **CandidateResponse 字段** | `id: str`；`run_id`；`domain_id`；`canonical_term: str`；`synonyms: list[str]`；`hint_parents: list[str]`；`confidence: float(0-1)`；`source_step: str\|None`；`status`；`rejected: bool`；`rejection_reason: str\|None`；`quality_score: float\|None`（quality_gate 评估后填）；`created_at/updated_at` |
| **4xx/5xx** | 400 `INVALID_STATUS_ENUM`；401/403/500 |

### B5. `PATCH /candidates/{cand_id}` — 修改 Candidate（编辑 canonical/synonyms/parents）

| 项 | 内容 |
|----|------|
| **Method** | PATCH |
| **权限** | `editor`（全局，JWT ws_role 域内含 term_editor 语义） +（仅 pending/audited/modified 状态可改） |
| **Request Pydantic** | `CandidatePatch(canonical_term: str\|None=Field(min_length=1), synonyms: list[str]\|None, hint_parents: list[str]\|None, confidence: float\|None=Field(ge=0,le=1), editor_note: str\|None)` |
| **成功响应 200** | `CandidateResponse` + 写 audit_log（`modification_count += 1`） |
| **4xx/5xx** | 404 `CANDIDATE_NOT_FOUND`；409 `STATUS_NOT_EDITABLE`（rejected/final_approved 等）；400 `EMPTY_CANONICAL`；401/403/500 |

### B6. `POST /candidates/{cand_id}/reject` — 驳回 Candidate

| 项 | 内容 |
|----|------|
| **Method** | POST |
| **权限** | `schema_auditor+`（全局L1初审，JWT ws_role 域内含 reviewer 语义） |
| **Body** | `CandidateReject(reason: str=Field(min_length=5,max_length=500))` |
| **成功响应 200** | `CandidateResponse`（`status="rejected"`, `rejected=True`, `rejection_reason` 填入） |
| **副作用** | 若存在关联 approval_task → task.status = rejected；记录 audit_log |
| **4xx/5xx** | 404；409 `ALREADY_REJECTED`；400 `SHORT_REASON`；401/403/500 |

### B7. `POST /candidates/{cand_id}/promote-to-usl` — 手动升为正式 USL Term（不经审批流）

| 项 | 内容 |
|----|------|
| **Method** | POST |
| **权限** | `admin only`（全局L2终审，JWT ws_role 域内含 super_admin 语义） |
| **Body** | `PromoteOptions(force_overwrite: bool=False, parent_term_id: str\|None=None)` |
| **成功响应 201** | `{"usl_term_id": str, "created_new": bool, "overwrote_existing": bool}` + 返回完整 `TermResponse` |
| **语义** | canonical + domain_id → 查 `usl_terms`：存在且 force_overwrite=False → 409 `TERM_EXISTS`；存在且 True → 更新 synonyms/parents 并返回 overwrote_existing=True；不存在 → 新建 |
| **4xx/5xx** | 404；409 `TERM_EXISTS`；403 `ADMIN_ONLY`；500 `PROMOTE_FAILED` |

---

## Group C: `/quality-gate/*` 2 + `/approval/*` 2 + `/dashboard/*` 1 = 5 接口

### C1. `GET /quality-gate/reports/{cand_id}` — 获取 QualityGate 16 指标报告

| 项 | 内容 |
|----|------|
| **Method** | GET |
| **权限** | `user/guest+`（全局，JWT ws_role 域内含 viewer 语义） |
| **Query** | `force: bool=False`（True=缓存未过期也重新跑 evaluate） |
| **成功响应 200** | `QualityReportResponse` |
| **QualityReportResponse 字段** | `report_id: str`；`candidate_id`；`run_id`；`generated_at`；`gate1_score/gate2_score/gate3_score: float` 各 0-1；`total_score: float = 0.35*g1 + 0.40*g2 + 0.25*g3`（权重 w1=0.35 / w2=0.40 / w3=0.25）；`submetrics: Quality16Submetrics`；`overall: Literal["PASS","REVIEW","FAIL"]`（PASS ≥ 0.8；REVIEW 0.5-0.8；FAIL < 0.5）；`recommend_auto_skip: bool`（≥ 0.9 且 reviewer=admin/L2终审 → True） |
| **Quality16Submetrics 字段** | Gate1(7): `g1_name_valid`, `g1_en_mapping_valid`, `g1_semantic_type_valid`, `g1_synonyms_size_valid`, `g1_synonyms_dedup_ratio`, `g1_circular_inclusion_free`, `g1_usl_duplicate_check`；Gate2(4): `g2_usl_disjointness`, `g2_cardinality_constraint`, `g2_isa_acyclic`, `g2_llm_semantic_judge`（注：g2_llm_semantic_judge 默认关闭，按需启用）；Gate3(5): `g3_property_density`, `g3_term_frequency_coverage`, `g3_synonym_richness`, `g3_usl_alignment_novelty`, `g3_hierarchy_contribution`；合计 7+4+5=16 子指标；每个子指标 = `{score: float(0-1), reason: str, rule_name: str, threshold: float}` |
| **4xx/5xx** | 404 `CANDIDATE_NOT_FOUND`；500 `EVALUATION_ERROR`（含 details）；401/403 |

### C2. `POST /quality-gate/reports` — 主动触发重新评估（批量 or 单 ID）

| 项 | 内容 |
|----|------|
| **Method** | POST |
| **权限** | `schema_auditor+`（全局L1初审，JWT ws_role 域内含 reviewer 语义） |
| **Body** | `EvaluateRequest(candidate_ids: list[str]=Field(min_length=1, max_length=100), sync: bool=True)`（sync=False 返回 task_id 轮询） |
| **成功响应** | sync=True 200: `{"generated": int, "reports": [QualityReportResponse]}`；sync=False 202: `{"async_task_id": str, "estimated_seconds": int}` |
| **4xx/5xx** | 400 `EMPTY_CANDIDATE_IDS`；404 `CANDIDATE_NOT_FOUND`（任一 ID 不存在则整批失败）；413 `TOO_MANY_IDS`；500；401/403 |

### C3. `GET /approval/tasks` — 审批待办列表（按角色/状态过滤）

| 项 | 内容 |
|----|------|
| **Method** | GET |
| **权限** | `schema_auditor+`（全局L1初审，JWT ws_role 域内含 reviewer 语义） |
| **Query** | `assigned_role: SemanticRoleEnum\|None`（对应 ws_role 域内角色：viewer/term_editor/domain_editor/reviewer/super_admin）；`status: ApprovalTaskStatus\|None`（多值）；`assignee_user_id: str\|None`；`domain_id: str\|None`；`order_by: Literal["created_at","priority"] = "created_at"`；`page/page_size` |
| **成功响应 200** | `{"total": int, "items": [ApprovalTaskResponse]}` |
| **ApprovalTaskResponse 字段** | `id: str`；`candidate_id` + 嵌套 `CandidateResponse`（摘要 canonical/confidence/domain）；`report_id` + `quality_total_score: float\|None`；`assigned_role: SemanticRoleEnum`；`assignee_user_id: str\|None`；`status: ApprovalTaskStatus`；`reviewer_comment: str\|None`；`comments: list[AuditComment]`（历史对话）；`created_at`；`resolved_at: datetime\|None`；`sla_deadline: datetime`（created + 48h，可配置）；`overdue: bool` |
| **4xx/5xx** | 400 `INVALID_ROLE`；401/403/500 |

### C4. `POST /approval/tasks/{task_id}/audit|modify|reject|final-approve` — 审批 4 动作（合并）

| 项 | 内容 |
|----|------|
| **URL Pattern** | 4 个端点共享 `task_id` + Body 结构 |
| **audit Body** | `AuditRequest(comment: str=Field(min_length=3), decisions: list[SubmetricDecision] = [])`；嵌套 `SubmetricDecision(submetric_name: str, accepted: bool, note: str)`；task 状态 audited |
| **modify Body** | `ModifyRequest(candidate_patch: CandidatePatch, editor_comment: str=Field(min_length=3))` → 内部调 B5 PATCH → 重新 evaluate → task 状态 modified |
| **reject Body** | `RejectRequest(reason: str=Field(min_length=10), close_task: bool=True)` → 调 B6 POST reject；task rejected |
| **final-approve Body** | `FinalApproveRequest(comment: str=Field(min_length=5), auto_promote: bool=True, writeback_now: bool=True)` → `admin only`（全局L2终审，JWT ws_role 域内含 super_admin 语义）；task final_approved；若 auto_promote=True 调 B7；writeback_now=True 调 `OntologyWritebackService` |
| **成功响应 200** | `ApprovalTaskResponse`（更新后状态 + 最新 report） |
| **4xx/5xx** | 404 `TASK_NOT_FOUND`；409 `TASK_NOT_PENDING`；403 `ROLE_DENIED`（如 final-approve 非 admin/L2终审）；400 `SHORT_COMMENT`；500 |

### C5. `GET /dashboard/summary` + `GET /dashboard/terms-trend` + `GET /dashboard/approvals-breakdown` — Dashboard 3 接口（合并写）

| 项 | 内容（3 端点合并） |
|----|------|
| **权限** | `user/guest+`（全局，JWT ws_role 域内含 viewer 语义） |
| **/summary 响应 200** | `DashboardSummary(total_domains: int, total_terms: int, total_hierarchy_edges: int, approved_candidates_this_week: int, pipeline_runs_7d_success_rate: float, pending_approval_count: int, rejected_this_week: int, usl_writeback_count_30d: int)`；全部字段非负 int 或 float(0-1) |
| **/terms-trend Query** | `days: int=Field(ge=7,le=180,default=30)`；`domain_id: str\|None` |
| **/terms-trend 响应** | `DailyTermBucket(date: str(YYYY-MM-DD), new_term_count: int, approved_candidate_count: int, promoted_count: int)` 列表，长度 = days，0 填充 |
| **/approvals-breakdown 响应** | `ApprovalsBreakdown(status_counts: dict[str,int], role_counts: dict[str,int], avg_approval_hours_by_role: dict[str,float], sla_violation_rate: float, top_5_slowest_domain_terms: list[{domain_id, avg_hours, sample_count}])` |
| **4xx/5xx** | 400 `DAYS_OUT_OF_RANGE`；401/403/500 |

---

## 21 API 索引汇总表

| 编号 | Method | Path | 分组 | 权限下界（全局 RoleType + JWT ws_role 域内角色说明） |
|------|--------|------|------|------------------------------------------------|
| A1 | GET | `/usl/domains` | A USL | user/guest（ws_role=viewer） |
| A2 | POST | `/usl/domains` | A USL | editor（ws_role=domain_editor） / admin（ws_role=super_admin） |
| A3 | PATCH/DELETE | `/usl/domains/{id}` | A USL | editor（ws_role=domain_editor） / admin（ws_role=super_admin，Del） |
| A4 | GET | `/usl/domains/{id}/terms` | A USL | user/guest（ws_role=viewer） |
| A5 | POST | `/usl/domains/{id}/terms` | A USL | editor（ws_role=term_editor） |
| A6 | PATCH/DELETE | `/usl/terms/{id}` | A USL | editor（ws_role=term_editor） / editor（ws_role=domain_editor，Del） |
| A7 | POST/GET/DELETE | `/usl/hierarchy[...]` | A USL | editor（ws_role=term_editor，写） / user/guest（ws_role=viewer，读） |
| A8 | CRUD | `/usl/property-specs` | A USL | editor（ws_role=domain_editor） |
| A9 | CRUD×2 | `/usl/disjoint-pairs` + `/usl/cardinality` | A USL | editor（ws_role=domain_editor） |
| B1 | POST | `/pipeline/runs` | B Pipeline | editor（ws_role=term_editor） |
| B2 | GET | `/pipeline/runs/{id}` | B Pipeline | user/guest（ws_role=viewer） |
| B3 | POST×2 | `/pipeline/runs/{id}/advance` + `/execute-all` | B Pipeline | editor（ws_role=term_editor） |
| B4 | GET | `/candidates` | B Candidates | user/guest（ws_role=viewer） |
| B5 | PATCH | `/candidates/{id}` | B Candidates | editor（ws_role=term_editor） |
| B6 | POST | `/candidates/{id}/reject` | B Candidates | schema_auditor（ws_role=reviewer，L1初审） |
| B7 | POST | `/candidates/{id}/promote-to-usl` | B Candidates | admin（ws_role=super_admin，L2终审） |
| C1 | GET | `/quality-gate/reports/{cand_id}` | C Quality | user/guest（ws_role=viewer） |
| C2 | POST | `/quality-gate/reports` | C Quality | schema_auditor（ws_role=reviewer，L1初审） |
| C3 | GET | `/approval/tasks` | C Approval | schema_auditor（ws_role=reviewer，L1初审） |
| C4 | POST×4 | `/approval/tasks/{id}/audit\|modify\|reject\|final-approve` | C Approval | schema_auditor（ws_role=reviewer，L1初审） / admin（ws_role=super_admin，L2终审，final） |
| C5 | GET×3 | `/dashboard/summary` + `/terms-trend` + `/approvals-breakdown` | C Dashboard | user/guest（ws_role=viewer） |

**合计**: Group A=9, Group B=7, Group C=5 → **21 个 API**。

---

## 全局错误枚举表（4xx/5xx code + error_code + message 模板）

| HTTP Code | error_code | message 模板 | 可能出现在 |
|-----------|------------|-------------|-----------|
| 400 | VALIDATION_ERROR | `{loc}: {msg}` (Pydantic 默认，但包装为 `{"detail":[{"type":"...","loc":[...],"msg":"..."}]}`) | 所有 Request 校验失败 |
| 400 | EMPTY_CANONICAL | 规范术语 canonical 不得为空 | A5, B5 |
| 400 | INVALID_DOMAIN_ID | domain_id 仅允许小写字母/数字/下划线，长度 2-64 | A2 |
| 400 | CYCLE_DETECTED | 检测到层级环: {path} | A7 |
| 400 | MIN_GT_MAX | min_card({min}) > max_card({max}) | A9 |
| 400 | STEP_OUT_OF_ORDER | 当前步骤={cur}，请求目标={tgt}，不允许跳过多步未执行 | B3 |
| 400 | SHORT_REASON / SHORT_COMMENT | reason/comment 长度不足（要求 {n} 字符） | B6, C4 |
| 401 | AUTH_REQUIRED | 未提供 Authorization Bearer Token | 全局 |
| 401 | TOKEN_EXPIRED | Token 已过期 | 全局 |
| 403 | ROLE_DENIED | 当前用户角色={role}（ws_role={ws_role}），需要任一角色={allowed} | 全局 Depends 守卫 |
| 403 | ADMIN_ONLY | 该操作仅允许 admin（全局L2终审，ws_role=super_admin）角色 | B7, C4-final |
| 404 | DOMAIN_NOT_FOUND | domain_id={id} 不存在 | A4-A9, B1 |
| 404 | TERM_NOT_FOUND | term_id={id} 不存在 | A6, A7, A8 |
| 404 | CANDIDATE_NOT_FOUND | candidate_id={id} 不存在 | B5-B7, C1-C2 |
| 404 | RUN_NOT_FOUND | run_id={id} 不存在 | B2-B3 |
| 404 | TASK_NOT_FOUND | task_id={id} 不存在 | C4 |
| 409 | DOMAIN_ID_EXISTS | domain_id={id} 已存在 | A2 |
| 409 | TERM_DUPLICATE | 同 domain={did} 下 canonical={c} 已存在 | A5 |
| 409 | EDGE_DUPLICATE | 层级边 (parent={p},child={c}) 已存在 | A7 |
| 409 | PAIR_SAME_TERM | disjoint pair term_a == term_b | A9 |
| 409 | TERM_EXISTS | promote 时 usl 已存在相同 canonical，指定 force_overwrite=True 覆盖 | B7 |
| 409 | STATUS_NOT_EDITABLE | candidate status={s} 不可编辑 | B5 |
| 409 | TASK_NOT_PENDING | task status={s}，仅 pending/audited/modified 可执行该操作 | C4 |
| 409 | RUN_ALREADY_FINISHED | run status={s}，advance 不可回退 | B3 |
| 413 | TOO_MANY_IDS | EvaluateRequest candidate_ids 数量={n}，上限 100 | C2 |
| 500 | DB_ERROR | 数据库操作失败: {detail} | 全局 |
| 500 | STEP_EXECUTION_ERROR | Pipeline 步骤 {step} 执行失败: {traceback} | B3 |
| 500 | EVALUATION_ERROR | QualityGate evaluate 异常: {detail} | C1 |
| 500 | PROMOTE_FAILED | promote-to-usl 内部错误，reason={detail} | B7 |
| 500 | OPA_EVAL_TIMEOUT | OPA Rego 规则评估超时（>5s） | QualityGate OPA 路径 |
